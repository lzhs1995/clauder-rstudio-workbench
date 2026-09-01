from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from clauder_workbench.fanout import load_fanout_contract, run_fanout
from clauder_workbench.resource import decide_resource_gate


def write_contract(root: Path, worker_count: int = 7) -> Path:
    workers = []
    for i in range(1, worker_count + 1):
        wid = f"w{i}"
        code = root / f"worker_{wid}.R"
        code.write_text(f"cat('{wid}')\n", encoding="utf-8")
        workers.append(
            {
                "id": wid,
                "code_file": str(code),
                "expected_state": f"state_{wid}.json",
                "expected_manifest": f"manifest_{wid}.csv",
                "expected_validation": f"validation_{wid}.csv",
            }
        )
    contract = root / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "task_key": "cpu-v044",
                "artifacts": {"output_root": str(root)},
                "resource_gate": {
                    "memory_scale_up_percent": 70,
                    "memory_hold_percent": 80,
                    "cpu_scale_up_percent": 75,
                    "cpu_hold_percent": 90,
                    "min_disk_free_gb_scale_up": 200,
                    "min_disk_free_gb_hold": 150,
                    "upload_backlog_hold": 2,
                    "healthy_samples_for_scale_up": 5,
                },
                "workers": workers,
            }
        ),
        encoding="utf-8",
    )
    return contract


def complete(root: Path, wid: str) -> None:
    (root / f"state_{wid}.json").write_text('{"stage":"complete"}', encoding="utf-8")
    (root / f"manifest_{wid}.csv").write_text(f"id,ok\n{wid},TRUE\n", encoding="utf-8")
    (root / f"validation_{wid}.csv").write_text(f"id,ok\n{wid},TRUE\n", encoding="utf-8")


def worker_id_from_code(code: str, count: int) -> str:
    return next(wid for wid in (f"w{i}" for i in range(1, count + 1)) if f"worker_{wid}.R" in code)


class CpuAwareAutoScaleTests(unittest.TestCase):
    def test_requires_five_healthy_samples_before_scale_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = load_fanout_contract(write_contract(root))

            def submit(code: str) -> dict:
                wid = worker_id_from_code(code, 7)
                complete(root, wid)
                return {"ok": True, "job_id": f"job-{wid}", "text": "started"}

            result = run_fanout(
                contract,
                submit_fn=submit,
                max_parallel=1,
                max_parallel_cap=3,
                auto_scale=True,
                mem_probe_fn=lambda: 60.0,
                cpu_probe_fn=lambda: 50.0,
                disk_probe_fn=lambda: 300.0,
                upload_backlog_probe_fn=lambda: 0,
                poll_interval_sec=0,
                sleep_fn=lambda _: None,
                max_iterations=30,
            )
            self.assertTrue(result["ok"])
            scale_events = [event for event in result["scale_log"] if event["action"] == "scale_up"]
            self.assertTrue(scale_events)
            self.assertGreaterEqual(scale_events[0]["iteration"], 4)
            self.assertLessEqual(result["max_parallel"], 3)

    def test_cpu_and_upload_backlog_throttle_without_killing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = load_fanout_contract(write_contract(root, worker_count=3))
            submitted = []

            def submit(code: str) -> dict:
                wid = worker_id_from_code(code, 3)
                submitted.append(wid)
                complete(root, wid)
                return {"ok": True, "job_id": f"job-{wid}", "text": "started"}

            result = run_fanout(
                contract,
                submit_fn=submit,
                max_parallel=3,
                auto_scale=True,
                mem_probe_fn=lambda: 60.0,
                cpu_probe_fn=lambda: 95.0,
                disk_probe_fn=lambda: 300.0,
                upload_backlog_probe_fn=lambda: 2,
                poll_interval_sec=0,
                sleep_fn=lambda _: None,
                max_iterations=20,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(submitted, ["w1", "w2", "w3"])
            self.assertTrue(any(event["action"] == "throttle" for event in result["scale_log"]))
            self.assertFalse(any(event["action"] == "scale_up" for event in result["scale_log"]))

    def test_resource_gate_reports_cpu_disk_and_backlog(self) -> None:
        decision = decide_resource_gate(
            current_parallel=1,
            memory_threshold=80,
            memory_override=60,
            cpu_scale_up_percent=75,
            cpu_hold_percent=90,
            cpu_override=91,
            min_disk_free_gb_scale_up=200,
            min_disk_free_gb_hold=150,
            disk_free_gb_override=140,
            upload_backlog=2,
            upload_backlog_hold=2,
        )
        self.assertEqual(decision["decision"], "hold")
        self.assertEqual(decision["cpu_used_percent"], 91)
        self.assertEqual(decision["disk_free_gb"], 140)
        self.assertEqual(decision["upload_backlog"], 2)
        self.assertTrue(any("cpu" in reason for reason in decision["reasons"]))
        self.assertTrue(any("disk" in reason for reason in decision["reasons"]))
        self.assertTrue(any("upload backlog" in reason for reason in decision["reasons"]))


if __name__ == "__main__":
    unittest.main()
