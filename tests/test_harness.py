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
    _native_smoke_parent_ok,
    _p6_durable_violations,
    _resource_gate_ok,
    _state_is_complete,
    build_parser,
    cmd_async_guard,
    cmd_completion_check,
    cmd_native_smoke,
    parse_requirements,
)
from clauder_workbench.evidence import build_evidence, stable_task_key, write_evidence
from clauder_workbench.inflight import archive_inflight, load_inflight, write_inflight
from clauder_workbench.installer import update_codex_config
from clauder_workbench.mcp_client import _retry_if_cold_timeout, _server_args, extract_job_id
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

    def test_macos_resource_fallback_is_implemented(self) -> None:
        text = Path(
            "skills/clauder-rstudio-workbench/clauder_workbench/resource.py"
        ).read_text(encoding="utf-8")
        self.assertIn('sys.platform == "darwin"', text)
        self.assertIn('["vm_stat"]', text)
        self.assertIn('["sysctl", "-n", "hw.memsize"]', text)

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
        # evidence *format* version stays 0.2.4; package/release version is tracked
        # separately via producer_version (decoupled).
        self.assertEqual(doc["schema_version"], "0.2.4")
        self.assertEqual(doc["producer_version"], "0.4.5")

    def test_schema_file_is_packaged(self) -> None:
        schema = Path("skills/clauder-rstudio-workbench/schemas/evidence.schema.json")
        self.assertTrue(schema.exists())
        self.assertEqual(json.loads(schema.read_text(encoding="utf-8"))["properties"]["schema_version"]["const"], "0.2.4")

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

    def test_native_smoke_two_step_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.EVIDENCE_DIR", root / "evidence"), mock.patch(
                "clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))
            ):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "start", "--task-key", "task-a", "--session-name", "default"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "list_sessions", "--ok", "--session-name", "default"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "execute_r", "--ok", "--marker", "NATIVE_EXECUTE_OK", "--pid", "123"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "execute_r_async", "--ok", "--job-id", "job123"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "get_async_result", "--ok", "--job-id", "job123", "--marker", "NATIVE_ASYNC_DONE"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "complete", "--task-key", "task-a"])), 0)

    def test_native_smoke_rejects_stdio_impersonation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.EVIDENCE_DIR", root / "evidence"), mock.patch(
                "clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))
            ):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "start", "--task-key", "task-a"])), 0)
                rc = cmd_native_smoke(
                    parser.parse_args([
                        "native-smoke", "record", "--task-key", "task-a", "--step", "execute_r",
                        "--ok", "--marker", "MCP_STDIO_OK", "--transport-class", "MCP_STDIO_OK",
                    ])
                )
                self.assertEqual(rc, 3)

    def test_native_smoke_complete_requires_all_steps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "start", "--task-key", "task-a"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "complete", "--task-key", "task-a"])), 3)

    def test_native_smoke_require_raw_file_blocks_record_without_raw_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args([
                    "native-smoke", "start", "--task-key", "task-a", "--session-name", "default",
                    "--require-raw-file",
                ])), 0)
                rc = cmd_native_smoke(parser.parse_args([
                    "native-smoke", "record", "--task-key", "task-a", "--step", "list_sessions",
                    "--ok", "--session-name", "default",
                ]))
                self.assertEqual(rc, 3)

    def test_native_smoke_require_raw_file_passes_full_chain(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ls = root / "ls.txt"; ls.write_text("sessions: default", encoding="utf-8")
            ex = root / "ex.txt"; ex.write_text("NATIVE_EXECUTE_OK pid=123", encoding="utf-8")
            asy = root / "async.txt"; asy.write_text("submitted job123", encoding="utf-8")
            res = root / "res.txt"; res.write_text("complete NATIVE_ASYNC_DONE", encoding="utf-8")
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args([
                    "native-smoke", "start", "--task-key", "task-a", "--session-name", "default",
                    "--require-raw-file",
                ])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args([
                    "native-smoke", "record", "--task-key", "task-a", "--step", "list_sessions",
                    "--ok", "--session-name", "default", "--raw-file", str(ls),
                ])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args([
                    "native-smoke", "record", "--task-key", "task-a", "--step", "execute_r",
                    "--ok", "--marker", "NATIVE_EXECUTE_OK", "--pid", "123", "--raw-file", str(ex),
                ])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args([
                    "native-smoke", "record", "--task-key", "task-a", "--step", "execute_r_async",
                    "--ok", "--job-id", "job123", "--raw-file", str(asy),
                ])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args([
                    "native-smoke", "record", "--task-key", "task-a", "--step", "get_async_result",
                    "--ok", "--job-id", "job123", "--marker", "NATIVE_ASYNC_DONE", "--raw-file", str(res),
                ])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "complete", "--task-key", "task-a"])), 0)
                state = json.loads((root / "native_smoke" / "task-a.json").read_text(encoding="utf-8"))
                for step in ("list_sessions", "execute_r", "execute_r_async", "get_async_result"):
                    entry = state["steps"][step]
                    self.assertTrue(entry.get("evidence_id"))
                    proof = entry.get("raw_file_proof")
                    self.assertTrue(proof)
                    self.assertEqual(len(proof["sha256"]), 64)
                    self.assertTrue(Path(proof["evidence_copy"]).exists())

    def test_native_smoke_require_raw_file_blocks_marker_absent_from_raw_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ex = root / "ex.txt"; ex.write_text("no marker present here", encoding="utf-8")
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.EVIDENCE_DIR", root / "evidence"), mock.patch(
                "clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))
            ):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args([
                    "native-smoke", "start", "--task-key", "task-a", "--session-name", "default",
                    "--require-raw-file",
                ])), 0)
                rc = cmd_native_smoke(parser.parse_args([
                    "native-smoke", "record", "--task-key", "task-a", "--step", "execute_r",
                    "--ok", "--marker", "NATIVE_EXECUTE_OK", "--pid", "123", "--raw-file", str(ex),
                ]))
                self.assertEqual(rc, 3)

    def test_native_smoke_complete_stamps_agent_identity(self) -> None:
        captured: list[dict] = []

        def cap(doc, write=True):
            captured.append(doc)
            return int(doc.get("exit_code", 0))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", cap):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "start", "--task-key", "task-a", "--session-name", "default", "--agent", "codex"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "list_sessions", "--ok", "--session-name", "default"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "execute_r", "--ok", "--marker", "NATIVE_EXECUTE_OK", "--pid", "123"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "execute_r_async", "--ok", "--job-id", "job123"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "get_async_result", "--ok", "--job-id", "job123", "--marker", "NATIVE_ASYNC_DONE"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "complete", "--task-key", "task-a"])), 0)
        complete_doc = captured[-1]
        self.assertEqual(complete_doc.get("transport_class"), "NATIVE_MCP_OK")
        self.assertEqual(complete_doc.get("agent"), "codex")
        self.assertEqual(len(complete_doc.get("parent_evidence_ids") or []), 4)

    def test_native_smoke_complete_infers_agent_from_tool_layer(self) -> None:
        captured: list[dict] = []

        def cap(doc, write=True):
            captured.append(doc)
            return int(doc.get("exit_code", 0))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", cap):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "start", "--task-key", "task-a", "--session-name", "default"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "list_sessions", "--ok", "--session-name", "default", "--tool-layer", "copilot-native"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "execute_r", "--ok", "--marker", "NATIVE_EXECUTE_OK", "--pid", "123", "--tool-layer", "copilot-native"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "execute_r_async", "--ok", "--job-id", "job123", "--tool-layer", "copilot-native"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "get_async_result", "--ok", "--job-id", "job123", "--marker", "NATIVE_ASYNC_DONE", "--tool-layer", "copilot-native"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "complete", "--task-key", "task-a"])), 0)
        self.assertEqual(captured[-1].get("agent"), "copilot")

    def test_native_smoke_agent_derives_tool_layer(self) -> None:
        captured: list[dict] = []

        def cap(doc, write=True):
            captured.append(doc)
            return int(doc.get("exit_code", 0))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", cap):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "start", "--task-key", "task-a", "--agent", "claude"])), 0)
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "record", "--task-key", "task-a", "--step", "list_sessions", "--ok", "--session-count", "1"])), 0)
        self.assertEqual(captured[-1]["extra"]["entry"]["tool_layer"], "claude-native")

    def test_native_smoke_agent_tool_layer_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", root / "native_smoke"), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", root / "native_smoke" / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                self.assertEqual(cmd_native_smoke(parser.parse_args(["native-smoke", "start", "--task-key", "task-a", "--agent", "codex"])), 0)
                rc = cmd_native_smoke(parser.parse_args([
                    "native-smoke", "record", "--task-key", "task-a", "--step", "list_sessions",
                    "--ok", "--session-count", "1", "--tool-layer", "copilot-native",
                ]))
                self.assertEqual(rc, 3)

    def test_native_smoke_complete_blocks_legacy_state_without_evidence_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            native_dir = root / "native_smoke"
            native_dir.mkdir()
            (native_dir / "task-a.json").write_text(json.dumps({
                "task_key": "task-a",
                "status": "recording",
                "started_at_utc": "2026-05-31T00:00:00Z",
                "session_name": "default",
                "required_steps": ["list_sessions", "execute_r", "execute_r_async", "get_async_result"],
                "steps": {
                    "list_sessions": {"step": "list_sessions", "ok": True, "recorded_at_utc": "2026-05-31T00:00:00Z", "tool_layer": "codex-native", "transport_class": "NATIVE_MCP_OK", "session_count": 1},
                    "execute_r": {"step": "execute_r", "ok": True, "recorded_at_utc": "2026-05-31T00:00:00Z", "tool_layer": "codex-native", "transport_class": "NATIVE_MCP_OK", "marker": "NATIVE_EXECUTE_OK", "pid": "123"},
                    "execute_r_async": {"step": "execute_r_async", "ok": True, "recorded_at_utc": "2026-05-31T00:00:00Z", "tool_layer": "codex-native", "transport_class": "NATIVE_MCP_OK", "job_id": "job123"},
                    "get_async_result": {"step": "get_async_result", "ok": True, "recorded_at_utc": "2026-05-31T00:00:00Z", "tool_layer": "codex-native", "transport_class": "NATIVE_MCP_OK", "job_id": "job123", "marker": "NATIVE_ASYNC_DONE"},
                },
            }), encoding="utf-8")
            with mock.patch("clauder_workbench.cli.NATIVE_SMOKE_DIR", native_dir), mock.patch(
                "clauder_workbench.cli.NATIVE_SMOKE_ARCHIVE_DIR", native_dir / "archive"
            ), mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))):
                parser = build_parser()
                rc = cmd_native_smoke(parser.parse_args(["native-smoke", "complete", "--task-key", "task-a", "--max-age-min", "999999"]))
                self.assertEqual(rc, 3)

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

    def test_native_smoke_parent_ok_requires_four_chained_parent_ids(self) -> None:
        doc = build_evidence(
            "native_smoke",
            "PASS",
            task_key="task-a",
            transport_class="NATIVE_MCP_OK",
            parent_evidence_ids=["p1", "p2", "p3", "p4"],
        )
        self.assertTrue(_native_smoke_parent_ok([doc], task_key="task-a", max_age_min=60))
        empty_chain = dict(doc)
        empty_chain["parent_evidence_ids"] = []
        self.assertFalse(_native_smoke_parent_ok([empty_chain], task_key="task-a", max_age_min=60))
        duplicate_chain = dict(doc)
        duplicate_chain["parent_evidence_ids"] = ["p1", "p1", "p2", "p3"]
        self.assertFalse(_native_smoke_parent_ok([duplicate_chain], task_key="task-a", max_age_min=60))

    def test_completion_check_blocks_empty_chain_native_smoke_parent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parent = build_evidence("native_smoke", "PASS", task_key="task-a", transport_class="NATIVE_MCP_OK")
            parent_path = write_evidence(parent, evidence_dir=Path(td))
            parser = build_parser()
            args = parser.parse_args([
                "completion-check",
                "--mode",
                "formal",
                "--policy",
                "strict",
                "--task-key",
                "task-a",
                "--require-native-smoke",
                "--parent-evidence",
                str(parent_path),
            ])
            with mock.patch("clauder_workbench.cli.emit", lambda doc, write=True: int(doc.get("exit_code", 0))), mock.patch(
                "clauder_workbench.cli.load_inflight", lambda task_key: None
            ):
                self.assertEqual(cmd_completion_check(args), 5)

    def test_installer_exposes_wrapper_options(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("AddHarnessToPath", text)
        self.assertIn("WorkbenchBinDir", text)
        self.assertIn("clauder-workbench.cmd", text)

    def test_readme_quickstart_uses_local_candidate_and_wrapper(self) -> None:
        text = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("local `v0.4.5` candidate", text)
        self.assertIn("no `v0.4.5` remote tag or release", text)
        self.assertIn("clauder-workbench.cmd", text)
        self.assertIn("./install.sh --clauder-dir", text)
        self.assertIn("-AddHarnessToPath", text)
        # The install/clone/zip/upgrade commands must not point at the old tag.
        self.assertNotIn("--branch v0.2.4", text)
        self.assertNotIn("git checkout v0.2.4", text)
        self.assertNotIn("releases/download/v0.2.4/", text)
        self.assertNotIn("--branch v0.3.1", text)
        self.assertNotIn("releases/download/v0.3.1/", text)

    def test_workbench_skill_documents_collection_release(self) -> None:
        text = Path("skills/clauder-rstudio-workbench/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("skill collection release `v0.4.5`", text)
        self.assertIn("cmaverse-paired-mval", text)
        self.assertIn("`v0.2.4` is the minimum safe release", text)
        self.assertNotIn("This skill release `v0.2.4`", text)

    def test_installer_exposes_zip_fallback_options(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("NoZipFallback", text)
        self.assertIn("Install-ClaudeRZipFallback", text)
        self.assertIn("InstallPython314", text)

    def test_installer_exposes_backup_retention(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("BackupRetention = 5", text)
        self.assertIn("function Prune-SkillBackups", text)
        self.assertIn("Select-Object -Skip $BackupRetention", text)
        self.assertIn("Would remove old skill backup", text)

    def test_installer_records_source_metadata(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("workbench_source_type", text)
        self.assertIn("workbench_ref", text)
        self.assertIn("claudeR_source_type", text)
        self.assertIn("configured_clients", text)
        self.assertIn("clauder_mcp_install_from", text)
        self.assertIn("clauder_mcp_exe_sha256", text)
        self.assertIn("prewarm_result", text)

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

    def test_installer_uses_persistent_lzhs_mcp_entry(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("Install-ClaudeRMcpTool", text)
        self.assertIn("Invoke-McpPrewarm", text)
        self.assertIn("ConfigureWorkspaceMcp", text)
        self.assertIn("uv_tool_from_local_lzhs_fork", text)
        self.assertIn("startup_timeout_sec = 180.0", text)
        self.assertIn("UV_CACHE_DIR", text)
        self.assertIn("clauder_mcp_source", text)
        self.assertIn("clauder_mcp_command", text)
        main_start = text.index("try {\n    Test-Prerequisites")
        self.assertLess(
            text.index("Install-ClaudeRMcpTool | Out-Null", main_start),
            text.index("    Install-Skill", main_start),
        )

    def test_codex_rstudio_mcp_check_accepts_persistent_lzhs_entry(self) -> None:
        from clauder_workbench import cli as cli_mod
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bridge = root / "projects" / "ClaudeR" / "clauder-mcp"
            bridge.mkdir(parents=True)
            exe = root / ("clauder-mcp.exe" if os.name == "nt" else "clauder-mcp")
            exe.write_text("", encoding="utf-8")
            cfg = root / "config.toml"
            cfg.write_text(
                f"""[mcp_servers.r-studio]\ncommand = \"{exe.as_posix()}\"\nstartup_timeout_sec = 180.0\n\n[mcp_servers.r-studio.env]\nHOME = \"{root.as_posix()}\"\nPYTHONIOENCODING = \"utf-8\"\nNO_PROXY = \"127.0.0.1,localhost\"\nUV_CACHE_DIR = \"{(root / 'uv-cache').as_posix()}\"\n""",
                encoding="utf-8",
            )
            with mock.patch.object(cli_mod, "CODEX_CONFIG", cfg):
                result = cli_mod._check_codex_rstudio_mcp_config({
                    "clauder_mcp_install_mode": "uv_tool_from_local_lzhs_fork",
                    "clauder_mcp_source": str(bridge),
                })
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["persistent_entry"])
        self.assertEqual(result["startup_timeout_sec"], 180.0)

    def test_codex_rstudio_mcp_check_blocks_bare_upstream_risk(self) -> None:
        from clauder_workbench import cli as cli_mod
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text(
                """[mcp_servers.r-studio]\ncommand = \"uvx\"\nargs = [\"clauder-mcp\"]\nstartup_timeout_sec = 180.0\n""",
                encoding="utf-8",
            )
            with mock.patch.object(cli_mod, "CODEX_CONFIG", cfg):
                result = cli_mod._check_codex_rstudio_mcp_config({})
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["bare_mcp"])
        self.assertIn("bare clauder-mcp", " ".join(result["reasons"]))

    def test_codex_rstudio_mcp_check_warns_uvx_local_dev_path(self) -> None:
        from clauder_workbench import cli as cli_mod
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bridge = root / "ClaudeR" / "clauder-mcp"
            bridge.mkdir(parents=True)
            cfg = root / "config.toml"
            cfg.write_text(
                f"""[mcp_servers.r-studio]\ncommand = \"uvx\"\nargs = [\"--from\", \"{bridge.as_posix()}\", \"clauder-mcp\"]\nstartup_timeout_sec = 180.0\n\n[mcp_servers.r-studio.env]\nUV_CACHE_DIR = \"C:/tmp/uv-cache\"\n""",
                encoding="utf-8",
            )
            with mock.patch.object(cli_mod, "CODEX_CONFIG", cfg), mock.patch.object(cli_mod, "LOCAL_CLAUDER_BRIDGE", bridge):
                result = cli_mod._check_codex_rstudio_mcp_config({})
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["uvx_from_local_bridge"])
        self.assertTrue(any("development" in w for w in result["warnings"]))

    def test_mcp_client_prefers_codex_persistent_entry(self) -> None:
        from clauder_workbench import mcp_client as mcp_mod
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe = root / ("clauder-mcp.exe" if os.name == "nt" else "clauder-mcp")
            exe.write_text("", encoding="utf-8")
            cfg = root / "config.toml"
            cfg.write_text(
                f"""[mcp_servers.r-studio]\ncommand = \"{exe.as_posix()}\"\nstartup_timeout_sec = 180.0\n\n[mcp_servers.r-studio.env]\nUV_CACHE_DIR = \"C:/tmp/uv-cache\"\n""",
                encoding="utf-8",
            )
            with mock.patch.object(mcp_mod, "CODEX_CONFIG", cfg):
                command, args = _server_args()
        self.assertEqual(command.replace("\\", "/"), exe.as_posix())
        self.assertEqual(args, [])

    def test_posix_installer_updates_codex_config_without_losing_other_sections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config.toml"
            config.write_text(
                "[projects.sample]\ntrust_level = \"trusted\"\n\n"
                "[mcp_servers.r-studio]\ncommand = \"uvx\"\nargs = [\"clauder-mcp\"]\n\n"
                "[mcp_servers.r-studio.env]\nHOME = \"/old\"\n",
                encoding="utf-8",
            )
            mcp = root / "bin" / "clauder-mcp"
            mcp.parent.mkdir()
            mcp.write_text("", encoding="utf-8")
            update_codex_config(config, mcp, root, root / "uv-cache")
            text = config.read_text(encoding="utf-8")
            try:
                import tomllib
            except ImportError:  # pragma: no cover - Python 3.10 fallback
                import tomli as tomllib

            parsed = tomllib.loads(text)
            self.assertEqual(parsed["projects"]["sample"]["trust_level"], "trusted")
            self.assertEqual(parsed["mcp_servers"]["r-studio"]["command"], str(mcp))
            self.assertEqual(parsed["mcp_servers"]["r-studio"]["startup_timeout_sec"], 180.0)
            self.assertEqual(parsed["mcp_servers"]["r-studio"]["env"]["HOME"], str(root))
            self.assertEqual(text.count("[mcp_servers.r-studio]"), 1)
            self.assertTrue(list(root.glob("config.toml.bak_*")))

    def test_posix_entrypoints_are_executable(self) -> None:
        self.assertTrue(os.access("install.sh", os.X_OK))
        self.assertTrue(os.access("skills/clauder-rstudio-workbench/harness/run.sh", os.X_OK))

    def test_cli_exposes_candidate_version(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit) as caught, mock.patch("sys.stdout"):
            parser.parse_args(["--version"])
        self.assertEqual(caught.exception.code, 0)

    def test_parent_evidence_accepts_repeated_and_grouped_values(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "completion-check",
            "--parent-evidence", "preflight.json", "resource.json",
            "--parent-evidence", "fanout.json",
            "--parent-evidence", "merge.json",
        ])
        self.assertEqual(
            args.parent_evidence,
            ["preflight.json", "resource.json", "fanout.json", "merge.json"],
        )

    def test_posix_installer_preserves_existing_skill_symlink(self) -> None:
        from clauder_workbench.installer import _install_skill

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source" / "demo"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("new", encoding="utf-8")
            target = root / "codex" / "demo"
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text("installed", encoding="utf-8")
            agents = root / "agents"
            agents.mkdir()
            link = agents / "demo"
            link.symlink_to(target, target_is_directory=True)

            installed = _install_skill(source, agents)

            self.assertEqual(installed, link)
            self.assertTrue(link.is_symlink())
            self.assertEqual((link / "SKILL.md").read_text(encoding="utf-8"), "installed")

    def test_posix_installer_backup_retention_defaults_to_keep_all(self) -> None:
        from clauder_workbench.installer import build_parser as build_installer_parser

        args = build_installer_parser().parse_args([])
        self.assertEqual(args.backup_retention, 0)

    def test_posix_installer_prunes_only_backups_older_than_retention(self) -> None:
        from clauder_workbench.installer import _prune_skill_backups

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backups = [root / f"demo_bak_20260819_00000{i}" for i in range(4)]
            for backup in backups:
                backup.mkdir()

            removed = _prune_skill_backups(root, "demo", 2)

            self.assertEqual(set(removed), set(backups[:2]))
            self.assertEqual(
                sorted(path.name for path in root.glob("demo_bak_*")),
                sorted(path.name for path in backups[2:]),
            )

    def test_posix_installer_retention_zero_preserves_backups(self) -> None:
        from clauder_workbench.installer import _prune_skill_backups

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup = root / "demo_bak_20260819_000001"
            backup.mkdir()

            self.assertEqual(_prune_skill_backups(root, "demo", 0), [])
            self.assertTrue(backup.exists())

    def test_posix_installer_reads_component_versions(self) -> None:
        from clauder_workbench.installer import _description_version, _pyproject_version

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            description = root / "DESCRIPTION"
            description.write_text("Package: ClaudeR\nVersion: 0.8.1\n", encoding="utf-8")
            pyproject = root / "pyproject.toml"
            pyproject.write_text('[project]\nname = "clauder-mcp"\nversion = "0.10.0"\n', encoding="utf-8")

            self.assertEqual(_description_version(description), "0.8.1")
            self.assertEqual(_pyproject_version(pyproject), "0.10.0")

    def test_posix_installer_records_dirty_git_state(self) -> None:
        from clauder_workbench.installer import _git_dirty

        result = mock.Mock(stdout=" M README.md\n")
        with mock.patch("clauder_workbench.installer.subprocess.run", return_value=result):
            self.assertTrue(_git_dirty(Path("/tmp/demo")))

    # v0.2.4: install.ps1 UTF-8 + TOML 自检测试
    def test_installer_has_utf8_no_bom_helpers(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertIn("Read-Utf8File", text)
        self.assertIn("Write-Utf8NoBom", text)
        self.assertIn("Test-TomlParseable", text)
        self.assertIn("Restore-FromLatestBackup", text)
        # 显式 UTF8Encoding(false) 构造 — 关键防 BOM 标志
        self.assertIn("UTF8Encoding($false)", text)

    def test_installer_codex_write_uses_no_bom_and_self_check(self) -> None:
        text = Path("install.ps1").read_text(encoding="utf-8")
        self.assertNotIn("Set-Content -LiteralPath $config -Value $content -Encoding UTF8", text)
        self.assertIn("Write-Utf8NoBom $config $content", text)
        self.assertIn("Test-TomlParseable $config", text)
        self.assertIn("Restore-FromLatestBackup $config", text)

    def test_doctor_check_toml_parse_flag_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor", "--check-toml-parse"])
        self.assertTrue(getattr(args, "check_toml_parse", False))

    def test_check_codex_toml_parseable_detects_bom(self) -> None:
        from clauder_workbench import cli as cli_mod
        sample_bytes = b"\xef\xbb\xbf[mcp_servers.r-studio]\ncommand = \"uvx\"\n"
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_bytes(sample_bytes)
            with mock.patch.object(cli_mod, "CODEX_CONFIG", cfg):
                result = cli_mod._check_codex_toml_parseable()
        # BOM 应被检测并剥离后 parse 成功
        self.assertTrue(result["bom_detected"])
        self.assertTrue(result["ok"])

    def test_check_codex_toml_parseable_handles_invalid_utf8(self) -> None:
        from clauder_workbench import cli as cli_mod
        # 真实事故的根因之一：install.ps1 将 UTF-8 字节按 GBK 误读后再写回 UTF-8。
        # 这里直接构造非法 UTF-8 序列，验证 _check_codex_toml_parseable 不崩溃并标记 ok=False。
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            # 0x80-0xFF 单独出现是非法 UTF-8 起始字节
            cfg.write_bytes(b"key = \"value\"\n[bad\x80table]\nx = 1\n")
            with mock.patch.object(cli_mod, "CODEX_CONFIG", cfg):
                result = cli_mod._check_codex_toml_parseable()
        self.assertFalse(result["ok"], result)
        self.assertIn("error", result)

    def test_check_codex_toml_parseable_accepts_chinese_paths(self) -> None:
        from clauder_workbench import cli as cli_mod
        good = (
            "[mcp_servers.r-studio]\n"
            "command = \"uvx\"\n\n"
            "[projects.'C:\\Users\\LZHS\\Desktop\\开题报告']\n"
            "trust_level = \"trusted\"\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_bytes(good)
            with mock.patch.object(cli_mod, "CODEX_CONFIG", cfg):
                result = cli_mod._check_codex_toml_parseable()
        self.assertTrue(result["ok"], result)

    def test_check_codex_toml_parseable_missing_file(self) -> None:
        from clauder_workbench import cli as cli_mod
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "nonexistent.toml"
            with mock.patch.object(cli_mod, "CODEX_CONFIG", cfg):
                result = cli_mod._check_codex_toml_parseable()
        self.assertFalse(result["ok"])
        self.assertIn("does not exist", result["error"])

    def test_check_codex_toml_parseable_rejects_unclosed_table(self) -> None:
        from clauder_workbench import cli as cli_mod
        # 模拟同事 1 真实事故：路径结尾的 ' 丢失 → unclosed table
        broken = b"[projects.'C:\\Users\\LZHS\\Desktop\\bad_path]\ntrust_level = \"trusted\"\n"
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_bytes(broken)
            with mock.patch.object(cli_mod, "CODEX_CONFIG", cfg):
                result = cli_mod._check_codex_toml_parseable()
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
