"""真实 SQLite 读锁验证首次 WAL 初始化；只使用独占临时数据库。"""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "skills/mplusautomation-guide/scripts/mplus_queue.py"
SPEC = importlib.util.spec_from_file_location("queue_wal_startup", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QueueWalStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="queue-wal-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.connect = sqlite3.connect
        self.reader = self.connect(self.root / "queue.sqlite", isolation_level=None)
        self.addCleanup(self.reader.close)
        self.reader.execute("CREATE TABLE fixture(value INTEGER)")
        self.reader.execute("INSERT INTO fixture VALUES(1)")
        self.reader.execute("BEGIN")
        self.reader.execute("SELECT * FROM fixture").fetchall()
        self.connections = []

    def connect_immediate(self, *args, **kwargs):
        # 真正的 SQLITE_BUSY；零等待让测试覆盖 journal_mode 的即时拒绝分支。
        kwargs["timeout"] = 0
        connection = self.connect(*args, **kwargs)
        self.connections.append(connection)
        return connection

    def test_initialization_waits_for_original_reader_then_succeeds(self):
        busy_seen = threading.Event()

        class ObservedConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                try:
                    return super().execute(sql, parameters)
                except sqlite3.OperationalError as exc:
                    if sql == "PRAGMA journal_mode=WAL" and str(exc) == "database is locked":
                        busy_seen.set()
                    raise

        def connect(*args, **kwargs):
            return self.connect_immediate(*args, factory=ObservedConnection, **kwargs)

        def initialize():
            try:
                queue = MODULE.Queue(self.root)
                return (queue.get("limit"), queue.get("cap"),
                        queue.db.execute("PRAGMA journal_mode").fetchone()[0],
                        queue.db.execute("PRAGMA busy_timeout").fetchone()[0])
            finally:
                for connection in self.connections:
                    connection.close()

        with patch.object(MODULE.sqlite3, "connect", connect), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(initialize)
            try:
                self.assertTrue(busy_seen.wait(5), "WAL initialization never observed the real reader lock")
                self.assertFalse(future.done(), "Initialization abandoned the recoverable reader lock")
            finally:
                self.reader.rollback()
            self.assertEqual(future.result(timeout=5), (1, 3, "wal", 30000))

    def test_busy_deadline_preserves_error_and_closes_connection(self):
        with patch.object(MODULE.sqlite3, "connect", self.connect_immediate), \
                patch.object(MODULE.time, "monotonic", side_effect=[0, 31]), \
                patch.object(MODULE.time, "sleep") as sleep:
            with self.assertRaisesRegex(sqlite3.OperationalError, "database is locked"):
                MODULE.Queue(self.root)
        sleep.assert_not_called()
        self.assertEqual(len(self.connections), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            self.connections[0].execute("SELECT 1")

    def test_nonbusy_failure_is_not_retried_and_closes_connection(self):
        self.reader.rollback()

        class FailedConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                if sql == "PRAGMA journal_mode=WAL":
                    raise sqlite3.OperationalError("disk I/O error")
                return super().execute(sql, parameters)

        def connect(*args, **kwargs):
            return self.connect_immediate(*args, factory=FailedConnection, **kwargs)

        with patch.object(MODULE.sqlite3, "connect", connect), patch.object(MODULE.time, "sleep") as sleep:
            with self.assertRaisesRegex(sqlite3.OperationalError, "disk I/O error"):
                MODULE.Queue(self.root)
        sleep.assert_not_called()
        self.assertEqual(len(self.connections), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            self.connections[0].execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
