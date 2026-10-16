"""Windows Mplus调度协调器：显式进程归属、持久回滚、只读资源观测。"""
import argparse
import ctypes
import json
import math
import os
import time
from contextlib import contextmanager
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
import psutil


def utc(): return datetime.now(timezone.utc).isoformat()


def save(path, value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,path)


def event(root, value):
    with (root/'actions.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({'at':utc(),**value},ensure_ascii=False)+'\n')


def identity(process): return dict(pid=process.pid,created=process.create_time())


def checked(ref, factory=psutil.Process):
    p=factory(ref['pid'])
    if not math.isfinite(ref['created']) or abs(p.create_time()-ref['created'])>.01:
        raise RuntimeError('Process identity changed; PID reuse or wrong creation time')
    return p


def owned_mplus(owner, factory=psutil.Process):
    parent=checked(owner,factory)
    children=[]
    for p in parent.children(recursive=True):
        try:
            if p.name().lower()=='mplus.exe': children.append(identity(p))
        except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    return children


def apply_owned(owner, targets, state, persist, factory=psutil.Process):
    """每个进程仅尝试一次；先保存原值再写，后续用户改值不被反复覆盖。"""
    actions=[]
    for ref in owned_mplus(owner,factory):
        key=f'{ref["pid"]}:{ref["created"]}'
        if key in state['processes']: continue
        checked(owner,factory)
        try:
            p=checked(ref,factory);changes={}
            for prop,wanted in targets.items():
                getter=p.nice if prop=='priority' else p.cpu_affinity
                prior=getter()
                changes[prop]=dict(prior=int(prior) if prop=='priority' else list(prior),target=wanted,status='planned')
        except psutil.NoSuchProcess: continue
        except psutil.AccessDenied as exc:
            actions.append(dict(**ref,status='access_denied',reason=str(exc)));continue
        state['processes'][key]=dict(**ref,changes=changes)
        persist(state)  # 崩溃后也能按已记录target条件恢复。
        for prop,change in changes.items():
            try:
                checked(owner,factory);p=checked(ref,factory)
                setter=p.nice if prop=='priority' else p.cpu_affinity
                if setter()!=change['prior']:
                    change['status']='skipped_concurrent_change'
                elif change['prior']==change['target']:
                    change['status']='already_target'
                else:
                    setter(change['target'])
                    if setter()!=change['target']: raise RuntimeError('Scheduling setter did not take effect')
                    change['status']='applied'
            except (psutil.NoSuchProcess,psutil.AccessDenied,RuntimeError) as exc:
                change['status']='failed';change['error']=str(exc)
            persist(state)
        actions.append(dict(**ref,changes=changes))
    return actions


def restore_owned(state, persist, factory=psutil.Process):
    results=[]
    for record in state['processes'].values():
        try: p=checked(record,factory)
        except (psutil.NoSuchProcess,psutil.AccessDenied,RuntimeError) as exc:
            results.append(dict(pid=record['pid'],status='identity_unavailable',reason=str(exc)));continue
        for prop,change in record['changes'].items():
            setter=p.nice if prop=='priority' else p.cpu_affinity
            try:
                if change['prior']==change['target'] or change['status']=='skipped_concurrent_change':
                    status='no_owned_change'
                elif setter()!=change['target']:
                    status='preserved_later_change'
                else:
                    setter(change['prior'])
                    if setter()!=change['prior']: raise RuntimeError('Restore did not take effect')
                    status='restored'
                change['restore_status']=status
                results.append(dict(pid=p.pid,property=prop,status=status))
            except (psutil.NoSuchProcess,psutil.AccessDenied,RuntimeError) as exc:
                change['restore_status']='failed';results.append(dict(pid=record['pid'],property=prop,status='failed',reason=str(exc)))
            persist(state)
    return results


def memory():
    class Performance(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in
          ['CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable','SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize']]+[(n,wintypes.DWORD) for n in ['HandleCount','ProcessCount','ThreadCount']]
    p=Performance();p.cb=ctypes.sizeof(p)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(p),p.cb): raise ctypes.WinError()
    return dict(physical_available_gib=p.PhysicalAvailable*p.PageSize/2**30,
                commit_headroom_gib=(p.CommitLimit-p.CommitTotal)*p.PageSize/2**30)


def sample(owner, prior=None):
    rows=[];next_sample={}
    for ref in owned_mplus(owner):
        try:
            p=checked(ref);cpu=p.cpu_times();mem=p.memory_info();clock=time.monotonic()
            key=f'{p.pid}:{ref["created"]}';now=dict(wall=clock,cpu=cpu.user+cpu.system)
            old=(prior or {}).get(key);delta=now['wall']-old['wall'] if old else None
            rows.append(dict(**ref,rss_gib=mem.rss/2**30,private_gib=getattr(mem,'private',0)/2**30,
                threads=p.num_threads(),priority=int(p.nice()),affinity=p.cpu_affinity(),
                wall_seconds=delta,cpu_seconds=now['cpu']-old['cpu'] if old else None,
                cpu_core_equivalents=(now['cpu']-old['cpu'])/delta if old and delta>0 else None,
                total_page_faults=getattr(mem,'num_page_faults',None)))
            next_sample[key]=now
        except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    return dict(at=utc(),host=memory(),owned_mplus=rows,
        limits='Page faults include soft faults; no disk-paging diagnosis or throughput claim from this sample.'),next_sample


