"""Drain output pipes for legacy ClaudeR async jobs without changing jobs.

ClaudeR releases before file-backed async output could block a child process
when its processx stdout/stderr pipes filled. This monitor keeps one MCP stdio
connection open and drains only job IDs already recorded by fanout-run.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import BLOCK, PASS, WARN
from .evidence import build_evidence, load_json
from .mcp_client import _server_env, _server_spec, _tool_result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def build_rescue_config(
    *,
    runtime_status: str,
    session_name: str,
    evidence_dir: str,
    interval_sec: float = 1.0,
    reconnect_sec: float = 2.0,
    call_timeout_sec: float = 20.0,
    max_connection_failures: int = 0,
) -> dict[str, Any]:
    root = Path(evidence_dir).expanduser().resolve()
    runtime = Path(runtime_status).expanduser().resolve()
    if interval_sec <= 0 or reconnect_sec <= 0 or call_timeout_sec <= 0:
        raise ValueError("interval, reconnect, and call timeout must be positive")
    if max_connection_failures < 0:
        raise ValueError("max_connection_failures cannot be negative")
    return {
        "runtime_status": str(runtime),
        "session_name": session_name,
        "evidence_dir": str(root),
        "log_dir": str(root / "async_io"),
        "events": str(root / "async_io_rescue_events.jsonl"),
        "checkpoint": str(root / "async_io_rescue_checkpoint.json"),
        "interval_sec": float(interval_sec),
        "reconnect_sec": float(reconnect_sec),
        "call_timeout_sec": float(call_timeout_sec),
        "max_connection_failures": int(max_connection_failures),
    }


def _runtime_snapshot(path: str | Path) -> dict[str, Any]:
    runtime = load_json(path)
    running = runtime.get("running") or []
    job_ids = [str(item["job_id"]) for item in running if isinstance(item, dict) and item.get("job_id")]
    return {
        "task_key": runtime.get("task_key"),
        "iteration": runtime.get("iteration"),
        "job_ids": job_ids,
        "pending": list(runtime.get("pending") or []),
        "done": list(runtime.get("done") or []),
        "failed": list(runtime.get("failed") or []),
    }


def _r_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_drain_code(job_ids: list[str], log_dir: str | Path) -> str:
    """Build read-only R code for existing async job process handles."""

    ids = json.dumps(job_ids, ensure_ascii=False, separators=(",", ":"))
    return f"""
