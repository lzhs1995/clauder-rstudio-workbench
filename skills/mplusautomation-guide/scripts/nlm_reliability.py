#!/usr/bin/env python3
"""Windows NotebookLM query runner with source and retry evidence.

This module never calls nlm login. Authentication is proved by the notebook
list command; query/source failures are classified separately and followed by
a fresh list check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

NETWORK_MARKERS = (
    "timeout", "timed out", "connection", "proxy", "dns", "network",
    "ssl", "unexpected_eof", "eof occurred", "reset by peer",
    "temporarily unavailable",
)
AUTH_MARKERS = ("unauthorized", "authentication", "401", "cookie expired")
NEW_ISSUES_RE = re.compile(r"NEW_ISSUES_COUNT\s*[:=]\s*(\d+)", re.I)
A5_NO_NEW_RE = re.compile(r"A5_NO_NEW_ISSUES\s*[:=]\s*(YES|NO)", re.I)

def as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value or "")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_json(text: str) -> object | None:
    """Parse JSON even when a CLI emits harmless leading or trailing text."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    starts = [pos for pos in (stripped.find("{"), stripped.find("[")) if pos >= 0]
    if not starts:
        return None
    start = min(starts)
    for end in range(len(stripped), start, -1):
        try:
            return json.loads(stripped[start:end])
        except json.JSONDecodeError:
            continue
    return None


def classify_failure(
    returncode: int | None,
    stdout: str,
    stderr: str,
    timed_out: bool = False,
) -> str:
    out_text = as_text(stdout).lower()
    err_text = as_text(stderr).lower()
    if timed_out or "timeout" in err_text or "timed out" in err_text:
        return "NETWORK_TIMEOUT"
    if any(marker in err_text for marker in AUTH_MARKERS):
        return "AUTH_FAILURE"
    if any(marker in err_text for marker in NETWORK_MARKERS):
        return "NETWORK_ERROR"
    if returncode not in (None, 0):
        if any(marker in out_text for marker in NETWORK_MARKERS):
            return "NETWORK_ERROR"
        return "NLM_ERROR"
    return "NLM_ERROR"


def request_fingerprint(
    notebook_id: str, source_ids: Sequence[str], prompt: str
) -> str:
    canonical = json.dumps(
        {
            "notebook_id": notebook_id,
            "source_ids": list(source_ids),
            "prompt": prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_prompt(
    prompt: str, source_ids: Sequence[str], filename: str | None
) -> list[str]:
    errors: list[str] = []
    if not source_ids:
        errors.append("source_ids_required")
    if "[" not in prompt or "]" not in prompt:
        errors.append("filename_marker_required")
    if filename and f"[{filename}]" not in prompt:
        errors.append("expected_filename_marker_missing")
    return errors


def validate_query_payload(payload: object, expected_source_ids: Sequence[str]) -> dict:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"status": "NLM_ERROR", "errors": ["json_object_required"]}
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        errors.append("answer_missing")
    used = payload.get("sources_used") or []
    if not isinstance(used, list):
        errors.append("sources_used_not_list")
        used = []
    missing = [sid for sid in expected_source_ids if sid not in used]
    if missing:
        errors.append("source_ids_not_used:" + ",".join(missing))
    citations = payload.get("citations") or {}
    values = list(citations.values()) if isinstance(citations, dict) else []
    if expected_source_ids and not any(sid in values for sid in expected_source_ids):
        errors.append("source_citations_missing")
    count_match = NEW_ISSUES_RE.search(answer or "")
    a5_match = A5_NO_NEW_RE.search(answer or "")
    if not count_match or not a5_match:
        errors.append("a5_trailer_missing")
    return {
        "status": "PASS" if not errors else "NLM_ERROR",
        "errors": errors,
        "sources_used": used,
        "citation_count": len(citations) if isinstance(citations, dict) else 0,
        "new_issues_count": int(count_match.group(1)) if count_match else None,
        "a5_no_new_issues": a5_match.group(1).upper() if a5_match else None,
    }


def run_list(
    executable: str,
    profile: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    command = [executable, "notebook", "list", "--json"]
    if profile:
        command.extend(["--profile", profile])
    completed = runner(command, capture_output=True, timeout=120, check=False)
    stdout = as_text(completed.stdout)
    stderr = as_text(completed.stderr)
    payload = compact_json(stdout)
    count = None
    if isinstance(payload, list):
        count = len(payload)
    elif isinstance(payload, dict):
        for key in ("notebooks", "items", "data"):
            if isinstance(payload.get(key), list):
                count = len(payload[key])
                break
    combined = stdout + stderr
    return {
        "checked_at_utc": utc_now(),
        "exit_code": completed.returncode,
        "status": (
            "AUTH_VALID"
            if completed.returncode == 0 and count is not None
            else classify_failure(completed.returncode, combined, "")
        ),
        "notebook_count": count,
    }


def source_list_contains(
    executable: str, notebook_id: str, source_id: str, profile: str | None = None
) -> dict:
    command = [executable, "source", "list", notebook_id, "--json"]
    if profile:
        command.extend(["--profile", profile])
    completed = subprocess.run(command, capture_output=True, timeout=120, check=False)
    payload = compact_json(as_text(completed.stdout))
    if isinstance(payload, list):
        sources: Iterable[object] = payload
    elif isinstance(payload, dict):
        sources = payload.get("sources") or payload.get("items") or payload.get("data") or []
    else:
        sources = []
    found = any(
        isinstance(item, dict) and item.get("id") == source_id
        for item in sources
    )
    return {"exit_code": completed.returncode, "source_id": source_id, "found": found}


def run_query(
    executable: str,
    notebook_id: str,
    prompt: str,
    source_ids: Sequence[str],
    output_dir: Path,
    filename: str | None = None,
    profile: str | None = "default",
    timeout: float = 180.0,
    attempts: int = 3,
    backoff: Sequence[float] = (2.0, 8.0, 20.0),
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    prompt_errors = validate_prompt(prompt, source_ids, filename)
    if prompt_errors:
        return {"status": "NLM_ERROR", "errors": prompt_errors}
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = request_fingerprint(notebook_id, source_ids, prompt)
    manifest_path = output_dir / "request-manifest.jsonl"
    seen: set[str] = set()
    if manifest_path.exists():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line).get("request_fingerprint"))
            except json.JSONDecodeError:
                continue
    if fingerprint in seen:
        return {
            "status": "DUPLICATE_REQUEST_BLOCKED",
            "request_fingerprint": fingerprint,
        }
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "request_fingerprint": fingerprint,
                    "notebook_id": notebook_id,
                    "source_ids": list(source_ids),
                    "profile": profile,
                    "created_at_utc": utc_now(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    attempts_log: list[dict] = []
    command = [
        executable,
        "query",
        "notebook",
        notebook_id,
        prompt,
        "--source-ids",
        ",".join(source_ids),
        "--new-conversation",
        "--timeout",
        str(int(timeout)),
        "--json",
    ]
    if profile:
        command.extend(["--profile", profile])
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            completed = runner(
                command,
                capture_output=True,
                timeout=timeout + 30,
                check=False,
            )
            stdout = as_text(completed.stdout)
            stderr = as_text(completed.stderr)
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            completed = None
            stdout = (
                (exc.stdout or b"").decode("utf-8", "replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )
            stderr = (
                (exc.stderr or b"").decode("utf-8", "replace")
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")
            )
            timed_out = True
        duration = round(time.monotonic() - started, 3)
        payload = compact_json(stdout)
        validation = (
            validate_query_payload(payload, source_ids)
            if payload is not None
            else {
                "status": "NLM_ERROR",
                "errors": ["json_response_missing"],
                "sources_used": [],
                "citation_count": 0,
                "new_issues_count": None,
                "a5_no_new_issues": None,
            }
        )
        failure = (
            None
            if validation["status"] == "PASS" and not timed_out
            else classify_failure(
                None if completed is None else completed.returncode,
                stdout,
                stderr,
                timed_out,
            )
        )
        raw_path = output_dir / f"attempt-{attempt:02d}.raw.txt"
        err_path = output_dir / f"attempt-{attempt:02d}.stderr.txt"
        raw_path.write_bytes(stdout.encode("utf-8", "replace"))
        err_path.write_bytes(stderr.encode("utf-8", "replace"))
        record = {
            "attempt": attempt,
            "started_at_utc": utc_now(),
            "duration_seconds": duration,
            "command": command,
            "exit_code": None if completed is None else completed.returncode,
            "failure_class": failure,
            "validation": validation,
            "raw_path": str(raw_path),
            "stderr_path": str(err_path),
        }
        attempts_log.append(record)
        if failure is None:
            result = {
                "status": "PASS",
                "request_fingerprint": fingerprint,
                "profile": profile,
                "attempts": attempts_log,
            }
            (output_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return result
        record["auth_recheck"] = run_list(executable, profile, runner)
        if failure in {"NLM_ERROR", "AUTH_FAILURE"}:
            break
        if attempt < attempts:
            delay = backoff[min(attempt - 1, len(backoff) - 1)] if backoff else 0
            sleep(delay)
    result = {
        "status": "NLM_ERROR",
        "request_fingerprint": fingerprint,
        "profile": profile,
        "attempts": attempts_log,
    }
    (output_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--nlm", default="nlm")
    pre.add_argument("--profile", default="default")
    pre.add_argument("--json-out", type=Path)
    qry = sub.add_parser("query")
    qry.add_argument("--nlm", default="nlm")
    qry.add_argument("--notebook-id", required=True)
    qry.add_argument("--source-id", action="append", required=True)
    qry.add_argument("--prompt-file", type=Path, required=True)
    qry.add_argument("--filename")
    qry.add_argument("--profile", default="default")
    qry.add_argument("--timeout", type=float, default=180)
    qry.add_argument("--attempts", type=int, default=3)
    qry.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "preflight":
        version = subprocess.run(
            [args.nlm, "--version"], capture_output=True, text=True, check=False
        )
        result = {
            "checked_at_utc": utc_now(),
            "version_exit_code": version.returncode,
            "version": (version.stdout or version.stderr).strip(),
            "notebook_list": run_list(args.nlm, args.profile),
        }
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        print(text, end="")
        if args.json_out:
            args.json_out.write_text(text, encoding="utf-8")
        return 0 if result["notebook_list"]["status"] == "AUTH_VALID" else 2
    prompt = args.prompt_file.read_text(encoding="utf-8")
    result = run_query(
        args.nlm,
        args.notebook_id,
        prompt,
        args.source_id,
        args.output_dir,
        filename=args.filename,
        profile=args.profile,
        timeout=args.timeout,
        attempts=args.attempts,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
