"""仅使用合成轮询；任务终态与任意 R stdout 必须分别判定。"""

from __future__ import annotations

import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench.fanout import run_fanout


GIB = 1024**3
COMMUNICATION_ERRORS = (
    "Async job error: Error communicating with RStudio: HTTP 503 Service Unavailable",
    "Async job error: Error communicating with RStudio: Connection reset by peer",
    "Async job error: Error communicating with RStudio: Expecting value: line 1 column 1 (char 0)",
)
MISSING_JOBS = (
    "Job original-0 not found",
    "No job found with ID 'original-0'. It may have completed or been removed.",
)


class RealTransportForbidden(BaseException):
    """普通 Exception 捕获不能吞掉测试隔离失败。"""


class FanoutPollLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        # 未注入的 MCP 入口与最底层 stdio 都在启动真实进程前失败。
        targets = ["clauder_workbench.mcp_client._session_run"]
        if importlib.util.find_spec("mcp") is not None:
            targets.append("mcp.client.stdio.stdio_client")
        for target in targets:
            guard = mock.patch(
                target, side_effect=RealTransportForbidden("real MCP transport forbidden")
            )
            blocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(blocked.assert_not_called)

    def _run(self, reply_fn, *, max_iterations=3, write_artifacts=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = {
                "artifacts": {"output_root": directory},
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
                        "id": str(index),
                        "code": str(index),
                        "expected_state": f"state-{index}.json",
                        "expected_manifest": f"manifest-{index}.csv",
                        "expected_validation": f"validation-{index}.csv",
                    }
                    for index in range(2)
                ],
            }
            submissions, polls, snapshots = [], [], []
            poll_counts = {}

            def submit(code):
                submissions.append(code)
                if write_artifacts:
                    (root / f"state-{code}.json").write_text(
                        '{"status":"complete"}', encoding="utf-8"
                    )
                    for prefix in ("manifest", "validation"):
                        (root / f"{prefix}-{code}.csv").write_text(
                            "ok\nTRUE\n", encoding="utf-8"
                        )
                return {"ok": True, "job_id": f"original-{code}"}

            def poll(job_id):
                polls.append(job_id)
                poll_counts[job_id] = poll_counts.get(job_id, 0) + 1
                return reply_fn(job_id, poll_counts[job_id])

            def sample():
                return {
                    "sampled_at": time.time(),
                    "host_verified": True,
                    "host_id": "synthetic-worker",
                    "session_pid": 1234,
                    "output_root": directory,
                    "physical_available_bytes": 2 * GIB,
                    "commit_available_bytes": 12 * GIB,
                    "logical_processors": 8,
                    "output_free_bytes": 12 * GIB,
                }

            result = run_fanout(
                contract,
                submit_fn=submit,
                poll_fn=poll,
                resource_probe_fn=sample,
                progress_callback=snapshots.append,
                max_parallel=2,
                max_iterations=max_iterations,
                poll_interval_sec=0,
                sleep_fn=lambda _: None,
            )
        return result, submissions, polls, snapshots

    def _assert_held(self, reply):
        result, submissions, polls, snapshots = self._run(lambda *_: dict(reply))
        self.assertEqual(result["still_running"], ["0"])
        self.assertEqual(result["done"], [])
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["terminal_failures"], [])
        self.assertEqual(result["pending"], ["1"])
        self.assertEqual(submissions, ["0"])
        self.assertGreaterEqual(len(polls), 3)
        self.assertEqual(set(polls), {"original-0"})
        self.assertTrue(snapshots)
        for snapshot in snapshots:
            self.assertEqual(
                [(worker["id"], worker["job_id"]) for worker in snapshot["running"]],
                [("0", "original-0")],
            )
        later_admission = [
            entry for entry in result["admission_log"] if entry["iteration"] > 0
        ]
        self.assertTrue(later_admission)
        self.assertTrue(all(entry["running"] == 1 for entry in later_admission))
        self.assertTrue(all(entry["available_slots"] == 0 for entry in later_admission))

    def test_http_communication_error_retains_job_and_reservation(self):
        self._assert_held({"ok": True, "text": COMMUNICATION_ERRORS[0]})

    def test_reset_communication_error_retains_job_and_reservation(self):
        self._assert_held({"ok": True, "text": COMMUNICATION_ERRORS[1]})

    def test_json_communication_error_retains_job_and_reservation(self):
        self._assert_held({"ok": True, "text": COMMUNICATION_ERRORS[2]})

    def test_job_not_found_retains_job_and_reservation(self):
        for ok in (True, False):
            with self.subTest(ok=ok):
                self._assert_held({"ok": ok, "text": MISSING_JOBS[0]})

    def test_no_job_found_retains_job_and_reservation(self):
        self._assert_held({"ok": True, "text": MISSING_JOBS[1]})

    def test_unproven_poll_never_spends_reserved_slot(self):
        for text in ("", "Waiting for result", "TimeoutError: response timed out",
                     "Async job error: calculation failed", "Async job cancelled",
                     "ordinary stdout without a status"):
            with self.subTest(text=text):
                self._assert_held({"ok": True, "text": text})

    def test_unknown_then_completed_uses_status_not_error_words_in_stdout(self):
        for text in COMMUNICATION_ERRORS + MISSING_JOBS:
            with self.subTest(text=text):
                def reply(job_id, count):
                    if job_id == "original-0" and count == 1:
                        return {"ok": True, "text": text}
                    return {
                        "ok": True, "job_id": job_id, "status": "completed",
                        "success": True, "text": text,
                    }

                result, submissions, polls, snapshots = self._run(reply)
                self.assertEqual(
                    [(worker["id"], worker["job_id"]) for worker in snapshots[0]["running"]],
                    [("0", "original-0")],
                )
                self.assertEqual(snapshots[0]["done"], [])
                self.assertTrue(result["ok"])
                self.assertEqual(result["done"], ["0", "1"])
                self.assertEqual(submissions, ["0", "1"])
                self.assertEqual(polls[:2], ["original-0", "original-0"])
                self.assertEqual(result["still_running"], [])
                self.assertEqual(result["terminal_failures"], [])

    def test_completed_stdout_is_not_a_poll_control_channel(self):
        for text in COMMUNICATION_ERRORS + MISSING_JOBS + (
            "Async job cancelled", "Job is still running", "unknown", ""
        ):
            with self.subTest(text=text):
                result, submissions, _, _ = self._run(
                    lambda job_id, _: {
                        "ok": True, "job_id": job_id, "status": "completed",
                        "success": True, "text": text,
                    }
                )
                self.assertTrue(result["ok"])
                self.assertEqual(result["done"], ["0", "1"])
                self.assertEqual(result["failed"], [])
                self.assertEqual(submissions, ["0", "1"])

    def _assert_terminal_failure(self, status, **updates):
        result, submissions, polls, _ = self._run(
            lambda job_id, _: {
                "ok": True, "job_id": job_id, "status": status,
                "text": "unprefixed task outcome", **updates,
            }
        )
        self.assertEqual(result["still_running"], [])
        self.assertEqual(result["failed"], ["0"])
        self.assertEqual(result["done"], [])
        self.assertEqual(result["pending"], ["1"])
        self.assertEqual(submissions, ["0"])
        self.assertEqual(set(polls), {"original-0"})
        self.assertEqual(result["terminal_failures"][0]["job_id"], "original-0")

    def test_explicit_error_releases_reservation_and_stops_batch(self):
        self._assert_terminal_failure("error")

    def test_explicit_cancelled_releases_reservation_and_stops_batch(self):
        self._assert_terminal_failure("cancelled")

    def test_completion_aliases_require_boolean_success(self):
        for status in ("complete", "completed", "done"):
            for success in (None, 1, "true"):
                with self.subTest(status=status, success=success):
                    self._assert_held({
                        "ok": True, "job_id": "original-0", "status": status,
                        "success": success, "text": "ordinary stdout",
                    })
            with self.subTest(status=status, success="missing"):
                self._assert_held({
                    "ok": True, "job_id": "original-0", "status": status,
                    "text": "ordinary stdout",
                })

    def test_completion_success_false_is_a_task_error(self):
        for status in ("complete", "completed", "done"):
            with self.subTest(status=status):
                self._assert_terminal_failure(status, success=False)

    def test_completion_aliases_with_boolean_success_release_reservation(self):
        for status in ("complete", "completed", "done"):
            with self.subTest(status=status):
                result, submissions, _, _ = self._run(
                    lambda job_id, _: {
                        "ok": True, "job_id": job_id, "status": status,
                        "success": True, "text": "ordinary stdout",
                    }
                )
                self.assertTrue(result["ok"])
                self.assertEqual(result["done"], ["0", "1"])
                self.assertEqual(submissions, ["0", "1"])

    def test_status_for_missing_or_different_job_is_unproven(self):
        for job_id in (None, "another-job"):
            for status in ("completed", "error", "cancelled"):
                with self.subTest(job_id=job_id, status=status):
                    reply = {
                        "ok": True, "status": status, "success": True,
                        "text": "ordinary stdout",
                    }
                    if job_id is not None:
                        reply["job_id"] = job_id
                    self._assert_held(reply)

    def test_failed_transport_with_terminal_status_is_unproven(self):
        for status in ("completed", "error", "cancelled"):
            with self.subTest(status=status):
                self._assert_held({
                    "ok": False, "job_id": "original-0", "status": status,
                    "success": True,
                    "text": "Async job error: Error communicating with RStudio: reset",
                })

    def test_unknown_status_cannot_release_reservation(self):
        for status in ("UNKNOWN", "running", "pending", "unrecognized"):
            with self.subTest(status=status):
                self._assert_held({
                    "ok": True, "job_id": "original-0", "status": status,
                    "success": True,
                    "text": "ordinary stdout",
                })

    def test_completed_process_alone_does_not_claim_valid_artifacts(self):
        result, submissions, _, _ = self._run(
            lambda job_id, _: {
                "ok": True, "job_id": job_id, "status": "completed",
                "success": True, "text": "done",
            },
            write_artifacts=False,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["done"], [])
        self.assertEqual(submissions, ["0"])


if __name__ == "__main__":
    unittest.main()
