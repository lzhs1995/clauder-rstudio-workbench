import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from clauder_workbench.compatibility import verify_source


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "ui.R").write_bytes(b"known-runtime")
        self.manifest = self.root / "manifest.json"
        self.doc = {"clauder_ref": "test-tag", "clauder_commit": "abc",
                    "critical_file_sha256": {"ui.R": hashlib.sha256(b"known-runtime").hexdigest()}}
        self.manifest.write_text(json.dumps(self.doc))

    def test_archive_scope_is_explicit(self):
        result = verify_source(self.manifest, self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["scope"], "archive_critical_files_only")

    def test_changed_critical_source_is_rejected(self):
        (self.root / "ui.R").write_bytes(b"changed-runtime")
        self.assertFalse(verify_source(self.manifest, self.root)["ok"])

    def test_git_commit_and_dirty_source_are_both_checked(self):
        (self.root / ".git").mkdir()
        for commit, status, expected in (("abc", "", True), ("other", "", False), ("abc", " M ui.R", False)):
            with mock.patch("subprocess.check_output", side_effect=[commit, status]):
                self.assertEqual(verify_source(self.manifest, self.root)["ok"], expected)

    def test_manifest_cannot_read_outside_source(self):
        self.doc["critical_file_sha256"] = {"../outside": "hash"}
        self.manifest.write_text(json.dumps(self.doc))
        with self.assertRaises(ValueError):
            verify_source(self.manifest, self.root)
