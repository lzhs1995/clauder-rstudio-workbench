"""初始化合成回归；所有数据库由测试临时目录独占，不启动模型。"""
from concurrent.futures import ThreadPoolExecutor
import contextlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

SCRIPT = Path(__file__).parents[1] / "skills/mplusautomation-guide/scripts/mplus_queue.py"
SPEC = importlib.util.spec_from_file_location("queue_init_candidate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QueueInitializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="queue-init-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.serial = 0

    def folder(self, settings=None):
        self.serial += 1
        root = self.root / str(self.serial)
        root.mkdir()
        if settings is not None:
            (root / "config.json").write_text(json.dumps(settings))
        return root

    def open(self, root):
        q = MODULE.Queue(root)
        self.addCleanup(q.db.close)
        return q

    def values(self, q):
        return tuple(q.get(k) for k in ("limit", "cap", "enabled"))

    def test_default_one_three_disabled(self):
        self.assertEqual(self.values(self.open(self.folder())), (1, 3, False))

    def test_declared_initial_and_cap(self):
        self.assertEqual(self.values(self.open(self.folder(
            {"parallel_cap": 4, "initial_parallel_limit": 3}))), (3, 4, False))

    def test_single_declaration_keeps_other_default(self):
        for config, expected in [({"parallel_cap": 5}, (1, 5, False)),
                                 ({"initial_parallel_limit": 2}, (2, 3, False))]:
            with self.subTest(config=config):
                self.assertEqual(self.values(self.open(self.folder(config))), expected)

    def test_processor_budget_boundary(self):
        q = self.open(self.folder({"resource_policy": {"processor_budget": 7},
                                  "parallel_cap": 7, "initial_parallel_limit": 7}))
        self.assertEqual(self.values(q), (7, 7, False))
        with self.assertRaises(ValueError):
            MODULE.Queue(self.folder({"resource_policy": {"processor_budget": 7},
                                      "parallel_cap": 8}))

    def test_invalid_declarations_rollback_and_release_connection(self):
        cases = [{"parallel_cap": 0}, {"parallel_cap": 13}, {"parallel_cap": True},
                 {"parallel_cap": "4"}, {"initial_parallel_limit": 1.9},
                 {"initial_parallel_limit": 0},
                 {"parallel_cap": 2, "initial_parallel_limit": 3}]
        for config in cases:
            with self.subTest(config=config):
                root = self.folder(config)
                for _ in range(2):
                    with self.assertRaises(ValueError):
                        MODULE.Queue(root)
                with contextlib.closing(sqlite3.connect(root / "queue.sqlite", timeout=1)) as db:
                    db.execute("BEGIN IMMEDIATE")
                    self.assertEqual(db.execute("SELECT count(*) FROM settings").fetchone()[0], 0)
                    db.rollback()
                (root / "config.json").write_text(json.dumps(
                    {"parallel_cap": 2, "initial_parallel_limit": 2}))
                self.assertEqual(self.values(self.open(root)), (2, 2, False))

    def test_malformed_json_rollback_then_corrected_first_init(self):
        root = self.folder()
        (root / "config.json").write_text('{"parallel_cap": 2,')
        for _ in range(2):
            with self.assertRaises(json.JSONDecodeError):
                MODULE.Queue(root)
        with contextlib.closing(sqlite3.connect(root / "queue.sqlite")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM settings").fetchone()[0], 0)
        (root / "config.json").write_text('{"parallel_cap": 4, "initial_parallel_limit": 2}')
        self.assertEqual(self.values(self.open(root)), (2, 4, False))

    def test_existing_ordinary_queue_not_migrated_with_or_without_events(self):
        for event in (False, True):
            with self.subTest(event=event):
                root = self.folder()
                q = self.open(root)
                q.set("limit", 2)
                q.set("cap", 5)
                q.set("enabled", True)
                if event:
                    q.event("fixture", {})
                before = list(q.db.execute("SELECT key,value FROM settings ORDER BY key"))
                before = [tuple(r) for r in before]
                (root / "config.json").write_text('{"parallel_cap": 6, "initial_parallel_limit": 4}')
                q2 = self.open(root)
                self.assertEqual(self.values(q2), (2, 5, True))
                self.assertEqual([tuple(r) for r in q2.db.execute(
                    "SELECT key,value FROM settings ORDER BY key")], before)

    def test_existing_malformed_config_preserves_prior_settings(self):
        root = self.folder({"parallel_cap": 4, "initial_parallel_limit": 2})
        q = self.open(root)
        before = [tuple(r) for r in q.db.execute("SELECT key,value FROM settings ORDER BY key")]
        (root / "config.json").write_text("{")
        with self.assertRaises(json.JSONDecodeError):
            MODULE.Queue(root)
        self.assertEqual([tuple(r) for r in q.db.execute(
            "SELECT key,value FROM settings ORDER BY key")], before)

    def test_apim_defaults_and_calibrated_one_two(self):
        for config, expected in [
                ({"apim_v2": True}, (1, 1, False)),
                ({"apim_v2": True, "parallel_cap": 2}, (1, 2, False)),
                ({"apim_v2": True, "parallel_cap": 2,
                  "initial_parallel_limit": 2, "calibrated": True}, (2, 2, False))]:
            with self.subTest(config=config):
                self.assertEqual(self.values(self.open(self.folder(config))), expected)

    def test_apim_invalid_cap_and_uncalibrated_two(self):
        for config in [
                {"apim_v2": True, "parallel_cap": 3},
                {"apim_v2": True, "parallel_cap": 2, "initial_parallel_limit": 2},
                {"apim_v2": True, "parallel_cap": 1, "initial_parallel_limit": 2,
                 "calibrated": True}]:
            with self.subTest(config=config):
                root = self.folder(config)
                with self.assertRaises(ValueError):
                    MODULE.Queue(root)
                with contextlib.closing(sqlite3.connect(root / "queue.sqlite")) as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM settings").fetchone()[0], 0)

    def test_apim_legacy_event_boundary_is_preserved(self):
        # 原APIM按events而非普通队列fresh_db判断；保留原语义，不静默迁移契约。
        for event in (False, True):
            root = self.folder({"apim_v2": True, "parallel_cap": 1})
            q = self.open(root)
            q.set("enabled", True)
            if event:
                q.event("fixture", {})
            (root / "config.json").write_text(json.dumps(
                {"apim_v2": True, "parallel_cap": 2, "initial_parallel_limit": 2,
                 "calibrated": True}))
            q2 = self.open(root)
            self.assertEqual(self.values(q2), (1, 1, True) if event else (2, 2, True))

    def concurrent_open(self, root, count=8):
        barrier = threading.Barrier(count, timeout=10)
        def work(_):
            barrier.wait()
            q = MODULE.Queue(root)
            try:
                return self.values(q), [tuple(r) for r in q.db.execute(
                    "SELECT key,value FROM settings ORDER BY key")]
            finally:
                q.db.close()
        with ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(work, range(count)))

    def test_concurrent_first_init_same_declaration(self):
        # 真正多连接在同一新目录并发，无预建数据库/串行warm-up。
        root = self.folder({"parallel_cap": 4, "initial_parallel_limit": 3})
        rows = self.concurrent_open(root)
        self.assertTrue(all(value == (3, 4, False) for value, _ in rows))
        self.assertTrue(all(settings == rows[0][1] for _, settings in rows))
        self.assertEqual(len(rows[0][1]), 7)
        self.assertEqual(json.loads(dict(rows[0][1])["autoscale_mode"]), "candidate_measured")

    def test_concurrent_default_first_init(self):
        rows = self.concurrent_open(self.folder())
        self.assertTrue(all(value == (1, 3, False) for value, _ in rows))

    def test_concurrent_failed_first_init_then_corrected(self):
        root = self.folder({"parallel_cap": 0})
        barrier = threading.Barrier(4, timeout=10)
        def invalid(_):
            barrier.wait()
            try:
                q = MODULE.Queue(root)
            except ValueError:
                return "INVALID"
            else:
                q.db.close()
                return "UNEXPECTED_SUCCESS"
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(invalid, range(4))), ["INVALID"] * 4)
        with contextlib.closing(sqlite3.connect(root / "queue.sqlite")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM settings").fetchone()[0], 0)
        (root / "config.json").write_text('{"parallel_cap": 4, "initial_parallel_limit": 2}')
        self.assertEqual(self.values(self.open(root)), (2, 4, False))

    def test_cli_failed_init_enable_and_existing_queue_preservation(self):
        bad = self.folder({"parallel_cap": 0})
        for action in ("init", "init", "enable"):
            call = subprocess.run([sys.executable, "-B", str(SCRIPT), action, "--root", str(bad)],
                                  capture_output=True, text=True, timeout=10)
            self.assertNotEqual(call.returncode, 0, (action, call.stdout, call.stderr))
        root = self.folder({"parallel_cap": 2, "initial_parallel_limit": 2})
        for action in ("init", "enable"):
            call = subprocess.run([sys.executable, "-B", str(SCRIPT), action, "--root", str(root)],
                                  capture_output=True, text=True, timeout=10)
            self.assertEqual(call.returncode, 0, call.stderr)
        (root / "config.json").write_text('{"parallel_cap": 6, "initial_parallel_limit": 4}')
        # 不运行status的主机资源采样；再次init已经覆盖有enabled的既有库入口。
        call = subprocess.run([sys.executable, "-B", str(SCRIPT), "init", "--root", str(root)],
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(call.returncode, 0, call.stderr)
        self.assertEqual(self.values(self.open(root)), (2, 2, True))


if __name__ == "__main__":
    unittest.main()
