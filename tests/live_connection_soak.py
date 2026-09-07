"""Opt-in live protocol soak. No R jobs, restarts, cancellation or data mutation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import psutil

from clauder_workbench.config_store import atomic_bytes
from clauder_workbench.readiness import ensure_ready


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client", choices=["codex", "claude", "copilot"], required=True)
    p.add_argument("--config-file", type=Path, required=True)
    p.add_argument("--session-name", required=True)
    p.add_argument("--protected-pid", type=int, nargs="+", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--duration-sec", type=float, default=3600)
    p.add_argument("--interval-sec", type=float, default=60)
    args = p.parse_args()
    if args.duration_sec <= 0 or args.interval_sec <= 0:
        p.error("duration and interval must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output / "checkpoint.json"
    if checkpoint.exists():
        p.error("existing run: use a new output directory; evidence is not overwritten")
    identities = {pid: psutil.Process(pid).create_time() for pid in args.protected_pid}
    config_hash = hashlib.sha256(args.config_file.read_bytes()).hexdigest()
    started = time.monotonic()
    records = []
    slot = 0
    while True:
        scheduled = started + slot * args.interval_sec
        time.sleep(max(0, scheduled - time.monotonic()))
        elapsed = time.monotonic() - started
        protected = {}
        for pid, stamp in identities.items():
            try:
                proc = psutil.Process(pid)
                protected[str(pid)] = proc.is_running() and proc.create_time() == stamp
            except psutil.Error:
                protected[str(pid)] = False
        begin = time.monotonic()
        result = ensure_ready(client=args.client, config_file=args.config_file,
            session_name=args.session_name, task_key="connection-soak", timeout=30)
        row = dict(slot=slot, elapsed_sec=elapsed, latency_sec=time.monotonic()-begin,
            at=datetime.now(timezone.utc).isoformat(), protected_pids=protected,
            memory_percent=psutil.virtual_memory().percent,
            free_disk_bytes=psutil.disk_usage(str(args.output)).free,
            configuration_unchanged=hashlib.sha256(args.config_file.read_bytes()).hexdigest() == config_hash,
            evidence=result)
        records.append(row)
        with (args.output / "samples.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            import os
            os.fsync(handle.fileno())
        good = result["decision"] == "PASS" and all(protected.values()) and row["configuration_unchanged"]
        final = elapsed >= args.duration_sec or not good
        doc = dict(status=("PASS" if good else "BLOCK") if final else "RUNNING",
            scope="independent_mcp_protocol_reconnects_not_agent_native_session_lifecycle",
            elapsed_sec=time.monotonic()-started, requested_duration_sec=args.duration_sec,
            samples=len(records), original_pids=identities, config_sha256=config_hash,
            all_passed=all(x["evidence"]["decision"] == "PASS" and all(x["protected_pids"].values()) and x["configuration_unchanged"] for x in records),
            max_latency_sec=max(x["latency_sec"] for x in records),
            max_schedule_lag_sec=max(x["elapsed_sec"]-x["slot"]*args.interval_sec for x in records),
            last=row)
        atomic_bytes(checkpoint, (json.dumps(doc, ensure_ascii=False, indent=2)+"\n").encode())
        print(f"CONNECTION_SOAK slot={slot} elapsed={elapsed:.1f}s status={doc['status']} protected={protected}", flush=True)
        if final:
            return 0 if good and doc["all_passed"] else 3
        slot += 1


if __name__ == "__main__":
    raise SystemExit(main())
