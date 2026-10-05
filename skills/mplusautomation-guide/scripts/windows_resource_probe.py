"""Windows 原生资源采样；只读，区分驻留、提交、分页和模型并行度。"""
import argparse
from collections import defaultdict
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time

import psutil


class PerformanceInfo(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD)] + [
        (n, ctypes.c_size_t) for n in (
            'CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal',
            'PhysicalAvailable', 'SystemCache', 'KernelTotal', 'KernelPaged',
            'KernelNonpaged', 'PageSize')
    ] + [(n, wintypes.DWORD) for n in ('HandleCount', 'ProcessCount', 'ThreadCount')]


def host_snapshot():
    info = PerformanceInfo()
    info.cb = ctypes.sizeof(info)
    ok = ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb)
    perf = {n: getattr(info, n) * info.PageSize for n in (
        'CommitTotal', 'CommitLimit', 'PhysicalAvailable', 'SystemCache',
        'KernelPaged', 'KernelNonpaged')} if ok else {}
    return {'utc': datetime.now(timezone.utc).isoformat(),
            'memory': psutil.virtual_memory()._asdict(), 'performance_bytes': perf,
            'disk_free_bytes': psutil.disk_usage(os.environ.get('SystemDrive', 'C:') + '/').free}


class PdhCounters:
    """英文计数器路径在中文 Windows 上也可用；失败明确留证。"""
    PATHS = {
        'pages_input_per_sec': r'\Memory\Pages Input/sec',
        'page_reads_per_sec': r'\Memory\Page Reads/sec',
        'page_writes_per_sec': r'\Memory\Page Writes/sec',
        'pages_output_per_sec': r'\Memory\Pages Output/sec',
        'disk_read_latency_sec': r'\PhysicalDisk(_Total)\Avg. Disk sec/Read',
        'disk_write_latency_sec': r'\PhysicalDisk(_Total)\Avg. Disk sec/Write',
        'disk_queue': r'\PhysicalDisk(_Total)\Avg. Disk Queue Length',
        'cpu_queue': r'\System\Processor Queue Length',
    }

    class Value(ctypes.Structure):
        _fields_ = [('status', wintypes.DWORD), ('value', ctypes.c_double)]

    def __init__(self):
        self.dll = ctypes.WinDLL('pdh')
        self.dll.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
        self.dll.PdhAddEnglishCounterW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
        self.dll.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
        self.dll.PdhGetFormattedCounterValue.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(self.Value)]
        self.dll.PdhCloseQuery.argtypes = [wintypes.HANDLE]
        self.query = wintypes.HANDLE()
        self.errors = {}
        self.counters = {}
        status = self.dll.PdhOpenQueryW(None, 0, ctypes.byref(self.query))
        if status:
            self.errors['open'] = status
            return
        for name, path in self.PATHS.items():
            handle = wintypes.HANDLE()
            status = self.dll.PdhAddEnglishCounterW(self.query, path, 0, ctypes.byref(handle))
            if status:
                self.errors[name] = status
            else:
                self.counters[name] = handle

    def collect(self):
        status = self.dll.PdhCollectQueryData(self.query)
        values = {}
        if status:
            return {'collect_error': status}
        for name, handle in self.counters.items():
            value = self.Value()
            status = self.dll.PdhGetFormattedCounterValue(handle, 0x200, None, ctypes.byref(value))
            values[name] = value.value if not status and value.status in (0, 1) else None
        return values

    def close(self):
        if self.query:
            self.dll.PdhCloseQuery(self.query)


def process_snapshot():
    rows = {}
    for p in psutil.process_iter():
        try:
            # 不逐个读取 cmdline/exe/environ，避免探测本身触发大量换页或泄露凭据。
            with p.oneshot():
                m = p.memory_info()
                cpu = p.cpu_times()
                # Windows 的 ppid()/num_threads() 可能各自枚举全机进程；只对 Mplus 取详情。
                rows[p.pid] = {'pid': p.pid, 'name': p.name(),
                               'create_time': p.create_time(), 'rss': m.rss,
                               'private': getattr(m, 'private', m.vms),
                               'cpu_seconds': cpu.user + cpu.system,
                               'sample_monotonic': time.monotonic()}
        except psutil.Error:
            continue
    return rows


