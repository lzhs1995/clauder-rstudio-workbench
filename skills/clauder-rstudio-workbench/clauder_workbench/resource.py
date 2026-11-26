from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import asyncio
import json
import math
import secrets
import time


def memory_used_percent() -> float | None:
    try:
        import psutil

        return float(psutil.virtual_memory().percent)
    except (ImportError, AttributeError):
        pass

    if os.name != "nt":
        if sys.platform == "darwin":
            try:
                vm = subprocess.run(
                    ["vm_stat"], capture_output=True, text=True, check=True, timeout=10
                ).stdout
                total = int(subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                ).stdout.strip())
                page_match = re.search(r"page size of\s+(\d+) bytes", vm)
                if not page_match or total <= 0:
                    return None
                page_size = int(page_match.group(1))
                pages: dict[str, int] = {}
                for line in vm.splitlines():
                    match = re.match(r"Pages (free|inactive|speculative):\s+(\d+)\.", line)
                    if match:
                        pages[match.group(1)] = int(match.group(2))
                available = sum(pages.get(name, 0) for name in ("free", "inactive", "speculative")) * page_size
                return round((1 - min(available, total) / total) * 100, 2)
            except (OSError, subprocess.SubprocessError, TypeError, ValueError):
                return None
        try:
            total_pages = int(os.sysconf("SC_PHYS_PAGES"))
            available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
            if total_pages > 0:
                return round((1 - available_pages / total_pages) * 100, 2)
        except (AttributeError, OSError, TypeError, ValueError):
            return None

    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_OperatingSystem | ForEach-Object { [math]::Round((1-$_.FreePhysicalMemory/$_.TotalVisibleMemorySize)*100, 2) })",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0:
            return None
        return float(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return None


def cpu_used_percent() -> float | None:
    try:
        import psutil

        return float(psutil.cpu_percent(interval=0.1))
    except (ImportError, AttributeError, OSError, TypeError, ValueError):
        pass
    try:
        logical = os.cpu_count() or 1
        return round(min(100.0, os.getloadavg()[0] / logical * 100.0), 2)
    except (AttributeError, OSError):
        return None


def disk_free_gb(path: str | None) -> float | None:
    target = Path(path or Path.home())
    while not target.exists() and target != target.parent:
        target = target.parent
    try:
        return round(shutil.disk_usage(target).free / (1024 ** 3), 3)
    except (OSError, ValueError):
        return None


def upload_backlog_count(path: str | None) -> int:
    if not path:
        return 0
    root = Path(path)
    if not root.exists():
        return 0
    try:
        return sum(1 for item in root.iterdir() if item.is_file() and not item.name.startswith("."))
    except OSError:
        return 0


def newest_mtime(root: str | None) -> float | None:
    if not root:
        return None
    base = Path(root)
    if not base.exists():
        return None
    latest = None
    for path in base.rglob("*"):
        if path.is_file():
            mt = path.stat().st_mtime
            latest = mt if latest is None else max(latest, mt)
    return latest


def decide_resource_gate(
    *,
    current_parallel: int = 1,
    memory_threshold: float = 85.0,
    output_root: str | None = None,
    previous_newest_mtime: float | None = None,
    io_blocked: bool = False,
    rterm_responsive: bool = True,
    mcp_responsive: bool = True,
    memory_override: float | None = None,
    cpu_scale_up_percent: float | None = None,
    cpu_hold_percent: float | None = None,
    cpu_override: float | None = None,
    min_disk_free_gb_scale_up: float | None = None,
    min_disk_free_gb_hold: float | None = None,
    disk_free_gb_override: float | None = None,
    upload_backlog: int = 0,
    upload_backlog_hold: int | None = None,
) -> dict[str, Any]:
    mem = memory_override if memory_override is not None else memory_used_percent()
    cpu = cpu_override if cpu_override is not None else cpu_used_percent()
    free_gb = disk_free_gb_override if disk_free_gb_override is not None else disk_free_gb(output_root)
    latest = newest_mtime(output_root)
    durable_advancing = True
    if previous_newest_mtime is not None and latest is not None:
        durable_advancing = latest >= previous_newest_mtime

    reasons: list[str] = []
    decision = "hold"
    if mem is None:
        reasons.append("memory could not be measured")
    elif mem >= memory_threshold:
        reasons.append(f"memory {mem:.2f}% is >= threshold {memory_threshold:.2f}%")
    if cpu_hold_percent is not None and cpu is not None and cpu >= cpu_hold_percent:
        reasons.append(f"cpu {cpu:.2f}% is >= hold threshold {cpu_hold_percent:.2f}%")
    elif cpu_scale_up_percent is not None and cpu is not None and cpu >= cpu_scale_up_percent:
        reasons.append(f"cpu {cpu:.2f}% is >= scale-up threshold {cpu_scale_up_percent:.2f}%")
    if min_disk_free_gb_hold is not None and free_gb is not None and free_gb < min_disk_free_gb_hold:
        reasons.append(f"disk free {free_gb:.2f}GB is < hold threshold {min_disk_free_gb_hold:.2f}GB")
    elif min_disk_free_gb_scale_up is not None and free_gb is not None and free_gb < min_disk_free_gb_scale_up:
        reasons.append(f"disk free {free_gb:.2f}GB is < scale-up threshold {min_disk_free_gb_scale_up:.2f}GB")
    if upload_backlog_hold is not None and upload_backlog >= upload_backlog_hold:
        reasons.append(f"upload backlog {upload_backlog} is >= hold threshold {upload_backlog_hold}")
    if io_blocked:
        reasons.append("I/O is marked blocked")
    if not rterm_responsive:
        reasons.append("Rterm/RStudio is not responsive")
    if not mcp_responsive:
        reasons.append("MCP is not responsive")
    if not durable_advancing:
        reasons.append("durable output is not advancing")

    if not reasons:
        decision = "increase_by_1"
        reasons.append("memory, CPU, disk, upload backlog, I/O, responsiveness, and durable output checks allow +1 concurrency")
    elif mem is not None and mem >= max(95.0, memory_threshold + 10):
        decision = "reduce_recommended"
    elif not mcp_responsive:
        decision = "stop_native_unstable"

    return {
        "decision": decision,
        "current_parallel": current_parallel,
        "recommended_parallel": current_parallel + 1 if decision == "increase_by_1" else current_parallel,
        "memory_used_percent": mem,
        "memory_threshold": memory_threshold,
        "cpu_used_percent": cpu,
        "cpu_scale_up_percent": cpu_scale_up_percent,
        "cpu_hold_percent": cpu_hold_percent,
        "disk_free_gb": free_gb,
        "min_disk_free_gb_scale_up": min_disk_free_gb_scale_up,
        "min_disk_free_gb_hold": min_disk_free_gb_hold,
        "upload_backlog": upload_backlog,
        "upload_backlog_hold": upload_backlog_hold,
        "output_root": output_root,
        "newest_mtime": latest,
        "previous_newest_mtime": previous_newest_mtime,
        "io_blocked": io_blocked,
        "rterm_responsive": rterm_responsive,
        "mcp_responsive": mcp_responsive,
        "durable_advancing": durable_advancing,
        "reasons": reasons,
    }


# fanout 专用准入；不改变独立 resource-gate 子命令的既有合同。
FANOUT_POLICY_DEFAULTS = {
    "worker_mem_gib": 1.0,
    "worker_commit_gib": 1.0,
    "worker_processors": 1,
    "worker_output_gib": 1.0,
    "reserve_mem_gib": 1.0,
    "reserve_commit_gib": 1.0,
    "reserve_processors": 1,
    "reserve_output_gib": 2.0,
    "sample_max_age_sec": 60.0,
}


def _finite_number(value: Any, *, minimum: float = 0, positive: bool = False) -> bool:
    try:
        return (
            isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > minimum if positive else value >= minimum)
        )
    except OverflowError:
        return False


