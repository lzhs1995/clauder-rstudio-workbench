from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench import config, installer


class RuntimeInstallDefaultsTests(unittest.TestCase):
    def test_platform_cache_paths(self):
        base = Path("/example/home")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.default_uv_cache_dir(base, "darwin"), base / "Library/Caches/uv")
            self.assertEqual(config.default_uv_cache_dir(base, "linux"), base / ".cache/uv")
            self.assertEqual(config.default_uv_cache_dir(base, "win32"), base / "AppData/Local/uv/cache")

    def test_explicit_platform_cache_roots(self):
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": "/cache/custom", "LOCALAPPDATA": "/local/custom"}):
            self.assertEqual(config.default_uv_cache_dir(Path("/user"), "linux"), Path("/cache/custom/uv"))
            self.assertEqual(config.default_uv_cache_dir(Path("/user"), "win32"), Path("/local/custom/uv/cache"))

    def test_installer_invokes_noneditable_harness_build(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pyproject.toml").write_text("[project]\nname='test'\nversion='0.0.0'\n")
            (root / "DESCRIPTION").write_text("Package: ClaudeR\n")
            (root / "clauder-mcp").mkdir()
            (root / "skills").mkdir()
            with mock.patch.object(installer.shutil, "which", return_value="/test/uv"), mock.patch.object(installer, "_run") as run:
                self.assertEqual(installer.main(["--repo-root", str(root), "--clauder-dir", str(root), "--skip-r-package", "--skip-mcp", "--dry-run"]), 0)
            self.assertEqual(run.call_args.args[0], ["/test/uv", "tool", "install", "--force", str(root.resolve())])


if __name__ == "__main__":
    unittest.main()
