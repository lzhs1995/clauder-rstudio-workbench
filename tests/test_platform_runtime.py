from __future__ import annotations

import unittest
from pathlib import Path

from clauder_workbench.installer import build_parser
from clauder_workbench.platform_runtime import (
    cache_dir,
    platform_name,
    resolve_runtime,
    user_home,
)


class PlatformRuntimeTests(unittest.TestCase):
    def test_supported_platform_names(self) -> None:
        self.assertEqual(platform_name("win32"), "windows")
        self.assertEqual(platform_name("darwin"), "macos")
        self.assertEqual(platform_name("linux"), "linux")

    def test_unknown_platform_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            platform_name("plan9")

    def test_home_environment_is_platform_specific(self) -> None:
        self.assertEqual(user_home(system="win32", environ={"USERPROFILE": "C:/Users/U"}), Path("C:/Users/U"))
        self.assertEqual(user_home(system="darwin", environ={"HOME": "/Users/u"}), Path("/Users/u"))
        self.assertEqual(user_home(system="linux", environ={"HOME": "/home/u"}), Path("/home/u"))

    def test_cache_roots_are_platform_specific(self) -> None:
        home = Path("/example/home")
        self.assertEqual(cache_dir(home, system="win32", environ={"LOCALAPPDATA": "C:/Local"}), Path("C:/Local/uv/cache"))
        self.assertEqual(cache_dir(home, system="darwin", environ={}), Path("/example/home/Library/Caches/uv"))
        self.assertEqual(cache_dir(home, system="linux", environ={"XDG_CACHE_HOME": "/cache"}), Path("/cache/uv"))

    def test_runtime_executable_and_wrapper_names(self) -> None:
        windows = resolve_runtime(system="win32", environ={"USERPROFILE": "C:/Users/U", "LOCALAPPDATA": "C:/Local"})
        macos = resolve_runtime(system="darwin", environ={"HOME": "/Users/u"})
        linux = resolve_runtime(system="linux", environ={"HOME": "/home/u"})
        self.assertEqual(windows.bridge_name, "clauder-mcp.exe")
        self.assertEqual(windows.workbench_path, Path("C:/Users/U/bin/clauder-workbench.cmd"))
        self.assertEqual(macos.bridge_path, Path("/Users/u/.local/bin/clauder-mcp"))
        self.assertEqual(linux.workbench_path, Path("/home/u/.local/bin/clauder-workbench"))
        self.assertEqual(windows.home_env, "USERPROFILE")
        self.assertEqual(macos.home_env, "HOME")
        self.assertEqual(linux.cache_env, "XDG_CACHE_HOME")
        self.assertEqual(
            windows.default_python,
            Path("C:/Local/Programs/Python/Python314/python.exe"),
        )

    def test_runtime_has_no_shared_user_path(self) -> None:
        for system in ("win32", "darwin", "linux"):
            runtime = resolve_runtime(system=system, environ={"HOME": "/portable", "USERPROFILE": "C:/portable"})
            self.assertNotIn("/Users/lzhs", str(runtime.home))
        self.assertEqual(str(resolve_runtime(system="win32", environ={"USERPROFILE": "C:/portable"}).home), "C:/portable")

    def test_installer_advertises_all_supported_systems(self) -> None:
        self.assertIn("Windows, macOS, or Linux", build_parser().description)


if __name__ == "__main__":
    unittest.main()
