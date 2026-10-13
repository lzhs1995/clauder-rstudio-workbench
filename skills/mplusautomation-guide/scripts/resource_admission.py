"""记录现有前台会话增量模型的实时资源准入；不创建工作者或关闭进程。"""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import psutil

from mplus_queue import resource_snapshot, _is_wsl, atomic_json

def assess(samples, available, budget, reserve, cpu_limit):
    if budget <= 0 or reserve < 0 or not 0 < cpu_limit <= 100:
        raise ValueError('Invalid measured budget or resource limit')
    return bool(len(samples) >= 3 and all(0 <= x < cpu_limit for x in samples)
                and available >= budget + reserve)


def paging_io_pressure(paging):
    """Return true only for output paging combined with elevated disk latency."""
    if not isinstance(paging, dict):
        return False
    page_out = paging.get('pages_output_sec')
    read_latency = paging.get('disk_read_latency_sec')
    write_latency = paging.get('disk_write_latency_sec')
    return (isinstance(page_out, (int, float)) and math.isfinite(page_out) and page_out > 0
            and ((isinstance(read_latency, (int, float)) and math.isfinite(read_latency) and read_latency >= 0.01)
                 or (isinstance(write_latency, (int, float)) and math.isfinite(write_latency) and write_latency >= 0.01)))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget-gib',type=float,required=True)
    parser.add_argument('--reserve-gib',type=float,required=True)
    parser.add_argument('--cpu-limit',type=float,default=85)
    parser.add_argument('--basis',required=True)
    parser.add_argument('--commit-reserve-gib',type=float,default=2.0)
    parser.add_argument('--disk-reserve-gib',type=float,default=10.0)
    parser.add_argument('--windows-profile',type=Path,
                        help='Fresh Windows host profile JSON; required when run inside WSL')
    parser.add_argument('--max-profile-age-sec',type=float,default=300)
    parser.add_argument('--runtime-health',type=Path,
                        help='Latest read-only runtime receipt; external Mplus keeps admission closed')
    args=parser.parse_args()
    samples=[] if _is_wsl() or args.windows_profile else [psutil.cpu_percent(interval=1) for _ in range(3)]
    snapshot=resource_snapshot(args.windows_profile,args.max_profile_age_sec)
    if args.windows_profile:
        samples=snapshot.get("cpu_percent_samples", [])
    runtime={}
    runtime_read_error=None
    if args.runtime_health:
        try:
            runtime=json.loads(args.runtime_health.read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            runtime_read_error=type(exc).__name__
    runtime_reasons=[]
    if args.runtime_health:
        if runtime_read_error:
            runtime_reasons.append('runtime_health_unverified')
        else:
            stamp=runtime.get('checked_at',runtime.get('generated_at'))
            try:
                parsed=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00'))
                age=(datetime.datetime.now(datetime.timezone.utc)-parsed).total_seconds()
                if age < -5 or age > args.max_profile_age_sec:
                    runtime_reasons.append('runtime_health_stale')
            except (TypeError,ValueError,AttributeError):
                runtime_reasons.append('runtime_health_unverified')
    if runtime.get('external_mplus_count',0):
        runtime_reasons.append('external_mplus_present')
    if runtime.get('target_mplus_count',0):
        runtime_reasons.append('target_mplus_already_running')
    paging = snapshot.get('paging') or {}
    resource_ok=(not snapshot.get('host_memory_unverified',False) and
                 assess(samples,snapshot['available_gib'],args.budget_gib,args.reserve_gib,args.cpu_limit))
    reasons=[]
    if snapshot.get('host_memory_unverified',False): reasons.append('host_memory_unverified')
    elif snapshot['available_gib'] < args.budget_gib + args.reserve_gib: reasons.append('physical_memory_reserve')
    if any(x >= args.cpu_limit for x in samples): reasons.append('cpu_limit')
    if len(samples)<3 or snapshot.get('host_cpu_unverified'):
        reasons.append('host_cpu_unverified')
    if snapshot.get('host_disk_unverified'):
        reasons.append('host_disk_unverified')
    elif snapshot['disk_free_gib'] < args.disk_reserve_gib:
        reasons.append('disk_reserve')
    # A single Pages Input/sec value is not a gate.  Hold only when output
    # paging and materially elevated disk latency occur together.
    if paging_io_pressure(paging):
        reasons.append('paging_io_pressure')
    commit=snapshot.get('free_virtual_gib')
    if commit is None:
        reasons.append('host_commit_unverified')
    elif commit < args.budget_gib + args.commit_reserve_gib:
        reasons.append('commit_reserve')
    reasons.extend(runtime_reasons)
    data=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        execution_class='existing_RStudio_frontend_one_Mplus_processor',new_R_workers=0,
        incremental_budget_gib=args.budget_gib,reserved_free_gib=args.reserve_gib,
        available_gib=snapshot['available_gib'],memory_percent=snapshot['memory_percent'],
        resource_source=snapshot.get('source'),host_memory_unverified=snapshot.get('host_memory_unverified',False),
        resource_error=snapshot.get('resource_error'),commit_percent=snapshot.get('commit_percent'),
        paging=snapshot.get('paging'),paging_interpretation='telemetry_only_not_a_speed_or_thrashing_verdict',
        cpu_percent_samples=samples,cpu_limit=args.cpu_limit,
        eligible=bool(resource_ok and not reasons), admission_reasons=reasons,
        commit_headroom_gib=commit,commit_reserve_gib=args.commit_reserve_gib,
        disk_free_gib=snapshot.get('disk_free_gib'),disk_reserve_gib=args.disk_reserve_gib,
        required_available_gib=args.budget_gib+args.reserve_gib,
        runtime_health=str(args.runtime_health) if args.runtime_health else None,
        runtime_health_read_error=runtime_read_error,
        basis=args.basis,generic_new_worker_gate='not overridden')
    atomic_json(args.output,data)
    print(json.dumps(data))

if __name__=='__main__': main()