def normalize_fanout_policy(resource_gate: dict[str, Any] | None) -> dict[str, Any]:
    """把本批 worker 预约转为字节；拒绝会绕过门槛的非有限或布尔数值。"""
    if resource_gate is not None and not isinstance(resource_gate, dict):
        raise ValueError("resource_gate must be an object")
    given = resource_gate or {}
    policy = {}
    for name, default in FANOUT_POLICY_DEFAULTS.items():
        value = given.get(name, default)
        if not _finite_number(value, positive=not name.startswith("reserve_")):
            raise ValueError(f"resource_gate.{name} must be finite and "
                             + ("nonnegative" if name.startswith("reserve_") else "positive"))
        if name.endswith("processors") and int(value) != value:
            raise ValueError(f"resource_gate.{name} must be an integer")
        policy[name] = value
        if name.endswith("_gib"):
            if not math.isfinite(value * 1024 ** 3):
                raise ValueError(f"resource_gate.{name} is too large")
            byte_value = math.ceil(value * 1024 ** 3)
            policy[name[:-4] + "_bytes"] = byte_value
    return policy


def fanout_admission(
    sample: dict[str, Any] | None,
    policy: dict[str, Any] | None,
    *,
    running_count: int = 0,
    now: float | None = None,
) -> dict[str, Any]:
    """返回本批额外可开槽数；当前用量与完整预约重复扣除是保守上界。"""
    policy = normalize_fanout_policy(policy)
    if isinstance(running_count, bool) or not isinstance(running_count, int) or running_count < 0:
        raise ValueError("running_count must be a nonnegative integer")
    now = time.time() if now is None else now
    sample = sample if isinstance(sample, dict) else {}
    identity_ok = (
        sample.get("host_verified") is True
        and isinstance(sample.get("host_id"), str) and bool(sample["host_id"].strip())
        and isinstance(sample.get("session_pid"), int) and not isinstance(sample["session_pid"], bool)
        and sample["session_pid"] > 0
        and isinstance(sample.get("output_root"), str) and bool(sample["output_root"].strip())
    )
    sampled_at = sample.get("sampled_at")
    age = now - sampled_at if _finite_number(now) and _finite_number(sampled_at) else None
    sample_reason = None
    if not identity_ok:
        sample_reason = "worker host resources unknown: host/session/output binding is unverified"
    elif age is None or age < 0:
        sample_reason = "worker host resources unknown: invalid or future sample time"
    elif age > policy["sample_max_age_sec"]:
        sample_reason = "worker host resources unknown: stale sample"
    if sample_reason and sample.get("reason"):
        sample_reason += "; " + str(sample["reason"])
    checks = {}
    reservations = {"scope": "this_fanout_batch_only", "running_count": running_count}
    for key, field, reserve_key, budget_key, label in (
        ("physical", "physical_available_bytes", "reserve_mem_bytes", "worker_mem_bytes", "physical bytes"),
        ("commit", "commit_available_bytes", "reserve_commit_bytes", "worker_commit_bytes", "commit bytes"),
        ("processors", "logical_processors", "reserve_processors", "worker_processors", "processor/thread budget"),
        ("output", "output_free_bytes", "reserve_output_bytes", "worker_output_bytes", "output volume bytes"),
    ):
        available = sample.get(field)
        reserved = running_count * policy[budget_key]
        valid = _finite_number(available)
        if key == "processors" and valid:
            valid = int(available) == available
        headroom = available - policy[reserve_key] - reserved if valid else None
        slots = max(0, math.floor(headroom / policy[budget_key])) if valid else 0
        reason = sample_reason or (
            f"worker host resources unknown: {label} unavailable" if not valid else
            f"{label} insufficient after reserve and running reservations" if slots < 1 else
            f"{label} allow {slots} additional worker(s) after reserve and running reservations"
        )
        checks[key] = {"available": available, "reserve": policy[reserve_key], "reserved": reserved,
                       "worker_budget": policy[budget_key], "headroom": headroom,
                       "slots": 0 if sample_reason else slots,
                       "ok": not sample_reason and slots > 0, "reason": reason}
        reservations[key] = reserved
    available_slots = min(c["slots"] for c in checks.values())
    return {
        "decision": "allow" if available_slots > 0 else "hold",
        "available_slots": available_slots,
        "reasons": [c["reason"] for c in checks.values()],
        "checks": checks, "reservations": reservations,
        "diagnostics": {"memory_used_percent": sample.get("memory_used_percent"),
                        "sample_age_sec": age, "host_id": sample.get("host_id"),
                        "session_pid": sample.get("session_pid"),
                        "session_name": sample.get("session_name"),
                        "resource_transport_class": sample.get("resource_transport_class"),
                        "output_root": sample.get("output_root"),
                        "probe_reason": sample.get("reason")},
    }


