"""Opt-in measured admission in the original HostReservations SQLite database.

The Windows sampler runs after BEGIN IMMEDIATE. Existing acquire/release callers
retain their contract; unregistered applications are not controlled by this API.
No observed-allocation credit, process termination or automatic release occurs.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
import re
import shutil
import time

GIB = 1024 ** 3
MAX_BYTES = 2 ** 53
KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}\Z")
VOLUME_RE = re.compile(r"[A-Za-z]:\\\Z")
POLICY_FIELDS = {
    "schema", "host_id", "physical_reserve_bytes", "commit_reserve_bytes",
    "processor_budget", "unmanaged_physical_bytes", "unmanaged_commit_bytes",
    "unmanaged_processors", "volume_reserve_bytes", "unmanaged_volume_bytes",
    "max_sample_seconds", "legacy_volume_bytes", "unmanaged_budget_verified",
    "unmanaged_budget_evidence_sha256",
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _integer(value, field, minimum=0, maximum=MAX_BYTES):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + field)
    return value


def _finite(value, field, minimum=0, maximum=MAX_BYTES):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not minimum <= value <= maximum):
        raise ValueError("invalid " + field)
    return value


def _key(value, field):
    if not isinstance(value, str) or KEY_RE.fullmatch(value) is None:
        raise ValueError("invalid " + field)
    return value


def _volumes(value, field, *, nonempty=False):
    if not isinstance(value, dict) or (nonempty and not value):
        raise ValueError("invalid " + field)
    result = {}
    for root, amount in value.items():
        if not isinstance(root, str) or VOLUME_RE.fullmatch(root) is None:
            raise ValueError("local drive root required: " + field)
        canonical = root.upper()
        if canonical in result:
            raise ValueError("duplicate drive alias: " + field)
        result[canonical] = _integer(amount, field)
    return dict(sorted(result.items()))


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != POLICY_FIELDS:
        raise ValueError("complete strict host policy required")
    value = dict(policy)
    if value["schema"] != "host-measured-policy-v1":
        raise ValueError("unsupported strict host policy")
    if (not isinstance(value["host_id"], str) or not 1 <= len(value["host_id"]) <= 255
            or value["host_id"] != value["host_id"].casefold()
            or any(ord(char) < 32 for char in value["host_id"])):
        raise ValueError("lowercase Windows computer name required")
    for field in ("physical_reserve_bytes", "commit_reserve_bytes",
                  "unmanaged_physical_bytes", "unmanaged_commit_bytes"):
        value[field] = _integer(value[field], field)
    value["processor_budget"] = _integer(value["processor_budget"], "processor_budget", 1, 4096)
    value["unmanaged_processors"] = _integer(value["unmanaged_processors"], "unmanaged_processors", 0, 4096)
    value["max_sample_seconds"] = _finite(value["max_sample_seconds"], "max_sample_seconds", .001, 30)
    value["volume_reserve_bytes"] = _volumes(value["volume_reserve_bytes"], "volume_reserve_bytes", nonempty=True)
    value["unmanaged_volume_bytes"] = _volumes(value["unmanaged_volume_bytes"], "unmanaged_volume_bytes")
    if set(value["unmanaged_volume_bytes"]) != set(value["volume_reserve_bytes"]):
        raise ValueError("explicit unmanaged growth required for every configured volume")
    if type(value["unmanaged_budget_verified"]) is not bool:
        raise ValueError("explicit unmanaged budget verification required")
    evidence = value["unmanaged_budget_evidence_sha256"]
    if value["unmanaged_budget_verified"]:
        if not isinstance(evidence, str) or re.fullmatch(r"[0-9a-f]{64}", evidence) is None:
            raise ValueError("unmanaged budget evidence digest required")
    elif evidence is not None:
        raise ValueError("unverified unmanaged budget cannot carry accepted evidence")
    if not isinstance(value["legacy_volume_bytes"], dict):
        raise ValueError("explicit legacy disk budgets required")
    legacy = {}
    for key, amounts in value["legacy_volume_bytes"].items():
        if not isinstance(key, str) or not key or len(key) > 1024:
            raise ValueError("invalid legacy reservation key")
        legacy[key] = _volumes(amounts, "legacy_volume_bytes", nonempty=True)
        if not set(legacy[key]) <= set(value["volume_reserve_bytes"]):
            raise ValueError("legacy volume missing configured reserve")
    value["legacy_volume_bytes"] = legacy
    return value


def _tables(db):
    db.execute("CREATE TABLE IF NOT EXISTS host_measured_policy (policy_id TEXT PRIMARY KEY, policy_json TEXT NOT NULL, sha256 TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS host_measured_control (singleton INTEGER PRIMARY KEY CHECK(singleton=1), active_policy_id TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS host_measured_reservations (key TEXT PRIMARY KEY, record_json TEXT NOT NULL)")


def configure_policy(db, policy_id, policy):
    """Host-owner preparation. Preserve policy history; new versions require no reservations."""
    _key(policy_id, "policy_id")
    policy = validate_policy(policy)
    raw = _canonical(policy)
    sha = hashlib.sha256(raw.encode()).hexdigest()
    if not policy["unmanaged_budget_verified"]:
        return dict(status="STRICT_HOST_POLICY_NOT_REGISTERED", policy_id=policy_id,
                    waiting_resource="unmanaged_growth", legacy_rows_changed=0)
    db.execute("BEGIN IMMEDIATE")
    try:
        _tables(db)
        old = db.execute("SELECT policy_id,policy_json,sha256 FROM host_measured_policy WHERE policy_id=?", (policy_id,)).fetchone()
        if old is not None and tuple(old) != (policy_id, raw, sha):
            raise ValueError("STRICT_HOST_POLICY_CONFLICT")
        current = db.execute("SELECT active_policy_id FROM host_measured_control WHERE singleton=1").fetchone()
        if current is not None and current[0] != policy_id:
            if db.execute("SELECT 1 FROM reservations LIMIT 1").fetchone() is not None:
                raise ValueError("ACTIVE_RESERVATIONS_PREVENT_POLICY_CHANGE")
        if old is None:
            db.execute("INSERT INTO host_measured_policy VALUES (?,?,?)", (policy_id, raw, sha))
        db.execute("INSERT OR REPLACE INTO host_measured_control VALUES (1,?)", (policy_id,))
        db.execute("COMMIT")
        return dict(status="STRICT_HOST_POLICY_REGISTERED", policy_id=policy_id,
                    sha256=sha, duplicate=old is not None, legacy_rows_changed=0)
    except BaseException:
        db.execute("ROLLBACK")
        raise


def _policy(db, policy_id):
    active = db.execute("SELECT active_policy_id FROM host_measured_control WHERE singleton=1").fetchone()
    row = db.execute("SELECT policy_id,policy_json,sha256 FROM host_measured_policy WHERE policy_id=?", (policy_id,)).fetchone()
    if row is None or active is None or active[0] != policy_id:
        raise ValueError("STRICT_HOST_POLICY_NOT_REGISTERED")
    policy = validate_policy(json.loads(row[1]))
    raw = _canonical(policy)
    if raw != row[1] or hashlib.sha256(raw.encode()).hexdigest() != row[2]:
        raise ValueError("STRICT_HOST_POLICY_CHANGED")
    return policy, row[2]


def windows_snapshot(volume_roots):
    """Windows APIs only. Pagefile/virtual address availability is not commit headroom."""
    if os.name != "nt":
        raise RuntimeError("WINDOWS_NATIVE_SAMPLER_REQUIRED")

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]

    class PerformanceInfo(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in (
            "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable",
            "SystemCache", "KernelTotal", "KernelPaged", "KernelNonpaged", "PageSize")] + [
            (name, wintypes.DWORD) for name in ("HandleCount", "ProcessCount", "ThreadCount")]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatus)]
    kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
    psapi.GetPerformanceInfo.argtypes = [ctypes.POINTER(PerformanceInfo), wintypes.DWORD]
    psapi.GetPerformanceInfo.restype = wintypes.BOOL
    kernel.GetActiveProcessorCount.argtypes = [wintypes.WORD]
    kernel.GetActiveProcessorCount.restype = wintypes.DWORD
    kernel.GetComputerNameW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetComputerNameW.restype = wintypes.BOOL
    kernel.GetVolumeNameForVolumeMountPointW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetVolumeNameForVolumeMountPointW.restype = wintypes.BOOL
    memory = MemoryStatus(); memory.dwLength = ctypes.sizeof(memory)
    performance = PerformanceInfo(); performance.cb = ctypes.sizeof(performance)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not psapi.GetPerformanceInfo(ctypes.byref(performance), ctypes.sizeof(performance)):
        raise ctypes.WinError(ctypes.get_last_error())
    count = int(kernel.GetActiveProcessorCount(0xFFFF))
    if not count:
        raise ctypes.WinError(ctypes.get_last_error())
    name = ctypes.create_unicode_buffer(256); size = wintypes.DWORD(len(name))
    if not kernel.GetComputerNameW(name, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    page = int(performance.PageSize)
    if page <= 0:
        raise ValueError("INVALID_NATIVE_PAGE_SIZE")
    volumes = {}
    for root in volume_roots:
        identity = ctypes.create_unicode_buffer(1024)
        if not kernel.GetVolumeNameForVolumeMountPointW(root, identity, len(identity)):
            raise ctypes.WinError(ctypes.get_last_error())
        usage = shutil.disk_usage(root)
        volumes[root] = dict(volume_id=identity.value.casefold(), free_bytes=usage.free, total_bytes=usage.total)
    return dict(source="WINDOWS_NATIVE_V1", host_id=name.value.casefold(),
        physical_total_bytes=min(int(memory.ullTotalPhys), int(performance.PhysicalTotal) * page),
        physical_available_bytes=min(int(memory.ullAvailPhys), int(performance.PhysicalAvailable) * page),
        commit_limit_bytes=int(performance.CommitLimit) * page,
        commit_total_bytes=int(performance.CommitTotal) * page,
        logical_processors=count, volumes=volumes)


def _owner(pid, created):
    import psutil
    try:
        process = psutil.Process(pid)
        return process.is_running() and abs(process.create_time() - created) < .001
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return None


def _snapshot(raw, roots, policy):
    if not isinstance(raw, dict) or raw.get("host_id") != policy["host_id"]:
        raise ValueError("HOST_IDENTITY_UNVERIFIED")
    if not isinstance(raw.get("source"), str) or not raw["source"]:
        raise ValueError("MEASUREMENT_SOURCE_UNVERIFIED")
    result = {"source": raw["source"], "host_id": raw["host_id"]}
    for key in ("physical_total_bytes", "physical_available_bytes", "commit_limit_bytes", "commit_total_bytes"):
        result[key] = _integer(raw.get(key), key)
    if (result["physical_total_bytes"] == 0 or result["commit_limit_bytes"] == 0
            or result["physical_available_bytes"] > result["physical_total_bytes"]
            or result["commit_total_bytes"] > result["commit_limit_bytes"]):
        raise ValueError("INVALID_NATIVE_MEMORY_COUNTERS")
    result["free_commit_bytes"] = result["commit_limit_bytes"] - result["commit_total_bytes"]
    result["logical_processors"] = _integer(raw.get("logical_processors"), "logical_processors", 1, 4096)
    entries = raw.get("volumes")
    if not isinstance(entries, dict) or set(entries) != set(roots):
        raise ValueError("OUTPUT_VOLUME_MEASUREMENT_MISSING")
    result["volumes"] = {}
    for root, value in entries.items():
        if not isinstance(value, dict) or not isinstance(value.get("volume_id"), str) or not value["volume_id"]:
            raise ValueError("OUTPUT_VOLUME_IDENTITY_UNVERIFIED")
        free = _integer(value.get("free_bytes"), "free_bytes")
        total = _integer(value.get("total_bytes"), "total_bytes", 1)
        if free > total:
            raise ValueError("INVALID_OUTPUT_VOLUME_COUNTERS")
        result["volumes"][root] = dict(volume_id=value["volume_id"], free_bytes=free, total_bytes=total)
    return result


def _legacy(row):
    key, pid, created, gib, processors, heartbeat = tuple(row)
    if not isinstance(key, str) or not key:
        raise ValueError("INVALID_LEGACY_RESERVATION_KEY")
    _integer(pid, "reservation_pid", 1, 2 ** 31 - 1)
    _finite(created, "reservation_created", .001)
    _finite(gib, "legacy_gib", 0, MAX_BYTES / GIB)
    _integer(processors, "reservation_processors", 1, 4096)
    # 四舍五入向上，不把旧浮点GiB误当bytes或低估。
    return dict(key=key, pid=pid, created=created, physical_bytes=math.ceil(gib * GIB),
                commit_bytes=math.ceil(gib * GIB), processors=processors)


def _denied(resource, reason, **evidence):
    return dict(admitted=False, new_reservation=False, waiting_resource=resource,
                reason=reason, **evidence)


def acquire_measured(db, key, pid, created, physical_bytes, commit_bytes, processors,
                     volume_bytes, policy_id, *, sampler=None, owner_probe=None, clock_ns=None):
    """Atomically sample and reserve. Tests alone may inject synchronous providers.

    The sampler duration bound is checked before admission; it cannot preempt an
    OS API that hangs. Hold the same database only for short native queries.
    """
    _key(key, "key"); _key(policy_id, "policy_id")
    _integer(pid, "pid", 1, 2 ** 31 - 1); _finite(created, "created", .001)
    _integer(physical_bytes, "physical_bytes"); _integer(commit_bytes, "commit_bytes")
    _integer(processors, "processors", 1, 4096)
    volumes = _volumes(volume_bytes, "volume_bytes", nonempty=True)
    sampler = sampler or windows_snapshot
    owner_probe = owner_probe or _owner
    clock_ns = clock_ns or time.monotonic_ns
    if not all(callable(value) for value in (sampler, owner_probe, clock_ns)):
        raise ValueError("CALLABLE_NATIVE_PROVIDER_REQUIRED")
    db.execute("BEGIN IMMEDIATE")
    try:
        _tables(db)
        policy, policy_sha = _policy(db, policy_id)
        if not policy["unmanaged_budget_verified"]:
            result = _denied("unmanaged_growth", "EXTERNAL_WORKLOAD_GROWTH_UNVERIFIED")
            db.execute("COMMIT"); return result
        if not set(volumes) <= set(policy["volume_reserve_bytes"]):
            raise ValueError("OUTPUT_VOLUME_NOT_IN_HOST_POLICY")
        contract = dict(key=key, pid=pid, created=created, physical_bytes=physical_bytes,
                        commit_bytes=commit_bytes, processors=processors, volume_bytes=volumes,
                        policy_id=policy_id, policy_sha256=policy_sha)
        rows = [_legacy(row) for row in db.execute("SELECT * FROM reservations").fetchall()]
        strict = {row[0]: json.loads(row[1]) for row in db.execute("SELECT key,record_json FROM host_measured_reservations")}
        previous = next((row for row in rows if row["key"] == key), None)
        if key in strict and strict[key].get("contract") != contract:
            raise ValueError("STRICT_RESERVATION_CONTRACT_CONFLICT")
        if previous is not None:
            if (previous["pid"] != pid or abs(previous["created"] - created) >= .001):
                raise ValueError("RESERVATION_OWNER_MISMATCH")
            if key not in strict:
                raise ValueError("STRICT_KEY_COLLIDES_WITH_LEGACY")
        elif key in strict:
            raise ValueError("RELEASED_STRICT_KEY_REQUIRES_NEW_ATTEMPT")
        for row in rows:
            if owner_probe(row["pid"], row["created"]) is not True:
                result = _denied("owner_identity", "EXISTING_OWNER_UNVERIFIED_OR_ORPHAN", reservation_key=row["key"])
                db.execute("COMMIT"); return result
        if owner_probe(pid, created) is not True:
            result = _denied("owner_identity", "CANDIDATE_OWNER_UNVERIFIED")
            db.execute("COMMIT"); return result
        roots = sorted(policy["volume_reserve_bytes"])
        before = clock_ns()
        try:
            raw = sampler(roots)
            after = clock_ns()
            _integer(before, "sample_start_ns", 0, 2 ** 63 - 1)
            _integer(after, "sample_end_ns", 0, 2 ** 63 - 1)
            if after < before or after - before > policy["max_sample_seconds"] * 1_000_000_000:
                result = _denied("measurement", "SAMPLE_DURATION_EXCEEDED", sample_duration_ns=after - before)
                db.execute("COMMIT"); return result
            sample = _snapshot(raw, roots, policy)
        except Exception as exc:
            result = _denied("measurement", "NATIVE_RESOURCE_MEASUREMENT_FAILED", error_type=type(exc).__name__, error=str(exc)[:512])
            db.execute("COMMIT"); return result
        identity = {root: value["volume_id"] for root, value in sample["volumes"].items()}
        # 同一底层volume即使有两个drive letter，增长相加、保留量取较大值。
        free_by_id, reserve_by_id, growth_by_id = {}, {}, {}
        for root, value in sample["volumes"].items():
            vid = value["volume_id"]
            free_by_id[vid] = min(free_by_id.get(vid, value["free_bytes"]), value["free_bytes"])
            reserve_by_id[vid] = max(reserve_by_id.get(vid, 0), policy["volume_reserve_bytes"][root])
            growth_by_id[vid] = growth_by_id.get(vid, 0) + policy["unmanaged_volume_bytes"][root]
        totals = dict(physical_bytes=policy["unmanaged_physical_bytes"],
                      commit_bytes=policy["unmanaged_commit_bytes"], processors=policy["unmanaged_processors"])
        for row in rows:
            saved = strict.get(row["key"])
            if saved is not None:
                saved_contract = saved.get("contract", {})
                if (saved.get("schema") != "host-measured-reservation-v1"
                        or saved_contract.get("key") != row["key"]
                        or saved_contract.get("pid") != row["pid"]
                        or saved_contract.get("created") != row["created"]
                        or saved_contract.get("processors") != row["processors"]
                        or saved_contract.get("policy_sha256") != policy_sha):
                    raise ValueError("STRICT_RESERVATION_RECORD_CHANGED")
                for field in ("physical_bytes", "commit_bytes"):
                    _integer(saved_contract.get(field), field)
                if row["physical_bytes"] != max(saved_contract["physical_bytes"], saved_contract["commit_bytes"]):
                    raise ValueError("STRICT_LEGACY_COMPATIBILITY_ROW_CHANGED")
                saved_volumes = _volumes(saved_contract.get("volume_bytes"), "saved_volume_bytes", nonempty=True)
                if saved.get("volume_identities") != {root: identity.get(root) for root in saved_volumes}:
                    raise ValueError("RESERVED_OUTPUT_VOLUME_IDENTITY_CHANGED")
                if row["key"] != key:
                    for field in totals:
                        totals[field] += saved_contract[field]
                    for root, amount in saved_volumes.items():
                        vid = identity[root]; growth_by_id[vid] = growth_by_id.get(vid, 0) + amount
            elif row["key"] != key:
                if row["key"] not in policy["legacy_volume_bytes"]:
                    result = _denied("legacy_disk_budget", "LEGACY_OUTPUT_GROWTH_UNVERIFIED",
                                     reservation_key=row["key"])
                    db.execute("COMMIT"); return result
                for field in totals:
                    totals[field] += row[field]
                for root, amount in policy["legacy_volume_bytes"][row["key"]].items():
                    vid = identity[root]; growth_by_id[vid] = growth_by_id.get(vid, 0) + amount
        required = {field: totals[field] + contract[field] for field in totals}
        for root, amount in volumes.items():
            vid = identity[root]; growth_by_id[vid] = growth_by_id.get(vid, 0) + amount
        evidence = dict(policy_id=policy_id, policy_sha256=policy_sha, sample=sample,
                        sample_duration_ns=after - before, required=required,
                        reserved_volume_growth_bytes=growth_by_id,
                        legacy_memory_reader_receives_max_gib=True, unregistered_processes_controlled=False,
                        unmanaged_evidence_independently_verified=False)
        decision_ns = clock_ns()
        _integer(decision_ns, "decision_ns", 0, 2 ** 63 - 1)
        evidence["sample_to_decision_ns"] = decision_ns - before
        if decision_ns < after or decision_ns - before > policy["max_sample_seconds"] * 1_000_000_000:
            result = _denied("measurement", "DECISION_BUDGET_EXCEEDED", **evidence)
        elif sample["physical_available_bytes"] - required["physical_bytes"] < policy["physical_reserve_bytes"]:
            result = _denied("physical_ram", "INSUFFICIENT_PHYSICAL_AVAILABLE", **evidence)
        elif sample["free_commit_bytes"] - required["commit_bytes"] < policy["commit_reserve_bytes"]:
            result = _denied("commit", "INSUFFICIENT_FREE_COMMIT", **evidence)
        elif required["processors"] > min(policy["processor_budget"], sample["logical_processors"]):
            result = _denied("processors", "PROCESSOR_RESERVATION_EXCEEDED", **evidence)
        elif any(free_by_id[vid] - growth_by_id.get(vid, 0) < floor for vid, floor in reserve_by_id.items()):
            result = _denied("disk_bytes", "OUTPUT_VOLUME_RESERVATION_EXCEEDED", **evidence)
        else:
            saved = dict(schema="host-measured-reservation-v1", contract=contract,
                         volume_identities={root: identity[root] for root in volumes})
            if previous is None:
                db.execute("INSERT INTO reservations VALUES (?,?,?,?,?,?)",
                    (key, pid, created, max(physical_bytes, commit_bytes) / GIB, processors, time.time()))
                db.execute("INSERT INTO host_measured_reservations VALUES (?,?)", (key, _canonical(saved)))
            result = dict(admitted=True, new_reservation=previous is None, duplicate=previous is not None,
                          execution_authorized=False, waiting_resource=None, **evidence)
        db.execute("COMMIT")
        return result
    except BaseException:
        db.execute("ROLLBACK")
        raise
