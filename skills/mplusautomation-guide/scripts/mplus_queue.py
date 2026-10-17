"""Durable local Mplus queue. Statistical work is performed by ClaudeR R workers."""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time

import psutil
_ownership_spec = importlib.util.spec_from_file_location('queue_ownership', Path(__file__).with_name('process_ownership.py'))
_ownership = importlib.util.module_from_spec(_ownership_spec)
_ownership_spec.loader.exec_module(_ownership)
verified_descendants = _ownership.verified_descendants


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_replace(source, target, timeout=5.0):
    """Flush before publication; tolerate bounded Windows reader sharing locks."""
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve() or source.parent.resolve() != target.parent.resolve():
        raise ValueError("Atomic publication requires distinct files in one directory")
    with source.open("r+b") as handle:
        os.fsync(handle.fileno())
    deadline = time.monotonic() + timeout
    delay = .05
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(delay, remaining))
            delay = min(.5, delay * 2)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    atomic_replace(temporary, path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def _is_wsl():
    """Return True when the queue is running inside WSL.

    ``psutil.virtual_memory()`` reports the WSL VM's view in this case.  That
    view can show several GiB available while Windows has less than one GiB of
    physical headroom, which is unsafe for admitting Mplus.
    """
    if os.name == "nt":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False


def _read_windows_profile(path, max_age=300):
    path = Path(path).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    stamp = payload.get("generated_at")
    if not isinstance(stamp, str):
        raise ValueError("Windows memory profile has no generated_at")
    generated = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=dt.timezone.utc)
    age = (dt.datetime.now(dt.timezone.utc) - generated).total_seconds()
    if age < -5:
        raise ValueError("Windows memory profile is future-dated")
    if age > max_age:
        raise ValueError(f"Windows memory profile is stale ({age:.1f}s > {max_age:.1f}s)")
    system = payload.get("profile", {}).get("system", {})
    required = ("free_phys_gib", "total_phys_gib", "free_virtual_gib", "commit_limit_gib", "committed_gib")
    if any(not isinstance(system.get(key), (int, float)) or not math.isfinite(system[key]) or system[key] < 0 for key in required):
        raise ValueError("Windows memory profile is missing numeric system fields")
    if system["total_phys_gib"] <= 0 or system["commit_limit_gib"] <= 0:
        raise ValueError("Windows memory profile has invalid capacity")
    result = {
        "available_gib": float(system["free_phys_gib"]),
        "total_gib": float(system["total_phys_gib"]),
        "free_virtual_gib": float(system["free_virtual_gib"]),
        "committed_gib": float(system["committed_gib"]),
        "commit_limit_gib": float(system["commit_limit_gib"]),
        # Optional Windows PDH measurements.  An absent field is retained as
        # unknown; it must never be interpreted as zero paging.
        "paging": payload.get("profile", {}).get("paging", {}),
        "profile_age_sec": age,
        "profile_path": str(path),
    }
    cpu = system.get("cpu_percent_samples", [])
    if len(cpu) >= 3 and all(isinstance(x, (int, float)) and math.isfinite(x) and 0 <= x <= 100 for x in cpu):
        result.update(cpu_percent_samples=cpu, cpu_percent=sum(cpu)/len(cpu))
    else:
        result["host_cpu_unverified"] = True
    if isinstance(system.get("disk_free_gib"), (int, float)) and math.isfinite(system["disk_free_gib"]):
        result["disk_free_gib"] = system["disk_free_gib"]
    else:
        result["host_disk_unverified"] = True
    return result


def resource_snapshot(windows_profile=None, max_profile_age_sec=300):
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.cwd().anchor or "/")
    snapshot = dict(at=time.time(), memory_percent=memory.percent,
                    available_gib=memory.available / 2**30, total_gib=memory.total / 2**30,
                    cpu_percent=psutil.cpu_percent(interval=0.1), disk_free_gib=disk.free / 2**30,
                    source="psutil", host_memory_unverified=False)
    if windows_profile:
        try:
            host = _read_windows_profile(windows_profile, max_profile_age_sec)
            snapshot.update(host, source="windows_profile")
            snapshot["memory_percent"] = 100 * (1 - snapshot["available_gib"] / snapshot["total_gib"])
            snapshot["commit_percent"] = 100 * snapshot["committed_gib"] / snapshot["commit_limit_gib"]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            snapshot.update(source="windows_profile_error", host_memory_unverified=True,
                            resource_error=str(exc), profile_path=str(Path(windows_profile)))
    elif _is_wsl():
        # Never use WSL's optimistic memory view for a new Windows Mplus claim.
        snapshot.update(source="wsl_psutil_unverified", host_memory_unverified=True,
                        resource_error="Windows host memory profile was not supplied")
    elif os.name == 'nt':
        from windows_memory import snapshot as native_memory
        perf = native_memory()['performance_bytes']
        if perf:
            snapshot.update(committed_gib=perf['CommitTotal']/2**30,
                            commit_limit_gib=perf['CommitLimit']/2**30,
                            free_virtual_gib=(perf['CommitLimit']-perf['CommitTotal'])/2**30)
    return snapshot


