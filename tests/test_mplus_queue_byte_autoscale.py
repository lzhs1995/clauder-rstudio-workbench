from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "skills" / "mplusautomation-guide" / "scripts" / "mplus_queue.py"
SPEC = importlib.util.spec_from_file_location("mplus_queue_byte_autoscale_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _snap(at: float, percent: float, available: float, commit: float | None = 6.0) -> dict:
    # 16 GiB Windows 主机：百分比高于 85%，但字节余量仍可能足够再起一个 Mplus
    snap = dict(at=at, memory_percent=percent, available_gib=available, total_gib=15.6,
                cpu_percent=20, disk_free_gib=50, host_memory_unverified=False)
    if commit is not None:
        snap["free_virtual_gib"] = commit
    return snap


def _ticks(q, n: int, **kw) -> None:
    for i in range(n):
        q.tick(_snap(1000 + 30 * (i + 1), **kw))


def _queue(root: Path, settings: dict | None = None):
    root.mkdir(parents=True, exist_ok=True)
    if settings is not None:
        (root / "config.json").write_text(json.dumps(settings), encoding="utf-8")
    return MODULE.Queue(root)


def test_high_percent_with_byte_headroom_adds_slot(tmp_path: Path) -> None:
    q = _queue(tmp_path / "q")
    assert q.get("limit") == 1
    _ticks(q, 5, percent=90, available=4.0)
    assert q.get("limit") == 2


def test_high_percent_without_byte_headroom_stays(tmp_path: Path) -> None:
    q = _queue(tmp_path / "q")
    # 1.9 - 0.5 < 1.5：不够再容纳一步
    _ticks(q, 10, percent=90, available=1.9)
    assert q.get("limit") == 1


def test_running_reservations_are_subtracted(tmp_path: Path) -> None:
    q = _queue(tmp_path / "q")
    q.db.execute("INSERT INTO tasks(id,payload,status) VALUES(?,?,?)",
                 ("t1", json.dumps({"memory_gib": 2.5}), "running"))
    # 4.0 - 2.5 - 0.5 < 1.5
    _ticks(q, 10, percent=90, available=4.0)
    assert q.get("limit") == 1


def test_commit_headroom_blocks_when_configured(tmp_path: Path) -> None:
    q = _queue(tmp_path / "q", {"resource_policy": {"commit_reserve_gib": 1.5}})
    _ticks(q, 10, percent=90, available=6.0, commit=1.8)
    assert q.get("limit") == 1
    q2 = _queue(tmp_path / "q2", {"resource_policy": {"commit_reserve_gib": 1.5}})
    _ticks(q2, 5, percent=90, available=6.0, commit=None)
    assert q2.get("limit") == 1


def test_percent_path_unchanged(tmp_path: Path) -> None:
    q = _queue(tmp_path / "q")
    _ticks(q, 5, percent=50, available=1.0)
    assert q.get("limit") == 2


def test_unverified_host_does_not_use_byte_path() -> None:
    snap = _snap(0, percent=90, available=8.0)
    snap["host_memory_unverified"] = True
    assert MODULE.scale_up_memory_ok(snap, 0.0) is False


def test_plain_queue_can_declare_initial_limit_and_cap(tmp_path: Path) -> None:
    q = _queue(tmp_path / "q", {"parallel_cap": 4, "initial_parallel_limit": 3})
    assert (q.get("limit"), q.get("cap")) == (3, 4)
    _ticks(q, 5, percent=90, available=8.0)
    assert q.get("limit") == 4
    _ticks(q, 10, percent=90, available=8.0)
    assert q.get("limit") == 4


def test_declared_limits_apply_only_to_new_queue(tmp_path: Path) -> None:
    root = tmp_path / "q"
    q = _queue(root)
    q.event("resources", {})
    q.db.close()
    q2 = _queue(root, {"parallel_cap": 4, "initial_parallel_limit": 3})
    assert (q2.get("limit"), q2.get("cap")) == (1, 3)


@pytest.mark.parametrize("settings", [
    {"parallel_cap": 0},
    {"parallel_cap": 13},
    {"parallel_cap": 2, "initial_parallel_limit": 3},
    {"initial_parallel_limit": 0},
])
def test_invalid_declared_limits_are_rejected(tmp_path: Path, settings: dict) -> None:
    with pytest.raises(ValueError):
        _queue(tmp_path / "q", settings)
