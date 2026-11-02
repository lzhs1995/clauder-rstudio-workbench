"""APIM v2 文件边界、不可变输入快照与宿主机资源预约。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inside(path, root):
    p, r = os.path.normcase(str(Path(path).resolve())), os.path.normcase(str(Path(root).resolve()))
    try:
        return os.path.commonpath([p, r]) == r
    except ValueError:  # Windows不同盘符不重叠。
        return False


def check_paths(root, sources, protected=()):
    root = Path(root).resolve()
    for source in sources:
        p = Path(source).resolve(strict=True)
        if inside(p, root) or inside(root, p.parent):
            raise ValueError('Run root and source directory must be disjoint: ' + str(p))
    for source in protected:
        if inside(root, source) or inside(source, root):
            raise ValueError('Run root overlaps a protected root')
    if root.exists():
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                entry = Path(directory) / name
                if entry.is_symlink() or (hasattr(entry, 'is_junction') and entry.is_junction()):
                    raise ValueError('Run tree contains an alias/reparse entry: ' + str(entry))
    return {'root': str(root), 'sources': [{'path': str(Path(p).resolve()), 'sha256': sha256(p)} for p in sources]}


def snapshot(root, sources, protected=()):
    result = check_paths(root, sources, protected)
    dst = Path(root) / 'source_snapshot'
    dst.mkdir(parents=True, exist_ok=True)
    for i, entry in enumerate(result['sources']):
        target = dst / ('source_%03d' % (i + 1) + Path(entry['path']).suffix)
        if target.exists():
            if sha256(target) != entry['sha256']:
                raise ValueError('Frozen source changed; use a new run root')
        else:
            with open(entry['path'], 'rb') as src, target.open('xb') as out:
                shutil.copyfileobj(src, out)
            if sha256(target) != entry['sha256'] or sha256(entry['path']) != entry['sha256']:
                raise ValueError('Source changed during snapshot')
            target.chmod(0o444)
        entry['snapshot'] = str(target)
    return result


class HostReservations:
    """只协调参与此协议的调度器；不接管外部分析进程。"""
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS reservations (key TEXT PRIMARY KEY, pid INTEGER, created REAL, gib REAL, processors INTEGER, heartbeat REAL)')

    def acquire(self, key, pid, created, gib, processors, available, commit, reserve, commit_reserve, processor_budget):
        import psutil
        self.db.execute('BEGIN IMMEDIATE')
        try:
            rows = self.db.execute('SELECT * FROM reservations').fetchall()
            alive = []
            for row in rows:
                try:
                    p = psutil.Process(row[1])
                    valid = abs(p.create_time() - row[2]) < .001 and p.is_running()
                except psutil.NoSuchProcess:
                    valid = False
                except psutil.AccessDenied:
                    valid = True  # 无法核实的预约不能擅自回收。
                if not valid:
                    # 父进程退出不证明Mplus子进程也退出；保留预约供显式核对。
                    raise ValueError('Orphan reservation requires process/output reconciliation: ' + row[0])
                elif row[0] != key:
                    alive.append(row)
            old = self.db.execute('SELECT pid,created FROM reservations WHERE key=?', (key,)).fetchone()
            if old is not None and (old[0] != pid or abs(old[1] - created) >= .001):
                raise ValueError('Reservation owner mismatch')
            total = sum(r[3] for r in alive)
            if available - total - gib < reserve or commit - total - gib < commit_reserve:
                result = {'admitted': False, 'reason': 'host_memory_reservation'}
            elif sum(r[4] for r in alive) + processors > processor_budget:
                result = {'admitted': False, 'reason': 'host_processor_reservation'}
            else:
                self.db.execute('INSERT OR REPLACE INTO reservations VALUES (?,?,?,?,?,?)', (key, pid, created, gib, processors, time.time()))
                result = {'admitted': True, 'reserved_gib': gib, 'other_reserved_gib': total}
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def release(self, key, pid, created):
        self.db.execute('DELETE FROM reservations WHERE key=? AND pid=? AND ABS(created-?)<.001', (key, pid, created))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['check', 'snapshot', 'acquire', 'release'])
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--request')
    source.add_argument('--payload')
    args = ap.parse_args()
    request = json.loads(args.payload if args.payload is not None else Path(args.request).read_text(encoding='utf-8'))
    if args.action in ('check', 'snapshot'):
        result = (check_paths if args.action == 'check' else snapshot)(**request)
    else:
        registry = HostReservations(request.pop('registry'))
        result = getattr(registry, args.action)(**request)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
