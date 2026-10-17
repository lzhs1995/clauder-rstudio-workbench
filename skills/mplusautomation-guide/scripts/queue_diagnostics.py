"""只读队列诊断；显式区分记录状态、进程存活、依赖和资源准入。"""
from __future__ import annotations
import argparse
from collections import Counter
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sqlite3
import statistics
import time
import psutil
from process_ownership import verified_descendants

_spec=importlib.util.spec_from_file_location('mplus_queue',Path(__file__).with_name('mplus_queue.py'))
mq=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mq)

def analyze(rows, settings, resources, policy, live_workers):
    """纯诊断：不 claim、不写数据库、不重排任务。"""
    indexed={r['id']:r for r in rows}
    active=[r['payload'] for r in rows if r['status']=='running']
    pending=[]
    for r in rows:
        if r['status']!='pending':continue
        p=r['payload'];blockers=[]
        for d in p.get('dependencies',[]):
            up=indexed.get(d['id'])
            if up is None or up['status']!='completed' or not (up.get('result') or {}).get(d.get('requires','estimation_ok')):
                blockers.append(d['id'])
        reuse=p.get('reuse_task')
        reuse_row=indexed.get(reuse)
        reuse_wait=bool(reuse and (not reuse_row or reuse_row['status'] not in ('completed','failed','blocked')))
        reason=('disabled' if not settings['enabled'] else 'dependency_wait' if blockers else
                'reuse_wait' if reuse_wait else mq.admission_reason(resources,active,p,settings['limit'],policy))
        pending.append(dict(id=r['id'],reason=reason or 'admissible',dependencies=blockers,
                            execution_class=p.get('execution_class'),processors=p.get('processors',1),
                            tables=p.get('tables'),dispatch_priority=p.get('dispatch_priority',p.get('priority',10))))
    durations=[]
    for r in rows:
        if r['status'] in ('completed','failed') and r.get('started') and r.get('finished'):
            durations.append(dict(id=r['id'],seconds=(dt.datetime.fromisoformat(r['finished'])-dt.datetime.fromisoformat(r['started'])).total_seconds(),status=r['status']))
    ds=sorted(d['seconds'] for d in durations)
    return dict(counts=dict(Counter(r['status'] for r in rows)),
                reused=sum(bool((r.get('result') or {}).get('reused')) for r in rows),
                running=[dict(id=r['id'],worker=r['worker'],worker_alive=r['worker'] in live_workers) for r in rows if r['status']=='running'],
                pending=pending,pending_reasons=dict(Counter(x['reason'] for x in pending)),
                timed_attempts=len(ds),median_seconds=statistics.median(ds) if ds else None,
                p90_seconds=ds[int(.9*(len(ds)-1))] if ds else None,
                longest=sorted(durations,key=lambda x:x['seconds'],reverse=True)[:10])

def summarize_host_mplus(processes, owned_mplus):
    """匹配 PID 及创建时间；缺失父进程不意味着可以终止进程。"""
    groups = {'owned': [], 'outside_verified_worker_tree': []}
    for process in processes:
        owned = any(process.get('pid') == item.get('pid')
                    and process.get('created') is not None
                    and item.get('created') is not None
                    and abs(process['created'] - item['created']) <= .1
                    for item in owned_mplus)
        groups['owned' if owned else 'outside_verified_worker_tree'].append(process)
    summary = {}
    for name, group in groups.items():
        private = [p['private_bytes'] for p in group if p.get('private_bytes') is not None]
        summary[name] = dict(count=len(group), known_private_bytes=sum(private),
                             private_measurement_complete=len(private) == len(group),
                             parent_missing_count=sum(p.get('parent_status') == 'missing' for p in group))
    return dict(summary=summary, processes=groups,
                limitation='Outside the verified worker tree is not proof of an unrelated or safely terminable job. Missing parents and CPU activity do not establish estimation success.')


