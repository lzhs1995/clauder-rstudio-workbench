from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from clauder_workbench.cli import (
    DEFAULT_RESOURCE_GATE_MAX_AGE_MIN,
    _resource_gate_status,
    build_parser,
    cmd_completion_check,
)
from clauder_workbench.evidence import build_evidence


TASK_KEY = "freshness-v042"


def _aged(doc: dict, minutes: float) -> dict:
    result = dict(doc)
    result["timestamp_utc"] = (
        datetime.now(timezone.utc) - timedelta(minutes=minutes)
    ).isoformat().replace("+00:00", "Z")
    return result


def _write(root: Path, name: str, doc: dict) -> Path:
    path = root / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _full_parent_chain(root: Path, *, monitor_decision: str) -> list[Path]:
    native = build_evidence(
        "native_smoke",
        "PASS",
        task_key=TASK_KEY,
        transport_class="NATIVE_MCP_OK",
        parent_evidence_ids=["p1", "p2", "p3", "p4"],
    )
    preflight = build_evidence("preflight", "PASS", task_key=TASK_KEY)
    gate = _aged(
        build_evidence("resource_gate", "increase_by_1", task_key=TASK_KEY),
        74,
    )
    monitor = build_evidence(
        "soak_monitor",
        monitor_decision,
        task_key=TASK_KEY,
        transport_class="MCP_STDIO_OK",
        extra={
            "monitored_transport": "NATIVE_MCP_OK",
            "summary": {"checks": {"heartbeat": True, "resources": True}},
        },
    )
    return [
        _write(root, "native", native),
        _write(root, "preflight", preflight),
        _write(root, "resource", gate),
        _write(root, "monitor", monitor),
    ]


