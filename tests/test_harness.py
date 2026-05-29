from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench.artifacts import artifact_ok, check_artifacts, parse_requirement
from clauder_workbench.cli import (
    _expected_clients,
    _job_complete_ok,
    _p6_durable_violations,
    _resource_gate_ok,
    _state_is_complete,
    build_parser,
    cmd_async_guard,
    cmd_completion_check,
    parse_requirements,
)
from clauder_workbench.evidence import build_evidence, stable_task_key, write_evidence
from clauder_workbench.inflight import archive_inflight, load_inflight, write_inflight
from clauder_workbench.mcp_client import _retry_if_cold_timeout, extract_job_id
from clauder_workbench.resource import decide_resource_gate
from clauder_workbench.transport import classify_transport


class HarnessUnitTests(unittest.TestCase):
    def test_task_key_is_stable(self) -> None:
        a = stable_task_key("C:/Project", "Task", "IamKing", "native")
        b = stable_task_key("c:/project", "task", "iamking", "native")
        self.assertEqual(a, b)

    def test_task_key_changes_with_session(self) -> None:
        a = stable_task_key("C:/Project", "Task", "A", "native")
        b = stable_task_key("C:/Project", "Task", "B", "native")
        self.assertNotEqual(a, b)

    def test_transport_native_required_blocks_http_hint(self) -> None:
        klass, _ = classify_transport(http_ok=True, native_required=True)
        self.assertEqual(klass, "BLOCKED")

    def test_transport_hints_are_ignored_without_explicit_permission(self) -> None:
        klass, reasons = classify_transport(native_ok=True)
        self.assertEqual(klass, "BLOCKED")
        self.assertIn("ignored", " ".join(reasons))

    def test_transport_allow_agent_hint_native(self) -> None:
        klass, _ = classify_transport(native_ok=True, allow_agent_hints=True)
        self.assertEqual(klass, "NATIVE_MCP_OK")

    def test_transport_allow_agent_hint_mcp_stdio(self) -> None:
        klass, _ = classify_transport(mcp_stdio_ok=True, allow_agent_hints=True)
        self.assertEqual(klass, "MCP_STDIO_OK")

    def test_transport_stdio_cannot_satisfy_native_required(self) -> None:
        klass, _ = classify_transport(mcp_stdio_ok=True, native_required=True, allow_agent_hints=True)
        self.assertEqual(klass, "BLOCKED")

    def test_transport_rscript_is_labeled_separately(self) -> None:
        klass, _ = classify_transport(rscript_ok=True, allow_agent_hints=True)
        self.assertEqual(klass, "RSCRIPT_ONLY")

    def test_resource_gate_allows_low_memory_ok_io(self) -> None:
        result = decide_resource_gate(memory_override=82.0, io_blocked=False)
        self.assertEqual(result["decision"], "increase_by_1")

    def test_resource_gate_holds_high_memory(self) -> None:
        result = decide_resource_gate(memory_override=90.0, io_blocked=False)
        self.assertEqual(result["decision"], "hold")

    def test_resource_gate_holds_io_blocked(self) -> None:
        result = decide_resource_gate(memory_override=82.0, io_blocked=True)
        self.assertEqual(result["decision"], "hold")

    def test_resource_gate_holds_rterm_unresponsive(self) -> None:
        result = decide_resource_gate(memory_override=82.0, rterm_responsive=False)
        self.assertEqual(result["decision"], "hold")

    def test_resource_gate_holds_mcp_unresponsive(self) -> None:
        result = decide_resource_gate(memory_override=82.0, mcp_responsive=False)
        self.assertEqual(result["decision"], "stop_native_unstable")

    def test_resource_gate_recommends_reduce_at_extreme_memory(self) -> None:
        result = decide_resource_gate(memory_override=96.0)
        self.assertEqual(result["decision"], "reduce_recommended")

    def test_parse_requirement_basic_kind_path(self) -> None:
        req = parse_requirement("validation::C:/out/validation.csv")
        self.assertEqual(req["kind"], "validation")
        self.assertEqual(req["path"], "C:/out/validation.csv")

    def test_parse_requirement_options(self) -> None:
        req = parse_requirement("manifest::C:/out/m.csv,min_rows=2,max_age_h=1,min_bytes=10")
        self.assertEqual(req["options"]["min_rows"], 2)
        self.assertEqual(req["options"]["max_age_h"], 1.0)
        self.assertEqual(req["options"]["min_bytes"], 10)

    def test_parse_requirements_defaults_to_file(self) -> None:
        reqs = parse_requirements(["C:/out/a.txt"])
        self.assertEqual(reqs[0]["kind"], "file")

    def test_gt_errors_empty_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "gt_errors.csv"
            p.write_text("", encoding="utf-8")
            ok, _ = artifact_ok(str(p), "gt_errors_empty")
            self.assertTrue(ok)

    def test_validation_csv_needs_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "validation.csv"
            p.write_text("a,b\n", encoding="utf-8")
            ok, _ = artifact_ok(str(p), "validation")
            self.assertFalse(ok)

    def test_validation_csv_min_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "validation.csv"
            p.write_text("a,b\n1,2\n", encoding="utf-8")
            ok, reason = artifact_ok(str(p), "validation", {"min_rows": 2})
            self.assertFalse(ok)
            self.assertIn("expected at least 2", reason)

    def test_validation_csv_passes_min_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "validation.csv"
            p.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
            ok, _ = artifact_ok(str(p), "validation", {"min_rows": 2})
            self.assertTrue(ok)

    def test_file_min_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "small.txt"
            p.write_text("x", encoding="utf-8")
            ok, _ = artifact_ok(str(p), "file", {"min_bytes": 2})
            self.assertFalse(ok)

    def test_rdata_min_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.RData"
            p.write_bytes(b"x")
            ok, _ = artifact_ok(str(p), "rdata")
            self.assertFalse(ok)

    def test_output_root_guard_blocks_outside_file(self) -> None:
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            p = Path(td1) / "x.txt"
            p.write_text("ok", encoding="utf-8")
            ok, _ = artifact_ok(str(p), "file", {"output_root": td2})
            self.assertFalse(ok)

    def test_output_root_guard_allows_inside_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.txt"
            p.write_text("ok", encoding="utf-8")
            ok, _ = artifact_ok(str(p), "file", {"output_root": td})
            self.assertTrue(ok)

    def test_max_age_blocks_stale_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "old.txt"
            p.write_text("ok", encoding="utf-8")
            old = time.time() - 7200
            os.utime(p, (old, old))
            ok, _ = artifact_ok(str(p), "file", {"max_age_h": 1})
            self.assertFalse(ok)

    def test_check_artifacts_combines_failures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "validation.csv"
            p.write_text("a,b\n", encoding="utf-8")
            result = check_artifacts([parse_requirement(f"validation::{p},min_rows=1")])
            self.assertFalse(result["ok"])

    def test_state_is_complete_from_status(self) -> None:
        self.assertTrue(_state_is_complete({"status": "complete"}))

    def test_state_is_complete_from_nested_progress(self) -> None:
        self.assertTrue(_state_is_complete({"progress": {"stage": "complete"}}))

    def test_state_incomplete_running(self) -> None:
        self.assertFalse(_state_is_complete({"status": "running"}))

    def test_build_evidence_schema_fields(self) -> None:
        doc = build_evidence("x", "PASS", task_key="abc", parent_evidence_ids=["p1"])
        self.assertIn("evidence_id", doc)
        self.assertEqual(doc["parent_evidence_ids"], ["p1"])
        self.assertEqual(doc["schema_version"], "0.2.3")

    def test_schema_file_is_packaged(self) -> None:
        schema = Path("skills/clauder-rstudio-workbench/schemas/evidence.schema.json")
        self.assertTrue(schema.exists())
        self.assertEqual(json.loads(schema.read_text(encoding="utf-8"))["properties"]["schema_version"]["const"], "0.2.3")

    def test_write_evidence_atomic_creates_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = write_evidence(build_evidence("x", "PASS"), evidence_dir=Path(td))
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["harness_name"], "x")

    def test_inflight_write_load_archive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("clauder_workbench.inflight.INFLIGHT_DIR", Path(td) / "inflight"), mock.patch(
                "clauder_workbench.inflight.ARCHIVE_DIR", Path(td) / "inflight" / "archive"
            ):
                key = "abc123"
                write_inflight(key, {"task_key": key, "job_id": "j1"})
                self.assertEqual(load_inflight(key)["job_id"], "j1")
                archived = archive_inflight(key, "complete")
                self.assertIsNotNone(archived)
                self.assertIsNone(load_inflight(key))

    def test_extract_job_id_from_async_text(self) -> None:
        text = 'Job abc123 started in a background R process. Use get_async_result("abc123") to check status.'
        self.assertEqual(extract_job_id(text), "abc123")

    def test_resource_gate_requires_matching_task(self) -> None:
        doc = build_evidence("resource_gate", "increase_by_1", task_key="task-a")
        self.assertTrue(_resource_gate_ok([doc], "task-a", 60))
        self.assertFalse(_resource_gate_ok([doc], "task-b", 60))

    def test_job_complete_requires_async_guard_complete_evidence(self) -> None:
        doc = build_evidence("async_guard", "PASS", task_key="task-a", extra={"archived_path": "archive.json"})
        self.assertTrue(_job_complete_ok([doc], "task-a"))
        self.assertFalse(_job_complete_ok([doc], "task-b"))

    def test_p6_durable_violations_small_rdata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.RData"
            p.write_bytes(b"x")
            req = parse_requirement(f"rdata::{p}")
            checks = check_artifacts([req])["checks"]
            self.assertTrue(_p6_durable_violations([req], checks))

    def test_async_guard_pre_submit_and_register_job(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("clauder_workbench.inflight.INFLIGHT_DIR", Path(td) / "inflight"), mock.patch(
                "clauder_workbench.inflight.ARCHIVE_DIR", Path(td) / "inflight" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                pre = parser.parse_args(["async-guard", "pre-submit", "--task-key", "task-a"])
                self.assertEqual(cmd_async_guard(pre), 0)
                self.assertEqual(load_inflight("task-a")["status"], "pre_submitted")
                reg = parser.parse_args(["async-guard", "register-job", "--task-key", "task-a", "--job-id", "job123"])
                self.assertEqual(cmd_async_guard(reg), 0)
                self.assertEqual(load_inflight("task-a")["job_id"], "job123")

    def test_async_guard_blocks_duplicate_pre_submit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("clauder_workbench.inflight.INFLIGHT_DIR", Path(td) / "inflight"), mock.patch(
                "clauder_workbench.inflight.ARCHIVE_DIR", Path(td) / "inflight" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                pre = parser.parse_args(["async-guard", "pre-submit", "--task-key", "task-a"])
                self.assertEqual(cmd_async_guard(pre), 0)
                self.assertEqual(cmd_async_guard(pre), 3)

    def test_async_guard_register_without_presubmit_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("clauder_workbench.inflight.INFLIGHT_DIR", Path(td) / "inflight"), mock.patch(
                "clauder_workbench.inflight.ARCHIVE_DIR", Path(td) / "inflight" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                reg = parser.parse_args(["async-guard", "register-job", "--task-key", "task-a", "--job-id", "job123"])
                self.assertEqual(cmd_async_guard(reg), 3)

    def test_async_guard_register_requires_job_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("clauder_workbench.inflight.INFLIGHT_DIR", Path(td) / "inflight"), mock.patch(
                "clauder_workbench.inflight.ARCHIVE_DIR", Path(td) / "inflight" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                pre = parser.parse_args(["async-guard", "pre-submit", "--task-key", "task-a"])
                self.assertEqual(cmd_async_guard(pre), 0)
                reg = parser.parse_args(["async-guard", "register-job", "--task-key", "task-a"])
                self.assertEqual(cmd_async_guard(reg), 3)

    def test_cold_start_retry_succeeds_on_second_attempt(self) -> None:
        calls = {"n": 0}

        async def fake(timeout: float) -> dict[str, object]:
            calls["n"] += 1
            if calls["n"] == 1:
                return {"ok": False, "reason": "TimeoutError: cold start"}
            return {"ok": True}

        result = _retry_if_cold_timeout(fake, timeout=1, retries=1)
        self.assertTrue(result["ok"])
        self.assertEqual(calls["n"], 2)
        self.assertTrue(result["cold_start_retried"])

    def test_cold_start_retry_does_not_retry_non_timeout(self) -> None:
        calls = {"n": 0}

        async def fake(timeout: float) -> dict[str, object]:
            calls["n"] += 1
            return {"ok": False, "reason": "ValueError: bad config"}

        result = _retry_if_cold_timeout(fake, timeout=1, retries=1)
        self.assertFalse(result["ok"])
        self.assertEqual(calls["n"], 1)

    def test_completion_check_p5_rejects_wrong_task_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            gate = build_evidence("resource_gate", "increase_by_1", task_key="task-a")
            gate_path = write_evidence(gate, evidence_dir=Path(td))
            parser = build_parser()
            args = parser.parse_args(
                [
                    "completion-check",
                    "--mode",
                    "formal",
                    "--policy",
                    "strict",
                    "--task-key",
                    "task-b",
                    "--require-resource-gate",
                    "--parent-evidence",
                    str(gate_path),
                ]
            )
            with mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))), mock.patch(
                "clauder_workbench.cli.load_inflight", lambda task_key: None
            ):
                self.assertEqual(cmd_completion_check(args), 5)

    def test_completion_check_requires_job_complete_when_requested(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["completion-check", "--mode", "formal", "--policy", "strict", "--task-key", "task-a", "--require-job-complete"])
        with mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))), mock.patch(
            "clauder_workbench.cli.load_inflight", lambda task_key: None
        ):
            self.assertEqual(cmd_completion_check(args), 5)

    def test_completion_check_p6_rejects_small_rdata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.RData"
            p.write_bytes(b"x")
            parser = build_parser()
            args = parser.parse_args(["completion-check", "--mode", "formal", "--policy", "strict", "--require-file", f"rdata::{p}"])
            with mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))), mock.patch(
                "clauder_workbench.cli.load_inflight", lambda task_key: None
            ):
                self.assertEqual(cmd_completion_check(args), 5)

    def test_completion_check_passes_with_complete_job_parent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parent = build_evidence("async_guard", "PASS", task_key="task-a", extra={"archived_path": "archive.json"})
            parent_path = write_evidence(parent, evidence_dir=Path(td))
            parser = build_parser()
            args = parser.parse_args(
                [
                    "completion-check",
                    "--mode",
                    "formal",
                    "--policy",
                    "strict",
                    "--task-key",
                    "task-a",
                    "--require-job-complete",
                    "--parent-evidence",
                    str(parent_path),
                ]
            )
            with mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))), mock.patch(
                "clauder_workbench.cli.load_inflight", lambda task_key: None
            ):
                self.assertEqual(cmd_completion_check(args), 0)

    def test_installer_exposes_wrapper_options(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("AddHarnessToPath", text)
        self.assertIn("WorkbenchBinDir", text)
        self.assertIn("clauder-workbench.cmd", text)

    def test_readme_quickstart_uses_v022_and_wrapper(self) -> None:
        text = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("--branch v0.2.3", text)
        self.assertIn("releases/download/v0.2.3/clauder-rstudio-workbench-v0.2.3.zip", text)
        self.assertIn("clauder-workbench.cmd", text)
        self.assertIn("-AddHarnessToPath", text)

    def test_installer_exposes_zip_fallback_options(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("NoZipFallback", text)
        self.assertIn("Install-ClaudeRZipFallback", text)
        self.assertIn("InstallPython314", text)

    def test_installer_records_source_metadata(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("workbench_source_type", text)
        self.assertIn("workbench_ref", text)
        self.assertIn("claudeR_source_type", text)
        self.assertIn("configured_clients", text)

    def test_expected_clients_defaults_to_install_info(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        self.assertEqual(_expected_clients(args, {"configured_clients": ["codex"]}), ["codex"])

    def test_expected_clients_all_expands_every_client(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor", "--expect-client", "all"])
        self.assertEqual(_expected_clients(args, {"configured_clients": ["codex"]}), ["codex", "claude", "copilot"])

    def test_expected_clients_auto_falls_back_to_codex(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        self.assertEqual(_expected_clients(args, {}), ["codex"])


if __name__ == "__main__":
    unittest.main()
