"""CHARLS 换源的单次 Windows 外层准入；统计排队仍由既有 APIM v2 负责。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid

SCHEMA = "CHARLS_SWAP_RUN_V1"
REQUEST = "W1_charls_swap_20261104"
MODELS = [
    {"id": "apim_sample1_x1_y1_m1_w1_step1", "family": "APIM"},
    {"id": "apimem_sample1_x1_y1_m1_w1_step1", "family": "APIMeM"},
]
GIB = 1024**3
MIN_RESERVE = 256 * 1024**2


class AdmissionError(ValueError):
    """证据不足时拒绝准入；不自动重试或结束任何进程。"""


def taipei_now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(value, message):
    if not value:
        raise AdmissionError(message)


def required(obj, key):
    require(isinstance(obj, dict) and key in obj and obj[key] is not None, "missing_field:" + key)
    return obj[key]


def integer(obj, key, minimum, maximum):
    value = required(obj, key)
    require(type(value) is int and minimum <= value <= maximum, "invalid_integer:" + key)
    return value


def hash_string(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) and value != "0" * 64,
            "invalid_sha256")
    return value


def load_json(path):
    # 拒绝重复JSON字段，避免审批方和执行方看到不同值。
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate_json_key:" + key)
            out[key] = value
        return out
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream, object_pairs_hook=pairs)


def write_new_json(path, value):
    """O_EXCL 原子抢占；即使写入失败也保留原文件，禁止重提。"""
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def append_jsonl(path, value):
    with Path(path).open("ab") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


def normalized(path):
    return os.path.normcase(os.path.abspath(path))


def inside(path, root):
    try:
        return os.path.commonpath([normalized(path), normalized(root)]) == normalized(root)
    except ValueError:
        return False


def reject_alias(path):
    """不跟随 symlink、junction/reparse；逐层检查所有现存祖先。"""
    path = Path(path).absolute()
    require(".." not in path.parts, "parent_traversal_not_allowed")
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode), "symlink_path:" + str(item))
        require(not getattr(info, "st_file_attributes", 0) & 0x400, "reparse_path:" + str(item))
    return path


def checked_file(record):
    path = Path(required(record, "path"))
    require(path.is_absolute(), "file_path_must_be_absolute")
    reject_alias(path)
    require(path.is_file(), "file_missing:" + str(path))
    expected = hash_string(required(record, "sha256"))
    require(sha256(path) == expected, "file_hash_mismatch:" + str(path))
    return path


def tree_bytes(root):
    """只扫描本次隔离根；活动文件瞬时消失可忽略，其他读错误失败关闭。"""
    total = maximum = count = 0
    root = reject_alias(root)
    if not root.exists():
        return {"bytes": 0, "largest_bytes": 0, "file_count": 0}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            try:
                reject_alias(path)
                if path.is_file():
                    length = path.stat().st_size
                    total += length
                    maximum = max(maximum, length)
                    count += 1
            except FileNotFoundError:
                continue
    return {"bytes": total, "largest_bytes": maximum, "file_count": count}


def process_identity(pid):
    import psutil  # 项目已声明依赖；缺失就失败，不执行安装。
    process = psutil.Process(pid)
    return {"pid": process.pid, "birth_epoch": process.create_time(), "exe": str(Path(process.exe()).absolute())}


def verify_identity(expected, getter=process_identity):
    actual = getter(expected["pid"])
    require(actual["pid"] == expected["pid"] and abs(actual["birth_epoch"] - expected["birth_epoch"]) <= 1e-6
            and normalized(actual["exe"]) == normalized(expected["exe"]), "process_identity_changed")
    return actual


def windows_resources():
    """只允许 Windows 宿主原生 Python；psutil 调用原生宿主 API，不用 WSL 值。"""
    require(os.name == "nt", "windows_native_runtime_required")
    import psutil
    names = []
    for process in psutil.process_iter(["pid", "name"]):
        name = process.info["name"]
        require(name is not None, "process_name_unreadable")
        if re.match(r"^(mplus|stata)", name, re.I):
            names.append({"pid": process.info["pid"], "name": name})
    return {"checked_at_taipei": taipei_now(), "native_platform": "Windows",
            "ram_available_bytes": psutil.virtual_memory().available,
            "c_free_bytes": shutil.disk_usage("C:\\").free, "engines": names}


def budget_check(config, resources, occupancy, additional=0, check_engines=True):
    budget = config["budget"]
    require(resources["native_platform"] == "Windows", "host_is_not_windows")
    if check_engines:
        require(not resources["engines"], "mplus_or_stata_busy")
        require(resources["ram_available_bytes"] >= budget["min_ram_available_bytes"], "ram_below_floor")
    require(occupancy["largest_bytes"] < budget["max_single_file_bytes"], "single_file_budget_exceeded")
    require(occupancy["bytes"] + additional + budget["reserve_bytes"] <= budget["max_total_bytes"],
            "isolated_root_budget_insufficient")
    require(resources["c_free_bytes"] - additional - budget["reserve_bytes"] >= budget["min_c_free_bytes"],
            "c_free_below_floor")


def validate_config(config, config_path=None):
    require(required(config, "schema") == SCHEMA, "wrong_config_schema")
    require(required(config, "ready") is True, "config_not_ready")
    require(required(config, "worker") == "W1" and required(config, "request_id") == REQUEST, "wrong_request")
    purpose = required(config, "purpose")
    require(isinstance(purpose, str) and purpose.strip(), "purpose_required")
    require(required(config, "models") == MODELS, "exactly_two_approved_models_required")
    require(isinstance(required(config, "scientific_contract"), dict), "scientific_contract_required")
    root = Path(required(config, "root"))
    require(root.is_absolute(), "absolute_run_root_required")
    reject_alias(root)
    sources = required(config, "sources")
    require(isinstance(sources, dict) and {"harmonized", "demographic", "health"} <= set(sources)
            and set(sources) <= {"harmonized", "demographic", "health", "spouse_roster"}, "source_roles_incomplete")
    protected = required(config, "protected_roots")
    require(isinstance(protected, list) and protected, "protected_roots_must_be_nonempty")
    for item in protected:
        require(Path(item).is_absolute(), "absolute_protected_path_required")
        reject_alias(item)
        require(not inside(root, item) and not inside(item, root), "run_overlaps_protected_root")
    source_sizes = 0
    for role, descriptor in sources.items():
        path = checked_file(descriptor)
        require(path.suffix.lower() == ".dta", "source_format_must_be_dta")
        require(not inside(path, root) and not inside(root, path.parent), "run_overlaps_source_directory")
        require(any(inside(path, p) for p in protected), "source_not_under_protected_root")
        source_sizes += path.stat().st_size
    files = required(config, "files")
    require(isinstance(files, dict) and set(files) == {"rscript", "python", "driver", "engine"}, "runtime_file_set_incomplete")
    for descriptor in files.values():
        path = checked_file(descriptor)
        require(not inside(path, root), "runtime_file_inside_mutable_root")
    require(normalized(files["python"]["path"]) == normalized(sys.executable), "runner_python_differs_from_pinned_python")
    code = required(config, "code_files")
    require(isinstance(code, list) and len(code) >= 2, "code_files_empty_or_incomplete")
    code_paths = []
    for descriptor in code:
        path = checked_file(descriptor)
        require(not inside(path, root), "code_file_inside_mutable_root")
        code_paths.append(normalized(path))
    require(len(code_paths) == len(set(code_paths)), "duplicate_code_file")
    require(normalized(__file__) in code_paths and normalized(files["driver"]["path"]) in code_paths,
            "runner_and_driver_must_be_hash_bound")
    scripts = Path(__file__).absolute().parent
    require(normalized(files["driver"]["path"]) == normalized(scripts / "charls_apim_swap_driver.R"),
            "driver_must_be_from_same_runtime_bundle")
    for name in ("workflow.R", "results.R", "apim_v2_config.R", "apim_v2_models.R", "apim_v2_runtime.R",
                 "apim_v2_data_adapter.R", "charls_apim_swap.R", "mplus_queue.py", "mplus_queue_worker.R",
                 "windows_coordinator.py", "process_ownership.py"):
        require((scripts / name).is_file(), "runtime_dependency_missing:" + name)
    expected_code = {normalized(p) for p in scripts.iterdir() if p.suffix in (".py", ".R") and not p.name.startswith("test_")}
    expected_code.add(normalized(scripts.parent / "assets" / "charls_apim_swap_config_v2.R"))
    require(set(code_paths) == expected_code, "runtime_code_manifest_must_cover_exact_bundle")
    if config_path:
        require(not inside(config_path, root), "private_config_must_be_outside_mutable_root")
    budget = required(config, "budget")
    integer(budget, "max_total_bytes", 1, 1000000000)
    integer(budget, "max_single_file_bytes", 1, 999999999)
    integer(budget, "min_c_free_bytes", 10 * GIB, 2**63 - 1)
    integer(budget, "min_ram_available_bytes", 3 * GIB, 2**63 - 1)
    integer(budget, "reserve_bytes", MIN_RESERVE, 999999999)
    growth = integer(budget, "run_growth_upper_bound_bytes", 1, 999999999)
    require(budget["reserve_bytes"] < budget["max_total_bytes"], "reserve_exceeds_total")
    for descriptor in sources.values():
        require(Path(descriptor["path"]).stat().st_size < budget["max_single_file_bytes"], "source_copy_exceeds_single_file_limit")
    require(source_sizes + growth + budget["reserve_bytes"] <= budget["max_total_bytes"], "source_and_growth_exceed_charls_budget")
    require(isinstance(required(budget, "growth_bound_basis"), str) and budget["growth_bound_basis"].strip(),
            "documented_growth_bound_required")
    return {"source_copy_bytes": source_sizes, "growth_upper_bound_bytes": growth}


def validate_grant(config, descriptor, expected_sha):
    require(hash_string(expected_sha) == required(descriptor, "sha256"), "grant_expected_sha_mismatch")
    path = checked_file(descriptor)
    grant = load_json(path)
    require(required(grant, "approved") is True, "grant_not_approved")
    for key in ("worker", "request_id", "purpose", "models"):
        require(required(grant, key) == config[key], "grant_mismatch:" + key)
    require(Path(required(grant, "root")).is_absolute() and normalized(grant["root"]) == normalized(config["root"]), "grant_root_mismatch")
    require(not inside(path, config["root"]), "grant_must_be_outside_mutable_root")
    return grant


def preflight(config_path, config_hash, grant_path, grant_hash, resources=None, require_empty=True):
    config_path = checked_file({"path": str(config_path), "sha256": config_hash})
    config = load_json(config_path)
    sizes = validate_config(config, config_path)
    descriptor = {"path": str(Path(grant_path).absolute()), "sha256": grant_hash}
    validate_grant(config, descriptor, grant_hash)
    root = Path(config["root"])
    if require_empty:
        require(not root.exists() or not any(root.iterdir()), "run_root_not_empty_observe_original_attempt")
    resources = windows_resources() if resources is None else resources
    occupancy = tree_bytes(root)
    additional = sizes["source_copy_bytes"] + sizes["growth_upper_bound_bytes"] if require_empty else sizes["growth_upper_bound_bytes"]
    budget_check(config, resources, occupancy, additional)
    return config, {"status": "PREFLIGHT_PASS_NOT_STARTED", "checked_at_taipei": taipei_now(),
                    "config_path": str(config_path), "config_sha256": config_hash,
                    "grant_path": descriptor["path"], "grant_sha256": grant_hash,
                    "resources": resources, "occupancy": occupancy, **sizes}


def copy_sources(config, root):
    """先以只读方式核原件，再独占复制至本方目录，复制后重核双方SHA。"""
    destination = Path(root) / "source_snapshot"
    destination.mkdir(exist_ok=False)
    copied = {}
    for role, descriptor in config["sources"].items():
        source = checked_file(descriptor)
        target = destination / (role + source.suffix.lower())
        with source.open("rb") as incoming, target.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        require(sha256(target) == descriptor["sha256"] == sha256(source), "source_changed_during_copy")
        target.chmod(stat.S_IREAD)
        copied[role] = {"path": str(target), "sha256": descriptor["sha256"], "original_path": str(source)}
    write_new_json(Path(root) / "SOURCE_SNAPSHOT.json", {"sources": copied, "time_taipei": taipei_now()})
    return copied


def persistent_stop(root, reason):
    try:
        write_new_json(Path(root) / "STOP_NEW_FIT.json", {"reason": str(reason), "time_taipei": taipei_now(), "no_kill": True})
    except FileExistsError:
        pass


def gate_fit(root, attempt_id, resources=None, identity_getter=process_identity):
    root = reject_alias(Path(root))
    require(not (root / "STOP_NEW_FIT.json").exists(), "persistent_stop_exists")
    binding = load_json(root / "RUN_BINDING.json")
    intent = load_json(root / "STARTED.json")
    owner = load_json(root / "PROCESS.json")
    require(binding["attempt_id"] == intent["attempt_id"] == owner["attempt_id"] == attempt_id, "attempt_mismatch")
    for field in ("config_sha256", "grant_sha256"):
        require(required(binding, field) == required(intent, field) == required(owner, field), "attempt_hash_binding_mismatch:" + field)
    require(sha256(root / "driver_request.json") == required(owner, "driver_request_sha256"), "driver_request_changed")
    config, report = preflight(binding["config_path"], binding["config_sha256"], binding["grant_path"],
                               binding["grant_sha256"], resources=resources, require_empty=False)
    require(normalized(config["root"]) == normalized(root), "binding_root_mismatch")
    verify_identity(owner["driver"], identity_getter)
    verify_identity(owner["supervisor"], identity_getter)
    require(sha256(owner["driver"]["exe"]) == config["files"]["rscript"]["sha256"], "running_rscript_hash_mismatch")
    # Windows system2可能经过cmd；沿每条父子边验证出生时间，不能只按同名exe放行。
    if identity_getter is process_identity:
        import psutil
        from process_ownership import is_verified_descendant
        require(is_verified_descendant(psutil.Process(os.getpid()),
                {"pid": owner["driver"]["pid"], "created": owner["driver"]["birth_epoch"]}, max_depth=4),
                "fit_gate_caller_not_owned_r_driver")
    copied = load_json(root / "SOURCE_SNAPSHOT.json")["sources"]
    require(set(copied) == set(config["sources"]), "source_snapshot_roles_incomplete")
    for role, descriptor in copied.items():
        path = checked_file(descriptor)
        require(inside(path, root / "source_snapshot") and descriptor["sha256"] == config["sources"][role]["sha256"],
                "source_snapshot_binding_mismatch")
    receipt = {"schema": "CHARLS_SWAP_FIT_ADMISSION_V1", "worker": "W1", "request_id": REQUEST,
               "attempt_id": attempt_id, "models": MODELS, "config_sha256": binding["config_sha256"],
               "grant_sha256": binding["grant_sha256"], "driver": owner["driver"],
               "resources": report["resources"], "occupancy": report["occupancy"],
               "admitted_at_taipei": taipei_now(), "queue": "existing_APIM_v2_serial_only"}
    write_new_json(root / "FIT_ADMITTED.json", receipt)
    return receipt


def launch(config_path, config_hash, grant_path, grant_hash):
    require(os.name == "nt", "windows_native_runtime_required")
    config, report = preflight(config_path, config_hash, grant_path, grant_hash)
    root = Path(config["root"])
    root.mkdir(parents=True, exist_ok=True)
    attempt = uuid.uuid4().hex
    supervisor = process_identity(os.getpid())
    intent = {"schema": "CHARLS_SWAP_STARTED_V1", "worker": "W1", "request_id": REQUEST, "attempt_id": attempt,
              "root": str(root), "created_at_taipei": taipei_now(), "supervisor": supervisor,
              "driver_exe": config["files"]["rscript"], "runner_sha256": sha256(__file__),
              "driver_sha256": config["files"]["driver"]["sha256"], "config_sha256": config_hash,
              "grant_sha256": grant_hash, "retry_allowed": False}
    write_new_json(root / "STARTED.json", intent)
    child = None
    try:
        write_new_json(root / "RUN_BINDING.json", {"attempt_id": attempt, **report})
        write_new_json(root / "PREFLIGHT.json", report)
        sources = copy_sources(config, root)
        temp = root / "tmp"
        temp.mkdir(exist_ok=False)
        driver_request = {"root": str(root), "attempt_id": attempt, "sources": sources,
                          "scientific_contract": config["scientific_contract"], "engine": config["files"]["engine"]["path"],
                          "python": config["files"]["python"]["path"], "gate_script": str(Path(__file__).absolute()),
                          "protected_roots": config["protected_roots"], "expected_models": MODELS,
                          "config_sha256": config_hash, "grant_sha256": grant_hash}
        request_path = root / "driver_request.json"
        write_new_json(request_path, driver_request)
        # 复制后、启动前再次现场检查，排除前检和复制之间的引擎/资源变化。
        preflight(config_path, config_hash, grant_path, grant_hash, require_empty=False)
        env = os.environ.copy()
        env.update({name: str(temp) for name in ("TEMP", "TMP", "TMPDIR")})
        env.update(CHARLS_SWAP_ATTEMPT_ID=attempt, CHARLS_SWAP_RUN_ROOT=str(root))
        with (root / "driver.stdout.log").open("xb") as stdout, (root / "driver.stderr.log").open("xb") as stderr:
            child = subprocess.Popen([config["files"]["rscript"]["path"], "--vanilla", config["files"]["driver"]["path"],
                                      "--request", str(request_path)], cwd=root, env=env, stdout=stdout, stderr=stderr)
            identity = process_identity(child.pid)
            require(normalized(identity["exe"]) == normalized(config["files"]["rscript"]["path"]), "started_exe_mismatch")
            write_new_json(root / "PROCESS.json", {"attempt_id": attempt, "driver": identity, "supervisor": supervisor,
                                                   "rscript_sha256": config["files"]["rscript"]["sha256"],
                                                   "driver_sha256": config["files"]["driver"]["sha256"],
                                                   "driver_request_sha256": sha256(request_path),
                                                   "config_sha256": config_hash, "grant_sha256": grant_hash})
            monitor(root, config, child, identity, attempt)
        return load_json(root / "DONE.json")
    except BaseException as error:
        persistent_stop(root, error)
        write_new_json(root / "LAUNCH_FAILURE.json", {"attempt_id": attempt, "error": str(error),
                       "time_taipei": taipei_now(), "intent_preserved": True, "retry_allowed": False,
                       "child_pid": None if child is None else child.pid, "no_process_killed": True})
        raise


def monitor(root, config, child, identity, attempt):
    import psutil
    peak_bytes = peak_working = peak_private = 0
    minimum_free = 2**63 - 1
    while child.poll() is None:
        try:
            verify_identity(identity)
            memory = psutil.Process(child.pid).memory_info()
        except psutil.NoSuchProcess:
            if child.poll() is not None:
                break
            raise
        occupancy, resources = tree_bytes(root), windows_resources()
        peak_bytes = max(peak_bytes, occupancy["bytes"])
        peak_working = max(peak_working, memory.rss)
        peak_private = max(peak_private, getattr(memory, "private", memory.rss))
        minimum_free = min(minimum_free, resources["c_free_bytes"])
        try:
            budget_check(config, resources, occupancy, check_engines=False)
        except AdmissionError as error:
            persistent_stop(root, error)
        append_jsonl(Path(root) / "monitor.jsonl", {"time_taipei": taipei_now(), "attempt_id": attempt,
                     "driver_pid": child.pid, "w1_bytes": occupancy["bytes"], "largest_bytes": occupancy["largest_bytes"],
                     "c_free_bytes": resources["c_free_bytes"], "driver_rss_bytes": memory.rss,
                     "driver_private_bytes": getattr(memory, "private", memory.rss)})
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    resources, occupancy = windows_resources(), tree_bytes(root)
    peak_bytes = max(peak_bytes, occupancy["bytes"])
    minimum_free = min(minimum_free, resources["c_free_bytes"])
    try:
        budget_check(config, resources, occupancy, check_engines=False)
    except AdmissionError as error:
        persistent_stop(root, error)
    unchanged = all(sha256(item["path"]) == item["sha256"] for item in config["sources"].values())
    complete_path = Path(root) / "DRIVER_COMPLETE.json"
    complete = load_json(complete_path) if complete_path.exists() else None
    valid_complete = bool(complete and complete.get("attempt_id") == attempt and complete.get("models") == MODELS
                          and complete.get("status") == "WORKFLOW_INTERNAL_VALIDATE_PASS")
    successful = child.returncode == 0 and valid_complete and unchanged and not (Path(root) / "STOP_NEW_FIT.json").exists()
    write_new_json(Path(root) / "DONE.json", {"schema": "CHARLS_SWAP_DONE_V1", "worker": "W1", "request_id": REQUEST,
                   "attempt_id": attempt, "ended_at_taipei": taipei_now(), "exit_code": child.returncode,
                   "status": "INTERNAL_WORKFLOW_PASS_NOT_SCIENTIFIC_RELEASE" if successful else "FAILED_OR_INCOMPLETE",
                   "driver_complete": complete, "source_hashes_unchanged": unchanged, "models": MODELS,
                   "peak_root_live_bytes": peak_bytes, "minimum_c_free_bytes": minimum_free,
                   "driver_peak_rss_bytes": peak_working, "driver_peak_private_bytes": peak_private,
                   "final_occupancy": occupancy, "final_resources": resources,
                   "measurement_boundary": "5-second samples; no hard quota; Mplus resource evidence remains in the existing APIM v2 workflow",
                   "no_process_killed": True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "launch"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--config-sha256", required=True)
        command.add_argument("--grant", type=Path, required=True)
        command.add_argument("--grant-sha256", required=True)
    gate = commands.add_parser("gate-fit")
    gate.add_argument("--run-root", type=Path, required=True)
    gate.add_argument("--attempt-id", required=True)
    arguments = parser.parse_args()
    try:
        if arguments.command == "gate-fit":
            result = gate_fit(arguments.run_root, arguments.attempt_id)
        elif arguments.command == "launch":
            result = launch(arguments.config, arguments.config_sha256, arguments.grant, arguments.grant_sha256)
        else:
            _, result = preflight(arguments.config, arguments.config_sha256, arguments.grant, arguments.grant_sha256)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") != "FAILED_OR_INCOMPLETE" else 1
    except Exception as error:
        print(json.dumps({"status": "DENIED_OR_FAILED", "error": str(error), "time_taipei": taipei_now()}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
