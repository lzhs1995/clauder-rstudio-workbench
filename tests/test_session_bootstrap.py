import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from clauder_workbench import session_bootstrap


class SessionBootstrapTests(unittest.TestCase):
    def test_valid_global_contract_passes_without_claiming_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.toml"
            config.write_text(
                '[mcp_servers.r-studio]\n'
                f'command = "{(root / "clauder-mcp").as_posix()}"\n'
                'startup_timeout_sec = 180\n'
                '[mcp_servers.r-studio.env]\nHOME = "/home/test"\n',
                encoding="utf-8",
            )
            bridge = root / "clauder-mcp"
            bridge.touch()
            with patch.object(session_bootstrap, "CODEX_CONFIG", config), \
                 patch.object(session_bootstrap, "PERSISTENT_MCP", bridge), \
                 patch.object(session_bootstrap, "LOCAL_CLAUDER_BRIDGE", bridge), \
                 patch.object(session_bootstrap, "EVIDENCE_DIR", root / "evidence"), \
                 redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(session_bootstrap.run(fail_closed=True), 0)
                # Codex 0.156.1 denies unknown SessionStart output fields.
                # The full receipt must not leak into a custom top-level key.
                self.assertEqual(json.loads(stdout.getvalue()), {"continue": True})
                records = list((root / "evidence").glob("*_session_bootstrap_*.json"))
                self.assertEqual(len(records), 1)
                doc = json.loads(records[0].read_text())
                self.assertEqual(doc["decision"], "PASS")
                self.assertEqual(doc["extra"]["native_registration"], "UNKNOWN")

    def test_invalid_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.toml"
            config.write_text("not = [valid\n", encoding="utf-8")
            with patch.object(session_bootstrap, "CODEX_CONFIG", config), \
                 patch.object(session_bootstrap, "LOCAL_CLAUDER_BRIDGE", root / "missing"), \
                 patch.object(session_bootstrap, "EVIDENCE_DIR", root / "evidence"), \
                 redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(session_bootstrap.run(fail_closed=True), 3)
                output = json.loads(stdout.getvalue())
                self.assertEqual(set(output), {"continue", "stopReason", "systemMessage"})
                self.assertIs(output["continue"], False)
                self.assertIn("Codex config is not valid TOML", output["stopReason"])
                records = list((root / "evidence").glob("*_session_bootstrap_*.json"))
                self.assertEqual(len(records), 1)
                self.assertEqual(json.loads(records[0].read_text())["decision"], "BLOCK")
                self.assertIn(str(records[0]), output["systemMessage"])


if __name__ == "__main__":
    unittest.main()
