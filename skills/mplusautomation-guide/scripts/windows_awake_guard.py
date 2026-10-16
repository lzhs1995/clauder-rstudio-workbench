"""Keep an owned Windows batch awake until its owner ends or requests release.

Requires psutil. Does not change a power plan, keep the display on, or override
deliberate sleep/lid actions. Run as a separate Windows Python process.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

import psutil
from mplus_queue import atomic_replace

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    # A monitoring reader may briefly hold a Windows handle without delete sharing.
    atomic_replace(temporary, path)


def owner_alive(owner: dict) -> bool:
    try:
        process = psutil.Process(owner["pid"])
        return (abs(process.create_time() - owner["created"]) < 0.01
                and process.is_running())
    except psutil.NoSuchProcess:
        return False


def run(owner_file: Path, output: Path, interval: float) -> int:
    if sys.platform != "win32":
        raise RuntimeError("Use native Windows Python for the Windows owner")
    if not math.isfinite(interval) or not 0 < interval <= 60:
        raise ValueError("interval must be positive and at most 60 seconds")
    owner = json.loads(owner_file.read_text(encoding="utf-8-sig"))["owner"]
    if (type(owner["pid"]) is not int or owner["pid"] <= 0
            or type(owner["created"]) not in (int, float)
            or not math.isfinite(owner["created"])):
        raise ValueError("owner requires a positive PID and finite creation time")
    if not owner_alive(owner):
        raise RuntimeError("Owner PID/creation time no longer identifies a live process")
    # An exclusive output root prevents competing guards from sharing receipts.
    output.mkdir(parents=True, exist_ok=False)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    set_state = kernel.SetThreadExecutionState
    set_state.argtypes = [ctypes.c_uint]
    set_state.restype = ctypes.c_uint
    previous = set_state(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    if not previous:
        raise ctypes.WinError(ctypes.get_last_error())
    reason = "error"
    try:
        process = psutil.Process()
        write_json(output / "identity.json", {
            "pid": process.pid, "created": process.create_time(), "owner": owner,
            "started_at": now(), "previous_execution_state": previous,
            "display_required": False, "away_mode_required": False,
        })
        while True:
            if (output / "stop.request").exists():
                reason = "stop_requested"
                break
            if not owner_alive(owner):
                reason = "owner_ended_or_replaced"
                break
            write_json(output / "heartbeat.json", {"at": now(), "owner": owner})
            time.sleep(interval)
    except KeyboardInterrupt:
        reason = "interrupted"
        raise
    finally:
        # The same thread that acquired the request must release it.
        released = bool(set_state(ES_CONTINUOUS))
        write_json(output / "completion.json", {
            "finished_at": now(), "reason": reason, "released": released,
        })
        if not released:
            raise ctypes.WinError(ctypes.get_last_error())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=10)
    args = parser.parse_args()
    return run(args.owner_file, args.output, args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
