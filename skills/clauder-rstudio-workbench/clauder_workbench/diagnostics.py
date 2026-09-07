from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .mcp_client import connection_probe
from .transport import discovery_sessions, http_execute_probe, terminal_status


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
