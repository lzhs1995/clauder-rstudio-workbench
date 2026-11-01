#!/usr/bin/env python3
"""构建或只读核验结果包清单；清单不列自身，外部回执固定其 SHA256。"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat


def relative_name(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Invalid portable relative path")
    path = PurePosixPath(value)
    if (path.is_absolute() or PureWindowsPath(value).drive or
            any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ValueError(f"Unsafe relative path: {value}")
    return value


def file_digest(path):
    if path.is_symlink():
        raise ValueError(f"Symlink is not an archived regular file: {path.name}")
    path_before = path.stat(follow_symlinks=False)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Manifest payload must be a regular file")
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    current = path.stat(follow_symlinks=False)
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    signature = lambda st: tuple(getattr(st, field) for field in fields)
    # Windows Python 的路径 stat 与句柄 fstat 可返回不同 ctime 语义。
    # 两者各自前后均须稳定；跨接口仍严格核文件身份、大小与修改时间。
    identity = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    if (signature(before) != signature(after) or
            signature(path_before) != signature(current) or
            identity(path_before) != identity(before) or
            identity(after) != identity(current)):
        raise ValueError(f"File changed during hashing: {path.name}")
    return {"bytes": after.st_size, "sha256": digest.hexdigest()}


def inventory(root, manifest_name):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Use an existing non-symlink package directory")
    relative_name(manifest_name)
    rows = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError(f"Symlink directory in package: {name}")
        for name in files:
            path = Path(directory) / name
            relative = relative_name(path.relative_to(root).as_posix())
            if relative != manifest_name:
                rows.append({"path": relative, **file_digest(path)})
    return sorted(rows, key=lambda row: row["path"])


def build(root, manifest_name="MANIFEST.json"):
    root = Path(root)
    rows = inventory(root, manifest_name)
    document = {"schema": "mplus-artifact-manifest-v1",
                "manifest_excluded_from_payload": manifest_name, "files": rows}
    target = root / manifest_name
    # 不覆盖历史清单；修复时先建一个新的候选包目录。
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"status": "PASS", "files": len(rows), "manifest": str(target),
            "manifest_sha256": file_digest(target)["sha256"]}


def verify(root, manifest_name="MANIFEST.json", expected_sha256=None):
    root = Path(root)
    relative_name(manifest_name)
    target = root / manifest_name
    manifest_digest = file_digest(target)["sha256"]
    if expected_sha256 is not None and manifest_digest != expected_sha256.lower():
        raise ValueError("Manifest differs from its external SHA256 pin")
    document = json.loads(target.read_text(encoding="utf-8"))
    rows = document.get("files") if isinstance(document, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Expected a files array")
    expected = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Expected file records")
        name = relative_name(row.get("path"))
        if name == manifest_name:
            raise ValueError("Manifest cannot hash itself; pin it in an external receipt")
        if name in expected:
            raise ValueError(f"Duplicate manifest entry: {name}")
        digest = row.get("sha256")
        if (type(row.get("bytes")) is not int or row["bytes"] < 0 or
                not isinstance(digest, str) or len(digest) != 64 or
                any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError(f"Invalid hash or length: {name}")
        expected[name] = {"bytes": row["bytes"], "sha256": digest}
    actual = {row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
              for row in inventory(root, manifest_name)}
    if set(expected) != set(actual):
        raise ValueError(f"File set changed: missing={sorted(set(expected)-set(actual))[:8]}, "
                         f"unlisted={sorted(set(actual)-set(expected))[:8]}")
    mismatches = [name for name in expected if expected[name] != actual[name]]
    if mismatches:
        raise ValueError(f"Payload hash/length mismatch: {mismatches[:8]}")
    if file_digest(target)["sha256"] != manifest_digest:
        raise ValueError("Manifest changed during verification")
    return {"status": "PASS", "files": len(actual),
            "manifest_sha256": manifest_digest,
            "scope": "Byte integrity; numerical and scientific validation are separate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["build", "verify"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--manifest", default="MANIFEST.json")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    try:
        if args.operation == "build":
            if args.expected_sha256:
                raise ValueError("--expected-sha256 applies only to verify")
            result = build(args.root, args.manifest)
        else:
            result = verify(args.root, args.manifest, args.expected_sha256)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
