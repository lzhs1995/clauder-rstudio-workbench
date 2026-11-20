from __future__ import annotations

import json
import re
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from clauder_workbench import mcp_client
from clauder_workbench.resource import (
    FanoutResourceProbe,
    _fanout_r_final_peek_code,
    _fanout_r_probe_code,
    fanout_admission,
    normalize_fanout_policy,
)


GIB = 1024 ** 3


def target_sample(**changes):
    sample = {
        "host_id": "worker-host:system:100", "session_pid": 123,
        "session_birth": 500.0, "output_root": "/worker/output",
        "worker_sampled_at": 1.0,
        "physical_available_bytes": 8 * GIB,
        "commit_available_bytes": 8 * GIB,
        "logical_processors": 8, "output_free_bytes": 12 * GIB,
        "memory_used_percent": 90.0,
    }
    return sample | changes


class FakeSession:
    def __init__(self, payloads=None, *, error=False):
        self.payloads = list(payloads or [target_sample()])
        self.error = error
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        text = "connected"
        if name == "execute_r":
            marker = re.search(r'cat\("(FANOUT_RESOURCE_[a-f0-9]+=)"', arguments["code"])[1]
            payload = self.payloads.pop(0) if len(self.payloads) > 1 else self.payloads[0]
            text = "Output:\n" + marker + json.dumps(payload) + "\n"
        elif name == "execute_r_async":
            text = "Job synthetic_job started"
        elif name == "get_async_result":
            return SimpleNamespace(isError=self.error,
                                   structuredContent={"job_id": arguments["job_id"], "status": "running"},
                                   content=[SimpleNamespace(text="still running")])
        return SimpleNamespace(isError=self.error, content=[SimpleNamespace(text=text)])


