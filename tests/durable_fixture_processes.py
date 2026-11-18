"""合成测试专用生命周期工具；只观察/清理已绑定到本夹具的进程。"""
import json
import os
from pathlib import Path
import shutil
import sys
import time

import psutil

WINDOWS = os.name == "nt"


def _shared_json_bytes(path):
    """仅测试夹具：Windows 读者不阻止生产 worker 原子替换状态文件。"""
    if not WINDOWS:
        with Path(path).open("rb") as stream:
            data = stream.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("Fixture JSON exceeds the bounded status reader")
        return data
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    # GENERIC_READ, FILE_SHARE_READ|WRITE|DELETE, OPEN_EXISTING。
    handle = create(str(Path(path).absolute()), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close(handle)
        raise
    with os.fdopen(fd, "rb") as stream:
        data = stream.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Fixture JSON exceeds the bounded status reader")
    return data


def read_fixture_json(path, *, deadline=None):
    """保持原阶段期限；永久权限、坏 JSON 和超期都真实失败，不伪造状态。"""
    end = min(time.monotonic() + 1, deadline) if deadline is not None else time.monotonic() + 1
    while True:
        try:
            return json.loads(_shared_json_bytes(path).decode("utf-8-sig"))
        except OSError as error:
            retry = WINDOWS and (getattr(error, "winerror", None) in {2, 5, 32, 33}
                                         or isinstance(error, (PermissionError, FileNotFoundError)))
            remaining = end - time.monotonic()
            if not retry or remaining <= 0:
                raise
            time.sleep(min(.02, remaining))


def preserve_fixture(root, destination, cleanup_error=None):
    """未排空则原地保留，不让复制活动锁的次生错误掩盖原清理失败。"""
    root, destination = Path(root), Path(destination)
    if cleanup_error is not None:
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "ORIGINAL_FIXTURE_RETAINED.json").write_text(json.dumps({
            "status": "CLEANUP_UNCONFIRMED_ORIGINAL_RETAINED", "original_root": str(root),
            "cleanup_error": repr(cleanup_error), "snapshot_complete": False,
            "source_deleted": False}, indent=2), encoding="utf-8")
        return
    shutil.copytree(root, destination)


def normalized(path):
    # OS提供的cwd/exe与夹具根均为绝对路径；热路径不逐层stat深目录。
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def exited(proc):
    if not proc.is_running() or proc.status() in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
        return True
    if os.name == "nt":
        try:
            proc.wait(timeout=0)
            return True
        except psutil.TimeoutExpired:
            pass
    return False


