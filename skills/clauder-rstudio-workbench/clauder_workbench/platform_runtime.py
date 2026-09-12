"""Cross-platform runtime contracts shared by installers and the harness.

The workbench deliberately keeps one behavioural implementation.  This module
contains only operating-system boundaries (paths, executable names and
environment keys), so Windows, macOS and Linux cannot silently drift in the
connection/evidence code.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class PlatformRuntime:
    """Resolved, user-writable platform paths for one process."""

    system: str
    home: Path
    cache_dir: Path
    bridge_name: str
    workbench_name: str
    home_env: str
    cache_env: str
    shell: str
    python_path: Path

    @property
    def bridge_path(self) -> Path:
        return self.home / ".local" / "bin" / self.bridge_name

    @property
    def bridge_python_path(self) -> Path:
        """Python embedded in the uv tool environment, used by the stable launcher."""
        if self.system == "windows":
            return self.home / "AppData" / "Local" / "uv" / "tools" / "clauder-mcp" / "Scripts" / "python.exe"
        return self.home / ".local" / "share" / "uv" / "tools" / "clauder-mcp" / "bin" / "python"

    @property
    def workbench_path(self) -> Path:
        if self.system == "windows":
            return self.home / "bin" / self.workbench_name
        return self.home / ".local" / "bin" / self.workbench_name

    @property
    def default_python(self) -> Path:
        return self.python_path


def platform_name(system: str | None = None, *, os_name: str | None = None) -> str:
    """Return the stable product names: ``windows``, ``macos`` or ``linux``."""
    value = (system or sys.platform).lower()
    if os_name == "nt" or value.startswith("win"):
        return "windows"
    if value in {"darwin", "macos", "mac"}:
        return "macos"
    if value.startswith("linux"):
        return "linux"
    raise ValueError(f"unsupported platform: {system or sys.platform}")


def user_home(*, system: str | None = None, environ: Mapping[str, str] | None = None,
              fallback: Path | None = None) -> Path:
    env = environ if environ is not None else os.environ
    kind = platform_name(system, os_name=("nt" if system == "win32" else None))
    key = "USERPROFILE" if kind == "windows" else "HOME"
    return Path(env.get(key) or fallback or Path.home()).expanduser()


def cache_dir(home: Path, *, system: str | None = None,
              environ: Mapping[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    kind = platform_name(system, os_name=("nt" if system == "win32" else None))
    if kind == "windows":
        base = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
        return base / "uv" / "cache"
    if kind == "macos":
        return home / "Library" / "Caches" / "uv"
    return Path(env.get("XDG_CACHE_HOME") or home / ".cache") / "uv"


def resolve_runtime(*, system: str | None = None,
                    environ: Mapping[str, str] | None = None,
                    fallback_home: Path | None = None) -> PlatformRuntime:
    env = environ if environ is not None else os.environ
    kind = platform_name(system, os_name=("nt" if system == "win32" else None))
    home = user_home(system=system, environ=env, fallback=fallback_home)
    if kind == "windows":
        local = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
        return PlatformRuntime(kind, home, cache_dir(home, system=system, environ=env),
                                "clauder-mcp.exe", "clauder-workbench.cmd",
                                "USERPROFILE", "LOCALAPPDATA", "powershell",
                                local / "Programs" / "Python" / "Python314" / "python.exe")
    return PlatformRuntime(kind, home, cache_dir(home, system=system, environ=env),
                           "clauder-mcp", "clauder-workbench",
                           "HOME", "XDG_CACHE_HOME", "sh", Path(sys.executable))
