#!/usr/bin/env python3
"""Mac 端 xdev 批次入口：只提交一次；恢复先核原启动正文，等待和取回不重派。"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import ntpath
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import subprocess
import sys
import time
import uuid


NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
DEFAULT_XDEV = Path.home() / ".agents/skills/cross-device-remote/scripts/xdev"


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def exclusive_bytes(path, body):
    with Path(path).open("xb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(Path(path).parent)


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@contextmanager
def locked(directory, create=False):
    import fcntl  # 此客户端仅运行在 Mac/POSIX；Windows worker 独立运行。
    directory = Path(directory)
    if create:
        directory.mkdir(parents=True, mode=0o700, exist_ok=False)
        sync_directory(directory.parent)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("状态目录不存在或是符号链接")
    with (directory / "LOCK").open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def windows_path(value):
    if not isinstance(value, str) or not value or any(c in value for c in "\r\n\0"):
        raise ValueError("Windows 路径须为单行非空字面量")
    path = PureWindowsPath(value)
    if ".." in path.parts or not (path.is_absolute() or re.match(r"^%[A-Za-z_][A-Za-z0-9_]*%[\\/]", value)):
        raise ValueError("Windows 路径须绝对定位，且不含父目录跳转")
    return value


def windows_paths_overlap(left, right):
    left, right = (ntpath.normcase(ntpath.normpath(value)) for value in (left, right))
    try:
        return ntpath.commonpath([left, right]) in (left, right)
    except ValueError:
        return False  # 不同盘符；环境变量别名另在 Windows 展开后复核。


def return_preflight_script(return_dir, work_dir, token):
    """生成取回前的 Windows 只读检查；不解析或重发模型启动正文。"""
    return (
        f"# XDEV_RETURN_PREFLIGHT_V1 {token}\n$ErrorActionPreference = 'Stop'\n"
        f"$BatchReturn = Expand {ps_quote(windows_path(return_dir))}\n"
        f"$BatchProtected = " + (f"Expand {ps_quote(windows_path(work_dir))}\n" if work_dir else "''\n")
        + r'''
function CanonicalBatchReturn([string]$Value) {
  $Full = [IO.Path]::GetFullPath($Value)
  if ($Full -eq [IO.Path]::GetPathRoot($Full)) { return $Full }
  return $Full.TrimEnd([char[]]'\/')
}
function BatchPathsOverlap([string]$Left, [string]$Right) {
  return ($Left.Equals($Right, [StringComparison]::OrdinalIgnoreCase) -or
    $Left.StartsWith($Right.TrimEnd([char[]]'\/') + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $Right.StartsWith($Left.TrimEnd([char[]]'\/') + '\', [StringComparison]::OrdinalIgnoreCase))
}
$BatchReturn = CanonicalBatchReturn $BatchReturn
if (-not (Test-Path -LiteralPath $BatchReturn -PathType Container)) { throw 'RETURN_DIRECTORY_MISSING' }
if ($BatchProtected) {
  $BatchProtected = CanonicalBatchReturn $BatchProtected
  if (BatchPathsOverlap $BatchReturn $BatchProtected) { throw 'RETURN_OVERLAPS_MPLUS_WORK' }
}
$BatchBindingPath = Join-Path $BatchReturn 'BATCH_BINDING.json'
$BatchKind = 'generic'
$BatchManifestSHA = $null
# 原研究目录的父目录也不能作为返回包；明确合成的测试现场可以保留诊断副本。
foreach ($NestedBinding in (Get-ChildItem -LiteralPath $BatchReturn -Filter 'BATCH_BINDING.json' -File -Recurse -Force)) {
  if ($NestedBinding.FullName -ieq $BatchBindingPath) { continue }
  $NestedContract = [IO.File]::ReadAllText($NestedBinding.FullName) | ConvertFrom-Json
  if ($NestedContract.schema -eq 'mplus-durable-plan/1' -and $NestedContract.synthetic -ne $true) {
    throw 'RETURN_CONTAINS_MPLUS_TREE'
  }
}
if ($BatchProtected -or (Test-Path -LiteralPath $BatchBindingPath)) {
  $BatchBinding = [IO.File]::ReadAllText($BatchBindingPath) | ConvertFrom-Json
  if ($BatchBinding.schema -ne 'mplus-durable-plan/1') { throw 'MPLUS_RETURN_BINDING_REQUIRED' }
  $BatchManifestPath = Join-Path $BatchReturn 'EXPORT_MANIFEST.json'
  $BatchExport = [IO.File]::ReadAllText($BatchManifestPath) | ConvertFrom-Json
  if ($BatchExport.schema -ne 'mplus-output-export/1' -or $BatchExport.input_copies_excluded -ne $true) {
    throw 'MPLUS_EXPORT_REQUIRED'
  }
  $BatchSourceWork = CanonicalBatchReturn $BatchExport.source_work
  if (BatchPathsOverlap $BatchReturn $BatchSourceWork) { throw 'RETURN_OVERLAPS_MPLUS_WORK' }
  if ($BatchProtected -and -not $BatchProtected.Equals($BatchSourceWork, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'MPLUS_EXPORT_WORK_DIFFERS'
  }
  if (-not $BatchReturn.Equals((CanonicalBatchReturn $BatchExport.directory), [StringComparison]::OrdinalIgnoreCase)) {
    throw 'MPLUS_EXPORT_DIRECTORY_DIFFERS'
  }
  $BatchExclusionPath = Join-Path $BatchReturn 'RETURN_INPUT_EXCLUSIONS.json'
  $BatchExcluded = [IO.File]::ReadAllText($BatchExclusionPath) | ConvertFrom-Json
  $BatchBindingSHA = (Get-FileHash -LiteralPath $BatchBindingPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($BatchExcluded.schema -ne 'mplus-return-input-exclusions/1' -or $BatchExcluded.binding_sha256 -ne $BatchBindingSHA) {
    throw 'MPLUS_EXPORT_INPUT_BINDING_DIFFERS'
  }
  $BatchEntries = @(Get-Item -LiteralPath $BatchReturn -Force) + @(Get-ChildItem -LiteralPath $BatchReturn -Recurse -Force)
  $BatchCount = 0
  foreach ($Entry in $BatchEntries) {
    if (($Entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'MPLUS_EXPORT_LINK_REFUSED' }
    if ($Entry.PSIsContainer) { continue }
    $Relative = $Entry.FullName.Substring($BatchReturn.Length + 1).Replace('\', '/')
    if ($Relative -ceq 'EXPORT_MANIFEST.json') { continue }
    $Property = $BatchExport.files.PSObject.Properties[$Relative]
    if ($null -eq $Property -or $Entry.Length -ne $Property.Value.bytes) { throw 'MPLUS_EXPORT_FILESET_DIFFERS' }
    if ((Get-FileHash -LiteralPath $Entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Property.Value.sha256) {
      throw 'MPLUS_EXPORT_FILE_HASH_DIFFERS'
    }
    $BatchCount++
  }
  if ($BatchCount -ne @($BatchExport.files.PSObject.Properties).Count) { throw 'MPLUS_EXPORT_FILESET_DIFFERS' }
  foreach ($Member in $BatchBinding.members) {
    if ($Member -notmatch '\A[A-Za-z0-9][A-Za-z0-9_.-]*\z') { throw 'MPLUS_MEMBER_INVALID' }
    foreach ($InputProperty in $BatchBinding.jobs.$Member.inputs.PSObject.Properties) {
      $InputName = $InputProperty.Name
      if ($InputName -ieq 'model.inp') { continue }
      if ($InputName -match '[\\/:]' -or $InputName -in @('.', '..')) { throw 'MPLUS_INPUT_NAME_INVALID' }
      $InputCopy = Join-Path (Join-Path (Join-Path $BatchReturn 'models') $Member) $InputName
      if (Test-Path -LiteralPath $InputCopy) { throw 'MPLUS_INPUT_COPY_REFUSED' }
    }
  }
  $BatchKind = 'mplus-output-export/1'
  $BatchManifestSHA = (Get-FileHash -LiteralPath $BatchManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
}
''' + f"Emit @{{ schema='xdev-return-preflight/1'; token={ps_quote(token)}; allowed=$true; "
        "kind=$BatchKind; directory=$BatchReturn; manifest_sha256=$BatchManifestSHA }\n"
    )


def load_plan(path):
    path = Path(path).expanduser().resolve()
    raw = path.read_bytes()
    plan = json.loads(raw.decode("utf-8"))
    if plan.get("schema") != "xdev-batch-plan/1" or not NAME.fullmatch(plan.get("name", "")):
        raise ValueError("计划 schema 或唯一任务名无效")
    plan["return_dir"] = windows_path(plan.get("return_dir"))
    if "mplus_work_dir" in plan:
        plan["mplus_work_dir"] = windows_path(plan["mplus_work_dir"])
        if windows_paths_overlap(plan["return_dir"], plan["mplus_work_dir"]):
            raise ValueError("return_dir 不能包含或位于原 Mplus 运行目录内")
    for key in ("launcher", "output_dir"):
        if not isinstance(plan.get(key), str) or not plan[key]:
            raise ValueError(f"缺少 {key}")
        plan[key] = str((path.parent / Path(plan[key]).expanduser()).resolve())
    launcher = Path(plan["launcher"])
    body = launcher.read_bytes()
    if body.startswith(b"\xef\xbb\xbf") or not body:
        raise ValueError("xdev 嵌入的 PowerShell 正文须为非空、无 BOM UTF-8")
    body.decode("utf-8", "strict")
    plan["launcher_sha256"] = hashlib.sha256(body).hexdigest()
    payload = plan.get("payload", [])
    if not isinstance(payload, list):
        raise ValueError("payload 必须是明确的文件清单")
    remote_names = set()
    for row in payload:
        if not isinstance(row, dict) or not isinstance(row.get("local"), str):
            raise ValueError("载荷须有 local 与 remote 路径")
        row["remote"] = windows_path(row.get("remote"))
        canonical = ntpath.normcase(ntpath.normpath(row["remote"]))
        if canonical in remote_names:
            raise ValueError("重复的 Windows 载荷目标")
        remote_names.add(canonical)
        row["local"] = str((path.parent / Path(row["local"]).expanduser()).resolve())
        row["sha256"] = sha(row["local"])
    plan["payload"] = payload
    plan["source_plan"] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    return plan


def manifest(directory):
    root = Path(directory).resolve()
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("返回目录包含符号链接")
        if path.is_dir():
            continue
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("返回目录包含非普通文件")
        digest = sha(path)
        after = path.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("核验时返回文件发生变化")
        files[path.relative_to(root).as_posix()] = {"sha256": digest, "bytes": after.st_size}
    return files


class Client:
    def __init__(self, directory, xdev=DEFAULT_XDEV, client_timeout=90):
        self.directory = Path(directory).resolve()
        self.xdev = str(Path(xdev).expanduser().resolve())
        self.client_timeout = client_timeout
        self.path = self.directory / "TASK.json"
        self.state = json.loads(self.path.read_text("utf-8")) if self.path.exists() else None

    def checkpoint(self, **changes):
        self.state.update(changes, updated_at=now())
        save(self.path, self.state)

    def timings(self):
        totals, counts, unclosed = {}, {}, []
        for directory in self.state["phases"]:
            path = Path(directory) / "RESULT.json"
            if not path.exists():
                unclosed.append(str(directory))
                continue
            row = json.loads(path.read_text("utf-8"))
            phase = row["phase"]
            totals[phase] = totals.get(phase, 0.0) + row["elapsed_seconds"]
            counts[phase] = counts.get(phase, 0) + 1
        return {"schema": "xdev-batch-timing/1", "name": self.state["plan"]["name"],
                "local_call_seconds": totals, "local_call_counts": counts,
                "unclosed_local_phases": unclosed,
                "windows_engine_seconds": None, "windows_queue_seconds": None,
                "note": "每项包含该 xdev 调用的排队、执行、轮询；不能拆称纯网络或引擎时间。"}

    def call(self, phase, arguments):
        # mkdir 后、台账追加前也可能退出；唯一目录避免该残留堵塞后续只读恢复。
        destination = self.directory / f"phase-{len(self.state['phases']):03d}-{phase}-{uuid.uuid4().hex[:8]}"
        destination.mkdir(exist_ok=False)
        intent = {"phase": phase, "started_at": now(), "arguments": [self.xdev, *arguments],
                  "client_timeout_seconds": self.client_timeout}
        save(destination / "INTENT.json", intent)
        self.state["phases"].append(str(destination))
        self.checkpoint(active_phase=phase, active_intent=str(destination / "INTENT.json"))
        started = time.perf_counter()
        print(f"XDEV_BATCH_PHASE {phase} started", flush=True)
        timed_out, local_error, rc = False, None, 2
        with (destination / "stdout.txt").open("xb") as out, (destination / "stderr.txt").open("xb") as err:
            try:
                # 独立进程组只含本次 xdev 客户端，绝不向共享 serve 或 Windows worker 发信号。
                proc = subprocess.Popen([self.xdev, *arguments], stdout=out, stderr=err,
                                        start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
                save(destination / "PROCESS.json", {"pid": proc.pid, "at": now(),
                                                   "role": "owned_local_xdev_client"})
                try:
                    rc = proc.wait(timeout=self.client_timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    rc = 124
            except OSError as exc:
                local_error = repr(exc)
        elapsed = time.perf_counter() - started
        stdout = (destination / "stdout.txt").read_text("utf-8", errors="replace")
        stderr = (destination / "stderr.txt").read_text("utf-8", errors="replace")
        ids = sorted({int(value) for value in re.findall(r"(?:job=|XDEV_WAITING id=)(\d+)", stdout + stderr)})
        receipt = {**intent, "finished_at": now(), "elapsed_seconds": elapsed, "exit_code": rc,
                   "queue_job_ids": ids, "local_wait_timed_out": timed_out, "local_error": local_error,
                   "stdout_sha256": sha(destination / "stdout.txt"),
                   "stderr_sha256": sha(destination / "stderr.txt")}
        save(destination / "RESULT.json", receipt)
        self.checkpoint(active_phase=None, active_intent=None, last_phase_result=str(destination / "RESULT.json"))
        print(f"XDEV_BATCH_PHASE {phase} rc={rc} seconds={elapsed:.3f}", flush=True)
        return rc, stdout, stderr, receipt

    def prepare(self, plan):
        frozen = self.directory / "frozen"
        frozen.mkdir()
        payload = []
        for index, row in enumerate(plan["payload"]):
            target = frozen / f"payload-{index:03d}{Path(row['local']).suffix}"
            # push 原本面向小脚本/日常增量；一次复制后固定，后续不读取活动源码提交。
            body = Path(row["local"]).read_bytes()
            if hashlib.sha256(body).hexdigest() != row["sha256"]:
                raise ValueError("固定载荷时源文件发生变化")
            exclusive_bytes(target, body)
            payload.append({**row, "snapshot": str(target)})
        body = Path(plan["launcher"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != plan["launcher_sha256"]:
            raise ValueError("固定启动正文时源文件发生变化")
        exclusive_bytes(frozen / "user-launcher.ps1", body)
        binding_id = uuid.uuid4().hex
        prefix = f"# XDEV_BATCH_BINDING_V1 {binding_id}\n$ErrorActionPreference = 'Stop'\n"
        for row in payload:
            prefix += (
                f"$BatchInput = Expand {ps_quote(row['remote'])}\n"
                f"if ((Get-FileHash -LiteralPath $BatchInput -Algorithm SHA256).Hash.ToLowerInvariant() "
                f"-ne {ps_quote(row['sha256'])}) {{ throw 'XDEV_BATCH_PAYLOAD_CHANGED' }}\n"
            )
        launcher = frozen / "launcher.ps1"
        exclusive_bytes(launcher, prefix.encode("utf-8") + body)
        self.state = {"schema": "xdev-batch-state/2", "created_at": now(), "status": "PREPARING",
                      "plan": plan, "xdev": self.xdev, "xdev_entry_sha256": sha(self.xdev),
                      "binding_id": binding_id, "launcher_snapshot": str(launcher),
                      "launcher_snapshot_sha256": sha(launcher), "payload_snapshots": payload,
                      "phases": [], "submission": "NOT_ATTEMPTED", "detachment_attempts": 0}
        self.checkpoint()

    def submit(self, plan_path):
        if self.state is not None:
            raise FileExistsError("任务已存在；使用 reconcile/wait/status，不重复 submit")
        self.prepare(load_plan(plan_path))
        return self._submit_prepared()

    def retry_preflight(self):
        # 健康检查没有入队副作用；只在从未 push/detach 的已存计划上恢复准备。
        if self.state["submission"] != "NOT_ATTEMPTED" or self.state["detachment_attempts"] != 0:
            raise ValueError("已尝试提交，须 reconcile 原任务，不能重做准备")
        for directory in self.state["phases"]:
            intent = json.loads((Path(directory) / "INTENT.json").read_text("utf-8"))
            if intent["phase"] != "health":
                raise ValueError("已尝试推送或其他操作；原结果待核，不能自动重做")
        return self._submit_prepared()

    def _submit_prepared(self):
        rc, stdout, _, _ = self.call("health", ["health"])
        if rc or not re.search(r"^XDEV_HEALTH OK\s*$", stdout, re.M):
            self.checkpoint(status="CHANNEL_NOT_READY")
            return rc or 2
        for row in self.state["payload_snapshots"]:
            if sha(row["snapshot"]) != row["sha256"]:
                raise ValueError("固定载荷发生变化")
            rc, stdout, _, _ = self.call("push", ["push", row["snapshot"], row["remote"]])
            if rc or not re.search(r"^XDEV_PUSHED .+ sha256=" + row["sha256"] + r"\b", stdout, re.M):
                self.checkpoint(status="PAYLOAD_NOT_CONFIRMED")
                return rc or 2
        launcher = self.state["launcher_snapshot"]
        if sha(launcher) != self.state["launcher_snapshot_sha256"]:
            raise ValueError("固定启动正文发生变化")
        # 先保存原意图和实际使用的固定正文；崩溃、超时或丢回执均不能第二次 detach。
        self.checkpoint(submission="INTENT", status="SUBMISSION_UNCONFIRMED", detachment_attempts=1)
        name = self.state["plan"]["name"]
        rc, stdout, stderr, receipt = self.call("detach", ["detach", name, launcher])
        accepted = re.search(r"^XDEV_DETACHED " + re.escape(name) + r" dir=(.+) pid=(\d+) job=(\d+)\s*$",
                             stdout, re.M)
        if rc == 0 and accepted:
            self.checkpoint(submission="CONFIRMED", status="SUBMITTED",
                            remote_job_directory=accepted[1], submission_queue_job_id=int(accepted[3]),
                            submission_receipt=receipt)
            return 0
        rejected = "NAME_EXISTS" in stdout + stderr
        self.checkpoint(submission="REJECTED" if rejected else "UNKNOWN",
                        status="NAME_COLLISION" if rejected else "SUBMISSION_UNCONFIRMED",
                        unresolved_job_ids=receipt["queue_job_ids"])
        return rc or 2

    def reconcile(self):
        """经原 xdev 通道只读核原 jobs/name/body.ps1；不重发 detach。"""
        if self.state["submission"] == "NOT_ATTEMPTED":
            raise ValueError("尚未尝试 detach；保留准备失败证据，不能当作已提交任务恢复")
        snapshot = Path(self.state["launcher_snapshot"])
        if sha(snapshot) != self.state["launcher_snapshot_sha256"]:
            raise ValueError("固定启动正文发生变化；无法核定原任务")
        body = snapshot.read_text("utf-8")
        name = self.state["plan"]["name"]
        binding = self.state["binding_id"]
        # 查询正文落盘后也可能退出；保留旧文件，并以新路径执行同一原任务的只读观察。
        probe = self.directory / f"binding-observe-{len(self.state['phases']):03d}-{uuid.uuid4().hex[:8]}.ps1"
        script = (
            f"# XDEV_BATCH_OBSERVE_V1 {binding}\n"
            f"$BatchJob = Join-Path $XRoot {ps_quote('jobs' + chr(92) + name)}\n"
            "$BatchBodyPath = Join-Path $BatchJob 'body.ps1'\n"
            "$BatchExists = Test-Path -LiteralPath $BatchBodyPath -PathType Leaf\n"
            "$BatchMatches = $false; $BatchHash = $null\n"
            "if ($BatchExists) {\n"
            "  $BatchBody = [IO.File]::ReadAllText($BatchBodyPath)\n"
            f"  $BatchMatches = $BatchBody.EndsWith({ps_quote(body)}, [StringComparison]::Ordinal)\n"
            "  $BatchHash = (Get-FileHash -LiteralPath $BatchBodyPath -Algorithm SHA256).Hash.ToLowerInvariant()\n"
            "}\n"
            f"Emit @{{ schema='xdev-batch-binding-observation/1'; binding_id={ps_quote(binding)}; "
            f"name={ps_quote(name)}; exists=$BatchExists; matches=$BatchMatches; "
            "body_sha256=$BatchHash; dir=$BatchJob }\n"
        )
        exclusive_bytes(probe, script.encode("utf-8"))
        rc, stdout, _, receipt = self.call("reconcile", ["run", str(probe), "--timeout", "30", "--wait", "45"])
        rows = []
        for line in stdout.splitlines():
            if line.startswith("XDEV_JSON "):
                try:
                    rows.append(json.loads(line[10:]))
                except json.JSONDecodeError:
                    pass
        matched = [row for row in rows if row.get("schema") == "xdev-batch-binding-observation/1"
                   and row.get("binding_id") == binding and row.get("name") == name]
        if rc == 0 and len(matched) == 1 and matched[0].get("exists") is True and matched[0].get("matches") is True:
            changes = {"submission": "CONFIRMED", "binding_observation": matched[0],
                       "binding_observation_receipt": receipt}
            if self.state["status"] not in ("FINISHED", "COLLECTED"):
                changes["status"] = "SUBMITTED"
            self.checkpoint(**changes)
            return 0
        self.checkpoint(last_binding_observation=matched or None, recovery="ORIGINAL_SUBMISSION_UNCONFIRMED")
        return rc or 2

    def wait(self, maximum):
        if self.state["submission"] != "CONFIRMED":
            raise ValueError("提交未确认：先 reconcile 核原正文；不会再次 detach")
        if self.state["status"] in ("FINISHED", "COLLECTED"):
            return self.state["remote_exit_code"]
        name = self.state["plan"]["name"]
        rc, stdout, _, receipt = self.call("wait", ["wait", name, "--max", str(maximum)])
        done = re.search(r"^XDEV_STATE " + re.escape(name) + r" DONE rc=(-?\d+) finished=(\S+)\s*$",
                         stdout, re.M)
        if done and (int(done[1]) & 255) == rc and not receipt["local_wait_timed_out"]:
            self.checkpoint(status="FINISHED", remote_exit_code=int(done[1]), remote_finished_at=done[2])
            return int(done[1])
        self.checkpoint(status="WAITING" if rc == 124 else "OBSERVATION_UNCONFIRMED")
        return rc or 2

    def verify_collection(self):
        if self.state["status"] != "COLLECTED":
            raise ValueError("尚无已核收的返回目录")
        receipt = json.loads((self.directory / "COLLECTION.json").read_text("utf-8"))
        if manifest(self.state["collected_directory"]) != receipt["files"]:
            self.checkpoint(collection_state="LOCAL_FILES_CHANGED")
            raise ValueError("已取回文件发生变化；保留旧回执，不能继续声称核验通过")
        return 0

    def check_return_directory(self):
        plan = self.state["plan"]
        token = uuid.uuid4().hex
        probe = self.directory / ("return-observe-" + token + ".ps1")
        exclusive_bytes(probe, return_preflight_script(plan["return_dir"], plan.get("mplus_work_dir"), token).encode("utf-8"))
        rc, stdout, _, receipt = self.call("return_preflight", ["run", str(probe), "--timeout", "30", "--wait", "45"])
        rows = []
        for line in stdout.splitlines():
            if line.startswith("XDEV_JSON "):
                try:
                    rows.append(json.loads(line[10:]))
                except json.JSONDecodeError:
                    pass
        matched = [row for row in rows if row.get("schema") == "xdev-return-preflight/1" and row.get("token") == token]
        if (rc != 0 or receipt["local_wait_timed_out"] or len(matched) != 1
                or matched[0].get("allowed") is not True
                or matched[0].get("kind") not in ("generic", "mplus-output-export/1")
                or (plan.get("mplus_work_dir") and matched[0].get("kind") != "mplus-output-export/1")):
            self.checkpoint(collection_state="RETURN_PREFLIGHT_REFUSED", return_preflight_observation=matched)
            return rc or 2
        self.checkpoint(return_preflight_observation=matched[0], return_preflight_receipt=receipt)
        return 0

    def collect(self, output=None):
        if self.state["status"] == "COLLECTED":
            self.verify_collection()
            return self.state["remote_exit_code"]
        if self.state["status"] != "FINISHED":
            raise ValueError("先 wait 核原任务终态再取回；失败作业也可取回诊断")
        target = Path(output or self.state["plan"]["output_dir"]).expanduser().resolve()
        if target == self.directory or self.directory in target.parents or target in self.directory.parents:
            raise ValueError("输出目录不能包含或位于本机状态目录内")
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            raise FileExistsError("输出目录非空；原次保留，另指定新的 --output 目录")
        checked = self.check_return_directory()
        if checked:
            return checked
        rc, stdout, _, receipt = self.call("pull", ["pull-dir", self.state["plan"]["return_dir"], str(target)])
        summary = re.search(r"^XDEV_PULLED_DIR (.+) files=(\d+) remote_files=(\d+)\s*$", stdout, re.M)
        if rc != 0 or not summary or Path(summary[1]).resolve() != target:
            self.checkpoint(status="FINISHED", collection_state="UNCONFIRMED")
            return rc or 2
        actual = manifest(target)
        preflight = self.state["return_preflight_observation"]
        if (preflight["kind"] == "mplus-output-export/1"
                and actual.get("EXPORT_MANIFEST.json", {}).get("sha256") != preflight.get("manifest_sha256")):
            self.checkpoint(collection_state="EXPORT_CHANGED_AFTER_PREFLIGHT")
            raise ValueError("Windows 预检后导出清单改变；原次保留，不采用本次取回")
        reported = {}
        for line in stdout.splitlines():
            match = re.fullmatch(r"  ([0-9a-f]{64})  (.+)", line)
            if match:
                filename = match[2].replace("\\", "/")
                if filename in reported:
                    raise ValueError("传输回执重复登记文件")
                reported[filename] = match[1]
        if int(summary[2]) != int(summary[3]) or int(summary[2]) != len(actual) or (
                reported != {name: pin["sha256"] for name, pin in actual.items()}):
            self.checkpoint(collection_state="HASH_OR_FILESET_MISMATCH")
            raise ValueError("返回文件集或 SHA 与传输回执不一致")
        collection = {"at": now(), "files": actual, "directory": str(target), "phase_receipt": receipt,
                      "archive_transport": "xdev internal remote ZIP SHA256 verification passed",
                      "numerical_validation": "REQUIRED_SEPARATELY"}
        save(self.directory / "COLLECTION.json", collection)
        self.checkpoint(status="COLLECTED", collection_state="FILES_VERIFIED",
                        collected_directory=str(target), numerical_validation="REQUIRED_SEPARATELY")
        return self.state["remote_exit_code"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--xdev", type=Path, default=DEFAULT_XDEV)
    parser.add_argument("--client-timeout", type=float, default=90,
                        help="本地 xdev 子进程等待上限；到期只终止此客户端，不终止 Windows 作业")
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--plan", required=True, type=Path)
    wait = sub.add_parser("wait")
    wait.add_argument("--max", type=int, default=60)
    collect = sub.add_parser("collect")
    collect.add_argument("--output", type=Path)
    for name in ("status", "timings", "reconcile", "retry-preflight", "verify-collection"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    if not math.isfinite(args.client_timeout) or not 0 < args.client_timeout <= 86400:
        parser.error("--client-timeout 须为正数且不超过一天")
    if args.command == "wait" and not 0 < args.max <= 86400:
        parser.error("--max 须为 1 至 86400 秒的本机等待预算")
    try:
        # TASK.json 原子替换；只读状态无需争抢正在等待/传输的客户端锁。
        if args.command in ("status", "timings"):
            client = Client(args.state, args.xdev, args.client_timeout)
            if client.state is None:
                raise ValueError("本机任务状态不存在")
            print(json.dumps(client.state if args.command == "status" else client.timings(),
                             ensure_ascii=False, indent=2))
            return 0
        if args.command == "submit":
            load_plan(args.plan)  # 无效计划不创建残缺的状态目录。
        with locked(args.state, create=args.command == "submit"):
            client = Client(args.state, args.xdev, args.client_timeout)
            if args.command != "submit" and client.state is None:
                raise ValueError("本机任务状态不存在")
            if args.command != "submit" and client.state["xdev"] != client.xdev:
                raise ValueError("恢复必须使用原 xdev 入口")
            if args.command == "submit":
                rc = client.submit(args.plan)
            elif args.command == "wait":
                rc = client.wait(args.max)
            elif args.command == "collect":
                rc = client.collect(args.output)
            elif args.command == "reconcile":
                rc = client.reconcile()
            elif args.command == "retry-preflight":
                rc = client.retry_preflight()
            elif args.command == "verify-collection":
                rc = client.verify_collection()
            else:
                rc = 0
            print(f"XDEV_BATCH_STATE {client.path}")
            print(f"XDEV_BATCH {client.state['status']} rc={rc}")
            return rc if 0 <= rc <= 255 else 1
    except (OSError, ValueError, KeyError) as exc:
        print(f"XDEV_BATCH_REFUSED {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
