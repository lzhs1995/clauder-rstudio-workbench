"""只验证新夹具生命周期和读取边界；没有研究数据、R或Mplus调用。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

import psutil
import durable_fixture_processes as fixture
from durable_fixture_processes import FixtureProcesses

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


class ProcessIdentityContracts(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='durable-identity-contract-')).resolve()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.registry = FixtureProcesses(self.root)
        self.children = []

    def tearDown(self):
        # 只在清理证明成功后释放；异常保留目录。
        self.registry.cleanup(self.children, self.work)
        import shutil
        shutil.rmtree(self.root)

    def test_different_launcher_and_actual_coordinator_are_bound(self):
        actual = self.root / 'actual.py'
        actual.write_text("import json,sys,time,psutil\nfrom pathlib import Path\n"
            "p=psutil.Process(); w=Path(sys.argv[2]); w.joinpath('STATUS.json').write_text(json.dumps({'worker':{'pid':p.pid,'created':p.create_time(),'exe':p.exe()}}))\n"
            "while True: time.sleep(.02)\n")
        shim = self.root / 'shim.py'
        shim.write_text("import subprocess,sys\np=subprocess.Popen([sys.executable,sys.argv[1],'run',sys.argv[2]])\nsys.exit(p.wait())\n")
        proc = subprocess.Popen([sys.executable, str(shim), str(actual), str(self.work)], cwd=self.root)
        self.children.append(proc)
        deadline = time.monotonic() + 10
        while not (self.work / 'STATUS.json').exists() and time.monotonic() < deadline:
            self.registry.observe(self.children, self.work)
            time.sleep(.02)
        real = self.registry.actual_coordinator(proc, self.work)
        self.assertNotEqual(real.pid, proc.pid)
        self.registry.crash_coordinator(proc, self.work)
        self.assertIsNotNone(proc.poll())

    def test_pid_reuse_never_receives_signal(self):
        fake = mock.Mock()
        fake.create_time.return_value = 2
        with mock.patch('durable_fixture_processes.psutil.Process', return_value=fake):
            with self.assertRaisesRegex(AssertionError, 'reused'):
                self.registry.current(dict(pid=999999, created=1, exe='unused'))
        fake.kill.assert_not_called()

    def test_unreadable_identity_is_not_success(self):
        with mock.patch('durable_fixture_processes.psutil.Process', side_effect=psutil.AccessDenied(999999)):
            with self.assertRaises(psutil.AccessDenied):
                self.registry.current(dict(pid=999999, created=1, exe='unused'))

    def test_repeat_observation_cannot_rebind_changed_executable(self):
        original = dict(pid=999999, created=1, exe='original-fixed-exe')
        self.registry.records[999999] = original.copy()
        fake = mock.Mock(pid=999999)
        fake.create_time.return_value = 1
        fake.is_running.return_value = True
        fake.status.return_value = psutil.STATUS_RUNNING
        fake.exe.return_value = 'different-exe'
        fake.wait.side_effect = psutil.TimeoutExpired(.2)
        with mock.patch('durable_fixture_processes.psutil.Process', return_value=fake):
            with self.assertRaisesRegex(AssertionError, 'identity changed'):
                self.registry.remember(fake, 'repeated-observation')
        self.assertEqual(self.registry.records[999999], original)
        fake.kill.assert_not_called()

    def test_unmarked_owned_child_is_cleaned(self):
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)', str(self.root)], cwd=self.root)
        self.children.append(proc)
        self.registry.observe(self.children, self.work)
        self.assertIn(proc.pid, self.registry.records)
        self.registry.cleanup(self.children, self.work)
        self.assertIsNotNone(proc.poll())

    def test_marker_in_same_directory_cannot_substitute_another_launcher(self):
        script = self.root / 'unrelated.py'
        script.write_text('import time\nwhile True: time.sleep(.02)\n')
        first = subprocess.Popen([sys.executable, str(script), 'run', str(self.work)], cwd=self.root)
        other = subprocess.Popen([sys.executable, str(script), 'run', str(self.work)], cwd=self.root)
        self.children.extend([first, other])
        self.registry.observe(self.children, self.work)
        process = psutil.Process(other.pid)
        (self.work / 'STATUS.json').write_text(json.dumps({'worker': {
            'pid': other.pid, 'created': process.create_time(), 'exe': process.exe()}}))
        with self.assertRaisesRegex(AssertionError, 'original launcher lineage'):
            self.registry.actual_coordinator(first, self.work)
        self.assertIsNone(first.poll())
        self.assertIsNone(other.poll())


class SharedFixtureReadContracts(unittest.TestCase):
    def test_windows_transient_denial_retries_without_fabricating_status(self):
        denied = PermissionError(13, 'sharing')
        with mock.patch.object(fixture, 'WINDOWS', True), \
             mock.patch.object(fixture, '_shared_json_bytes', side_effect=[denied, denied, b'{"stage":"HOLD"}']) as read, \
             mock.patch.object(fixture.time, 'sleep'):
            self.assertEqual(fixture.read_fixture_json('status'), {'stage': 'HOLD'})
        self.assertEqual(read.call_count, 3)

    def test_original_deadline_is_not_restarted_on_denial(self):
        denied = PermissionError(13, 'still denied')
        with mock.patch.object(fixture, 'WINDOWS', True), \
             mock.patch.object(fixture, '_shared_json_bytes', side_effect=denied) as read, \
             mock.patch.object(fixture.time, 'monotonic', side_effect=[5.0, 5.1, 5.2]), \
             mock.patch.object(fixture.time, 'sleep') as sleep:
            with self.assertRaises(PermissionError):
                fixture.read_fixture_json('status', deadline=5.15)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    def test_posix_permission_error_and_corrupt_json_are_not_swallowed(self):
        with mock.patch.object(fixture, 'WINDOWS', False), \
             mock.patch.object(fixture, '_shared_json_bytes', side_effect=PermissionError(13, 'denied')) as read:
            with self.assertRaises(PermissionError):
                fixture.read_fixture_json('status')
        self.assertEqual(read.call_count, 1)
        with mock.patch.object(fixture, '_shared_json_bytes', return_value=b'{bad') as read:
            with self.assertRaises(json.JSONDecodeError):
                fixture.read_fixture_json('status')
        self.assertEqual(read.call_count, 1)

    def test_json_reader_allows_atomic_writer_and_keeps_content_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'STATUS.json'
            path.write_text('{"n":0}', encoding='utf-8')
            errors = []
            def writer():
                try:
                    for n in range(1, 101):
                        candidate = path.with_suffix('.tmp')
                        candidate.write_text(json.dumps({'n': n}), encoding='utf-8')
                        os.replace(candidate, path)
                except BaseException as error:
                    errors.append(error)
            thread = threading.Thread(target=writer)
            thread.start()
            observed = []
            while thread.is_alive():
                observed.append(fixture.read_fixture_json(path)['n'])
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(fixture.read_fixture_json(path), {'n': 100})
            self.assertTrue(all(0 <= n <= 100 for n in observed))

    def test_oversized_status_is_not_read_unbounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'STATUS.json'
            with path.open('wb') as stream:
                stream.truncate(2 * 1024 * 1024 + 1)
            with self.assertRaisesRegex(ValueError, 'bounded status reader'):
                fixture.read_fixture_json(path)


class FixturePreservationContracts(unittest.TestCase):
    def test_unconfirmed_cleanup_keeps_original_without_copying_active_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, dest = Path(tmp) / 'source', Path(tmp) / 'evidence'
            root.mkdir()
            lock = root / '.batch-worker.lock'
            lock.write_bytes(b'original lock')
            error = AssertionError('original cleanup failure')
            with mock.patch.object(fixture.shutil, 'copytree', side_effect=AssertionError('must not copy')) as copy:
                fixture.preserve_fixture(root, dest, error)
            copy.assert_not_called()
            self.assertEqual(lock.read_bytes(), b'original lock')
            retained = json.loads((dest / 'ORIGINAL_FIXTURE_RETAINED.json').read_text())
            self.assertFalse(retained['snapshot_complete'])
            self.assertFalse(retained['source_deleted'])
            self.assertEqual(retained['original_root'], str(root))
            self.assertIn('original cleanup failure', retained['cleanup_error'])

    def test_confirmed_cleanup_copies_complete_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, dest = Path(tmp) / 'source', Path(tmp) / 'evidence'
            root.mkdir()
            (root / 'result.json').write_bytes(b'original result')
            fixture.preserve_fixture(root, dest)
            self.assertEqual((dest / 'result.json').read_bytes(), b'original result')
            self.assertTrue(root.exists())


if __name__ == '__main__':
    unittest.main()
