"""通用 async fan-out 编排层。

一个 RStudio 同时驱动 N 个子 R worker，file-poll 轮询每个 worker 的
state/manifest/validation 三件套，动态资源门，并在全部完成后做"自主合并"门禁。

设计要点（与 clauder-rstudio-workbench 的传输证据边界一致）：
- ``run_fanout`` 经 Python MCP stdio 自行提交 + 轮询，evidence 必须标 ``MCP_STDIO_OK``，
  不得冒充 native ``mcp__r_studio__`` wrapper 成功。
- native-wrapper 模式不在此提交：由 ``plan_fanout`` 生成 contract + 提交代码，agent 用 native
  wrapper 提交、``async-guard register-job`` 记录真实 job_id，再用 ``poll_fanout``/``merge_gate``
  读 durable files 验证。

依赖优雅降级：PyYAML / psutil 为可选；缺失时回退到内置最小 YAML 解析与 PowerShell 资源采样。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from .resource import memory_used_percent

WORKER_FILE_KEYS = ("expected_state", "expected_manifest", "expected_validation")


# --------------------------------------------------------------------------- #
# Contract 加载（YAML/JSON，nested workers 支持）
# --------------------------------------------------------------------------- #
def _minimal_yaml(text: str) -> Any:
    """无 PyYAML 时的最小嵌套解析器。

    支持本 skill task.yaml 的子集：标量 ``key: value``、嵌套映射 ``key:`` + 缩进、
    列表 ``- item`` 或 ``- key: value`` 起头的字典列表项。不支持流式/锚点/多行标量。
    """

    def coerce(value: str) -> Any:
        v = value.strip()
        if v == "" or v in {"~", "null", "None"}:
            return None
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        low = v.lower()
        if low in {"true", "false"}:
            return low == "true"
        try:
            if "." not in v and "e" not in low:
                return int(v)
            return float(v)
        except ValueError:
            return v

    # 预处理：剥离注释行/空行，记录 (indent, raw)；遇到不支持的特性立即报错，避免静默误解析
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            continue
        stripped = raw.rstrip()
        if not stripped.strip():
            continue
        body = stripped.strip()
        if body.endswith("|") or body.endswith(">") or body.endswith("|-") or body.endswith(">-"):
            raise ValueError(
                "minimal YAML parser does not support block scalars (|, >); "
                "install PyYAML (pip install '.[fanout]') to use 'code:' blocks in contracts"
            )
        if body.startswith("&") or body.startswith("*"):
            raise ValueError("minimal YAML parser does not support anchors/aliases; install PyYAML")
        if (body.endswith("]") and "[" in body and ":" in body.split("[", 1)[0]) or (
            body.endswith("}") and "{" in body
        ):
            raise ValueError("minimal YAML parser does not support flow-style collections; install PyYAML")
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, body))

    pos = 0

    def parse_block(min_indent: int) -> Any:
        nonlocal pos
        if pos >= len(lines):
            return None
        indent, content = lines[pos]
        if content.startswith("- "):
            return parse_list(indent)
        return parse_map(indent)

    def parse_map(map_indent: int) -> dict[str, Any]:
        nonlocal pos
        result: dict[str, Any] = {}
        while pos < len(lines):
            indent, content = lines[pos]
            if indent < map_indent or content.startswith("- "):
                break
            if indent > map_indent:
                break
            if ":" not in content:
                pos += 1
                continue
            key, _, rest = content.partition(":")
            key = key.strip()
            rest = rest.strip()
            pos += 1
            if rest:
                result[key] = coerce(rest)
            else:
                # 嵌套块：下一行缩进更深则递归
                if pos < len(lines) and lines[pos][0] > map_indent:
                    result[key] = parse_block(lines[pos][0])
                else:
                    result[key] = None
        return result

    def parse_list(list_indent: int) -> list[Any]:
        nonlocal pos
        items: list[Any] = []
        while pos < len(lines):
            indent, content = lines[pos]
            if indent != list_indent or not content.startswith("- "):
                break
            item_body = content[2:].strip()
            if ":" in item_body:
                # 字典列表项：把 "- key: val" 当作该字典的第一行
                key, _, rest = item_body.partition(":")
                entry: dict[str, Any] = {}
                rest = rest.strip()
                if rest:
                    entry[key.strip()] = coerce(rest)
                else:
                    entry[key.strip()] = None
                pos += 1
                # 后续更深缩进的键并入该字典项
                child_indent = list_indent + 2
                if pos < len(lines) and lines[pos][0] > list_indent:
                    child_indent = lines[pos][0]
                while pos < len(lines) and lines[pos][0] >= child_indent and not lines[pos][1].startswith("- "):
                    sub = parse_map(child_indent)
                    entry.update(sub)
                    break
                # 若第一行的值为空且后面是嵌套块（如 env:）
                items.append(entry)
            else:
                items.append(coerce(item_body))
                pos += 1
        return items

    parsed = parse_block(lines[0][0]) if lines else {}
    return parsed or {}


def load_fanout_contract(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"fan-out contract not found: {path}")
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(text)
        except Exception:
            data = _minimal_yaml(text)
    if not isinstance(data, dict):
        raise ValueError(f"contract root must be a mapping, got {type(data).__name__}: {path}")
    data.setdefault("_contract_path", str(p.resolve()))
    return data


# --------------------------------------------------------------------------- #
# 路径解析与 worker 状态
# --------------------------------------------------------------------------- #
def output_root_of(contract: dict[str, Any]) -> str | None:
    artifacts = contract.get("artifacts") or {}
    if isinstance(artifacts, dict):
        return artifacts.get("output_root")
    return None


def resolve_worker_path(contract: dict[str, Any], worker: dict[str, Any], key: str) -> Path | None:
    value = worker.get(key)
    if not value:
        return None
    candidate = Path(str(value))
    if candidate.is_absolute():
        return candidate
    contract_dir = Path(contract.get("_contract_path", ".")).parent
    root = output_root_of(contract)
    if root:
        root_path = Path(root)
        if not root_path.is_absolute():
            # 相对 output_root 必须相对 contract 文件解析，避免随进程 cwd 漂移
            root_path = contract_dir / root_path
        base = root_path
    else:
        base = contract_dir
    return base / candidate


def state_is_complete(state: Any) -> bool:
    """worker state 是否表示完成。与 cli._state_is_complete 语义保持一致。"""
    done = {"complete", "completed", "done", "success", "pass"}
    if isinstance(state, dict):
        for k in ("status", "state", "stage", "decision"):
            if str(state.get(k, "")).lower() in done:
                return True
        if state.get("complete") is True or state.get("completed") is True:
            return True
        return state_is_complete(state.get("progress")) or state_is_complete(state.get("result"))
    if isinstance(state, list):
        return any(state_is_complete(x) for x in state)
    return str(state).strip().lower() in done


def worker_status(
    contract: dict[str, Any],
    worker: dict[str, Any],
    *,
    fresh_after: float | None = None,
    max_age_h: float | None = None,
) -> dict[str, Any]:
    wid = worker.get("id") or "<unknown>"
    files: dict[str, Any] = {}
    for key in WORKER_FILE_KEYS:
        path = resolve_worker_path(contract, worker, key)
        files[key] = {
            "path": str(path) if path else None,
            "exists": bool(path and path.exists()),
        }
    state_path = resolve_worker_path(contract, worker, "expected_state")
    complete = False
    stage = None
    updated_at = None
    fresh = True
    state_mtime = None
    if state_path and state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8-sig"))
            stage = state.get("stage") if isinstance(state, dict) else None
            updated_at = state.get("updated_at") if isinstance(state, dict) else None
            complete = state_is_complete(state)
            state_mtime = state_path.stat().st_mtime
            if fresh_after is not None and state_mtime < fresh_after:
                fresh = False
            if max_age_h is not None and (time.time() - state_mtime) / 3600 > max_age_h:
                fresh = False
        except Exception as exc:
            stage = f"<state read error: {exc}>"
    manifest_ok = files["expected_manifest"]["exists"]
    validation_ok = files["expected_validation"]["exists"]
    done = bool(complete and manifest_ok and validation_ok and fresh)
    return {
        "id": wid,
        "complete": done,
        "state_complete": complete,
        "fresh": fresh,
        "manifest_exists": manifest_ok,
        "validation_exists": validation_ok,
        "stage": stage,
        "updated_at": updated_at,
        "state_mtime": state_mtime,
        "files": files,
    }


# --------------------------------------------------------------------------- #
# 规划
# --------------------------------------------------------------------------- #
def _validate_contract(contract: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    workers = contract.get("workers")
    if not isinstance(workers, list) or not workers:
        problems.append("contract.workers must be a non-empty list")
        return problems
    seen: set[str] = set()
    for i, w in enumerate(workers):
        if not isinstance(w, dict):
            problems.append(f"worker[{i}] must be a mapping")
            continue
        wid = w.get("id")
        if not wid:
            problems.append(f"worker[{i}] missing id")
        elif wid in seen:
            problems.append(f"duplicate worker id: {wid}")
        else:
            seen.add(wid)
        if not w.get("code_file") and not w.get("code"):
            problems.append(f"worker {wid or i} must set code_file or code")
        for key in WORKER_FILE_KEYS:
            if not w.get(key):
                problems.append(f"worker {wid or i} missing {key}")
    return problems


def plan_fanout(contract: dict[str, Any], *, advise_parallel: bool = True) -> dict[str, Any]:
    problems = _validate_contract(contract)
    workers = contract.get("workers") or []
    rg = contract.get("resource_gate") or {}
    memory_threshold = float(rg.get("memory_threshold", 85.0)) if isinstance(rg, dict) else 85.0
    requested = contract.get("max_parallel")
    recommended = requested
    advice_reason = "max_parallel taken from contract"
    if advise_parallel and not requested:
        mem = memory_used_percent()
        if mem is None:
            recommended = 1
            advice_reason = "memory unknown; conservative start at 1"
        elif mem >= memory_threshold:
            recommended = 1
            advice_reason = f"memory {mem:.1f}% >= threshold; start at 1"
        else:
            recommended = min(len(workers), 3)
            advice_reason = f"memory {mem:.1f}% < threshold; conservative start min(workers,3)"
    worker_plans = []
    for w in workers if isinstance(workers, list) else []:
        if not isinstance(w, dict):
            continue
        worker_plans.append(
            {
                "id": w.get("id"),
                "code_file": w.get("code_file"),
                "expected_state": str(resolve_worker_path(contract, w, "expected_state") or ""),
                "expected_manifest": str(resolve_worker_path(contract, w, "expected_manifest") or ""),
                "expected_validation": str(resolve_worker_path(contract, w, "expected_validation") or ""),
            }
        )
    return {
        "ok": not problems,
        "problems": problems,
        "task_key": contract.get("task_key"),
        "worker_count": len(worker_plans),
        "requested_max_parallel": requested,
        "recommended_max_parallel": recommended,
        "advice_reason": advice_reason,
        "memory_threshold": memory_threshold,
        "output_root": output_root_of(contract),
        "workers": worker_plans,
    }


# --------------------------------------------------------------------------- #
# 提交代码构造
# --------------------------------------------------------------------------- #
def build_submit_code(worker: dict[str, Any]) -> str:
    """构造提交给 execute_r_async 的 R 代码。"""
    if worker.get("code"):
        return str(worker["code"])
    code_file = str(worker["code_file"]).replace("\\", "/")
    lines = ['options(encoding = "UTF-8")']
    env = worker.get("env") or {}
    if isinstance(env, dict):
        for key, value in env.items():
            lines.append(f"Sys.setenv({json.dumps(str(key))} = {json.dumps(str(value), ensure_ascii=False)})")
    lines.append(f'source({json.dumps(code_file, ensure_ascii=False)}, encoding = "UTF-8", local = FALSE)')
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 轮询 / 运行 / merge-gate
# --------------------------------------------------------------------------- #
def poll_once(
    contract: dict[str, Any],
    *,
    fresh_after: float | None = None,
    max_age_h: float | None = None,
) -> dict[str, Any]:
    workers = [w for w in (contract.get("workers") or []) if isinstance(w, dict)]
    statuses = [worker_status(contract, w, fresh_after=fresh_after, max_age_h=max_age_h) for w in workers]
    done = [s["id"] for s in statuses if s["complete"]]
    pending = [s["id"] for s in statuses if not s["complete"]]
    return {
        "worker_count": len(workers),
        "done": done,
        "pending": pending,
        "all_complete": len(done) == len(workers) and len(workers) > 0,
        "statuses": statuses,
    }


def _artifacts_max_age_h(contract: dict[str, Any]) -> float | None:
    artifacts = contract.get("artifacts") or {}
    if isinstance(artifacts, dict) and artifacts.get("max_age_h") is not None:
        try:
            return float(artifacts["max_age_h"])
        except (TypeError, ValueError):
            return None
    return None


def merge_gate(contract: dict[str, Any]) -> dict[str, Any]:
    """多-worker 自主合并完成门。

    若 contract.artifacts.max_age_h 设定，则过期的 worker 产出视为未完成（防止误判旧产出为成功）。
    """
    problems = _validate_contract(contract)
    max_age_h = _artifacts_max_age_h(contract)
    poll = poll_once(contract, max_age_h=max_age_h)
    violations: list[str] = list(problems)
    for s in poll["statuses"]:
        if s["complete"]:
            continue
        if not s["state_complete"]:
            violations.append(f"worker {s['id']}: state not complete (stage={s['stage']})")
        elif not s["fresh"]:
            violations.append(f"worker {s['id']}: output is stale (older than max_age_h={max_age_h})")
        if not s["manifest_exists"]:
            violations.append(f"worker {s['id']}: manifest missing")
        if not s["validation_exists"]:
            violations.append(f"worker {s['id']}: validation missing")
    ok = poll["all_complete"] and not violations
    return {
        "ok": ok,
        "all_complete": poll["all_complete"],
        "max_age_h": max_age_h,
        "violations": violations,
        "done": poll["done"],
        "pending": poll["pending"],
        "worker_count": poll["worker_count"],
        "statuses": poll["statuses"],
    }


def run_fanout(
    contract: dict[str, Any],
    *,
    submit_fn: Callable[[str], dict[str, Any]],
    max_parallel: int | None = None,
    poll_interval_sec: float = 30.0,
    job_timeout_min: float = 180.0,
    first_artifact_timeout_min: float | None = None,
    reuse_existing: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
    register_fn: Callable[[str, str], None] | None = None,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """mcp-stdio 模式：提交 N 个 worker 并 file-poll 至完成。

    ``submit_fn(code)`` 必须经独立 MCP stdio 提交并返回
    ``{"ok": bool, "job_id": str|None, "text": str}``。

    防误判：``run_started`` 之后写入的产出才算本轮完成（``fresh_after``）。
    ``reuse_existing=True`` 时（断点续跑）才把更早的完成产出当作已完成、跳过提交。
    ``first_artifact_timeout_min`` 用于尽早发现"提交成功但子 R 进程静默死亡"（一直无产出）。
    """
    problems = _validate_contract(contract)
    if problems:
        return {"ok": False, "problems": problems, "transport_class": "BLOCKED"}

    run_started = time.time()
    fresh_boundary = run_started - 2.0  # 容忍文件系统 mtime 秒级粒度；旧产出仍远早于此
    workers = [w for w in contract.get("workers") if isinstance(w, dict)]
    by_id = {w["id"]: w for w in workers}
    level = int(max_parallel or contract.get("max_parallel") or 1)
    if level < 1:
        level = 1

    # 续跑：仅当显式 reuse_existing 时，已完成的旧产出才计入 done（否则一律重新提交本轮）
    pending: list[str] = []
    done: list[str] = []
    for w in workers:
        if reuse_existing and worker_status(contract, w)["complete"]:
            done.append(w["id"])
        else:
            pending.append(w["id"])

    running: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    submit_log: list[dict[str, Any]] = []
    iterations = 0

    while (pending or running) and not failed:
        while pending and len(running) < level and not failed:
            wid = pending.pop(0)
            worker = by_id[wid]
            code = build_submit_code(worker)
            result = submit_fn(code)
            entry = {"id": wid, "ok": bool(result.get("ok")), "job_id": result.get("job_id"), "text": result.get("text")}
            submit_log.append(entry)
            if not result.get("ok") or not result.get("job_id"):
                failed.append(wid)
                break
            running[wid] = {"job_id": result["job_id"], "submitted_at": time.time()}
            if register_fn:
                try:
                    register_fn(wid, result["job_id"])
                except Exception:
                    pass

        for wid in list(running.keys()):
            worker = by_id[wid]
            # 只有本轮 run 开始后写入的产出才算完成（reuse_existing 时放宽）
            status = worker_status(
                contract, worker, fresh_after=None if reuse_existing else fresh_boundary
            )
            if status["complete"]:
                running.pop(wid, None)
                done.append(wid)
                continue
            elapsed_min = (time.time() - running[wid]["submitted_at"]) / 60
            no_artifact = not any(f["exists"] for f in status["files"].values())
            if first_artifact_timeout_min is not None and no_artifact and elapsed_min > first_artifact_timeout_min:
                running.pop(wid, None)
                failed.append(wid)
                continue
            if elapsed_min > job_timeout_min:
                running.pop(wid, None)
                failed.append(wid)

        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            break
        if (pending or running) and not failed:
            sleep_fn(poll_interval_sec)

    return {
        "ok": not failed and not pending and not running,
        "transport_class": "MCP_STDIO_OK",
        "done": done,
        "failed": failed,
        "pending": pending,
        "still_running": list(running.keys()),
        "submit_log": submit_log,
        "iterations": iterations,
        "max_parallel": level,
    }
