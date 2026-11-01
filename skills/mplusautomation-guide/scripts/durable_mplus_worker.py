#!/usr/bin/env python3
"""Windows 单批次 Mplus 执行器：固定来源、永久调用意图、独立引擎监督与原目录恢复。

科研调用必须在 Windows，明确提供预算已用量和授权说明。--synthetic-test 仅用于
具名合成夹具，其结果始终标注为合成。此模块不改旧探针、旧工作目录或共享 xdev。
"""
import argparse
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
import uuid

import psutil

from orphan_output_guard import assess_member, adopt_member, recovery_lock, verify_pins
from verify_saved_batch import OUTPUTS, Rejected, document, safe_name, snapshot, verify_member


SCHEMA = "mplus-durable-plan/1"
HERE = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    path = Path(path)
    first = path.stat()
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    last = path.stat()
    if (first.st_ino, first.st_size, first.st_mtime_ns) != (last.st_ino, last.st_size, last.st_mtime_ns):
        raise Rejected("File changed while hashing: " + str(path))
    return value.hexdigest()


def load(path):
    return document(path)[0]


def load_binding(work):
    binding_path = Path(work) / "BATCH_BINDING.json"
    expected = load(Path(work) / "BATCH_BINDING_SHA256.json")
    if digest(binding_path) != expected.get("sha256"):
        raise Rejected("Original batch binding changed; budgets cannot be reset during recovery")
    return load(binding_path)


def atomic_json(path, value, *, new=False):
    """调用方持有对应 OS 锁；新证据不覆盖原文件。"""
    path = Path(path)
    if path.is_symlink() or (new and path.exists()):
        raise Rejected("Refusing to replace prior evidence: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with temp.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if new and path.exists():
        raise Rejected("Evidence appeared while writing: " + str(path))
    os.replace(temp, path)


@contextmanager
def file_lock(path):
    path = Path(path)
    if path.is_symlink():
        raise Rejected("Lock is a symlink")
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def host():
    # 此执行目录只能在原主机运行；PID 始终结合精确创建时间，boot_time 仅作观察值。
    return {"hostname": platform.node(), "system": platform.system()}


def process_record():
    proc = psutil.Process()
    return {"pid": proc.pid, "created": proc.create_time(), "exe": proc.exe(),
            "host": host(), "boot_time": psutil.boot_time(), "at": now()}


def process_finished(proc):
    if not proc.is_running():
        return True
    if os.name == "nt":
        # Windows 的已退出进程可因其他句柄仍在而继续被查询；零等待读真实退出状态。
        try:
            proc.wait(timeout=0)
        except psutil.TimeoutExpired:
            pass
        else:
            return True
    return proc.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD)


def live_guardian(claim, work, member):
    if claim.get("host") != host():
        raise Rejected("Guardian record is from another host")
    # Windows 的 psutil.boot_time 在不同进程内是略有差异的估计值，不能精确比相等。
    # 主机、PID、精确创建时间、exe 与原命令共同确认身份，不从时钟估计推断死亡。
    try:
        proc = psutil.Process(claim["pid"])
        if abs(proc.create_time() - claim["created"]) > 1e-3:
            return False
        # macOS 对未回收进程的 cmdline/exe 可能报 AccessDenied；先核内核终态。
        if process_finished(proc):
            return False
        args = proc.cmdline()
        if (os.path.normcase(str(Path(proc.exe()).resolve())) != os.path.normcase(str(Path(claim["exe"]).resolve()))
                or "guardian" not in args or str(work) not in args or member not in args):
            raise Rejected("Live guardian identity differs")
        return not process_finished(proc)
    except psutil.NoSuchProcess:
        return False
    except psutil.Error as exc:
        # 身份查询期间也可能退出。仅确认原进程已消失/终止才继续，活进程不可读仍 HOLD。
        try:
            observed = psutil.Process(claim["pid"])
            if (abs(observed.create_time() - claim["created"]) > 1e-3
                    or process_finished(observed)):
                return False
        except psutil.NoSuchProcess:
            return False
        except psutil.Error:
            pass
        raise Rejected("Guardian process is unreadable: " + str(exc)) from exc


