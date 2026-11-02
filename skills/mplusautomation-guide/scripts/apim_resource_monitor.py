"""只观测指定R worker及其Mplus子进程；不扫描/终止其他分析。"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import psutil
from process_ownership import verified_descendants


def monitor(pid, created, folder, engine_sha256, interval=.2):
    folder = Path(folder)
    parent = psutil.Process(pid)
    if abs(parent.create_time() - created) > .1:
        raise ValueError('Worker PID was reused')
    started = time.time()
    peak_rss = peak_private = 0
    engine_pids = set()
    samples = 0
    errors = []
    ready = folder / 'monitor.ready'
    ready.write_text(str(started), encoding='ascii')
    while True:
        try:
            children = verified_descendants(parent, names={'mplus.exe'})
            processes = [parent] + children
            rss = private = 0
            for process in processes:
                try:
                    memory = process.memory_info()
                    rss += memory.rss
                    private += getattr(memory, 'private', memory.rss)
                    if process.pid != pid:
                        engine_pids.add((process.pid, process.create_time()))
                except psutil.NoSuchProcess:
                    continue
            peak_rss = max(peak_rss, rss)
            peak_private = max(peak_private, private)
            samples += 1
        except psutil.NoSuchProcess:
            errors.append('worker_exited_before_monitor_stop')
            break
        if (folder / 'monitor.stop').exists():
            if children:
                raise ValueError('Engine still alive at monitor stop')
            break
        time.sleep(interval)
    receipt = dict(worker_pid=pid, worker_created=created, engine_sha256=engine_sha256,
                   peak_rss_gib=peak_rss / 2**30, peak_private_gib=peak_private / 2**30,
                   engine_identities=sorted(engine_pids), samples=samples, interval_seconds=interval,
                   elapsed_seconds=time.time()-started, errors=errors,
                   measured_engine=bool(engine_pids), engine_exited=not errors)
    (folder / 'resource_measurement.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--created', type=float, required=True)
    p.add_argument('--folder', required=True)
    p.add_argument('--engine-sha256', required=True)
    a = p.parse_args()
    print(json.dumps(monitor(a.pid, a.created, a.folder, a.engine_sha256)))