def mplus_details(row):
    p = psutil.Process(row['pid'])
    details = dict(row)
    try:
        if p.create_time() != row['create_time']:
            return dict(details, identity_changed=True)
        details['ppid'] = p.ppid()
        details['threads'] = p.num_threads()
        details['priority'] = int(p.nice())
        details['affinity'] = p.cpu_affinity()
        details['cwd'] = p.cwd()
        inputs = [a for a in p.cmdline() if a.lower().endswith('.inp')]
        if inputs:
            inp = Path(details['cwd']) / inputs[-1]
            details['input'] = str(inp)
            if inp.is_file():
                source = inp.read_text(encoding='utf-8', errors='replace')
                clean = re.sub(r'!.*', '', source)
                details['analysis_settings'] = re.findall(
                    r'(?im)\b(?:PROCESSORS|STARTS|BOOTSTRAP|ESTIMATOR|TYPE|INTEGRATION|ALGORITHM|STITERATIONS)\s*=\s*[^;]+;', clean)
                out = inp.with_suffix('.out')
                if out.is_file():
                    details['output_bytes'] = out.stat().st_size
                    details['output_mtime'] = out.stat().st_mtime
    except (psutil.Error, OSError) as e:
        details['detail_error'] = str(e)
    return details


def probe(seconds=10):
    print('stage=host_snapshot', flush=True)
    before = host_snapshot()
    counters = PdhCounters()
    print('stage=process_census', flush=True)
    census_start = time.monotonic()
    first = process_snapshot()
    first_census_seconds = time.monotonic() - census_start
    counters.collect()
    psutil.cpu_percent(percpu=True)
    disk_before = psutil.disk_io_counters()
    start = time.monotonic()
    print('stage=sampling', flush=True)
    samples = []
    cpu_samples = []
    for _ in range(seconds):
        time.sleep(1)
        samples.append(counters.collect())
        cpu_samples.append(psutil.cpu_percent(percpu=True))
    end = time.monotonic()
    disk_after = psutil.disk_io_counters()
    census_start = time.monotonic()
    second = process_snapshot()
    second_census_seconds = time.monotonic() - census_start
    # 进程枚举也可能耗时，CPU 差值必须使用包含第二次枚举的实际间隔。
    elapsed = time.monotonic() - start
    pdh_errors = counters.errors
    counters.close()
    rows = []
    groups = defaultdict(lambda: {'count': 0, 'rss': 0, 'private': 0, 'cpu_cores': 0.0})
    for pid, row in second.items():
        old = first.get(pid)
        row['cpu_cores'] = (max(0, row['cpu_seconds'] - old['cpu_seconds']) /
                            max(0.001, row['sample_monotonic'] - old['sample_monotonic'])) if old and old['create_time'] == row['create_time'] else None
        group = groups[row['name']]
        group['count'] += 1
        group['rss'] += row['rss']
        group['private'] += row['private']
        group['cpu_cores'] += row['cpu_cores'] or 0.0
        rows.append(row)
    means = {k: sum(s[k] for s in samples if s.get(k) is not None) / len([s for s in samples if s.get(k) is not None])
             for k in counters.PATHS if any(s.get(k) is not None for s in samples)}
    mplus = [mplus_details(r) for r in rows if r['name'].lower() in ('mplus.exe', 'mplus')]
    return {'schema_version': 1, 'before': before, 'after': host_snapshot(),
            'logical_cpus': psutil.cpu_count(), 'physical_cores': psutil.cpu_count(logical=False),
            'sample_seconds': end-start, 'process_cpu_interval_seconds': elapsed,
            'census_seconds': {'first': first_census_seconds, 'second': second_census_seconds},
            'cpu_percent_per_logical_mean': [sum(v[i] for v in cpu_samples)/len(cpu_samples) for i in range(len(cpu_samples[0]))],
            'pdh_means': means, 'pdh_errors': pdh_errors,
            'disk_read_bytes_per_sec': (disk_after.read_bytes-disk_before.read_bytes)/(end-start),
            'disk_write_bytes_per_sec': (disk_after.write_bytes-disk_before.write_bytes)/(end-start),
            'groups': dict(groups), 'processes': rows, 'mplus': mplus,
            'limitations': 'Group RSS double-counts shared pages. Private commit is not physical RAM. Page reads include mapped files, not only pagefile. CPU cores are CPU seconds / wall seconds; 1.0 means one busy logical CPU. Shared-host deltas are observational, not controlled speedup.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    ap.add_argument('--seconds', type=int, default=10, choices=range(2, 61))
    args = ap.parse_args()
    if os.name != 'nt':
        ap.error('Run with native Windows Python; WSL memory does not measure host pressure.')
    report = probe(args.seconds)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'receipt': str(out), 'after': report['after'], 'pdh_means': report['pdh_means'],
                      'mplus': report['mplus'], 'top_rss': sorted(report['processes'], key=lambda r: r['rss'], reverse=True)[:12],
                      'top_cpu': sorted([r for r in report['processes'] if r['pid'] != 0], key=lambda r: r['cpu_cores'] or 0, reverse=True)[:8]}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
