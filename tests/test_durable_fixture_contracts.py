"""只验证 verify_saved_batch.snapshot() 的读取边界；没有研究数据、R或Mplus调用。"""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/mplusautomation-guide/scripts/verify_saved_batch.py'
SPEC = importlib.util.spec_from_file_location('bounded_reader_candidate', SCRIPT)
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


class SnapshotBounds(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'tiny.json'
        self.path.write_bytes(b'{"a":1}')

    def test_tiny_file_reads_size_plus_one_and_keeps_sha(self):
        real = os.fdopen
        calls = []
        class Observe:
            def __init__(self, fd, mode): self.file = real(fd, mode)
            def __enter__(self): return self
            def __exit__(self, *args): self.file.close()
            def fileno(self): return self.file.fileno()
            def read(self, n): calls.append(n); return self.file.read(n)
        with mock.patch.object(reader.os, 'fdopen', Observe):
            data, pin = reader.snapshot(self.path)
        self.assertEqual(calls, [8])
        self.assertEqual(data, b'{"a":1}')
        self.assertEqual(pin['sha256'], hashlib.sha256(data).hexdigest())

    def test_empty_file_is_bounded(self):
        self.path.write_bytes(b'')
        self.assertEqual(reader.snapshot(self.path)[0], b'')

    def test_growth_during_read_rejected(self):
        real = os.fdopen
        path = self.path
        class Grow:
            def __init__(self, fd, mode): self.file = real(fd, mode)
            def __enter__(self): return self
            def __exit__(self, *args): self.file.close()
            def fileno(self): return self.file.fileno()
            def read(self, n):
                with path.open('ab') as stream: stream.write(b'x')
                return self.file.read(n)
        with mock.patch.object(reader.os, 'fdopen', Grow):
            with self.assertRaisesRegex(reader.Rejected, 'changed|growing'):
                reader.snapshot(self.path)

    def test_short_read_rejected_without_identity_change(self):
        real = os.fdopen
        class Short:
            def __init__(self, fd, mode): self.file = real(fd, mode)
            def __enter__(self): return self
            def __exit__(self, *args): self.file.close()
            def fileno(self): return self.file.fileno()
            def read(self, n): return self.file.read(n)[:-1]
        with mock.patch.object(reader.os, 'fdopen', Short):
            with self.assertRaisesRegex(reader.Rejected, 'Short'):
                reader.snapshot(self.path)

    def test_opened_identity_change_rejected_before_read(self):
        before = self.path.stat()
        changed = types.SimpleNamespace(st_dev=before.st_dev, st_ino=before.st_ino + 1,
                                        st_size=before.st_size, st_mtime_ns=before.st_mtime_ns)
        with mock.patch.object(reader.os, 'fstat', return_value=changed):
            with self.assertRaisesRegex(reader.Rejected, 'before reading'):
                reader.snapshot(self.path)

    def test_oversized_sparse_file_rejected(self):
        with self.path.open('wb') as stream: stream.truncate(128 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(reader.Rejected, 'bounded reader'):
            reader.snapshot(self.path)

    def test_symlink_rejected_when_available(self):
        link = self.path.with_name('alias')
        try: link.symlink_to(self.path)
        except OSError as error: self.skipTest(str(error))
        with self.assertRaisesRegex(reader.Rejected, 'non-symlink'):
            reader.snapshot(link)


if __name__ == '__main__':
    unittest.main()