def number(value, name, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise Rejected("Invalid " + name)
    if value < 0 or (not zero and value == 0):
        raise Rejected("Invalid " + name)
    return value


def source_inventory(source, members, provenance_only):
    contract, pin = document(source / "contracts/RUN_CONTRACT.json")
    references = {"contracts/RUN_CONTRACT.json": pin["sha256"]}
    jobs = {}
    for member in members:
        src = source / "models" / member
        job, pin = document(src / "job.json")
        expected = job.get("hashes", {})
        if not expected or "model.inp" not in expected:
            raise Rejected("Missing source input contract")
        inp, _ = snapshot(src / "model.inp")
        if any(name.encode("ascii").lower() in inp.lower() for name in provenance_only):
            raise Rejected("A provenance-only file is referenced by model.inp")
        names = set(expected) | set(OUTPUTS) | {"job.json", "engine_receipt.json"}
        for name in names:
            raw, part = snapshot(src / safe_name(name))
            if name in expected and part["sha256"] != expected[name]:
                raise Rejected("Source input differs from job.json: " + member + "/" + name)
            references["models/" + member + "/" + name] = part["sha256"]
        cap = number(job.get("cap_seconds", contract.get("per_model_seconds")), "member cap")
        if cap > number(contract["per_model_seconds"], "contract cap"):
            raise Rejected("Member cap exceeds its original contract")
        jobs[member] = {"inputs": {n: h for n, h in expected.items() if n not in provenance_only},
                        "cap_seconds": cap}
    return references, jobs, contract


def make_binding(plan_path, synthetic):
    plan_path = Path(plan_path).resolve()
    plan = load(plan_path)
    if plan.get("schema") != SCHEMA or not str(plan.get("authorization", "")).strip():
        raise Rejected("A versioned plan with an explicit authorization description is required")
    source = Path(plan["source"]).expanduser().resolve()
    engine = Path(plan["engine"]).expanduser().resolve()
    if not Path(plan["source"]).is_absolute() or not Path(plan["engine"]).is_absolute():
        raise Rejected("Source and engine paths must be absolute")
    if digest(engine) != plan["engine_sha256"]:
        raise Rejected("Engine bytes differ from the plan")
    if not synthetic and os.name != "nt":
        raise Rejected("Real Mplus execution is Windows-only")
    if synthetic and load(source / "TEST_FIXTURE.json") != {"synthetic": True}:
        raise Rejected("Synthetic mode requires an explicit synthetic source fixture")
    contract = load(source / "contracts/RUN_CONTRACT.json")
    primary = [safe_name(x) for x in contract["primary_sequence"]]
    members = [safe_name(x) for x in plan.get("members", primary)]
    if not members or len(members) != len(set(members)) or not set(members) <= set(primary):
        raise Rejected("Empty, duplicate or out-of-contract members")
    provenance = sorted({safe_name(x) for x in plan.get("provenance_only", [])})
    if any(not x.endswith(".json") for x in provenance):
        raise Rejected("Provenance exceptions must name JSON metadata")
    references, jobs, contract = source_inventory(source, members, provenance)
    budget = plan["budget"]
    for key in ("max_engine_starts", "max_total_engine_seconds", "prior_engine_starts", "prior_engine_seconds"):
        number(budget[key], key, zero=key.startswith("prior_"))
    if any(not isinstance(budget[k], int) or isinstance(budget[k], bool)
           for k in ("max_engine_starts", "prior_engine_starts")):
        raise Rejected("Call budgets must be integers")
    if (budget["max_engine_starts"] > contract["max_mplus_calls"]
            or budget["max_total_engine_seconds"] > contract["total_engine_seconds"]):
        raise Rejected("Plan budget exceeds its original source contract")
    if not synthetic and contract.get("executable_sha256") != plan["engine_sha256"]:
        raise Rejected("Engine hash differs from the original source contract")
    # 不由恢复推断已用量为零；四个预算字段全部由有来源的计划明确给出。
    if (budget["prior_engine_starts"] > budget["max_engine_starts"]
            or budget["prior_engine_seconds"] > budget["max_total_engine_seconds"]):
        raise Rejected("Prior budget use already exceeds the plan")
    poll = number(plan.get("poll_seconds", 1.0), "poll interval")
    if poll < 0.02 or poll > 30:
        raise Rejected("Poll interval is outside the supported range")
    binding = {"schema": SCHEMA, "authorization": plan["authorization"], "source": str(source),
               "engine": str(engine), "engine_sha256": plan["engine_sha256"], "members": members,
               "provenance_only": provenance, "references": references, "jobs": jobs,
               "budget": budget, "poll_seconds": poll, "host": host(), "synthetic": synthetic,
               "complete_original_family": members == primary,
               "resource_contract": {k: contract[k] for k in
                   ("minimum_available_gib", "minimum_commit_available_gib", "max_cpu_percent", "resource_wait_seconds")},
               "code": {n: digest(HERE / n) for n in
                   ("durable_mplus_worker.py", "orphan_output_guard.py", "verify_saved_batch.py")}}
    if synthetic:
        script = Path(plan["synthetic_script"]).resolve()
        binding.update(synthetic_script=str(script), synthetic_script_sha256=digest(script))
    return binding


def validate_binding(binding):
    if binding["host"] != host():
        raise Rejected("Execution work belongs to another host")
    if not binding["synthetic"] and os.name != "nt":
        raise Rejected("Real Mplus execution is Windows-only")
    if digest(binding["engine"]) != binding["engine_sha256"]:
        raise Rejected("Engine changed since the batch was bound")
    for name, pin in binding["code"].items():
        if digest(HERE / name) != pin:
            raise Rejected("Worker code changed; preserve the original pinned executable")
    if binding["synthetic"] and digest(binding["synthetic_script"]) != binding["synthetic_script_sha256"]:
        raise Rejected("Synthetic fixture changed")
    actual, jobs, _ = source_inventory(Path(binding["source"]), binding["members"], binding["provenance_only"])
    if actual != binding["references"] or jobs != binding["jobs"]:
        raise Rejected("Original source or output changed since the batch was bound")


def memory_state():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (k, ctypes.c_ulonglong) for k in ("total", "avail", "commit_limit", "commit_avail", "virtual", "virtual_avail", "extended")]
    value = Memory()
    value.length = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise OSError("GlobalMemoryStatusEx failed")
    return {"available_gib": value.avail / 2**30, "commit_available_gib": value.commit_avail / 2**30}


