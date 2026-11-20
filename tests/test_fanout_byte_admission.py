from __future__ import annotations

import inspect
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench import fanout


GIB = 1024 ** 3


def _contract(root: Path, workers: int = 4) -> dict:
    return {
        "task_key": "synthetic-byte-admission",
        "_contract_path": str(root / "contract.json"),
        "artifacts": {"output_root": str(root)},
        "resource_gate": {
            "worker_mem_gib": 1,
            "worker_commit_gib": 1,
            "worker_processors": 1,
            "worker_output_gib": 1,
            "reserve_mem_gib": 1,
            "reserve_commit_gib": 1,
            "reserve_processors": 1,
            "reserve_output_gib": 2,
            "sample_max_age_sec": 60,
        },
        "workers": [
            {
                "id": f"w{i}",
                "code": f"worker <- {i}",
                "expected_state": f"state_w{i}.json",
                "expected_manifest": f"manifest_w{i}.csv",
                "expected_validation": f"validation_w{i}.csv",
            }
            for i in range(workers)
        ],
    }


def _sample(root: Path, **updates: object) -> dict:
    sample = {
        "sampled_at": time.time(),
        "host_verified": True,
        "host_id": "synthetic-worker",
        "session_pid": 1234,
        "output_root": str(root),
        "physical_available_bytes": 12 * GIB,
        "commit_available_bytes": 16 * GIB,
        "logical_processors": 8,
        "output_free_bytes": 24 * GIB,
        "memory_used_percent": 90.0,
    }
    sample.update(updates)
    return sample


def _probe_kwargs(function: object, sample: dict | None) -> dict:
    # 同一行为回归可对旧版运行；旧版忽略字节探针，不能用签名错误冒充红测试。
    if "resource_probe_fn" not in inspect.signature(function).parameters:
        return {}
    return {"resource_probe_fn": lambda: dict(sample) if sample is not None else None}


def _plan(contract: dict, sample: dict | None, *, memory: float | None = 90.0) -> dict:
    with mock.patch.object(fanout, "memory_used_percent", return_value=memory, create=True):
        return fanout.plan_fanout(contract, **_probe_kwargs(fanout.plan_fanout, sample))


def _run(contract: dict, sample: dict | None, **updates: object) -> tuple[dict, list[str]]:
    submissions: list[str] = []

    def submit(code: str) -> dict:
        submissions.append(code)
        return {"ok": True, "job_id": f"synthetic-job-{len(submissions)}", "text": "started"}

    kwargs = {
        "submit_fn": submit,
        "max_parallel": 1,
        "max_parallel_cap": 4,
        "auto_scale": True,
        "mem_probe_fn": lambda: sample.get("memory_used_percent") if sample is not None else None,
        "cpu_probe_fn": lambda: 0.0,
        "disk_probe_fn": lambda: 24.0,
        "sleep_fn": lambda _: None,
        "poll_interval_sec": 0,
        "max_iterations": 2,
        **_probe_kwargs(fanout.run_fanout, sample),
    }
    kwargs.update(updates)
    return fanout.run_fanout(contract, **kwargs), submissions


