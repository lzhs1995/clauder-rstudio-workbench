"""Fault-injection tests for isolated pair selection; never install real R/uv."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from clauder_workbench import paired_release as pair


class PairedFullUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="paired-full-upgrade-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.wb = self.root / "workbench source"
        self.cr = self.root / "ClaudeR source"
        self.wb.mkdir()
        (self.wb / "pyproject.toml").write_text('[project]\nversion="1.0.0"\n', encoding="utf-8")
        (self.cr / "clauder-mcp" / "src" / "clauder_mcp").mkdir(parents=True)
        self.server = self.cr / "clauder-mcp" / "src" / "clauder_mcp" / "server.py"
        self.server.write_bytes(b"# candidate bridge\n")
        (self.cr / "DESCRIPTION").write_bytes(b"Package: ClaudeR\nVersion: 2.0.0\n")
        (self.cr / "clauder-mcp" / "pyproject.toml").write_text('[project]\nversion="3.0.0"\n', encoding="utf-8")
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({
            "clauder_ref": "fixture", "clauder_commit": "fixture", "workbench_version": "1.0.0",
            "r_package_version": "2.0.0", "mcp_bridge_version": "3.0.0",
            "critical_file_sha256": {p.relative_to(self.cr).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in [self.server, self.cr / "DESCRIPTION", self.cr / "clauder-mcp" / "pyproject.toml"]},
        }), encoding="utf-8")
        self.releases = self.root / "isolated releases"
        self.kw = dict(release_root=self.releases, workbench_source=self.wb,
                       clauder_source=self.cr, manifest_path=self.manifest,
                       python="fixture-python", r="fixture-R", rscript="fixture-Rscript")
        self.calls = []
        self.bridge_patch = mock.patch.object(pair, "verify_bridge", side_effect=self.bridge_probe)
        self.r_patch = mock.patch.object(pair, "verify_r", side_effect=self.r_probe)
        self.bridge_mock = self.bridge_patch.start()
        self.r_mock = self.r_patch.start()
        self.addCleanup(self.bridge_patch.stop)
        self.addCleanup(self.r_patch.stop)

    def runner(self, command):
        self.calls.append(command)
        if command[1:3] == ["-m", "venv"]:
            venv = Path(command[3])
            scripts = venv / ("Scripts" if os.name == "nt" else "bin")
            scripts.mkdir(parents=True)
            suffix = ".exe" if os.name == "nt" else ""
            for name in ("python", "clauder-mcp", "clauder-workbench"):
                (scripts / (name + suffix)).write_bytes(("fixture " + name).encode())
            (venv / "fixture-bridge").mkdir()
            (venv / "fixture-bridge" / "server.py").write_bytes(self.server.read_bytes())
            (venv / "fixture-workbench").mkdir()
            (venv / "fixture-workbench" / "__init__.py").write_bytes(b"# fixture workbench")
        if "INSTALL" in command:
            library = Path(next(x[len("--library="):] for x in command if x.startswith("--library=")))
            (library / "ClaudeR").mkdir()
            (library / "ClaudeR" / "DESCRIPTION").write_bytes(b"Package: ClaudeR\nVersion: 2.0.0\n")

    def bridge_probe(self, manifest, python, require_workbench=False):
        return {"ok": True, "checks": {"bridge_version": True, "bridge_source_hash": True,
                "workbench_version": require_workbench}, "actual": {"python": str(python),
                "bridge_source": str(python.parent.parent / "fixture-bridge" / "server.py"),
                "workbench_source": str(python.parent.parent / "fixture-workbench" / "__init__.py"),
                "bridge_version": manifest["mcp_bridge_version"], "workbench_version": manifest["workbench_version"]}}

    def r_probe(self, manifest, rscript, library):
        return {"ok": True, "checks": {"R_package_version": True, "R_package_library": True},
                "actual": {"version": manifest["r_package_version"], "path": str(library / "ClaudeR")}}

    def stage(self, name):
        return pair.stage(**self.kw, release_id=name, apply=True, runner=self.runner)

    def test_default_stage_is_no_write_no_probe_no_install(self):
        result = pair.stage(**self.kw, release_id="new", runner=self.runner)
        self.assertEqual(result["status"], "PLAN")
        self.assertFalse(self.releases.exists())
        self.assertEqual(self.calls, [])
        self.bridge_mock.assert_not_called()
        self.r_mock.assert_not_called()

    def test_pair_is_staged_outside_live_environment_and_rollback_restores_same_pair(self):
        self.stage("old")
        first = pair.activate(self.releases / "old", expected_active_sha="ABSENT", apply=True)
        old_pointer = (self.releases / "active.json").read_bytes()
        self.stage("new")
        plan = pair.activate(self.releases / "new", expected_active_sha=first["after_sha256"])
        self.assertEqual(plan["status"], "PLAN")
        self.assertEqual((self.releases / "active.json").read_bytes(), old_pointer)
        second = pair.activate(self.releases / "new", expected_active_sha=first["after_sha256"], apply=True)
        result = pair.rollback(self.releases, activation_id=second["event_id"],
                               expected_active_sha=second["after_sha256"], apply=True)
        self.assertEqual(result["status"], "SELECTED_PAIR_ONLY")
        self.assertEqual((self.releases / "active.json").read_bytes(), old_pointer)
        expected_scripts = "Scripts" if os.name == "nt" else "bin"
        expected_python = "python.exe" if os.name == "nt" else "python"
        self.assertEqual(self.bridge_mock.call_args.args[1],
                         self.releases / "old" / "venv" / expected_scripts / expected_python)
        self.assertEqual(self.r_mock.call_args.args[2], self.releases / "old" / "r-library")
        for command in self.calls:
            self.assertNotIn("tool", command)
            if "INSTALL" in command:
                self.assertTrue(any(x.startswith("--library=" + str(self.releases)) for x in command))
        for name in ("old", "new"):
            self.assertTrue((self.releases / name / "release.json").exists())

    def test_first_selection_can_rollback_to_no_selection(self):
        self.stage("new")
        result = pair.activate(self.releases / "new", expected_active_sha="ABSENT", apply=True)
        pair.rollback(self.releases, activation_id=result["event_id"],
                      expected_active_sha=result["after_sha256"], apply=True)
        self.assertFalse((self.releases / "active.json").exists())
        self.assertTrue((self.releases / "new" / "release.json").exists())

    def test_mismatched_workbench_version_fails_before_directory_creation(self):
        (self.wb / "pyproject.toml").write_text('[project]\nversion="0.0.1"\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Workbench source version"):
            self.stage("new")
        self.assertFalse(self.releases.exists())
        self.assertFalse(self.calls)

    def test_install_failure_retained_and_cannot_select_old_bridge_as_success(self):
        self.stage("old")
        pointer = pair.activate(self.releases / "old", expected_active_sha="ABSENT", apply=True)
        before = (self.releases / "active.json").read_bytes()
        def broken(command):
            self.runner(command)
            if "pip" in command:
                raise subprocess.CalledProcessError(23, command)
        with self.assertRaises(subprocess.CalledProcessError):
            pair.stage(**self.kw, release_id="failed", apply=True, runner=broken)
        failed = self.releases / "failed"
        self.assertTrue((failed / "FAILED.json").exists())
        self.assertFalse((failed / "release.json").exists())
        with self.assertRaises(FileNotFoundError):
            pair.activate(failed, expected_active_sha=pointer["after_sha256"], apply=True)
        self.assertEqual((self.releases / "active.json").read_bytes(), before)
        with self.assertRaises(FileExistsError):
            self.stage("failed")

    def test_loaded_old_bridge_location_is_rejected_even_if_version_matches(self):
        def old_location(*args, **kwargs):
            doc = self.bridge_probe(*args, **kwargs)
            doc["actual"]["bridge_source"] = str(self.root / "old shared uv" / "server.py")
            return doc
        self.bridge_mock.side_effect = old_location
        with self.assertRaisesRegex(RuntimeError, "runtime verification"):
            self.stage("new")
        self.assertFalse((self.releases / "new" / "release.json").exists())

    def test_loaded_wrong_python_is_rejected(self):
        def old_python(*args, **kwargs):
            doc = self.bridge_probe(*args, **kwargs)
            doc["actual"]["python"] = str(self.root / "old python")
            return doc
        self.bridge_mock.side_effect = old_python
        with self.assertRaisesRegex(RuntimeError, "runtime verification"):
            self.stage("new")

    def test_loaded_old_workbench_location_is_rejected_even_if_version_matches(self):
        def old_workbench(*args, **kwargs):
            doc = self.bridge_probe(*args, **kwargs)
            doc["actual"]["workbench_source"] = str(self.root / "old workbench" / "__init__.py")
            return doc
        self.bridge_mock.side_effect = old_workbench
        with self.assertRaisesRegex(RuntimeError, "runtime verification"):
            self.stage("new")

    def test_same_version_installed_package_edit_is_rejected(self):
        self.stage("new")
        release = self.releases / "new"
        (release / "r-library" / "ClaudeR" / "DESCRIPTION").write_bytes(b"modified code, same version")
        with self.assertRaisesRegex(ValueError, "package bytes changed"):
            pair.verify(release)

    def test_r_probe_rejection_does_not_write_success_record(self):
        self.r_mock.side_effect = lambda *args: {"ok": False, "checks": {"R_package_library": False}, "actual": {}}
        with self.assertRaisesRegex(RuntimeError, "runtime verification"):
            self.stage("new")
        self.assertTrue((self.releases / "new" / "FAILED.json").exists())
        self.assertFalse((self.releases / "new" / "release.json").exists())

    def test_changed_source_during_install_is_rejected(self):
        def mutating(command):
            self.runner(command)
            if "INSTALL" in command:
                self.server.write_bytes(b"changed while installing")
        with self.assertRaisesRegex(RuntimeError, "source changed"):
            pair.stage(**self.kw, release_id="new", apply=True, runner=mutating)
        self.assertFalse((self.releases / "new" / "release.json").exists())

    def test_external_active_change_is_not_overwritten_on_activate_or_rollback(self):
        self.stage("old")
        first = pair.activate(self.releases / "old", expected_active_sha="ABSENT", apply=True)
        self.stage("new")
        second = pair.activate(self.releases / "new", expected_active_sha=first["after_sha256"], apply=True)
        external = b'{"external":"keep me"}\n'
        (self.releases / "active.json").write_bytes(external)
        with self.assertRaisesRegex(RuntimeError, "ACTIVE_CONFLICT"):
            pair.activate(self.releases / "old", expected_active_sha=second["after_sha256"], apply=True)
        with self.assertRaisesRegex(RuntimeError, "ACTIVE_CONFLICT"):
            pair.rollback(self.releases, activation_id=second["event_id"],
                          expected_active_sha=second["after_sha256"], apply=True)
        self.assertEqual((self.releases / "active.json").read_bytes(), external)

    def test_rollback_reverifies_old_pair_and_preserves_current_on_failure(self):
        self.stage("old")
        first = pair.activate(self.releases / "old", expected_active_sha="ABSENT", apply=True)
        self.stage("new")
        second = pair.activate(self.releases / "new", expected_active_sha=first["after_sha256"], apply=True)
        before = (self.releases / "active.json").read_bytes()
        self.r_mock.side_effect = lambda *args: {"ok": False, "checks": {"R_package_version": False}, "actual": {}}
        with self.assertRaisesRegex(ValueError, "verification failed"):
            pair.rollback(self.releases, activation_id=second["event_id"],
                          expected_active_sha=second["after_sha256"], apply=True)
        self.assertEqual((self.releases / "active.json").read_bytes(), before)

    def test_tampered_launcher_is_rejected_before_runtime_probe(self):
        self.stage("new")
        release = self.releases / "new"
        record = json.loads((release / "release.json").read_text(encoding="utf-8"))
        (release / record["paths"]["bridge_launcher"]).write_bytes(b"unrelated replacement")
        self.bridge_mock.reset_mock()
        with self.assertRaisesRegex(ValueError, "launcher changed"):
            pair.verify(release)
        self.bridge_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
