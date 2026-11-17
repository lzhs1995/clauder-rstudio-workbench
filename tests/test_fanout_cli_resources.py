from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench import cli


class FanoutCliResourceTests(unittest.TestCase):
    def _call(self, root, command, *, selected=None, deficient=False, unknown=False,
              no_advise=False, worker_session=None, remote_root=None):
        contract = {
            "task_key": "synthetic-cli-admission", "session_name": "contract-target",
            "artifacts": {"output_root": str(root)},
            "resource_gate": {"worker_output_root": remote_root or str(root)},
            "workers": [{"id": "one", "code": "1+1", "expected_state": "s.json",
                         "expected_manifest": "m.csv", "expected_validation": "v.csv"}],
        }
        if worker_session:
            contract["workers"][0]["session"] = worker_session
        path = root / "task.json"
        path.write_text(json.dumps(contract))
        args = [command, "--contract", str(path)]
        if selected:
            args += ["--session-name", selected]
        if no_advise:
            args += ["--no-advise"]
        if command == "fanout-run":
            args += ["--max-iterations", "1", "--max-parallel", "2"]
        captured = []
        probes = []

        class FakeTargetProbe:
            def __init__(self, session, output, **kwargs):
                self.session, self.output = session, output
                self.submissions = []
                self.sample_count = 0
                probes.append(self)

            def sample(self):
                self.sample_count += 1
                if unknown:
                    return {"host_verified": False, "reason": "target probe timeout"}
                return {"host_verified": True, "sampled_at": time.time(),
                        "host_id": "synthetic-remote", "session_pid": 101,
                        "output_root": self.output, "physical_available_bytes": 16 * 1024**3,
                        "commit_available_bytes": 0 if deficient else 16 * 1024**3,
                        "logical_processors": 8, "output_free_bytes": 16 * 1024**3}

            def submit(self, code):
                self.submissions.append(code)
                return {"ok": True, "job_id": "synthetic-one", "text": "started"}

            def poll(self, job_id):
                return {"ok": True, "text": f"Job {job_id} is still running"}

        def emit(doc):
            captured.append(doc)
            return doc["exit_code"]

        namespace = cli.build_parser().parse_args(args)
        # 本机富余探针不能成为目标资源不足时的回退。
        with mock.patch.object(cli, "FanoutResourceProbe", FakeTargetProbe), \
             mock.patch.object(cli, "_native_smoke_gate", return_value=(True, False, [], [])), \
             mock.patch.object(cli, "emit", side_effect=emit), \
             mock.patch.object(cli, "write_inflight"), \
             mock.patch.object(cli, "call_tool", return_value={"ok": True, "text": "still running"}), \
             mock.patch("clauder_workbench.fanout.memory_used_percent", return_value=1), \
             mock.patch("clauder_workbench.fanout.disk_free_gb", return_value=1000):
            rc = cli.cmd_fanout_plan(namespace) if command == "fanout-plan" else cli.cmd_fanout_run(namespace)
        return rc, captured[-1], probes

    def test_session_override_and_contract_target_in_plan_and_run(self):
        with tempfile.TemporaryDirectory() as td:
            for command in ("fanout-plan", "fanout-run"):
                for selected in (None, "explicit-target"):
                    with self.subTest(command=command, selected=selected):
                        _, _, probes = self._call(Path(td), command, selected=selected, deficient=True)
                        self.assertEqual(probes[0].session, selected or "contract-target")
                        self.assertEqual(probes[0].sample_count, 1)

    def test_target_shortage_holds_despite_plentiful_local_resources(self):
        with tempfile.TemporaryDirectory() as td:
            for command in ("fanout-plan", "fanout-run"):
                rc, doc, probes = self._call(Path(td), command, deficient=True)
                self.assertEqual(rc, cli.BLOCK)
                self.assertEqual(probes[0].submissions, [])
                self.assertIn("commit", json.dumps(doc).lower())

    def test_probe_timeout_holds_without_local_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            for command in ("fanout-plan", "fanout-run"):
                rc, _, probes = self._call(Path(td), command, unknown=True)
                self.assertEqual(rc, cli.BLOCK)
                self.assertEqual(probes[0].submissions, [])

    def test_target_output_path_is_not_resolved_on_python_host(self):
        with tempfile.TemporaryDirectory() as td:
            _, _, probes = self._call(Path(td), "fanout-plan", remote_root="Q:/synthetic-output")
            self.assertEqual(probes[0].output, "Q:/synthetic-output")

    def test_validation_only_never_constructs_or_calls_probe(self):
        with tempfile.TemporaryDirectory() as td:
            rc, _, probes = self._call(Path(td), "fanout-plan", no_advise=True)
            self.assertEqual(rc, cli.PASS)
            self.assertEqual(probes, [])

    def test_conflicting_worker_session_holds_without_sampling_or_submit(self):
        with tempfile.TemporaryDirectory() as td:
            for command in ("fanout-plan", "fanout-run"):
                rc, _, probes = self._call(Path(td), command, worker_session="different-target")
                self.assertEqual(rc, cli.BLOCK)
                self.assertEqual(probes[0].sample_count, 0)
                self.assertEqual(probes[0].submissions, [])


if __name__ == "__main__":
    unittest.main()
