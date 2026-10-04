from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "mplusautomation-guide" / "scripts" / "mplus_queue.py"
SPEC = importlib.util.spec_from_file_location("mplus_queue_resource_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _profile(path: Path, generated_at: str | None = None) -> None:
    path.write_text(json.dumps({
        "generated_at": generated_at or "2026-10-04T22:45:45+00:00",
        "profile": {"system": {
            "free_phys_gib": 1.15, "total_phys_gib": 15.612,
            "free_virtual_gib": 7.276, "commit_limit_gib": 46.051,
            "committed_gib": 38.774,
        }}
    }), encoding="utf-8")


def test_windows_profile_overrides_wsl_view(tmp_path: Path) -> None:
    path = tmp_path / "windows.json"
    _profile(path, generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
    snapshot = MODULE.resource_snapshot(path)
    assert snapshot["source"] == "windows_profile"
    assert snapshot["host_memory_unverified"] is False
    assert snapshot["available_gib"] == 1.15
    assert snapshot["commit_percent"] > 80


def test_stale_profile_is_held(tmp_path: Path) -> None:
    path = tmp_path / "windows.json"
    _profile(path, generated_at="2020-01-01T00:00:00+00:00")
    snapshot = MODULE.resource_snapshot(path, max_profile_age_sec=300)
    assert snapshot["host_memory_unverified"] is True
    assert MODULE.admission_reason(snapshot, [], {"memory_gib": 0.2}, 1) == "host_memory_unverified"


def test_unverified_snapshot_is_held() -> None:
    snapshot = {"host_memory_unverified": True, "available_gib": 99, "total_gib": 100,
                "memory_percent": 1, "cpu_percent": 1, "disk_free_gib": 100}
    assert MODULE.admission_reason(snapshot, [], {"memory_gib": 0.2}, 1) == "host_memory_unverified"
