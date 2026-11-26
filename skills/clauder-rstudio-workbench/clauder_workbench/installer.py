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
from .config import default_uv_cache_dir
from .platform_runtime import resolve_runtime


def _run(command: list[str], *, dry_run: bool = False) -> None:
    print("+", shlex.join(command))
    if dry_run:
        return
    subprocess.run(command, check=True)


def _git_value(repo: Path, *args: str) -> str:
    # 来源探测不可继承调用方的 Git 仓库或配置覆盖环境。
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _git_dirty(repo: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_metadata(repo: Path) -> dict[str, Any]:
    # 只有真实 Git 工作树顶层才可声明来源，防止目录继承父仓库身份。
    empty: dict[str, Any] = {
        "source_type": "directory", "commit": None, "ref": None,
        "dirty": None, "url": None,
    }
    root = repo.resolve()
    top = _git_value(root, "rev-parse", "--show-toplevel")
    if top == "unknown":
        return empty
    try:
        if Path(top).resolve() != root:
            return empty
    except (OSError, RuntimeError, ValueError):
        return empty
    def value(*args: str) -> str | None:
        found = _git_value(root, *args)
        return None if found in {"", "unknown"} else found
    return {
        "source_type": "git",
        "commit": value("rev-parse", "HEAD"),
        "ref": value("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": _git_dirty(root),
        "url": value("config", "--get", "remote.origin.url"),
    }


def _pyproject_version(path: Path) -> str:
    try:
        try:
            import tomllib
        except ImportError:  # pragma: no cover - Python 3.10 fallback
            import tomli as tomllib  # type: ignore[no-redef]
        return str(tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"])
    except (KeyError, OSError, ValueError):
        return "unknown"


def _description_version(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Version:"):
                return line.partition(":")[2].strip() or "unknown"
    except OSError:
        pass
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
    config_path: Path, mcp_command: Path, home: Path, uv_cache_dir: Path, *,
    dry_run: bool = False,
) -> Path | None:
    from .config_store import update_config
    result = update_config(config_path, client="codex", command=mcp_command,
                           home=home, cache=uv_cache_dir, dry_run=dry_run)
    print(json.dumps(result, ensure_ascii=False))
    return Path(result["backup"]) if result.get("backup") else None


def _install_stable_bridge_launcher(runtime: Any, *, dry_run: bool = False,
                                   bridge_python: Path | None = None) -> Path:
    """Replace uv's symlink entry with a stable, directly executable launcher.

    Desktop app-server reports ENOENT when it follows a stale uv-generated
    shebang/symlink chain.  The launcher keeps the public path stable while
    invoking the embedded uv Python directly.
    """
    target = runtime.bridge_path
    if runtime.system == "windows":
        # uv installs a genuine PE entry point. Never overwrite an .exe with
        # batch text; versioned candidate installs use their own Scripts entry.
        if not dry_run and not target.is_file():
            raise RuntimeError(f"Windows persistent MCP executable is missing: {target}")
        return target
    python = bridge_python or runtime.bridge_python_path
    content = (
        "#!/bin/sh\n"
        "set -eu\n"
        f'exec {shlex.quote(str(python))} -c \'from clauder_mcp import main; raise SystemExit(main())\' "$@"\n'
    )
    if dry_run:
        print(f"Would install stable bridge launcher: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        backup = target.with_name(target.name + ".uv-tool")
        if not backup.exists():
            target.rename(backup)
        else:
            target.unlink()
    elif target.exists():
        existing = target.read_text(encoding="utf-8", errors="ignore")
        if existing != content:
            backup = target.with_name(target.name + ".bak")
            shutil.copy2(target, backup)
    _atomic_write(target, content)
    if runtime.system != "windows":
        target.chmod(0o755)
    return target


def _skill_sources(repo_root: Path) -> list[Path]:
    skills_root = repo_root / "skills"
    return sorted(
        path for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _prune_skill_backups(
    destination_root: Path,
    skill_name: str,
    retention: int,
    *,
    dry_run: bool = False,
) -> list[Path]:
    if retention == 0:
        return []
    backups = sorted(
        (path for path in destination_root.glob(f"{skill_name}_bak_*") if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    stale = backups[retention:]
    for path in stale:
        action = "Would remove" if dry_run else "Removing"
        print(f"{action} old skill backup: {path}")
        if not dry_run:
            shutil.rmtree(path)
    return stale


def _install_skill(
    source: Path,
    destination_root: Path,
    *,
    backup_retention: int = 0,
    dry_run: bool = False,
) -> Path:
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
        _prune_skill_backups(destination_root, source.name, backup_retention, dry_run=True)
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
    _prune_skill_backups(destination_root, source.name, backup_retention)
    return destination


def _write_install_info(
    destination: Path,
    *,
    repo_root: Path,
    clauder_dir: Path,
    mcp_command: Path,
    uv_cache_dir: Path,
    configured_clients: list[str],
    backup_retention: int,
    dry_run: bool,
) -> None:
    workbench = _git_metadata(repo_root)
    clauder = _git_metadata(clauder_dir)
    info: dict[str, Any] = {
        "schema_version": "0.4.0",
        "platform": sys.platform,
        "workbench_version": __version__,
        "git_commit": workbench["commit"],
        "git_branch_or_tag": workbench["ref"],
        "workbench_dirty": workbench["dirty"],
        "workbench_source_type": workbench["source_type"],
        "workbench_source_url": workbench["url"],
        "installed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "installed_from": str(repo_root),
        "install_destination": str(destination),
        "configured_clients": configured_clients,
        "skill_backup_retention": backup_retention,
        "claudeR_source_type": clauder["source_type"],
        "claudeR_source_url": clauder["url"],
        "claudeR_ref": clauder["ref"],
        "claudeR_commit": clauder["commit"],
        "claudeR_dirty": clauder["dirty"],
        "claudeR_version": _description_version(clauder_dir / "DESCRIPTION"),
        "claudeR_git_origin": clauder["url"],
        "clauder_mcp_version": _pyproject_version(clauder_dir / "clauder-mcp" / "pyproject.toml"),
        "clauder_mcp_source": str(clauder_dir / "clauder-mcp"),
        "clauder_mcp_command": str(mcp_command),
        "clauder_mcp_install_mode": "uv_tool_from_local_fork",
        "clauder_mcp_install_from": str(clauder_dir / "clauder-mcp"),
        "clauder_mcp_exe_sha256": _sha256(mcp_command),
        "recommended_r_studio_startup_timeout_sec": 180.0,
        "runtime_verification_scope": "source declarations and executable hash, not running namespaces",
        "loaded_r_namespace": "NOT_CHECKED",
        "loaded_mcp_server": "NOT_CHECKED",
        "harness_install_mode": "packaged",
        "uv_cache_dir": str(uv_cache_dir),
    }
    print(f"Install info: {destination / 'INSTALL_INFO.json'}")
    if not dry_run:
        _atomic_write(destination / "INSTALL_INFO.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install ClaudeR workbench on Windows, macOS, or Linux"
    )
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--clauder-dir", type=Path, default=Path.home() / "projects" / "ClaudeR")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--agents-home", type=Path, default=Path.home() / ".agents")
    parser.add_argument("--uv-cache-dir", type=Path, default=default_uv_cache_dir())
    parser.add_argument("--configure-codex", action="store_true")
    parser.add_argument("--configure-claude", action="store_true", help="merge user .claude.json without launching Claude")
    parser.add_argument("--configure-copilot", action="store_true")
    parser.add_argument("--sync-agents-skill", action="store_true")
    parser.add_argument("--sync-clauder-alias", action="store_true", help="install the thin legacy $clauder alias with backup")
    parser.add_argument("--skip-r-package", action="store_true")
    parser.add_argument("--skip-mcp", action="store_true")
    parser.add_argument("--skip-harness", action="store_true")
    parser.add_argument(
        "--backup-retention",
        type=_non_negative_int,
        default=0,
        help="number of per-skill backups to keep; 0 keeps all backups (default: 0)",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime = resolve_runtime()
    repo_root = (args.repo_root or Path(__file__).resolve().parents[3]).expanduser().resolve()
    clauder_dir = args.clauder_dir.expanduser().resolve()
    codex_home = args.codex_home.expanduser().resolve()
    agents_home = args.agents_home.expanduser().resolve()
    uv_cache_dir = args.uv_cache_dir.expanduser().resolve()
    # Keep the persistent bridge location in the shared platform contract.
    mcp_command = runtime.bridge_path

    if not (repo_root / "pyproject.toml").exists():
        raise SystemExit(f"Invalid workbench repository: {repo_root}")
    if not (clauder_dir / "DESCRIPTION").exists() or not (clauder_dir / "clauder-mcp").exists():
        raise SystemExit(f"Invalid ClaudeR repository: {clauder_dir}")
    manifest = repo_root / "runtime-compatibility.json"
    if (not args.skip_r_package or not args.skip_mcp) and not manifest.is_file():
        raise SystemExit("Runtime compatibility manifest is required before updating R or MCP; nothing was installed")
    if manifest.exists() and (not args.skip_r_package or not args.skip_mcp):
        from .compatibility import verify_source
        pair = verify_source(manifest, clauder_dir)
        print(json.dumps({"runtime_compatibility": pair}))
        if not pair["ok"]:
            raise SystemExit("ClaudeR source does not match the published pair; runtime was not changed")

    if not args.skip_r_package:
        r_command = shutil.which("R")
        if not r_command:
            raise SystemExit("R was not found on PATH")
        _run([r_command, "CMD", "INSTALL", str(clauder_dir)], dry_run=args.dry_run)
        if not args.dry_run:
            from .runtime_install import verify_r
            rscript = shutil.which("Rscript")
            if not rscript:
                raise SystemExit("R was installed but Rscript is unavailable for installed-runtime verification")
            installed_r = verify_r(json.loads(manifest.read_text(encoding="utf-8")), Path(rscript))
            print(json.dumps({"installed_R_verification": installed_r}))
            if not installed_r["ok"]:
                raise SystemExit("Installed R package did not match the source pair; configuration was not changed")

    uv = shutil.which("uv")
    if not args.skip_mcp or not args.skip_harness:
        if not uv:
            raise SystemExit("uv was not found on PATH")
    if not args.skip_mcp:
        _run([
            uv or "uv", "tool", "install", "--force", "--from",
            str(clauder_dir / "clauder-mcp"), "clauder-mcp",
        ], dry_run=args.dry_run)
        if not args.dry_run:
            from .runtime_install import verify_bridge
            tools_root = Path(subprocess.check_output([uv or "uv", "tool", "dir"], text=True).strip())
            bridge_python = tools_root / "clauder-mcp" / ("Scripts/python.exe" if runtime.system == "windows" else "bin/python")
            installed_bridge = verify_bridge(json.loads(manifest.read_text(encoding="utf-8")), bridge_python)
            print(json.dumps({"installed_bridge_verification": installed_bridge}))
            if not installed_bridge["ok"]:
                raise SystemExit("Installed MCP did not match the source pair; configuration was not changed")
            if runtime.system == "windows":
                tool_bin = Path(subprocess.check_output([uv or "uv", "tool", "dir", "--bin"], text=True).strip())
                mcp_command = tool_bin / "clauder-mcp.exe"
                if not mcp_command.is_file():
                    raise SystemExit(f"Installed Windows MCP entry point is missing: {mcp_command}")
    # Keep the Codex/Claude/Copilot command path stable across uv upgrades.
    if not args.skip_mcp and runtime.system != "windows":
        _install_stable_bridge_launcher(runtime, dry_run=args.dry_run,
                                       bridge_python=None if args.dry_run else bridge_python)
    if not args.skip_harness:
        _run([uv or "uv", "tool", "install", "--force", str(repo_root)], dry_run=args.dry_run)

    destinations: list[Path] = []
    for source in _skill_sources(repo_root):
        destination = _install_skill(
            source,
            codex_home / "skills",
            backup_retention=args.backup_retention,
            dry_run=args.dry_run,
        )
        if source.name == "clauder-rstudio-workbench":
            destinations.append(destination)
        if args.sync_agents_skill:
            destination = _install_skill(
                source,
                agents_home / "skills",
                backup_retention=args.backup_retention,
                dry_run=args.dry_run,
            )
            if source.name == "clauder-rstudio-workbench":
                destinations.append(destination)

    if args.configure_codex:
        update_codex_config(
            codex_home / "config.toml",
            mcp_command,
            runtime.home,
            uv_cache_dir,
            dry_run=args.dry_run,
        )

    if args.sync_clauder_alias:
        _install_skill(repo_root / "adapters" / "clauder", codex_home / "skills",
                       backup_retention=args.backup_retention, dry_run=args.dry_run)

    configured_clients = ["codex"] if args.configure_codex else []
    from .config_store import update_config
    for client, selected, path in (
        ("claude", args.configure_claude, runtime.home / ".claude.json"),
        ("copilot", args.configure_copilot, runtime.home / ".copilot" / "mcp-config.json"),
    ):
        if selected:
            update_config(path, client=client, command=mcp_command, home=runtime.home,
                          cache=uv_cache_dir, dry_run=args.dry_run)
            configured_clients.append(client)
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
            backup_retention=args.backup_retention,
            dry_run=args.dry_run,
        )

    print("Install complete. Verify the selected client's actual tools with native-smoke; configuration alone is not readiness. Do not restart RStudio. Use a supported targeted client reload only if its loaded configuration is stale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
