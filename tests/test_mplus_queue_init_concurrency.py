from __future__ import annotations

import contextlib
import importlib.util
import inspect
import io
import json
import multiprocessing
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "mplusautomation-guide" / "scripts" / "mplus_queue.py"
WAIT_SECONDS = 20


def _settings(connection) -> dict:
    return {key: json.loads(value) for key, value in connection.execute("SELECT key, value FROM settings")}


def _init_worker(root: str, checkpoint: str | None, channel) -> None:
    # 每个 spawn 子进程执行真实 init 入口，仅在测试侧协调语句边界和 SQLite 调用。
    spec = importlib.util.spec_from_file_location("mplus_queue_init_concurrency_worker", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    original_connect = sqlite3.connect
    connections = []
    paused = False
    lines, first_line = inspect.getsourcelines(module.Queue.__init__)
    checkpoint_statement = ('config = self.root / "config.json"' if checkpoint == "after_defaults"
                            else 'self.set("limit", initial)')
    checkpoint_line = max(first_line + offset for offset, line in enumerate(lines)
                          if line.strip() == checkpoint_statement)

    class CoordinatedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            statement = " ".join(sql.upper().split())
            if checkpoint is None and statement == "BEGIN IMMEDIATE":
                # 到达真实写事务请求后才通知父进程；不修改 SQLite 的等待、重试或隔离语义。
                channel.send({"kind": "begin_attempt"})
            return super().execute(sql, parameters)

    def trace(frame, event, argument):
        nonlocal paused
        if (checkpoint is not None and not paused and event == "line"
                and frame.f_code is module.Queue.__init__.__code__
                and frame.f_lineno == checkpoint_line):
            # 在完整默认值循环／cap调用之后停，提前插入的COMMIT也会被隔离断言抓住。
            paused = True
            connection = frame.f_locals["self"].db
            channel.send({"kind": "paused", "in_transaction": connection.in_transaction,
                          "settings": _settings(connection)})
            if not channel.poll(WAIT_SECONDS) or channel.recv() != "release":
                raise TimeoutError("Parent did not release the initialization checkpoint")
        return trace

    def connect(*args, **kwargs):
        connection = original_connect(*args, factory=CoordinatedConnection, **kwargs)
        connections.append(connection)
        return connection

    try:
        output = io.StringIO()
        with mock.patch.object(module.sqlite3, "connect", connect), \
                mock.patch.object(sys, "argv", [str(SCRIPT), "init", "--root", root]), \
                contextlib.redirect_stdout(output):
            sys.settrace(trace)
            try:
                module.main()
            finally:
                sys.settrace(None)
        channel.send({"kind": "response", "result": json.loads(output.getvalue())})
    except BaseException as exc:
        channel.send({"kind": "error", "type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        for connection in connections:
            connection.close()
        channel.close()


class QueueInitConcurrencyTest(unittest.TestCase):
    def _receive(self, channel, expected: str) -> dict:
        self.assertTrue(channel.poll(WAIT_SECONDS), f"Missing worker event: {expected}")
        message = channel.recv()
        self.assertEqual(message["kind"], expected, message)
        return message

    def _check_coordinated_initializers(self, checkpoint: str) -> None:
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(
                json.dumps({"parallel_cap": 2, "initial_parallel_limit": 2}), encoding="utf-8")
            first_parent, first_child = context.Pipe()
            second_parent, second_child = context.Pipe()
            first = context.Process(target=_init_worker, args=(str(root), checkpoint, first_child))
            second = context.Process(target=_init_worker, args=(str(root), None, second_child))
            started = []
            try:
                first.start()
                started.append(first)
                first_child.close()
                pause = self._receive(first_parent, "paused")
                self.assertTrue(pause["in_transaction"])
                expected_cap = 3 if checkpoint == "after_defaults" else 2
                self.assertEqual((pause["settings"]["limit"], pause["settings"]["cap"]),
                                 (1, expected_cap))
                second.start()
                started.append(second)
                second_child.close()
                self._receive(second_parent, "begin_attempt")
                # 独立连接必须看不到未提交值，且即时写锁探针必须得到 SQLITE_BUSY。
                # 这与次进程已到达 BEGIN 的信号共同证明隔离，不靠 sleep 或超时猜测竞态。
                with contextlib.closing(sqlite3.connect(root / "queue.sqlite", timeout=0,
                                                       isolation_level=None)) as observer:
                    self.assertEqual(_settings(observer), {})
                    with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                        observer.execute("BEGIN IMMEDIATE")
                self.assertFalse(second_parent.poll(), "Second init returned before the first committed")
                first_parent.send("release")
                first_result = self._receive(first_parent, "response")["result"]
                second_result = self._receive(second_parent, "response")["result"]
                for result in (first_result, second_result):
                    self.assertEqual((result["limit"], result["cap"]), (2, 2))
                for process in started:
                    process.join(WAIT_SECONDS)
                    self.assertEqual(process.exitcode, 0)
                with contextlib.closing(sqlite3.connect(root / "queue.sqlite")) as observer:
                    final = _settings(observer)
                    self.assertEqual((final["limit"], final["cap"]), (2, 2))
            finally:
                # 失败时释放本测试的首进程，并仅回收本测试自己启动的子进程。
                with contextlib.suppress(BrokenPipeError, EOFError, OSError):
                    first_parent.send("release")
                for process in started:
                    process.join(WAIT_SECONDS)
                    if process.is_alive():
                        process.terminate()
                        process.join(WAIT_SECONDS)
                for channel in (first_parent, first_child, second_parent, second_child):
                    channel.close()

    def test_second_init_cannot_observe_defaults_before_declaration(self) -> None:
        self._check_coordinated_initializers("after_defaults")

    def test_second_init_cannot_observe_cap_before_limit(self) -> None:
        self._check_coordinated_initializers("after_cap")


if __name__ == "__main__":
    unittest.main()
