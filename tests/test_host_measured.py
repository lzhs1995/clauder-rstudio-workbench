"""Synthetic SQLite/measurement tests: no production database or Windows calls."""
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "mplusautomation-guide" / "scripts"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# 显式按仓库路径加载，不依赖已安装技能或其他测试的 sys.path/module 缓存。
hm = _load("host_measured_test_subject", "host_measured.py")
HostReservations = _load("apim_v2_io_measured_test_subject", "apim_v2_io.py").HostReservations

G = 1024 ** 3
C = "C:\\"
D = "D:\\"


def policy(**updates):
    value = dict(schema="host-measured-policy-v1", host_id="fixture-host",
        physical_reserve_bytes=G, commit_reserve_bytes=G, processor_budget=8,
        unmanaged_physical_bytes=0, unmanaged_commit_bytes=0, unmanaged_processors=0,
        volume_reserve_bytes={C: 20_000_000_000}, unmanaged_volume_bytes={C: 0},
        max_sample_seconds=1, legacy_volume_bytes={}, unmanaged_budget_verified=True,
        unmanaged_budget_evidence_sha256="a" * 64)
    value.update(updates)
    return value


def snapshot(roots, **updates):
    value = dict(source="SYNTHETIC_TEST_ONLY", host_id="fixture-host",
        physical_total_bytes=16 * G, physical_available_bytes=8 * G,
        commit_limit_bytes=32 * G, commit_total_bytes=16 * G, logical_processors=16,
        volumes={root: dict(volume_id="fixture-volume-" + root[0], free_bytes=40 * G, total_bytes=100 * G)
                 for root in roots})
    value.update(updates)
    return value


