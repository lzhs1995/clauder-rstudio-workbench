import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from clauder_workbench import session_bootstrap

class SessionBootstrapTests(unittest.TestCase):
    def test_selected_client_result_preserves_output_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            check = {"ok": True, "reasons": [], "warnings": [], "client": "claude"}
            with patch.object(session_bootstrap, "inspect_client", return_value=check) as inspect, patch.object(session_bootstrap, "EVIDENCE_DIR", Path(tmp)), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(session_bootstrap.run(client="claude", config_file=Path("project.json")), 0)
            inspect.assert_called_once_with("claude", Path("project.json"))
            self.assertEqual(json.loads(out.getvalue()), {"continue": True})
            record = json.loads(next(Path(tmp).glob("*.json")).read_text())
            self.assertEqual(record["extra"]["native_registration"], "UNKNOWN")
            self.assertEqual(record["agent"], "claude")

    def test_missing_client_fails_closed_and_no_fail_closed_is_only_exit_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            check = {"ok": False, "reasons": ["R_STUDIO_CONFIG_MISSING"], "warnings": [], "client": "copilot"}
            with patch.object(session_bootstrap, "inspect_client", return_value=check), patch.object(session_bootstrap, "EVIDENCE_DIR", Path(tmp)), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(session_bootstrap.run(client="copilot"), 3)
            self.assertEqual(set(json.loads(out.getvalue())), {"continue", "stopReason", "systemMessage"})
            with patch.object(session_bootstrap, "inspect_client", return_value=check), patch.object(session_bootstrap, "EVIDENCE_DIR", Path(tmp)), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(session_bootstrap.run(client="copilot", fail_closed=False), 0)
            self.assertFalse(json.loads(out.getvalue())["continue"])

if __name__ == "__main__":
    unittest.main()
