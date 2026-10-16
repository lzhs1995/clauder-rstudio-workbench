"""Exercise actual Windows request acquisition/release and owner identity."""
import json
import ctypes
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import psutil

SCRIPT = Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts/windows_awake_guard.py"


def wait_json(path, process):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        assert process.poll() is None, "guard ended before receipt"
        time.sleep(0.05)
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
                fresh = wait_json(output / "heartbeat.json", guard)
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