@contextmanager
def exclusive(root):
    import msvcrt
    with (root/'coordinator.lock').open('a+b') as f:
        f.seek(0)
        if not f.read(1): f.write(b'0');f.flush()
        f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        try: yield
        finally:
            f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['observe','watch','stop','restore'])
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--owner-pid',type=int);parser.add_argument('--owner-created',type=float)
    parser.add_argument('--interval',type=float,default=30)
    parser.add_argument('--duration',type=float,default=0,help='0: watch until stop/owner exit; observe defaults to one interval')
    parser.add_argument('--affinity',help='Optional validated host CPU indices, comma separated; no default pinning')
    args=parser.parse_args()
    if os.name!='nt': parser.error('Run with native Windows Python; WSL metrics are not host metrics')
    if not math.isfinite(args.interval) or not 1<=args.interval<=60: parser.error('interval must be 1..60 seconds')
    if not math.isfinite(args.duration) or args.duration<0: parser.error('duration must be nonnegative')
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    if args.mode=='stop':
        (root/'stop.request').write_text(utc(),encoding='utf-8');print('Stop requested; verify coordinator exit/restore log');return
    with exclusive(root):
        statefile=root/'scheduling_state.json'
        persist=lambda s:save(statefile,s)
        if args.mode=='restore':
            state=json.loads(statefile.read_text(encoding='utf-8'))
            result=restore_owned(state,persist);event(root,dict(event='restore',results=result));print(json.dumps(result));return
        if args.owner_pid is None or args.owner_created is None: parser.error('owner PID and creation time are both required')
        owner=dict(pid=args.owner_pid,created=args.owner_created);checked(owner)
        targets=dict(priority=int(psutil.ABOVE_NORMAL_PRIORITY_CLASS))
        if args.affinity:
            cpus=sorted(set(int(v) for v in args.affinity.split(',')))
            if not cpus or min(cpus)<0 or max(cpus)>=psutil.cpu_count(): parser.error('invalid affinity CPU index')
            targets['affinity']=cpus
        if args.mode=='observe': targets={}
        state=dict(owner=owner,targets=targets,processes={})
        if statefile.exists() or (root/'coordinator_identity.json').exists():
            raise RuntimeError('Use a fresh output directory for each watch/observation; restore old state separately')
        if (root/'stop.request').exists(): raise RuntimeError('Stop marker exists; use a new observation/watch directory')
        save(root/'coordinator_identity.json',dict(**identity(psutil.Process()),owner=owner,mode=args.mode,targets=targets))
        if args.mode=='watch': persist(state)
        duration=args.duration or (args.interval if args.mode=='observe' else None)
        start=time.monotonic();prior=None;reason='running'
        try:
            while True:
                if (root/'stop.request').exists(): reason='stop_requested';break
                try:
                    if args.mode=='watch':
                        actions=apply_owned(owner,targets,state,persist)
                        if actions: event(root,dict(event='apply',actions=actions))
                    row,prior=sample(owner,prior);event(root,dict(event='sample',**row))
                except (psutil.NoSuchProcess,RuntimeError) as exc:
                    reason='owner_unavailable';event(root,dict(event=reason,reason=str(exc)));break
                elapsed=time.monotonic()-start
                if duration is not None and elapsed>=duration: reason='duration_elapsed';break
                pause=min(args.interval,max(0,duration-elapsed)) if duration is not None else args.interval
                end=time.monotonic()+pause
                while time.monotonic()<end and not (root/'stop.request').exists():
                    time.sleep(min(1,max(0,end-time.monotonic())))
        except BaseException as exc:
            reason='interrupted' if isinstance(exc,KeyboardInterrupt) else 'error'
            event(root,dict(event=reason,reason=str(exc)));raise
        finally:
            restored=restore_owned(state,persist) if args.mode=='watch' else []
            event(root,dict(event='finished',restore=restored))
            save(root/'completion.json',dict(status='COORDINATOR_STOPPED',stop_reason=reason,mode=args.mode,at=utc(),
                owned_mplus_identities=len(state['processes']),restore=restored,new_mplus_calls=0,
                throughput_improvement_verified=False))
        print(json.dumps(dict(status='COORDINATOR_STOPPED',mode=args.mode,output=str(root),owned_mplus_identities=len(state['processes']))))


if __name__=='__main__': main()