@contextmanager
def awake():
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        yield
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def detached_args():
    return {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}


def stop_owned(proc, created, *, reap_root=False):
    """只停止本次新建且创建时间一致的引擎树，不按程序名批量结束进程。"""
    try:
        root = psutil.Process(proc.pid)
        if abs(root.create_time() - created) > 1e-3:
            raise Rejected("PID was reused; refusing termination")
        children = root.children(recursive=True)
        # psutil.Process.kill 自带 PID 重用检查；这些对象来自原根的实际子进程链。
        for child in children + [root]:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        # Popen 必须自己 wait 原根，避免 psutil 提前消费其真实非零退出状态。
        psutil.wait_procs(children + ([root] if reap_root else []), timeout=10)
    except psutil.NoSuchProcess:
        pass


def guardian(work, member):
    work = Path(work).resolve()
    member = safe_name(member)
    binding = load_binding(work)
    validate_binding(binding)
    attempt = work / "attempts" / member
    dest = work / "models" / member
    intent = load(attempt / "INTENT.json")
    if intent["member"] != member or intent["inputs"] != binding["jobs"][member]["inputs"]:
        raise Rejected("Engine intent does not match the bound input contract")
    with file_lock(attempt / ".guardian.lock"), awake():
        if (attempt / "CLAIM.json").exists():
            return 75  # 永久领取记录不是过期锁；它保证同一意图不会第二次启动 Mplus。
        with recovery_lock(work):
            for name, pin in intent["inputs"].items():
                if digest(dest / name) != pin:
                    raise Rejected("Staged input changed before engine launch")
            if any((dest / name).exists() for name in OUTPUTS) or (dest / "ENGINE_STARTED.json").exists():
                raise Rejected("A fresh engine may not overwrite existing output")
            claim = {**process_record(), "attempt_id": intent["attempt_id"], "member": member}
            atomic_json(attempt / "CLAIM.json", claim, new=True)
        proc = None
        created = None
        started = time.monotonic()
        state, exit_code, started_engine = "LAUNCH_FAILED", None, False
        try:
            if (work / "STOP").exists():
                state = "STOPPED_BEFORE_ENGINE"
            else:
                command = [binding["engine"]]
                if binding["synthetic"]:
                    command += ["-X", "utf8", binding["synthetic_script"]]
                command.append("model.inp")
                with (attempt / "engine.stdout.log").open("xb") as stdout, (attempt / "engine.stderr.log").open("xb") as stderr:
                    proc = subprocess.Popen(command, cwd=dest, stdout=stdout, stderr=stderr, **detached_args())
                started_engine = True
                created = psutil.Process(proc.pid).create_time()
                marker = {"pid": proc.pid, "created": created, "at": now(), "inputs": intent["inputs"],
                          "attempt_id": intent["attempt_id"], "engine_sha256": binding["engine_sha256"],
                          "host": host(), "boot_time": psutil.boot_time(), "supervisor": claim}
                with recovery_lock(work):
                    atomic_json(dest / "ENGINE_STARTED.json", marker, new=True)
                state = "EXITED"
                while proc.poll() is None:
                    elapsed = time.monotonic() - started
                    atomic_json(attempt / "PROGRESS.json", {"at": now(), "stage": "ENGINE_RUNNING",
                        "member": member, "attempt_id": intent["attempt_id"], "elapsed_seconds": elapsed,
                        "cap_seconds": intent["cap_seconds"], "engine_pid": proc.pid})
                    if elapsed >= intent["cap_seconds"] or (work / "STOP").exists():
                        state = "TIMEOUT" if elapsed >= intent["cap_seconds"] else "STOPPED"
                        stop_owned(proc, created)
                        break
                    time.sleep(binding["poll_seconds"])
                exit_code = proc.wait(timeout=15)
        except BaseException as exc:
            state = "SUPERVISOR_ERROR"
            if proc is not None and proc.poll() is None and created is not None:
                stop_owned(proc, created)
                exit_code = proc.wait(timeout=15)
            error = repr(exc)
        else:
            error = None
        receipt = {"schema": "mplus-durable-engine-exit/1", "at": now(), "member": member,
                   "attempt_id": intent["attempt_id"], "engine_started": started_engine,
                   "engine_exit_code": exit_code, "engine_state": state,
                   "wall_seconds": time.monotonic() - started, "cap_seconds": intent["cap_seconds"],
                   "inputs": intent["inputs"], "engine_sha256": binding["engine_sha256"],
                   "guardian": claim, "synthetic": binding["synthetic"], "error": error}
        with recovery_lock(work):
            atomic_json(attempt / "ENGINE_EXIT.json", receipt, new=True)
        return 0 if exit_code == 0 and state == "EXITED" else 2


