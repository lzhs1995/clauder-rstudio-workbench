"""Bounded local monitoring support. Never starts or kills statistical jobs."""
import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil


@contextlib.contextmanager
def singleton(path):
    """由内核释放锁；进程崩溃后的旧文件不代表仍持锁。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    if path.stat().st_size == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    locked = False
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def append_bounded(path, text, limit=8 * 1024**2, backups=3):
    """仅轮转明确指定的运行日志，不触碰模型输入或输出。"""
    path = Path(path)
    encoded = text.encode('utf-8')
    if len(encoded) > limit:
        raise ValueError('One log record exceeds rotation limit')
    if path.exists() and path.stat().st_size + len(encoded) > limit:
        for index in range(backups, 1, -1):
            older = path.with_name(path.name + f'.{index - 1}')
            if older.exists():
                os.replace(older, path.with_name(path.name + f'.{index}'))
        os.replace(path, path.with_name(path.name + '.1'))
    with path.open('ab') as handle:
        handle.write(encoded)


def log_error(path, message):
    # ENOSPC 时错误日志也可能写不出，不能让报告错误再次杀死监控。
    try:
        append_bounded(path, dt.datetime.now(dt.timezone.utc).isoformat() + ' ' + message + '\n')
        return True
    except OSError:
        return False


def matches_script(process, script):
    """精确匹配脚本参数与目录，排除内联诊断自身。"""
    command = process.cmdline()
    if '-c' in command or len(command) < 2:
        return False
    for arg in command[1:]:
        if arg.startswith('-'):
            continue
        candidate = Path(arg)
        if not candidate.is_absolute():
            candidate = Path(process.cwd()) / candidate
        if candidate.resolve() == Path(script).resolve():
            return True
    return False


def script_processes(script):
    matches = []
    for process in psutil.process_iter():
        if process.pid == os.getpid():
            continue
        try:
            if process.name().lower().startswith('python') and matches_script(process, script):
                matches.append(dict(pid=process.pid, created=process.create_time()))
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            # 身份未知时停止恢复判断，不冒险启动第二实例。
            raise
    return matches


def supervise(root, script, interval=15):
    from mplus_queue import atomic_json
    root, script = Path(root).resolve(), Path(script).resolve()
    evidence = root / 'evidence'
    stop = root / 'stop_monitor_supervisor'
    last_restart = 0.
    retries = 0
    child = None
    with singleton(evidence / 'monitor_supervisor.lock'):
        while not stop.exists():
            try:
                now = time.time()
                matches = script_processes(script)
                free = psutil.disk_usage(str(root)).free / 2**30
                report = evidence / 'PROGRESS.md'
                age = now - report.stat().st_mtime if report.exists() else None
                action = 'observing'
                if len(matches) > 1:
                    action = 'duplicate_monitor_requires_review'
                elif matches and (age is None or age > 120):
                    action = 'live_monitor_stale_requires_review'
                elif not matches:
                    if (root / 'stop_monitor').exists():
                        action = 'operator_stop'
                    elif free < .5:
                        action = 'disk_wait'
                    elif now - last_restart < min(300, 15 * 2**min(retries, 5)):
                        action = 'restart_backoff'
                    else:
                        child = subprocess.Popen([sys.executable, '-X', 'utf8', str(script)],
                            cwd=str(script.parent), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        last_restart = now
                        retries += 1
                        action = 'monitor_restarted'
                elif age is not None and age <= 120:
                    retries = 0
                if child is not None:
                    child.poll()
                atomic_json(evidence / 'monitor_supervisor.json', dict(
                    updated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    pid=os.getpid(), created=psutil.Process().create_time(),
                    monitor=matches, monitor_report_age_seconds=age,
                    action=action, disk_free_gib=free, restart_attempts=retries,
                    stops_or_submits_models=False))
            except (OSError, psutil.Error, ValueError) as exc:
                log_error(evidence / 'monitor_supervisor_errors.log', repr(exc))
            time.sleep(interval)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--monitor', required=True)
    parser.add_argument('--interval', type=float, default=15)
    args = parser.parse_args()
    if args.interval < 1:
        parser.error('--interval must be at least one second')
    supervise(args.root, args.monitor, args.interval)
