from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "mplusautomation-guide" / "scripts" / "mplus_queue.py"
SPEC = importlib.util.spec_from_file_location("mplus_queue_byte_autoscale_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _snap(at: float, percent: float, available: float, commit: float | None = 6.0, **extra) -> dict:
    # 16 GiB Windows 主机：百分比高于 85%，但字节余量仍可能足够再起一个 Mplus
    snap = dict(at=at, memory_percent=percent, available_gib=available, total_gib=15.6,
                cpu_percent=20, disk_free_gib=50, host_memory_unverified=False)
    if commit is not None:
        snap["free_virtual_gib"] = commit
    snap.update(extra)
    return snap


def _ticks(q, n: int, **kw) -> None:
    for i in range(n):
        q.tick(_snap(1000 + 30 * (i + 1), **kw))


class ByteAutoscaleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.queues = []

    def tearDown(self) -> None:
        for q in self.queues:
            q.db.close()
        self._tmp.cleanup()

    def _queue(self, name: str, settings: dict | None = None):
        root = self.tmp / name
        root.mkdir(parents=True, exist_ok=True)
        if settings is not None:
            (root / "config.json").write_text(json.dumps(settings), encoding="utf-8")
        q = MODULE.Queue(root)
        self.queues.append(q)
        return q

    def test_high_percent_with_byte_headroom_adds_slot(self) -> None:
        q = self._queue("q")
        self.assertEqual(q.get("limit"), 1)
        _ticks(q, 5, percent=90, available=4.0)
        self.assertEqual(q.get("limit"), 2)

    def test_high_percent_without_byte_headroom_stays(self) -> None:
        q = self._queue("q")
        # 1.9 - 0.5 < 1.5：不够再容纳一步
        _ticks(q, 10, percent=90, available=1.9)
        self.assertEqual(q.get("limit"), 1)

    def test_running_reservations_are_subtracted(self) -> None:
        q = self._queue("q")
        q.db.execute("INSERT INTO tasks(id,payload,status) VALUES(?,?,?)",
                     ("t1", json.dumps({"memory_gib": 2.5}), "running"))
        # 4.0 - 2.5 - 0.5 < 1.5
        _ticks(q, 10, percent=90, available=4.0)
        self.assertEqual(q.get("limit"), 1)

    def test_commit_headroom_blocks_when_configured(self) -> None:
        policy = {"resource_policy": {"commit_reserve_gib": 1.5}}
        q = self._queue("q", policy)
        _ticks(q, 10, percent=90, available=6.0, commit=1.8)
        self.assertEqual(q.get("limit"), 1)
        q2 = self._queue("q2", policy)
        _ticks(q2, 5, percent=90, available=6.0, commit=None)
        self.assertEqual(q2.get("limit"), 1)

    def test_commit_headroom_also_checked_on_percent_path(self) -> None:
        q = self._queue("q", {"resource_policy": {"commit_reserve_gib": 2.0}})
        _ticks(q, 10, percent=70, available=6.0, commit=0.3)
        self.assertEqual(q.get("limit"), 1)

    def test_percent_path_unchanged(self) -> None:
        q = self._queue("q")
        _ticks(q, 5, percent=50, available=1.0)
        self.assertEqual(q.get("limit"), 2)

    def test_unverified_host_never_counts_as_healthy(self) -> None:
        for percent in (40.0, 90.0):
            with self.subTest(percent=percent):
                snap = _snap(0, percent=percent, available=8.0, host_memory_unverified=True)
                self.assertIs(MODULE.scale_up_memory_ok(snap, 0.0), False)

    def test_unverified_cpu_or_disk_blocks_scale_up(self) -> None:
        for flag in ("host_cpu_unverified", "host_disk_unverified"):
            with self.subTest(flag=flag):
                q = self._queue(flag)
                _ticks(q, 10, percent=50, available=8.0, **{flag: True})
                self.assertEqual(q.get("limit"), 1)

    def test_plain_queue_can_declare_initial_limit_and_cap(self) -> None:
        q = self._queue("q", {"parallel_cap": 4, "initial_parallel_limit": 3})
        self.assertEqual((q.get("limit"), q.get("cap")), (3, 4))
        _ticks(q, 5, percent=90, available=8.0)
        self.assertEqual(q.get("limit"), 4)
        _ticks(q, 10, percent=90, available=8.0)
        self.assertEqual(q.get("limit"), 4)

    def test_declared_limits_apply_only_to_new_queue(self) -> None:
        # init/enable 只写 settings；没有 events 的既有队列也必须保留原值
        for with_event in (False, True):
            with self.subTest(with_event=with_event):
                name = f"q{int(with_event)}"
                q = self._queue(name)
                q.set("enabled", True)
                if with_event:
                    q.event("resources", {})
                q2 = self._queue(name, {"parallel_cap": 6, "initial_parallel_limit": 4})
                self.assertEqual((q2.get("limit"), q2.get("cap")), (1, 3))

    def test_cli_status_does_not_rewrite_existing_queue(self) -> None:
        # 正式 CLI：init → enable → 改 config → status，默认起点与已声明起点都保持原值
        for first, expected in ((None, (1, 3)), ({"parallel_cap": 2, "initial_parallel_limit": 2}, (2, 2))):
            with self.subTest(first=first):
                root = self.tmp / f"cli{expected[1]}"
                root.mkdir()
                if first is not None:
                    (root / "config.json").write_text(json.dumps(first), encoding="utf-8")
                for action in ("init", "enable"):
                    subprocess.run([sys.executable, str(SCRIPT), action, "--root", str(root)],
                                   check=True, capture_output=True)
                (root / "config.json").write_text(json.dumps({"parallel_cap": 4, "initial_parallel_limit": 3}),
                                                  encoding="utf-8")
                subprocess.run([sys.executable, str(SCRIPT), "status", "--root", str(root)],
                               check=True, capture_output=True)
                q = MODULE.Queue(root)
                self.queues.append(q)
                self.assertEqual((q.get("limit"), q.get("cap")), expected)

    def test_invalid_declared_limits_are_rejected(self) -> None:
        cases = [
            {"parallel_cap": 0},
            {"parallel_cap": 13},
            {"parallel_cap": 2, "initial_parallel_limit": 3},
            {"initial_parallel_limit": 0},
            {"parallel_cap": True},
            {"parallel_cap": 4, "initial_parallel_limit": 1.9},
            {"parallel_cap": "4"},
        ]
        for i, settings in enumerate(cases):
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    self._queue(f"bad{i}", settings)


if __name__ == "__main__":
    unittest.main()
