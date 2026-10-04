"""记录现有前台会话增量模型的实时资源准入；不创建工作者或关闭进程。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import psutil

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
    args=parser.parse_args()
    samples=[psutil.cpu_percent(interval=1) for _ in range(3)]
    mem=psutil.virtual_memory()
    data=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        execution_class='existing_RStudio_frontend_one_Mplus_processor',new_R_workers=0,
        incremental_budget_gib=args.budget_gib,reserved_free_gib=args.reserve_gib,
        available_gib=mem.available/2**30,memory_percent=mem.percent,
        cpu_percent_samples=samples,cpu_limit=args.cpu_limit,
        eligible=assess(samples,mem.available/2**30,args.budget_gib,args.reserve_gib,args.cpu_limit),
        basis=args.basis,generic_new_worker_gate='not overridden')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.output.with_name(args.output.name+f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    os.replace(temporary,args.output)
    print(json.dumps(data))

if __name__=='__main__': main()