def _fanout_r_probe_code(marker: str, output_root: str, *, identity_only: bool = False) -> str:
    """RStudio 主机只读采样，所有中间值局限在 local 环境。"""
    # 固定 PowerShell 文本不插入合同数据，CIM 调用和 system2 都有超时。
    powershell = (
        "$ErrorActionPreference='Stop'; "
        "$m=Get-CimInstance Win32_PerfRawData_PerfOS_Memory -OperationTimeoutSec 2; "
        "[double]$m.CommitLimit-[double]$m.CommittedBytes"
    )
    resource_code = "" if identity_only else r'''
  memory <- ps::ps_system_memory()
  result$physical_available_bytes <- memory$avail
  result$logical_processors <- ps::ps_cpu_count(logical = TRUE)
  target <- output_path
  while (!dir.exists(target) && !identical(dirname(target), target)) target <- dirname(target)
  if (!dir.exists(target)) stop("output volume cannot be resolved")
  result$output_free_bytes <- ps::ps_disk_usage(target)$available[[1]]
  result$output_volume_path <- target
  result$commit_available_bytes <- NULL
  if (.Platform$OS.type == "windows") {
    commit_text <- suppressWarnings(system2("powershell.exe",
      c("-NoProfile", "-NonInteractive", "-Command", shQuote(POWER_SHELL_COMMAND)),
      stdout = TRUE, stderr = FALSE, timeout = 3))
    status <- attr(commit_text, "status")
    if (is.null(status) || identical(status, 0L)) {
      value <- suppressWarnings(as.numeric(tail(commit_text, 1)))
      if (length(value) == 1 && is.finite(value) && value >= 0) result$commit_available_bytes <- value
    }
    result$commit_source <- "Win32_PerfRawData_PerfOS_Memory.CommitLimit-CommittedBytes"
  } else if (identical(unname(Sys.info()["sysname"]), "Linux")) {
    info <- readLines("/proc/meminfo", warn = FALSE)
    field <- function(name) {
      row <- grep(paste0("^", name, ":"), info, value = TRUE)
      if (length(row) != 1) return(NA_real_)
      suppressWarnings(as.numeric(strsplit(trimws(sub("^[^:]+:", "", row)), "[[:space:]]+")[[1]][1]) * 1024)
    }
    limit <- field("CommitLimit")
    used <- field("Committed_AS")
    if (is.finite(limit) && is.finite(used)) result$commit_available_bytes <- max(0, limit - used)
    result$commit_source <- "/proc/meminfo CommitLimit-Committed_AS"
  } else {
    result$commit_source <- "unsupported; no swap-as-commit substitution"
  }
'''.replace("POWER_SHELL_COMMAND", json.dumps(powershell))
    template = r'''local({
  if (!requireNamespace("ps", quietly = TRUE) || !requireNamespace("jsonlite", quietly = TRUE))
    stop("worker resource probe requires ps and jsonlite")
  output_path <- OUTPUT_ROOT
  absolute <- if (.Platform$OS.type == "windows") {
    grepl("^[A-Za-z]:[/\\\\]|^[/\\\\]{2}", output_path)
  } else startsWith(output_path, "/")
  if (!absolute) stop("worker output_root must be absolute on the target host")
  output_path <- normalizePath(output_path, winslash = "/", mustWork = FALSE)
  result <- list(host_id = paste(unname(Sys.info()["nodename"]),
    unname(Sys.info()["sysname"]), as.numeric(ps::ps_boot_time()), sep = ":"),
    session_pid = Sys.getpid(), session_birth = as.numeric(ps::ps_create_time(ps::ps_handle())),
    output_root = output_path, worker_sampled_at = as.numeric(Sys.time()))
RESOURCE_CODE
  cat(MARKER, jsonlite::toJSON(result, auto_unbox = TRUE, null = "null", na = "null", digits = NA), "\n", sep = "")
})'''
    values = {"OUTPUT_ROOT": json.dumps(output_root, ensure_ascii=False),
              "RESOURCE_CODE": resource_code, "MARKER": json.dumps(marker)}
    return re.sub(r"OUTPUT_ROOT|RESOURCE_CODE|MARKER", lambda match: values[match[0]], template)


