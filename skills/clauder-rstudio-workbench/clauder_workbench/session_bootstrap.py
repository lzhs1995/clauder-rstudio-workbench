"""Codex session-start preflight for the persistent ClaudeR/RStudio bridge.

This command runs before a Codex task is created.  It validates the durable
configuration and bridge provenance, but deliberately does *not* claim that
the host injected native ``mcp__r_studio__*`` tools: that registry is owned by
the Codex app-server and is only observable from the current task layer.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import BLOCK, CODEX_CONFIG, EVIDENCE_DIR, LOCAL_CLAUDER_BRIDGE, PASS, PERSISTENT_MCP, UV_CACHE_DIR
from .evidence import build_evidence, print_json, write_evidence


def _toml_ok() -> tuple[bool, str | None]:
    if not CODEX_CONFIG.exists():
        return False, f"Codex config missing: {CODEX_CONFIG}"
    try:
        import tomllib
        raw = CODEX_CONFIG.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        tomllib.loads(raw.decode("utf-8"))
        return True, None
    except Exception as exc:  # pragma: no cover - platform parser details
        return False, f"Codex config is not valid TOML: {exc}"


def _server_config() -> tuple[bool, list[str], dict[str, Any]]:
    ok, error = _toml_ok()
    reasons = [error] if error else []
    details: dict[str, Any] = {"config_path": str(CODEX_CONFIG)}
    if not ok:
        return False, reasons, details
    import tomllib
    raw = CODEX_CONFIG.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    data = tomllib.loads(raw.decode("utf-8"))
    server = ((data.get("mcp_servers") or {}).get("r-studio") or {})
    command = str(server.get("command") or "")
    env = server.get("env") or {}
    timeout = float(server.get("startup_timeout_sec") or 0)
    details.update({"command": command, "startup_timeout_sec": timeout,
                    "env_keys": sorted(str(k) for k in env)})
    if Path(command).resolve() != PERSISTENT_MCP.resolve():
        reasons.append(f"r-studio command is not persistent bridge: {command or '<missing>'}")
    if not Path(command).exists():
        reasons.append(f"persistent bridge executable missing: {command}")
    if timeout < 180:
        reasons.append("r-studio startup_timeout_sec must be at least 180")
    if not env.get("HOME") and not os.name == "nt":
        reasons.append("r-studio MCP env HOME is missing")
    return not reasons, reasons, details


def run(*, client: str = "codex", fail_closed: bool = True) -> int:
    """Run the global startup contract and emit durable evidence.

    Native registration is reported as ``UNKNOWN`` here by design.  A later
    current-task native smoke is required to transition to ``READY``.
    """
    config_ok, reasons, details = _server_config()
    bridge_ok = LOCAL_CLAUDER_BRIDGE.exists()
    if not bridge_ok:
        reasons.append(f"ClaudeR bridge source is missing: {LOCAL_CLAUDER_BRIDGE}")
    decision = "PASS" if config_ok and bridge_ok else "BLOCK"
    exit_code = PASS if decision == "PASS" else BLOCK
    native_status = "UNKNOWN"
    evidence = build_evidence(
        "session_bootstrap",
        decision,
        reasons=(reasons or ["global Codex r-studio configuration and bridge preflight passed"]),
        transport_class="NOT_VERIFIED",
        exit_code=exit_code,
        extra={
            "client": client,
            "scope": "global_session_start_preflight",
            "persistent_bridge": str(PERSISTENT_MCP),
            "uv_cache_dir": str(UV_CACHE_DIR),
            "bridge_source": str(LOCAL_CLAUDER_BRIDGE),
            "native_registration": native_status,
            "native_registration_note": "Codex app-server task tool registry is not visible to a shell hook; current-task native smoke remains mandatory",
            "fail_closed": fail_closed,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **details,
        },
    )
    path = write_evidence(evidence, evidence_dir=EVIDENCE_DIR)
    evidence.setdefault("extra", {})["evidence_path"] = str(path)
    # Hook consumers can display this without parsing human output.
    print_json({"continue": decision == "PASS", "session_bootstrap": evidence})
    return exit_code if fail_closed else PASS


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="session-bootstrap")
    parser.add_argument("--client", default="codex")
    parser.add_argument("--no-fail-closed", action="store_true")
    args = parser.parse_args(argv)
    return run(client=args.client, fail_closed=not args.no_fail_closed)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
