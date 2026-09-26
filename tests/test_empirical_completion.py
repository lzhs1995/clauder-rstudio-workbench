"""Receipt integration only: no R process, model, config or connection changes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from clauder_workbench.cli import build_parser, cmd_completion_check


class EmpiricalCompletionTests(unittest.TestCase):
    def test_explicit_empirical_contract_cannot_be_skipped_by_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            def artifact(name, text):
                p = root / name
                p.write_text(text)
                return {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            csv = artifact("sample.csv", "id,x\na,1\nb,2\n")
            contract = {"schema_version": 1, "task_id": "synthetic-completion", "script": artifact("stage.R", "# synthetic source"),
                        "inputs": [csv], "outputs": [csv], "runtime": {key: "recorded" for key in
                        ("session_id", "job_id", "transport", "source_revision", "installed_version", "loaded_version")},
                        "samples": [{"artifact": csv, "keys": ["id"], "expected_n": 2}]}
            file = root / "trace.json"
            args = build_parser().parse_args(["completion-check", "--mode", "diagnostic", "--policy", "skip", "--empirical-contract", str(file)])
            results = []
            def emit(doc):
                results.append(doc)
                return doc["exit_code"]
            with patch("clauder_workbench.cli.emit", side_effect=emit):
                file.write_text(json.dumps(contract))
                self.assertEqual(cmd_completion_check(args), 0)
                contract["samples"][0]["same_members_as"] = artifact("other.csv", "id,x\na,1\nc,2\n")
                file.write_text(json.dumps(contract))
                self.assertEqual(cmd_completion_check(args), 5)
            self.assertFalse(results[-1]["extra"]["empirical_trace"]["pass"])
            self.assertIn("EMPIRICAL-TRACE-CONTRACT-FAILED", results[-1]["policy_violations"])


if __name__ == "__main__":
    unittest.main()
