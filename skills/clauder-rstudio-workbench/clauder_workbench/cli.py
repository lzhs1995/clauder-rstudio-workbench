from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    LOCAL_CLAUDER_BRIDGE,
    PASS,
    PYTHON314,
    TRANSPORT_UNSTABLE,
    WARN,
    WINDOWS_STORE_PYTHON,
    python_command,
)
from .evidence import build_evidence, load_json, print_json, stable_task_key, write_evidence
from .inflight import archive_inflight, list_inflight, load_inflight, write_inflight
from .mcp_client import EXPECTED_R_STUDIO_TOOLS, call_tool, extract_job_id, list_tools, preflight_smoke
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


def cmd_doctor(args: argparse.Namespace) -> int:
    reasons: list[str] = []
    warnings: list[str] = []
    install_info, install_info_path = _load_install_info()
    expected_clients = _expected_clients(args, install_info)
    py_smoke = run_python_smoke()
    if not PYTHON314.exists():
        warnings.append(f"default Python314 missing: {PYTHON314}; using {python_command()}")
    if str(WINDOWS_STORE_PYTHON).lower() in current_python().lower():
        reasons.append("current python appears to be WindowsApps redirector")
    if not LOCAL_CLAUDER_BRIDGE.exists():
        warnings.append(f"local patched ClaudeR bridge missing: {LOCAL_CLAUDER_BRIDGE}")
    if not DISCOVERY_DIR.exists():
        warnings.append(f"discovery directory missing: {DISCOVERY_DIR}")
    if "codex" in expected_clients:
        if not CODEX_CONFIG.exists():
            warnings.append(f"Codex config missing: {CODEX_CONFIG}")
        elif not codex_config_mentions_local_bridge():
            warnings.append("Codex config does not mention local patched ClaudeR bridge")
    if "claude" in expected_clients and not CLAUDE_JSON.exists():
        warnings.append(f"Claude Code user config missing: {CLAUDE_JSON}")
    if "copilot" in expected_clients and not COPILOT_CONFIG.exists():
        warnings.append(f"Copilot MCP config missing: {COPILOT_CONFIG}")

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
            "discovery_dir": str(DISCOVERY_DIR),
            "codex_config": str(CODEX_CONFIG),
            "claude_json": str(CLAUDE_JSON),
            "copilot_config": str(COPILOT_CONFIG),
            "install_info_path": str(install_info_path) if install_info_path else "",
            "install_info": install_info,
            "expect_client": args.expect_client,
            "expected_clients": expected_clients,
            "discovery_sessions": discovery_sessions(),
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

    parent_docs = []
    for path in args.parent_evidence or []:
        try:
            parent_docs.append(load_json(path))
        except Exception as exc:
            reasons.append(f"could not read parent evidence {path}: {exc}")

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


def add_common_task_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-key")
    parser.add_argument("--project-root", default="")
    parser.add_argument("--task-label", default="")
    parser.add_argument("--session-name", default="")
    parser.add_argument("--transport-scope", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clauder_workbench")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor")
    p.add_argument("--expect-client", choices=["auto", "codex", "claude", "copilot", "all"], default="auto")

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
    p.add_argument("--parent-evidence", nargs="*", default=[])

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
    p.add_argument("--parent-evidence", nargs="*", default=[])
    p.add_argument("--require-file", action="append", default=[])
    p.add_argument("--require-transport-class")
    p.add_argument("--require-preflight", action="store_true")
    p.add_argument("--transport-class")
    p.add_argument("--io-mode", choices=["marshal_small", "durable_files", "hybrid"], default="durable_files")
    p.add_argument("--outputs", nargs="*", default=[])
    p.add_argument("--state-file")
    p.add_argument("--require-resource-gate", action="store_true")
    p.add_argument("--resource-gate-max-age-min", type=float, default=60.0)
    p.add_argument("--require-job-complete", action="store_true")

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
        if args.cmd == "resource-gate":
            return cmd_resource_gate(args)
        if args.cmd == "completion-check":
            return cmd_completion_check(args)
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
