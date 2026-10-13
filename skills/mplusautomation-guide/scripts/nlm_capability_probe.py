#!/usr/bin/env python3
"""Probe the installed NotebookLM CLI without changing authentication state."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


AUTH_MARKERS = ("login", "authentication", "unauthorized", "401", "cookie")
NETWORK_MARKERS = ("timeout", "timed out", "connection", "proxy", "dns", "network")
VERSION_RE = re.compile(r"\b\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\b")
Runner = Callable[..., subprocess.CompletedProcess[str]]


def _safe_error(stdout: str, stderr: str) -> str:
    """Return a short category only; never persist raw auth/network output."""
    text = f"{stdout}\n{stderr}".lower()
    if any(marker in text for marker in AUTH_MARKERS):
        return "AUTH_FAILURE"
    if any(marker in text for marker in NETWORK_MARKERS):
        return "NETWORK_FAILURE"
    return "COMMAND_FAILURE"


def _notebook_count(text: str) -> int | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("notebooks", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
    return None


def probe(
    executable: str = "nlm",
    profile: str | None = None,
    attempts: int = 3,
    runner: Runner = subprocess.run,
) -> dict:
    """Run version and notebook-list checks; never invoke ``nlm login``."""
    if attempts < 1:
        raise ValueError("attempts must be positive")
    resolved = shutil.which(executable) or executable
    version_result = runner(
        [resolved, "--version"], capture_output=True, text=True, timeout=60, check=False
    )
    version_text = f"{version_result.stdout}\n{version_result.stderr}"
    version_match = VERSION_RE.search(version_text)
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "executable": resolved,
        "cli_version": version_match.group(0) if version_match else None,
        "profile": profile,
        "auth_check": "nlm notebook list --json",
        "attempts": [],
        "notebook_count": None,
        "status": "NLM_ERROR",
    }
    command: Sequence[str] = [resolved, "notebook", "list", "--json"]
    if profile:
        command = [*command, "--profile", profile]
    for attempt in range(1, attempts + 1):
        completed = runner(
            command, capture_output=True, text=True, timeout=120, check=False
        )
        if completed.returncode == 0:
            count = _notebook_count(completed.stdout)
            if count is not None:
                result["notebook_count"] = count
                result["attempts"].append({"attempt": attempt, "exit_code": 0})
                result["status"] = "AUTH_VALID"
                break
        result["attempts"].append(
            {
                "attempt": attempt,
                "exit_code": completed.returncode,
                "failure_class": _safe_error(completed.stdout, completed.stderr),
            }
        )
    else:
        failures = [item.get("failure_class") for item in result["attempts"]]
        if len(failures) == attempts and all(item == "AUTH_FAILURE" for item in failures):
            result["status"] = "AUTH_REQUIRED"
        elif any(item == "NETWORK_FAILURE" for item in failures):
            result["status"] = "NETWORK_ERROR"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default="nlm")
    parser.add_argument("--profile")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = probe(args.executable, args.profile, args.attempts)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    return 0 if result["status"] == "AUTH_VALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
