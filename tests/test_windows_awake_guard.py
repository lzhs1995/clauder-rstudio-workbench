"""Exercise actual Windows request acquisition/release and owner identity."""
import json
import ctypes
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import durable_fixture_processes as fixture

SCRIPT = Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts/windows_awake_guard.py"


def wait_json(path, process, *, deadline=None):
    if deadline is None:
        deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            # Windows 读取允许删除共享；并发替换只在原期限内短暂重试。
            return fixture.read_fixture_json(path, deadline=deadline)
        except FileNotFoundError:
            pass
        assert process.poll() is None, "guard ended before receipt"
        time.sleep(max(0, min(0.05, deadline - time.monotonic())))
    raise AssertionError("guard did not write receipt")


def real_windows_lifecycle(tmp_path, finish):
    owner = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                             stdin=subprocess.PIPE)
    guard = None
    try:
        identity = {"pid": owner.pid, "created": psutil.Process(owner.pid).create_time()}
        owner_file = tmp_path / "owner.json"
        owner_file.write_text(json.dumps({"owner": identity}), encoding="utf-8")
        output = tmp_path / "guard"
        guard = subprocess.Popen([sys.executable, str(SCRIPT), "--owner-file", str(owner_file),
                                  "--output", str(output), "--interval", "0.05"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        started = wait_json(output / "identity.json", guard)
        assert started["owner"] == identity
        assert not started["display_required"] and not started["away_mode_required"]
        heartbeat = wait_json(output / "heartbeat.json", guard)
        if finish == "reader_lock":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel.CreateFileW
            create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint,
                               ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
            create.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle.restype = ctypes.c_int
            handle = create(str(output / "heartbeat.json"), 0x80000000, 3, None, 3, 0, None)
            assert handle not in (None, ctypes.c_void_p(-1).value)
            try:
                time.sleep(0.35)
                assert guard.poll() is None, "transient reader lock must not end awake request"
            finally:
                assert kernel.CloseHandle(handle)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                fresh = wait_json(output / "heartbeat.json", guard, deadline=deadline)
                if fresh["at"] != heartbeat["at"]:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("heartbeat did not resume after reader released lock")
        if finish in ("stop", "reader_lock"):
            (output / "stop.request").touch()
        else:
            owner.stdin.close()
            owner.wait(timeout=10)
        stdout, stderr = guard.communicate(timeout=15)
        assert guard.returncode == 0, (stdout, stderr)
        receipt = json.loads((output / "completion.json").read_text(encoding="utf-8"))
        assert receipt["released"] is True
        assert receipt["reason"] == ("owner_ended_or_replaced" if finish == "owner_exit" else "stop_requested")
        if finish in ("stop", "reader_lock"):
            assert owner.poll() is None, "guard must not terminate owner"
    finally:
        if guard is not None and guard.poll() is None:
            guard.terminate()
            guard.communicate(timeout=10)
        if owner.poll() is None:
            owner.stdin.close()
            owner.wait(timeout=10)


def rejects_stale_identity_before_power_request(tmp_path):
    process = psutil.Process()
    owner_file = tmp_path / "owner.json"
    owner_file.write_text(json.dumps({"owner": {"pid": process.pid,
                          "created": process.create_time() - 100}}), encoding="utf-8")
    output = tmp_path / "guard"
    result = subprocess.run([sys.executable, str(SCRIPT), "--owner-file", str(owner_file),
                             "--output", str(output)], capture_output=True, timeout=15)
    assert result.returncode != 0
    assert not output.exists()


class AwakeReceiptReadTests(unittest.TestCase):
    def test_transient_windows_read_denial_recovers_real_receipt(self):
        denied = PermissionError(13, "synthetic sharing violation")
        denied.winerror = 32
        process = mock.Mock()
        with mock.patch.object(fixture, "WINDOWS", True), \
             mock.patch.object(fixture, "_shared_json_bytes",
                               side_effect=[denied, b'{"at":"fresh"}']) as read, \
             mock.patch.object(time, "sleep"):
            self.assertEqual(wait_json(Path("heartbeat.json"), process), {"at": "fresh"})
        self.assertEqual(read.call_count, 2)

    def test_missing_receipt_waits_for_publication(self):
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(fixture, "WINDOWS", False), \
             mock.patch.object(fixture, "_shared_json_bytes",
                               side_effect=[FileNotFoundError(), b'{"at":"first"}']) as read, \
             mock.patch.object(time, "sleep"):
            self.assertEqual(wait_json(Path("heartbeat.json"), process), {"at": "first"})
        self.assertEqual(read.call_count, 2)
        process.poll.assert_called_once_with()

    def test_caller_deadline_bounds_windows_sharing_retry(self):
        clock = [5.0]
        denied = PermissionError(13, "persistent sharing violation")
        denied.winerror = 32

        def advance(seconds):
            clock[0] += seconds

        with mock.patch.object(fixture, "WINDOWS", True), \
             mock.patch.object(fixture, "_shared_json_bytes", side_effect=denied), \
             mock.patch.object(time, "monotonic", side_effect=lambda: clock[0]), \
             mock.patch.object(time, "sleep", side_effect=advance):
            with self.assertRaises(PermissionError):
                wait_json(Path("heartbeat.json"), mock.Mock(), deadline=5.05)
        self.assertAlmostEqual(clock[0], 5.05)

    def test_expired_deadline_does_not_start_a_new_read(self):
        with mock.patch.object(time, "monotonic", return_value=5.0), \
             mock.patch.object(fixture, "read_fixture_json") as read:
            with self.assertRaisesRegex(AssertionError, "did not write receipt"):
                wait_json(Path("heartbeat.json"), mock.Mock(), deadline=5.0)
        read.assert_not_called()

    def test_corrupt_json_and_nonretryable_read_errors_fail(self):
        for error in (PermissionError(13, "denied"), OSError(28, "disk full")):
            with self.subTest(error=error), \
                 mock.patch.object(fixture, "WINDOWS", False), \
                 mock.patch.object(fixture, "_shared_json_bytes", side_effect=error) as read:
                with self.assertRaises(type(error)):
                    wait_json(Path("heartbeat.json"), mock.Mock())
                self.assertEqual(read.call_count, 1)
        with mock.patch.object(fixture, "_shared_json_bytes", return_value=b'{bad') as read:
            with self.assertRaises(json.JSONDecodeError):
                wait_json(Path("heartbeat.json"), mock.Mock())
        self.assertEqual(read.call_count, 1)

    def test_guard_exit_before_publication_is_reported(self):
        process = mock.Mock()
        process.poll.return_value = 1
        with mock.patch.object(fixture, "read_fixture_json", side_effect=FileNotFoundError()):
            with self.assertRaisesRegex(AssertionError, "guard ended before receipt"):
                wait_json(Path("heartbeat.json"), process)


@unittest.skipUnless(sys.platform == "win32", "Windows power API")
class WindowsAwakeGuardTests(unittest.TestCase):
    def test_stop_releases_request_without_stopping_owner(self):
        with tempfile.TemporaryDirectory() as root:
            real_windows_lifecycle(Path(root), "stop")

    def test_owner_exit_releases_request(self):
        with tempfile.TemporaryDirectory() as root:
            real_windows_lifecycle(Path(root), "owner_exit")

    def test_stale_identity_never_acquires_request(self):
        with tempfile.TemporaryDirectory() as root:
            rejects_stale_identity_before_power_request(Path(root))

    def test_transient_reader_lock_keeps_request_alive(self):
        with tempfile.TemporaryDirectory() as root:
            real_windows_lifecycle(Path(root), "reader_lock")


if __name__ == "__main__":
    unittest.main()