class FixtureProcesses:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.records = {}
        self.events = []
        self.self_pid = os.getpid()
        self.self_created = psutil.Process().create_time()
        self.python_launcher_exe = normalized(Path(sys.executable).resolve())
        self.python_runtime_exe = normalized(psutil.Process().exe())

    def event(self, stage, **fields):
        self.events.append(dict(stage=stage, monotonic=time.monotonic(), **fields))
        (self.root / "FIXTURE_PROCESS_EVENTS.json").write_text(
            json.dumps(self.events, indent=2), encoding="utf-8")

    def belongs(self, proc):
        root = normalized(self.root)
        cwd = normalized(proc.cwd())
        return cwd == root or cwd.startswith(root + os.sep) or any(
            os.path.normcase(arg.replace("/", os.sep)) == root or
            os.path.normcase(arg.replace("/", os.sep)).startswith(root + os.sep)
            for arg in proc.cmdline())

    def remember(self, proc, origin, expected_created=None):
        try:
            created = proc.create_time()
            if expected_created is not None and abs(created - expected_created) >= 1e-3:
                raise AssertionError("Fixture PID creation identity differs")
            # run_worker()部分测试在pytest本进程调用Worker；它不是清理目标。
            if proc.pid == self.self_pid and abs(created-self.self_created) < 1e-3:
                return None
            old = self.records.get(proc.pid)
            if old is not None:
                if abs(old["created"] - created) >= 1e-3:
                    raise AssertionError("Fixture PID was reused")
                # 重复观察验证原绑定，不用当前 exe/argv 覆盖已固定的身份。
                return old if self.current(old) is not None else None
            if exited(proc):
                return None
            if not self.belongs(proc):
                raise AssertionError("Process is outside this synthetic fixture")
            # macOS framework Python 先以同 PID exec 到当前测试解释器的实际二进制。
            # 只在首次绑定前等这一个已知转换；绑定后仍拒绝任何 exe/PID 变化。
            if (sys.platform == "darwin" and self.python_launcher_exe != self.python_runtime_exe
                    and normalized(proc.exe()) == self.python_launcher_exe):
                end = time.monotonic() + 1
                while True:
                    # psutil.Process.exe() 按实例缓存；启动转换必须用同 PID 的新观察。
                    proc = psutil.Process(proc.pid)
                    if normalized(proc.exe()) != self.python_launcher_exe:
                        break
                    if time.monotonic() >= end:
                        raise AssertionError("Python framework launch identity did not stabilize")
                    time.sleep(.005)
                if (abs(proc.create_time()-created) >= 1e-3
                        or normalized(proc.exe()) != self.python_runtime_exe
                        or not self.belongs(proc)):
                    raise AssertionError("Unexpected Python startup identity transition")
            record = dict(pid=proc.pid, created=created, exe=normalized(proc.exe()),
                          argv=proc.cmdline(), origin=origin)
            self.records[proc.pid] = record
            return record
        except psutil.NoSuchProcess:
            return None

    def current(self, record):
        try:
            proc = psutil.Process(record["pid"])
            if abs(proc.create_time() - record["created"]) >= 1e-3:
                raise AssertionError("Fixture PID was reused; refusing signal")
            if exited(proc):
                return None
            if normalized(proc.exe()) != record["exe"] or not self.belongs(proc):
                # 已知进程退出中可能短暂清空cmdline；只等原PID，不猜测死亡。
                try:
                    proc.wait(timeout=.2)
                    return None
                except psutil.TimeoutExpired:
                    raise AssertionError("Fixture executable/path identity changed")
            return proc
        except psutil.NoSuchProcess:
            return None

    def observe(self, children, work):
        for child in children:
            if child.poll() is None:
                try:
                    self.remember(psutil.Process(child.pid), "popen")
                except psutil.NoSuchProcess:
                    pass
        paths = [Path(work) / "STATUS.json"] + list((Path(work) / "attempts").glob("*/CLAIM.json")) + list((Path(work) / "models").glob("*/ENGINE_STARTED.json"))
        for path in paths:
            if not path.exists():
                continue
            try:
                doc = read_fixture_json(path)
            except json.JSONDecodeError:
                if path.name == "STATUS.json" and not children and not self.records:
                    continue  # 旧目录拒绝测试刻意放入非JSON，没有新子进程。
                raise
            marker = doc.get("worker", doc)
            if "pid" in marker and "created" in marker:
                try:
                    self.remember(psutil.Process(marker["pid"]), "marker:" + str(path.relative_to(self.root)), marker["created"])
                except psutil.NoSuchProcess:
                    pass
        # 只沿已知且身份仍相同的进程树走访，不扫描全局进程表。
        for record in list(self.records.values()):
            proc = self.current(record)
            if proc is None:
                continue
            try:
                for child in proc.children(recursive=True):
                    self.remember(child, "descendant:" + str(proc.pid))
            except psutil.NoSuchProcess:
                pass

    def actual_coordinator(self, popen, work):
        marker = read_fixture_json(Path(work) / "STATUS.json")["worker"]
        launcher = self.records.get(popen.pid)
        if launcher is None:
            launcher = self.remember(psutil.Process(popen.pid), "coordinator-launcher")
        if launcher is None or self.current(launcher) is None:
            raise AssertionError("Original coordinator launcher is not alive and bound")
        record = self.remember(psutil.Process(marker["pid"]), "actual-coordinator", marker["created"])
        if record is None or abs(record["created"] - marker["created"]) >= 1e-3:
            raise AssertionError("Actual coordinator is not bound")
        proc = self.current(record)
        if proc is None or "run" not in proc.cmdline() or normalized(work) not in [normalized(a) for a in proc.cmdline() if a == str(work)]:
            raise AssertionError("Actual coordinator command differs")
        if proc.pid != popen.pid:
            ancestors = proc.parents()
            if not any(p.pid == launcher["pid"] and abs(p.create_time()-launcher["created"]) < 1e-3
                       for p in ancestors):
                raise AssertionError("Actual coordinator is outside the original launcher lineage")
        return proc

    def crash_coordinator(self, popen, work):
        proc = self.actual_coordinator(popen, work)
        self.event("COORDINATOR_CRASH_INTENT", actual_pid=proc.pid, popen_pid=popen.pid,
                   created=proc.create_time())
        proc.kill()
        if proc.pid != popen.pid:
            proc.wait(timeout=5)
        popen.wait(timeout=5)
        if self.current(self.records[proc.pid]) is not None:
            raise AssertionError("Actual coordinator did not exit")
        self.event("COORDINATOR_EXIT_CONFIRMED", actual_pid=proc.pid, popen_pid=popen.pid)

    def cleanup(self, children, work):
        self.observe(children, work)
        # 正常释放后先有限等候；不把入口退出当全部子孙退出。
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.observe(children, work)
            if not any(self.current(r) is not None for r in self.records.values()):
                break
            time.sleep(.05)
        self.observe(children, work)
        for record in list(self.records.values()):
            proc = self.current(record)
            if proc is not None:
                # 杀前再次收集已知父的子孙；只使用本夹具身份链。
                for child in proc.children(recursive=True):
                    self.remember(child, "cleanup-descendant:" + str(proc.pid))
                proc.kill()
        for record in list(self.records.values()):
            proc = self.current(record)
            if proc is not None:
                proc.kill()
        # Popen回收自己的根；psutil不提前消费其退出状态。
        for child in children:
            child.wait(timeout=5)
        deadline = time.monotonic() + 5
        alive = []
        while True:
            alive = [r for r in self.records.values() if self.current(r) is not None]
            if not alive or time.monotonic() >= deadline:
                break
            time.sleep(.05)
        self.event("CLEANUP_OBSERVED", known_records=list(self.records.values()), still_alive=alive)
        if alive:
            raise AssertionError("Synthetic children still alive; preserve fixture")