def _fanout_structured_job_status(payload: Any, job_id: str) -> dict[str, Any]:
    """只信精确 job_id 的结构字段；日志正文不参与终态判断。"""
    unknown = {"status": "unknown", "job_id": job_id,
               "reason": "original job terminal state is unverified; reservation retained"}
    if not isinstance(payload, dict) or payload.get("job_id") != job_id:
        return {**unknown, "reason": "structured job_id missing or mismatched; reservation retained"}
    status = payload.get("status")
    if not isinstance(status, str):
        return unknown
    status = status.lower()
    if status in {"complete", "completed", "done"}:
        success = payload.get("success")
        if not isinstance(success, bool):
            return {**unknown, "reason": "completed status lacks boolean success; reservation retained"}
        return {"job_id": job_id, "status": "completed" if success else "error", "success": success}
    if status in {"error", "failed", "cancelled", "canceled"}:
        return {"job_id": job_id, "status": "cancelled" if status in {"cancelled", "canceled"} else "error",
                "success": False}
    if status == "running":
        return {"job_id": job_id, "status": "running"}
    return unknown


def _fanout_r_final_peek_code(marker: str, job_id: str) -> str:
    """只读已收集的 ClaudeR final 缓存；不检查进程、不收集或取消任务。"""
    template = r'''local({
  requested_id <- JOB_ID
  result <- list(job_id = requested_id, status = "unknown")
  ns <- if ("ClaudeR" %in% loadedNamespaces()) asNamespace("ClaudeR") else NULL
  if (!is.null(ns) && exists(".claude_bg_jobs", envir = ns, inherits = FALSE)) {
    jobs <- get(".claude_bg_jobs", envir = ns, inherits = FALSE)
    if (is.environment(jobs) && exists(requested_id, envir = jobs, inherits = FALSE)) {
      entry <- get(requested_id, envir = jobs, inherits = FALSE)
      final <- if (is.list(entry)) entry[["final"]] else NULL
      metadata <- if (is.list(final)) final[["metadata"]] else NULL
      if (is.list(metadata) && identical(metadata[["job_id"]], requested_id)) {
        status <- final[["status"]]
        success <- final[["success"]]
        if (identical(status, "complete") &&
            is.logical(success) && length(success) == 1L && !is.na(success)) {
          result <- list(job_id = requested_id, status = status, success = success)
        }
      }
    }
  }
  cat(MARKER, jsonlite::toJSON(result, auto_unbox = TRUE, null = "null", na = "null"), "\n", sep = "")
})'''
    values = {"JOB_ID": json.dumps(job_id, ensure_ascii=False), "MARKER": json.dumps(marker)}
    return re.sub(r"JOB_ID|MARKER", lambda match: values[match[0]], template)


