from __future__ import annotations

import csv
import hashlib
import json
import math
import multiprocessing
import os
import re
import socket
import statistics
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import psutil
except ImportError:  # pragma: no cover - installed harness declares psutil
    psutil = None  # type: ignore[assignment]

from .config import INFLIGHT_DIR
from .evidence import build_evidence, load_json, utc_now
from .fanout import load_fanout_contract, output_root_of, resolve_worker_path
from .mcp_client import call_tool


RESOURCE_FIELDS = [
    "sequence",
    "scheduled_utc",
    "timestamp_utc",
    "lag_sec",
    "ok",
    "missed_before_slot",
    "cpu_percent",
    "memory_percent",
    "disk_free_gb",
    "r_worker_count",
    "rstudio_pid",
    "rstudio_pid_alive",
    "port_open",
    "newest_state_mtime",
    "max_running_state_age_sec",
    "completed_workers",
    "observed_workers",
    "errors",
]

PROGRESS_FIELDS = [
    "resource_sequence",
    "timestamp_utc",
    "worker_id",
    "status",
    "stage",
    "elapsed_seconds",
    "total_reps",
    "canonical_filled",
    "percent",
    "state_mtime",
    "state_age_sec",
    "monotonic",
    "read_error",
]

HEARTBEAT_FIELDS = [
    "sequence",
    "scheduled_utc",
    "timestamp_utc",
    "lag_sec",
    "ok",
    "latency_sec",
    "reported_pid",
    "expected_pid_match",
    "consecutive_failures",
    "missed_before_slot",
    "text",
]

DEFAULT_MONITOR_POLICY: dict[str, Any] = {
    "sample_sec": 30.0,
    "heartbeat_sec": 60.0,
    "heartbeat_timeout_sec": 30.0,
    "min_heartbeat_success_rate": 0.99,
    "max_heartbeat_gap_sec": 120.0,
    "heartbeat_p95_max_sec": 5.0,
    "max_state_gap_sec": 120.0,
    "memory_hold_percent": 85.0,
    "memory_abort_percent": 90.0,
    "memory_abort_samples": 3,
    "min_disk_free_gb": 75.0,
    "transport_stall_sec": 600.0,
    "max_supervised_restarts": 3,
    "restart_backoff_sec": 2.0,
    "critical_metric_failure_samples": 3,
}

DONE_STATES = {"complete", "completed", "done", "success", "pass"}
PSUTIL_ERRORS: tuple[type[BaseException], ...] = (
    ((psutil.Error,) if psutil is not None else ())
    + (PermissionError, OSError, SystemError)
)


