from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from clauder_workbench.fanout import async_poll_terminal_error, load_fanout_contract, run_fanout


class FanoutTerminalPollTests(unittest.TestCase):
    def test_only_explicit_job_terminal_messages_are_classified(self) -> None:
        self.assertIsNotNone(async_poll_terminal_error({"ok": True, "text": "Async job error: boom"}))
        self.assertIsNone(async_poll_terminal_error({"ok": False, "text": "ConnectionError: bridge reset"}))
        self.assertIsNone(async_poll_terminal_error({"ok": True, "text": "Job a is still running"}))

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
                submit_fn=submit,
                poll_fn=lambda _: {"ok": True, "text": "Async job error: postprocess failed"},
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