class WorkerResourceProbeTests(unittest.TestCase):
    def patch_session(self, session):
        async def run(timeout, runner):
            self.assertGreater(timeout, 0)
            return await runner(session, "synthetic-bridge", [])
        return mock.patch.object(mcp_client, "_session_run", side_effect=run)

    def test_target_sample_and_submit_share_selected_route_and_identity(self):
        session = FakeSession()
        with self.patch_session(session):
            probe = FanoutResourceProbe("selected-worker", "/worker/output", timeout=90)
            sample = probe.sample()
            self.assertTrue(sample["host_verified"])
            self.assertEqual(sample["host_id"], "worker-host:system:100")
            self.assertEqual(sample["session_name"], "selected-worker")
            self.assertEqual(sample["resource_transport_class"], "MCP_STDIO_OK")
            self.assertGreater(sample["sampled_at"], sample["worker_sampled_at"])
            self.assertEqual(fanout_admission(sample, {})["decision"], "allow")
            result = probe.submit("synthetic <- TRUE")
        self.assertTrue(result["ok"])
        self.assertEqual(result["transport_class"], "MCP_STDIO_OK")
        self.assertEqual([name for name, _ in session.calls],
                         ["connect_session", "execute_r", "connect_session", "execute_r", "execute_r_async"])
        self.assertTrue(all(args["session_name"] == "selected-worker"
                            for name, args in session.calls if name == "connect_session"))

    def test_sample_timeout_is_short_without_shortening_submission_timeout(self):
        session = FakeSession()
        timeouts = []
        async def run(timeout, runner):
            timeouts.append(timeout)
            return await runner(session, "bridge", [])
        with mock.patch.object(mcp_client, "_session_run", side_effect=run):
            probe = FanoutResourceProbe("selected-worker", "/worker/output", timeout=60)
            self.assertTrue(probe.sample()["host_verified"])
            self.assertTrue(probe.submit("1")["ok"])
            self.assertTrue(probe.poll("synthetic_job")["ok"])
        self.assertEqual(timeouts, [10, 60, 60])

    def test_normalized_target_path_keeps_original_requested_binding(self):
        session = FakeSession([target_sample(output_root="/resolved/output")])
        with self.patch_session(session):
            probe = FanoutResourceProbe("selected", "/linked/output")
            sample = probe.sample()
        self.assertEqual(sample["output_root"], "/resolved/output")
        self.assertEqual(sample["requested_output_root"], "/linked/output")

    def test_poll_rebinds_original_selector_and_checks_job_without_waiting(self):
        session = FakeSession()
        with self.patch_session(session):
            probe = FanoutResourceProbe("non-default-worker", "/worker/output")
            probe.sample()
            result = probe.poll("original_job")
        self.assertTrue(result["ok"])
        self.assertEqual(result["job_id"], "original_job")
        self.assertEqual([name for name, _ in session.calls],
                         ["connect_session", "execute_r", "connect_session", "execute_r", "get_async_result"])
        self.assertEqual(session.calls[-1][1], {"job_id": "original_job", "wait_s": 0})
        self.assertEqual(session.calls[-3][1], {"session_name": "non-default-worker"})

    def test_poll_identity_change_and_unknown_keep_original_job_without_call(self):
        session = FakeSession([target_sample(), target_sample(session_pid=999)])
        with self.patch_session(session):
            probe = FanoutResourceProbe("selected", "/worker/output")
            self.assertFalse(probe.poll("original_job")["ok"])
            probe.sample()
            result = probe.poll("original_job")
        self.assertFalse(result["ok"])
        self.assertEqual(result["job_id"], "original_job")
        self.assertIn("identity changed", result["reason"])
        self.assertNotIn("get_async_result", [name for name, _ in session.calls])
        self.assertNotIn("execute_r_async", [name for name, _ in session.calls])

    def test_no_implicit_session_or_output_root_and_no_probe_before_sample(self):
        session = FakeSession()
        with self.patch_session(session):
            for selector, root in [("", "/worker/output"), ("selected", "")]:
                probe = FanoutResourceProbe(selector, root)
                self.assertFalse(probe.sample()["host_verified"])
                self.assertFalse(probe.submit("1")["ok"])
            self.assertFalse(FanoutResourceProbe("selected", "/worker/output").submit("1")["ok"])
        self.assertFalse(session.calls)

    def test_timeout_and_tool_error_hold_without_local_fallback(self):
        async def timeout(*_args, **_kwargs):
            return {"ok": False, "reason": "TimeoutError"}
        for patcher in [mock.patch.object(mcp_client, "_session_run", side_effect=timeout),
                        self.patch_session(FakeSession(error=True))]:
            with patcher, mock.patch("clauder_workbench.resource.memory_used_percent", side_effect=AssertionError("local probe")):
                probe = FanoutResourceProbe("selected", "/worker/output")
                sample = probe.sample()
                self.assertFalse(sample["host_verified"])
                self.assertEqual(fanout_admission(sample, {})["available_slots"], 0)
                self.assertFalse(probe.submit("1")["ok"])

    def test_host_pid_birth_and_output_changes_block_before_submit(self):
        for changes in [{"host_id": "different-host"}, {"session_pid": 124},
                        {"session_birth": 501.0}, {"output_root": "/different/output"}]:
            with self.subTest(changes=changes):
                session = FakeSession([target_sample(), target_sample(**changes)])
                with self.patch_session(session):
                    probe = FanoutResourceProbe("selected", "/worker/output")
                    self.assertTrue(probe.sample()["host_verified"])
                    result = probe.submit("1")
                self.assertFalse(result["ok"])
                self.assertTrue(result["hold"])
                self.assertFalse(result["submission_attempted"])
                self.assertIn("identity changed", result["reason"])
                self.assertNotIn("execute_r_async", [name for name, _ in session.calls])

    def test_identity_change_between_samples_invalidates_old_sample(self):
        session = FakeSession([target_sample(), target_sample(session_pid=124)])
        with self.patch_session(session):
            probe = FanoutResourceProbe("selected", "/worker/output")
            self.assertTrue(probe.sample()["host_verified"])
            self.assertFalse(probe.sample()["host_verified"])
            self.assertFalse(probe.submit("1")["ok"])

    def test_target_insufficient_even_when_orchestrator_would_be_healthy(self):
        session = FakeSession([target_sample(physical_available_bytes=GIB // 2)])
        with self.patch_session(session), mock.patch("clauder_workbench.resource.memory_used_percent", return_value=1), mock.patch(
            "clauder_workbench.resource.disk_free_gb", return_value=1000
        ):
            sample = FanoutResourceProbe("selected", "/worker/output").sample()
        admission = fanout_admission(sample, {})
        self.assertEqual(admission["available_slots"], 0)
        self.assertIn("physical bytes insufficient", admission["checks"]["physical"]["reason"])

    def test_incomplete_commit_and_stale_sample_block_submission(self):
        for changes in [{"commit_available_bytes": None}, {"logical_processors": None}]:
            session = FakeSession([target_sample(**changes)])
            with self.patch_session(session):
                probe = FanoutResourceProbe("selected", "/worker/output")
                self.assertTrue(probe.sample()["host_verified"])
                self.assertFalse(probe.submit("1")["ok"])
            self.assertNotIn("execute_r_async", [name for name, _ in session.calls])
        session = FakeSession()
        with self.patch_session(session):
            probe = FanoutResourceProbe("selected", "/worker/output", sample_max_age_sec=1)
            sample = probe.sample()
            with mock.patch("clauder_workbench.resource.time.time", return_value=sample["sampled_at"] + 2):
                self.assertFalse(probe.submit("1")["ok"])

    def test_before_submission_timeout_is_hold(self):
        session = FakeSession()
        invocation = []
        async def run(_timeout, runner):
            invocation.append(True)
            if len(invocation) > 1:
                return {"ok": False, "reason": "TimeoutError"}
            return await runner(session, "bridge", [])
        with mock.patch.object(mcp_client, "_session_run", side_effect=run):
            probe = FanoutResourceProbe("selected", "/worker/output")
            probe.sample()
            result = probe.submit("1")
            self.assertFalse(result["ok"])
            self.assertTrue(result["hold"])
            self.assertFalse(result["submission_attempted"])
            self.assertFalse(probe.submit("1")["ok"])
        self.assertEqual(len(invocation), 2)

    def test_unknown_submit_is_not_retried_even_after_new_sample(self):
        class UnknownSession(FakeSession):
            async def call_tool(self, name, arguments):
                if name == "execute_r_async":
                    self.calls.append((name, arguments))
                    raise TimeoutError("response lost after request")
                return await super().call_tool(name, arguments)
        session = UnknownSession()
        with self.patch_session(session):
            probe = FanoutResourceProbe("selected", "/worker/output")
            probe.sample()
            result = probe.submit("1")
            self.assertFalse(result["ok"])
            self.assertFalse(result["hold"])
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertTrue(result["submission_attempted"])
            probe.sample()
            again = probe.submit("1")
            self.assertEqual(again["status"], "UNKNOWN")
        self.assertEqual(sum(name == "execute_r_async" for name, _ in session.calls), 1)

    def test_sample_expiring_during_identity_check_prevents_submission(self):
        clock = [1000.0]
        class DelayedIdentitySession(FakeSession):
            async def call_tool(self, name, arguments):
                if name == "execute_r" and any(item[0] == "execute_r" for item in self.calls):
                    clock[0] += 2
                return await super().call_tool(name, arguments)
        session = DelayedIdentitySession()
        with self.patch_session(session), mock.patch("clauder_workbench.resource.time.time", side_effect=lambda: clock[0]):
            probe = FanoutResourceProbe("selected", "/worker/output", sample_max_age_sec=1)
            probe.sample()
            result = probe.submit("1")
        self.assertFalse(result["ok"])
        self.assertTrue(result["hold"])
        self.assertIn("became stale", result["reason"])
        self.assertNotIn("execute_r_async", [name for name, _ in session.calls])

    def test_probe_code_uses_target_volume_and_bounded_commit_read(self):
        code = _fanout_r_probe_code("synthetic=", "C:/output/MARKER/RESOURCE_CODE")
        self.assertIn('output_path <- "C:/output/MARKER/RESOURCE_CODE"', code)
        self.assertTrue(code.startswith("local({"))
        self.assertIn("ps::ps_system_memory()", code)
        self.assertIn("ps::ps_disk_usage(target)$available", code)
        self.assertIn("CommitLimit", code)
        self.assertIn("CommittedBytes", code)
        self.assertIn("timeout = 3", code)
        self.assertNotIn("execute_r_async", code)


class FanoutAdmissionMathTests(unittest.TestCase):
    def sample(self, **changes):
        return target_sample(host_verified=True, sampled_at=time.time()) | changes

    def test_high_percentage_does_not_replace_byte_gates(self):
        admission = fanout_admission(self.sample(memory_used_percent=99), {})
        self.assertEqual(admission["decision"], "allow")
        self.assertEqual(admission["available_slots"], 7)
        self.assertTrue(all(check["ok"] for check in admission["checks"].values()))

    def test_each_budget_independently_holds_with_reason(self):
        for field, key in [("physical_available_bytes", "physical"), ("commit_available_bytes", "commit"),
                           ("logical_processors", "processors"), ("output_free_bytes", "output")]:
            with self.subTest(field=field):
                admission = fanout_admission(self.sample(**{field: 0}), {})
                self.assertEqual(admission["available_slots"], 0)
                self.assertFalse(admission["checks"][key]["ok"])
                self.assertIn("insufficient", admission["checks"][key]["reason"])

    def test_running_reservations_deduct_all_four_dimensions(self):
        admission = fanout_admission(self.sample(), {}, running_count=3)
        self.assertEqual(admission["available_slots"], 4)
        self.assertEqual(admission["reservations"]["scope"], "this_fanout_batch_only")
        for key in ("physical", "commit", "output"):
            self.assertEqual(admission["checks"][key]["reserved"], 3 * GIB)
        self.assertEqual(admission["checks"]["processors"]["reserved"], 3)

    def test_invalid_samples_never_allow_one(self):
        for sample in [None, {}, self.sample(sampled_at=1), self.sample(sampled_at=time.time() + 30),
                       self.sample(host_verified=False), self.sample(session_pid=True),
                       self.sample(physical_available_bytes=float("nan")), self.sample(commit_available_bytes=None)]:
            with self.subTest(sample=sample):
                admission = fanout_admission(sample, {})
                self.assertEqual(admission["available_slots"], 0)
                self.assertEqual(admission["decision"], "hold")
                self.assertTrue(any("unknown" in reason for reason in admission["reasons"]))

    def test_invalid_contract_numbers_are_rejected(self):
        for key, value in [("worker_mem_gib", True), ("worker_commit_gib", 0),
                           ("reserve_mem_gib", -1), ("worker_output_gib", float("inf")),
                           ("worker_processors", 1.5), ("sample_max_age_sec", float("nan")),
                           ("worker_mem_gib", 1e308), ("worker_mem_gib", 10 ** 1000)]:
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError):
                    normalize_fanout_policy({key: value})


class PollStatusSession(FakeSession):
    def __init__(self, *, structured=None, text="synthetic output", final=None, poll_error=False,
                 peek_error=False, peek_timeout=False):
        super().__init__()
        self.structured = structured
        self.text = text
        self.final = final
        self.poll_error = poll_error
        self.peek_error = peek_error
        self.peek_timeout = peek_timeout

    async def call_tool(self, name, arguments):
        if name == "get_async_result":
            self.calls.append((name, arguments))
            return SimpleNamespace(isError=self.poll_error, structuredContent=self.structured,
                                   content=[SimpleNamespace(text=self.text)])
        if name == "execute_r" and "FANOUT_FINAL_" in arguments["code"]:
            self.calls.append((name, arguments))
            if self.peek_timeout:
                raise TimeoutError("terminal cache unavailable")
            marker = re.search(r'cat\("(FANOUT_FINAL_[a-f0-9]+=)"', arguments["code"])[1]
            text = "Output:\n" + marker + json.dumps(self.final) + "\n"
            return SimpleNamespace(isError=self.peek_error, content=[SimpleNamespace(text=text)])
        return await super().call_tool(name, arguments)


class WorkerPollStatusTests(unittest.TestCase):
    def poll(self, session):
        async def run(timeout, runner):
            return await runner(session, "synthetic-bridge", [])
        with mock.patch.object(mcp_client, "_session_run", side_effect=run):
            probe = FanoutResourceProbe("selected-worker", "/worker/output")
            self.assertTrue(probe.sample()["host_verified"])
            return probe.poll("original_job")

    def test_structured_success_ignores_legal_stdout_error_words(self):
        for text in ["Error: legitimate printed label", "Async job error: printed example",
                     "Job original_job not found", "No job found with ID 'original_job'."]:
            with self.subTest(text=text):
                session = PollStatusSession(structured={"job_id": "original_job", "status": "completed", "success": True}, text=text)
                result = self.poll(session)
                self.assertTrue(result["ok"])
                self.assertEqual(result["status"], "completed")
                self.assertTrue(result["success"])
                self.assertEqual(result["text"], text)
                self.assertFalse(any("FANOUT_FINAL_" in args.get("code", "") for _, args in session.calls))

    def test_structured_status_requires_exact_job_and_explicit_success(self):
        payloads = [None, {}, {"job_id": "other", "status": "error"},
                    {"status": "complete", "success": True},
                    {"job_id": "original_job", "status": "completed"},
                    {"job_id": "original_job", "status": "completed", "success": "true"},
                    {"job_id": "original_job", "status": "not_found"}]
        for payload in payloads:
            with self.subTest(payload=payload):
                result = self.poll(PollStatusSession(structured=payload))
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["job_id"], "original_job")

    def test_structured_errors_cancel_and_running_are_distinct(self):
        for payload, expected in [({"status": "complete", "success": False}, "error"),
                                  ({"status": "failed"}, "error"), ({"status": "error"}, "error"),
                                  ({"status": "cancelled"}, "cancelled"), ({"status": "running"}, "running")]:
            with self.subTest(payload=payload):
                result = self.poll(PollStatusSession(structured={"job_id": "original_job", **payload}))
                self.assertEqual(result["status"], expected)

    def test_mcp_error_overrides_structured_terminal(self):
        session = PollStatusSession(structured={"job_id": "original_job", "status": "complete", "success": True}, poll_error=True)
        result = self.poll(session)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(any("FANOUT_FINAL_" in args.get("code", "") for _, args in session.calls))

    def test_legacy_cache_success_and_failure_ignore_poll_text(self):
        for success, expected in [(True, "completed"), (False, "error")]:
            session = PollStatusSession(text="Error: legitimate output; Async job error: printed example",
                                        final={"job_id": "original_job", "status": "complete", "success": success})
            result = self.poll(session)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["status_source"], "clauder_final_cache")
            self.assertEqual([name for name, _ in session.calls],
                             ["connect_session", "execute_r", "connect_session", "execute_r", "get_async_result", "execute_r"])

    def test_legacy_missing_unverified_and_timeout_keep_unknown(self):
        for session in [
            PollStatusSession(text="Async job error: Error communicating with RStudio: reset", final={"job_id": "original_job", "status": "unknown"}),
            PollStatusSession(text="Job original_job not found"),
            PollStatusSession(text="No job found with ID 'original_job'."),
            PollStatusSession(final={"job_id": "other", "status": "complete", "success": True}),
            PollStatusSession(final={"job_id": "original_job", "status": "complete"}),
            PollStatusSession(final={"job_id": "original_job", "status": "error", "success": False}),
            PollStatusSession(final={"job_id": "original_job", "status": "cancelled", "success": False}),
            PollStatusSession(peek_error=True), PollStatusSession(peek_timeout=True),
        ]:
            with self.subTest(session=session):
                result = self.poll(session)
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["job_id"], "original_job")
                self.assertNotIn("execute_r_async", [name for name, _ in session.calls])

    def test_terminal_cache_probe_is_read_only_and_excludes_stdout(self):
        code = _fanout_r_final_peek_code("synthetic=", "original_job")
        self.assertTrue(code.startswith("local({"))
        self.assertIn('exists(".claude_bg_jobs", envir = ns, inherits = FALSE)', code)
        self.assertIn('identical(metadata[["job_id"]], requested_id)', code)
        self.assertIn('entry[["final"]]', code)
        self.assertIn('final[["success"]]', code)
        self.assertIn('identical(status, "complete")', code)
        for forbidden in ["check_background_job(", "$is_alive(", "$get_result(", "$kill(",
                          'final[["output"]]', 'final[["error"]]', "assign(", "rm("]:
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
