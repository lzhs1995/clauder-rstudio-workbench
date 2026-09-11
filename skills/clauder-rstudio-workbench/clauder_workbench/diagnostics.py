from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .mcp_client import connection_probe
from .transport import discovery_sessions, http_execute_probe, terminal_status


STARTUP_STATES = (
    "CONFIG_VALID",
    "BRIDGE_VALID",
    "RSTUDIO_DISCOVERED",
    "TARGET_BOUND",
    "NATIVE_TOOLS_OBSERVED",
    "NATIVE_SMOKE_VERIFIED",
    "READY",
)


def agent_tool_status(inventory: Path | None) -> dict[str, Any]:
    # 工具名仅作为外部观察，不能建立 native-smoke 的证据链。
    result: dict[str, Any] = {"status": "UNKNOWN", "native_verified": False,
                              "scope": "supplied_inventory_observation_not_native_smoke"}
    if inventory is None:
        return result
    try:
        raw = inventory.read_bytes()
        doc = json.loads(raw)
        names = doc if isinstance(doc, list) else doc.get("tools")
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise ValueError("expected a JSON list of tool names or an object with tools: [names]")
        found = sorted(n for n in names if re.search(r"mcp__r[-_]studio__", n))
        result.update(status="OBSERVED_PRESENT" if found else "OBSERVED_ABSENT",
                      matching_tools=found, inventory_path=str(inventory),
                      inventory_sha256=hashlib.sha256(raw).hexdigest())
    except (OSError, ValueError, AttributeError) as exc:
        result.update(status="INVALID", reason=str(exc))
    return result


def startup_contract(layers: dict[str, Any], *, session_name: str = "") -> dict[str, Any]:
    """Classify connection readiness without confusing independent layers.

    This is intentionally evidence-oriented: a configured file, a working
    stdio bridge, a live discovery record and the current agent tool registry
    are separate gates.  The function never treats HTTP/stdio as native proof.
    """
    states: list[dict[str, Any]] = []

    config_ok = bool((layers.get("client_config") or {}).get("ok"))
    states.append({"state": "CONFIG_VALID", "ok": config_ok,
                   "reason": None if config_ok else "CONFIG_INVALID"})
    bridge_ok = bool((layers.get("bridge") or {}).get("ok"))
    states.append({"state": "BRIDGE_VALID", "ok": bridge_ok,
                   "reason": None if bridge_ok else "BRIDGE_NOT_STARTABLE"})

    rstudio = layers.get("rstudio") or {}
    discovery = rstudio.get("discovery") or []
    named = [item for item in discovery if item.get("session_name") == session_name] if session_name else []
    healthy = [item for item in discovery if item.get("port_open") and item.get("token_present")]
    discovered_ok = len(named) == 1 and bool(named[0].get("port_open")) if session_name else len(healthy) == 1
    if discovered_ok:
        discovery_reason = None
    elif session_name and not named:
        discovery_reason = "DISCOVERY_RECORD_MISSING"
    elif session_name and len(named) > 1:
        discovery_reason = "DISCOVERY_RECORD_AMBIGUOUS"
    elif discovery and not healthy:
        discovery_reason = "DISCOVERY_RECORD_STALE"
    elif len(healthy) > 1:
        discovery_reason = "TARGET_NAME_MISMATCH"
    else:
        discovery_reason = "RSTUDIO_ADDIN_NOT_RUNNING"
    states.append({"state": "RSTUDIO_DISCOVERED", "ok": discovered_ok, "reason": discovery_reason})

    bound_ok = bool(rstudio.get("ok"))
    states.append({"state": "TARGET_BOUND", "ok": bound_ok,
                   "reason": None if bound_ok else "TARGET_NAME_MISMATCH"})

    tools = layers.get("agent_tools") or {}
    tools_ok = tools.get("status") == "OBSERVED_PRESENT"
    tool_reason = None if tools_ok else (
        "CODEX_NATIVE_TOOLS_NOT_REGISTERED" if tools.get("status") == "OBSERVED_ABSENT"
        else "NATIVE_TOOLS_NOT_OBSERVED"
    )
    states.append({"state": "NATIVE_TOOLS_OBSERVED", "ok": tools_ok, "reason": tool_reason})

    # An inventory is only an observation.  The four-call native-smoke chain
    # remains the sole proof that the current task can execute RStudio tools.
    smoke_ok = bool((layers.get("native") or {}).get("ok"))
    states.append({"state": "NATIVE_SMOKE_VERIFIED", "ok": smoke_ok,
                   "reason": None if smoke_ok else "NATIVE_SMOKE_NOT_VERIFIED"})

    ready = all(item["ok"] for item in states)
    reason = None if ready else next(item["reason"] for item in states if not item["ok"])
    next_action = {
        "CONFIG_INVALID": "repair the selected client entry, then rerun diagnostics",
        "BRIDGE_NOT_STARTABLE": "verify the persistent clauder-mcp executable and provenance",
        "RSTUDIO_ADDIN_NOT_RUNNING": "run ClaudeR claudeAddin() and Start Server in the target RStudio",
        "DISCOVERY_RECORD_MISSING": "use an existing discovered session name; do not guess a target",
        "DISCOVERY_RECORD_STALE": "start the Addin for the intended RStudio session; stale records are not reused",
        "DISCOVERY_RECORD_AMBIGUOUS": "select exactly one discovered session by name and PID",
        "TARGET_NAME_MISMATCH": "bind to a session listed by list_sessions/discovery",
        "CODEX_NATIVE_TOOLS_NOT_REGISTERED": "create a fresh Codex task context; MCP tools are task-scoped",
        "NATIVE_TOOLS_NOT_OBSERVED": "supply the current task tool inventory, then run native-smoke",
        "NATIVE_SMOKE_NOT_VERIFIED": "run list_sessions → execute_r → execute_r_async/get_async_result in the current task",
    }.get(reason or "", "run the four-step native smoke in the current task")
    return {"states": states, "ok": ready, "reason": reason,
            "next_action": next_action,
            "native_gate": "NATIVE_SMOKE_OK" if smoke_ok else "NOT_VERIFIED"}


