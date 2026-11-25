"""合成 guardian 退出顺序回归；不创建进程、不等待真实时钟。"""
from pathlib import Path
import sys
import unittest
from unittest import mock

import psutil

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts"
sys.path.insert(0, str(SCRIPTS))
import durable_mplus_worker as worker


class GuardianObservation:
    """在等待超时与调用者继续之间显式切换内核观察状态。"""
    pid = 12345

    def __init__(self, transition):
        self.transition = transition
        self.state = "running"
        self.waits = []

    def create_time(self):
        return 1.0

    def is_running(self):
        if self.state == "gone":
            raise psutil.NoSuchProcess(self.pid)
        return True

    def status(self):
        if self.state == "unreadable":
            raise psutil.AccessDenied(self.pid)
        return {"running": psutil.STATUS_RUNNING, "zombie": psutil.STATUS_ZOMBIE,
                "dead": psutil.STATUS_DEAD}[self.state]

    def cmdline(self):
        raise psutil.AccessDenied(self.pid)

    def wait(self, timeout):
        self.waits.append(timeout)
        if timeout == .2:
            self.state = self.transition
        elif timeout != 0:
            raise AssertionError("Unexpected wait budget")
        # Windows 的零等待探针也交给真实 process_finished 检查终态。
        raise psutil.TimeoutExpired(timeout, self.pid)


class GuardianExitObservationTests(unittest.TestCase):
    def observe(self, process):
        claim = {"pid": process.pid, "created": 1.0, "exe": "synthetic-python",
                 "host": worker.host()}
        with mock.patch.object(worker.psutil, "Process", return_value=process), \
                mock.patch.object(worker.time, "sleep", side_effect=AssertionError("No sleeps")):
            return worker.live_guardian(claim, Path("synthetic-work"), "synthetic-member")

    def test_exit_after_wait_timeout_is_reobserved(self):
        for transition in ("gone", "zombie", "dead"):
            with self.subTest(transition=transition):
                process = GuardianObservation(transition)
                self.assertFalse(self.observe(process))
                self.assertEqual([t for t in process.waits if t != 0], [.2])

    def test_still_live_after_wait_timeout_holds(self):
        process = GuardianObservation("running")
        with self.assertRaisesRegex(worker.Rejected, "Guardian process is unreadable"):
            self.observe(process)
        self.assertEqual([t for t in process.waits if t != 0], [.2])

    def test_unreadable_terminal_probe_after_timeout_holds(self):
        process = GuardianObservation("unreadable")
        with self.assertRaisesRegex(worker.Rejected, "Guardian process is unreadable"):
            self.observe(process)
        self.assertEqual([t for t in process.waits if t != 0], [.2])

    def test_reused_pid_does_not_match_original_guardian(self):
        original = GuardianObservation("running")
        replacement = mock.Mock()
        replacement.create_time.return_value = 2.0
        claim = {"pid": original.pid, "created": 1.0, "exe": "synthetic-python",
                 "host": worker.host()}
        with mock.patch.object(worker.psutil, "Process", side_effect=[original, replacement]):
            self.assertFalse(worker.live_guardian(claim, Path("synthetic-work"), "synthetic-member"))
        replacement.wait.assert_not_called()
        replacement.cmdline.assert_not_called()


if __name__ == "__main__":
    unittest.main()