class MeasuredAdmissionTests(unittest.TestCase):
    def setUp(self):
        # 两个新增API延迟导入host_measured；只在本测试期间绑定并在结束后恢复。
        modules = patch.dict(sys.modules, {"host_measured": hm})
        modules.start()
        self.addCleanup(modules.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "registry.sqlite"
        self.registry = HostReservations(self.path)

    def tearDown(self):
        self.registry.db.close()
        self.tmp.cleanup()

    def configure(self, **updates):
        return self.registry.configure_measured_policy("host-policy-1", policy(**updates))

    def acquire(self, key="a", **updates):
        request = dict(key=key, pid=1234, created=10.5, physical_bytes=G,
                       commit_bytes=G, processors=1, volume_bytes={C: 1024},
                       policy_id="host-policy-1", sampler=snapshot,
                       owner_probe=lambda pid, created: True)
        request.update(updates)
        return self.registry.acquire_measured(**request)

    def rows(self):
        return [tuple(row) for row in self.registry.db.execute("SELECT * FROM reservations ORDER BY key")]

    def test_legacy_acquire_and_identity_scoped_release_remain_usable(self):
        # 用真实旧API核同库内存/CPU预算与原owner释放，不携带私有base源码。
        fake = types.SimpleNamespace(
            Process=lambda pid: types.SimpleNamespace(create_time=lambda: 10.5, is_running=lambda: True),
            NoSuchProcess=type("Missing", (Exception,), {}),
            AccessDenied=type("Denied", (Exception,), {}))
        with patch.dict(sys.modules, psutil=fake):
            first = self.registry.acquire("legacy-a", 1234, 10.5, 2, 2, 8, 8, 1, 1, 4)
            self.assertTrue(first["admitted"])
            memory = self.registry.acquire("legacy-b", 1234, 10.5, 2, 1, 4, 8, 1, 1, 4)
            self.assertEqual(memory["reason"], "host_memory_reservation")
            cpu = self.registry.acquire("legacy-b", 1234, 10.5, 1, 3, 8, 8, 1, 1, 4)
            self.assertEqual(cpu["reason"], "host_processor_reservation")
            with self.assertRaisesRegex(ValueError, "owner mismatch"):
                self.registry.acquire("legacy-a", 99, 10.5, 2, 2, 8, 8, 1, 1, 4)
        self.assertEqual(len(self.rows()), 1)
        self.registry.release("legacy-a", 99, 10.5)
        self.registry.release("legacy-a", 1234, 11.5)
        self.assertEqual(len(self.rows()), 1)
        self.registry.release("legacy-a", 1234, 10.5)
        self.assertEqual(self.rows(), [])

    def test_no_policy_refuses_without_sampler_or_rows(self):
        with self.assertRaisesRegex(ValueError, "NOT_REGISTERED"):
            self.acquire(sampler=lambda roots: self.fail("sampler called"))
        self.assertEqual(self.rows(), [])

    def test_policy_registration_is_explicit_and_immutable(self):
        first = self.configure()
        self.assertFalse(first["duplicate"])
        self.assertTrue(self.configure()["duplicate"])
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            self.configure(commit_reserve_bytes=0)
        self.assertEqual(self.rows(), [])

    def test_policy_requires_independent_reserves_and_external_verification(self):
        for field in ("physical_reserve_bytes", "commit_reserve_bytes", "unmanaged_physical_bytes",
                      "unmanaged_commit_bytes", "unmanaged_processors", "unmanaged_budget_verified"):
            with self.subTest(field=field):
                p = policy(); p.pop(field)
                with self.assertRaises(ValueError):
                    self.registry.configure_measured_policy("x", p)
        pending = self.configure(unmanaged_budget_verified=False, unmanaged_budget_evidence_sha256=None)
        self.assertEqual(pending["waiting_resource"], "unmanaged_growth")
        self.assertEqual(pending["status"], "STRICT_HOST_POLICY_NOT_REGISTERED")
        with self.assertRaisesRegex(ValueError, "NOT_REGISTERED"):
            self.acquire(sampler=lambda roots: self.fail("unknown growth must block before sample"))
        self.assertFalse(self.configure()["duplicate"])

    def test_policy_version_change_requires_empty_original_reservations(self):
        self.configure(); self.acquire()
        with self.assertRaisesRegex(ValueError, "ACTIVE_RESERVATIONS"):
            self.registry.configure_measured_policy("host-policy-2", policy(commit_reserve_bytes=2*G))
        self.registry.release("a", 1234, 10.5)
        new = self.registry.configure_measured_policy("host-policy-2", policy(commit_reserve_bytes=2*G))
        self.assertEqual(new["policy_id"], "host-policy-2")
        self.assertEqual(self.registry.db.execute("SELECT COUNT(*) FROM host_measured_policy").fetchone()[0], 2)
        with self.assertRaisesRegex(ValueError, "NOT_REGISTERED"):
            self.acquire()
        self.assertTrue(self.acquire("b", policy_id="host-policy-2")["admitted"])

    def test_every_policy_volume_requires_explicit_unmanaged_growth(self):
        for unmanaged in ({}, {C: 0}):
            with self.subTest(unmanaged=unmanaged), self.assertRaisesRegex(ValueError, "every configured volume"):
                self.configure(volume_reserve_bytes={C: 20_000_000_000, D: 20_000_000_000},
                               unmanaged_volume_bytes=unmanaged)
        self.assertEqual(self.rows(), [])

    def test_sampler_executes_under_same_database_write_lock(self):
        self.configure()
        calls = []
        def locked_sample(roots):
            self.assertTrue(self.registry.db.in_transaction)
            other = sqlite3.connect(self.path, timeout=0, isolation_level=None)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    other.execute("BEGIN IMMEDIATE")
            finally:
                other.close()
            calls.append(roots)
            return snapshot(roots)
        result = self.acquire(sampler=locked_sample)
        self.assertTrue(result["admitted"])
        self.assertTrue(result["new_reservation"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(calls, [[C]])
        self.assertEqual(len(self.rows()), 1)

    def test_physical_and_commit_do_not_compensate_each_other(self):
        self.configure()
        cases = [({"physical_available_bytes": G}, "physical_ram"),
                 ({"commit_total_bytes": 32 * G - G}, "commit")]
        for updates, expected in cases:
            with self.subTest(expected=expected):
                result = self.acquire(sampler=lambda roots: snapshot(roots, **updates))
                self.assertEqual(result["waiting_resource"], expected)
                self.assertFalse(result["admitted"])
                self.assertEqual(self.rows(), [])

    def test_external_growth_and_cpu_budget_are_charged(self):
        self.configure(unmanaged_physical_bytes=2 * G, unmanaged_commit_bytes=3 * G,
                       unmanaged_processors=7)
        result = self.acquire(processors=2)
        self.assertEqual(result["waiting_resource"], "processors")
        self.assertEqual(result["required"], dict(physical_bytes=3 * G, commit_bytes=4 * G, processors=9))
        self.assertEqual(self.rows(), [])

    def test_actual_cpu_count_also_caps_declared_threads(self):
        self.configure()
        result = self.acquire(processors=5, sampler=lambda roots: snapshot(roots, logical_processors=4))
        self.assertEqual(result["waiting_resource"], "processors")

    def test_disk_floor_and_growth_are_independent(self):
        self.configure(unmanaged_volume_bytes={C: 2 * G})
        result = self.acquire(volume_bytes={C: G}, sampler=lambda roots: snapshot(roots,
            volumes={C: dict(volume_id="vol-c", free_bytes=20_000_000_000 + 2 * G, total_bytes=100 * G)}))
        self.assertEqual(result["waiting_resource"], "disk_bytes")
        self.assertEqual(result["reserved_volume_growth_bytes"], {"vol-c": 3 * G})
        self.assertEqual(self.rows(), [])

    def test_same_volume_two_drive_aliases_sum_growth(self):
        self.configure(volume_reserve_bytes={C: 20_000_000_000, D: 20_000_000_000},
                       unmanaged_volume_bytes={C: 0, D: 0})
        def aliased(roots):
            return snapshot(roots, volumes={root: dict(volume_id="same-volume", free_bytes=20_000_000_000+3*G,
                                                       total_bytes=100*G) for root in roots})
        first = self.acquire(volume_bytes={C: 2 * G}, sampler=aliased)
        self.assertTrue(first["admitted"])
        second = self.acquire("b", volume_bytes={D: 2 * G}, sampler=aliased)
        self.assertEqual(second["waiting_resource"], "disk_bytes")
        self.assertEqual(len(self.rows()), 1)

    def test_snapshot_bad_counter_values_never_admit(self):
        self.configure()
        cases = [dict(physical_available_bytes=float("nan")), dict(commit_total_bytes=-1),
                 dict(commit_limit_bytes=None), dict(logical_processors=True),
                 dict(commit_total_bytes=33*G), dict(host_id="other-host"),
                 dict(volumes={}), dict(physical_total_bytes=0)]
        for updates in cases:
            with self.subTest(updates=updates):
                result = self.acquire(sampler=lambda roots: snapshot(roots, **updates))
                self.assertEqual(result["waiting_resource"], "measurement")
                self.assertEqual(self.rows(), [])

    def test_measurement_errors_and_duration_fail_closed(self):
        self.configure()
        def broken(roots):
            raise OSError("native query unavailable")
        self.assertEqual(self.acquire(sampler=broken)["waiting_resource"], "measurement")
        times = iter([100, 2_000_000_100])
        result = self.acquire(clock_ns=lambda: next(times))
        self.assertEqual(result["reason"], "SAMPLE_DURATION_EXCEEDED")
        times = iter([200, 100])
        self.assertEqual(self.acquire(clock_ns=lambda: next(times))["reason"], "SAMPLE_DURATION_EXCEEDED")
        self.assertEqual(self.rows(), [])

    def test_post_sample_decision_time_cannot_use_stale_measurement(self):
        self.configure()
        clock = iter([100, 200, 1_000_000_101])
        result = self.acquire(clock_ns=lambda: next(clock))
        self.assertEqual(result["reason"], "DECISION_BUDGET_EXCEEDED")
        self.assertEqual(result["sample_duration_ns"], 100)
        self.assertEqual(self.rows(), [])

    def test_invalid_budgets_rejected_before_sampling(self):
        self.configure()
        for updates in (dict(physical_bytes=float("nan")), dict(commit_bytes=-1), dict(processors=True),
                        dict(created=float("inf")), dict(pid=0), dict(volume_bytes={C: -1}),
                        dict(volume_bytes={"C:/": 1}), dict(volume_bytes={C: 1, "c:\\": 2})):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.acquire(sampler=lambda roots: self.fail("sampled invalid budget"), **updates)
        self.assertEqual(self.rows(), [])

    def test_missing_output_floor_refuses(self):
        self.configure()
        with self.assertRaisesRegex(ValueError, "OUTPUT_VOLUME_NOT_IN_HOST_POLICY"):
            self.acquire(volume_bytes={D: 1})

    def test_orphan_and_unknown_existing_owner_are_retained(self):
        self.configure(legacy_volume_bytes={"legacy": {C: 0}})
        self.registry.db.execute("INSERT INTO reservations VALUES (?,?,?,?,?,?)", ("legacy", 7, 12.0, 1.0, 1, 1.0))
        before = self.rows()
        for status in (None, False):
            with self.subTest(status=status):
                result = self.acquire(owner_probe=lambda pid, created: status if pid == 7 else True)
                self.assertEqual(result["waiting_resource"], "owner_identity")
                self.assertEqual(self.rows(), before)

    def test_candidate_owner_must_be_verified(self):
        self.configure()
        for value in (False, None, 1):
            self.assertEqual(self.acquire(owner_probe=lambda p, c: value)["reason"], "CANDIDATE_OWNER_UNVERIFIED")
        self.assertEqual(self.rows(), [])

    def test_legacy_gib_rows_count_against_both_memory_budgets(self):
        self.configure(legacy_volume_bytes={"legacy": {C: G}})
        self.registry.db.execute("INSERT INTO reservations VALUES (?,?,?,?,?,?)", ("legacy", 7, 12.0, 2.0, 1, 1.0))
        first = self.acquire(sampler=lambda roots: snapshot(roots, physical_available_bytes=3 * G))
        self.assertEqual(first["waiting_resource"], "physical_ram")
        second = self.acquire(sampler=lambda roots: snapshot(roots, commit_total_bytes=29 * G))
        self.assertEqual(second["waiting_resource"], "commit")
        self.assertEqual(first["required"]["physical_bytes"], 3 * G)
        self.assertEqual(first["required"]["commit_bytes"], 3 * G)
        self.assertEqual(len(self.rows()), 1)

    def test_unmapped_legacy_disk_budget_blocks_instead_of_using_zero(self):
        self.configure()
        self.registry.db.execute("INSERT INTO reservations VALUES (?,?,?,?,?,?)", ("legacy", 7, 12.0, 1.0, 1, 1.0))
        result = self.acquire()
        self.assertEqual(result["waiting_resource"], "legacy_disk_budget")
        self.assertEqual(len(self.rows()), 1)

    def test_strict_separate_budgets_and_max_gib_for_old_reader(self):
        self.configure()
        first = self.acquire(physical_bytes=G//2, commit_bytes=2*G)
        self.assertTrue(first["admitted"])
        self.assertEqual(self.rows()[0][3], 2.0)
        second = self.acquire("b", physical_bytes=G, commit_bytes=G)
        self.assertTrue(second["admitted"])
        self.assertEqual(second["required"]["physical_bytes"], G + G//2)
        self.assertEqual(second["required"]["commit_bytes"], 3*G)
        fake = types.SimpleNamespace(Process=lambda pid: types.SimpleNamespace(create_time=lambda: 10.5, is_running=lambda: True),
                                     NoSuchProcess=type("Missing", (Exception,), {}), AccessDenied=type("Denied", (Exception,), {}))
        with patch.dict(sys.modules, psutil=fake):
            old = self.registry.acquire("legacy-after", 1234, 10.5, 1.5, 1, 4, 4, 1, 1, 8)
        self.assertFalse(old["admitted"])

    def test_same_key_contract_change_rejected_and_duplicate_is_not_execution_grant(self):
        self.configure()
        self.assertTrue(self.acquire()["admitted"])
        before = self.rows()
        duplicate = self.acquire()
        self.assertTrue(duplicate["duplicate"])
        self.assertFalse(duplicate["new_reservation"])
        self.assertFalse(duplicate["execution_authorized"])
        with self.assertRaisesRegex(ValueError, "CONTRACT_CONFLICT"):
            self.acquire(commit_bytes=2*G)
        with self.assertRaises(ValueError):
            self.acquire(pid=99)
        self.assertEqual(self.rows(), before)

    def test_old_release_leaves_strict_identity_tombstone(self):
        self.configure(); self.acquire()
        self.registry.release("a", 1234, 10.5)
        self.assertEqual(self.rows(), [])
        with self.assertRaisesRegex(ValueError, "RELEASED_STRICT_KEY"):
            self.acquire()

    def test_changed_volume_identity_or_legacy_row_blocks(self):
        self.configure(); self.acquire()
        def changed(roots):
            return snapshot(roots, volumes={C: dict(volume_id="other-volume", free_bytes=40*G, total_bytes=100*G)})
        with self.assertRaisesRegex(ValueError, "VOLUME_IDENTITY_CHANGED"):
            self.acquire("b", sampler=changed)
        self.registry.db.execute("UPDATE reservations SET gib=0.1 WHERE key='a'")
        with self.assertRaisesRegex(ValueError, "COMPATIBILITY_ROW_CHANGED"):
            self.acquire("b")
        self.assertEqual(len(self.rows()), 1)

    def test_two_connections_compete_under_one_measurement_lock(self):
        self.configure()
        barrier = threading.Barrier(2)
        results, errors = [], []
        def contender(key):
            reg = HostReservations(self.path)
            try:
                barrier.wait(timeout=5)
                result = reg.acquire_measured(key, 1234, 10.5, 3*G//2, 3*G//2, 1, {C: 1}, "host-policy-1",
                    sampler=lambda roots: snapshot(roots, physical_available_bytes=3*G),
                    owner_probe=lambda p, c: True)
                results.append(result)
            except BaseException as exc:
                errors.append(repr(exc))
            finally:
                reg.db.close()
        threads = [threading.Thread(target=contender, args=(key,)) for key in ("thread-a", "thread-b")]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(sorted(result["admitted"] for result in results), [False, True])
        self.assertEqual(len(self.rows()), 1)

    @unittest.skipIf(sys.platform == "win32", "default non-Windows refusal test")
    def test_default_sampler_refuses_non_windows(self):
        self.configure()
        result = self.acquire(sampler=hm.windows_snapshot)
        self.assertEqual(result["waiting_resource"], "measurement")
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
