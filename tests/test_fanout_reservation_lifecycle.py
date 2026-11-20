import tempfile
import time
import unittest
from pathlib import Path

from clauder_workbench.fanout import run_fanout


class ReservationLifecycleTests(unittest.TestCase):
    def test_complete_files_do_not_release_still_running_reservation(self):
        self._assert_reservation_retained("Job is still running")

    def test_empty_poll_does_not_release_running_reservation(self):
        self._assert_reservation_retained("")

    def test_missing_job_does_not_release_running_reservation(self):
        self._assert_reservation_retained("No job found with ID 'original'.")

    def _assert_reservation_retained(self, poll_text):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            contract = {"artifacts": {"output_root": td}, "workers": [
                {"id": str(i), "code": str(i), "expected_state": f"s{i}.json",
                 "expected_manifest": f"m{i}.csv", "expected_validation": f"v{i}.csv"}
                for i in range(2)]}
            submitted = []

            def submit(code):
                submitted.append(code)
                (root / f"s{code}.json").write_text('{"status":"complete"}')
                for prefix in ("m", "v"):
                    (root / f"{prefix}{code}.csv").write_text("ok\ntrue\n")
                return {"ok": True, "job_id": f"job-{code}"}

            def sample():
                return {"host_verified": True, "host_id": "synthetic", "session_pid": 77,
                        "output_root": td, "sampled_at": time.time(),
                        "physical_available_bytes": 2 * 1024**3, "commit_available_bytes": 9 * 1024**3,
                        "logical_processors": 8, "output_free_bytes": 9 * 1024**3}

            result = run_fanout(contract, submit_fn=submit, resource_probe_fn=sample,
                                poll_fn=lambda _: {"ok": True, "text": poll_text},
                                max_parallel=2, max_iterations=2, poll_interval_sec=0,
                                sleep_fn=lambda _: None)
            self.assertEqual(submitted, ["0"])
            self.assertEqual(result["still_running"], ["0"])
            self.assertEqual(result["done"], [])
            self.assertEqual(result["pending"], ["1"])

    def test_unknown_submission_is_preserved_and_not_retried(self):
        with tempfile.TemporaryDirectory() as td:
            contract = {"artifacts": {"output_root": td}, "workers": [
                {"id": "one", "code": "1+1", "expected_state": "s", "expected_manifest": "m",
                 "expected_validation": "v"}]}
            sample = {"host_verified": True, "host_id": "synthetic", "session_pid": 77,
                      "output_root": td, "sampled_at": time.time(),
                      "physical_available_bytes": 9 * 1024**3, "commit_available_bytes": 9 * 1024**3,
                      "logical_processors": 8, "output_free_bytes": 9 * 1024**3}
            calls = []

            def submit(code):
                calls.append(code)
                return {"ok": False, "status": "UNKNOWN", "submission_attempted": True,
                        "hold": False, "reason": "transport lost after submit"}

            result = run_fanout(contract, submit_fn=submit, resource_probe_fn=lambda: sample,
                                max_iterations=3, sleep_fn=lambda _: None)
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["submit_log"][0]["status"], "UNKNOWN")
            self.assertTrue(result["submit_log"][0]["submission_attempted"])
            self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
