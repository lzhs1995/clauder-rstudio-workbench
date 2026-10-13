"""Windows 原生轻量准入探针：只读；全机进程清单仅按需采样。"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import psutil
from windows_resource_probe import host_snapshot, PdhCounters, process_snapshot
from mplus_queue import atomic_json


def collect(samples=3, interval=1.0, include_processes=False):
    if os.name != "nt":
        raise RuntimeError("Use native Windows Python; WSL is not the host")
    if samples < 3 or not 0.1 <= interval <= 10:
        raise ValueError("Require >=3 samples and 0.1<=interval<=10")
    started = time.monotonic()
    counters = PdhCounters()
    counters.collect()
    psutil.cpu_percent()
    rows = []
    try:
        for _ in range(samples):
            time.sleep(interval)
            rows.append(dict(cpu_percent=psutil.cpu_percent(), paging=counters.collect(),
                             host=host_snapshot()))
    finally:
        counters.close()
    last = rows[-1]["host"]
    perf = last["performance_bytes"]
    if "CommitLimit" not in perf or "CommitTotal" not in perf:
        raise RuntimeError("Windows commit headroom unavailable")
    gib = 2**30
    system = dict(free_phys_gib=last["memory"]["available"]/gib,
                  total_phys_gib=last["memory"]["total"]/gib,
                  free_virtual_gib=(perf["CommitLimit"]-perf["CommitTotal"])/gib,
                  committed_gib=perf["CommitTotal"]/gib,
                  commit_limit_gib=perf["CommitLimit"]/gib,
                  disk_free_gib=last["disk_free_bytes"]/gib,
                  cpu_percent_samples=[r["cpu_percent"] for r in rows])
    paging = {}
    for source, target in {"pages_input_per_sec":"pages_input_sec",
                           "pages_output_per_sec":"pages_output_sec",
                           "page_reads_per_sec":"page_reads_sec",
                           "page_writes_per_sec":"page_writes_sec",
                           "disk_read_latency_sec":"disk_read_latency_sec",
                           "disk_write_latency_sec":"disk_write_latency_sec",
                           "disk_queue":"disk_queue", "cpu_queue":"cpu_queue"}.items():
        values = [r["paging"][source] for r in rows if isinstance(r["paging"].get(source),(int,float))]
        paging[target] = sum(values)/len(values) if values else None
    paging["sample_count"] = samples
    payload = dict(generated_at=datetime.now(timezone.utc).isoformat(), returncode=0,
                   profile=dict(system=system,paging=paging,counter_errors=counters.errors),
                   samples=rows, interpretation="paging_telemetry_not_proof_of_thrashing")
    if include_processes:
        payload["profile"]["processes"] = list(process_snapshot().values())
    payload["duration_seconds"] = time.monotonic()-started
    return payload


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--samples",type=int,default=3)
    ap.add_argument("--interval",type=float,default=1)
    ap.add_argument("--include-processes",action="store_true")
    args=ap.parse_args()
    data=collect(args.samples,args.interval,args.include_processes)
    atomic_json(args.output,data)
    print(json.dumps(dict(output=str(args.output),system=data["profile"]["system"],
                         paging=data["profile"]["paging"],duration_seconds=data["duration_seconds"])))

if __name__ == "__main__":
    main()
