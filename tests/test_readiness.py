from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from clauder_workbench import cli, readiness as r
from clauder_workbench.config_store import update_config


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.cfg = self.root / "client.toml"
        self.exe = self.root / ("clauder-mcp.exe" if os.name == "nt" else "clauder-mcp")
        self.exe.touch()
        self.spec_kwargs = dict(command=self.exe, home=self.root, cache=self.root / "cache")
        update_config(self.cfg, client="codex", **self.spec_kwargs)
        self.discovery = self.root / ".claude_r_sessions"
        self.discovery.mkdir()
        self.identity = dict(session_name="A", pid=123, port=48878, started_at="test")
        (self.discovery / "A.json").write_text(json.dumps(self.identity))
        self.probe = self.stack.enter_context(mock.patch.object(r, "connection_probe", return_value={"ok": True, "pid": 123}))
        self.stack.enter_context(mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "unit-test-context"}))
        self.stack.enter_context(mock.patch.object(r, "client_process", return_value={"pid": 42, "created_at": 1.0}))

    def ready(self, **kwargs):
        args = dict(client="codex", session_name="A", task_key="ready", config_file=self.cfg)
        args.update(kwargs)
        return r.ensure_ready(**args)

    def test_read_only_cli_checks_exact_client_configuration(self):
        before = self.cfg.read_bytes()
        with mock.patch.object(cli, "emit", side_effect=lambda d: d["exit_code"]):
            self.assertEqual(cli.main(["ensure-ready", "--client", "codex", "--session-name", "A",
                                      "--task-key", "ready", "--config-file", str(self.cfg)]), 0)
        self.assertEqual(self.cfg.read_bytes(), before)
        self.assertEqual(self.probe.call_args.kwargs["server_spec"][0], str(self.exe))

    def test_json_clients_do_not_read_codex(self):
        for client in ("claude", "copilot"):
            path = self.root / (client + ".json")
            update_config(path, client=client, **self.spec_kwargs)
            doc = self.ready(client=client, config_file=path)
            self.assertEqual(doc["decision"], "PASS", doc)
            self.assertEqual(self.probe.call_args.kwargs["config_path"], path)

    def test_missing_config_does_not_spawn_or_install(self):
        self.cfg.rename(self.root / "saved.toml")
        self.assertEqual(self.ready()["decision"], "BLOCK")
        self.probe.assert_not_called()
        self.assertFalse(self.cfg.exists())

    def test_disabled_entry_is_never_enabled_by_safe_repair(self):
        self.cfg.write_text(self.cfg.read_text().replace("[mcp_servers.r-studio]", "[mcp_servers.r-studio]\nenabled=false"))
        with mock.patch.object(r.config, "PERSISTENT_MCP", self.exe), mock.patch.object(r.config, "HOME", self.root):
            self.assertIn("R_STUDIO_EXPLICITLY_DISABLED", self.ready(repair="safe")["reasons"])
        self.probe.assert_not_called()
        self.assertIn("enabled=false", self.cfg.read_text())

    def test_unknown_discovery_is_not_deleted(self):
        (self.discovery / "A.json").write_text("{")
        self.assertEqual(self.ready()["decision"], "BLOCK")
        self.probe.assert_not_called()
        self.assertEqual((self.discovery / "A.json").read_text(), "{")

    def test_wrong_live_pid_fails_closed(self):
        self.probe.return_value = {"ok": True, "pid": 456}
        self.assertEqual(self.ready()["decision"], "BLOCK")

    def test_discovery_changes_during_probe_fail_closed(self):
        def change(*args, **kwargs):
            (self.discovery / "A.json").write_text(json.dumps({**self.identity, "started_at": "new"}))
            return {"ok": True, "pid": 123}
        self.probe.side_effect = change
        self.assertEqual(self.ready()["decision"], "BLOCK")

    def test_stdio_does_not_satisfy_native(self):
        self.assertEqual(self.ready()["transport_class"], "MCP_STDIO_OK")
        self.assertEqual(self.ready(require_native=True)["decision"], "BLOCK")

    def test_future_and_naive_timestamps_cannot_pass(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        self.assertFalse(cli._timestamp_fresh_enough(future, 60))
        self.assertFalse(cli._timestamp_fresh_enough("2026-09-07T10:00:00", 60))

    def make_native_fixture(self):
        # 合成协议证据只用于单元测试，不进入真实验收目录。
        for key in ("NATIVE_SMOKE_DIR", "NATIVE_SMOKE_ARCHIVE_DIR", "EVIDENCE_DIR"):
            self.stack.enter_context(mock.patch.object(cli, key, self.root / key))
        docs = []
        self.stack.enter_context(mock.patch.object(cli, "emit", side_effect=lambda d: (docs.append(d), d["exit_code"])[1]))
        def gate(*argv):
            return cli.main(["native-smoke", *argv, "--task-key", "ready"])
        self.assertEqual(gate("start", "--session-name", "A", "--agent", "codex", "--require-raw-file", "--config-file", str(self.cfg)), 0)
        for step, flags, txt in (
            ("list_sessions", ["--session-name", "A"], "A pid=123"),
            ("execute_r", ["--pid", "123", "--marker", "SYNC"], "SYNC pid=123"),
            ("execute_r_async", ["--job-id", "j"], "Job j started"),
            ("get_async_result", ["--job-id", "j", "--marker", "DONE"], "j DONE")):
            raw = self.root / (step + ".txt")
            raw.write_text(txt)
            self.assertEqual(gate("record", "--step", step, "--ok", "--raw-file", str(raw), *flags), 0)
        self.assertEqual(gate("complete"), 0)
        path = self.root / "fixture-native.json"
        path.write_text(json.dumps(docs[-1]))
        return path, docs[-1]

    def test_current_chain_passes_native_requirement(self):
        path, _ = self.make_native_fixture()
        self.assertEqual(self.ready(require_native=True, native_evidence=path)["transport_class"], "NATIVE_MCP_OK")

    def test_native_evidence_names_a_different_rstudio_target(self):
        path, doc = self.make_native_fixture()
        for field, value in (("session_name", "another-rstudio"), ("pid", "456")):
            with self.subTest(field=field):
                # 客户端上下文、配置、原始归档均合法，只更改声明的 R 目标。
                path.write_text(json.dumps({**doc, field: value}))
                result = self.ready(require_native=True, native_evidence=path)
                self.assertEqual(result["decision"], "BLOCK")
                self.assertIn("NATIVE_RSTUDIO_IDENTITY_MISMATCH", result["reasons"])

    def test_cross_session_evidence_is_rejected(self):
        path, _ = self.make_native_fixture()
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "different-thread"}):
            self.assertEqual(self.ready(require_native=True, native_evidence=path)["decision"], "BLOCK")

    def test_changed_config_invalidates_native_evidence(self):
        path, _ = self.make_native_fixture()
        self.cfg.write_text(self.cfg.read_text() + "\n# externally changed\n")
        self.assertEqual(self.ready(require_native=True, native_evidence=path)["decision"], "BLOCK")

    def test_resumed_thread_in_new_process_invalidates_native_evidence(self):
        path, _ = self.make_native_fixture()
        with mock.patch.object(r, "client_process", return_value={"pid": 43, "created_at": 2.0}):
            self.assertEqual(self.ready(require_native=True, native_evidence=path)["decision"], "BLOCK")

    def test_tampered_raw_copy_invalidates_consumer(self):
        path, doc = self.make_native_fixture()
        raw = Path(doc["extra"]["steps"]["list_sessions"]["raw_file_proof"]["evidence_copy"])
        raw.write_text("tampered")
        self.assertEqual(self.ready(require_native=True, native_evidence=path)["decision"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
