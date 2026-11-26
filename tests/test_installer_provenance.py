"""真实临时 Git 夹具验证安装来源；不安装运行时、不修改用户配置。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from clauder_workbench import installer


@unittest.skipUnless(shutil.which("git"), "requires Git for real provenance fixtures")
class InstallerProvenanceTests(unittest.TestCase):
    def setUp(self):
        clean = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        ambient = patch.dict(os.environ, clean, clear=True)
        ambient.start()
        self.addCleanup(ambient.stop)
        temp = tempfile.TemporaryDirectory(prefix="installer-provenance-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.hooks = self.base / "empty-hooks"
        self.hooks.mkdir()
        self.env = dict(
            os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
            GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
            GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
        )

    def git(self, repo, *args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True,
            text=True, env=self.env, timeout=30,
        ).stdout.strip()

    def commit(self, repo, message):
        self.git(repo, "-c", f"core.hooksPath={self.hooks}", "-c", "commit.gpgsign=false",
                 "commit", "-q", "-m", message)

    def repo(self, name):
        repo = self.base / name
        repo.mkdir()
        self.git(repo, "init", "-q")
        (repo / "tracked").write_text(f"{name}\n", encoding="utf-8")
        self.git(repo, "add", "tracked")
        self.commit(repo, "fixture")
        return repo

    def assert_directory(self, value):
        self.assertEqual(value["source_type"], "directory")
        for key in ("commit", "ref", "url", "dirty"):
            self.assertIsNone(value[key], key)

    def test_nested_plain_directory_cannot_inherit_parent(self):
        parent = self.repo("parent")
        self.git(parent, "remote", "add", "origin", "https://example.invalid/wrong-parent.git")
        nested = parent / "release" / "clean-source"
        nested.mkdir(parents=True)
        # Git 自身会向上查找，安装器必须拒绝把外层仓库当来源。
        self.assertEqual(self.git(nested, "rev-parse", "HEAD"), self.git(parent, "rev-parse", "HEAD"))
        self.assert_directory(installer._git_metadata(nested))

    def test_exact_root_records_own_commit_url_and_dirty(self):
        repo = self.repo("actual")
        self.git(repo, "remote", "add", "origin", "https://example.invalid/actual.git")
        value = installer._git_metadata(repo)
        self.assertEqual(value["source_type"], "git")
        self.assertEqual(value["commit"], self.git(repo, "rev-parse", "HEAD"))
        self.assertEqual(value["url"], "https://example.invalid/actual.git")
        self.assertFalse(value["dirty"])
        (repo / "tracked").write_text("changed\n", encoding="utf-8")
        self.assertTrue(installer._git_metadata(repo)["dirty"])

    def test_linked_worktree_dotgit_file_is_valid_root(self):
        repo = self.repo("main")
        linked = self.base / "linked"
        self.git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
        self.assertTrue((linked / ".git").is_file())
        value = installer._git_metadata(linked)
        self.assertEqual(value["source_type"], "git")
        self.assertEqual(value["commit"], self.git(repo, "rev-parse", "HEAD"))
        self.assertEqual(value["ref"], "HEAD")
        self.assertIsNone(value["url"])

    def test_nested_independent_repository_uses_child_identity(self):
        parent = self.repo("parent")
        child = parent / "child"
        child.mkdir()
        self.git(child, "init", "-q")
        (child / "child").write_text("child\n", encoding="utf-8")
        self.git(child, "add", "child")
        self.commit(child, "child")
        value = installer._git_metadata(child)
        self.assertEqual(value["source_type"], "git")
        self.assertEqual(value["commit"], self.git(child, "rev-parse", "HEAD"))
        self.assertNotEqual(value["commit"], self.git(parent, "rev-parse", "HEAD"))

    def test_git_unavailable_does_not_claim_provenance(self):
        directory = self.base / "plain"
        directory.mkdir()
        with patch.object(installer.subprocess, "run", side_effect=FileNotFoundError("fixture unavailable")):
            self.assert_directory(installer._git_metadata(directory))

    def test_install_info_both_directory_sources_use_null_git_fields(self):
        parent = self.repo("parent")
        self.git(parent, "remote", "add", "origin", "https://example.invalid/wrong-parent.git")
        wb = parent / "copied-workbench"
        cr = parent / "copied-clauder"
        wb.mkdir()
        cr.mkdir()
        (cr / "DESCRIPTION").write_text("Package: ClaudeR\nVersion: 0.16.5.9001\n", encoding="utf-8")
        (cr / "clauder-mcp").mkdir()
        (cr / "clauder-mcp/pyproject.toml").write_text('[project]\nversion="0.16.4.post1"\n', encoding="utf-8")
        destination = self.base / "installed-info"
        installer._write_install_info(
            destination, repo_root=wb, clauder_dir=cr, mcp_command=self.base / "unused-launcher",
            uv_cache_dir=self.base / "cache", configured_clients=[], backup_retention=0, dry_run=False,
        )
        info = json.loads((destination / "INSTALL_INFO.json").read_text(encoding="utf-8"))
        for key in ("git_commit", "git_branch_or_tag", "workbench_dirty", "workbench_source_url",
                    "claudeR_commit", "claudeR_ref", "claudeR_dirty", "claudeR_source_url", "claudeR_git_origin"):
            self.assertIsNone(info[key], key)
        self.assertEqual(info["workbench_source_type"], "directory")
        self.assertEqual(info["claudeR_source_type"], "directory")
        self.assertEqual(info["installed_from"], str(wb))
        self.assertEqual(info["skill_backup_retention"], 0)
        self.assertEqual(info["configured_clients"], [])
        self.assertEqual(info["claudeR_version"], "0.16.5.9001")

    def test_git_environment_cannot_make_directory_impersonate_parent(self):
        parent = self.repo("parent")
        nested = parent / "copied-source"
        nested.mkdir()
        with patch.dict(os.environ, {"GIT_DIR": str(parent / ".git"), "GIT_WORK_TREE": str(nested)}):
            self.assert_directory(installer._git_metadata(nested))

    def test_git_environment_cannot_redirect_actual_source(self):
        unrelated = self.repo("unrelated")
        actual = self.repo("actual-source")
        self.git(actual, "remote", "add", "origin", "https://example.invalid/actual-source.git")
        expected = self.git(actual, "rev-parse", "HEAD")
        self.assertNotEqual(expected, self.git(unrelated, "rev-parse", "HEAD"))
        overrides = {
            "GIT_DIR": str(unrelated / ".git"), "GIT_WORK_TREE": str(actual),
            "GIT_INDEX_FILE": str(unrelated / ".git/index"), "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "remote.origin.url",
            "GIT_CONFIG_VALUE_0": "https://example.invalid/injected.git",
        }
        with patch.dict(os.environ, overrides):
            value = installer._git_metadata(actual)
            self.assertEqual(value["source_type"], "git")
            self.assertEqual(value["commit"], expected)
            self.assertEqual(value["url"], "https://example.invalid/actual-source.git")
            self.assertFalse(value["dirty"])


if __name__ == "__main__":
    unittest.main()
