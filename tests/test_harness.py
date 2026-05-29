from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench.artifacts import artifact_ok, check_artifacts, parse_requirement
from clauder_workbench.cli import _state_is_complete, parse_requirements
from clauder_workbench.evidence import build_evidence, stable_task_key, write_evidence
from clauder_workbench.inflight import archive_inflight, load_inflight, write_inflight
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
        self.assertEqual(doc["schema_version"], "0.2.0")

    def test_schema_file_is_packaged(self) -> None:
        schema = Path("skills/clauder-rstudio-workbench/schemas/evidence.schema.json")
        self.assertTrue(schema.exists())
        self.assertEqual(json.loads(schema.read_text(encoding="utf-8"))["properties"]["schema_version"]["const"], "0.2.0")

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


if __name__ == "__main__":
    unittest.main()