class FanoutByteAdmissionTests(unittest.TestCase):
    def test_plan_high_percent_does_not_override_sufficient_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = _plan(_contract(root), _sample(root))
            self.assertTrue(result["ok"])
            self.assertGreater(result["recommended_max_parallel"], 1)
            self.assertEqual(result["resource_admission"]["decision"], "allow")

    def test_run_high_percent_scales_and_keeps_transport_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result, submitted = _run(_contract(root), _sample(root), max_parallel_cap=3)
            self.assertGreater(len(submitted), 1)
            self.assertLessEqual(len(submitted), 3)
            self.assertGreater(result["max_parallel"], 1)
            self.assertEqual(result["transport_class"], "MCP_STDIO_OK")
            self.assertFalse(result["ok"])

    def test_each_insufficient_resource_holds_plan_and_actual_submission(self) -> None:
        cases = [
            ("physical_available_bytes", GIB, "physical"),
            ("commit_available_bytes", GIB, "commit"),
            ("logical_processors", 1, "thread"),
            ("output_free_bytes", 2 * GIB, "output"),
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for field, value, reason in cases:
                with self.subTest(resource=field):
                    sample = _sample(root, **{field: value, "memory_used_percent": 10.0})
                    result, submitted = _run(_contract(root), sample, max_parallel=3)
                    self.assertEqual(submitted, [])
                    plan = _plan(_contract(root), sample, memory=10.0)
                    self.assertEqual(plan["recommended_max_parallel"], 0)
                    self.assertEqual(plan["resource_admission"]["decision"], "hold")
                    self.assertIn(reason, " ".join(plan["resource_admission"]["reasons"]).lower())
                    self.assertIn(reason, json.dumps(result).lower())

    def test_unknown_probe_holds_without_suggesting_one_worker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result, submitted = _run(_contract(root), None)
            self.assertEqual(submitted, [])
            plan = _plan(_contract(root), None, memory=None)
            self.assertEqual(plan["recommended_max_parallel"], 0)
            reason = plan["advice_reason"].lower()
            self.assertIn("worker", reason)
            self.assertIn("unknown", reason)
            self.assertNotIn("start at 1", reason)
            self.assertIn("unknown", json.dumps(result).lower())

    def test_stale_future_and_unbound_samples_never_submit(self) -> None:
        cases = [
            {"sampled_at": time.time() - 120},
            {"sampled_at": time.time() + 300},
            {"host_verified": False},
            {"host_id": ""},
            {"session_pid": None},
            {"output_root": "different-worker-volume"},
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for updates in cases:
                with self.subTest(updates=updates):
                    sample = _sample(root, **updates)
                    result, submitted = _run(_contract(root), sample)
                    self.assertEqual(submitted, [])
                    plan = _plan(_contract(root), sample)
                    self.assertEqual(plan["recommended_max_parallel"], 0)
                    self.assertEqual(plan["resource_admission"]["decision"], "hold")

    def test_missing_resource_fields_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for field in ("physical_available_bytes", "commit_available_bytes", "logical_processors", "output_free_bytes"):
                with self.subTest(resource=field):
                    sample = _sample(root)
                    sample.pop(field)
                    _, submitted = _run(_contract(root), sample)
                    self.assertEqual(submitted, [])
                    plan = _plan(_contract(root), sample)
                    self.assertEqual(plan["recommended_max_parallel"], 0)

    def test_running_reservations_are_subtracted_from_each_resource(self) -> None:
        cases = [
            ("physical_available_bytes", 3 * GIB),
            ("commit_available_bytes", 3 * GIB),
            ("logical_processors", 3),
            ("output_free_bytes", 4 * GIB),
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for field, value in cases:
                with self.subTest(resource=field):
                    sample = _sample(root, **{field: value, "memory_used_percent": 10.0})
                    result, submitted = _run(_contract(root), sample, auto_scale=False, max_parallel=4)
                    self.assertEqual(len(submitted), 2)
                    self.assertEqual(len(result["still_running"]), 2)
                    self.assertEqual(len(result["pending"]), 2)

    def test_explicit_plan_request_stays_visible_but_admission_is_separate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            contract = _contract(root)
            contract["max_parallel"] = 4
            plan = _plan(contract, _sample(root, physical_available_bytes=3 * GIB))
            self.assertEqual(plan["requested_max_parallel"], 4)
            self.assertEqual(plan["recommended_max_parallel"], 4)
            self.assertEqual(plan.get("admitted_parallel"), 2)
            self.assertEqual(plan["resource_admission"]["available_slots"], 2)

    def test_explicit_fixed_parallel_remains_a_hard_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            contract = _contract(root)
            contract["max_parallel"] = 3
            result, submitted = _run(contract, _sample(root), max_parallel=2, auto_scale=False)
            self.assertEqual(len(submitted), 2)
            self.assertEqual(result["max_parallel"], 2)
            self.assertEqual(result["start_max_parallel"], 2)

    def test_auto_parallel_preserves_start_and_cap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result, submitted = _run(_contract(root), _sample(root), max_parallel=2, max_parallel_cap=3)
            self.assertEqual(result["start_max_parallel"], 2)
            self.assertEqual(result["max_parallel_cap"], 3)
            self.assertEqual(result["max_parallel"], 3)
            self.assertEqual(len(submitted), 3)

    def test_snapshot_is_rechecked_before_later_admission(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            contract = _contract(root)
            sufficient = _sample(root)
            deficient = _sample(root, commit_available_bytes=GIB)
            snapshots = iter([sufficient, deficient])
            if "resource_probe_fn" not in inspect.signature(fanout.run_fanout).parameters:
                kwargs = {}
            else:
                kwargs = {"resource_probe_fn": lambda: next(snapshots, deficient)}
            result, submitted = _run(contract, sufficient, max_parallel=1, **kwargs)
            self.assertEqual(len(submitted), 2)
            self.assertEqual(len(result["still_running"]), 2)


if __name__ == "__main__":
    unittest.main()