def host_mplus_inventory(owned_mplus):
    """按需枚举全机 Mplus；不输出可能携带凭据的完整命令行。"""
    rows, issues = [], []
    for proc in psutil.process_iter(['pid', 'name']):
        if (proc.info.get('name') or '').lower() not in ('mplus', 'mplus.exe'):
            continue
        try:
            created = proc.create_time()
            mem = proc.memory_info()
            row = dict(pid=proc.pid, created=created, ppid=proc.ppid(),
                       cpu_seconds=sum(proc.cpu_times()[:2]),
                       wall_seconds=max(0, time.time()-created),
                       rss_bytes=mem.rss, private_bytes=getattr(mem, 'private', None))
            try:
                row['cwd'] = proc.cwd()
            except psutil.Error:
                row['cwd'] = None
            try:
                parent = proc.parent()
                row['parent_status'] = 'missing' if parent is None else (
                    'pid_reused' if parent.create_time() > created else 'present')
            except psutil.NoSuchProcess:
                row['parent_status'] = 'missing'
            except psutil.Error:
                row['parent_status'] = 'unknown'
            rows.append(row)
        except psutil.Error as exc:
            issues.append(dict(pid=proc.pid, error=type(exc).__name__))
    report = summarize_host_mplus(rows, owned_mplus)
    report['inspection_issues'] = issues
    return report


def collect(root, namespace=None, host_processes=False):
    root=Path(root).resolve()
    db=sqlite3.connect((root/'queue.sqlite').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try:
        rows=[dict(x) for x in db.execute('SELECT * FROM tasks')]
        for r in rows:
            r['payload']=json.loads(r['payload']);r['result']=json.loads(r['result'] or '{}')
        settings={r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM settings')}
        workers=[dict(x) for x in db.execute('SELECT * FROM workers')]
    finally:db.close()
    live=[];processes=[];identity=[]
    for w in workers:
        try:
            p=psutil.Process(w['pid'])
            if w.get('created') is None or abs(p.create_time()-w['created'])>.1:
                identity.append(dict(worker=w['id'],status='identity_mismatch_or_missing'));continue
            live.append(w['id'])
            for child in verified_descendants(p,names={'mplus','mplus.exe'}):
                if child.name().lower() in ('mplus','mplus.exe'):
                    mem=child.memory_info()
                    processes.append(dict(worker=w['id'],pid=child.pid,created=child.create_time(),cpu_seconds=sum(child.cpu_times()[:2]),
                        rss_bytes=mem.rss,private_bytes=getattr(mem,'private',None)))
        except (psutil.Error,RuntimeError) as e:identity.append(dict(worker=w['id'],status=type(e).__name__))
    config=json.loads((root/'config.json').read_text(encoding='utf-8-sig')) if (root/'config.json').exists() else {}
    resources=mq.resource_snapshot()
    result=analyze(rows,settings,resources,config.get('resource_policy',{}),live)
    result.update(utc=mq.utc(),resources=resources,owned_mplus=processes,worker_identity_issues=identity,producers_done=settings.get('producers_done'))
    if host_processes:
        result['host_mplus'] = host_mplus_inventory(processes)
    if namespace is not None:
        result['namespace_counts']=dict(Counter(r['status'] for r in rows if r['id'].startswith(namespace+'-')))
    result['limitations']=['Counts are invocation records, not independent models or validated manuscript cells.',
      'Timing excludes still-running and interrupted attempts; no whole-project ETA follows from the median.',
      'Process presence or a single CPU sample does not prove progress; compare timestamps and CPU deltas.',
      'Wall time includes sleep, suspension, and resource contention; CPU time is not a convergence diagnostic.',
      'An admissible reused task may copy a validated result instead of launching a model.']
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True)
    parser.add_argument('--namespace')
    parser.add_argument('--host-processes', action='store_true', help='Read-only inventory of all Mplus processes, including those outside registered worker trees')
    parser.add_argument('--output',help='New evidence path; existing files are never overwritten')
    args=parser.parse_args()
    report=json.dumps(collect(args.root,args.namespace,args.host_processes),ensure_ascii=False,indent=2)
    if args.output:
        with Path(args.output).open('x',encoding='utf-8') as f:f.write(report)
    else:print(report)
