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
            "cpu_percent_samples": [18.0, 20.0, 19.0],
            "disk_free_gib": 12.5,
        }, "paging": {"pages_input_sec": 0.0, "page_reads_sec": 0.0,
                        "disk_sec_per_transfer": 0.001, "samples": 3}}
    }), encoding="utf-8")


def test_windows_profile_overrides_wsl_view(tmp_path: Path) -> None:
    path = tmp_path / "windows.json"
    _profile(path, generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
    snapshot = MODULE.resource_snapshot(path)
    assert snapshot["source"] == "windows_profile"
    assert snapshot["host_memory_unverified"] is False
    assert snapshot["available_gib"] == 1.15
    assert snapshot["commit_percent"] > 80
    assert snapshot['cpu_percent'] == 19.0
    assert snapshot['disk_free_gib'] == 12.5


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


def test_mapped_file_reads_do_not_create_an_arbitrary_admission_block() -> None:
    snapshot = {"host_memory_unverified": False, "available_gib": 8,
                "total_gib": 15.6, "memory_percent": 49, "cpu_percent": 10,
                "disk_free_gib": 100,
                "paging": {"pages_input_sec": 250.0}}
    assert MODULE.admission_reason(snapshot, [], {"memory_gib": 0.2}, 1) is None


def test_missing_paging_is_unknown_not_pressure() -> None:
    snapshot = {"host_memory_unverified": False, "available_gib": 8,
                "total_gib": 15.6, "memory_percent": 49, "cpu_percent": 10,
                "disk_free_gib": 100}
    assert MODULE.admission_reason(snapshot, [], {"memory_gib": 0.2}, 1) is None


def test_profile_missing_native_cpu_cannot_use_wsl_cpu(tmp_path):
    path=tmp_path/'host.json'
    from datetime import datetime, timezone
    _profile(path, datetime.now(timezone.utc).isoformat())
    payload=json.loads(path.read_text())
    del payload['profile']['system']['cpu_percent_samples']
    path.write_text(json.dumps(payload))
    snap=MODULE.resource_snapshot(path)
    assert MODULE.admission_reason(snap, [], {'memory_gib':.1},1)=='host_cpu_unverified'


def test_profile_future_date_is_not_fresh(tmp_path):
    path=tmp_path/'host.json'
    _profile(path, '2099-01-01T00:00:00+00:00')
    assert MODULE.resource_snapshot(path)['host_memory_unverified'] is True


def test_commit_gate_distinct_from_physical_memory():
    snap=dict(available_gib=8,total_gib=16,memory_percent=50,
              cpu_percent=10,disk_free_gib=20,free_virtual_gib=1)
    assert MODULE.admission_reason(snap,[],{'memory_gib':.5},1,{'commit_reserve_gib':2})=='predicted_commit'


def test_invalid_number_is_not_an_available_memory_budget(tmp_path):
    from datetime import datetime, timezone
    path=tmp_path/'host.json'
    _profile(path, datetime.now(timezone.utc).isoformat())
    payload=json.loads(path.read_text());payload['profile']['system']['free_phys_gib']=float('nan')
    path.write_text(json.dumps(payload))
    assert MODULE.resource_snapshot(path)['host_memory_unverified'] is True