def _epoch_to_utc(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _append_csv(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if needs_header:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_r_worker_count(
    process_iter: Callable[[], Any] | None = None,
) -> tuple[int | None, list[str]]:
    """Count likely R workers without allowing an optional metric to crash monitoring."""

    if process_iter is None and psutil is None:
        return None, ["process enumeration: psutil is unavailable"]
    iterator_factory = process_iter or psutil.process_iter
    count = 0
    errors: list[str] = []
    try:
        iterator = iterator_factory()
        for proc in iterator:
            try:
                name = str(proc.name() or "").lower()
                cmdline = proc.cmdline() or []
                command = " ".join(str(part) for part in cmdline).lower()
                if name in {"r", "rscript"} or "callr" in command or "claude_bg_worker" in command:
                    count += 1
            except PSUTIL_ERRORS as exc:
                errors.append(f"pid={getattr(proc, 'pid', '?')}: {type(exc).__name__}: {exc}")
                continue
    except PSUTIL_ERRORS as exc:
        return None, [f"process enumeration: {type(exc).__name__}: {exc}"]
    return count, errors


def port_open(port: int, connector: Callable[..., Any] | None = None) -> bool:
    connect = connector or socket.create_connection
    try:
        with connect(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def _safe_metric(name: str, func: Callable[[], Any]) -> tuple[Any | None, str | None]:
    try:
        return func(), None
    except PSUTIL_ERRORS + (ValueError,) as exc:
        return None, f"{name}: {type(exc).__name__}: {exc}"


def _policy(contract: dict[str, Any]) -> dict[str, Any]:
    policy = dict(DEFAULT_MONITOR_POLICY)
    configured = contract.get("monitor") or {}
    if isinstance(configured, dict):
        for key in policy:
            if configured.get(key) is not None:
                policy[key] = configured[key]
    for key in (
        "sample_sec",
        "heartbeat_sec",
        "heartbeat_timeout_sec",
        "min_heartbeat_success_rate",
        "max_heartbeat_gap_sec",
        "heartbeat_p95_max_sec",
        "max_state_gap_sec",
        "memory_hold_percent",
        "memory_abort_percent",
        "min_disk_free_gb",
        "transport_stall_sec",
        "restart_backoff_sec",
    ):
        policy[key] = float(policy[key])
    for key in ("memory_abort_samples", "max_supervised_restarts", "critical_metric_failure_samples"):
        policy[key] = int(policy[key])
    if policy["sample_sec"] <= 0 or policy["heartbeat_sec"] <= 0:
        raise ValueError("monitor sample_sec and heartbeat_sec must be positive")
    if not 0 < policy["min_heartbeat_success_rate"] <= 1:
        raise ValueError("monitor min_heartbeat_success_rate must be in (0, 1]")
    return policy


def _output_root(contract: dict[str, Any]) -> Path:
    raw = output_root_of(contract)
    if not raw:
        raise ValueError("fan-out contract artifacts.output_root is required for soak-monitor")
    root = Path(str(raw)).expanduser()
    if not root.is_absolute():
        root = Path(str(contract.get("_contract_path") or ".")).parent / root
    return root.resolve()


def _initial_checkpoint(config: dict[str, Any], now: float) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "logical_run_id": str(uuid.uuid4()),
        "task_key": config["task_key"],
        "started_at_epoch": now,
        "started_at_utc": _epoch_to_utc(now),
        "updated_at_utc": _epoch_to_utc(now),
        "next_resource_epoch": now,
        "next_heartbeat_epoch": now,
        "resource_planned": 0,
        "resource_observed": 0,
        "resource_missed_slots": 0,
        "heartbeat_planned": 0,
        "heartbeat_observed": 0,
        "heartbeat_success": 0,
        "heartbeat_missed_slots": 0,
        "heartbeat_failures": 0,
        "max_consecutive_heartbeat_failures": 0,
        "heartbeat_failure_started_epoch": None,
        "newest_state_at_heartbeat_failure": None,
        "memory_abort_streak": 0,
        "critical_metric_failure_streak": 0,
        "supervised_restarts": 0,
        "last_progress": {},
        "violations": [],
        "aborted": False,
        "abort_reason": None,
        "admission_open": True,
    }


def _load_checkpoint(config: dict[str, Any], *, resume: bool) -> dict[str, Any]:
    path = Path(config["checkpoint_path"])
    if path.exists():
        if not resume:
            raise FileExistsError(f"monitor checkpoint already exists; pass --resume to continue: {path}")
        checkpoint = load_json(path)
        if checkpoint.get("task_key") != config["task_key"]:
            raise ValueError("monitor checkpoint task_key does not match contract")
        return checkpoint
    if resume:
        raise FileNotFoundError(f"--resume requested but checkpoint is missing: {path}")
    checkpoint = _initial_checkpoint(config, time.time())
    _atomic_json(path, checkpoint)
    return checkpoint


def _read_states(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for worker in contract.get("workers") or []:
        if not isinstance(worker, dict):
            continue
        worker_id = str(worker.get("id") or "")
        path = resolve_worker_path(contract, worker, "expected_state")
        if path is None or not path.exists():
            continue
        try:
            mtime = path.stat().st_mtime
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
            rows.append({"worker_id": worker_id, "path": path, "mtime": mtime, "doc": doc, "read_error": None})
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            rows.append({
                "worker_id": worker_id,
                "path": path,
                "mtime": mtime,
                "doc": {},
                "read_error": f"{type(exc).__name__}: {exc}",
            })
    return rows


def _known_jobs(task_key: str) -> list[str]:
    found: set[str] = set()
    for path in INFLIGHT_DIR.glob("*.json"):
        try:
            doc = load_json(path)
        except Exception:
            continue
        registered_key = str(doc.get("task_key") or "")
        belongs = doc.get("fanout_task_key") == task_key or registered_key.startswith(task_key + ":")
        if belongs and doc.get("job_id"):
            found.add(str(doc["job_id"]))
    return sorted(found)


def _cancel_jobs(config: dict[str, Any], reason: str) -> None:
    rows: list[dict[str, Any]] = []
    for job_id in _known_jobs(config["task_key"]):
        started = time.monotonic()
        try:
            result = call_tool("cancel_async_job", {"job_id": job_id}, timeout=30, retries=0)
        except Exception as exc:
            result = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        rows.append({"job_id": job_id, "latency_sec": time.monotonic() - started, "result": result})
    _atomic_json(
        Path(config["evidence_dir"]) / "safety_cancellations.json",
        {"task_key": config["task_key"], "timestamp_utc": utc_now(), "reason": reason, "cancellations": rows},
    )


def _record_event(config: dict[str, Any], event: str, **extra: Any) -> None:
    _append_jsonl(
        Path(config["evidence_dir"]) / "monitor_events.jsonl",
        {"timestamp_utc": utc_now(), "event": event, **extra},
    )


def _mark_abort(config: dict[str, Any], checkpoint: dict[str, Any], reason: str) -> None:
    checkpoint["aborted"] = True
    checkpoint["abort_reason"] = reason
    checkpoint["updated_at_utc"] = utc_now()
    _atomic_json(Path(config["evidence_dir"]) / "abort_requested.json", {
        "status": "BLOCKED",
        "task_key": config["task_key"],
        "reason": reason,
        "timestamp_utc": checkpoint["updated_at_utc"],
    })
    _atomic_json(Path(config["checkpoint_path"]), checkpoint)
    _record_event(config, "abort_requested", reason=reason)
    _cancel_jobs(config, reason)


def _next_slot(checkpoint: dict[str, Any], prefix: str, interval: float, now: float) -> tuple[float, int]:
    key = f"next_{prefix}_epoch"
    scheduled = float(checkpoint[key])
    overdue = max(0, math.floor((now - scheduled) / interval)) if now >= scheduled else 0
    current = scheduled + overdue * interval
    checkpoint[f"{prefix}_planned"] = int(checkpoint.get(f"{prefix}_planned", 0)) + overdue + 1
    checkpoint[f"{prefix}_missed_slots"] = int(checkpoint.get(f"{prefix}_missed_slots", 0)) + overdue
    checkpoint[key] = current + interval
    return current, overdue


def _sample_resource(config: dict[str, Any], contract: dict[str, Any], checkpoint: dict[str, Any], scheduled: float, missed: int) -> None:
    if psutil is None:
        raise RuntimeError("psutil is required for soak-monitor resource sampling")
    now = time.time()
    errors: list[str] = []
    cpu, err = _safe_metric("cpu_percent", lambda: float(psutil.cpu_percent(interval=None)))
    if err:
        errors.append(err)
    memory, err = _safe_metric("memory_percent", lambda: float(psutil.virtual_memory().percent))
    if err:
        errors.append(err)
    disk, err = _safe_metric("disk_free_gb", lambda: float(psutil.disk_usage(config["output_root"]).free) / 1_000_000_000)
    if err:
        errors.append(err)
    pid_alive, err = _safe_metric("rstudio_pid_alive", lambda: bool(psutil.pid_exists(int(config["expected_pid"]))))
    if err:
        errors.append(err)
    port_ok, err = _safe_metric("port_open", lambda: port_open(int(config["port"])))
    if err:
        errors.append(err)
    r_count, worker_errors = safe_r_worker_count()
    if worker_errors:
        _record_event(
            config,
            "noncritical_metric_error",
            metric="r_worker_count",
            error_count=len(worker_errors),
            examples=worker_errors[:5],
        )

    states, states_error = _safe_metric("state_files", lambda: _read_states(contract))
    if states_error:
        errors.append(states_error)
        states = []
    states = states or []
    newest = max((float(row["mtime"]) for row in states), default=0.0)
    running_ages: list[float] = []
    completed = 0
    last_progress = checkpoint.setdefault("last_progress", {})
    violations = checkpoint.setdefault("violations", [])
    sequence = int(checkpoint.get("resource_observed", 0)) + 1
    stamp = _epoch_to_utc(now)

    for row in states:
        doc = row["doc"]
        worker_id = str(row["worker_id"] or row["path"].stem.removeprefix("state_"))
        status = str(doc.get("status") or "").lower()
        if status in DONE_STATES:
            completed += 1
        age = max(0.0, now - float(row["mtime"])) if row["mtime"] else 0.0
        if status == "running":
            running_ages.append(age)
        reps = float(doc.get("total_reps") or 0)
        elapsed = float(doc.get("elapsed_seconds") or 0)
        previous = last_progress.get(worker_id)
        monotonic_ok = previous is None or (reps >= float(previous[0]) and elapsed >= float(previous[1]))
        if not monotonic_ok:
            violations.append({
                "timestamp_utc": stamp,
                "worker_id": worker_id,
                "type": "non_monotonic_progress",
                "previous": previous,
                "current": [reps, elapsed],
            })
        last_progress[worker_id] = [reps, elapsed]
        if status == "running" and age > float(config["policy"]["max_state_gap_sec"]):
            violations.append({
                "timestamp_utc": stamp,
                "worker_id": worker_id,
                "type": "state_update_gap",
                "age_sec": age,
            })
        _append_csv(Path(config["evidence_dir"]) / "state_progress.csv", PROGRESS_FIELDS, {
            "resource_sequence": sequence,
            "timestamp_utc": stamp,
            "worker_id": worker_id,
            "status": doc.get("status", ""),
            "stage": doc.get("stage", ""),
            "elapsed_seconds": elapsed,
            "total_reps": reps,
            "canonical_filled": doc.get("canonical_filled", ""),
            "percent": doc.get("percent", ""),
            "state_mtime": f"{float(row['mtime']):.6f}" if row["mtime"] else "",
            "state_age_sec": f"{age:.3f}",
            "monotonic": monotonic_ok,
            "read_error": row.get("read_error") or "",
        })

    critical_unknown = any(value is None for value in (memory, disk, pid_alive, port_ok))
    checkpoint["critical_metric_failure_streak"] = (
        int(checkpoint.get("critical_metric_failure_streak", 0)) + 1 if critical_unknown else 0
    )
    if memory is not None and float(memory) >= float(config["policy"]["memory_abort_percent"]):
        checkpoint["memory_abort_streak"] = int(checkpoint.get("memory_abort_streak", 0)) + 1
    else:
        checkpoint["memory_abort_streak"] = 0

    admission_open = memory is not None and float(memory) < float(config["policy"]["memory_hold_percent"])
    checkpoint["admission_open"] = admission_open
    _atomic_json(Path(config["evidence_dir"]) / "admission_status.json", {
        "task_key": config["task_key"],
        "timestamp_utc": stamp,
        "allow_new_jobs": admission_open,
        "memory_percent": memory,
        "memory_hold_percent": config["policy"]["memory_hold_percent"],
    })

    resource_ok = not critical_unknown and bool(pid_alive) and bool(port_ok)
    _append_csv(Path(config["evidence_dir"]) / "resource_samples.csv", RESOURCE_FIELDS, {
        "sequence": sequence,
        "scheduled_utc": _epoch_to_utc(scheduled),
        "timestamp_utc": stamp,
        "lag_sec": f"{max(0.0, now - scheduled):.6f}",
        "ok": resource_ok,
        "missed_before_slot": missed,
        "cpu_percent": "" if cpu is None else f"{float(cpu):.3f}",
        "memory_percent": "" if memory is None else f"{float(memory):.3f}",
        "disk_free_gb": "" if disk is None else f"{float(disk):.6f}",
        "r_worker_count": "" if r_count is None else r_count,
        "rstudio_pid": config["expected_pid"],
        "rstudio_pid_alive": "" if pid_alive is None else pid_alive,
        "port_open": "" if port_ok is None else port_ok,
        "newest_state_mtime": f"{newest:.6f}" if newest else "",
        "max_running_state_age_sec": f"{max(running_ages):.3f}" if running_ages else "",
        "completed_workers": completed,
        "observed_workers": len(states),
        "errors": " | ".join(errors),
    })
    checkpoint["resource_observed"] = sequence
    checkpoint["latest_state_mtime"] = newest or checkpoint.get("latest_state_mtime")
    checkpoint["updated_at_utc"] = stamp

    abort_reason: str | None = None
    if disk is not None and float(disk) < float(config["policy"]["min_disk_free_gb"]):
        abort_reason = f"disk free {float(disk):.3f}GB below {config['policy']['min_disk_free_gb']}GB"
    elif int(checkpoint["memory_abort_streak"]) >= int(config["policy"]["memory_abort_samples"]):
        abort_reason = f"memory >= {config['policy']['memory_abort_percent']}% for {checkpoint['memory_abort_streak']} samples"
    elif pid_alive is False or port_ok is False:
        abort_reason = f"RStudio liveness failed: pid_alive={pid_alive}, port_open={port_ok}"
    elif int(checkpoint["critical_metric_failure_streak"]) >= int(config["policy"]["critical_metric_failure_samples"]):
        abort_reason = f"critical resource metrics unavailable for {checkpoint['critical_metric_failure_streak']} samples"
    elif int(checkpoint.get("heartbeat_failures", 0)) >= 3 and checkpoint.get("heartbeat_failure_started_epoch"):
        failure_age = now - float(checkpoint["heartbeat_failure_started_epoch"])
        if failure_age > float(config["policy"]["transport_stall_sec"]):
            at_failure = float(checkpoint.get("newest_state_at_heartbeat_failure") or 0.0)
            if newest <= at_failure:
                abort_reason = "MCP heartbeat failed beyond transport_stall_sec and durable state stopped advancing"
    if abort_reason:
        _mark_abort(config, checkpoint, abort_reason)
    elif missed:
        _record_event(config, "resource_slots_missed", count=missed, scheduled_utc=_epoch_to_utc(scheduled))


def _sample_heartbeat(config: dict[str, Any], checkpoint: dict[str, Any], scheduled: float, missed: int) -> None:
    now = time.time()
    stamp = _epoch_to_utc(now)
    code = "cat('STRESS_HEARTBEAT pid=', Sys.getpid(), ' time=', format(Sys.time(), tz='UTC', usetz=TRUE), '\\n', sep='')"
    started = time.monotonic()
    try:
        result = call_tool(
            "execute_r",
            {"code": code},
            timeout=float(config["policy"]["heartbeat_timeout_sec"]),
            retries=0,
        )
    except Exception as exc:
        result = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    latency = time.monotonic() - started
    text = str(result.get("text") or result.get("reason") or "")
    match = re.search(r"STRESS_HEARTBEAT pid=(\d+)", text)
    reported_pid = int(match.group(1)) if match else None
    ok = bool(result.get("ok")) and reported_pid == int(config["expected_pid"])
    failures = 0 if ok else int(checkpoint.get("heartbeat_failures", 0)) + 1
    checkpoint["heartbeat_failures"] = failures
    checkpoint["max_consecutive_heartbeat_failures"] = max(
        int(checkpoint.get("max_consecutive_heartbeat_failures", 0)), failures
    )
    if ok:
        checkpoint["heartbeat_success"] = int(checkpoint.get("heartbeat_success", 0)) + 1
        checkpoint["heartbeat_failure_started_epoch"] = None
        checkpoint["newest_state_at_heartbeat_failure"] = None
    elif checkpoint.get("heartbeat_failure_started_epoch") is None:
        checkpoint["heartbeat_failure_started_epoch"] = now
        checkpoint["newest_state_at_heartbeat_failure"] = checkpoint.get("latest_state_mtime") or 0.0
    sequence = int(checkpoint.get("heartbeat_observed", 0)) + 1
    _append_csv(Path(config["evidence_dir"]) / "heartbeat.csv", HEARTBEAT_FIELDS, {
        "sequence": sequence,
        "scheduled_utc": _epoch_to_utc(scheduled),
        "timestamp_utc": stamp,
        "lag_sec": f"{max(0.0, now - scheduled):.6f}",
        "ok": ok,
        "latency_sec": f"{latency:.6f}",
        "reported_pid": reported_pid or "",
        "expected_pid_match": reported_pid == int(config["expected_pid"]),
        "consecutive_failures": failures,
        "missed_before_slot": missed,
        "text": text.replace("\n", "\\n")[:2000],
    })
    _append_jsonl(Path(config["evidence_dir"]) / "heartbeat_raw.jsonl", {
        "sequence": sequence,
        "scheduled_utc": _epoch_to_utc(scheduled),
        "timestamp_utc": stamp,
        "latency_sec": latency,
        "reported_pid": reported_pid,
        "ok": ok,
        "result": result,
    })
    checkpoint["heartbeat_observed"] = sequence
    checkpoint["last_heartbeat_observed_epoch"] = now
    checkpoint["updated_at_utc"] = stamp
    if missed:
        _record_event(config, "heartbeat_slots_missed", count=missed, scheduled_utc=_epoch_to_utc(scheduled))


def _sampling_worker(config: dict[str, Any]) -> int:
    if psutil is None:
        _record_event(config, "sampling_worker_crash", error="psutil is unavailable")
        return 70
    contract = load_fanout_contract(config["contract"])
    checkpoint = _reconcile_checkpoint(config, load_json(config["checkpoint_path"]))
    psutil.cpu_percent(interval=None)
    try:
        while not Path(config["stop_file"]).exists() and not checkpoint.get("aborted"):
            now = time.time()
            if now >= float(checkpoint["next_resource_epoch"]):
                scheduled, missed = _next_slot(checkpoint, "resource", float(config["policy"]["sample_sec"]), now)
                _sample_resource(config, contract, checkpoint, scheduled, missed)
                _atomic_json(Path(config["checkpoint_path"]), checkpoint)
            now = time.time()
            if not checkpoint.get("aborted") and now >= float(checkpoint["next_heartbeat_epoch"]):
                scheduled, missed = _next_slot(checkpoint, "heartbeat", float(config["policy"]["heartbeat_sec"]), now)
                _sample_heartbeat(config, checkpoint, scheduled, missed)
                _atomic_json(Path(config["checkpoint_path"]), checkpoint)
            wait_for = min(float(checkpoint["next_resource_epoch"]), float(checkpoint["next_heartbeat_epoch"])) - time.time()
            time.sleep(max(0.1, min(wait_for, 1.0)))
        return 3 if checkpoint.get("aborted") else 0
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        _record_event(
            config,
            "sampling_worker_crash",
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
        return 70


def _sampling_process_entry(config: dict[str, Any]) -> None:
    raise SystemExit(_sampling_worker(config))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _truthy_csv(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "pass", "ok"}


def _reconcile_checkpoint(config: dict[str, Any], checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Recover committed CSV observations if a worker died before checkpointing them."""

    evidence_dir = Path(config["evidence_dir"])
    resource_rows = _read_csv(evidence_dir / "resource_samples.csv")
    heartbeat_rows = _read_csv(evidence_dir / "heartbeat.csv")
    if resource_rows:
        observed = max(int(row.get("sequence") or 0) for row in resource_rows)
        missed = sum(int(row.get("missed_before_slot") or 0) for row in resource_rows)
        checkpoint["resource_observed"] = max(int(checkpoint.get("resource_observed", 0)), observed)
        checkpoint["resource_missed_slots"] = max(int(checkpoint.get("resource_missed_slots", 0)), missed)
        checkpoint["resource_planned"] = max(int(checkpoint.get("resource_planned", 0)), observed + missed)
        scheduled = [_parse_utc(row.get("scheduled_utc", "")) for row in resource_rows]
        last_scheduled = max((value for value in scheduled if value is not None), default=None)
        if last_scheduled is not None:
            checkpoint["next_resource_epoch"] = max(
                float(checkpoint.get("next_resource_epoch", 0.0)),
                last_scheduled + float(config["policy"]["sample_sec"]),
            )
    if heartbeat_rows:
        observed = max(int(row.get("sequence") or 0) for row in heartbeat_rows)
        missed = sum(int(row.get("missed_before_slot") or 0) for row in heartbeat_rows)
        successful = sum(_truthy_csv(row.get("ok")) for row in heartbeat_rows)
        checkpoint["heartbeat_observed"] = max(int(checkpoint.get("heartbeat_observed", 0)), observed)
        checkpoint["heartbeat_missed_slots"] = max(int(checkpoint.get("heartbeat_missed_slots", 0)), missed)
        checkpoint["heartbeat_planned"] = max(int(checkpoint.get("heartbeat_planned", 0)), observed + missed)
        checkpoint["heartbeat_success"] = max(int(checkpoint.get("heartbeat_success", 0)), successful)
        scheduled = [_parse_utc(row.get("scheduled_utc", "")) for row in heartbeat_rows]
        last_scheduled = max((value for value in scheduled if value is not None), default=None)
        if last_scheduled is not None:
            checkpoint["next_heartbeat_epoch"] = max(
                float(checkpoint.get("next_heartbeat_epoch", 0.0)),
                last_scheduled + float(config["policy"]["heartbeat_sec"]),
            )
    checkpoint["updated_at_utc"] = utc_now()
    _atomic_json(Path(config["checkpoint_path"]), checkpoint)
    return checkpoint


def _percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _finalize(config: dict[str, Any]) -> dict[str, Any]:
    evidence_dir = Path(config["evidence_dir"])
    checkpoint = load_json(config["checkpoint_path"])
    heartbeat_rows = _read_csv(evidence_dir / "heartbeat.csv")
    resource_rows = _read_csv(evidence_dir / "resource_samples.csv")
    heartbeat_times = [
        value for value in (_parse_utc(row.get("timestamp_utc", "")) for row in heartbeat_rows) if value is not None
    ]
    heartbeat_gaps = [b - a for a, b in zip(heartbeat_times, heartbeat_times[1:])]
    latencies = [float(row["latency_sec"]) for row in heartbeat_rows if row.get("latency_sec")]
    planned = int(checkpoint.get("heartbeat_planned", 0))
    successful = int(checkpoint.get("heartbeat_success", 0))
    success_rate = successful / planned if planned else 0.0
    max_gap = max(heartbeat_gaps, default=0.0)
    p95 = _percentile95(latencies)
    violations = list(checkpoint.get("violations") or [])
    checks = {
        "not_aborted": not bool(checkpoint.get("aborted")),
        "heartbeat_success_ge_minimum": success_rate >= float(config["policy"]["min_heartbeat_success_rate"]),
        "heartbeat_max_gap_within_limit": max_gap <= float(config["policy"]["max_heartbeat_gap_sec"]),
        "heartbeat_p95_within_limit": p95 is not None and p95 < float(config["policy"]["heartbeat_p95_max_sec"]),
        "no_three_consecutive_heartbeat_failures": int(checkpoint.get("max_consecutive_heartbeat_failures", 0)) < 3,
        "no_progress_violations": not violations,
        "supervised_restarts_within_budget": int(checkpoint.get("supervised_restarts", 0)) <= int(config["policy"]["max_supervised_restarts"]),
    }
    decision = "PASS" if all(checks.values()) else "BLOCK"
    summary = {
        "schema_version": "1.0",
        "task_key": config["task_key"],
        "logical_run_id": checkpoint["logical_run_id"],
        "started_at_utc": checkpoint["started_at_utc"],
        "completed_at_utc": utc_now(),
        "duration_seconds": max(0.0, time.time() - float(checkpoint["started_at_epoch"])),
        "decision": decision,
        "checks": checks,
        "policy": config["policy"],
        "resource_planned": int(checkpoint.get("resource_planned", 0)),
        "resource_observed": int(checkpoint.get("resource_observed", 0)),
        "resource_missed_slots": int(checkpoint.get("resource_missed_slots", 0)),
        "heartbeat_planned": planned,
        "heartbeat_observed": int(checkpoint.get("heartbeat_observed", 0)),
        "heartbeat_success": successful,
        "heartbeat_missed_slots": int(checkpoint.get("heartbeat_missed_slots", 0)),
        "heartbeat_success_rate": success_rate,
        "heartbeat_max_gap_sec": max_gap,
        "heartbeat_p95_latency_sec": p95,
        "max_consecutive_heartbeat_failures": int(checkpoint.get("max_consecutive_heartbeat_failures", 0)),
        "supervised_restarts": int(checkpoint.get("supervised_restarts", 0)),
        "aborted": bool(checkpoint.get("aborted")),
        "abort_reason": checkpoint.get("abort_reason"),
        "stop_file_seen": Path(config["stop_file"]).exists(),
        "resource_rows": len(resource_rows),
        "heartbeat_rows": len(heartbeat_rows),
        "max_memory_percent": max((float(row["memory_percent"]) for row in resource_rows if row.get("memory_percent")), default=None),
        "min_disk_free_gb": min((float(row["disk_free_gb"]) for row in resource_rows if row.get("disk_free_gb")), default=None),
        "violations": violations,
    }
    _atomic_json(evidence_dir / "monitor_summary.json", summary)
    _atomic_json(evidence_dir / "monitor_violations.json", {"task_key": config["task_key"], "violations": violations})
    artifact_paths = [
        evidence_dir / name
        for name in (
            "resource_samples.csv",
            "state_progress.csv",
            "heartbeat.csv",
            "heartbeat_raw.jsonl",
            "monitor_events.jsonl",
            "monitor_checkpoint.json",
            "monitor_summary.json",
            "monitor_violations.json",
            "admission_status.json",
        )
        if (evidence_dir / name).exists()
    ]
    artifact_hashes = [
        {"path": str(path), "sha256": _sha256(path), "size_bytes": path.stat().st_size}
        for path in artifact_paths
    ]
    return build_evidence(
        "soak_monitor",
        decision,
        reasons=[
            f"heartbeat schedule success {successful}/{planned} = {success_rate:.6%}",
            f"max heartbeat gap {max_gap:.6f}s; p95 latency {p95 if p95 is not None else 'NA'}s",
            f"supervised restarts={checkpoint.get('supervised_restarts', 0)}; violations={len(violations)}",
        ],
        task_key=config["task_key"],
        transport_class="MCP_STDIO_OK",
        pid=config["expected_pid"],
        artifact_paths=[str(path) for path in artifact_paths],
        policy_violations=[name for name, ok in checks.items() if not ok],
        exit_code=0 if decision == "PASS" else 3,
        extra={
            "monitored_transport": config["monitored_transport"],
            "contract": config["contract"],
            "output_root": config["output_root"],
            "summary": summary,
            "artifact_hashes": artifact_hashes,
        },
    )


def build_monitor_config(
    *,
    contract_path: str,
    evidence_dir: str,
    expected_pid: int,
    port: int,
    stop_file: str,
    monitored_transport: str = "NATIVE_MCP_OK",
) -> dict[str, Any]:
    contract = load_fanout_contract(contract_path)
    task_key = str(contract.get("task_key") or "")
    if not task_key:
        raise ValueError("fan-out contract task_key is required for soak-monitor")
    output_root = _output_root(contract)
    evidence = Path(evidence_dir).expanduser().resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    return {
        "contract": str(Path(contract_path).expanduser().resolve()),
        "task_key": task_key,
        "output_root": str(output_root),
        "evidence_dir": str(evidence),
        "checkpoint_path": str(evidence / "monitor_checkpoint.json"),
        "expected_pid": int(expected_pid),
        "port": int(port),
        "stop_file": str(Path(stop_file).expanduser().resolve()),
        "monitored_transport": monitored_transport,
        "policy": _policy(contract),
    }


def run_soak_monitor(config: dict[str, Any], *, resume: bool = False) -> dict[str, Any]:
    checkpoint = _load_checkpoint(config, resume=resume)
    _record_event(
        config,
        "monitor_started" if not resume else "monitor_resumed",
        logical_run_id=checkpoint["logical_run_id"],
        task_key=config["task_key"],
    )
    ctx = multiprocessing.get_context("spawn")
    while True:
        process = ctx.Process(target=_sampling_process_entry, args=(config,), daemon=False)
        process.start()
        process.join()
        exit_code = int(process.exitcode or 0)
        checkpoint = load_json(config["checkpoint_path"])
        if exit_code in {0, 3} or checkpoint.get("aborted") or Path(config["stop_file"]).exists():
            break
        restarts = int(checkpoint.get("supervised_restarts", 0)) + 1
        checkpoint["supervised_restarts"] = restarts
        checkpoint["updated_at_utc"] = utc_now()
        _atomic_json(Path(config["checkpoint_path"]), checkpoint)
        _record_event(config, "supervisor_restart", exit_code=exit_code, restart_number=restarts)
        if restarts > int(config["policy"]["max_supervised_restarts"]):
            _mark_abort(config, checkpoint, f"sampling worker exceeded restart budget after exit code {exit_code}")
            break
        time.sleep(float(config["policy"]["restart_backoff_sec"]))
    return _finalize(config)


def monitor_status(config: dict[str, Any]) -> dict[str, Any]:
    checkpoint = Path(config["checkpoint_path"])
    if not checkpoint.exists():
        return {"task_key": config["task_key"], "status": "not_started", "checkpoint": str(checkpoint)}
    doc = load_json(checkpoint)
    return {
        "task_key": config["task_key"],
        "status": "blocked" if doc.get("aborted") else "running",
        "checkpoint": str(checkpoint),
        "logical_run_id": doc.get("logical_run_id"),
        "updated_at_utc": doc.get("updated_at_utc"),
        "admission_open": doc.get("admission_open"),
        "resource_observed": doc.get("resource_observed"),
        "heartbeat_observed": doc.get("heartbeat_observed"),
        "heartbeat_success": doc.get("heartbeat_success"),
        "heartbeat_missed_slots": doc.get("heartbeat_missed_slots"),
        "supervised_restarts": doc.get("supervised_restarts"),
        "abort_reason": doc.get("abort_reason"),
    }
