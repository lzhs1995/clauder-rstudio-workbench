"""Verify the published source pair before replacing a runtime installation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def verify_source(manifest_path: Path, source: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = {}
    for name, expected in manifest["critical_file_sha256"].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()):
            raise ValueError("compatibility manifest path escapes source")
        checks[name] = path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected
    commit = None
    clean = None
    if (source / ".git").exists():
        commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        clean = not subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip()
        checks["exact_git_commit"] = commit == manifest["clauder_commit"]
        checks["clean_source"] = clean
    return {"ok": bool(checks) and all(checks.values()), "checks": checks,
            "commit": commit, "clean": clean, "ref": manifest["clauder_ref"],
            "scope": "git_commit_and_critical_files" if commit else "archive_critical_files_only"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    args = p.parse_args(argv)
    result = verify_source(args.manifest, args.source)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