job_ids <- jsonlite::fromJSON({_r_string(ids)})
log_dir <- {_r_string(str(Path(log_dir).expanduser().resolve()))}
drain <- get0('drain_background_job_io', envir = asNamespace('ClaudeR'), inherits = FALSE)
if (is.function(drain)) {{
  result <- lapply(job_ids, function(job_id) drain(job_id, log_dir))
}} else {{
  jobs_env <- get('.claude_bg_jobs', envir = asNamespace('ClaudeR'))
  append_raw <- function(path, bytes) {{
    if (!is.raw(bytes) || !length(bytes)) return(0L)
    con <- file(path, open = 'ab')
    on.exit(close(con), add = TRUE)
    writeBin(bytes, con)
    flush(con)
    as.integer(length(bytes))
  }}
  result <- lapply(job_ids, function(job_id) {{
    if (!exists(job_id, envir = jobs_env, inherits = FALSE))
      return(list(job_id = job_id, found = FALSE, alive = FALSE, stdout_bytes = 0L, stderr_bytes = 0L))
    info <- get(job_id, envir = jobs_env, inherits = FALSE)
    if (is.null(info$process))
      return(list(job_id = job_id, found = TRUE, alive = FALSE, stdout_bytes = 0L, stderr_bytes = 0L))
    read_bytes <- function(stream) tryCatch(
      if (identical(stream, 'stdout')) info$process$read_output_bytes(-1L) else info$process$read_error_bytes(-1L),
      error = function(error) structure(raw(0), read_error = conditionMessage(error))
    )
    out <- read_bytes('stdout')
    err <- read_bytes('stderr')
    list(
      job_id = job_id,
      found = TRUE,
      alive = tryCatch(isTRUE(info$process$is_alive()), error = function(error) FALSE),
      stdout_bytes = append_raw(file.path(log_dir, paste0(job_id, '.stdout.bin')), out),
      stderr_bytes = append_raw(file.path(log_dir, paste0(job_id, '.stderr.bin')), err),
      error = paste(na.omit(c(attr(out, 'read_error', exact = TRUE), attr(err, 'read_error', exact = TRUE))), collapse = ' | ')
    )
  }})
}}
cat(jsonlite::toJSON(result, auto_unbox = TRUE, null = 'null'))
"""


def rescue_status(config: dict[str, Any]) -> dict[str, Any]:
    checkpoint = Path(config["checkpoint"])
    if not checkpoint.exists():
        return {"status": "not_started", "checkpoint": str(checkpoint)}
    try:
        status = load_json(checkpoint)
    except Exception as exc:
        return {"status": "unreadable", "checkpoint": str(checkpoint), "error": f"{type(exc).__name__}: {exc}"}
    status["status"] = "active" if status.get("job_ids") or status.get("pending") else "complete"
    status["checkpoint"] = str(checkpoint)
    return status


def _checkpoint(config: dict[str, Any], snapshot: dict[str, Any], **extra: Any) -> None:
    _atomic_json(
        Path(config["checkpoint"]),
        {
            "schema_version": "1.0",
            "updated_at_utc": _utc_now(),
            "session_name": config["session_name"],
            **snapshot,
            **extra,
            "submissions_performed": 0,
            "cancellations_performed": 0,
        },
    )


async def _run_connection(config: dict[str, Any], *, once: bool) -> bool:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command, arguments, environment = _server_spec()
    parameters = StdioServerParameters(command=command, args=arguments, env=_server_env(environment))
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            connected = _tool_result(
                await session.call_tool("connect_session", {"session_name": config["session_name"]}),
                tool_name="connect_session",
            )
            if not connected["ok"]:
                raise RuntimeError(f"connect_session failed: {connected['text']}")

            while True:
                snapshot = _runtime_snapshot(config["runtime_status"])
                event: dict[str, Any] = {"timestamp_utc": _utc_now(), **snapshot}
                if snapshot["job_ids"]:
                    result = await asyncio.wait_for(
                        session.call_tool(
                            "execute_r",
                            {"code": build_drain_code(snapshot["job_ids"], config["log_dir"])},
                        ),
                        timeout=config["call_timeout_sec"],
                    )
                    tool_result = _tool_result(result, tool_name="execute_r")
                    event["ok"] = tool_result["ok"]
                    event["result_text"] = tool_result["text"][-12000:]
                    if not tool_result["ok"]:
                        raise RuntimeError(f"execute_r drain failed: {tool_result['text']}")
                else:
                    event.update({"ok": True, "result_text": "[]"})
                _append_jsonl(Path(config["events"]), event)
                _checkpoint(config, snapshot, last_ok=True, connection_failures=0)
                if not snapshot["job_ids"] and not snapshot["pending"]:
                    return True
                if once:
                    return False
                await asyncio.sleep(config["interval_sec"])


async def _run(config: dict[str, Any], *, once: bool) -> dict[str, Any]:
    failures = 0
    task_key: str | None = None
    while True:
        try:
            task_key = _runtime_snapshot(config["runtime_status"])["task_key"]
            complete = await _run_connection(config, once=once)
            decision = "PASS" if complete else "WARN"
            reasons = ["all recorded jobs reached terminal state"] if complete else ["snapshot drained; work remains"]
            exit_code = PASS if complete or once else WARN
            break
        except (KeyboardInterrupt, asyncio.CancelledError):
            raise
        except Exception as exc:
            failures += 1
            error = f"{type(exc).__name__}: {exc}"
            _append_jsonl(
                Path(config["events"]),
                {"timestamp_utc": _utc_now(), "ok": False, "connection_failure": failures, "error": error},
            )
            snapshot = {"task_key": task_key, "job_ids": [], "pending": [], "done": [], "failed": []}
            _checkpoint(config, snapshot, last_ok=False, connection_failures=failures, last_error=error)
            limit = int(config["max_connection_failures"])
            if once or (limit and failures >= limit):
                decision, reasons, exit_code = "BLOCK", [error], BLOCK
                break
            await asyncio.sleep(config["reconnect_sec"])

    artifacts = [config["checkpoint"], config["events"], config["log_dir"]]
    return build_evidence(
        "async_io_rescue",
        decision,
        reasons=reasons,
        task_key=task_key,
        transport_class="MCP_STDIO_OK",
        session_name=config["session_name"],
        io_mode="durable_files",
        artifact_paths=artifacts,
        exit_code=exit_code,
        extra={
            "connection_failures": failures,
            "submissions_performed": 0,
            "cancellations_performed": 0,
            "checkpoint": rescue_status(config),
        },
    )


def run_async_io_rescue(config: dict[str, Any], *, once: bool = False) -> dict[str, Any]:
    Path(config["evidence_dir"]).mkdir(parents=True, exist_ok=True)
    Path(config["log_dir"]).mkdir(parents=True, exist_ok=True)
    return asyncio.run(_run(config, once=once))