class FanoutResourceProbe:
    """固定 RStudio 选择器采样；不以 Python 本机资源替代 worker 主机。"""

    def __init__(self, session_name: str, output_root: str | None, timeout: float = 10.0,
                 *, sample_max_age_sec: float = 60.0):
        self.session_name = str(session_name or "")
        self.output_root = str(output_root or "")
        if not _finite_number(timeout, positive=True) or not _finite_number(sample_max_age_sec, positive=True):
            raise ValueError("probe timeout and sample_max_age_sec must be finite and positive")
        self.timeout = float(timeout)
        self.sample_timeout = min(self.timeout, 10.0)
        self.sample_max_age_sec = float(sample_max_age_sec)
        self._binding: tuple[Any, ...] | None = None
        self._last_sample: dict[str, Any] | None = None
        self._submission_unknown = False

    @staticmethod
    def _identity(sample: dict[str, Any]) -> tuple[Any, ...] | None:
        host, pid, birth, root = (sample.get(key) for key in
                                  ("host_id", "session_pid", "session_birth", "output_root"))
        if (not isinstance(host, str) or not host.strip()
                or not isinstance(pid, int) or isinstance(pid, bool) or pid < 1
                or not _finite_number(birth, positive=True)
                or not isinstance(root, str) or not root.strip()):
            return None
        return host, pid, birth, root

    def _unknown(self, reason: str, sampled_at: float) -> dict[str, Any]:
        return {"host_verified": False, "sampled_at": sampled_at,
                "reason": "worker host resources unknown: " + reason,
                "session_name": self.session_name, "output_root": self.output_root}

    def _invoke(self, *, code: str | None = None, job_id: str | None = None) -> dict[str, Any]:
        from . import mcp_client

        sampled_at = time.time()
        if not self.session_name.strip() or not self.output_root.strip():
            return {"ok": False, "hold": True, "submission_attempted": False,
                    "reason": "explicit RStudio session and worker output_root are required"}
        marker = "FANOUT_RESOURCE_" + secrets.token_hex(12) + "="
        submission_attempted = False

        async def runner(session: Any, command: str, args: list[str]) -> dict[str, Any]:
            nonlocal submission_attempted
            bound = mcp_client._tool_result(await session.call_tool(
                "connect_session", {"session_name": self.session_name}), tool_name="connect_session")
            if not bound["ok"]:
                return {"ok": False, "reason": "target RStudio connect_session failed"}
            checked = mcp_client._tool_result(await asyncio.wait_for(session.call_tool(
                "execute_r", {"code": _fanout_r_probe_code(marker, self.output_root,
                                                         identity_only=code is not None or job_id is not None)}),
                timeout=self.sample_timeout),
                tool_name="execute_r")
            if not checked["ok"]:
                return {"ok": False, "reason": "target RStudio resource/identity probe failed"}
            payloads = [line[len(marker):] for line in checked["text"].splitlines() if line.startswith(marker)]
            try:
                if len(payloads) != 1:
                    raise ValueError("resource marker missing or ambiguous")
                sample = json.loads(payloads[0])
                identity = self._identity(sample)
                if identity is None:
                    raise ValueError("worker identity is incomplete")
            except (ValueError, TypeError, AttributeError) as exc:
                return {"ok": False, "reason": str(exc)}
            if self._binding is not None and identity != self._binding:
                return {"ok": False, "reason": "worker host/R PID/birth/output identity changed"}
            if code is None and job_id is None:
                self._binding = identity
                return {"ok": True, "sample": {**sample, "sampled_at": sampled_at,
                                                "host_verified": True, "session_name": self.session_name,
                                                "requested_output_root": self.output_root,
                                                "resource_transport_class": "MCP_STDIO_OK"}}
            if self._binding is None:
                return {"ok": False, "reason": "worker resource sample required before submission"}
            if job_id is not None:
                # 原 job_id 只在原目标轮询；资源余量不足不阻止观察已经提交的任务。
                # 新配套默认可能等待300秒；轮询原 job 必须显式零等待。
                raw = await session.call_tool("get_async_result", {"job_id": job_id, "wait_s": 0})
                is_error = bool(getattr(raw, "isError", False) or getattr(raw, "is_error", False))
                polled = {"ok": not is_error, "is_error": is_error, "text": mcp_client._result_text(raw),
                          "job_id": job_id, "transport_class": "MCP_STDIO_OK",
                          "worker_host": identity[0], "session_pid": identity[1]}
                if is_error:
                    return {**polled, "status": "unknown",
                            "reason": "MCP polling error; original job and reservation retained"}
                structured = getattr(raw, "structuredContent", None)
                if structured is None:
                    structured = getattr(raw, "structured_content", None)
                if structured is not None:
                    status_result = _fanout_structured_job_status(structured, job_id)
                    return {**polled, **status_result, "ok": status_result["status"] != "unknown",
                            "status_source": "mcp_structured_content"}
                # 旧桥接仅返回 TextContent；从同一 R 会话读取已收集 final，绝不解析 stdout。
                status_marker = "FANOUT_FINAL_" + secrets.token_hex(12) + "="
                peek = await asyncio.wait_for(session.call_tool(
                    "execute_r", {"code": _fanout_r_final_peek_code(status_marker, job_id)}),
                    timeout=self.sample_timeout)
                if bool(getattr(peek, "isError", False) or getattr(peek, "is_error", False)):
                    return {**polled, "ok": False, "status": "unknown",
                            "reason": "terminal-cache probe failed; original job and reservation retained"}
                lines = [line[len(status_marker):] for line in mcp_client._result_text(peek).splitlines()
                         if line.startswith(status_marker)]
                try:
                    if len(lines) != 1:
                        raise ValueError("terminal-cache marker missing or ambiguous")
                    final = json.loads(lines[0])
                except (ValueError, TypeError):
                    final = None
                if not isinstance(final, dict) or final.get("status") != "complete":
                    final = None
                status_result = _fanout_structured_job_status(final, job_id)
                return {**polled, **status_result, "ok": status_result["status"] != "unknown",
                        "status_source": "clauder_final_cache"}
            latest = self._last_sample
            age = time.time() - latest["sampled_at"] if latest is not None else None
            if age is None or age < 0 or age > self.sample_max_age_sec:
                return {"ok": False, "reason": "worker resource sample became stale before submission"}
            # 身份复核和提交保持同一个 MCP 客户端连接，不跨失败目标重试。
            submission_attempted = True
            submitted = mcp_client._tool_result(await session.call_tool(
                "execute_r_async", {"code": code}), tool_name="execute_r_async")
            submitted_job_id = mcp_client.extract_job_id(submitted["text"])
            return {"ok": bool(submitted["ok"] and submitted_job_id), "job_id": submitted_job_id,
                    "text": submitted["text"], "transport_class": "MCP_STDIO_OK",
                    "worker_host": identity[0], "session_pid": identity[1]}

        try:
            timeout = self.sample_timeout if code is None and job_id is None else self.timeout
            result = asyncio.run(mcp_client._session_run(timeout, runner))
        except Exception as exc:
            result = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        if code is not None:
            result["submission_attempted"] = submission_attempted
            if not result.get("ok"):
                result["hold"] = not submission_attempted
                result["status"] = "UNKNOWN" if submission_attempted else "HOLD"
                if submission_attempted:
                    self._submission_unknown = True
        return result

    def poll(self, job_id: str) -> dict[str, Any]:
        if not isinstance(job_id, str) or not job_id.strip():
            return {"ok": False, "job_id": job_id, "status": "unknown", "reason": "original job_id is required"}
        if self._binding is None:
            return {"ok": False, "job_id": job_id, "status": "unknown",
                    "reason": "worker host identity unknown; original job_id retained without polling"}
        result = self._invoke(job_id=job_id)
        return {"status": "unknown", **result, "job_id": job_id}

    def sample(self) -> dict[str, Any]:
        started = time.time()
        result = self._invoke()
        if not result.get("ok"):
            self._last_sample = None
            return self._unknown(str(result.get("reason") or "probe failed"), started)
        sample = result["sample"]
        # 样本时钟来自调用起点；远端时钟仅保留诊断，不直接相减判断新鲜度。
        age = time.time() - sample["sampled_at"]
        if age < 0 or age > self.sample_max_age_sec:
            self._last_sample = None
            return self._unknown("sample timed out or became stale", sample["sampled_at"])
        self._last_sample = sample
        return sample

    def submit(self, code: str) -> dict[str, Any]:
        if self._submission_unknown:
            return {"ok": False, "hold": False, "status": "UNKNOWN", "job_id": None,
                    "submission_attempted": False,
                    "reason": "prior submission outcome unknown; reconcile the original attempt before any new submission"}
        sample = self._last_sample
        if sample is None:
            return {"ok": False, "hold": True, "submission_attempted": False,
                    "job_id": None, "reason": "worker host resources unknown: no valid sample"}
        age = time.time() - sample["sampled_at"]
        if age < 0 or age > self.sample_max_age_sec or any(
            not _finite_number(sample.get(name)) for name in
            ("physical_available_bytes", "commit_available_bytes", "logical_processors", "output_free_bytes")
        ):
            return {"ok": False, "hold": True, "submission_attempted": False,
                    "job_id": None, "reason": "worker host resources unknown: stale or incomplete sample"}
        result = self._invoke(code=code)
        if not result.get("ok"):
            self._last_sample = None
        return result