def connection_layers(config_check: dict[str, Any], *, session_name: str = "",
                      timeout: float = 30.0, probe_http: bool = False,
                      inventory: Path | None = None) -> dict[str, Any]:
    live = connection_probe(session_name=session_name, timeout=timeout)
    sessions = discovery_sessions()
    matches = [s for s in sessions if s.get("session_name") == session_name]
    # bind 后若会话消失，bridge 可能重新选取默认会话；不能把其他 PID 当目标成功。
    identity_ok = bool(live.get("ok") and len(matches) == 1 and matches[0].get("pid") == live.get("pid"))
    return {
        "terminal": terminal_status(),
        "client_config": {**config_check, "scope": "configured_file_only",
                          "running_agent_effective_config": "UNKNOWN", "writer_identity": "UNKNOWN"},
        "bridge": {"ok": bool(live.get("bridge_ok")), "scope": "independent_mcp_stdio",
                   "command": live.get("command"), "args": live.get("args"),
                   "tools": live.get("tools", []), "missing": live.get("missing", [])},
        "rstudio": {"ok": identity_ok, "scope": "explicit_session_live_execution",
                    "session_name": session_name, "pid": live.get("pid"), "r_version": live.get("r_version"),
                    "reason": live.get("reason") if identity_ok or not live.get("ok") else "discovery/live PID mismatch or ambiguous session",
                    "discovery": sessions, "probe": live},
        "agent_tools": agent_tool_status(inventory),
        "http": http_execute_probe(session_name=session_name, timeout=min(timeout, 10.0)) if probe_http else {"status": "NOT_CHECKED"},
    }
