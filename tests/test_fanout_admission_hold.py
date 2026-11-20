"""资源回压回归：只用合成提交/原 job 轮询，不启动 R 或外部进程。"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest

from clauder_workbench.fanout import run_fanout


GIB = 1024 ** 3
SAFE = {"physical_available_bytes": 100 * GIB, "commit_available_bytes": 100 * GIB,
        "logical_processors": 16, "output_free_bytes": 100 * GIB, "backlog": 0}


class SyntheticFanout:
    def __init__(self, root, frames, count=3):
        self.root = root
        self.frames = frames
        self.iteration = -1
        self.submits = []
        self.polls = []
        self.registrations = []
        self.snapshots = []
        self.complete_at = {}
        self.unknown_at = set()
        self.raise_at = set()
        self.contract = {
            "task_key": "synthetic-hold",
            "artifacts": {"output_root": str(root)},
            "resource_gate": {
                "worker_mem_gib": 1, "worker_commit_gib": 1, "worker_processors": 1,
                "worker_output_gib": 1, "reserve_mem_gib": 1, "reserve_commit_gib": 1,
                "reserve_processors": 1, "reserve_output_gib": 2, "sample_max_age_sec": 60,
            },
            "workers": [
                {"id": f"w{i}", "code": f"w{i}",
                 "expected_state": f"state_w{i}.json",
                 "expected_manifest": f"manifest_w{i}.csv",
                 "expected_validation": f"validation_w{i}.csv"}
                for i in range(1, count + 1)
            ],
        }

    def probe_resources(self):
        self.iteration += 1
        return {
            "sampled_at": time.time(), "host_verified": True,
            "host_id": "synthetic-worker", "session_pid": 1234,
            "output_root": str(self.root),
            **self.frames[min(self.iteration, len(self.frames) - 1)],
        }

    def probe(self, key):
        return self.frames[min(self.iteration, len(self.frames) - 1)][key]

    def submit(self, code):
        self.submits.append((self.iteration, code))
        return {"ok": True, "job_id": "original-" + code, "text": "mock submitted"}

    def poll(self, job_id):
        self.polls.append((self.iteration, job_id))
        key = (self.iteration, job_id)
        if key in self.raise_at:
            raise TimeoutError("synthetic transport uncertainty")
        if key in self.unknown_at:
            return {"ok": False, "text": "UNKNOWN transport result; retain original job"}
        wid = job_id.removeprefix("original-")
        if wid in self.complete_at and self.iteration >= self.complete_at[wid]:
            (self.root / f"state_{wid}.json").write_text(json.dumps({"stage": "complete"}))
            (self.root / f"manifest_{wid}.csv").write_text("id,value\nsynthetic,1\n")
            (self.root / f"validation_{wid}.csv").write_text("id,ok\nsynthetic,TRUE\n")
            return {"ok": True, "job_id": job_id, "status": "completed",
                    "success": True, "text": "mock complete"}
        return {"ok": True, "job_id": job_id, "status": "running", "text": "still running"}

    def run(self, **overrides):
        kwargs = {
            "submit_fn": self.submit, "poll_fn": self.poll,
            "register_fn": lambda worker, job: self.registrations.append((worker, job)),
            "progress_callback": self.snapshots.append,
            "max_parallel": 3, "max_parallel_cap": 3,
            "auto_scale": True, "max_iterations": len(self.frames),
            "resource_probe_fn": self.probe_resources,
            # 旧百分比与本机磁盘探针不能代替 worker 主机的字节采样。
            "mem_probe_fn": lambda: None,
            "cpu_probe_fn": lambda: None,
            "disk_probe_fn": lambda: None,
            "upload_backlog_probe_fn": lambda: self.probe("backlog"),
            "memory_hold_percent": 85, "cpu_hold_percent": 90,
            "min_disk_free_gb_hold": 40, "upload_backlog_hold": 3,
            "sleep_fn": lambda _: None, "poll_interval_sec": 0,
        }
        kwargs.update(overrides)
        return run_fanout(self.contract, **kwargs)


class FanoutAdmissionHoldTests(unittest.TestCase):
    @staticmethod
    def admits(snapshot):
        return snapshot["scale_event"]["resource_admission"]["available_slots"] > 0

    def test_each_known_hold_has_zero_submissions_with_zero_running(self):
        for key, value in (("physical_available_bytes", GIB),
                           ("commit_available_bytes", GIB),
                           ("logical_processors", 1),
                           ("output_free_bytes", 5 * GIB), ("backlog", 4)):
            with self.subTest(metric=key), tempfile.TemporaryDirectory() as tmp:
                fixture = SyntheticFanout(Path(tmp), [{**SAFE, key: value}] * 3)
                result = fixture.run()
                self.assertEqual(fixture.submits, [])
                self.assertEqual(fixture.polls, [])
                self.assertEqual(result["pending"], ["w1", "w2", "w3"])
                self.assertEqual(result["iterations"], 1)
                self.assertTrue(all(e["action"] == "hold_resources" for e in result["scale_log"]))
                self.assertTrue(all(not self.admits(e) for e in fixture.snapshots))

    def test_unknown_physical_cannot_mask_other_known_hold(self):
        for key, value, reason in (("commit_available_bytes", GIB, "commit"),
                                   ("output_free_bytes", 5 * GIB, "output"),
                                   ("backlog", 4, "upload backlog")):
            with self.subTest(metric=key), tempfile.TemporaryDirectory() as tmp:
                fixture = SyntheticFanout(Path(tmp), [{**SAFE, "physical_available_bytes": None, key: value}])
                result = fixture.run()
                self.assertEqual(fixture.submits, [])
                admission = result["scale_log"][0]["resource_admission"]
                self.assertTrue(any("physical" in item and "unknown" in item for item in admission["reasons"]))
                self.assertTrue(any(reason in item for item in admission["reasons"]))

    def test_each_required_unknown_metric_holds_all_new_submissions(self):
        for key in SAFE:
            with self.subTest(metric=key), tempfile.TemporaryDirectory() as tmp:
                fixture = SyntheticFanout(Path(tmp), [{**SAFE, key: None}] * 2)
                result = fixture.run()
                self.assertEqual(fixture.submits, [])
                self.assertEqual(result["pending"], ["w1", "w2", "w3"])
                self.assertTrue(all(e["resource_admission"]["available_slots"] == 0 for e in result["scale_log"]))

    def test_unconfigured_optional_and_legacy_diagnostic_metrics_do_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SyntheticFanout(Path(tmp), [{**SAFE, "backlog": None}])
            fixture.complete_at = {"w1": 0, "w2": 0, "w3": 0}
            result = fixture.run(cpu_hold_percent=None, min_disk_free_gb_hold=None,
                                 upload_backlog_hold=None)
            self.assertTrue(result["ok"])
            self.assertEqual(len(fixture.submits), 3)
            self.assertEqual(result["percentage_policy"], "diagnostic_only")

    def test_zero_running_hold_returns_then_recovery_can_submit_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SyntheticFanout(Path(tmp), [{**SAFE, "output_free_bytes": 5 * GIB}, SAFE])
            held = fixture.run()
            self.assertFalse(held["ok"])
            self.assertEqual(held["iterations"], 1)
            self.assertEqual(fixture.submits, [])
            self.assertEqual(held["still_running"], [])
            # 原次零提交且已返回 HOLD，下一次有效采样可正常准入；没有未知原 job 被重投。
            fixture.complete_at = {"w1": 1, "w2": 1, "w3": 1}
            result = fixture.run(healthy_samples_for_scale_up=5)
            self.assertTrue(result["ok"])
            self.assertEqual(fixture.submits, [(1, "w1"), (1, "w2"), (1, "w3")])
            self.assertEqual(result["max_parallel"], 3)
            self.assertEqual([self.admits(x) for x in fixture.snapshots], [False, True])

    def test_existing_jobs_drain_and_unknown_original_job_never_resubmits(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SyntheticFanout(Path(tmp), [SAFE, {**SAFE, "physical_available_bytes": GIB},
                                                 {**SAFE, "physical_available_bytes": None, "output_free_bytes": 5 * GIB}, SAFE])
            fixture.complete_at = {"w1": 1, "w2": 3, "w3": 3}
            fixture.raise_at = {(1, "original-w2")}
            fixture.unknown_at = {(2, "original-w2")}
            result = fixture.run(max_parallel=2, max_parallel_cap=2)
            self.assertTrue(result["ok"])
            self.assertEqual(fixture.submits, [(0, "w1"), (0, "w2"), (3, "w3")])
            self.assertEqual(fixture.registrations, [("w1", "original-w1"), ("w2", "original-w2"), ("w3", "original-w3")])
            self.assertEqual([self.admits(x) for x in fixture.snapshots], [True, False, False, True])
            self.assertIn((1, "original-w1"), fixture.polls)
            self.assertIn((2, "original-w2"), fixture.polls)
            self.assertEqual(result["terminal_failures"], [])
            self.assertTrue(any("UNKNOWN transport" in x["text"] for x in result["progress_log"]))
            self.assertTrue(any("TimeoutError" in x["text"] for x in result["progress_log"]))

    def test_hold_resets_expansion_streak_but_not_existing_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SyntheticFanout(Path(tmp), [SAFE, {**SAFE, "output_free_bytes": 5 * GIB}, SAFE, SAFE], count=2)
            fixture.complete_at = {"w1": 3, "w2": 3}
            result = fixture.run(max_parallel=1, max_parallel_cap=2, healthy_samples_for_scale_up=2)
            self.assertTrue(result["ok"])
            self.assertEqual(fixture.submits, [(0, "w1"), (3, "w2")])
            self.assertEqual([x["iteration"] for x in result["scale_log"] if x["action"] == "scale_up"], [3])


if __name__ == "__main__":
    unittest.main()
