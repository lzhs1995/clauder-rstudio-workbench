"""Static safety lint for async fan-out worker R scripts.

These workers run in a detached Rterm via async submission. A worker MUST write
its durable state/manifest/validation files and then let the Rterm process exit
cleanly. Wrapping the worker body in ``sink()`` is a recorded failure mode: the
Rterm finishes the computation but does not exit (the sink connection keeps the
process alive), so the fan-out slot is never released and the run can only be
recovered by cancelling the job after confirming the durable output is complete.

This lint is a hard gate: any ``sink(`` in a fan-out worker BLOCKs before submit.
Workers should log via ``cat()`` + ``flush.console()`` and the state-file helper,
never by redirecting the global output connection with ``sink()``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _code_lines(text: str) -> list[tuple[int, str]]:
    """Return (lineno, code-before-comment) for non-blank, non-comment lines."""
    out: list[tuple[int, str]] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # drop a trailing inline comment (naive: R strings rarely contain '#sink')
        code = raw.split("#", 1)[0]
        out.append((i, code))
    return out


def lint_worker_text(text: str, *, name: str = "<worker>") -> list[str]:
    """Return a list of blocking issue strings for one worker's R source."""
    issues: list[str] = []
    for lineno, code in _code_lines(text):
        if "sink(" in code:
            issues.append(
                f"{name}:{lineno}: forbidden sink() in a fan-out worker — sink() keeps the "
                "Rterm process alive after the computation finishes, so the job never exits "
                "and the slot is never released. Log via cat()+flush.console() and write_state(); "
                "do not wrap the worker in sink()."
            )
    return issues


def lint_worker_file(path: str | Path) -> dict[str, Any]:
    """Lint a single worker .R file. Returns {path, ok, issues, error?}."""
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "ok": False, "issues": [], "error": "file not found"}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"path": str(p), "ok": False, "issues": [], "error": str(exc)}
    issues = lint_worker_text(text, name=p.name)
    return {"path": str(p), "ok": not issues, "issues": issues}


def lint_worker_files(paths: list[str | Path]) -> dict[str, Any]:
    """Lint several worker files. ok is True only if every file passes."""
    results = [lint_worker_file(p) for p in paths]
    all_issues: list[str] = []
    for r in results:
        if r.get("error"):
            all_issues.append(f"{r['path']}: {r['error']}")
        all_issues.extend(r.get("issues", []))
    return {"ok": all(r["ok"] for r in results) if results else True,
            "results": results, "issues": all_issues}
