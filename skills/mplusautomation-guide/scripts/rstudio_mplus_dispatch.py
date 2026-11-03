"""把一次有界 Mplus 合同交给已有 RStudio R worker 的 MplusAutomation 调用。

通道只在 Windows 本机传递小 JSON，不新增跨机队列。原监督器继续拥有引擎 cap。
未知回执、R 生命周期变化或已有领取均停止；不会从本模块直接补发引擎。
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    # R 与 Python 并行观察同一请求；发布前必须写完，且不可覆盖已有回执。
    temporary = path.with_name(path.name + ".part")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    # 同目录硬链接在 APFS / NTFS 上原子发布且拒绝已有目标；中断 .part 保留供核查。
    os.link(temporary, path)
    temporary.unlink()


def now():
    return datetime.now(timezone.utc).isoformat()


def live_process(pid, created):
    import psutil
    process = psutil.Process(int(pid))
    if not math.isclose(process.create_time(), float(created), abs_tol=0.01, rel_tol=0):
        raise RuntimeError("原 R PID 已被复用，禁止向新进程派发")
    if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
        raise RuntimeError("原 R worker 已退出；先核原监督器与输出")
    return process


def ancestry_to_owner(owner):
    """逐条核父子创建时间，避免 Windows 父 PID 复用造成虚假归属。"""
    import psutil
    target = live_process(owner["r_pid"], owner["r_created"])
    if not re.fullmatch(r"(?:R|Rterm|Rscript|rsession(?:-utf8)?)(?:\.exe)?", target.name(), re.I):
        raise RuntimeError("已登记 owner 不是 R 进程")
    studio_r = live_process(owner["rstudio_r_pid"], owner["rstudio_r_created"])
    studio = live_process(owner["rstudio_pid"], owner["rstudio_created"])
    if (not studio_r.name().lower().startswith("rsession")
            or not studio.name().lower().startswith("rstudio")
            or studio_r.ppid() != studio.pid or studio.create_time() > studio_r.create_time()):
        raise RuntimeError("已登记 RStudio 父链改变")
    # R worker 到主 RStudio R 的链也要实查，不能只信 JSON 字段。
    ancestor = target
    for _ in range(64):
        if ancestor.pid == studio_r.pid:
            break
        parent = ancestor.parent()
        if parent is None or parent.create_time() > ancestor.create_time() + 0.01:
            raise RuntimeError("R worker 不再属于已登记 RStudio")
        ancestor = parent
    else:
        raise RuntimeError("RStudio 父链过长")
    current = psutil.Process()
    rows = []
    for _ in range(64):
        created = current.create_time()
        row = {"pid": current.pid, "created": created, "ppid": current.ppid(),
               "name": current.name(), "executable": current.exe()}
        rows.append(row)
        if current.pid == target.pid:
            live_process(current.pid, owner["r_created"])
            for prior in rows:
                observed = live_process(prior["pid"], prior["created"])
                if observed.ppid() != prior["ppid"]:
                    raise RuntimeError("观测过程中父链改变")
            return rows
        parent = current.parent()
        if parent is None or parent.create_time() > created + 0.01:
            break
        if current.ppid() != parent.pid or current.create_time() != created:
            break
        current = parent
    raise RuntimeError("调用进程不属于已绑定的原 R worker")


def files(root):
    root = Path(root)
    result = {}
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("单成员导出只允许普通文件")
        result[path.name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    return result


def command_text(python, script, request):
    values = [str(Path(p).resolve()) for p in (python, script, request)]
    # cmd 的展开不是 JSON 引号转义。拒绝会改变字面路径的字符。
    if any(any(c in value for c in '%!"\r\n') for value in values):
        raise ValueError("cmd 路径包含不支持的展开字符")
    return ('@echo off\r\nchcp 65001 >nul\r\n"' + values[0] +
            '" -X utf8 -B "' + values[1] + '" invoke --request "' +
            values[2] + '" --input "%~1"\r\nexit /b %ERRORLEVEL%\r\n')


def prepare_request(channel, contract_path, work, output, helpers):
    channel, contract_path, work, output, helpers = map(
        lambda p: Path(p).resolve(), (channel, contract_path, work, output, helpers))
    owner_path = channel / "R_OWNER.json"
    owner = read(owner_path)
    ancestry_to_owner(owner)
    contract = read(contract_path)
    ident = contract["member"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", ident):
        raise ValueError("非法成员标识")
    if contract["schema"] != "pp-scientific-single-pilot/1" or contract["new_engine_calls_maximum"] != 1:
        raise ValueError("需要已授权的单调用原监督合同")
    if output.exists() or (work / "RSTUDIO_REQUEST_CLAIM.json").exists() or (work / "guard/CLAIM.json").exists():
        raise RuntimeError("原领取或输出已存在；只可核收，不再提交")
    source = Path(contract["inputs"]["model.inp"]["path"])
    if digest(source) != contract["inputs"]["model.inp"]["sha256"]:
        raise RuntimeError("输入哈希改变")
    dispatch = channel / "requests" / ident
    dispatch.mkdir(parents=True, exist_ok=False)
    work.mkdir(exist_ok=True)
    target = dispatch / "model.inp"
    shutil.copy2(source, target)
    request_path = dispatch / "REQUEST.json"
    wrapper = dispatch / "launch.cmd"
    wrapper.write_bytes(command_text(sys.executable, Path(__file__), request_path).encode("utf-8"))
    request = {
        "schema": "rstudio-mplus-dispatch/1", "at": now(), "member": ident,
        "contract": str(contract_path), "contract_sha256": digest(contract_path),
        "target": str(target), "input_sha256": digest(target),
        "wrapper": str(wrapper), "wrapper_sha256": digest(wrapper),
        "dispatch_source": str(Path(__file__).resolve()), "dispatch_sha256": digest(__file__),
        "owner": owner, "owner_file": str(owner_path), "owner_sha256": digest(owner_path),
        "guard_work": str(work / "guard"), "guard_export": str(work / "guard_export"),
        "output": str(output), "helpers": str(helpers),
        "cap_seconds": contract["cap_seconds"],
        "wait_seconds": float(contract["cap_seconds"]) + 180.0,
        "new_engine_calls_maximum": 1,
    }
    write_new(work / "RSTUDIO_REQUEST_CLAIM.json", {"request": str(request_path), "created_at": now()})
    # REQUEST 最后出现，R 只会看到完整的待执行请求。
    write_new(request_path, request)
    return request_path


def verify_request(request_path):
    request_path = Path(request_path).resolve()
    request = read(request_path)
    if request["schema"] != "rstudio-mplus-dispatch/1":
        raise ValueError("未知请求格式")
    for key, expected in (("contract", "contract_sha256"), ("target", "input_sha256"),
                          ("wrapper", "wrapper_sha256"), ("dispatch_source", "dispatch_sha256"),
                          ("owner_file", "owner_sha256")):
        if digest(request[key]) != request[expected]:
            raise RuntimeError("请求绑定文件已改变: " + key)
    if Path(request["dispatch_source"]).resolve() != Path(__file__).resolve():
        raise RuntimeError("本次使用了不同的调度源码")
    if read(request["owner_file"]) != request["owner"]:
        raise RuntimeError("R 身份改变")
    return request


def invoke(request_path, model_input):
    """此入口只能由 runModels 的 command adapter 调入，再调用原 cap 监督器。"""
    request_path = Path(request_path).resolve()
    request = verify_request(request_path)
    if Path(model_input).resolve() != Path(request["target"]).resolve():
        raise RuntimeError("MplusAutomation 传入了其他模型")
    call_path = request_path.parent / "R_MPLUSAUTOMATION_CALL.json"
    call = read(call_path)
    if (call["request_sha256"] != digest(request_path) or call["function"] != "MplusAutomation::runModels"
            or int(call["r_pid"]) != int(request["owner"]["r_pid"])):
        raise RuntimeError("缺少本次 R/MplusAutomation 调用证据")
    ancestry = ancestry_to_owner(request["owner"])
    (request_path.parent / "BRIDGE_CLAIM").mkdir(exist_ok=False)
    write_new(request_path.parent / "BRIDGE_IDENTITY.json", {
        "at": now(), "request_sha256": digest(request_path),
        "R_call_sha256": digest(call_path), "ancestry": ancestry,
        "function": call["function"], "supervisor_route": "MplusAutomation command adapter",
    })
    helper = Path(request["helpers"]) / "run_scoped_pilot.py"
    contract = read(request["contract"])
    if digest(helper) != contract["runner_sha256"]:
        raise RuntimeError("原 cap 监督器源码改变")
    spec = importlib.util.spec_from_file_location("rstudio_original_scoped_guard", helper)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    rc = guard.run(request["contract"], request["guard_work"], request["guard_export"], request["helpers"])
    # runModels 按同名输出检查返回；原监督目录和完整导出仍保留。
    guard_out = Path(request["guard_export"]) / "model.out"
    if guard_out.exists():
        shutil.copy2(guard_out, request_path.parent / "model.out")
    return rc


def finish_request(request_path):
    request_path = Path(request_path).resolve()
    request = verify_request(request_path)
    dispatch = request_path.parent
    reply = read(dispatch / "R_WRAPPER_RETURN.json")
    if reply["request_sha256"] != digest(request_path) or reply["status"] != "WRAPPER_RETURNED":
        raise RuntimeError("不是原 runModels 的终态回执")
    call = read(dispatch / "R_MPLUSAUTOMATION_CALL.json")
    identity = read(dispatch / "BRIDGE_IDENTITY.json")
    if (identity["request_sha256"] != digest(request_path)
            or identity["R_call_sha256"] != digest(dispatch / "R_MPLUSAUTOMATION_CALL.json")
            or call["function"] != "MplusAutomation::runModels"
            or call["request_sha256"] != digest(request_path)
            or int(reply["r_pid"]) != int(request["owner"]["r_pid"])):
        raise RuntimeError("R/MplusAutomation 调用链证据改变")
    exported = Path(request["guard_export"])
    manifest = read(exported / "EXPORT_MANIFEST.json")
    actual = files(exported)
    del actual["EXPORT_MANIFEST.json"]
    if actual != manifest["files"] or "data.dat" in actual or manifest["individual_inputs_exported"]:
        raise RuntimeError("原监督器导出集合不一致")
    receipt = read(exported / "ENGINE_RECEIPT.json")
    if not receipt["engine_exit_confirmed"] or receipt["actual_engine_calls"] not in (0, 1):
        raise RuntimeError("引擎退出或调用数未知，不能接收")
    output = Path(request["output"])
    output.mkdir(exist_ok=False)
    for name in actual:
        shutil.copy2(exported / name, output / name)
    shutil.copy2(exported / "EXPORT_MANIFEST.json", output / "GUARD_EXPORT_MANIFEST.json")
    for name in ("R_MPLUSAUTOMATION_CALL.json", "R_WRAPPER_RETURN.json", "BRIDGE_IDENTITY.json"):
        shutil.copy2(dispatch / name, output / name)
    if (dispatch / "MplusAutomation.log").is_file():
        shutil.copy2(dispatch / "MplusAutomation.log", output / "MplusAutomation.log")
    write_new(output / "EXPORT_MANIFEST.json", {
        "schema": "pp-single-pilot-export/1", "files": files(output),
        "individual_inputs_exported": False, "source_work": request["guard_work"],
        "engine_exit_confirmed": True, "execution_route": "WINDOWS_RSTUDIO_CLAUDER_MPLUSAUTOMATION",
    })
    return 0 if receipt["state"] == "EXITED" and receipt["exit_code"] == 0 else 2


def execute_stage(channel, contract, work, output, helpers):
    request_path = prepare_request(channel, contract, work, output, helpers)
    request = read(request_path)
    deadline = time.monotonic() + request["wait_seconds"]
    response = request_path.parent / "R_WRAPPER_RETURN.json"
    while not response.exists():
        # R 退出后的监督器可能仍在完成自己的 cap；不在这里杀死或收养它。
        live_process(request["owner"]["r_pid"], request["owner"]["r_created"])
        if time.monotonic() >= deadline:
            raise RuntimeError("原 R 回执期限已过；保留本次请求与引擎领取，禁止重提")
        time.sleep(0.25)
    return finish_request(request_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("invoke",))
    parser.add_argument("--request", required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    raise SystemExit(invoke(args.request, args.input))
