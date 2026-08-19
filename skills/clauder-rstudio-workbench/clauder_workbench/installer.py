from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__


def _run(command: list[str], *, dry_run: bool = False) -> None:
    print("+", shlex.join(command))
    if dry_run:
        return
    subprocess.run(command, check=True)


def _git_value(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _toml_string(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _remove_toml_sections(text: str, names: set[str]) -> str:
    output: list[str] = []
    skip = False
    for line in text.splitlines():
        match = re.match(r"^\s*\[([^]]+)]\s*$", line)
        if match:
            skip = match.group(1) in names
            if not skip:
                output.append(line)
            continue
        if not skip:
            output.append(line)
    return "\n".join(output).rstrip()


def update_codex_config(
    config_path: Path,
    mcp_command: Path,
    home: Path,
    uv_cache_dir: Path,
    *,
    dry_run: bool = False,
) -> Path | None:
    existing = config_path.read_text(encoding="utf-8-sig") if config_path.exists() else ""
    cleaned = _remove_toml_sections(
        existing,
        {"mcp_servers.r-studio", "mcp_servers.r-studio.env"},
    )
    env_lines = [
        f"HOME = {_toml_string(home)}",
        'PYTHONIOENCODING = "utf-8"',
        'NO_PROXY = "127.0.0.1,localhost"',
        f"UV_CACHE_DIR = {_toml_string(uv_cache_dir)}",
    ]
    if os.name == "nt":
        env_lines.insert(1, f"USERPROFILE = {_toml_string(home)}")
    block = "\n".join([
        "[mcp_servers.r-studio]",
        f"command = {_toml_string(mcp_command)}",
        "startup_timeout_sec = 180.0",
        "",
        "[mcp_servers.r-studio.env]",
        *env_lines,
    ])
    updated = f"{cleaned}\n\n{block}\n" if cleaned else f"{block}\n"

    try:
        import tomllib
    except ImportError:  # pragma: no cover - Python 3.10 fallback
        import tomli as tomllib  # type: ignore[no-redef]
    tomllib.loads(updated)

    backup = None
    if config_path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = config_path.with_name(f"{config_path.name}.bak_{stamp}")
    print(f"Codex config: {config_path}")
    if backup:
        print(f"Codex config backup: {backup}")
    if dry_run:
        return backup
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if backup:
        shutil.copy2(config_path, backup)
    _atomic_write(config_path, updated)
    tomllib.loads(config_path.read_text(encoding="utf-8"))
    return backup


def _skill_sources(repo_root: Path) -> list[Path]:
    skills_root = repo_root / "skills"
    return sorted(
        path for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )


def _install_skill(source: Path, destination_root: Path, *, dry_run: bool = False) -> Path:
    destination = destination_root / source.name
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = destination_root / f"{source.name}_bak_{stamp}"
    staging = destination_root / f".{source.name}_staging_{stamp}"
    old = destination_root / f".{source.name}_old_{stamp}"
    print(f"Skill: {source} -> {destination}")
    if destination.is_symlink():
        target = destination.resolve(strict=False)
        if target.exists():
            print(f"Preserving skill symlink: {destination} -> {target}")
            return destination
        raise RuntimeError(f"Refusing to replace broken skill symlink: {destination} -> {target}")
    if dry_run:
        return destination
    destination_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, staging)
    try:
        if destination.exists():
            shutil.copytree(destination, backup)
            destination.rename(old)
        staging.rename(destination)
        if old.exists():
            shutil.rmtree(old)
    except Exception:
        if not destination.exists() and old.exists():
            old.rename(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination


def _write_install_info(
    destination: Path,
    *,
    repo_root: Path,
    clauder_dir: Path,
    mcp_command: Path,
    uv_cache_dir: Path,
    configured_clients: list[str],
    dry_run: bool,
) -> None:
    info: dict[str, Any] = {
        "schema_version": "0.4.0",
        "platform": sys.platform,
        "workbench_version": __version__,
        "git_commit": _git_value(repo_root, "rev-parse", "HEAD"),
        "git_branch_or_tag": _git_value(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "workbench_source_type": "git" if (repo_root / ".git").exists() else "directory",
        "workbench_source_url": _git_value(repo_root, "config", "--get", "remote.origin.url"),
        "installed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "installed_from": str(repo_root),
        "install_destination": str(destination),
        "configured_clients": configured_clients,
        "claudeR_source_type": "git" if (clauder_dir / ".git").exists() else "directory",
        "claudeR_source_url": _git_value(clauder_dir, "config", "--get", "remote.origin.url"),
        "claudeR_ref": _git_value(clauder_dir, "rev-parse", "--abbrev-ref", "HEAD"),
        "claudeR_commit": _git_value(clauder_dir, "rev-parse", "HEAD"),
        "claudeR_git_origin": _git_value(clauder_dir, "config", "--get", "remote.origin.url"),
        "clauder_mcp_source": str(clauder_dir / "clauder-mcp"),
        "clauder_mcp_command": str(mcp_command),
        "clauder_mcp_install_mode": "uv_tool_from_local_fork",
        "clauder_mcp_install_from": str(clauder_dir / "clauder-mcp"),
        "clauder_mcp_exe_sha256": _sha256(mcp_command),
        "r_studio_startup_timeout_sec": 180.0,
        "uv_cache_dir": str(uv_cache_dir),
    }
    print(f"Install info: {destination / 'INSTALL_INFO.json'}")
    if not dry_run:
        _atomic_write(destination / "INSTALL_INFO.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install ClaudeR workbench on macOS/Linux")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--clauder-dir", type=Path, default=Path.home() / "projects" / "ClaudeR")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--agents-home", type=Path, default=Path.home() / ".agents")
    parser.add_argument("--uv-cache-dir", type=Path, default=Path.home() / "Library" / "Caches" / "uv")
    parser.add_argument("--configure-codex", action="store_true")
    parser.add_argument("--sync-agents-skill", action="store_true")
    parser.add_argument("--skip-r-package", action="store_true")
    parser.add_argument("--skip-mcp", action="store_true")
    parser.add_argument("--skip-harness", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = (args.repo_root or Path(__file__).resolve().parents[3]).expanduser().resolve()
    clauder_dir = args.clauder_dir.expanduser().resolve()
    codex_home = args.codex_home.expanduser().resolve()
    agents_home = args.agents_home.expanduser().resolve()
    uv_cache_dir = args.uv_cache_dir.expanduser().resolve()
    mcp_command = Path.home() / ".local" / "bin" / ("clauder-mcp.exe" if os.name == "nt" else "clauder-mcp")

    if not (repo_root / "pyproject.toml").exists():
        raise SystemExit(f"Invalid workbench repository: {repo_root}")
    if not (clauder_dir / "DESCRIPTION").exists() or not (clauder_dir / "clauder-mcp").exists():
        raise SystemExit(f"Invalid ClaudeR repository: {clauder_dir}")

    if not args.skip_r_package:
        r_command = shutil.which("R")
        if not r_command:
            raise SystemExit("R was not found on PATH")
        _run([r_command, "CMD", "INSTALL", str(clauder_dir)], dry_run=args.dry_run)

    uv = shutil.which("uv")
    if not args.skip_mcp or not args.skip_harness:
        if not uv:
            raise SystemExit("uv was not found on PATH")
    if not args.skip_mcp:
        _run([
            uv or "uv", "tool", "install", "--force", "--from",
            str(clauder_dir / "clauder-mcp"), "clauder-mcp",
        ], dry_run=args.dry_run)
    if not args.skip_harness:
        _run([uv or "uv", "tool", "install", "--force", "--editable", str(repo_root)], dry_run=args.dry_run)

    destinations: list[Path] = []
    for source in _skill_sources(repo_root):
        destination = _install_skill(source, codex_home / "skills", dry_run=args.dry_run)
        if source.name == "clauder-rstudio-workbench":
            destinations.append(destination)
        if args.sync_agents_skill:
            destination = _install_skill(source, agents_home / "skills", dry_run=args.dry_run)
            if source.name == "clauder-rstudio-workbench":
                destinations.append(destination)

    if args.configure_codex:
        update_codex_config(
            codex_home / "config.toml",
            mcp_command,
            Path.home(),
            uv_cache_dir,
            dry_run=args.dry_run,
        )

    configured_clients = ["codex"] if args.configure_codex else []
    unique_destinations: dict[Path, Path] = {}
    for destination in destinations:
        unique_destinations.setdefault(destination.resolve(strict=False), destination)
    for destination in unique_destinations.values():
        _write_install_info(
            destination,
            repo_root=repo_root,
            clauder_dir=clauder_dir,
            mcp_command=mcp_command,
            uv_cache_dir=uv_cache_dir,
            configured_clients=configured_clients,
            dry_run=args.dry_run,
        )

    print("Install complete. Restart MCP clients after configuration changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
