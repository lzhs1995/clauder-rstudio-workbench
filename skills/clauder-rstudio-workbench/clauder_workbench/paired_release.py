"""Stage isolated runtime pairs and select/roll back their recorded pair.

Selection only writes active.json. It does not edit client configuration, reload
an agent, change an existing RStudio library, or replace any shared uv tool.
Mutating commands default to a plan; --apply is explicit. Failed stages remain
on disk for inspection and cannot be selected.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

from .compatibility import verify_source
from .runtime_install import verify_bridge, verify_r


SCOPE = "selected pair only; client configuration and existing processes unchanged"
EXCLUDED_SOURCE_DIRS = {".git", "__pycache__", ".venv", "build", "dist", ".pytest_cache"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _bytes(doc):
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_bytes(path, data):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix="." + path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _write_new(path, doc):
    with Path(path).open("xb") as handle:
        handle.write(_bytes(doc))
        handle.flush()
        os.fsync(handle.fileno())


def _pin(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": _hash(data)}


def _source_snapshot(root):
    root = Path(root).resolve()
    files = {}
    for directory, subdirs, names in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if d not in EXCLUDED_SOURCE_DIRS
                            and not d.endswith(".egg-info"))
        for name in sorted(names):
            path = Path(directory) / name
            if name in {".git", ".DS_Store"} or name.endswith((".pyc", ".pyo")):
                continue
            if path.is_symlink():
                raise ValueError(f"Source symlink is not a fixed candidate file: {path}")
            files[path.relative_to(root).as_posix()] = _hash(path.read_bytes())
        if any((Path(directory) / d).is_symlink() for d in subdirs):
            raise ValueError("Source directory symlinks are not supported")
    return {"root": str(root), "files": files,
            "sha256": _hash(json.dumps(files, sort_keys=True).encode("utf-8"))}


def _version(path):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    return str(tomllib.loads(Path(path).read_text(encoding="utf-8"))["project"]["version"])


def _validate_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", value) or value in {".", ".."}:
        raise ValueError("release/event id must be a single safe path component")
    return value


@contextmanager
def _lock(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".pair.lock"
    with path.open("xb") as handle:
        handle.write(_bytes({"pid": os.getpid(), "at": _now()}))
    try:
        yield
    finally:
        path.unlink()


def _run(command):
    subprocess.run(command, check=True, timeout=1800)


def _relative_child(release, relative):
    path = release / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Release record path escapes its directory")
    # The venv executable may legitimately symlink to the base Python.
    if not path.absolute().is_relative_to(release.absolute()):
        raise ValueError("Release path escapes its directory")
    return path


def _probe_pair(release, paths, manifest, rscript):
    python = _relative_child(release, paths["python"])
    library = _relative_child(release, paths["r_library"])
    bridge = verify_bridge(manifest, python, require_workbench=True)
    r = verify_r(manifest, Path(rscript), library)
    bridge_actual = bridge.get("actual", {})
    bridge["checks"]["candidate_python"] = (
        Path(bridge_actual.get("python", "")).absolute() == python.absolute())
    bridge["checks"]["candidate_bridge_location"] = (
        Path(bridge_actual.get("bridge_source", "")).resolve().is_relative_to((release / "venv").resolve()))
    bridge["checks"]["candidate_workbench_location"] = (
        Path(bridge_actual.get("workbench_source") or "").resolve().is_relative_to((release / "venv").resolve()))
    bridge["ok"] = bool(bridge.get("ok")) and all(bridge["checks"].values())
    checks = {"bridge": bridge["ok"], "R": r["ok"]}
    for name in ("bridge_launcher", "workbench_launcher"):
        checks[name] = _relative_child(release, paths[name]).is_file()
    return {"ok": all(checks.values()), "checks": checks, "bridge": bridge, "R": r,
            "scope": "new bounded probe processes; no existing agent or RStudio reload"}


def _installed_snapshots(probes):
    roots = {"bridge": Path(probes["bridge"]["actual"]["bridge_source"]).parent,
             "workbench": Path(probes["bridge"]["actual"]["workbench_source"]).parent,
             "R": Path(probes["R"]["actual"]["path"])}
    if not all(p.is_dir() for p in roots.values()):
        raise ValueError("Actual installed package directory is missing")
    return {name: _source_snapshot(path) for name, path in roots.items()}


def stage(*, release_root, release_id, workbench_source, clauder_source, manifest_path,
          python=sys.executable, r="R", rscript="Rscript", apply=False, runner=None):
    root = Path(release_root).expanduser().resolve()
    release = root / _validate_id(release_id)
    wb, cr = Path(workbench_source).resolve(), Path(clauder_source).resolve()
    if release.is_relative_to(wb) or release.is_relative_to(cr):
        raise ValueError("Release root must be outside both source trees")
    manifest_path = Path(manifest_path).resolve()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    source_check = verify_source(manifest_path, cr)
    if not source_check["ok"]:
        raise ValueError("ClaudeR source does not match the candidate pair")
    if _version(wb / "pyproject.toml") != manifest["workbench_version"]:
        raise ValueError("Workbench source version does not match the candidate pair")
    sources = {"workbench": _source_snapshot(wb), "ClaudeR": _source_snapshot(cr)}
    if release.exists():
        raise FileExistsError(f"Release already exists; preserve original attempt: {release}")
    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    paths = {"python": f"venv/{scripts}/python{suffix}", "r_library": "r-library",
             "bridge_launcher": f"venv/{scripts}/clauder-mcp{suffix}",
             "workbench_launcher": f"venv/{scripts}/clauder-workbench{suffix}"}
    commands = [[str(python), "-m", "venv", str(release / "venv")],
                [str(release / paths["python"]), "-m", "pip", "--isolated", "--require-virtualenv",
                 "install", "--no-user", "--disable-pip-version-check",
                 str(cr / "clauder-mcp"), str(wb)],
                [str(r), "CMD", "INSTALL", "--library=" + str(release / paths["r_library"]), str(cr)]]
    plan = {"status": "PLAN", "release_dir": str(release), "commands": commands,
            "source_check": source_check, "sources": sources, "manifest": _pin(manifest_path),
            "paths": paths, "scope": SCOPE}
    if not apply:
        return plan
    with _lock(root):
        release.mkdir()
        (release / paths["r_library"]).mkdir()
        _write_new(release / "STAGE_INTENT.json", plan)
        (release / "manifest.json").write_bytes(manifest_bytes)
        execute = runner or _run
        try:
            for command in commands:
                execute(command)
            if manifest_path.read_bytes() != manifest_bytes:
                raise RuntimeError("Candidate manifest changed during stage")
            for name, source in (("workbench", wb), ("ClaudeR", cr)):
                if _source_snapshot(source) != sources[name]:
                    raise RuntimeError(f"Candidate {name} source changed during stage")
            probes = _probe_pair(release, paths, manifest, rscript)
            if not probes["ok"]:
                raise RuntimeError("Installed candidate failed actual runtime verification: " + json.dumps(probes))
            record = {"schema": "clauder-paired-release/v1", "status": "STAGED_VERIFIED",
                      "release_id": release_id, "created_at": _now(), "paths": paths,
                      "manifest_sha256": _hash(manifest_bytes), "sources": sources,
                      "rscript": str(rscript), "verification": probes, "scope": SCOPE,
                      "installed_packages": _installed_snapshots(probes),
                      "launcher_sha256": {key: _hash((release / paths[key]).read_bytes())
                                          for key in ("bridge_launcher", "workbench_launcher")}}
            _write_new(release / "release.json", record)
            return {"status": "STAGED_VERIFIED", "release": _pin(release / "release.json"),
                    "verification": probes, "scope": SCOPE}
        except Exception as error:
            _write_new(release / "FAILED.json", {"status": "FAILED", "at": _now(),
                       "type": type(error).__name__, "error": str(error), "scope": SCOPE})
            raise


def verify(release_dir, *, rscript=None):
    release = Path(release_dir).expanduser().resolve()
    record = _read_json(release / "release.json")
    if record.get("schema") != "clauder-paired-release/v1" or record.get("status") != "STAGED_VERIFIED":
        raise ValueError("Not a verified paired release")
    if (release / "FAILED.json").exists() or record["release_id"] != release.name:
        raise ValueError("Failed or relocated release cannot be selected")
    manifest_bytes = (release / "manifest.json").read_bytes()
    if _hash(manifest_bytes) != record["manifest_sha256"]:
        raise ValueError("Release manifest changed")
    for key, expected in record["launcher_sha256"].items():
        if _hash(_relative_child(release, record["paths"][key]).read_bytes()) != expected:
            raise ValueError("Release launcher changed")
    probes = _probe_pair(release, record["paths"], json.loads(manifest_bytes), rscript or record["rscript"])
    if not probes["ok"]:
        raise ValueError("Paired release runtime verification failed: " + json.dumps(probes))
    if _installed_snapshots(probes) != record["installed_packages"]:
        raise ValueError("Installed paired package bytes changed")
    return {"status": "VERIFIED", "ok": True, "release": _pin(release / "release.json"),
            "verification": probes,
            "client_command": str(release / record["paths"]["bridge_launcher"]),
            "workbench_command": str(release / record["paths"]["workbench_launcher"]),
            "r_library": str(release / record["paths"]["r_library"]), "scope": SCOPE}


def _active_bytes(root):
    path = root / "active.json"
    if path.is_symlink():
        raise ValueError("Refusing a symlink active record")
    return path.read_bytes() if path.exists() else None


def _cas(current, expected):
    actual = _hash(current) if current is not None else "ABSENT"
    if actual != expected:
        raise RuntimeError(f"ACTIVE_CONFLICT: expected {expected}, found {actual}; no overwrite")


def _transition(root, before, after, event, *, apply):
    result = {"status": "PLAN", "event": event, "before_sha256": _hash(before) if before else "ABSENT",
              "after_sha256": _hash(after) if after else "ABSENT", "scope": SCOPE}
    if not apply:
        return result
    events = root / "events"
    events.mkdir(exist_ok=True)
    event_id = uuid.uuid4().hex
    intent = {**result, "at": _now(), "before_text": before.decode("utf-8") if before is not None else None,
              "after_text": after.decode("utf-8") if after is not None else None}
    _write_new(events / (event_id + ".intent.json"), intent)
    _cas(_active_bytes(root), result["before_sha256"])
    if after is None:
        (root / "active.json").unlink()
    else:
        _atomic_bytes(root / "active.json", after)
    if _active_bytes(root) != after:
        raise RuntimeError("ACTIVE_CONFLICT_AFTER_WRITE: inspect original intent; no automatic overwrite")
    result.update(status="SELECTED_PAIR_ONLY", event_id=event_id, intent=_pin(events / (event_id + ".intent.json")))
    _write_new(events / (event_id + ".result.json"), result)
    return result


def activate(release_dir, *, expected_active_sha, apply=False, rscript=None):
    release = Path(release_dir).expanduser().resolve()
    root = release.parent
    before = _active_bytes(root)
    _cas(before, expected_active_sha)
    verified = verify(release, rscript=rscript)
    after = _bytes({"schema": "clauder-selected-pair/v1", "release_id": release.name,
                    "release_sha256": verified["release"]["sha256"], "scope": SCOPE})
    if apply:
        with _lock(root):
            _cas(_active_bytes(root), expected_active_sha)
            return _transition(root, before, after, "activate", apply=True)
    return _transition(root, before, after, "activate", apply=False)


def rollback(release_root, *, activation_id, expected_active_sha, apply=False, rscript=None):
    root = Path(release_root).expanduser().resolve()
    event_id = _validate_id(activation_id)
    intent_path = root / "events" / (event_id + ".intent.json")
    result = _read_json(root / "events" / (event_id + ".result.json"))
    if result.get("status") != "SELECTED_PAIR_ONLY" or result.get("event") != "activate":
        raise ValueError("Rollback requires a completed activation event")
    if result["intent"] != _pin(intent_path):
        raise ValueError("Activation intent changed")
    intent = _read_json(intent_path)
    before = _active_bytes(root)
    _cas(before, expected_active_sha)
    if expected_active_sha != result["after_sha256"] or before != intent["after_text"].encode("utf-8"):
        raise RuntimeError("ACTIVE_CONFLICT: this activation is not current")
    prior = intent["before_text"]
    after = prior.encode("utf-8") if prior is not None else None
    if after is not None:
        old = json.loads(after)
        if old.get("schema") != "clauder-selected-pair/v1":
            raise ValueError("Prior record is not a complete selected pair")
        verified = verify(root / _validate_id(old["release_id"]), rscript=rscript)
        if verified["release"]["sha256"] != old["release_sha256"]:
            raise ValueError("Prior release changed; refusing rollback")
    if apply:
        with _lock(root):
            _cas(_active_bytes(root), expected_active_sha)
            return _transition(root, before, after, "rollback:" + event_id, apply=True)
    return _transition(root, before, after, "rollback:" + event_id, apply=False)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("stage", help="plan or install into a new isolated release directory")
    for name in ("release-root", "workbench-source", "clauder-source", "manifest"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--release-id", required=True)
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--r", default="R")
    p.add_argument("--rscript", default="Rscript")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("verify", help="probe a staged pair without changing selection or client config")
    p.add_argument("--release-dir", type=Path, required=True)
    p.add_argument("--rscript")
    p = sub.add_parser("activate", help="select a verified pair record, not live clients")
    p.add_argument("--release-dir", type=Path, required=True)
    p.add_argument("--expected-active-sha", required=True, help="current active.json SHA256, or ABSENT")
    p.add_argument("--rscript")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("rollback", help="CAS restore the complete prior pair after verifying it")
    p.add_argument("--release-root", type=Path, required=True)
    p.add_argument("--activation-id", required=True)
    p.add_argument("--expected-active-sha", required=True)
    p.add_argument("--rscript")
    p.add_argument("--apply", action="store_true")
    return parser


def main(argv=None):
    args = vars(build_parser().parse_args(argv))
    command = args.pop("command")
    if command == "stage":
        args["manifest_path"] = args.pop("manifest")
    try:
        result = globals()[command](**args)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "FAILED", "error": str(error), "type": type(error).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
