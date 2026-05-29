from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ARCHIVE_DIR, INFLIGHT_DIR, ensure_state_dirs


def inflight_path(task_key: str) -> Path:
    return INFLIGHT_DIR / f"{task_key}.json"


def load_inflight(task_key: str) -> dict[str, Any] | None:
    path = inflight_path(task_key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_inflight(task_key: str, doc: dict[str, Any]) -> Path:
    ensure_state_dirs()
    INFLIGHT_DIR.mkdir(parents=True, exist_ok=True)
    target = inflight_path(task_key)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=str(INFLIGHT_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return target


def archive_inflight(task_key: str, reason: str) -> Path | None:
    ensure_state_dirs()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    source = inflight_path(task_key)
    if not source.exists():
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = ARCHIVE_DIR / f"{ts}_{task_key}.json"
    doc = json.loads(source.read_text(encoding="utf-8-sig"))
    doc["archive_reason"] = reason
    doc["archived_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    target.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source.unlink()
    return target


def list_inflight() -> list[dict[str, Any]]:
    ensure_state_dirs()
    rows = []
    for path in INFLIGHT_DIR.glob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            doc = {"path": str(path), "error": str(exc)}
        rows.append(doc)
    return rows
