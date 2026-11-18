from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from clauder_workbench.fanout import async_poll_terminal_error, load_fanout_contract, run_fanout


def _resource_sample(root: Path, **updates: object) -> dict:
    # 合成目标主机样本；测试不读取实际机器资源或连接 RStudio。
    sample = {
        "sampled_at": time.time(),
        "host_verified": True,
        "host_id": "synthetic-worker",
        "session_pid": 1234,
        "output_root": str(root),
        "physical_available_bytes": 32 * 1024 ** 3,
        "commit_available_bytes": 64 * 1024 ** 3,
        "logical_processors": 16,
        "output_free_bytes": 512 * 1024 ** 3,
        "memory_used_percent": 90.0,
    }
    sample.update(updates)
    return sample


class FanoutTerminalPollTests(unittest.TestCase):
    def test_only_explicit_job_terminal_messages_are_classified(self) -> None:
        self.assertIsNone(async_poll_terminal_error({"ok": True, "text": "Async job error: boom"}))
        self.assertIsNone(async_poll_terminal_error({"ok": False, "text": "ConnectionError: bridge reset"}))
        self.assertIsNone(async_poll_terminal_error({"ok": True, "text": "Job a is still running"}))
        self.assertIsNotNone(async_poll_terminal_error({
            "ok": True, "job_id": "original-job", "status": "error", "text": "boom",
        }, "original-job"))

    def test_run_fanout_stops_on_async_job_error_without_resubmission(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            worker = root / "worker.R"
            worker.write_text("x <- 1\n", encoding="utf-8")
            contract_path = root / "contract.json"
            contract_path.write_text(json.dumps({
                "task_key": "terminal-error-test",
                "artifacts": {"output_root": str(root)},
                "workers": [{
                    "id": "w1",
                    "code_file": str(worker),
                    "expected_state": "state_w1.json",
                    "expected_manifest": "manifest_w1.csv",
                    "expected_validation": "validation_w1.csv",
                }],
            }), encoding="utf-8")
            submissions = []

            def submit(code: str) -> dict:
                submissions.append(code)
                return {"ok": True, "job_id": "original-job", "text": "started"}

            result = run_fanout(
                load_fanout_contract(contract_path),
                submit_fn=submit, resource_probe_fn=lambda: _resource_sample(root),
                poll_fn=lambda job_id: {
                    "ok": True, "job_id": job_id, "status": "error",
                    "text": "Async job error: postprocess failed",
                },
                poll_interval_sec=0,
                sleep_fn=lambda _: None,
                max_iterations=5,
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["failed"], ["w1"])
            self.assertEqual(len(submissions), 1)
            self.assertEqual(result["terminal_failures"][0]["job_id"], "original-job")


if __name__ == "__main__":
    unittest.main()
