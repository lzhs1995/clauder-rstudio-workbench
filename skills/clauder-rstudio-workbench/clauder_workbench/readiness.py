"""Client-specific readiness. Read-only unless --repair safe is explicit."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import psutil

from . import config
from .config_store import update_config
from .evidence import build_evidence, load_json
from .mcp_client import connection_probe


def client_path(client: str, explicit: Path | None = None) -> Path:
    return Path(explicit or {"codex": config.CODEX_CONFIG, "claude": config.CLAUDE_JSON,
                             "copilot": config.COPILOT_CONFIG}[client]).expanduser().resolve()


def client_process(client: str) -> dict | None:
    try:
        for process in psutil.Process().parents():
            if client in process.name().lower():
                return {"pid": process.pid, "created_at": process.create_time()}
    except psutil.Error:
        pass
    return None


def client_context(client: str, path: Path | None = None) -> dict:
    path = client_path(client, path)
    raw = path.read_bytes() if path.is_file() else None
    # Codex supplies this in the real agent shell. Other clients must supply
    # their own documented session identity; no process is launched to infer it.
    session = os.environ.get("CODEX_THREAD_ID") if client == "codex" else None
    if not session:
        session = os.environ.get("CLAUDER_WORKBENCH_CLIENT_SESSION_ID")
    return {"client": client, "client_session_id": session, "client_process": client_process(client),
            "config_path": str(path),
            "config_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None}


def load_server(client: str, path: Path) -> tuple:
    raw = path.read_text(encoding="utf-8-sig")
    if client == "codex":
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        data = tomllib.loads(raw)
        servers = data.get("mcp_servers", {})
    else:
        data = json.loads(raw)
        servers = data.get("mcpServers", {})
    server = servers.get("r-studio")
    if not isinstance(server, dict):
        raise ValueError("R_STUDIO_CONFIG_MISSING")
    if server.get("enabled") is False or server.get("disabled") is True:
        raise ValueError("R_STUDIO_EXPLICITLY_DISABLED")
    command = server.get("command")
    if server.get("url") or not isinstance(command, str):
        raise ValueError("PERSISTENT_STDIO_COMMAND_REQUIRED")
    exe = Path(command)
    if not exe.is_absolute() or not exe.is_file() or exe.name not in {"clauder-mcp", "clauder-mcp.exe"}:
        raise ValueError("PERSISTENT_ABSOLUTE_EXECUTABLE_REQUIRED")
    args = server.get("args", [])
    env = server.get("env", {})
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise ValueError("INVALID_ARGUMENTS")
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("INVALID_ENVIRONMENT")
    home_key = "USERPROFILE" if os.name == "nt" else "HOME"
    if not env.get(home_key) or not Path(env[home_key]).is_absolute():
        raise ValueError("EXPLICIT_DISCOVERY_HOME_REQUIRED")
    if not env.get("UV_CACHE_DIR") or not Path(env["UV_CACHE_DIR"]).is_absolute():
        raise ValueError("USER_WRITABLE_CACHE_PATH_REQUIRED")
    if client == "codex":
        timeout = server.get("startup_timeout_sec")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("STARTUP_TIMEOUT_REQUIRED")
    return command, args, env


def discovery_identity(server_spec: tuple, session_name: str) -> dict:
    env = server_spec[2]
    root = Path(env["USERPROFILE" if os.name == "nt" else "HOME"]) / ".claude_r_sessions"
    matches = []
    for path in root.glob("*.json"):
        try:
            item = load_json(path)
            if isinstance(item, dict) and item.get("session_name") == session_name:
                matches.append(item)
        except (OSError, ValueError):
            pass  # Unknown/corrupt records are never removed by a reader.
    if len(matches) != 1:
        raise ValueError("DISCOVERY_TARGET_MISSING_OR_AMBIGUOUS")
    item = matches[0]
    if type(item.get("pid")) is not int or item["pid"] <= 0 or type(item.get("port")) is not int or not 0 < item["port"] < 65536:
        raise ValueError("DISCOVERY_IDENTITY_INVALID")
    # Tokens are authentication material, not shareable evidence.
    return {k: item.get(k) for k in ("session_name", "pid", "port", "started_at")}


def native_status(path: Path | None, *, client: str, context: dict,
                  session_name: str, pid: int, task_key: str, max_age_min: float) -> dict:
    from .cli import NATIVE_SMOKE_STEPS, _native_smoke_parent_ok, _native_smoke_step_valid
    if path is None:
        return {"ok": False, "reason": "CURRENT_AGENT_NATIVE_SMOKE_REQUIRED"}
    try:
        doc = load_json(path)
        if not context.get("client_session_id") or not context.get("config_sha256") or not context.get("client_process"):
            raise ValueError("CURRENT_CLIENT_CONTEXT_UNKNOWN")
        if not _native_smoke_parent_ok([doc], task_key, max_age_min):
            raise ValueError("NATIVE_CHAIN_STALE_OR_INVALID")
        if doc.get("task_key") != task_key or doc.get("agent") != client:
            raise ValueError("NATIVE_AGENT_OR_TASK_MISMATCH")
        if doc.get("session_name") != session_name or str(doc.get("pid")) != str(pid):
            raise ValueError("NATIVE_RSTUDIO_IDENTITY_MISMATCH")
        extra = doc.get("extra", {})
        if extra.get("client_context") != context:
            raise ValueError("NATIVE_CLIENT_CONTEXT_OR_CONFIG_CHANGED")
        steps = extra.get("steps", {})
        state = {"agent": client, "require_raw_file": True, "steps": steps}
        for step in NATIVE_SMOKE_STEPS:
            entry = steps.get(step, {})
            if not entry.get("raw_file_proof") or not _native_smoke_step_valid(step, entry, state)[0]:
                raise ValueError("NATIVE_RAW_EVIDENCE_INVALID")
            if entry.get("evidence_id") not in doc["parent_evidence_ids"]:
                raise ValueError("NATIVE_PARENT_LINK_MISMATCH")
        raw = Path(steps["execute_r"]["raw_file_proof"]["evidence_copy"]).read_text(encoding="utf-8")
        if not re.search(r"(?<!\d)" + re.escape(str(pid)) + r"(?!\d)", raw):
            raise ValueError("NATIVE_PID_NOT_IN_RAW_OUTPUT")
        return {"ok": True, "evidence_id": doc["evidence_id"], "evidence_path": str(path)}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"ok": False, "reason": str(exc) if type(exc) is ValueError else type(exc).__name__}


def ensure_ready(*, client: str, session_name: str, task_key: str,
                 config_file: Path | None = None, repair: str = "none",
                 require_native: bool = False, native_evidence: Path | None = None,
                 timeout: float = 30, max_age_min: float = 10) -> dict:
    path = client_path(client, config_file)
    layers = {"config_path": str(path), "client": client,
              "config_scope": "explicit_file_not_running_agent_effective_config",
              "repair": repair, "native": {"ok": False, "reason": "NOT_CHECKED"}}
    try:
        if repair == "safe":
            if not config.PERSISTENT_MCP.is_file():
                raise ValueError("REPAIR_REQUIRES_EXISTING_PERSISTENT_EXECUTABLE")
            layers["config_update"] = update_config(path, client=client,
                command=config.PERSISTENT_MCP, home=config.HOME, cache=config.UV_CACHE_DIR)
        spec = load_server(client, path)
        context = client_context(client, path)
        layers["client_context"] = context
        identity = discovery_identity(spec, session_name)
        layers["discovery"] = identity
        probe = connection_probe(session_name, timeout, server_spec=spec, config_path=path)
        layers["stdio"] = probe
        after = discovery_identity(spec, session_name)
        if not probe.get("ok") or identity != after or probe.get("pid") != identity["pid"]:
            raise ValueError("RSTUDIO_LIVE_PROBE_FAILED_OR_IDENTITY_CHANGED")
        if client_context(client, path) != context:
            raise ValueError("CONFIG_CHANGED_DURING_PROBE")
        if require_native or native_evidence:
            layers["native"] = native_status(native_evidence, client=client, context=context,
                session_name=session_name, pid=identity["pid"], task_key=task_key, max_age_min=max_age_min)
        if require_native and not layers["native"].get("ok"):
            raise ValueError(layers["native"]["reason"])
        native_ok = layers["native"].get("ok")
        return build_evidence("ensure_ready", "PASS", task_key=task_key, agent=client,
            session_name=session_name, pid=identity["pid"],
            transport_class="NATIVE_MCP_OK" if native_ok else "MCP_STDIO_OK",
            parent_evidence_ids=[layers["native"]["evidence_id"]] if native_ok else [],
            reasons=["explicit target is ready on the verified transport only"], extra=layers)
    except Exception as exc:
        # Parser exceptions may contain user secrets. Only emit our stable codes.
        reason = str(exc) if type(exc) is ValueError and re.fullmatch(r"[A-Z_]+", str(exc)) else type(exc).__name__
        return build_evidence("ensure_ready", "BLOCK", task_key=task_key, agent=client,
            session_name=session_name, transport_class="BLOCKED", exit_code=config.BLOCK,
            reasons=[reason], extra=layers)
