from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .artifacts import check_artifacts, parse_requirement
from .config import (
    AGENTS_INSTALL_INFO,
    BLOCK,
    CLAUDE_JSON,
    COPILOT_CONFIG,
    CODEX_CONFIG,
    CODEX_INSTALL_INFO,
    CONTRACT_FAILED,
    DISCOVERY_DIR,
    EVIDENCE_DIR,
    HOME,
    IS_WINDOWS,
    LOCAL_CLAUDER_BRIDGE,
    NATIVE_SMOKE_ARCHIVE_DIR,
    NATIVE_SMOKE_DIR,
    PASS,
    PERSISTENT_MCP,
    PYTHON314,
    TRANSPORT_UNSTABLE,
    WARN,
    WINDOWS_STORE_PYTHON,
    UV_CACHE_DIR,
    python_command,
)
from .evidence import build_evidence, load_json, print_json, stable_task_key, utc_now, write_evidence
from .fanout import (
    build_submit_code,
    lint_contract_workers,
    load_fanout_contract,
    merge_gate,
    plan_fanout,
    poll_once,
    run_fanout,
)
from .worker_lint import lint_worker_file
from .inflight import archive_inflight, list_inflight, load_inflight, write_inflight
from .mcp_client import EXPECTED_R_STUDIO_TOOLS, call_tool, extract_job_id, list_tools, preflight_smoke, submit_async
from .resource import decide_resource_gate
from .transport import (
    classify_transport,
    codex_config_mentions_local_bridge,
    current_python,
    discovery_sessions,
    http_execute_probe,
    rscript_probe,
    run_python_smoke,
)


def emit(doc: dict[str, Any], *, write: bool = True) -> int:
    if write:
        path = write_evidence(doc)
        doc.setdefault("extra", {})
        doc["extra"]["evidence_path"] = str(path)
    print_json(doc)
    return int(doc.get("exit_code", 0))


def parse_bool_flag(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "y", "ok", "pass"}


def _load_install_info() -> tuple[dict[str, Any], Path | None]:
    for path in (CODEX_INSTALL_INFO, AGENTS_INSTALL_INFO):
        if path and path.exists():
            try:
                return load_json(path), path
            except Exception:
                return {}, path
    return {}, None


def _expected_clients(args: argparse.Namespace, install_info: dict[str, Any]) -> list[str]:
    requested = getattr(args, "expect_client", "auto") or "auto"
    if requested == "all":
        return ["codex", "claude", "copilot"]
    if requested != "auto":
        return [requested]
    configured = install_info.get("configured_clients") or []
    if isinstance(configured, str):
        configured = [configured]
    configured = [str(item).strip().lower() for item in configured if str(item).strip()]
    valid = [item for item in configured if item in {"codex", "claude", "copilot"}]
    return valid or ["codex"]


def _check_codex_toml_parseable() -> dict[str, Any]:
    """v0.2.4: 验证 Codex config.toml 是否能成功 parse。
    
    防御 install.ps1 写 toml 时 BOM/编码/换行问题导致 codex 启动失败的回归。
    返回 {"ok": bool, "path": str, "error": str (only on failure), "skipped": str (only when skipped)}
    """
    result: dict[str, Any] = {"path": str(CODEX_CONFIG)}
    if not CODEX_CONFIG.exists():
        result["ok"] = False
        result["error"] = "config.toml does not exist"
        return result
    try:
        try:
            import tomllib  # py3.11+
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        result["ok"] = True
        result["skipped"] = "no tomllib/tomli available; cannot verify"
        return result
    try:
        raw = CODEX_CONFIG.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            result["bom_detected"] = True
            raw = raw[3:]
        else:
            result["bom_detected"] = False
        text = raw.decode("utf-8")
        tomllib.loads(text)
        result["ok"] = True
        return result
    except UnicodeDecodeError as exc:
        result["ok"] = False
        result["error"] = f"utf-8 decode failed: {exc}"
        return result
    except Exception as exc:
        result["ok"] = False
        result["error"] = f"toml parse failed: {exc}"
        return result



