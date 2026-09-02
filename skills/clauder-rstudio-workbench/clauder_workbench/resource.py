from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


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
