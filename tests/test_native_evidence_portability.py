from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from clauder_workbench import cli


class NativeEvidencePortabilityTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        old_cwd = Path.cwd()
        self.stack.callback(os.chdir, old_cwd)
        os.chdir(self.root)
        for name, value in (("NATIVE_SMOKE_DIR", self.root / "state"),
                            ("NATIVE_SMOKE_ARCHIVE_DIR", self.root / "archive"),
                            ("EVIDENCE_DIR", self.root / "evidence")):
            self.stack.enter_context(mock.patch.object(cli, name, value))
        self.docs = []

        def emit(doc, **kwargs):
            self.docs.append(doc)
            return doc["exit_code"]

        self.stack.enter_context(mock.patch.object(cli, "emit", side_effect=emit))
        self.assertEqual(self.run_gate("start", "--session-name", "A", "--agent", "codex", "--require-raw-file"), 0)
        for step, extra, output in (
            ("list_sessions", ["--session-name", "A"], "A pid=123"),
            ("execute_r", ["--marker", "NATIVE_EXECUTE_OK", "--pid", "123"], "NATIVE_EXECUTE_OK pid=123"),
            ("execute_r_async", ["--job-id", "test-job"], "started test-job"),
            ("get_async_result", ["--job-id", "test-job", "--marker", "NATIVE_ASYNC_DONE"], "test-job NATIVE_ASYNC_DONE"),
        ):
            Path(step + ".txt").write_text(output, encoding="utf-8")
            self.assertEqual(self.run_gate("record", "--step", step, "--ok", "--raw-file", step + ".txt", *extra), 0)
        self.state = json.loads((self.root / "state" / "portable.json").read_text())

    def run_gate(self, *args):
        return cli.main(["native-smoke", *args, "--task-key", "portable"])

    def test_complete_after_cwd_change_and_original_move(self):
        for step, entry in self.state["steps"].items():
            self.assertTrue(Path(entry["raw_file"]).is_absolute())
            (self.root / (step + ".txt")).rename(self.root / (step + ".moved"))
        other = self.root / "other"
        other.mkdir()
        os.chdir(other)
        self.assertEqual(self.run_gate("complete"), 0)
        self.assertEqual(len(self.docs[-1]["parent_evidence_ids"]), 4)

    def test_tampered_unmarked_step_copy_blocks_completion(self):
        proof = self.state["steps"]["execute_r_async"]["raw_file_proof"]
        Path(proof["evidence_copy"]).write_text("unrelated replacement", encoding="utf-8")
        self.assertEqual(self.run_gate("complete"), 3)
        self.assertIn("hash/size mismatch", " ".join(self.docs[-1]["reasons"]))

    def test_missing_preserved_copy_blocks_even_when_original_exists(self):
        proof = self.state["steps"]["list_sessions"]["raw_file_proof"]
        path = Path(proof["evidence_copy"])
        path.rename(path.with_suffix(".moved"))
        self.assertEqual(self.run_gate("complete"), 3)


if __name__ == "__main__":
    unittest.main()