class FreshnessV042Tests(unittest.TestCase):
    def test_parser_default_is_120_minutes(self) -> None:
        args = build_parser().parse_args(["completion-check"])
        self.assertEqual(DEFAULT_RESOURCE_GATE_MAX_AGE_MIN, 120.0)
        self.assertEqual(args.resource_gate_max_age_min, 120.0)

    def test_74_minute_gate_passes_120_and_fails_60(self) -> None:
        gate = _aged(
            build_evidence("resource_gate", "increase_by_1", task_key=TASK_KEY),
            74,
        )
        accepted = _resource_gate_status([gate], TASK_KEY, 120)
        rejected = _resource_gate_status([gate], TASK_KEY, 60)
        self.assertTrue(accepted["accepted"])
        self.assertFalse(rejected["accepted"])
        self.assertGreater(accepted["selected_age_min"], 73)
        self.assertLess(accepted["selected_age_min"], 75)

    def test_gate_older_than_120_is_rejected(self) -> None:
        gate = _aged(
            build_evidence("resource_gate", "increase_by_1", task_key=TASK_KEY),
            121,
        )
        status = _resource_gate_status([gate], TASK_KEY, 120)
        self.assertFalse(status["accepted"])

    def test_wrong_task_and_wrong_decision_are_not_candidates(self) -> None:
        wrong_task = build_evidence(
            "resource_gate", "increase_by_1", task_key="different"
        )
        wrong_decision = build_evidence(
            "resource_gate", "hold", task_key=TASK_KEY
        )
        status = _resource_gate_status(
            [wrong_task, wrong_decision], TASK_KEY, 120
        )
        self.assertFalse(status["accepted"])
        self.assertEqual(status["candidate_count"], 0)

    def test_full_chain_passes_with_74_minute_gate_and_monitor_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parents = _full_parent_chain(Path(td), monitor_decision="PASS")
            args = build_parser().parse_args(
                [
                    "completion-check",
                    "--mode",
                    "formal",
                    "--policy",
                    "strict",
                    "--task-key",
                    TASK_KEY,
                    "--require-native-smoke",
                    "--native-smoke-max-age-min",
                    "120",
                    "--require-preflight",
                    "--require-resource-gate",
                    "--require-soak-monitor",
                    "--soak-monitor-max-age-min",
                    "120",
                    "--require-transport-class",
                    "NATIVE_MCP_OK",
                    "--transport-class",
                    "NATIVE_MCP_OK",
                    "--parent-evidence",
                    *[str(path) for path in parents],
                ]
            )
            captured: list[dict] = []
            with mock.patch(
                "clauder_workbench.cli.emit",
                lambda doc, write=True: captured.append(doc) or int(doc["exit_code"]),
            ), mock.patch("clauder_workbench.cli.load_inflight", return_value=None):
                self.assertEqual(cmd_completion_check(args), 0)
            gate_check = captured[0]["extra"]["resource_gate_check"]
            self.assertTrue(gate_check["accepted"])
            self.assertEqual(gate_check["max_age_min"], 120.0)
            self.assertIsNotNone(gate_check["selected_evidence_id"])

    def test_block_monitor_is_only_failure_after_default_fix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parents = _full_parent_chain(Path(td), monitor_decision="BLOCK")
            args = build_parser().parse_args(
                [
                    "completion-check",
                    "--mode",
                    "formal",
                    "--policy",
                    "strict",
                    "--task-key",
                    TASK_KEY,
                    "--require-native-smoke",
                    "--native-smoke-max-age-min",
                    "120",
                    "--require-preflight",
                    "--require-resource-gate",
                    "--require-soak-monitor",
                    "--soak-monitor-max-age-min",
                    "120",
                    "--require-transport-class",
                    "NATIVE_MCP_OK",
                    "--transport-class",
                    "NATIVE_MCP_OK",
                    "--parent-evidence",
                    *[str(path) for path in parents],
                ]
            )
            captured: list[dict] = []
            with mock.patch(
                "clauder_workbench.cli.emit",
                lambda doc, write=True: captured.append(doc) or int(doc["exit_code"]),
            ), mock.patch("clauder_workbench.cli.load_inflight", return_value=None):
                self.assertEqual(cmd_completion_check(args), 5)
            self.assertEqual(
                captured[0]["policy_violations"],
                ["MISSING-SOAK-MONITOR-EVIDENCE"],
            )

    def test_contract_override_60_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gate = _aged(
                build_evidence(
                    "resource_gate", "increase_by_1", task_key=TASK_KEY
                ),
                74,
            )
            gate_path = _write(root, "gate", gate)
            contract = root / "contract.json"
            contract.write_text(
                json.dumps(
                    {
                        "task_key": TASK_KEY,
                        "require_resource_gate": True,
                        "resource_gate_max_age_min": 60,
                    }
                ),
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                [
                    "completion-check",
                    "--contract",
                    str(contract),
                    "--task-key",
                    TASK_KEY,
                    "--parent-evidence",
                    str(gate_path),
                ]
            )
            captured: list[dict] = []
            with mock.patch(
                "clauder_workbench.cli.emit",
                lambda doc, write=True: captured.append(doc) or int(doc["exit_code"]),
            ), mock.patch("clauder_workbench.cli.load_inflight", return_value=None):
                self.assertEqual(cmd_completion_check(args), 5)
            self.assertEqual(
                captured[0]["extra"]["resource_gate_check"]["max_age_min"], 60.0
            )
            self.assertIn("is stale", " ".join(captured[0]["reasons"]))

    def test_schema_copies_document_resource_gate_completion_policy(self) -> None:
        shared = Path("shared/schemas/fanout-contract.schema.json")
        packaged = Path(
            "skills/clauder-rstudio-workbench/schemas/fanout-contract.schema.json"
        )
        self.assertEqual(shared.read_bytes(), packaged.read_bytes())
        properties = json.loads(shared.read_text(encoding="utf-8"))["properties"]
        self.assertEqual(properties["require_resource_gate"]["type"], "boolean")
        self.assertEqual(
            properties["resource_gate_max_age_min"]["minimum"], 0
        )


if __name__ == "__main__":
    unittest.main()
