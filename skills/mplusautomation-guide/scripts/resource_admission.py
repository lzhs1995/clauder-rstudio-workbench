"""记录现有前台会话增量模型的实时资源准入；不创建工作者或关闭进程。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import psutil

from mplus_queue import resource_snapshot

def assess(samples, available, budget, reserve, cpu_limit):
    if budget <= 0 or reserve < 0 or not 0 < cpu_limit <= 100:
        raise ValueError('Invalid measured budget or resource limit')
    return bool(len(samples) >= 3 and all(0 <= x < cpu_limit for x in samples)
                and available >= budget + reserve)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget-gib',type=float,required=True)
    parser.add_argument('--reserve-gib',type=float,required=True)
    parser.add_argument('--cpu-limit',type=float,default=85)
    parser.add_argument('--basis',required=True)
    parser.add_argument('--windows-profile',type=Path,
                        help='Fresh Windows host profile JSON; required when run inside WSL')
    parser.add_argument('--max-profile-age-sec',type=float,default=300)
    parser.add_argument('--runtime-health',type=Path,
                        help='Latest read-only runtime receipt; external Mplus keeps admission closed')
    args=parser.parse_args()
    samples=[psutil.cpu_percent(interval=1) for _ in range(3)]
    snapshot=resource_snapshot(args.windows_profile,args.max_profile_age_sec)
    runtime={}
    if args.runtime_health:
        runtime=json.loads(args.runtime_health.read_text(encoding='utf-8-sig'))
    runtime_reasons=[]
    if runtime.get('external_mplus_count',0):
        runtime_reasons.append('external_mplus_present')
    if runtime.get('target_mplus_count',0):
        runtime_reasons.append('target_mplus_already_running')
    resource_ok=(not snapshot.get('host_memory_unverified',False) and
                 assess(samples,snapshot['available_gib'],args.budget_gib,args.reserve_gib,args.cpu_limit))
    reasons=[]
    if snapshot.get('host_memory_unverified',False): reasons.append('host_memory_unverified')
    elif snapshot['available_gib'] < args.budget_gib + args.reserve_gib: reasons.append('physical_memory_reserve')
    if any(x >= args.cpu_limit for x in samples): reasons.append('cpu_limit')
    reasons.extend(runtime_reasons)
    data=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        execution_class='existing_RStudio_frontend_one_Mplus_processor',new_R_workers=0,
        incremental_budget_gib=args.budget_gib,reserved_free_gib=args.reserve_gib,
        available_gib=snapshot['available_gib'],memory_percent=snapshot['memory_percent'],
        resource_source=snapshot.get('source'),host_memory_unverified=snapshot.get('host_memory_unverified',False),
        resource_error=snapshot.get('resource_error'),commit_percent=snapshot.get('commit_percent'),
        cpu_percent_samples=samples,cpu_limit=args.cpu_limit,
        eligible=bool(resource_ok and not runtime_reasons), admission_reasons=reasons,
        runtime_health=str(args.runtime_health) if args.runtime_health else None,
        basis=args.basis,generic_new_worker_gate='not overridden')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.output.with_name(args.output.name+f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    os.replace(temporary,args.output)
    print(json.dumps(data))

if __name__=='__main__': main()
