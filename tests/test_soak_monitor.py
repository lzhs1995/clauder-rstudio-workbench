from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench.cli import _soak_monitor_parent_ok, build_parser, cmd_completion_check
from clauder_workbench.evidence import build_evidence
from clauder_workbench.soak_monitor import (
    HEARTBEAT_FIELDS,
    RESOURCE_FIELDS,
    _append_csv,
    _finalize,
    _initial_checkpoint,
    _load_checkpoint,
    _next_slot,
    _reconcile_checkpoint,
    _sample_heartbeat,
    _sample_resource,
    build_monitor_config,
    monitor_status,
    run_soak_monitor,
    safe_r_worker_count,
)


def _contract(root: Path, *, monitor: dict | None = None) -> Path:
    output = root / "output"
    output.mkdir()
    worker = root / "worker.R"
    worker.write_text("cat('ok')\n", encoding="utf-8")
    path = root / "contract.json"
    path.write_text(
        json.dumps(
            {
                "task_key": "monitor-test",
                "transport": "native-wrapper",
                "artifacts": {"output_root": str(output)},
                "monitor": monitor or {},
                "workers": [
                    {
                        "id": "w01",
                        "code_file": str(worker),
                        "expected_state": "state_w01.json",
                        "expected_manifest": "manifest_w01.csv",
                        "expected_validation": "validation_w01.csv",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _config(root: Path, *, monitor: dict | None = None) -> dict:
    contract = _contract(root, monitor=monitor)
    return build_monitor_config(
        contract_path=str(contract),
        evidence_dir=str(root / "evidence"),
        expected_pid=1234,
        port=8788,
        stop_file=str(root / "stop.monitor"),
    )


class FakeProcess:
    def __init__(self, *, name: str = "R", cmdline: list[str] | None = None, error: Exception | None = None):
        self.pid = 42
        self._name = name
        self._cmdline = cmdline or []
        self._error = error

    def name(self) -> str:
        return self._name

    def cmdline(self) -> list[str]:
        if self._error:
            raise self._error
        return self._cmdline


class SoakMonitorTests(unittest.TestCase):
    def test_process_iter_start_system_error_is_nonfatal(self) -> None:
        def broken_iter():
            raise SystemError("proc_cmdline returned a result with an exception set")

        count, errors = safe_r_worker_count(broken_iter)
        self.assertIsNone(count)
        self.assertIn("SystemError", errors[0])

    def test_per_process_permission_and_system_errors_are_skipped(self) -> None:
        processes = [
            FakeProcess(error=PermissionError("denied")),
            FakeProcess(error=SystemError("bad cmdline")),
            FakeProcess(name="R", cmdline=["R", "--worker"]),
        ]
        count, errors = safe_r_worker_count(lambda: iter(processes))
        self.assertEqual(count, 1)
        self.assertEqual(len(errors), 2)

    def test_exact_scheduled_slot_accounting_reproduces_73_of_74(self) -> None:
        checkpoint = {
            "next_heartbeat_epoch": 1000.0,
            "heartbeat_planned": 72,
            "heartbeat_missed_slots": 0,
            "heartbeat_success": 72,
        }
        scheduled, missed = _next_slot(checkpoint, "heartbeat", 60.0, 1060.0)
        self.assertEqual(scheduled, 1060.0)
        self.assertEqual(missed, 1)
        self.assertEqual(checkpoint["heartbeat_planned"], 74)
        self.assertEqual(checkpoint["heartbeat_missed_slots"], 1)
        checkpoint["heartbeat_success"] += 1
        self.assertEqual(checkpoint["heartbeat_success"] / checkpoint["heartbeat_planned"], 73 / 74)

    def test_csv_resume_does_not_duplicate_header(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "heartbeat.csv"
            row = {name: "" for name in HEARTBEAT_FIELDS}
            _append_csv(path, HEARTBEAT_FIELDS, row)
            _append_csv(path, HEARTBEAT_FIELDS, row)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines.count(",".join(HEARTBEAT_FIELDS)), 1)
            self.assertEqual(len(lines), 3)

    def test_checkpoint_requires_explicit_resume_and_preserves_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = _config(root)
            first = _load_checkpoint(config, resume=False)
            with self.assertRaises(FileExistsError):
                _load_checkpoint(config, resume=False)
            resumed = _load_checkpoint(config, resume=True)
            self.assertEqual(first["logical_run_id"], resumed["logical_run_id"])

    def test_reconcile_recovers_csv_row_written_before_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = _config(root)
            checkpoint = _load_checkpoint(config, resume=False)
            row = {name: "" for name in HEARTBEAT_FIELDS}
            row.update(
                {
                    "sequence": 1,
                    "scheduled_utc": "2026-08-20T00:00:00Z",
                    "timestamp_utc": "2026-08-20T00:00:00Z",
                    "ok": True,
                    "latency_sec": "0.1",
                    "missed_before_slot": 0,
                }
            )
            _append_csv(Path(config["evidence_dir"]) / "heartbeat.csv", HEARTBEAT_FIELDS, row)
            reconciled = _reconcile_checkpoint(config, checkpoint)
            self.assertEqual(reconciled["heartbeat_observed"], 1)
            self.assertEqual(reconciled["heartbeat_planned"], 1)
            self.assertEqual(reconciled["heartbeat_success"], 1)

    def test_noncritical_worker_enumeration_failure_still_writes_resource_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = _config(root)
            checkpoint = _initial_checkpoint(config, 1000.0)
            with mock.patch("clauder_workbench.soak_monitor.psutil.cpu_percent", return_value=10.0), mock.patch(
                "clauder_workbench.soak_monitor.psutil.virtual_memory", return_value=mock.Mock(percent=50.0)
            ), mock.patch(
                "clauder_workbench.soak_monitor.psutil.disk_usage", return_value=mock.Mock(free=100_000_000_000)
            ), mock.patch(
                "clauder_workbench.soak_monitor.psutil.pid_exists", return_value=True
            ), mock.patch(
                "clauder_workbench.soak_monitor.port_open", return_value=True
            ), mock.patch(
                "clauder_workbench.soak_monitor.psutil.process_iter", side_effect=SystemError("macOS proc_cmdline")
            ):
                contract = json.loads(Path(config["contract"]).read_text(encoding="utf-8"))
                contract["_contract_path"] = config["contract"]
                _sample_resource(config, contract, checkpoint, 1000.0, 0)
            with (Path(config["evidence_dir"]) / "resource_samples.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["ok"], "True")
            self.assertEqual(rows[0]["r_worker_count"], "")
            self.assertFalse(checkpoint["aborted"])

    def test_heartbeat_error_is_recorded_without_immediate_abort(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = _config(root)
            checkpoint = _initial_checkpoint(config, 1000.0)
            with mock.patch(
                "clauder_workbench.soak_monitor.call_tool",
                return_value={"ok": False, "reason": "TimeoutError"},
            ):
                _sample_heartbeat(config, checkpoint, 1000.0, 0)
            self.assertEqual(checkpoint["heartbeat_failures"], 1)
            self.assertFalse(checkpoint["aborted"])
            with (Path(config["evidence_dir"]) / "heartbeat.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["ok"], "False")

    def test_disk_safety_gate_blocks_and_calls_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = _config(root)
            checkpoint = _initial_checkpoint(config, 1000.0)
            with mock.patch("clauder_workbench.soak_monitor.psutil.cpu_percent", return_value=10.0), mock.patch(
                "clauder_workbench.soak_monitor.psutil.virtual_memory", return_value=mock.Mock(percent=50.0)
            ), mock.patch(
                "clauder_workbench.soak_monitor.psutil.disk_usage", return_value=mock.Mock(free=70_000_000_000)
            ), mock.patch(
                "clauder_workbench.soak_monitor.psutil.pid_exists", return_value=True
            ), mock.patch(
                "clauder_workbench.soak_monitor.port_open", return_value=True
            ), mock.patch(
                "clauder_workbench.soak_monitor.safe_r_worker_count", return_value=(1, [])
            ), mock.patch("clauder_workbench.soak_monitor._cancel_jobs") as cancel:
                contract = json.loads(Path(config["contract"]).read_text(encoding="utf-8"))
                contract["_contract_path"] = config["contract"]
                _sample_resource(config, contract, checkpoint, 1000.0, 0)
            self.assertTrue(checkpoint["aborted"])
            cancel.assert_called_once()

    def test_finalize_blocks_one_missed_slot_below_99_percent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = _config(root)
            checkpoint = _initial_checkpoint(config, 1000.0)
            checkpoint.update(
                {
                    "heartbeat_planned": 74,
                    "heartbeat_observed": 73,
                    "heartbeat_success": 73,
                    "heartbeat_missed_slots": 1,
                }
            )
            Path(config["stop_file"]).touch()
            Path(config["evidence_dir"]).mkdir(exist_ok=True)
            for idx in range(73):
                row = {name: "" for name in HEARTBEAT_FIELDS}
                row.update(
                    {
                        "sequence": idx + 1,
                        "scheduled_utc": f"2026-08-20T00:{idx % 60:02d}:00Z",
                        "timestamp_utc": f"2026-08-20T00:{idx % 60:02d}:00Z",
                        "ok": True,
                        "latency_sec": "0.1",
                    }
                )
                _append_csv(Path(config["evidence_dir"]) / "heartbeat.csv", HEARTBEAT_FIELDS, row)
            _append_csv(
                Path(config["evidence_dir"]) / "resource_samples.csv",
                RESOURCE_FIELDS,
                {name: "" for name in RESOURCE_FIELDS},
            )
            Path(config["checkpoint_path"]).write_text(json.dumps(checkpoint), encoding="utf-8")
            evidence = _finalize(config)
            self.assertEqual(evidence["decision"], "BLOCK")
            self.assertIn("heartbeat_success_ge_minimum", evidence["policy_violations"])

    def test_supervisor_restart_preserves_logical_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = _config(root)
            original = _load_checkpoint(config, resume=False)
            Path(config["checkpoint_path"]).unlink()

            exits = iter([70, 0])

            class Process:
                def __init__(self, **_: object):
                    self.exitcode = None

                def start(self) -> None:
                    return None

                def join(self) -> None:
                    self.exitcode = next(exits)
                    if self.exitcode == 0:
                        Path(config["stop_file"]).touch()

            context = mock.Mock()
            context.Process.side_effect = lambda *args, **kwargs: Process()
            with mock.patch("clauder_workbench.soak_monitor.multiprocessing.get_context", return_value=context), mock.patch(
                "clauder_workbench.soak_monitor.time.sleep"
            ), mock.patch(
                "clauder_workbench.soak_monitor._finalize", return_value={"decision": "PASS"}
            ):
                result = run_soak_monitor(config, resume=False)
            checkpoint = json.loads(Path(config["checkpoint_path"]).read_text(encoding="utf-8"))
            self.assertEqual(result["decision"], "PASS")
            self.assertNotEqual(original["logical_run_id"], checkpoint["logical_run_id"])
            self.assertEqual(checkpoint["supervised_restarts"], 1)

    def test_monitor_parent_gate_requires_pass_and_matching_task(self) -> None:
        summary = {"checks": {"heartbeat": True, "resources": True}}
        good = build_evidence(
            "soak_monitor",
            "PASS",
            task_key="task-a",
            transport_class="MCP_STDIO_OK",
            extra={"monitored_transport": "NATIVE_MCP_OK", "summary": summary},
        )
        self.assertTrue(_soak_monitor_parent_ok([good], "task-a", 120))
        self.assertFalse(_soak_monitor_parent_ok([good], "task-b", 120))
        bad = dict(good, decision="BLOCK")
        self.assertFalse(_soak_monitor_parent_ok([bad], "task-a", 120))
        stale = dict(good, timestamp_utc="2020-01-01T00:00:00Z")
        self.assertFalse(_soak_monitor_parent_ok([stale], "task-a", 120))

    def test_formal_completion_requires_monitor_parent(self) -> None:
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
                "--require-soak-monitor",
            ]
        )
        captured: list[dict] = []

        def emit(doc: dict, *, write: bool = True) -> int:
            captured.append(doc)
            return int(doc["exit_code"])

        with mock.patch("clauder_workbench.cli.emit", emit), mock.patch(
            "clauder_workbench.cli.load_inflight", return_value=None
        ):
            self.assertEqual(cmd_completion_check(args), 5)
        self.assertIn("MISSING-SOAK-MONITOR-EVIDENCE", captured[0]["policy_violations"])

    def test_formal_completion_accepts_matching_monitor_parent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td) / "monitor.json"
            parent.write_text(
                json.dumps(
                    build_evidence(
                        "soak_monitor",
                        "PASS",
                        task_key="task-a",
                        transport_class="MCP_STDIO_OK",
                        extra={
                            "monitored_transport": "NATIVE_MCP_OK",
                            "summary": {"checks": {"heartbeat": True, "resources": True}},
                        },
                    )
                ),
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                [
                    "completion-check",
                    "--mode",
                    "formal",
                    "--policy",
                    "strict",
                    "--task-key",
                    "task-a",
                    "--require-soak-monitor",
                    "--parent-evidence",
                    str(parent),
                ]
            )
            with mock.patch(
                "clauder_workbench.cli.emit", lambda doc, write=True: int(doc["exit_code"])
            ), mock.patch("clauder_workbench.cli.load_inflight", return_value=None):
                self.assertEqual(cmd_completion_check(args), 0)

    def test_status_reads_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = _config(root)
            checkpoint = _load_checkpoint(config, resume=False)
            status = monitor_status(config)
            self.assertEqual(status["logical_run_id"], checkpoint["logical_run_id"])
            self.assertEqual(status["status"], "running")

    def test_fanout_schema_copies_match_and_document_monitor(self) -> None:
        shared = Path("shared/schemas/fanout-contract.schema.json")
        packaged = Path("skills/clauder-rstudio-workbench/schemas/fanout-contract.schema.json")
        self.assertEqual(shared.read_bytes(), packaged.read_bytes())
        schema = json.loads(shared.read_text(encoding="utf-8"))
        self.assertIn("monitor", schema["properties"])
        self.assertIn("require_soak_monitor", schema["properties"])


if __name__ == "__main__":
    unittest.main()
