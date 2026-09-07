"""Scoped, conflict-detecting MCP configuration updates shared by installers."""
from __future__ import annotations

import argparse
from collections.abc import MutableMapping
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid


def digest(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def snapshot(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


@contextmanager
def config_lock(path: Path):
    # 不自动回收旧锁，避免误认另一个仍在执行的写入者已经死亡。
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".clauder.lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump({"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        lock.unlink()


def atomic_bytes(path: Path, data: bytes):
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _mapping(parent, key):
    value = parent.setdefault(key, {})
    if not isinstance(value, MutableMapping):
        raise ValueError(f"{key} must be a table/object; refusing destructive conversion")
    return value


def render_config(raw: bytes | None, *, client: str, command: str, home: str,
                  cache: str, windows: bool = False) -> bytes:
    source = (raw or b"").decode("utf-8-sig")
    if client == "codex":
        import tomlkit
        doc = tomlkit.parse(source)
        servers = _mapping(doc, "mcp_servers")
    else:
        doc = json.loads(source or "{}")
        if not isinstance(doc, dict):
            raise ValueError("configuration must be an object")
        servers = _mapping(doc, "mcpServers")
    server = _mapping(servers, "r-studio")
    # URL 型条目不是本地 bridge，不能半转换为同时有 URL 和 command 的坏配置。
    if server.get("url"):
        raise ValueError("r-studio is a URL transport; explicit migration is required")
    old_command = str(server.get("command") or "")
    args = server.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("args must be a string array; refusing lossy conversion")
    args = list(args)
    old_name = old_command.replace("\\", "/").rsplit("/", 1)[-1]
    if old_name in {"uvx", "uvx.exe"}:
        if len(args) >= 3 and args[:1] == ["--from"] and args[2] == "clauder-mcp":
            args = args[3:]
        elif args[:1] == ["clauder-mcp"]:
            args = args[1:]
        else:
            raise ValueError("unrecognized uvx launcher args; refusing to guess")
    elif args and old_name not in {"clauder-mcp", "clauder-mcp.exe", ""}:
        raise ValueError("custom launcher with args requires explicit migration")
    server["command"] = command
    if "args" in server or args:
        server["args"] = args
    if client == "codex":
        server.setdefault("startup_timeout_sec", 180.0)
    else:
        server["type"] = "local" if client == "copilot" else "stdio"
        if client == "copilot":
            server.setdefault("tools", ["*"])
    env = _mapping(server, "env")
    env["HOME"] = home
    if windows:
        env["USERPROFILE"] = home
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # 补上 loopback，但保留原有 NO_PROXY 网络策略。
    no_proxy = [s.strip() for s in str(env.get("NO_PROXY") or "").split(",") if s.strip()]
    env["NO_PROXY"] = ",".join(dict.fromkeys([*no_proxy, "127.0.0.1", "localhost"]))
    env["UV_CACHE_DIR"] = cache
    if client == "codex":
        updated = tomlkit.dumps(doc)
        tomlkit.parse(updated)
    else:
        updated = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        json.loads(updated)
    return updated.encode("utf-8")


def update_config(path: Path, *, client: str, command: Path, home: Path,
                  cache: Path, windows: bool | None = None, dry_run: bool = False) -> dict:
    path = path.expanduser().resolve()
    kwargs = dict(client=client, command=str(command), home=str(home), cache=str(cache),
                  windows=os.name == "nt" if windows is None else windows)
    if dry_run:
        original = snapshot(path)
        candidate = render_config(original, **kwargs)
        return {"changed": original != candidate, "dry_run": True, "path": str(path)}
    with config_lock(path):
        original = snapshot(path)
        candidate = render_config(original, **kwargs)
        if candidate == original:
            return {"changed": False, "path": str(path), "sha256": digest(candidate)}
        backup = None
        if original is not None:
            backup = path.with_name(path.name + ".bak_clauder_" + uuid.uuid4().hex)
            atomic_bytes(backup, original)
        if snapshot(path) != original:
            raise RuntimeError("CONFIG_CONFLICT: another writer changed the file; not overwritten")
        atomic_bytes(path, candidate)
        if snapshot(path) != candidate:
            # 不回滚覆盖并行外部写入者的新内容。
            raise RuntimeError("CONFIG_CONFLICT_AFTER_WRITE: inspect backup; no automatic overwrite")
        audit = {"at": datetime.now(timezone.utc).isoformat(), "writer": "clauder-workbench",
                 "pid": os.getpid(), "python": sys.executable, "client": client,
                 "before_sha256": digest(original), "after_sha256": digest(candidate),
                 "backup": str(backup) if backup else None}
        audit_path = path.with_name(path.name + ".clauder-writes.jsonl")
        fd = os.open(audit_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return {"changed": True, "path": str(path), "backup": audit["backup"],
                "sha256": audit["after_sha256"], "audit_path": str(audit_path)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client", choices=["codex", "claude", "copilot"], required=True)
    p.add_argument("--path", type=Path, required=True)
    p.add_argument("--command", type=Path, required=True)
    p.add_argument("--home", type=Path, required=True)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        print(json.dumps(update_config(args.path, client=args.client, command=args.command,
                                       home=args.home, cache=args.cache, dry_run=args.dry_run), indent=2))
        return 0
    except Exception as exc:
        # 解析错误可能包含 secret 原文，不回显异常正文。
        print(json.dumps({"status": "BLOCK", "error_type": type(exc).__name__,
                          "reason": "configuration unchanged or conflict detected; inspect private backup and config"}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