class Worker:
    def __init__(self, work, plan=None, synthetic=False):
        requested = Path(work).expanduser().absolute()
        if requested.is_symlink():
            raise Rejected("Work directory is a symlink")
        self.work = requested.resolve()
        self.work.mkdir(parents=True, exist_ok=True)
        self.plan, self.synthetic = plan, synthetic

    def status(self, stage, member=None, **extra):
        value = {"at": now(), "stage": stage, "member": member, "worker": process_record(), **extra}
        atomic_json(self.work / "STATUS.json", value)
        print(json.dumps(value, ensure_ascii=False), flush=True)

    def initialize(self):
        binding_path = self.work / "BATCH_BINDING.json"
        if binding_path.exists():
            self.binding = load_binding(self.work)
            if self.plan and make_binding(self.plan, self.synthetic) != self.binding:
                raise Rejected("Resume plan changed; original binding is preserved")
        else:
            present = {p.name for p in self.work.iterdir()} - {".batch-worker.lock"}
            if present or self.plan is None:
                raise Rejected("A new plan requires an empty work directory; legacy work is never inferred")
            self.binding = make_binding(self.plan, self.synthetic)
            source = Path(self.binding["source"])
            if source == self.work or source in self.work.parents or self.work in source.parents:
                raise Rejected("Source and new work must be independent directory trees")
            atomic_json(binding_path, self.binding, new=True)
            atomic_json(self.work / "BATCH_BINDING_SHA256.json", {"sha256": digest(binding_path)}, new=True)
        if self.binding["synthetic"] != self.synthetic:
            raise Rejected("Synthetic mode must be explicit on every invocation")
        validate_binding(self.binding)
        for name in ("models", "attempts"):
            if (self.work / name).is_symlink():
                raise Rejected("Execution subdirectory is a symlink")
            (self.work / name).mkdir(exist_ok=True)

    def budget(self):
        budget = self.binding["budget"]
        calls, seconds, unknown = budget["prior_engine_starts"], budget["prior_engine_seconds"], []
        actual_new_starts = 0
        for folder in (self.work / "attempts").iterdir():
            if folder.is_symlink() or folder.name not in self.binding["members"]:
                raise Rejected("Unexpected attempt directory")
            intent_path = folder / "INTENT.json"
            if not intent_path.exists():
                if any(folder.iterdir()):
                    raise Rejected("Attempt lacks its permanent budget intent")
                continue
            intent = load(intent_path)
            if intent["member"] != folder.name or intent["inputs"] != self.binding["jobs"][folder.name]["inputs"]:
                raise Rejected("Budget intent differs from the bound member")
            if intent["cap_seconds"] != self.binding["jobs"][folder.name]["cap_seconds"]:
                raise Rejected("Budget cap changed")
            calls += 1  # 保留已保留的调用，不因监督器失败或主进程重启返还。
            if (folder / "ENGINE_EXIT.json").exists():
                receipt = load(folder / "ENGINE_EXIT.json")
                if receipt["attempt_id"] != intent["attempt_id"] or receipt["inputs"] != intent["inputs"]:
                    raise Rejected("Engine receipt does not match its budget intent")
                seconds += number(receipt["wall_seconds"], "observed engine duration", zero=True)
                actual_new_starts += int(receipt["engine_started"])
            else:
                seconds += intent["cap_seconds"]
                unknown.append(folder.name)
                actual_new_starts += int((self.work / "models" / folder.name / "ENGINE_STARTED.json").exists())
        return {"reserved_calls": calls, "charged_or_reserved_seconds": seconds,
                "unsettled_members": unknown, "recorded_new_engine_starts": actual_new_starts,
                "max_engine_starts": budget["max_engine_starts"],
                "max_total_engine_seconds": budget["max_total_engine_seconds"]}

    def prepare(self, member):
        dest = self.work / "models" / member
        folder = self.work / "attempts" / member
        intent_path = folder / "INTENT.json"
        if dest.is_symlink() or folder.is_symlink():
            raise Rejected("Member directory is a symlink")
        if intent_path.exists():
            return load(intent_path)
        used = self.budget()
        cap = self.binding["jobs"][member]["cap_seconds"]
        if used["unsettled_members"]:
            raise Rejected("A previous invocation has no settled budget; no next engine is authorized")
        if (used["reserved_calls"] + 1 > used["max_engine_starts"]
                or used["charged_or_reserved_seconds"] + cap > used["max_total_engine_seconds"]):
            raise Rejected("Original cumulative budget exhausted")
        inputs = self.binding["jobs"][member]["inputs"]
        with recovery_lock(self.work):
            dest.mkdir(exist_ok=True)
            if any(p.name not in inputs for p in dest.iterdir()):
                raise Rejected("Unclaimed member has prior output; no overwrite or automatic rerun")
            for name, pin in inputs.items():
                raw, actual = snapshot(Path(self.binding["source"]) / "models" / member / name)
                if actual["sha256"] != pin:
                    raise Rejected("Source changed while staging")
                if (dest / name).exists():
                    if (dest / name).is_symlink():
                        raise Rejected("Staged input is a symlink")
                    if digest(dest / name) != pin:
                        raise Rejected("Partial staged input changed")
                else:
                    with (dest / name).open("xb") as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
            folder.mkdir(exist_ok=True)
            intent = {"schema": "mplus-durable-engine-intent/1", "at": now(),
                      "attempt_id": uuid.uuid4().hex, "member": member, "inputs": inputs,
                      "cap_seconds": cap, "host": host(),
                      "admission_deadline": time.time() + self.binding["resource_contract"]["resource_wait_seconds"]}
            atomic_json(intent_path, intent, new=True)
        return intent

    def admit(self, member, intent):
        if self.binding["synthetic"]:
            return
        required = self.binding["resource_contract"]
        while True:
            if time.time() > intent["admission_deadline"] or (self.work / "STOP").exists():
                raise Rejected("Original admission wait expired or STOP requested")
            mem = memory_state()
            cpu = psutil.cpu_percent(0.2)
            others = [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "mplus.exe"]
            if (not others and mem["available_gib"] >= required["minimum_available_gib"]
                    and mem["commit_available_gib"] >= required["minimum_commit_available_gib"]
                    and cpu <= required["max_cpu_percent"]):
                return
            if time.time() > intent["admission_deadline"] or (self.work / "STOP").exists():
                raise Rejected("Original admission wait expired or STOP requested")
            self.status("ADMISSION_WAIT", member, **mem, cpu_percent=cpu, other_mplus=others)
            time.sleep(min(5, self.binding["poll_seconds"]))

    def collect_member(self, member, intent):
        folder = self.work / "attempts" / member
        dest = self.work / "models" / member
        options = {"provenance_only": self.binding["provenance_only"]}
        marker_path = dest / "ENGINE_STARTED.json"
        if marker_path.exists():
            marker = load(marker_path)
            if (marker.get("host") != host() or marker.get("attempt_id") != intent["attempt_id"]
                    or marker.get("engine_sha256") != self.binding["engine_sha256"]):
                raise Rejected("Engine marker does not belong to this attempt")
        exit_path = folder / "ENGINE_EXIT.json"
        receipt = None
        if exit_path.exists():
            receipt = load(exit_path)
            if (receipt["attempt_id"] != intent["attempt_id"] or receipt["inputs"] != intent["inputs"]
                    or receipt["engine_sha256"] != self.binding["engine_sha256"]
                    or receipt["cap_seconds"] != intent["cap_seconds"]
                    or receipt["engine_exit_code"] != 0 or receipt["engine_state"] != "EXITED"):
                raise Rejected("Engine did not terminate successfully: " + str(receipt.get("engine_state")))
            if (dest / "RESULT.json").exists() and load(dest / "RESULT.json").get("engine_receipt_sha256") != digest(exit_path):
                raise Rejected("Engine exit receipt changed after result acceptance")
        checked = assess_member(self.binding["source"], self.work, member, self.binding["engine"], **options)
        if checked["decision"] == "WAIT_FOR_ORIGINAL_ENGINE":
            if time.time() > marker["created"] + intent["cap_seconds"]:
                # 仅原预算到期才终止已严格绑定的本批原引擎；不是因为重启便收掉孤儿。
                stop_owned(psutil.Process(marker["pid"]), marker["created"], reap_root=True)
                with recovery_lock(self.work):
                    atomic_json(folder / "RECOVERY_BUDGET_STOP.json", {"at": now(),
                        "attempt_id": intent["attempt_id"], "engine_exit_code": None,
                        "original_cap_seconds": intent["cap_seconds"], "marker": marker}, new=True)
                raise Rejected("Original engine budget expired after supervisor loss; exit/time remain unconfirmed")
            return None
        if checked["decision"] not in ("ADOPTABLE_SAVED_OUTPUTS", "REUSE_VERIFIED_RESULT"):
            raise Rejected("Saved output is not adoptable: " + checked.get("reason", checked["decision"]))
        if receipt is None:
            if checked["decision"] == "REUSE_VERIFIED_RESULT":
                raise Rejected("Verified output has lost its original execution receipt; budget cannot be inferred")
            adopted = adopt_member(self.binding["source"], self.work, member, self.binding["engine"], **options)
            if adopted["decision"] not in ("OUTPUTS_ADOPTED", "ADOPTION_ALREADY_RECORDED"):
                raise Rejected("Orphan output adoption did not complete: " + adopted["decision"])
            self.status("OUTPUTS_ADOPTED_BUDGET_UNKNOWN", member, adoption=adopted.get("adoption"),
                        engine_exit_code=None, remaining_budget=None)
            raise Rejected("Complete orphan outputs adopted separately; original exit/time budget remains unknown")
        if checked["decision"] != "REUSE_VERIFIED_RESULT":
            result = {"member": member, "at": now(), "engine_exit_code": 0, "engine_state": "EXITED",
                      "status": "PASS_NUMERIC", "wall_seconds": receipt["wall_seconds"],
                      "probe_cap_seconds": intent["cap_seconds"], "inputs": intent["inputs"],
                      "removed_input_copies": [], "synthetic": self.binding["synthetic"],
                      "attempt_id": intent["attempt_id"], "engine_receipt_sha256": digest(exit_path),
                      "compare": {name: {"sha_new": row["saved_sha256"]} for name, row in checked["comparison"].items()}}
            with recovery_lock(self.work):
                verify_pins(checked["pins"])
                atomic_json(dest / "RESULT.json", result, new=True)
        verified = verify_member(Path(self.binding["source"]), self.work, member, 1e-6, set(self.binding["provenance_only"]))
        verify_pins(verified["pins"])
        return verified

    def run_member(self, member):
        validate_binding(self.binding)
        intent = self.prepare(member)
        folder = self.work / "attempts" / member
        claim_path = folder / "CLAIM.json"
        if not claim_path.exists():
            self.admit(member, intent)
            # 可能迟到的旧监督器也必须先原子领取同一永久 CLAIM；不能两次启动引擎。
            attempt_id = uuid.uuid4().hex
            atomic_json(folder / ("SUPERVISOR_LAUNCH_" + attempt_id + ".json"),
                        {"at": now(), "attempt_id": intent["attempt_id"], "worker": process_record()}, new=True)
            command = [sys.executable, "-B", str(HERE / "durable_mplus_worker.py"), "guardian",
                       "--work", str(self.work), "--member", member]
            with (folder / ("supervisor_" + attempt_id + ".log")).open("xb") as stream:
                proc = subprocess.Popen(command, cwd=self.work, stdout=stream, stderr=subprocess.STDOUT, **detached_args())
            # 回收本 worker 派生监督器的退出状态；daemon 线程不随主进程退出终止监督器。
            threading.Thread(target=proc.wait, name="guardian-reaper", daemon=True).start()
        deadline = time.monotonic() + 30
        last_status = 0
        while True:
            if claim_path.exists():
                claim = load(claim_path)
                if claim["attempt_id"] != intent["attempt_id"]:
                    raise Rejected("Guardian claim changed")
                if not live_guardian(claim, self.work, member):
                    value = self.collect_member(member, intent)
                    if value is not None:
                        return value
            elif time.monotonic() > deadline:
                raise Rejected("Guardian claim not observed; preserve original intent and inspect its launch log")
            if time.monotonic() - last_status >= 2:
                last_status = time.monotonic()
                self.status("OBSERVING_ORIGINAL_ENGINE", member, attempt_id=intent["attempt_id"])
            time.sleep(self.binding["poll_seconds"])

    def run(self):
        if not (self.work / "BATCH_BINDING.json").exists():
            present = {p.name for p in self.work.iterdir()} - {".batch-worker.lock"}
            if present:
                print(json.dumps({"stage": "REFUSED", "reason": "Legacy or unknown work directory; no files changed"}))
                return 2
        with file_lock(self.work / ".batch-worker.lock"), awake():
            results = []
            try:
                self.initialize()
                self.status("WORKER_RUNNING", total=len(self.binding["members"]), synthetic=self.binding["synthetic"])
                for member in self.binding["members"]:
                    if (self.work / "STOP").exists():
                        raise Rejected("STOP requested; no new member launched")
                    results.append(self.run_member(member))
                    self.status("MEMBER_VERIFIED", member, done=len(results), total=len(self.binding["members"]))
                used = self.budget()
                if (used["unsettled_members"] or used["charged_or_reserved_seconds"] > used["max_total_engine_seconds"]
                        or used["reserved_calls"] > used["max_engine_starts"]):
                    raise Rejected("Cumulative engine budget is unsettled or exceeded")
                self.status("BATCH_VERIFIED", done=len(results), total=len(results), budget=used,
                            complete_original_family=self.binding["complete_original_family"], synthetic=self.binding["synthetic"])
                return 0
            except (Rejected, OSError, ValueError, KeyError, TypeError) as exc:
                self.status("HOLD", reason=str(exc), verified_members=len(results))
                return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    run = modes.add_parser("run")
    run.add_argument("--work", type=Path, required=True)
    run.add_argument("--plan", type=Path)
    run.add_argument("--synthetic-test", action="store_true")
    child = modes.add_parser("guardian")
    child.add_argument("--work", type=Path, required=True)
    child.add_argument("--member", required=True)
    args = parser.parse_args(argv)
    try:
        return guardian(args.work, args.member) if args.mode == "guardian" else Worker(args.work, args.plan, args.synthetic_test).run()
    except (Rejected, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"stage": "REFUSED", "reason": str(exc)}, ensure_ascii=False), flush=True)
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
