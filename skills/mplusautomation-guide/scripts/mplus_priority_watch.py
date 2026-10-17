"""Windows轻量采样；仅可调整指定R父进程下Mplus优先级，退出恢复。"""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import time
import psutil
from windows_memory import snapshot
from process_ownership import is_verified_descendant, verified_descendants


class VALUE(ctypes.Structure):
    _fields_ = [('status', wintypes.DWORD), ('value', ctypes.c_double)]


class Paging:
    # 使用英文计数器名，兼容中文Windows；计数器不可用时报告缺失而非零。
    def __init__(self):
        self.dll = ctypes.WinDLL('pdh')
        self.query = wintypes.HANDLE()
        self.counters = {}
        self.dll.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
        self.dll.PdhAddEnglishCounterW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
        self.dll.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
        self.dll.PdhGetFormattedCounterValue.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(VALUE)]
        self.dll.PdhCloseQuery.argtypes = [wintypes.HANDLE]
        self.errors = {}
        status = self.dll.PdhOpenQueryW(None, 0, ctypes.byref(self.query))
        if status:
            raise OSError(f'PdhOpenQuery: {status}')
        for key, name in {'page_reads_per_sec': r'\Memory\Page Reads/sec',
                          'pages_input_per_sec': r'\Memory\Pages Input/sec',
                          'disk_transfer_seconds': r'\PhysicalDisk(_Total)\Avg. Disk sec/Transfer'}.items():
            counter = wintypes.HANDLE()
            status = self.dll.PdhAddEnglishCounterW(self.query, name, 0, ctypes.byref(counter))
            if status:
                self.errors[key] = status
            else:
                self.counters[key] = counter
        self.dll.PdhCollectQueryData(self.query)

    def read(self):
        self.dll.PdhCollectQueryData(self.query)
        result = {}
        for key, counter in self.counters.items():
            value = VALUE()
            status = self.dll.PdhGetFormattedCounterValue(counter, 0x200, None, ctypes.byref(value))
            result[key] = value.value if status == 0 and value.status in (0, 1) else None
        return result

    def close(self):
        self.dll.PdhCloseQuery(self.query)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--interval', type=float, default=10)
    parser.add_argument('--owner-pid', type=int, required=True)
    parser.add_argument('--prioritize-owned-mplus', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.interval <= 60 or not args.interval <= args.duration <= 86400:
        parser.error('Require 1<=interval<=60 and interval<=duration<=86400')
    owner = psutil.Process(args.owner_pid)
    identity = (owner.pid, owner.create_time())
    if owner.name().lower() not in {'rsession-utf8.exe', 'rsession.exe', 'rterm.exe'}:
        parser.error('Owner must be the assigned R process')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # 独占新日志，禁止覆盖上次监测证据。
    stream = args.output.open('x', encoding='utf8')
    restored = {}
    previous = {}
    paging = None
    def emit(row):
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        stream.flush()
    try:
        paging = Paging()
        emit(dict(event='start', time=time.time(), owner=identity, counter_errors=paging.errors,
                  submission=False, memory_admission_overridden=False))
        psutil.cpu_percent()
        stop = time.monotonic() + args.duration
        while time.monotonic() < stop:
            time.sleep(min(args.interval, max(0, stop-time.monotonic())))
            if not owner.is_running() or owner.create_time() != identity[1]:
                emit(dict(event='owner_exited')); break
            owned = {(p.pid,p.create_time()) for p in verified_descendants(owner,names={'mplus.exe'})}
            row = snapshot()
            row.update(event='sample', cpu_percent=psutil.cpu_percent(), paging=paging.read(),
                       disk_free_gib=psutil.disk_usage(str(args.output.parent)).free/2**30, models=[])
            for p in psutil.process_iter(['name']):
                if (p.info['name'] or '').lower() != 'mplus.exe':
                    continue
                try:
                    key = (p.pid, p.create_time())
                    mem = p.memory_info()
                    cpu = sum(p.cpu_times()[:2])
                    now = time.monotonic()
                    old = previous.get(key)
                    model = dict(pid=p.pid, created=key[1], owned=key in owned,
                                 rss_mib=mem.rss/2**20, private_mib=getattr(mem,'private',0)/2**20,
                                 cpu_core_percent=100*(cpu-old[0])/(now-old[1]) if old else None,
                                 io=p.io_counters()._asdict(), priority=p.nice())
                    previous[key] = (cpu, now)
                    if args.prioritize_owned_mplus and model['owned'] and key not in restored:
                        if not is_verified_descendant(p,dict(pid=identity[0],created=identity[1])):
                            model['owned']=False
                            row['models'].append(model)
                            continue
                        # 不提高原来已高于AboveNormal的优先级；绝不用Realtime。
                        if p.nice() in {psutil.IDLE_PRIORITY_CLASS, psutil.BELOW_NORMAL_PRIORITY_CLASS, psutil.NORMAL_PRIORITY_CLASS}:
                            restored[key] = p.nice()
                            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
                            emit(dict(event='priority_changed', pid=p.pid, created=key[1], original=restored[key]))
                    row['models'].append(model)
                except psutil.Error as exc:
                    emit(dict(event='process_access_error', pid=p.pid, error=type(exc).__name__))
            emit(row)
    finally:
        for (pid, created), original in restored.items():
            try:
                p = psutil.Process(pid)
                if p.create_time() == created and p.nice() == psutil.ABOVE_NORMAL_PRIORITY_CLASS:
                    p.nice(original)
                    emit(dict(event='priority_restored', pid=pid, original=original))
            except psutil.Error as exc:
                emit(dict(event='priority_restore_status', pid=pid, status=type(exc).__name__))
        if paging:
            paging.close()
        emit(dict(event='end', time=time.time(), monitor_private_mib=getattr(psutil.Process().memory_info(),'private',0)/2**20))
        stream.close()
    print(json.dumps(dict(receipt=str(args.output), owner=identity, submitted_models=0)))


if __name__ == '__main__':
    main()
