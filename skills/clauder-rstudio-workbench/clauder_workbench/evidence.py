from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import EVIDENCE_DIR, default_agent, ensure_state_dirs, normalize_path


SCHEMA_VERSION = "0.2.2"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_task_key(
    project_root: str = "",
    task_label: str = "",
    session_name: str = "",
    transport_scope: str = "",
) -> str:
    raw = "|".join(
        [
            normalize_path(project_root),
            task_label.strip().lower(),
            session_name.strip().lower(),
            transport_scope.strip().lower(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def build_evidence(
    harness_name: str,
    decision: str,
    *,
    reasons: list[str] | None = None,
    parent_evidence_ids: list[str] | None = None,
    task_key: str | None = None,
    transport_class: str | None = None,
    session_name: str | None = None,
    pid: int | str | None = None,
    job_id: str | None = None,
    io_mode: str | None = None,
    artifact_paths: list[str] | None = None,
    policy_violations: list[str] | None = None,
    exit_code: int = 0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": str(uuid.uuid4()),
        "parent_evidence_ids": parent_evidence_ids or [],
        "task_key": task_key,
        "harness_name": harness_name,
        "timestamp_utc": utc_now(),
        "agent": default_agent(),
        "transport_class": transport_class,
        "session_name": session_name,
        "pid": pid,
        "job_id": job_id,
        "io_mode": io_mode,
        "decision": decision,
        "reasons": reasons or [],
        "artifact_paths": artifact_paths or [],
        "policy_violations": policy_violations or [],
        "exit_code": exit_code,
    }
    if extra:
        doc["extra"] = extra
    return doc


def write_evidence(doc: dict[str, Any], evidence_dir: Path | None = None) -> Path:
    ensure_state_dirs()
    target_dir = evidence_dir or EVIDENCE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_harness = str(doc.get("harness_name") or "harness").replace(" ", "_")
    evidence_id = str(doc.get("evidence_id") or uuid.uuid4())
    target = target_dir / f"{ts}_{safe_harness}_{evidence_id}.json"
    fd, tmp_name = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=str(target_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return target


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def print_json(doc: dict[str, Any]) -> None:
    print(json.dumps(doc, ensure_ascii=False, indent=2))
