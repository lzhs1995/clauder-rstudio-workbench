from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any


def csv_data_rows(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        if len(rows) < 2:
            return 0
        return sum(1 for row in rows[1:] if any(cell.strip() for cell in row))
    except Exception:
        return None


def parse_requirement(value: str) -> dict[str, Any]:
    if "::" in value:
        kind, rest = value.split("::", 1)
    else:
        kind, rest = "file", value
    parts = rest.split(",")
    req: dict[str, Any] = {"path": parts[0], "kind": kind.lower(), "options": {}}
    for part in parts[1:]:
        if not part.strip():
            continue
        if "=" not in part:
            req["options"][part.strip()] = True
            continue
        key, raw = part.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if key in {"min_rows", "min_bytes"}:
            req["options"][key] = int(raw)
        elif key in {"max_age_h"}:
            req["options"][key] = float(raw)
        else:
            req["options"][key] = raw
    return req


def _under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def artifact_ok(path: str, artifact_type: str = "file", options: dict[str, Any] | None = None) -> tuple[bool, str]:
    options = options or {}
    p = Path(path)
    if not p.exists():
        return False, f"missing: {path}"
    size = p.stat().st_size
    kind = artifact_type.lower()

    output_root = options.get("output_root")
    if output_root and not _under_root(p, Path(str(output_root))):
        return False, f"{path} is outside required output_root: {output_root}"

    max_age_h = options.get("max_age_h")
    if max_age_h is not None:
        age_h = (time.time() - p.stat().st_mtime) / 3600
        if age_h > float(max_age_h):
            return False, f"{path} is stale: age {age_h:.2f}h > max_age_h {float(max_age_h):.2f}"

    if kind in {"gt_errors_empty", "empty_ok"}:
        return True, "empty or tiny file is acceptable for this artifact type"
    if kind in {"manifest", "validation", "csv_rows"}:
        rows = csv_data_rows(p)
        if rows is None:
            return False, f"{kind} could not be parsed as CSV: {path}"
        min_rows = int(options.get("min_rows", 1))
        if rows < min_rows:
            return False, f"{kind} has {rows} data rows, expected at least {min_rows}: {path}"
        return True, f"csv has {rows} data rows"
    if kind in {"rdata", "rds"}:
        min_bytes = int(options.get("min_bytes", 1024))
        if size < min_bytes:
            return False, f"{kind} is too small to be credible: {path} ({size} < {min_bytes} bytes)"
        return True, "binary artifact exists and passes size threshold"
    min_bytes = int(options.get("min_bytes", 1))
    if size < min_bytes:
        return False, f"file is smaller than required for artifact type {kind}: {path} ({size} < {min_bytes} bytes)"
    return True, "file exists"


def check_artifacts(requirements: list[dict[str, Any] | tuple[str, str]]) -> dict[str, Any]:
    checks = []
    ok_all = True
    for req in requirements:
        if isinstance(req, tuple):
            path, kind = req
            options: dict[str, Any] = {}
        else:
            path = req["path"]
            kind = req["kind"]
            options = req.get("options", {})
        ok, reason = artifact_ok(path, kind, options)
        ok_all = ok_all and ok
        checks.append({"path": path, "artifact_type": kind, "options": options, "ok": ok, "reason": reason})
    return {"ok": ok_all, "checks": checks}
