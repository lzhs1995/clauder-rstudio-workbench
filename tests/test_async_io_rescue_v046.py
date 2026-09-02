from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench.async_io_rescue import (
    _run,
    _runtime_snapshot,
    build_drain_code,
    build_rescue_config,
    rescue_status,
)
from clauder_workbench.cli import build_parser


class AsyncIoRescueTests(unittest.TestCase):
    def _runtime(self, root: Path, running: list[dict] | None = None, pending: list[str] | None = None) -> Path:
        path = root / "fanout_runtime_status.json"
        path.write_text(
            json.dumps(
                {
                    "task_key": "task-a",
                    "iteration": 7,
                    "running": running or [],
                    "pending": pending or [],
                    "done": ["w00"],
                    "failed": [],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_parser_exposes_run_and_status(self) -> None:
        args = build_parser().parse_args(
            [
                "async-io-rescue",
                "status",
                "--runtime-status",
                "/tmp/runtime.json",
                "--session-name",
                "default",
                "--evidence-dir",
                "/tmp/evidence",
            ]
        )
        self.assertEqual(args.cmd, "async-io-rescue")
        self.assertEqual(args.action, "status")

    def test_runtime_snapshot_tracks_only_recorded_running_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = self._runtime(
                root,
                running=[{"id": "w01", "job_id": "original-1"}, {"id": "w02"}],
                pending=["w03"],
            )
            first = _runtime_snapshot(path)
            self.assertEqual(first["job_ids"], ["original-1"])
            self.assertEqual(first["pending"], ["w03"])

            self._runtime(root, running=[{"id": "w03", "job_id": "original-3"}])
            second = _runtime_snapshot(path)
            self.assertEqual(second["job_ids"], ["original-3"])

    def test_drain_code_cannot_submit_or_cancel(self) -> None:
        code = build_drain_code(["original-1"], "/tmp/logs")
        self.assertIn("read_output_bytes", code)
        self.assertIn("read_error_bytes", code)
        self.assertNotIn("execute_r_async", code)
        self.assertNotIn("cancel_async_job", code)
        self.assertNotIn("$kill", code)

    def test_status_uses_durable_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = self._runtime(root)
            config = build_rescue_config(
                runtime_status=str(runtime), session_name="default", evidence_dir=str(root / "evidence")
            )
            self.assertEqual(rescue_status(config)["status"], "not_started")
            checkpoint = Path(config["checkpoint"])
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_text(
                json.dumps({"job_ids": ["original-1"], "pending": [], "submissions_performed": 0, "cancellations_performed": 0}),
                encoding="utf-8",
            )
            status = rescue_status(config)
            self.assertEqual(status["status"], "active")
            self.assertEqual(status["submissions_performed"], 0)
            self.assertEqual(status["cancellations_performed"], 0)

    def test_reconnect_keeps_same_runtime_and_never_mutates_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = self._runtime(root)
            config = build_rescue_config(
                runtime_status=str(runtime),
                session_name="default",
                evidence_dir=str(root / "evidence"),
                max_connection_failures=2,
            )

            async def fake_sleep(_: float) -> None:
                return None

            with mock.patch(
                "clauder_workbench.async_io_rescue._run_connection",
                new=mock.AsyncMock(side_effect=[RuntimeError("transport closed"), True]),
            ) as connection, mock.patch(
                "clauder_workbench.async_io_rescue.asyncio.sleep", side_effect=fake_sleep
            ):
                result = asyncio.run(_run(config, once=False))

            self.assertEqual(result["decision"], "PASS")
            self.assertEqual(connection.await_count, 2)
            self.assertEqual(result["extra"]["submissions_performed"], 0)
            self.assertEqual(result["extra"]["cancellations_performed"], 0)


if __name__ == "__main__":
    unittest.main()