def _load_codex_toml() -> dict[str, Any]:
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        raw = CODEX_CONFIG.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        return tomllib.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _check_codex_rstudio_mcp_config(install_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate that Codex uses a persistent MCP entry from the local fork."""
    install_info = install_info or {}
    result: dict[str, Any] = {
        "ok": True,
        "warnings": [],
        "reasons": [],
        "path": str(CODEX_CONFIG),
    }
    if not CODEX_CONFIG.exists():
        result["ok"] = False
        result["reasons"].append(f"Codex config missing: {CODEX_CONFIG}")
        return result

    data = _load_codex_toml()
    server = ((data.get("mcp_servers") or {}).get("r-studio") or {}) if isinstance(data, dict) else {}
    env = (server.get("env") or {}) if isinstance(server, dict) else {}
    command = str(server.get("command") or "")
    args = server.get("args") or []
    if isinstance(args, str):
        args = [args]
    args = [str(a) for a in args]
    startup_timeout = server.get("startup_timeout_sec")
    try:
        startup_timeout_float = float(startup_timeout)
    except (TypeError, ValueError):
        startup_timeout_float = None

    local_bridge = str(LOCAL_CLAUDER_BRIDGE)
    local_bridge_norm = local_bridge.replace("\\", "/").lower()
    expected_name = "clauder-mcp.exe" if IS_WINDOWS else "clauder-mcp"
    persistent = bool(command) and not args and Path(command).name.lower() == expected_name
    uvx_from_local = (
        command.lower() == "uvx"
        and "--from" in args
        and any(local_bridge_norm == a.replace("\\", "/").lower() for a in args)
    )
    bare_mcp = (command.lower() in {"uvx", "uv"} and "clauder-mcp" in args and "--from" not in args)

    result.update({
        "command": command,
        "args": args,
        "startup_timeout_sec": startup_timeout,
        "env": {k: env.get(k) for k in ("HOME", "USERPROFILE", "PYTHONIOENCODING", "NO_PROXY", "UV_CACHE_DIR")},
        "platform": "windows" if IS_WINDOWS else sys.platform,
        "expected_persistent_command": str(PERSISTENT_MCP),
        "persistent_entry": persistent,
        "uvx_from_local_bridge": uvx_from_local,
        "bare_mcp": bare_mcp,
    })

    if bare_mcp:
        result["reasons"].append("r-studio MCP uses bare clauder-mcp without --from; this can pull an unpinned PyPI build and lose local fork features")
    elif not persistent:
        if uvx_from_local:
            result["warnings"].append("r-studio MCP still uses uvx --from the local fork; valid for development but not the stable persistent install")
        else:
            result["reasons"].append(f"r-studio MCP command is neither persistent {expected_name} nor uvx --from the local fork")

    if startup_timeout_float is None or startup_timeout_float < 180:
        result["reasons"].append("r-studio startup_timeout_sec is missing or below 180 seconds")
    if not env.get("UV_CACHE_DIR"):
        result["warnings"].append("r-studio MCP env missing UV_CACHE_DIR; cache parity/prewarm is weaker")
    if not IS_WINDOWS and not env.get("HOME"):
        result["warnings"].append("r-studio MCP env missing HOME; session discovery may inherit an unexpected home directory")

    source_url = str(install_info.get("claudeR_source_url") or "")
    source_path = str(install_info.get("clauder_mcp_source") or "")
    command_info = str(install_info.get("clauder_mcp_command") or "")
    install_from = str(install_info.get("clauder_mcp_install_from") or "")
    exe_sha256 = str(install_info.get("clauder_mcp_exe_sha256") or "")
    install_mode = str(install_info.get("clauder_mcp_install_mode") or "")
    provenance_ok = (
        "lzhs1995/ClaudeR" in source_url
        or "projects\\ClaudeR" in source_url
        or "projects/ClaudeR" in source_url
        or "projects\\ClaudeR" in source_path
        or "projects/ClaudeR" in source_path
        or "projects\\ClaudeR" in install_from
        or "projects/ClaudeR" in install_from
    )
    if persistent and install_info:
        accepted_modes = {"uv_tool_from_local_fork", "uv_tool_from_local_lzhs_fork"}
        if install_mode and install_mode not in accepted_modes:
            result["warnings"].append(f"unexpected clauder_mcp_install_mode={install_mode}")
        if command_info and command and Path(command_info) != Path(command):
            result["warnings"].append(f"INSTALL_INFO clauder_mcp_command differs from Codex command: {command_info}")
        if command and not Path(command).exists():
            result["reasons"].append(f"persistent clauder-mcp does not exist: {command}")
        if source_path and not Path(source_path).exists():
            result["reasons"].append(f"INSTALL_INFO clauder_mcp_source does not exist: {source_path}")
        if not exe_sha256:
            result["warnings"].append("INSTALL_INFO missing clauder_mcp_exe_sha256")
        if not provenance_ok:
            result["reasons"].append("INSTALL_INFO does not prove local ClaudeR fork provenance")

    result["ok"] = not result["reasons"]
    return result


def cmd_doctor(args: argparse.Namespace) -> int:
    reasons: list[str] = []
    warnings: list[str] = []
    install_info, install_info_path = _load_install_info()
    expected_clients = _expected_clients(args, install_info)
    py_smoke = run_python_smoke()
    if not PYTHON314 or not PYTHON314.exists():
        warnings.append(f"preferred harness Python missing: {PYTHON314}; using {python_command()}")
    if IS_WINDOWS and str(WINDOWS_STORE_PYTHON).lower() in current_python().lower():
        reasons.append("current python appears to be WindowsApps redirector")
    if not LOCAL_CLAUDER_BRIDGE.exists():
        warnings.append(f"local patched ClaudeR bridge missing: {LOCAL_CLAUDER_BRIDGE}")
    if not DISCOVERY_DIR.exists():
        warnings.append(f"discovery directory missing: {DISCOVERY_DIR}")
    codex_rstudio_mcp_info: dict[str, Any] = {}
    if "codex" in expected_clients:
        if not CODEX_CONFIG.exists():
            warnings.append(f"Codex config missing: {CODEX_CONFIG}")
        else:
            codex_rstudio_mcp_info = _check_codex_rstudio_mcp_config(install_info)
            reasons.extend(codex_rstudio_mcp_info.get("reasons", []))
            warnings.extend(codex_rstudio_mcp_info.get("warnings", []))
            if not codex_config_mentions_local_bridge() and not codex_rstudio_mcp_info.get("persistent_entry"):
                warnings.append("Codex config does not mention local patched ClaudeR bridge")
    if "claude" in expected_clients and not CLAUDE_JSON.exists():
        warnings.append(f"Claude Code user config missing: {CLAUDE_JSON}")
    if "copilot" in expected_clients and not COPILOT_CONFIG.exists():
        warnings.append(f"Copilot MCP config missing: {COPILOT_CONFIG}")

    # v0.2.4: 可选 TOML parse 自检，防止 install.ps1 写坏 .codex/config.toml 后无人发现
    toml_parse_info: dict[str, Any] = {}
    if getattr(args, "check_toml_parse", False) and "codex" in expected_clients:
        toml_parse_info = _check_codex_toml_parseable()
        if not toml_parse_info.get("ok", True):
            reasons.append(
                f"Codex config.toml parse failed: {toml_parse_info.get('error', 'unknown')}; "
                f"see guide section 27.11 for recovery."
            )

    exit_code = BLOCK if reasons else WARN if warnings else PASS
    decision = "BLOCK" if reasons else "WARN" if warnings else "PASS"
    doc = build_evidence(
        "doctor",
        decision,
        reasons=reasons + warnings or ["configuration checks passed"],
        exit_code=exit_code,
        extra={
            "python314": str(PYTHON314),
            "python_command": python_command(),
            "current_python": current_python(),
            "python_smoke": py_smoke,
            "local_bridge": str(LOCAL_CLAUDER_BRIDGE),
            "persistent_mcp": str(PERSISTENT_MCP),
            "uv_cache_dir": str(UV_CACHE_DIR),
            "home": str(HOME),
            "platform": "windows" if IS_WINDOWS else sys.platform,
            "discovery_dir": str(DISCOVERY_DIR),
            "codex_config": str(CODEX_CONFIG),
            "claude_json": str(CLAUDE_JSON),
            "copilot_config": str(COPILOT_CONFIG),
            "install_info_path": str(install_info_path) if install_info_path else "",
            "install_info": install_info,
            "expect_client": args.expect_client,
            "expected_clients": expected_clients,
            "discovery_sessions": discovery_sessions(),
            "toml_parse_check": toml_parse_info,
            "codex_rstudio_mcp_check": codex_rstudio_mcp_info,
        },
    )
    return emit(doc)


def cmd_transport_classify(args: argparse.Namespace) -> int:
    transport_class, reasons = classify_transport(
        native_ok=args.native_ok,
        mcp_stdio_ok=args.mcp_stdio_ok,
        http_ok=args.http_ok,
        rscript_ok=args.rscript_ok,
        native_required=args.native_required,
        allow_agent_hints=args.allow_agent_hints,
        probe_stdio=args.probe_mcp_stdio,
        probe_http=args.probe_http,
        probe_rscript=args.probe_rscript,
        timeout=args.timeout,
    )
    exit_code = PASS
    if transport_class == "BLOCKED":
        exit_code = TRANSPORT_UNSTABLE
    elif transport_class in {"HTTP_ONLY_DIAGNOSTIC", "RSCRIPT_ONLY"}:
        exit_code = WARN
    doc = build_evidence(
        "transport_classify",
        transport_class,
        reasons=reasons,
        transport_class=transport_class,
        exit_code=exit_code,
        extra={
            "native_required": args.native_required,
            "probe_mcp_stdio": args.probe_mcp_stdio,
            "probe_http": args.probe_http,
            "probe_rscript": args.probe_rscript,
            "allow_agent_hints": args.allow_agent_hints,
        },
    )
    return emit(doc)


def cmd_tool_surface(args: argparse.Namespace) -> int:
    probe_result: dict[str, Any] | None = None
    explicit_tools = args.tools or []
    if not explicit_tools and args.probe_mcp_stdio:
        probe_result = list_tools(timeout=args.timeout)
        explicit_tools = probe_result.get("tools", [])
    tools = set(explicit_tools)
    expected = set(args.expected or [])
    if not expected and args.default_rstudio_expected:
        expected = EXPECTED_R_STUDIO_TOOLS
    missing = sorted(expected - tools)
    decision = "PASS" if not missing else "BLOCK"
    exit_code = PASS if not missing else BLOCK
    doc = build_evidence(
        "tool_surface",
        decision,
        reasons=["all expected tools are present"] if not missing else [f"missing tools: {', '.join(missing)}"],
        exit_code=exit_code,
        extra={"tools": sorted(tools), "expected": sorted(expected), "missing": missing, "probe_result": probe_result},
    )
    return emit(doc)


def cmd_preflight(args: argparse.Namespace) -> int:
    parents = args.parent_evidence or []
    transport_class = args.transport_class
    preflight_result: dict[str, Any] | None = None
    if not transport_class:
        if args.probe_mcp_stdio:
            preflight_result = preflight_smoke(session_name=args.session_name, timeout=args.timeout, async_poll_attempts=args.async_poll_attempts)
            transport_class = "MCP_STDIO_OK" if preflight_result.get("ok") else "BLOCKED"
        else:
            transport_class, _ = classify_transport(
                native_ok=args.native_ok,
                mcp_stdio_ok=args.mcp_stdio_ok,
                native_required=args.native_required,
                allow_agent_hints=args.allow_agent_hints,
                probe_stdio=False,
                probe_http=args.probe_http,
                probe_rscript=args.probe_rscript,
                timeout=args.timeout,
            )
    reasons = ["preflight evidence recorded"] if preflight_result is None else [preflight_result.get("reason") or "MCP stdio preflight completed"]
    exit_code = PASS
    decision = "PASS"
    if preflight_result is not None and not preflight_result.get("ok"):
        decision = "BLOCK"
        exit_code = TRANSPORT_UNSTABLE
    if args.native_required and transport_class != "NATIVE_MCP_OK":
        decision = "BLOCK"
        exit_code = TRANSPORT_UNSTABLE
        reasons = [f"native wrapper required but transport_class={transport_class}"]
    doc = build_evidence(
        "preflight",
        decision,
        reasons=reasons,
        parent_evidence_ids=parents,
        task_key=args.task_key,
        transport_class=transport_class,
        session_name=args.session_name,
        pid=args.pid,
        exit_code=exit_code,
        extra={
            "expected_layers": ["list_sessions/connect_session", "execute_r smoke", "execute_r_async/get_async_result smoke"],
            "native_required": args.native_required,
            "preflight_result": preflight_result,
            "note": "Native wrapper calls occur in the active agent tool layer; this harness independently probes MCP stdio/HTTP/Rscript unless native evidence is supplied.",
        },
    )
    return emit(doc)


def cmd_connect(args: argparse.Namespace) -> int:
    transport_class, reasons = classify_transport(
        native_ok=args.native_ok,
        mcp_stdio_ok=args.mcp_stdio_ok,
        http_ok=args.http_ok,
        rscript_ok=args.rscript_ok,
        native_required=args.native_required,
        allow_agent_hints=args.allow_agent_hints,
        probe_stdio=args.probe_mcp_stdio,
        probe_http=args.probe_http,
        probe_rscript=args.probe_rscript,
        timeout=args.timeout,
    )
    exit_code = PASS if transport_class in {"NATIVE_MCP_OK", "MCP_STDIO_OK"} else WARN
    if transport_class == "BLOCKED":
        exit_code = TRANSPORT_UNSTABLE
    doc = build_evidence(
        "connect",
        transport_class,
        reasons=reasons,
        transport_class=transport_class,
        session_name=args.session_name,
        exit_code=exit_code,
        extra={"max_attempts": args.max_attempts, "native_required": args.native_required},
    )
    return emit(doc)


def make_task_key(args: argparse.Namespace) -> str:
    if getattr(args, "task_key", None):
        return args.task_key
    return stable_task_key(
        project_root=getattr(args, "project_root", "") or "",
        task_label=getattr(args, "task_label", "") or "",
        session_name=getattr(args, "session_name", "") or "",
        transport_scope=getattr(args, "transport_scope", "") or "",
    )


NATIVE_SMOKE_STEPS = ("list_sessions", "execute_r", "execute_r_async", "get_async_result")


def _safe_task_key(task_key: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in task_key)[:128] or "task"


def _native_smoke_path(task_key: str) -> Path:
    NATIVE_SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    return NATIVE_SMOKE_DIR / f"{_safe_task_key(task_key)}.json"


def _load_native_smoke(task_key: str) -> dict[str, Any] | None:
    path = _native_smoke_path(task_key)
    if not path.exists():
        return None
    return load_json(path)


def _write_native_smoke(task_key: str, state: dict[str, Any]) -> Path:
    path = _native_smoke_path(task_key)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _archive_native_smoke(task_key: str, reason: str) -> str | None:
    path = _native_smoke_path(task_key)
    if not path.exists():
        return None
    NATIVE_SMOKE_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = NATIVE_SMOKE_ARCHIVE_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{_safe_task_key(task_key)}_{reason}.json"
    path.replace(target)
    return str(target)


def _load_parent_docs(paths: list[str] | None) -> tuple[list[dict[str, Any]], list[str]]:
    docs: list[dict[str, Any]] = []
    reasons: list[str] = []
    for path in paths or []:
        try:
            docs.append(load_json(path))
        except Exception as exc:
            reasons.append(f"could not read parent evidence {path}: {exc}")
    return docs, reasons


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _timestamp_fresh_enough(timestamp_utc: str | None, max_age_min: float) -> bool:
    dt = _parse_utc(timestamp_utc)
    if dt is None:
        return False
    age_sec = (datetime.now(timezone.utc) - dt).total_seconds()
    return age_sec <= max_age_min * 60


def _native_smoke_parent_ok(parent_docs: list[dict[str, Any]], task_key: str | None = None, max_age_min: float = 60.0) -> bool:
    for doc in parent_docs:
        if doc.get("harness_name") != "native_smoke":
            continue
        if doc.get("decision") != "PASS" or doc.get("transport_class") != "NATIVE_MCP_OK":
            continue
        parent_ids = [str(x) for x in (doc.get("parent_evidence_ids") or []) if str(x)]
        if len(parent_ids) != len(NATIVE_SMOKE_STEPS) or len(set(parent_ids)) != len(NATIVE_SMOKE_STEPS):
            continue
        if task_key and doc.get("task_key") not in {task_key, None, ""}:
            continue
        if not _timestamp_fresh_enough(str(doc.get("timestamp_utc") or ""), max_age_min):
            continue
        return True
    return False


def _contract_requires_native_smoke(contract: dict[str, Any]) -> bool:
    if bool(contract.get("requires_native_smoke")):
        return True
    transport = str(contract.get("transport") or "").lower()
    return transport in {"native-wrapper", "native_wrapper", "native"}


def _native_smoke_gate(contract: dict[str, Any], parent_evidence: list[str] | None, task_key: str | None = None) -> tuple[bool, list[str], list[dict[str, Any]]]:
    parent_docs, reasons = _load_parent_docs(parent_evidence)
    if not _contract_requires_native_smoke(contract):
        return True, reasons, parent_docs
    max_age = 60.0
    native_cfg = contract.get("native_smoke") or {}
    if isinstance(native_cfg, dict) and native_cfg.get("max_age_min") is not None:
        try:
            max_age = float(native_cfg["max_age_min"])
        except (TypeError, ValueError):
            pass
    key = task_key or contract.get("task_key")
    if not _native_smoke_parent_ok(parent_docs, str(key) if key else None, max_age):
        reasons.append(
            "contract requires fresh native_smoke parent evidence with transport_class=NATIVE_MCP_OK and four chained record parent ids; "
            "run native-smoke start -> native list_sessions/execute_r/execute_r_async/get_async_result -> "
            "native-smoke record/complete first"
        )
        return False, reasons, parent_docs
    return True, reasons, parent_docs


def _agent_from_tool_layer(steps: dict[str, Any]) -> str | None:
    for entry in steps.values():
        tool_layer = str(entry.get("tool_layer") or "")
        if tool_layer.endswith("-native"):
            return tool_layer[: -len("-native")]
    return None


def _native_tool_layer_for_agent(agent: str | None) -> str | None:
    if agent in {"codex", "claude", "copilot"}:
        return f"{agent}-native"
    return None


def _native_smoke_expected_agent(state: dict[str, Any]) -> str | None:
    return str(state.get("agent") or "") or None


def _native_smoke_existing_tool_layer(state: dict[str, Any]) -> str | None:
    for prior in (state.get("steps") or {}).values():
        layer = str(prior.get("tool_layer") or "")
        if layer:
            return layer
    return None


def _raw_file_proof(raw_file: str | None, evidence_id: str) -> dict[str, Any] | None:
    if not raw_file:
        return None
    source = Path(raw_file).expanduser().resolve()
    stat = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    target_dir = EVIDENCE_DIR / "raw" / evidence_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)
    return {
        "source_path": str(source),
        "sha256": digest.hexdigest(),
        "size_bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        "evidence_copy": str(target),
    }


def _native_smoke_step_valid(step: str, entry: dict[str, Any], state: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if entry.get("transport_class") != "NATIVE_MCP_OK":
        reasons.append(f"{step} transport_class must be NATIVE_MCP_OK")
    tool_layer = str(entry.get("tool_layer") or "")
    if not tool_layer.endswith("-native"):
        reasons.append(f"{step} must be recorded from an agent native wrapper tool layer")
    expected_agent = _native_smoke_expected_agent(state)
    if expected_agent:
        expected_layer = _native_tool_layer_for_agent(expected_agent)
        if tool_layer != expected_layer:
            reasons.append(f"{step} tool_layer must be {expected_layer} for agent={expected_agent}")
    existing_layer = _native_smoke_existing_tool_layer(state)
    if existing_layer and tool_layer and tool_layer != existing_layer:
        reasons.append(f"{step} tool_layer {tool_layer} does not match prior native smoke tool_layer {existing_layer}")
    if not entry.get("ok"):
        reasons.append(f"{step} is not recorded as ok")
    if step == "list_sessions":
        if not entry.get("session_name") and int(entry.get("session_count") or 0) < 1:
            reasons.append("list_sessions needs --session-name or --session-count >= 1")
    elif step == "execute_r":
        if not entry.get("marker"):
            reasons.append("execute_r needs a native output marker")
    elif step == "execute_r_async":
        if not entry.get("job_id"):
            reasons.append("execute_r_async needs the real job_id")
    elif step == "get_async_result":
        if not entry.get("job_id"):
            reasons.append("get_async_result needs the same job_id")
        async_job = (state.get("steps") or {}).get("execute_r_async", {}).get("job_id")
        if async_job and entry.get("job_id") != async_job:
            reasons.append("get_async_result job_id does not match execute_r_async job_id")
        if not entry.get("marker"):
            reasons.append("get_async_result needs a completion marker")
    raw_file = entry.get("raw_file")
    marker = entry.get("marker")
    if state.get("require_raw_file") and not raw_file:
        reasons.append(f"{step} requires --raw-file in high-assurance mode (--require-raw-file)")
    if raw_file and marker:
        try:
            raw = Path(raw_file).read_text(encoding="utf-8-sig", errors="replace")
            if str(marker) not in raw:
                reasons.append(f"marker not found in raw_file for {step}")
        except Exception as exc:
            reasons.append(f"could not read raw_file for {step}: {exc}")
    return not reasons, reasons


def cmd_native_smoke(args: argparse.Namespace) -> int:
    task_key = make_task_key(args)
    if args.action == "list":
        states: list[dict[str, Any]] = []
        NATIVE_SMOKE_DIR.mkdir(parents=True, exist_ok=True)
        for path in NATIVE_SMOKE_DIR.glob("*.json"):
            if path.name == "archive":
                continue
            try:
                states.append(load_json(path))
            except Exception:
                continue
        doc = build_evidence("native_smoke_list", "PASS", reasons=["listed native smoke states"], exit_code=PASS, extra={"states": states})
        return emit(doc)

    if args.action == "cancel":
        archived = _archive_native_smoke(task_key, args.reason or "cancel")
        doc = build_evidence(
            "native_smoke_cancel",
            "PASS",
            reasons=["archived native smoke state" if archived else "no native smoke state found"],
            task_key=task_key,
            exit_code=PASS,
            extra={"archived_path": archived},
        )
        return emit(doc)

    if args.action == "start":
        existing = _load_native_smoke(task_key)
        if existing and not args.force:
            doc = build_evidence(
                "native_smoke_start",
                "BLOCK",
                reasons=[f"native smoke state already exists for task_key={task_key}; use --force or cancel it"],
                task_key=task_key,
                policy_violations=["NATIVE-SMOKE-DUPLICATE-START"],
                exit_code=BLOCK,
                extra={"state": existing},
            )
            return emit(doc)
        if existing and args.force:
            _archive_native_smoke(task_key, "force")
        state = {
            "task_key": task_key,
            "status": "started",
            "started_at_utc": utc_now(),
            "session_name": args.session_name,
            "agent": args.agent,
            "require_raw_file": bool(args.require_raw_file),
            "required_steps": list(NATIVE_SMOKE_STEPS),
            "steps": {},
        }
        path = _write_native_smoke(task_key, state)
        doc = build_evidence(
            "native_smoke_start",
            "PASS",
            reasons=[
                "native smoke started; now run real agent-native list_sessions, execute_r, execute_r_async, and get_async_result, then record each step"
            ],
            task_key=task_key,
            session_name=args.session_name,
            exit_code=PASS,
            extra={"state_path": str(path), "required_steps": list(NATIVE_SMOKE_STEPS)},
            agent=args.agent,
        )
        return emit(doc)

    state = _load_native_smoke(task_key)
    if not state:
        doc = build_evidence(
            "native_smoke",
            "BLOCK",
            reasons=[f"native smoke state missing for task_key={task_key}; run native-smoke start first"],
            task_key=task_key,
            policy_violations=["NATIVE-SMOKE-WITHOUT-START"],
            exit_code=BLOCK,
        )
        return emit(doc)

    if args.action == "record":
        if args.step not in NATIVE_SMOKE_STEPS:
            doc = build_evidence("native_smoke_record", "BLOCK", reasons=[f"unknown step: {args.step}"], task_key=task_key, exit_code=BLOCK)
            return emit(doc)
        expected_layer = _native_tool_layer_for_agent(args.agent or state.get("agent"))
        tool_layer = args.tool_layer or expected_layer or "codex-native"
        entry = {
            "step": args.step,
            "ok": bool(args.ok),
            "recorded_at_utc": utc_now(),
            "tool_layer": tool_layer,
            "transport_class": args.transport_class,
            "session_name": args.session_name or state.get("session_name"),
            "session_count": args.session_count,
            "pid": args.pid,
            "job_id": args.job_id,
            "marker": args.marker,
            "raw_file": args.raw_file,
        }
        ok, reasons = _native_smoke_step_valid(args.step, entry, state)
        if not ok:
            doc = build_evidence(
                "native_smoke_record",
                "BLOCK",
                reasons=reasons,
                task_key=task_key,
                transport_class="BLOCKED",
                session_name=entry.get("session_name"),
                job_id=entry.get("job_id"),
                policy_violations=["NATIVE-SMOKE-INVALID-STEP"],
                exit_code=BLOCK,
                extra={"entry": entry},
            )
            return emit(doc)
        doc = build_evidence(
            "native_smoke_record",
            "PASS",
            reasons=[f"recorded native smoke step: {args.step}"],
            task_key=task_key,
            transport_class="NATIVE_MCP_OK",
            session_name=entry.get("session_name"),
            pid=entry.get("pid"),
            job_id=entry.get("job_id"),
            exit_code=PASS,
            extra={"entry": entry},
            agent=args.agent or state.get("agent"),
        )
        entry["evidence_id"] = doc["evidence_id"]
        try:
            proof = _raw_file_proof(entry.get("raw_file"), str(doc["evidence_id"]))
        except Exception as exc:
            fail_doc = build_evidence(
                "native_smoke_record",
                "BLOCK",
                reasons=[f"could not preserve raw_file proof for {args.step}: {exc}"],
                task_key=task_key,
                transport_class="BLOCKED",
                session_name=entry.get("session_name"),
                job_id=entry.get("job_id"),
                policy_violations=["NATIVE-SMOKE-RAW-PROOF-FAILED"],
                exit_code=BLOCK,
                extra={"entry": entry},
                agent=args.agent or state.get("agent"),
            )
            return emit(fail_doc)
        if proof:
            entry["raw_file_proof"] = proof
            doc["artifact_paths"] = [proof["evidence_copy"]]
        doc["extra"]["entry"] = entry
        state.setdefault("steps", {})[args.step] = entry
        state["status"] = "recording"
        state["updated_at_utc"] = utc_now()
        _write_native_smoke(task_key, state)
        return emit(doc)

    if args.action == "complete":
        steps = state.get("steps") or {}
        reasons: list[str] = []
        for step in NATIVE_SMOKE_STEPS:
            entry = steps.get(step)
            if not entry:
                reasons.append(f"missing native smoke step: {step}")
                continue
            ok, step_reasons = _native_smoke_step_valid(step, entry, state)
            reasons.extend(step_reasons)
            if not entry.get("evidence_id"):
                reasons.append(f"native smoke step is missing record evidence_id: {step}")
            if not _timestamp_fresh_enough(str(entry.get("recorded_at_utc") or ""), args.max_age_min):
                reasons.append(f"native smoke step is stale: {step}")
        if reasons:
            doc = build_evidence(
                "native_smoke",
                "BLOCK",
                reasons=reasons,
                task_key=task_key,
                transport_class="BLOCKED",
                policy_violations=["NATIVE-SMOKE-INCOMPLETE"],
                exit_code=BLOCK,
                extra={"state": state},
            )
            return emit(doc)
        parent_ids = [step.get("evidence_id") for step in steps.values() if step.get("evidence_id")]
        if len(parent_ids) != len(NATIVE_SMOKE_STEPS):
            doc = build_evidence(
                "native_smoke",
                "BLOCK",
                reasons=["native smoke complete requires one parent evidence_id for each recorded step"],
                task_key=task_key,
                transport_class="BLOCKED",
                policy_violations=["NATIVE-SMOKE-PARENT-EVIDENCE-MISSING"],
                exit_code=BLOCK,
                extra={"state": state},
            )
            return emit(doc)
        state["status"] = "complete"
        state["completed_at_utc"] = utc_now()
        _write_native_smoke(task_key, state)
        smoke_agent = args.agent or state.get("agent") or _agent_from_tool_layer(steps)
        doc = build_evidence(
            "native_smoke",
            "PASS",
            reasons=["native wrapper smoke passed: list_sessions + execute_r + execute_r_async/get_async_result"],
            parent_evidence_ids=[str(x) for x in parent_ids if x],
            task_key=task_key,
            transport_class="NATIVE_MCP_OK",
            session_name=state.get("session_name") or steps.get("list_sessions", {}).get("session_name"),
            pid=steps.get("execute_r", {}).get("pid"),
            job_id=steps.get("execute_r_async", {}).get("job_id"),
            exit_code=PASS,
            extra={"state_path": str(_native_smoke_path(task_key)), "steps": steps},
            agent=smoke_agent,
        )
        return emit(doc)

    doc = build_evidence("native_smoke", "BLOCK", reasons=[f"unknown action: {args.action}"], task_key=task_key, exit_code=BLOCK)
    return emit(doc)


def cmd_async_guard(args: argparse.Namespace) -> int:
    if args.action == "list":
        doc = build_evidence("async_guard", "PASS", reasons=["listed in-flight jobs"], exit_code=PASS, extra={"inflight": list_inflight()})
        return emit(doc)

    task_key = make_task_key(args)
    if args.action == "complete":
        archived = archive_inflight(task_key, args.reason or "complete")
        doc = build_evidence(
            "async_guard",
            "PASS",
            reasons=["archived in-flight record" if archived else "no in-flight record found"],
            task_key=task_key,
            job_id=args.job_id,
            exit_code=PASS,
            extra={"archived_path": str(archived) if archived else None},
        )
        return emit(doc)

    if args.action == "cancel":
        archived = archive_inflight(task_key, args.reason or "cancel")
        doc = build_evidence(
            "async_guard",
            "PASS",
            reasons=["cancel/archive recorded"],
            task_key=task_key,
            job_id=args.job_id,
            exit_code=PASS,
            extra={"archived_path": str(archived) if archived else None},
        )
        return emit(doc)

    if args.action == "register-job":
        existing = load_inflight(task_key)
        policy_violations: list[str] = []
        reasons: list[str] = []
        if not existing:
            policy_violations.append("REGISTER-JOB-WITHOUT-PRESUBMIT")
            reasons.append(f"no pre-submit record found for task_key={task_key}")
        if not args.job_id:
            policy_violations.append("REGISTER-JOB-MISSING-JOB-ID")
            reasons.append("register-job requires --job-id from the actual execute_r_async response")
        if policy_violations:
            doc = build_evidence(
                "async_guard",
                "BLOCK",
                reasons=reasons,
                task_key=task_key,
                job_id=args.job_id,
                policy_violations=policy_violations,
                exit_code=BLOCK,
                extra={"existing": existing},
            )
            return emit(doc)
        existing = existing or {}
        existing.update(
            {
                "job_id": args.job_id,
                "status": "inflight",
                "registered_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "registration_transport": args.transport_scope,
            }
        )
        write_inflight(task_key, existing)
        doc = build_evidence(
            "async_guard",
            "PASS",
            reasons=["registered real async job_id for pre-submitted task"],
            task_key=task_key,
            session_name=args.session_name,
            job_id=args.job_id,
            io_mode=existing.get("io_mode"),
            exit_code=PASS,
            extra={"inflight": existing},
        )
        return emit(doc)

    existing = load_inflight(task_key)
    policy_violations: list[str] = []
    reasons: list[str] = []
    job_id = args.job_id
    if args.io_mode == "durable_files" and args.outputs and not args.allow_large_outputs:
        policy_violations.append("P2 BIG-MODEL-LARGE-OUTPUTS")
        reasons.append("durable_files mode cannot marshal outputs unless --allow-large-outputs is explicit")
    if existing and not args.force_new_job:
        policy_violations.append("P4 RESUBMIT-AFTER-TRANSIENT")
        reasons.append(f"in-flight task already exists for task_key={task_key}")
    elif existing and args.force_new_job:
        policy_violations.append("FORCE-NEW-JOB")
        archive_inflight(task_key, "force-new-job")

    if policy_violations:
        exit_code = BLOCK
        decision = "BLOCK"
    else:
        exit_code = PASS
        decision = "PASS"
        action_label = "pre-submit" if args.action in {"pre-submit", "submit"} else args.action
        reasons.append(f"async {action_label} is allowed by guard")
        status = "pre_submitted"
        job_id = args.job_id
        via_mcp_stdio_result = None
        if args.via_mcp_stdio:
            if not args.code_file:
                policy_violations.append("MCP-STDIO-SUBMIT-MISSING-CODE-FILE")
                reasons.append("--via-mcp-stdio requires --code-file")
                exit_code = BLOCK
                decision = "BLOCK"
            else:
                code = Path(args.code_file).read_text(encoding="utf-8-sig")
                via_mcp_stdio_result = call_tool("execute_r_async", {"code": code, "outputs": args.outputs or []}, timeout=args.timeout, retries=1)
                job_id = extract_job_id(via_mcp_stdio_result.get("text", ""))
                if not via_mcp_stdio_result.get("ok") or not job_id:
                    policy_violations.append("MCP-STDIO-SUBMIT-FAILED")
                    reasons.append("diagnostic MCP stdio execute_r_async failed or returned no job_id")
                    exit_code = BLOCK
                    decision = "BLOCK"
                else:
                    status = "inflight"
                    reasons.append("diagnostic MCP stdio execute_r_async submitted a job")
        if decision == "PASS":
            write_inflight(
                task_key,
                {
                    "task_key": task_key,
                    "job_id": job_id,
                    "status": status,
                    "io_mode": args.io_mode,
                    "outputs": args.outputs or [],
                    "session_name": args.session_name,
                    "transport_scope": args.transport_scope,
                    "pre_submitted_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "via_mcp_stdio": args.via_mcp_stdio,
                    "via_mcp_stdio_result": via_mcp_stdio_result,
                },
            )

    doc = build_evidence(
        "async_guard",
        decision,
        reasons=reasons,
        task_key=task_key,
        session_name=args.session_name,
        job_id=job_id,
        io_mode=args.io_mode,
        policy_violations=policy_violations,
        exit_code=exit_code,
        extra={"outputs": args.outputs or [], "force_new_job": args.force_new_job, "via_mcp_stdio": args.via_mcp_stdio},
    )
    return emit(doc)


def cmd_resource_gate(args: argparse.Namespace) -> int:
    decision = decide_resource_gate(
        current_parallel=args.current_parallel,
        memory_threshold=args.memory_threshold,
        output_root=args.output_root,
        previous_newest_mtime=args.previous_newest_mtime,
        io_blocked=args.io_blocked,
        rterm_responsive=not args.rterm_unresponsive,
        mcp_responsive=not args.mcp_unresponsive,
        memory_override=args.memory_override,
    )
    exit_code = PASS
    if args.mode == "enforce" and decision["decision"] != "increase_by_1":
        exit_code = BLOCK
    doc = build_evidence(
        "resource_gate",
        decision["decision"],
        reasons=decision["reasons"],
        task_key=args.task_key,
        exit_code=exit_code,
        extra=decision | {"mode": args.mode},
    )
    return emit(doc)


def parse_requirements(values: list[str] | None) -> list[dict[str, Any]]:
    reqs: list[dict[str, Any]] = []
    for value in values or []:
        reqs.append(parse_requirement(value))
    return reqs


def _state_is_complete(state: Any) -> bool:
    if isinstance(state, dict):
        for key in ("status", "state", "stage", "decision"):
            if str(state.get(key, "")).lower() in {"complete", "completed", "done", "success", "pass"}:
                return True
        progress = state.get("progress")
        if _state_is_complete(progress):
            return True
        result = state.get("result")
        if _state_is_complete(result):
            return True
        return bool(state.get("complete") is True or state.get("completed") is True)
    if isinstance(state, list):
        return any(_state_is_complete(item) for item in state)
    return str(state).strip().lower() in {"complete", "completed", "done", "success", "pass"}


def _load_contract(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"contract not found: {path}")
    if p.suffix.lower() == ".json":
        return load_json(p)
    data: dict[str, Any] = {}
    current_list: str | None = None
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not line.startswith("-"):
            current_list = line[:-1].strip()
            data.setdefault(current_list, [])
            continue
        if line.startswith("-") and current_list:
            data.setdefault(current_list, []).append(line[1:].strip().strip("'\""))
            continue
        current_list = None
        if ":" in line:
            key, value = line.split(":", 1)
            value = value.strip().strip("'\"")
            if value.lower() in {"true", "false"}:
                data[key.strip()] = value.lower() == "true"
            else:
                data[key.strip()] = value
    return data


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fresh_enough(doc: dict[str, Any], max_age_min: float | None) -> bool:
    if max_age_min is None:
        return True
    ts = _parse_utc(str(doc.get("timestamp_utc") or ""))
    if ts is None:
        return False
    age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60
    return age_min <= max_age_min


def _matching_task(doc: dict[str, Any], task_key: str | None) -> bool:
    if not task_key:
        return True
    return doc.get("task_key") == task_key


def _resource_gate_ok(parent_docs: list[dict[str, Any]], task_key: str | None, max_age_min: float | None) -> bool:
    return any(
        doc.get("harness_name") == "resource_gate"
        and doc.get("decision") == "increase_by_1"
        and _matching_task(doc, task_key)
        and _fresh_enough(doc, max_age_min)
        for doc in parent_docs
    )


def _job_complete_ok(parent_docs: list[dict[str, Any]], task_key: str | None) -> bool:
    return any(
        doc.get("harness_name") == "async_guard"
        and _matching_task(doc, task_key)
        and doc.get("decision") == "PASS"
        and (
            "archived_path" in (doc.get("extra") or {})
            or any("archived in-flight record" in str(reason) for reason in doc.get("reasons", []))
        )
        for doc in parent_docs
    )


def _p6_durable_violations(requirements: list[dict[str, Any]], artifact_checks: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for req, check in zip(requirements, artifact_checks):
        path = Path(req["path"])
        kind = str(req.get("kind") or "file").lower()
        options = req.get("options", {})
        reason = str(check.get("reason") or "")
        if any(marker in reason for marker in ["outside required output_root", "stale:", "missing:"]):
            violations.append(reason)
            continue
        if not path.exists():
            continue
        if kind not in {"validation", "manifest", "csv_rows", "gt_errors_empty", "empty_ok"}:
            min_bytes = int(options.get("min_bytes", 1024))
            size = path.stat().st_size
            if size < min_bytes:
                violations.append(f"{path} is below durable size threshold: {size} < {min_bytes} bytes")
    return violations


def cmd_completion_check(args: argparse.Namespace) -> int:
    contract = _load_contract(args.contract)
    contract_require_files = contract.get("require_file") or contract.get("require_files") or []
    if isinstance(contract_require_files, str):
        contract_require_files = [contract_require_files]
    requirements = parse_requirements(list(contract_require_files) + args.require_file)
    artifacts = check_artifacts(requirements)
    policy_violations: list[str] = []
    reasons = [check["reason"] for check in artifacts["checks"] if not check["ok"]]

    parent_docs, parent_reasons = _load_parent_docs(args.parent_evidence)
    reasons.extend(parent_reasons)

    require_transport_class = args.require_transport_class or contract.get("require_transport_class")
    if require_transport_class:
        seen = {doc.get("transport_class") for doc in parent_docs}
        if require_transport_class not in seen and args.transport_class != require_transport_class:
            policy_violations.append("P1 NATIVE-ONLY-HTTP-EVIDENCE")
            reasons.append(f"required transport_class {require_transport_class} not proven")
    require_preflight = args.require_preflight or bool(contract.get("require_preflight"))
    if require_preflight and not any(doc.get("harness_name") == "preflight" for doc in parent_docs):
        policy_violations.append("MISSING-PREFLIGHT-EVIDENCE")
        reasons.append("required preflight parent evidence is missing")
    require_native_smoke = args.require_native_smoke or bool(contract.get("requires_native_smoke"))
    if require_native_smoke and not _native_smoke_parent_ok(parent_docs, args.task_key or contract.get("task_key"), args.native_smoke_max_age_min):
        policy_violations.append("MISSING-NATIVE-SMOKE-EVIDENCE")
        reasons.append("required native_smoke parent evidence with transport_class=NATIVE_MCP_OK and four chained record parent ids is missing, stale, or incomplete")
    if args.io_mode == "durable_files" and args.outputs:
        policy_violations.append("P2 BIG-MODEL-LARGE-OUTPUTS")
        reasons.append("durable_files completion includes marshaled outputs")
    state_file = args.state_file or contract.get("state_file")
    if state_file:
        try:
            state = load_json(state_file)
            if not _state_is_complete(state):
                policy_violations.append("P3 RDATA-INCOMPLETE-READ")
                reasons.append("state file does not prove complete")
        except Exception as exc:
            policy_violations.append("P3 RDATA-INCOMPLETE-READ")
            reasons.append(f"state file could not be read: {exc}")
    require_job_complete = args.require_job_complete or bool(contract.get("require_job_complete"))
    if require_job_complete and not _job_complete_ok(parent_docs, args.task_key):
        policy_violations.append("P3 RDATA-INCOMPLETE-READ")
        reasons.append("required async job completion evidence is missing")
    if args.task_key and load_inflight(args.task_key):
        policy_violations.append("P4 RESUBMIT-AFTER-TRANSIENT")
        reasons.append("task still has an active in-flight record")
    require_resource_gate = args.require_resource_gate or bool(contract.get("require_resource_gate"))
    if require_resource_gate:
        max_age_min = args.resource_gate_max_age_min
        if contract.get("resource_gate_max_age_min") is not None:
            max_age_min = float(contract["resource_gate_max_age_min"])
        gate_ok = _resource_gate_ok(parent_docs, args.task_key, max_age_min)
        if not gate_ok:
            policy_violations.append("P5 CONCURRENCY-WITHOUT-GATE")
            reasons.append("fresh matching resource_gate increase_by_1 evidence is missing")
    p6_violations = _p6_durable_violations(requirements, artifacts["checks"])
    if p6_violations:
        policy_violations.append("P6 COMPLETION-WITHOUT-DURABLE")
        reasons.extend(p6_violations)
    elif requirements and not artifacts["ok"]:
        policy_violations.append("ARTIFACT-CONTRACT-FAILED")

    policy = args.policy
    if policy == "auto":
        policy = "strict" if args.mode == "formal" else "warn"
    if policy == "skip":
        policy_violations = []
    if policy_violations and policy == "strict":
        exit_code = CONTRACT_FAILED
        decision = "CONTRACT_FAILED"
    elif policy_violations or not artifacts["ok"]:
        exit_code = WARN
        decision = "WARN"
    else:
        exit_code = PASS
        decision = "PASS"
        reasons.append("completion contract passed")

    doc = build_evidence(
        "completion_check",
        decision,
        reasons=reasons,
        parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
        task_key=args.task_key,
        transport_class=args.transport_class,
        io_mode=args.io_mode,
        artifact_paths=[req["path"] for req in requirements],
        policy_violations=policy_violations,
        exit_code=exit_code,
        extra={"artifact_checks": artifacts["checks"], "mode": args.mode, "policy": policy, "contract": str(args.contract or "")},
    )
    return emit(doc)


def cmd_worker_lint(args: argparse.Namespace) -> int:
    """Static-safety lint for fan-out worker R scripts (forbids sink(), etc.)."""
    if args.contract:
        contract = load_fanout_contract(args.contract)
        lint = lint_contract_workers(contract)
        results = lint["results"]
        issues = lint["issues"]
        errors = lint["errors"]
        task_key = contract.get("task_key")
    else:
        results = [lint_worker_file(p) for p in (args.code_file or [])]
        issues = [i for r in results for i in r.get("issues", [])]
        errors = [f"{r['path']}: {r['error']}" for r in results if r.get("error")]
        task_key = None
    # missing/unreadable files are a usage error; real lint findings are a BLOCK
    if issues:
        decision, exit_code = "BLOCK", BLOCK
    elif errors:
        decision, exit_code = "USAGE", 3
    else:
        decision, exit_code = "PASS", PASS
    reasons = issues or errors or [f"{len(results)} worker file(s) passed worker-lint"]
    doc = build_evidence(
        "worker_lint",
        decision,
        reasons=reasons,
        task_key=task_key,
        exit_code=exit_code,
        extra={"results": results, "issue_count": len(issues), "error_count": len(errors)},
    )
    return emit(doc)


def cmd_fanout_plan(args: argparse.Namespace) -> int:
    contract = load_fanout_contract(args.contract)
    task_key = contract.get("task_key") or "fanout"
    native_ok, native_reasons, parent_docs = _native_smoke_gate(contract, args.parent_evidence, task_key)
    if not native_ok:
        doc = build_evidence(
            "fanout_plan",
            "BLOCK",
            reasons=native_reasons,
            parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
            task_key=task_key,
            transport_class="BLOCKED",
            policy_violations=["MISSING-NATIVE-SMOKE-EVIDENCE"],
            exit_code=BLOCK,
            extra={"contract": str(args.contract)},
        )
        return emit(doc)
    plan = plan_fanout(contract, advise_parallel=not args.no_advise)
    submit_codes = {}
    for worker in contract.get("workers") or []:
        if isinstance(worker, dict) and worker.get("id"):
            try:
                submit_codes[worker["id"]] = build_submit_code(worker)
            except Exception as exc:
                submit_codes[worker["id"]] = f"<error: {exc}>"
    exit_code = PASS if plan["ok"] else CONTRACT_FAILED
    decision = "PASS" if plan["ok"] else "CONTRACT_FAILED"
    reasons = plan["problems"] or [
        f"{plan['worker_count']} workers planned; recommended start parallel={plan['recommended_max_parallel']} ({plan['advice_reason']})"
    ]
    doc = build_evidence(
        "fanout_plan",
        decision,
        reasons=reasons,
        parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
        task_key=plan["task_key"],
        exit_code=exit_code,
        extra=plan | {"submit_codes": submit_codes, "contract": str(args.contract)},
    )
    return emit(doc)


def cmd_fanout_run(args: argparse.Namespace) -> int:
    contract = load_fanout_contract(args.contract)
    transport = (args.transport or contract.get("transport") or "mcp-stdio").lower()
    task_key = contract.get("task_key") or "fanout"
    native_ok, native_reasons, parent_docs = _native_smoke_gate(contract, args.parent_evidence, task_key)
    if not native_ok:
        doc = build_evidence(
            "fanout_run",
            "BLOCK",
            reasons=native_reasons,
            parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
            task_key=task_key,
            transport_class="BLOCKED",
            policy_violations=["MISSING-NATIVE-SMOKE-EVIDENCE"],
            exit_code=BLOCK,
            extra={"contract": str(args.contract), "transport": transport},
        )
        return emit(doc)
    if transport != "mcp-stdio":
        doc = build_evidence(
            "fanout_run",
            "BLOCK",
            reasons=[
                f"fanout-run only submits via mcp-stdio (got transport={transport}). "
                "For native-wrapper, use fanout-plan to emit submit codes, submit them via the native "
                "mcp__r_studio__ wrapper, record job_ids with async-guard register-job, then use fanout-poll/merge-gate."
            ],
            task_key=contract.get("task_key"),
            transport_class="BLOCKED",
            exit_code=BLOCK,
            extra={"transport": transport, "contract": str(args.contract)},
        )
        return emit(doc)

    session_name = args.session_name or contract.get("session_name") or ""
    poll_interval = float(args.poll_interval_sec or contract.get("poll_interval_sec") or 30.0)
    job_timeout = float(args.job_timeout_min or contract.get("job_timeout_min") or 180.0)
    if args.dry_run:
        plan = plan_fanout(contract, advise_parallel=True)
        doc = build_evidence(
            "fanout_run",
            "PASS" if plan["ok"] else "CONTRACT_FAILED",
            reasons=["dry-run: contract validated, no jobs submitted"] + (plan["problems"] or []),
            parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
            task_key=task_key,
            transport_class="N/A",
            exit_code=PASS if plan["ok"] else CONTRACT_FAILED,
            extra=plan | {"dry_run": True, "contract": str(args.contract)},
        )
        return emit(doc)

    def submit_fn(code: str) -> dict[str, Any]:
        return submit_async(session_name, code, timeout=args.submit_timeout)

    def register_fn(worker_id: str, job_id: str) -> None:
        write_inflight(
            f"{task_key}:{worker_id}",
            {
                "task_key": f"{task_key}:{worker_id}",
                "fanout_task_key": task_key,
                "worker_id": worker_id,
                "job_id": job_id,
                "session_name": session_name,
                "transport_class": "MCP_STDIO_OK",
                "registered_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )

    def poll_fn(job_id: str) -> dict[str, Any]:
        return call_tool(
            "get_async_result",
            {"job_id": job_id},
            timeout=args.submit_timeout,
            retries=0,
        )

    result = run_fanout(
        contract,
        submit_fn=submit_fn,
        max_parallel=args.max_parallel,
        poll_interval_sec=poll_interval,
        job_timeout_min=job_timeout,
        first_artifact_timeout_min=args.first_artifact_timeout_min,
        reuse_existing=args.reuse_existing,
        register_fn=register_fn,
        poll_fn=poll_fn,
        max_iterations=args.max_iterations,
        auto_scale=args.auto_scale,
        memory_threshold=args.memory_threshold,
        max_parallel_cap=args.max_parallel_cap,
    )
    for wid in result.get("done", []):
        archive_inflight(f"{task_key}:{wid}", "worker complete")
    exit_code = PASS if result["ok"] else BLOCK
    decision = "PASS" if result["ok"] else "BLOCK"
    worker_total = len([w for w in (contract.get("workers") or []) if isinstance(w, dict)])
    reasons = [
        f"done={len(result.get('done', []))}/{worker_total} workers; "
        f"failed={result.get('failed')}; pending={result.get('pending')}; "
        f"still_running={result.get('still_running')}; max_parallel={result.get('max_parallel')}"
        + (f"; auto_scale start={result.get('start_max_parallel')}->{result.get('max_parallel')} "
           f"cap={result.get('max_parallel_cap')} scale_events={len(result.get('scale_log', []))}"
           if result.get("auto_scale") else "")
    ]
    doc = build_evidence(
        "fanout_run",
        decision,
        reasons=reasons,
        parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
        task_key=task_key,
        transport_class=result.get("transport_class", "MCP_STDIO_OK"),
        session_name=session_name,
        exit_code=exit_code,
        extra=result | {"contract": str(args.contract)},
    )
    return emit(doc)


def cmd_fanout_poll(args: argparse.Namespace) -> int:
    contract = load_fanout_contract(args.contract)
    task_key = contract.get("task_key") or "fanout"
    native_ok, native_reasons, parent_docs = _native_smoke_gate(contract, args.parent_evidence, task_key)
    if not native_ok:
        doc = build_evidence(
            "fanout_poll",
            "BLOCK",
            reasons=native_reasons,
            parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
            task_key=task_key,
            transport_class="BLOCKED",
            policy_violations=["MISSING-NATIVE-SMOKE-EVIDENCE"],
            exit_code=BLOCK,
            extra={"contract": str(args.contract)},
        )
        return emit(doc)
    poll = poll_once(contract)
    exit_code = PASS if poll["all_complete"] else WARN
    decision = "PASS" if poll["all_complete"] else "WARN"
    reasons = [
        f"done={len(poll['done'])}/{poll['worker_count']}; pending={poll['pending']}"
    ]
    doc = build_evidence(
        "fanout_poll",
        decision,
        reasons=reasons,
        parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
        task_key=task_key,
        exit_code=exit_code,
        extra=poll | {"contract": str(args.contract)},
    )
    return emit(doc)


def cmd_merge_gate(args: argparse.Namespace) -> int:
    contract = load_fanout_contract(args.contract)
    task_key = contract.get("task_key") or "fanout"
    native_ok, native_reasons, parent_docs = _native_smoke_gate(contract, args.parent_evidence, task_key)
    if not native_ok:
        doc = build_evidence(
            "merge_gate",
            "BLOCK",
            reasons=native_reasons,
            parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
            task_key=task_key,
            transport_class="BLOCKED",
            policy_violations=["MISSING-NATIVE-SMOKE-EVIDENCE"],
            exit_code=BLOCK,
            extra={"contract": str(args.contract)},
        )
        return emit(doc)
    gate = merge_gate(contract)
    artifact_paths: list[str] = []
    for s in gate["statuses"]:
        for key in ("expected_manifest", "expected_validation"):
            p = s["files"].get(key, {}).get("path")
            if p:
                artifact_paths.append(p)
    if gate["ok"]:
        exit_code, decision = PASS, "PASS"
    elif gate["all_complete"]:
        exit_code, decision = BLOCK, "BLOCK"
    else:
        exit_code, decision = CONTRACT_FAILED, "CONTRACT_FAILED"
    reasons = gate["violations"] or [
        f"all {gate['worker_count']} workers complete with manifest+validation present"
    ]
    doc = build_evidence(
        "merge_gate",
        decision,
        reasons=reasons,
        parent_evidence_ids=[doc.get("evidence_id") for doc in parent_docs if doc.get("evidence_id")],
        task_key=task_key,
        artifact_paths=artifact_paths,
        policy_violations=gate["violations"],
        exit_code=exit_code,
        extra=gate | {"contract": str(args.contract)},
    )
    return emit(doc)


def add_common_task_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-key")
    parser.add_argument("--project-root", default="")
    parser.add_argument("--task-label", default="")
    parser.add_argument("--session-name", default="")
    parser.add_argument("--transport-scope", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clauder_workbench")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor")
    p.add_argument("--expect-client", choices=["auto", "codex", "claude", "copilot", "all"], default="auto")
    p.add_argument("--check-toml-parse", action="store_true",
                   help="Validate that Codex config.toml parses cleanly; BLOCK if it does not.")

    p = sub.add_parser("transport-classify")
    p.add_argument("--native-ok", action="store_true")
    p.add_argument("--mcp-stdio-ok", action="store_true")
    p.add_argument("--http-ok", action="store_true")
    p.add_argument("--rscript-ok", action="store_true")
    p.add_argument("--native-required", action="store_true")
    p.add_argument("--allow-agent-hints", action="store_true")
    p.add_argument("--probe-mcp-stdio", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--probe-http", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--probe-rscript", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--timeout", type=float, default=20.0)

    p = sub.add_parser("tool-surface")
    p.add_argument("--tools", nargs="*", default=[])
    p.add_argument("--expected", nargs="*", default=[])
    p.add_argument("--probe-mcp-stdio", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--default-rstudio-expected", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--timeout", type=float, default=20.0)

    p = sub.add_parser("preflight")
    add_common_task_args(p)
    p.add_argument("--native-ok", action="store_true")
    p.add_argument("--mcp-stdio-ok", action="store_true")
    p.add_argument("--native-required", action="store_true")
    p.add_argument("--allow-agent-hints", action="store_true")
    p.add_argument("--probe-mcp-stdio", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--probe-http", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--probe-rscript", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--async-poll-attempts", type=int, default=2)
    p.add_argument("--transport-class")
    p.add_argument("--pid")
    p.add_argument("--parent-evidence", nargs="*", action="extend", default=[])

    p = sub.add_parser("connect")
    p.add_argument("--session-name", default="")
    p.add_argument("--native-ok", action="store_true")
    p.add_argument("--mcp-stdio-ok", action="store_true")
    p.add_argument("--http-ok", action="store_true")
    p.add_argument("--rscript-ok", action="store_true")
    p.add_argument("--native-required", action="store_true")
    p.add_argument("--allow-agent-hints", action="store_true")
    p.add_argument("--probe-mcp-stdio", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--probe-http", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--probe-rscript", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--max-attempts", type=int, default=20)

    p = sub.add_parser("async-guard")
    p.add_argument("action", choices=["pre-submit", "register-job", "submit", "list", "complete", "cancel"])
    add_common_task_args(p)
    p.add_argument("--job-id")
    p.add_argument("--io-mode", choices=["marshal_small", "durable_files", "hybrid"], default="durable_files")
    p.add_argument("--outputs", nargs="*", default=[])
    p.add_argument("--allow-large-outputs", action="store_true")
    p.add_argument("--force-new-job", action="store_true")
    p.add_argument("--via-mcp-stdio", action="store_true")
    p.add_argument("--code-file")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--reason")

    p = sub.add_parser("native-smoke")
    p.add_argument("action", choices=["start", "record", "complete", "list", "cancel"])
    add_common_task_args(p)
    p.add_argument("--step", choices=list(NATIVE_SMOKE_STEPS))
    p.add_argument("--ok", action="store_true")
    p.add_argument("--tool-layer", choices=["codex-native", "claude-native", "copilot-native"],
                   help="Agent native wrapper layer that produced this step. Defaults to <agent>-native when --agent was set at start, otherwise codex-native.")
    p.add_argument("--transport-class", choices=["NATIVE_MCP_OK", "MCP_STDIO_OK", "HTTP_ONLY_DIAGNOSTIC", "RSCRIPT_ONLY", "BLOCKED"], default="NATIVE_MCP_OK")
    p.add_argument("--session-count", type=int, default=0)
    p.add_argument("--pid")
    p.add_argument("--job-id")
    p.add_argument("--marker")
    p.add_argument("--raw-file")
    p.add_argument("--agent", choices=["codex", "claude", "copilot"], help="Agent identity recorded in native_smoke evidence (provenance for multi-agent setups).")
    p.add_argument("--require-raw-file", action="store_true", help="High-assurance mode: every recorded step must supply --raw-file (a dump of the real native MCP tool output); markers are verified to appear inside it.")
    p.add_argument("--max-age-min", type=float, default=20.0)
    p.add_argument("--force", action="store_true")
    p.add_argument("--reason")

    p = sub.add_parser("resource-gate")
    p.add_argument("mode", choices=["advise", "enforce"])
    p.add_argument("--task-key")
    p.add_argument("--current-parallel", type=int, default=1)
    p.add_argument("--memory-threshold", type=float, default=85.0)
    p.add_argument("--memory-override", type=float)
    p.add_argument("--output-root")
    p.add_argument("--previous-newest-mtime", type=float)
    p.add_argument("--io-blocked", action="store_true")
    p.add_argument("--rterm-unresponsive", action="store_true")
    p.add_argument("--mcp-unresponsive", action="store_true")

    p = sub.add_parser("completion-check")
    p.add_argument("--mode", choices=["formal", "diagnostic"], default="formal")
    p.add_argument("--policy", choices=["auto", "strict", "warn", "skip"], default="auto")
    p.add_argument("--contract")
    p.add_argument("--task-key")
    p.add_argument("--parent-evidence", nargs="*", action="extend", default=[])
    p.add_argument("--require-file", action="append", default=[])
    p.add_argument("--require-transport-class")
    p.add_argument("--require-preflight", action="store_true")
    p.add_argument("--require-native-smoke", action="store_true")
    p.add_argument("--native-smoke-max-age-min", type=float, default=60.0)
    p.add_argument("--transport-class")
    p.add_argument("--io-mode", choices=["marshal_small", "durable_files", "hybrid"], default="durable_files")
    p.add_argument("--outputs", nargs="*", default=[])
    p.add_argument("--state-file")
    p.add_argument("--require-resource-gate", action="store_true")
    p.add_argument("--resource-gate-max-age-min", type=float, default=60.0)
    p.add_argument("--require-job-complete", action="store_true")

    p = sub.add_parser("worker-lint")
    p.add_argument("--contract", help="Lint every worker code_file in this fan-out contract.")
    p.add_argument("--code-file", action="append",
                   help="Lint a specific worker .R file (repeatable). Alternative to --contract.")

    p = sub.add_parser("fanout-plan")
    p.add_argument("--contract", required=True)
    p.add_argument("--parent-evidence", nargs="*", action="extend", default=[])
    p.add_argument("--no-advise", action="store_true",
                   help="Skip memory-based parallelism advice; only validate the contract.")

    p = sub.add_parser("fanout-run")
    p.add_argument("--contract", required=True)
    p.add_argument("--parent-evidence", nargs="*", action="extend", default=[])
    p.add_argument("--transport", choices=["mcp-stdio", "native-wrapper"], default=None)
    p.add_argument("--session-name", default="")
    p.add_argument("--max-parallel", type=int)
    p.add_argument("--poll-interval-sec", type=float)
    p.add_argument("--job-timeout-min", type=float)
    p.add_argument("--first-artifact-timeout-min", type=float,
                   help="Fail a worker that produces no output file within this many minutes (detects silent R death).")
    p.add_argument("--reuse-existing", action="store_true",
                   help="Resume: treat already-complete worker outputs as done and skip resubmission. "
                        "Default off (always resubmits this run and only counts fresh outputs).")
    p.add_argument("--submit-timeout", type=float, default=60.0)
    p.add_argument("--max-iterations", type=int)
    p.add_argument("--auto-scale", action="store_true",
                   help="Dynamic concurrency (best-practice §6): start at --max-parallel and raise "
                        "concurrency by 1 each poll cycle while system memory stays below "
                        "--memory-threshold and work remains; throttle (no new submissions) at/above it. "
                        "Running jobs are never killed.")
    p.add_argument("--memory-threshold", type=float, default=85.0,
                   help="Memory %% ceiling for --auto-scale (default 85). At/above it, no new workers are submitted.")
    p.add_argument("--max-parallel-cap", type=int,
                   help="Hard upper bound for --auto-scale concurrency (default: worker count).")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate contract and report plan without submitting any jobs.")

    p = sub.add_parser("fanout-poll")
    p.add_argument("--contract", required=True)
    p.add_argument("--parent-evidence", nargs="*", action="extend", default=[])

    p = sub.add_parser("merge-gate")
    p.add_argument("--contract", required=True)
    p.add_argument("--parent-evidence", nargs="*", action="extend", default=[])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cmd == "doctor":
            return cmd_doctor(args)
        if args.cmd == "transport-classify":
            return cmd_transport_classify(args)
        if args.cmd == "tool-surface":
            return cmd_tool_surface(args)
        if args.cmd == "preflight":
            return cmd_preflight(args)
        if args.cmd == "connect":
            return cmd_connect(args)
        if args.cmd == "async-guard":
            return cmd_async_guard(args)
        if args.cmd == "native-smoke":
            return cmd_native_smoke(args)
        if args.cmd == "resource-gate":
            return cmd_resource_gate(args)
        if args.cmd == "completion-check":
            return cmd_completion_check(args)
        if args.cmd == "worker-lint":
            return cmd_worker_lint(args)
        if args.cmd == "fanout-plan":
            return cmd_fanout_plan(args)
        if args.cmd == "fanout-run":
            return cmd_fanout_run(args)
        if args.cmd == "fanout-poll":
            return cmd_fanout_poll(args)
        if args.cmd == "merge-gate":
            return cmd_merge_gate(args)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        doc = build_evidence("internal_error", "BLOCK", reasons=[f"{type(exc).__name__}: {exc}"], exit_code=BLOCK)
        print_json(doc)
        return BLOCK
    parser.error(f"unknown command: {args.cmd}")
    return BLOCK


if __name__ == "__main__":
    raise SystemExit(main())
