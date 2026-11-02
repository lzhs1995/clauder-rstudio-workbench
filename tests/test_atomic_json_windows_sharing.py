"""进度 JSON 的 Windows 共享读冲突；没有 R 或 Mplus 估计。"""
import ctypes
import errno
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts"
sys.path.insert(0, str(SCRIPTS))
import durable_mplus_worker as worker


def win_error(code):
    error = PermissionError(errno.EACCES, "synthetic sharing violation")
    error.winerror = code
    return error


class AtomicJsonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "PROGRESS.json"
        self.path.write_text('{"stage":"old"}', encoding="utf-8")

    def test_retry_preserves_same_snapshot_and_complete_utf8(self):
        real_replace = os.replace
        sources = []

        def replace(source, target):
            sources.append((source, source.read_bytes()))
            if len(sources) < 4:
                raise win_error(5)
            return real_replace(source, target)

        with mock.patch.object(worker.os, "replace", side_effect=replace), mock.patch.object(worker.time, "sleep"):
            worker.atomic_json(self.path, {"stage": "核收", "count": 38})
        self.assertEqual(json.loads(self.path.read_bytes()), {"stage": "核收", "count": 38})
        self.assertEqual(len(sources), 4)
        self.assertEqual(len(set(sources)), 1)
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_non_windows_permission_failure_is_not_retried(self):
        with mock.patch.object(worker.os, "replace", side_effect=PermissionError("denied")) as replace:
            with self.assertRaises(PermissionError):
                worker.atomic_json(self.path, {"stage": "new"})
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(json.loads(self.path.read_bytes())["stage"], "old")
        self.assertEqual(len(list(self.root.glob("*.tmp"))), 1)

    def test_disk_full_is_not_retried(self):
        error = OSError(errno.ENOSPC, "full")
        error.winerror = 112
        with mock.patch.object(worker.os, "replace", side_effect=error) as replace:
            with self.assertRaises(OSError):
                worker.atomic_json(self.path, {"stage": "new"})
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(json.loads(self.path.read_bytes())["stage"], "old")

    def test_deadline_keeps_old_evidence_and_pending_snapshot(self):
        clock = [0.0]

        def sleep(seconds):
            clock[0] += seconds

        with mock.patch.object(worker.os, "replace", side_effect=win_error(32)), \
             mock.patch.object(worker.time, "monotonic", side_effect=lambda: clock[0]), \
             mock.patch.object(worker.time, "sleep", side_effect=sleep):
            with self.assertRaises(PermissionError):
                worker.atomic_json(self.path, {"stage": "pending"})
        self.assertAlmostEqual(clock[0], 2.0)
        self.assertEqual(json.loads(self.path.read_bytes())["stage"], "old")
        pending = list(self.root.glob("*.tmp"))
        self.assertEqual(len(pending), 1)
        self.assertEqual(json.loads(pending[0].read_bytes())["stage"], "pending")

    def test_new_evidence_that_appears_during_retry_is_preserved(self):
        self.path.unlink()
        with mock.patch.object(worker.os, "replace", side_effect=win_error(33)), \
             mock.patch.object(worker.time, "sleep", side_effect=lambda _: self.path.write_text('{"owner":"other"}')):
            with self.assertRaises(worker.Rejected):
                worker.atomic_json(self.path, {"owner": "this"}, new=True)
        self.assertEqual(json.loads(self.path.read_bytes()), {"owner": "other"})

    @unittest.skipUnless(os.name == "nt", "Requires a real Windows file sharing handle")
    def test_native_read_handle_reproduces_failure_then_retry_recovers(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong,
                                      ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.restype = ctypes.c_int
        # FILE_SHARE_READ|WRITE，故意不设 FILE_SHARE_DELETE，复现只读轮询碰撞。
        handle = kernel.CreateFileW(str(self.path), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        first = self.root / "first.tmp"
        first.write_text('{"stage":"new"}', encoding="utf-8")
        try:
            with self.assertRaises(OSError) as raised:
                os.replace(first, self.path)
            self.assertIn(raised.exception.winerror, (5, 32, 33))
            self.assertEqual(json.loads(self.path.read_bytes())["stage"], "old")
            released = threading.Event()

            def release():
                time.sleep(0.15)
                kernel.CloseHandle(handle)
                released.set()

            thread = threading.Thread(target=release)
            thread.start()
            try:
                worker.atomic_json(self.path, {"stage": "recovered"})
            finally:
                thread.join(timeout=3)
            self.assertTrue(released.is_set())
            self.assertEqual(json.loads(self.path.read_bytes())["stage"], "recovered")
        finally:
            if "released" not in locals() or not released.is_set():
                kernel.CloseHandle(handle)


if __name__ == "__main__":
    unittest.main()
