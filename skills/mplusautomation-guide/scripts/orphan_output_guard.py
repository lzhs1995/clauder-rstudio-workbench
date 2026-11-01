#!/usr/bin/env python3
"""只读判断孤儿 Mplus 输出；可另写采用回执，绝不启动、终止或重提估计。

此工具补充 saved-batch 合同，不代替 Windows worker 的调度和累计预算。
采用孤儿输出要求启动前输入哈希、仍在的输入副本、原进程已退出以及完整结果匹配。
老回执缺少这些证据时保留 HOLD，不能把缺证据转成自动重算。
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import uuid

from verify_saved_batch import (
    OUTPUTS, Rejected, document, normalized_out, numeric_values, safe_name, snapshot, verify_member,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(path):
    return os.path.normcase(str(Path(path).resolve()))


def process_state(marker, directory, engine):
    """只能从原 PID+创建时间、exe、cwd、输入参数确认活跃；不可读时保持未知。"""
    import psutil
    try:
        pid, created = marker["pid"], marker["created"]
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return {"state": "UNKNOWN", "reason": "invalid PID"}
        if not isinstance(created, (float, int)) or not math.isfinite(created) or created <= 0:
            return {"state": "UNKNOWN", "reason": "invalid process creation time"}
        proc = psutil.Process(pid)
        actual_created = proc.create_time()
        if abs(actual_created - created) > 1e-3:
            return {"state": "EXITED", "reason": "recorded PID has been reused",
                    "current_process_created": actual_created}
        if canonical(proc.exe()) != canonical(engine) or canonical(proc.cwd()) != canonical(directory):
            return {"state": "UNKNOWN", "reason": "live PID executable or working directory differs"}
        if "model.inp" not in [Path(arg).name.lower() for arg in proc.cmdline()[1:]]:
            return {"state": "UNKNOWN", "reason": "live PID input argument differs"}
        if abs(psutil.Process(pid).create_time() - created) > 1e-3:
            return {"state": "UNKNOWN", "reason": "process changed during inspection"}
        return {"state": "RUNNING", "pid": pid, "created": actual_created,
                "exe": proc.exe(), "cwd": proc.cwd()}
    except psutil.NoSuchProcess:
        return {"state": "EXITED", "reason": "recorded process absent"}
    except (psutil.Error, OSError, KeyError, TypeError, ValueError) as exc:
        return {"state": "UNKNOWN", "reason": type(exc).__name__}


def verify_pins(pins):
    for pin in pins:
        _, current = snapshot(pin["path"])
        if any(current[key] != pin[key] for key in ("sha256", "bytes", "inode", "mtime_ns")):
            raise Rejected("A pinned source or output changed during recovery verification")


def assess_member(source, work, member, engine, tolerance=1e-6, provenance_only=(), probe=process_state):
    source, work = Path(source).resolve(), Path(work).resolve()
    member = safe_name(member)
    src, dst = source / "models" / member, work / "models" / member
    pins, details = [], {}
    row = {"member": member, "decision": "HOLD", "new_engine_authorized": False,
           "engine_calls": 0, "engine_exit_code": None, "budget_remaining": None, "at": now()}
    try:
        if not math.isfinite(tolerance) or tolerance < 0:
            raise Rejected("Invalid numeric tolerance")
        if source == work or dst.is_symlink() or (work / "models").is_symlink():
            raise Rejected("Recovery work must be a separate non-symlink directory")
        contract, pin = document(source / "contracts/RUN_CONTRACT.json")
        pins.append(pin)
        if member not in contract["primary_sequence"]:
            raise Rejected("Member is outside the original primary sequence")
        job, pin = document(src / "job.json")
        pins.append(pin)
        expected = job.get("hashes", {})
        if not expected or "model.inp" not in expected:
            raise Rejected("Missing original input hashes")
        provenance_only = {safe_name(name) for name in provenance_only}
        if any(not name.endswith(".json") for name in provenance_only):
            raise Rejected("Provenance-only exceptions must explicitly name JSON metadata")
        inp, _ = snapshot(src / "model.inp")
        if any(name.lower().encode("ascii") in inp.lower() for name in provenance_only):
            raise Rejected("A provenance-only input is referenced by model.inp")
        for name, digest in expected.items():
            _, pin = snapshot(src / safe_name(name))
            pins.append(pin)
            if pin["sha256"] != digest:
                raise Rejected("Original input changed: " + name)
        runtime = {name: digest for name, digest in expected.items() if name not in provenance_only}
        details["inputs"] = runtime
        if not dst.exists():
            return {**row, "decision": "NO_WORK_DIRECTORY", "reason": "No adoption or new estimation authorized",
                    "pins": pins}
        marker_path = dst / "ENGINE_STARTED.json"
        marker = None
        if marker_path.exists():
            marker, pin = document(marker_path)
            pins.append(pin)
            observed = probe(marker, dst, engine)
            details["process"] = observed
            if observed["state"] == "RUNNING":
                return {**row, "decision": "WAIT_FOR_ORIGINAL_ENGINE", **details, "pins": pins}
            if observed["state"] != "EXITED":
                raise Rejected("Original process state is unknown; no adoption or resubmission")
        if (dst / "RESULT.json").exists():
            checked = verify_member(source, work, member, tolerance, provenance_only)
            pins.extend(checked["pins"])
            verify_pins(pins)
            return {**row, "decision": "REUSE_VERIFIED_RESULT", "engine_exit_code": 0,
                    **details, "comparison": checked["compare"], "pins": pins}
        if marker is None:
            raise Rejected("Saved output lacks an original engine-start record")
        # 当前输入相同不能补造启动前来源记录。旧薄回执保持待审，不自动重算。
        if marker.get("inputs") != runtime:
            raise Rejected("Engine-start record lacks the exact original runtime input hashes")
        created = marker.get("created")
        if not isinstance(created, (float, int)) or not math.isfinite(created) or created <= 0:
            raise Rejected("Engine-start record lacks a valid creation time")
        for name, digest in runtime.items():
            _, pin = snapshot(dst / name)
            pins.append(pin)
            if pin["sha256"] != digest:
                raise Rejected("Staged input changed: " + name)
        comparison = {}
        for name in OUTPUTS:
            original, old_pin = snapshot(src / name)
            saved, new_pin = snapshot(dst / name)
            pins.extend((old_pin, new_pin))
            if (old_pin["device"], old_pin["inode"]) == (new_pin["device"], new_pin["inode"]):
                raise Rejected("Saved output aliases the original: " + name)
            if int(new_pin["mtime_ns"]) / 1e9 + 2 < created:
                raise Rejected("Saved output predates the recorded engine start: " + name)
            comparison[name] = {"original_sha256": old_pin["sha256"], "saved_sha256": new_pin["sha256"]}
            if name == "model.out":
                if normalized_out(original) != normalized_out(saved):
                    raise Rejected("Non-clock Mplus output differences require review")
            else:
                old, new = numeric_values(original), numeric_values(saved)
                if len(old) != len(new):
                    raise Rejected("Numeric output length differs: " + name)
                difference = max(abs(a - b) for a, b in zip(old, new))
                if difference > tolerance:
                    raise Rejected("Numeric output differs: " + name)
                comparison[name].update(count=len(new), max_absolute_difference=difference)
        verify_pins(pins)
        return {**row, "decision": "ADOPTABLE_SAVED_OUTPUTS", **details, "comparison": comparison,
                "pins": pins, "exit_code_basis": "UNKNOWN: controller receipt absent",
                "budget_basis": "No new invocation; original time/call ledger remains authoritative"}
    except (Rejected, OSError, ValueError, KeyError, TypeError) as exc:
        return {**row, "decision": "HOLD", **details, "reason": str(exc), "pins": pins}


@contextmanager
def recovery_lock(work):
    """恢复采用只写同一工作目录的独立回执；真正 worker 接入时也须持有同一锁。"""
    path = Path(work) / ".orphan-recovery.lock"
    if path.is_symlink():
        raise OSError("Recovery lock cannot be a symlink")
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def adopt_member(source, work, member, engine, **kwargs):
    """仅新建 ADOPTION 回执；不伪造 RESULT/exit=0，不移动任何旧输入/输出/失败。"""
    work = Path(work).resolve()
    with recovery_lock(work):
        result = assess_member(source, work, member, engine, **kwargs)
        if result["decision"] != "ADOPTABLE_SAVED_OUTPUTS":
            return result
        verify_pins(result["pins"])
        folder = work / "recovery_adoptions"
        if folder.is_symlink():
            raise OSError("Adoption directory cannot be a symlink")
        folder.mkdir(exist_ok=True)
        target = folder / (safe_name(member) + ".json")
        if target.exists():
            prior, _ = document(target)
            if (prior.get("schema") != "mplus-orphan-adoption/1"
                    or prior.get("decision") != "OUTPUTS_ADOPTED" or prior.get("member") != member
                    or prior.get("source") != str(Path(source).resolve()) or prior.get("work") != str(work)
                    or prior.get("engine_exit_code") is not None
                    or prior.get("comparison") != result["comparison"] or prior.get("inputs") != result["inputs"]):
                return {**result, "decision": "HOLD", "reason": "Existing adoption pins differ"}
            return {**result, "decision": "ADOPTION_ALREADY_RECORDED", "adoption": str(target)}
        # 新原子文件仅记录统计输出采用；历史进程退出码及预算继续保持未知/原值。
        record = {**result, "schema": "mplus-orphan-adoption/1", "decision": "OUTPUTS_ADOPTED",
                  "source": str(Path(source).resolve()), "work": str(work)}
        temp = folder / (".adoption-" + uuid.uuid4().hex + ".tmp")
        with temp.open("x", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
        return {**record, "adoption": str(target)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--member", required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--provenance-only-file", action="append", default=[])
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--record-adoption", action="store_true")
    args = parser.parse_args(argv)
    if args.report.exists():
        parser.error("--report must be new; prior evidence is preserved")
    if args.source.resolve() in args.report.resolve().parents or (
            (args.work / "models").resolve() in args.report.resolve().parents):
        parser.error("--report must be outside original sources and model output directories")
    if os.name != "nt":
        parser.error("Run this process/recovery CLI on Windows via xdev; use verify_saved_batch.py for Mac readback")
    action = adopt_member if args.record_adoption else assess_member
    try:
        result = action(args.source, args.work, args.member, args.engine, tolerance=args.tolerance,
                        provenance_only=args.provenance_only_file)
    except OSError as exc:
        result = {"decision": "HOLD", "reason": "Recovery lock or filesystem unavailable: " + str(exc),
                  "engine_calls": 0, "new_engine_authorized": False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"decision": result["decision"], "report": str(args.report.resolve()),
                      "engine_calls": 0, "engine_exit_code": result.get("engine_exit_code")},
                     ensure_ascii=False))
    if result["decision"] in ("REUSE_VERIFIED_RESULT", "ADOPTABLE_SAVED_OUTPUTS",
                               "OUTPUTS_ADOPTED", "ADOPTION_ALREADY_RECORDED"):
        return 0
    return 75 if result["decision"] == "WAIT_FOR_ORIGINAL_ENGINE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