def complete_input_manifest(payload):
    """Resolve MplusAutomation's DATA FILE and TYPE=IMPUTATION list format."""
    inp = Path(payload["input"]).resolve()
    files = {str(inp): dict(path=str(inp), sha256=payload["input_sha256"])}
    for item in payload.get("input_files", []):
        files[str(Path(item["path"]).resolve())] = item
    text = re.sub(r"![^\n]*", "", inp.read_text(encoding="utf-8-sig"))
    section = re.search(r"(?:^|\n)\s*DATA\s*:(.*?)(?=^\s*[A-Z][A-Z0-9 _]*\s*:|\Z)", text, re.I | re.M | re.S)
    if section:
        match = re.search(r"\bFILE\s*(?:=|IS)\s*([^;]+);", section[1], re.I)
        if match:
            name = match[1].strip().strip('\"\'')
            if "*" in name or "?" in name:
                raise ValueError("Expand DATA wildcards into a reviewed input manifest first")
            data = (inp.parent / name).resolve()
            paths = [data]
            if re.search(r"\bTYPE\s*(?:=|IS)\s*IMPUTATION\b", section[1], re.I):
                names = [x.strip().strip('\"\'') for x in data.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
                if not names:
                    raise ValueError("Empty imputation file list")
                paths += [(inp.parent / x).resolve() for x in names]
            for path in paths:
                if inp.parent not in path.parents:
                    raise ValueError("DATA input leaves the isolated model directory: " + str(path))
                if str(path) not in files:
                    files[str(path)] = dict(path=str(path), sha256=sha256(path))
    return list(files.values())


def content_key(payload):
    signature = sorted((Path(x["path"]).name.lower(), x["sha256"]) for x in payload["input_files"])
    return hashlib.sha256(json.dumps(signature).encode("utf-8")).hexdigest()


DEFAULT_POLICY = dict(memory_hold_percent=90, memory_resume_percent=85,
                      reserve_gib=1.5, cpu_hold_percent=90, cpu_resume_percent=75,
                      disk_reserve_gib=10, processor_budget=12)


def admission_reason(snapshot, running, candidate, limit, policy=None):
    policy = {**DEFAULT_POLICY, **(policy or {})}
    if snapshot.get("host_memory_unverified"):
        return "host_memory_unverified"
    if snapshot.get("host_cpu_unverified"):
        return "host_cpu_unverified"
    if snapshot.get("host_disk_unverified"):
        return "host_disk_unverified"
    if len(running) >= limit:
        return "parallel_limit"
    # 作业类别限制只控制准入，不改统计输入或终止已运行的模型。
    category = candidate.get("execution_class")
    class_limit = policy.get("max_running_by_class", {}).get(category)
    if class_limit is not None and sum(x.get("execution_class") == category for x in running) >= class_limit:
        return "class_limit:" + category
    if snapshot["memory_percent"] >= policy["memory_hold_percent"] or snapshot["available_gib"] < policy["reserve_gib"]:
        return "memory_hold"
    if snapshot["cpu_percent"] >= policy["cpu_hold_percent"]:
        return "cpu_hold"
    if snapshot["disk_free_gib"] < policy["disk_reserve_gib"]:
        return "disk_hold"
    processors = max(1, int(candidate.get("processors", 1)))
    if sum(max(1, int(x.get("processors", 1))) for x in running) + processors > policy["processor_budget"]:
        return "processor_budget"
    memory = float(candidate.get("memory_gib", 0.5))
    # Conservative reservation also covers workers claimed before Mplus allocates RAM.
    reserved = sum(float(x.get("memory_gib", 0.5)) for x in running)
    commit_reserve = policy.get('commit_reserve_gib')
    if commit_reserve is not None:
        headroom = snapshot.get('free_virtual_gib')
        if headroom is None:
            return 'host_commit_unverified'
        if headroom - memory - reserved < commit_reserve:
            return 'predicted_commit'
    remaining = snapshot["available_gib"] - memory - reserved
    if remaining < policy["reserve_gib"] or 100 * (1 - remaining / snapshot["total_gib"]) >= policy["memory_hold_percent"]:
        return "predicted_memory"
    return None


def inspect_output(path, savedata_contract=None):
    path = Path(path)
    if not path.exists():
        return dict(estimation_ok=False, savedata_ok=False, status="FAIL", reasons=["missing_output"])
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    errors = [x.strip() for x in lines if re.search(r"\*\*\* ERROR|DID NOT TERMINATE NORMALLY|FAILED TO CONVERGE|NO CONVERGENCE", x)]
    saved_errors = [x for x in errors if "ERROR in SAVEDATA command" in x]
    estimation_errors = [x for x in errors if x not in saved_errors]
    warnings = [x.strip() for x in lines if re.search(r"\*\*\* WARNING|NOT POSITIVE DEFINITE|COULD NOT BE COMPUTED|ILL-CONDITIONED", x)]
    def count(label):
        m = re.search(r"^\s*" + label + r"\s+(\d+)\s*$", text, re.M)
        return int(m[1]) if m else None
    requested, completed = count("Requested"), count("Completed")
    params = re.findall(r"^\s*\S+\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$", text.split("MODEL RESULTS", 1)[-1], re.M) if "MODEL RESULTS" in text else []
    imputation_only = bool(re.search(r"^\s*DATA IMPUTATION\s*:",text,re.M)) and not params
    savedata_ok = not saved_errors
    savedata_files = []
    if imputation_only:
        contract = savedata_contract or {}
        match = re.search(r"\bSAVE\s*=\s*([^;]+);",text.split("DATA IMPUTATION",1)[-1],re.I)
        pattern = contract.get("pattern") or (match[1].strip().strip('\"\'') if match else None)
        safe = pattern and "/" not in pattern and "\\" not in pattern and ".." not in pattern
        numeric_pattern=re.compile(re.escape(pattern).replace(r"\*",r"\d+"),re.I) if safe else None
        data = [p for p in path.parent.iterdir() if numeric_pattern.fullmatch(p.name)] if safe else []
        counts=[]
        for file in data:
            with file.open(encoding="utf-8") as f:
                counts.append(sum(1 for line in f if line.strip()))
            savedata_files.append(dict(path=str(file), rows=counts[-1], sha256=sha256(file)))
        expected_count=contract.get("expected_count",requested)
        savedata_ok = bool(data) and len(data)==expected_count and len(set(counts))==1 and counts[0]>0
        if contract.get("rows") is not None:
            savedata_ok = savedata_ok and all(n==contract["rows"] for n in counts)
    elif savedata_contract and savedata_contract.get("pattern"):
        pattern = savedata_contract["pattern"]
        safe = "/" not in pattern and "\\" not in pattern and ".." not in pattern
        files = list(path.parent.glob(pattern)) if safe else []
        for file in files:
            with file.open(encoding="utf-8") as f:
                rows = sum(1 for line in f if line.strip())
            savedata_files.append(dict(path=str(file), rows=rows, sha256=sha256(file)))
        savedata_ok = savedata_ok and bool(files) and all(x["rows"] > 0 for x in savedata_files)
        if savedata_contract.get("rows") is not None:
            savedata_ok = savedata_ok and all(x["rows"] == savedata_contract["rows"] for x in savedata_files)
        if savedata_contract.get("expected_count") is not None:
            savedata_ok = savedata_ok and len(files) == savedata_contract["expected_count"]
    replicated = requested is not None and requested > 0 and requested == completed
    normal = "THE MODEL ESTIMATION TERMINATED NORMALLY" in text
    valid = not estimation_errors and (requested is None or replicated) and (savedata_ok and replicated if imputation_only else bool(params) and (normal or replicated))
    reasons = list(errors)
    if requested is not None and not replicated:
        reasons.append("incomplete_replications")
    if not valid and not reasons:
        reasons.append("estimation_not_verified")
    return dict(estimation_ok=valid, savedata_ok=savedata_ok,
                status="FAIL" if not valid or not savedata_ok else "REVIEW" if warnings else "PASS",
                requested=requested, completed=completed, parameter_rows=len(params),
                reasons=reasons, warnings=warnings, savedata_files=savedata_files, output=str(path), sha256=sha256(path))


class Queue:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "queue.sqlite", timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, payload TEXT NOT NULL,
          status TEXT NOT NULL, worker TEXT, created TEXT, started TEXT, finished TEXT, result TEXT);
        CREATE TABLE IF NOT EXISTS workers(id TEXT PRIMARY KEY, pid INTEGER, created REAL, heartbeat REAL, task TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY, at TEXT, kind TEXT, payload TEXT);
        """)
        for key, value in dict(enabled=False, limit=1, cap=3, healthy=0, last_sample=0, producers_done=False).items():
            self.db.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (key, json.dumps(value)))
        config = self.root / "config.json"
        settings = json.loads(config.read_text(encoding="utf-8-sig")) if config.exists() else {}
        self.policy = {**DEFAULT_POLICY, **settings.get("resource_policy", {})}
        self.windows_memory_profile = settings.get("windows_memory_profile")
        if self.windows_memory_profile:
            profile = Path(self.windows_memory_profile)
            if not profile.is_absolute():
                profile = self.root / profile
            self.windows_memory_profile = str(profile)
        self.profile_max_age_sec = float(self.policy.get("windows_profile_max_age_sec", 300))
        self.producer_state_files = settings.get("producer_state_files", [])
        self.mplus_command = settings.get("mplus")
        # 可选范围门控：同名历史成功输出只表示候选资格，不证明数值复现。
        self.success_policy = settings.get("historical_success_policy")
        self.success_names = None
        if self.success_policy is not None:
            try:
                manifest = Path(self.success_policy["manifest"])
                if sha256(manifest) != self.success_policy["sha256"]:
                    raise ValueError("Historical-success manifest changed")
                names = json.loads(manifest.read_text(encoding="utf-8"))["allowed_output_names"]
                if not isinstance(names, list) or any(not isinstance(n, str) or Path(n).name != n or not n.lower().endswith('.out') for n in names):
                    raise ValueError("Invalid historical-success output names")
                self.success_names = {n.lower() for n in names}
            except BaseException:
                self.db.close()
                raise

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def get(self, key):
        return json.loads(self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()[0])

    def set(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, json.dumps(value)))

    def event(self, kind, payload):
        self.db.execute("INSERT INTO events(at,kind,payload) VALUES(?,?,?)", (utc(), kind, json.dumps(payload)))

    def enqueue(self, payload, imported=False):
        payload = dict(payload)
        for key in ("id", "fingerprint", "input", "output", "script"):
            if not payload.get(key):
                raise ValueError("Missing " + key)
        for key in ("input", "output"):
            file = Path(payload[key]).resolve()
            if self.root not in file.parents:
                raise ValueError("Task path outside queue root: " + key)
        payload["input_files"] = complete_input_manifest(payload)
        self.verify_inputs(payload)
        atomic_json(Path(payload["input"]).parent / "input_manifest.json",dict(captured_utc=utc(),files=payload["input_files"]))
        if payload.get("reuse_identical_inputs"):
            payload["content_key"] = content_key(payload)
        with self.transaction():
            prior = self.db.execute("SELECT payload,status FROM tasks WHERE id=?", (payload["id"],)).fetchone()
            if prior:
                if json.loads(prior["payload"])["fingerprint"] != payload["fingerprint"]:
                    raise ValueError("Task ID fingerprint conflict")
                if imported:
                    if prior["status"] == "running":
                        raise ValueError("Cannot import a running task")
                    self.verify_inputs(payload)
                    result = inspect_output(payload["output"], payload.get("savedata_contract"))
                    result["reused"] = True
                    self.publish(payload, result)
                    self.db.execute("UPDATE tasks SET payload=?,status=?,finished=?,result=? WHERE id=?",
                                    (json.dumps(payload), "completed" if result["estimation_ok"] else "failed", utc(), json.dumps(result), payload["id"]))
                    self.event("imported", dict(id=payload["id"], result=result))
                    return result
                return dict(id=payload["id"], status=prior["status"], reused_registration=True)
            if imported:
                self.verify_inputs(payload)
                result = inspect_output(payload["output"], payload.get("savedata_contract"))
                result["reused"] = True
                self.publish(payload, result)
                self.db.execute("INSERT INTO tasks(id,payload,status,created,finished,result) VALUES(?,?,?,?,?,?)",
                                (payload["id"], json.dumps(payload), "completed" if result["estimation_ok"] else "failed", utc(), utc(), json.dumps(result)))
                self.event("imported", dict(id=payload["id"], result=result))
                return result
            if payload.get("content_key"):
                for candidate in self.db.execute("SELECT id,payload,status FROM tasks WHERE status IN ('pending','running','completed','failed') AND json_extract(payload,'$.input_sha256')=? ORDER BY created",(payload["input_sha256"],)):
                    other = json.loads(candidate["payload"])
                    if other.get("reuse_task"):
                        continue
                    try:
                        other["input_files"] = complete_input_manifest(other)
                        self.verify_inputs(other)
                    except (OSError,ValueError):
                        continue
                    if content_key(other) == payload["content_key"]:
                        payload["reuse_task"] = candidate["id"]
                        self.event("reuse_bound",dict(id=payload["id"],source=candidate["id"],content_key=payload["content_key"]))
                        break
            self.db.execute("INSERT INTO tasks(id,payload,status,created) VALUES(?,?,?,?)",
                            (payload["id"], json.dumps(payload), "pending", utc()))
            self.event("enqueued", payload)
        return dict(id=payload["id"], status="pending")

    def verify_inputs(self, payload):
        files = [dict(path=payload["input"], sha256=payload["input_sha256"])] + payload.get("input_files", [])
        files += payload.get("consumed_files", [])
        for file in files:
            if sha256(file["path"]) != file["sha256"]:
                raise ValueError("Input changed before claim: " + file["path"])

    def publish(self, payload, result):
        folder = Path(payload["output"]).parent
        record = dict(payload.get("record") or {})
        record.update(status="estimated" if result.get("estimation_ok") and result.get("status") == "PASS"
                      else "estimated_with_warnings" if result.get("estimation_ok") else "estimation_error",
                      utc=utc(), error=result.get("r_error"), reused_from=payload.get("legacy_source"))
        atomic_json(folder / "validation.json", result)
        atomic_json(folder / "model_status.json", record)

    def dependencies_ready(self, payload):
        for dependency in payload.get("dependencies", []):
            row = self.db.execute("SELECT status,result FROM tasks WHERE id=?", (dependency["id"],)).fetchone()
            if not row:
                return False, "dependency_failed" if self.get("producers_done") else "dependency_pending"
            result = json.loads(row["result"] or "{}")
            if row["status"] in ("failed", "blocked"):
                return False, "dependency_failed"
            if row["status"] == "deferred":
                return False, "dependency_deferred"
            if row["status"] != "completed":
                return False, "dependency_pending"
            if not result.get(dependency.get("requires", "estimation_ok"), False):
                return False, "dependency_failed"
        return True, None

    def waiting_producer_tasks(self):
        """读取显式配置的等待记录；只调整领取顺序，不修改模型或资源门槛。"""
        waiting = set()
        for name in self.producer_state_files:
            try:
                path = (self.root / name).resolve()
                if self.root not in path.parents:
                    continue
                state = json.loads(path.read_text(encoding="utf-8-sig"))
                if not isinstance(state, dict) or state.get("stage") not in ("dependency_wait", "compound_model_wait"):
                    continue
                target = Path(state["waiting_for"]).resolve()
                if self.root not in target.parents:
                    continue
                request = json.loads((target.parent / "request.json").read_text(encoding="utf-8-sig"))
                if not isinstance(request, dict):
                    continue
                row = self.db.execute("SELECT payload,status FROM tasks WHERE id=?", (request["id"],)).fetchone()
                if not row or row["status"] != "pending":
                    continue
                payload = json.loads(row["payload"])
                if (Path(payload["output"]).resolve().parent != target.parent or
                        payload["fingerprint"] != request.get("fingerprint")):
                    continue
                waiting.add(request["id"])
            except (OSError, ValueError, KeyError, TypeError):
                # 正在发布或损坏的状态不能令估计队列退出。
                continue
        # 优先处理尚未完成的前置任务和等价输入的实际执行者。
        todo = list(waiting)
        while todo:
            row = self.db.execute("SELECT payload FROM tasks WHERE id=?", (todo.pop(),)).fetchone()
            payload = json.loads(row[0])
            parents = [d["id"] for d in payload.get("dependencies", [])]
            if payload.get("reuse_task"):
                parents.append(payload["reuse_task"])
            for parent in parents:
                row = self.db.execute("SELECT status FROM tasks WHERE id=?", (parent,)).fetchone()
                if parent not in waiting and row and row[0] == "pending":
                    waiting.add(parent)
                    todo.append(parent)
        return waiting

    def running_for_admission(self, rows):
        """只抵扣有完整归属证据的 Mplus 私有内存；其余维持原预留。"""
        running = []
        for row in rows:
            payload = json.loads(row["payload"])
            booked = dict(payload)
            booked["observed_memory_credit_gib"] = 0.0
            if self.policy.get("credit_observed_running_private") and self.mplus_command and row["worker"]:
                owner = self.db.execute("SELECT pid,created FROM workers WHERE id=?", (row["worker"],)).fetchone()
                try:
                    if owner is not None:
                        process = psutil.Process(owner["pid"])
                        if abs(process.create_time() - owner["created"]) < .1:
                            expected_dir = Path(payload["input"]).parent.resolve()
                            expected_exe = Path(self.mplus_command).resolve()
                            matches = [child for child in verified_descendants(process,names={'mplus.exe'})
                                       if child.name().lower() == "mplus.exe"
                                       and Path(child.exe()).resolve() == expected_exe
                                       and Path(child.cwd()).resolve() == expected_dir
                                       and Path(payload["input"]).name.lower() in
                                       [x.lower() for x in child.cmdline()[1:]]
                                       and time.time() - child.create_time() >= 30]
                            if len(matches) == 1:
                                used = getattr(matches[0].memory_info(), "private", 0) / 2**30
                                credit = min(float(payload.get("memory_gib", .5)), max(0.0, used))
                                booked["memory_gib"] = float(payload.get("memory_gib", .5)) - credit
                                booked["observed_memory_credit_gib"] = credit
                except (psutil.Error, OSError, ValueError, RuntimeError):
                    pass
            running.append(booked)
        return running

    def claim(self, worker, snapshot=None):
        snapshot = snapshot or resource_snapshot(self.windows_memory_profile, self.profile_max_age_sec)
        with self.transaction():
            if not self.get("enabled"):
                return dict(status="waiting", reason="disabled")
            active = self.db.execute("SELECT payload,worker FROM tasks WHERE status='running'").fetchall()
            running = self.running_for_admission(active)
            rows = list(self.db.execute("SELECT * FROM tasks WHERE status='pending'"))
            waiting_producers = self.waiting_producer_tasks()
            rows.sort(key=lambda r: (0 if r["id"] in waiting_producers else 1, json.loads(r["payload"]).get("dispatch_priority", json.loads(r["payload"]).get("priority", 10)), -json.loads(r["payload"]).get("estimated_seconds", 0), r["created"]))
            reasons = set()
            for row in rows:
                payload = json.loads(row["payload"])
                if payload.get("reuse_task"):
                    source = self.db.execute("SELECT * FROM tasks WHERE id=?",(payload["reuse_task"],)).fetchone()
                    if source and source["status"] == "deferred":
                        result = dict(estimation_ok=False, savedata_ok=False, status="DEFERRED",
                                      deferred=True, reason="reuse_source_deferred", source=source["id"])
                        self.publish_deferred(payload, result)
                        self.db.execute("UPDATE tasks SET status='deferred',finished=?,result=? WHERE id=?",
                                        (utc(), json.dumps(result), row["id"]))
                        self.event("reuse_source_deferred", dict(id=row["id"], result=result))
                        continue
                    if not source or source["status"] not in ("completed","failed","blocked"):
                        reasons.add("reuse_pending")
                        continue
                    original=json.loads(source["payload"])
                    original["input_files"]=complete_input_manifest(original)
                    self.verify_inputs(original)
                    self.verify_inputs(payload)
                    if content_key(original)!=payload["content_key"]:
                        raise ValueError("Reuse source content changed")
                    for file in Path(original["output"]).parent.iterdir():
                        if file.is_file() and file.name not in ("request.json","validation.json","model_status.json","input_manifest.json"):
                            shutil.copy2(file,Path(payload["output"]).parent / file.name)
                    result=inspect_output(payload["output"],payload.get("savedata_contract"))
                    result.update(reused=True,reused_task=source["id"])
                    self.publish(payload,result)
                    self.db.execute("UPDATE tasks SET status=?,finished=?,result=? WHERE id=?",
                                    ("completed" if result["estimation_ok"] else "failed",utc(),json.dumps(result),row["id"]))
                    self.event("reuse_finished",dict(id=row["id"],source=source["id"],result=result))
                    continue
                if self.success_names is not None and Path(payload["output"]).name.lower() not in self.success_names:
                    result = dict(estimation_ok=False, savedata_ok=False, status="DEFERRED", deferred=True,
                                  reason="no_historical_success_candidate_user_scope", evidence=self.success_policy)
                    self.publish_deferred(payload, result)
                    self.db.execute("UPDATE tasks SET status='deferred',finished=?,result=? WHERE id=?",
                                    (utc(), json.dumps(result), row["id"]))
                    self.event("historical_scope_deferred", dict(id=row["id"], result=result))
                    continue
                ready, reason = self.dependencies_ready(payload)
                if reason == "dependency_failed":
                    result=dict(estimation_ok=False,savedata_ok=False,status="FAIL",reason=reason)
                    self.publish(payload,result)
                    self.db.execute("UPDATE tasks SET status='blocked',finished=?,result=? WHERE id=?",
                                    (utc(), json.dumps(result), row["id"]))
                    continue
                if reason == "dependency_deferred":
                    result=dict(estimation_ok=False,savedata_ok=False,status="DEFERRED",
                                deferred=True,reason=reason)
                    self.publish_deferred(payload, result)
                    self.db.execute("UPDATE tasks SET status='deferred',finished=?,result=? WHERE id=?",
                                    (utc(), json.dumps(result), row["id"]))
                    self.event("dependency_deferred", dict(id=row["id"], result=result))
                    continue
                if not ready:
                    reasons.add(reason)
                    continue
                reason = admission_reason(snapshot, running, payload, self.get("limit"), self.policy)
                if reason:
                    reasons.add(reason)
                    continue
                try:
                    self.verify_inputs(payload)
                except (OSError, ValueError) as exc:
                    result = dict(estimation_ok=False, savedata_ok=False, status="FAIL", reasons=[str(exc)])
                    self.publish(payload, result)
                    self.db.execute("UPDATE tasks SET status='failed',finished=?,result=? WHERE id=?", (utc(), json.dumps(result), row["id"]))
                    self.event("invalid_input", dict(id=row["id"], result=result))
                    continue
                self.db.execute("UPDATE tasks SET status='running',worker=?,started=? WHERE id=?", (worker, utc(), row["id"]))
                self.event("claimed", dict(id=row["id"], worker=worker, resources=snapshot,
                                           waiting_producer=row["id"] in waiting_producers,
                                           observed_running_memory_credit_gib=sum(x["observed_memory_credit_gib"] for x in running)))
                return dict(status="claimed", task=payload)
            return dict(status="waiting", reason=",".join(sorted(reasons)) or "no_ready_tasks")

    def finish(self, task_id, worker, result):
        with self.transaction():
            row = self.db.execute("SELECT status,worker,payload FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row or row["status"] != "running" or row["worker"] != worker:
                raise ValueError("Completion does not own a running task")
            status = "completed" if result.get("estimation_ok") else "failed"
            self.publish(json.loads(row["payload"]), result)
            self.db.execute("UPDATE tasks SET status=?,finished=?,result=? WHERE id=?",
                            (status, utc(), json.dumps(result), task_id))
            self.event("finished", dict(id=task_id, worker=worker, result=result))

    def publish_deferred(self, payload, result, prior=None):
        folder = Path(payload["output"]).parent
        record = dict(payload.get("record") or {})
        record.update(status="deferred", utc=utc(), deferred=True,
                      reason=result.get("reason"), prior_result=prior)
        atomic_json(folder / "validation.json", result)
        atomic_json(folder / "model_status.json", record)

    def defer(self, task_id, reason, evidence=None):
        """Archive a task without treating it as an estimation failure.

        A running task can be deferred only after its recorded worker and all
        matching Mplus descendants have exited. This prevents a new worker from
        being admitted while the old estimator still owns the input directory.
        """
        with self.transaction():
            row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row or row["status"] not in ("pending", "running", "failed"):
                raise ValueError("Only pending, running or failed tasks can be deferred")
            payload = json.loads(row["payload"])
            prior = json.loads(row["result"] or "null")
            if row["status"] == "running":
                owner = self.db.execute("SELECT pid,created FROM workers WHERE id=?", (row["worker"],)).fetchone()
                if owner is not None:
                    try:
                        process = psutil.Process(owner["pid"])
                        if abs(process.create_time() - owner["created"]) < .1:
                            raise ValueError("Recorded worker is still alive; stop it before deferring")
                    except psutil.NoSuchProcess:
                        pass
                expected_dir = Path(payload["input"]).parent.resolve()
                expected_input = Path(payload["input"]).name.lower()
                for process in psutil.process_iter(["pid", "name"]):
                    try:
                        if process.name().lower() != "mplus.exe":
                            continue
                        if Path(process.cwd()).resolve() == expected_dir and expected_input in [x.lower() for x in process.cmdline()[1:]]:
                            raise ValueError("Matching Mplus process is still alive; stop it before deferring")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            result=dict(estimation_ok=False, savedata_ok=False, status="DEFERRED",
                        deferred=True, reason=reason, evidence=evidence or {}, output=payload["output"])
            self.publish_deferred(payload, result, prior=prior)
            self.db.execute("UPDATE tasks SET status='deferred',worker=NULL,finished=?,result=? WHERE id=?",
                            (utc(), json.dumps(result), task_id))
            self.event("deferred", dict(id=task_id, reason=reason, evidence=evidence or {}, prior=prior))
            return result

    def import_result(self, task_id):
        with self.transaction():
            row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row or row["status"] != "pending":
                raise ValueError("Only an unclaimed task can import prior results")
            payload = json.loads(row["payload"])
            result = inspect_output(payload["output"],payload.get("savedata_contract"))
            result["reused"] = True
            self.db.execute("UPDATE tasks SET status=?,finished=?,result=? WHERE id=?",
                            ("completed" if result["estimation_ok"] else "failed", utc(), json.dumps(result), task_id))
            self.event("imported", dict(id=task_id, result=result))
            return result

    def revalidate(self, task_id):
        with self.transaction():
            row=self.db.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
            if not row or row["status"] not in ("completed","failed"):
                raise ValueError("Only a terminal task can be revalidated")
            payload=json.loads(row["payload"])
            old=json.loads(row["result"])
            if sha256(payload["output"])!=old["sha256"]:
                raise ValueError("Output changed since prior validation")
            result=inspect_output(payload["output"],payload.get("savedata_contract"))
            result["reused"]=old.get("reused",False)
            self.db.execute("UPDATE tasks SET status=?,result=? WHERE id=?",("completed" if result["estimation_ok"] else "failed",json.dumps(result),task_id))
            self.event("revalidated",dict(id=task_id,previous=old,result=result))
            return result

    def tick(self, snapshot=None):
        snapshot = snapshot or resource_snapshot(self.windows_memory_profile, self.profile_max_age_sec)
        with self.transaction():
            if snapshot["at"] - self.get("last_sample") < 30:
                return
            good = snapshot["memory_percent"] < self.policy["memory_resume_percent"] and snapshot["cpu_percent"] < self.policy["cpu_resume_percent"] and snapshot["disk_free_gib"] >= self.policy["disk_reserve_gib"]
            healthy = self.get("healthy") + 1 if good else 0
            limit = self.get("limit")
            if healthy >= 5 and limit < self.get("cap"):
                limit += 1
                healthy = 0
            self.set("healthy", healthy)
            self.set("limit", limit)
            self.set("last_sample", snapshot["at"])
            self.set("resources", snapshot)
            self.event("resources", dict(**snapshot, healthy=healthy, limit=limit))

    def state(self, full=True):
        tasks = [dict(r) for r in self.db.execute("SELECT * FROM tasks" + ("" if full else " WHERE status='running'") + " ORDER BY created,id")]
        for t in tasks:
            t["payload"] = json.loads(t["payload"])
            t["result"] = json.loads(t["result"] or "null")
        totals = dict(self.db.execute("SELECT status,count(*) FROM tasks GROUP BY status").fetchall())
        counts = {status: totals.get(status,0) for status in ("pending", "running", "completed", "failed", "blocked", "deferred")}
        reused = self.db.execute("SELECT count(*) FROM tasks WHERE json_extract(result,'$.reused')=1").fetchone()[0]
        return dict(updated_utc=utc(), enabled=self.get("enabled"), limit=self.get("limit"), cap=self.get("cap"),
                    producers_done=self.get("producers_done"), counts=counts, reused=reused, tasks=tasks,
                    workers=[dict(r) for r in self.db.execute("SELECT * FROM workers")])

    def register(self, worker, pid):
        process = psutil.Process(pid)
        with self.transaction():
            prior = self.db.execute("SELECT * FROM workers WHERE id=?", (worker,)).fetchone()
            if prior and psutil.pid_exists(prior["pid"]):
                previous = psutil.Process(prior["pid"])
                if abs(previous.create_time() - prior["created"]) < 0.1 and prior["pid"] != pid:
                    raise ValueError("Worker identity already owned by a live process")
            if prior and self.db.execute("SELECT count(*) FROM tasks WHERE worker=? AND status='running'", (worker,)).fetchone()[0]:
                raise ValueError("Worker has an unresolved prior task; inspect its original process first")
            self.db.execute("INSERT OR REPLACE INTO workers VALUES(?,?,?,?,?)", (worker, pid, process.create_time(), time.time(), None))
            self.event("worker_registered", dict(worker=worker,pid=pid,created=process.create_time()))
        return dict(status="registered",worker=worker,pid=pid)

    def worker_artifacts(self, worker):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", worker):
            raise ValueError("Invalid worker artifact ID")
        records=[]
        for row in self.db.execute("SELECT id,status,payload,result FROM tasks WHERE worker=? ORDER BY created",(worker,)):
            payload=json.loads(row["payload"]);result=json.loads(row["result"] or "{}")
            records.append(dict(task=row["id"],state=row["status"],output=payload["output"],
                                estimation_ok=result.get("estimation_ok"),savedata_ok=result.get("savedata_ok")))
        done=self.get("producers_done") and not self.db.execute("SELECT 1 FROM tasks WHERE status IN ('pending','running') LIMIT 1").fetchone()
        passed=bool(records) and all(x["estimation_ok"] and x["savedata_ok"] for x in records)
        has_deferred = any(x["state"] == "deferred" for x in records)
        stage="complete" if done and passed else "completed_with_deferred" if done and has_deferred else "completed_with_model_failures" if done else "running"
        for prefix,rows in [("manifest",records or [dict(task="worker_registered",state="waiting",output="",estimation_ok=None,savedata_ok=None)]),
                            ("validation",[dict(check="all_assigned_models_and_savedata",passed=passed,models=len(records))])]:
            target=self.root / f"{prefix}_{worker}.csv"
            temporary=target.with_name(target.name+f".{os.getpid()}.tmp")
            with temporary.open("w",encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            atomic_replace(temporary,target)
        atomic_json(self.root / f"state_{worker}.json",dict(worker=worker,stage=stage,updated_at=utc(),models=len(records)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["init", "enqueue", "import-request", "claim", "finish", "defer", "status", "enable", "disable", "tick", "inspect", "import", "revalidate", "register", "producers-done"])
    p.add_argument("--root", required=True)
    p.add_argument("--request")
    p.add_argument("--worker")
    p.add_argument("--task")
    p.add_argument("--output")
    p.add_argument("--pid", type=int)
    p.add_argument("--r-error")
    p.add_argument("--reason")
    p.add_argument("--evidence")
    args = p.parse_args()
    q = Queue(args.root)
    request = json.loads(Path(args.request).read_text(encoding="utf-8-sig")) if args.request else None
    if args.action == "enqueue":
        result = q.enqueue(request)
    elif args.action == "import-request":
        result = q.enqueue(request, imported=True)
    elif args.action == "register":
        result = q.register(args.worker,args.pid)
    elif args.action == "claim":
        q.tick()
        result = q.claim(args.worker)
    elif args.action == "finish":
        row=q.db.execute("SELECT payload FROM tasks WHERE id=?",(args.task,)).fetchone()
        payload=json.loads(row[0]) if row else {}
        if payload.get("output") != args.output:
            raise ValueError("Completion output does not match the claimed task")
        result = inspect_output(args.output,payload.get("savedata_contract"))
        if args.r_error:
            result.update(estimation_ok=False, status="FAIL", r_error=args.r_error)
        q.finish(args.task, args.worker, result)
    elif args.action == "defer":
        evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8-sig")) if args.evidence else {}
        result = q.defer(args.task, args.reason or "operator_deferred", evidence)
    elif args.action == "inspect":
        result = inspect_output(args.output)
    elif args.action == "import":
        result = q.import_result(args.task)
    elif args.action == "revalidate":
        result = q.revalidate(args.task)
    elif args.action in ("enable", "disable", "producers-done"):
        q.set("producers_done" if args.action == "producers-done" else "enabled", args.action != "disable")
        result = q.state(full=False)
    elif args.action == "tick":
        q.tick()
        result = q.state(full=False)
    else:
        result = q.state(full=False)
    if args.worker and args.action in ("claim","finish","register"):
        try:
            q.worker_artifacts(args.worker)
        except OSError as exc:
            q.event("artifact_write_blocked",dict(worker=args.worker,error=str(exc)))
            result["artifact_warning"]=str(exc)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
