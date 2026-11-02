"""给现成家族做统一准入和成本结转；不启动 R 或 Mplus，不修改冻结候选。"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def write_once(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def positive_cost(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def rebase(plan, costs):
    """每个已闭合前序批次只结转一次；不改变本家族模型和预算。"""
    result = json.loads(json.dumps(plan))
    seen = set()
    for item in costs:
        require(item["source"] not in seen, "重复的历史成本来源")
        seen.add(item["source"])
        require(item.get("engine_accounting_complete") is True, "前序引擎退出/成本尚未闭合")
        require(type(item["new_engine_calls"]) is int and item["new_engine_calls"] >= 0,
                "前序调用数未知")
        require(positive_cost(item["new_engine_seconds"]), "前序耗时未知")
        result["prior_named_engine_calls"] += item["new_engine_calls"]
        result["prior_named_engine_seconds"] += item["new_engine_seconds"]
    base = result["single_model_base"]
    base["historical_engine_calls"] = result["prior_named_engine_calls"]
    base["historical_engine_seconds"] = result["prior_named_engine_seconds"]
    base["new_plus_historical_seconds_ceiling"] = result["prior_named_engine_seconds"] + result["per_model_seconds"]
    result["queue_added_history"] = costs
    return result


def closed_cost(source):
    """复用既有成本读取器；包括启动过但没有导出结果的成员。"""
    plan_path, result_path = Path(source["plan"]), Path(source["result"])
    require(sha(plan_path) == source["plan_sha256"], "前序计划改变")
    result = read(result_path)
    if source.get("result_sha256"):
        require(sha(result_path) == source["result_sha256"], "前序回执改变")
    require(result.get("engine_accounting_complete") is True, "前序回执成本未闭合")
    require(result.get("batch_plan_sha256") == sha(plan_path), "前序回执与计划不匹配")
    plan = read(plan_path)
    helper = plan_path.parent / "engine_attempt_accounting.py"
    require(sha(helper) == plan["code_sha256"][helper.name], "成本读取器版本变化")
    spec = importlib.util.spec_from_file_location("queue_attempt_accounting", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    attempts = [module.inspect_attempt(m["id"], Path(source["work"]) / m["id"],
                result_path.parent / "members" / m["id"], plan["per_model_seconds"])
                for m in plan["members"] if m["mode"] != "import"]
    cost = module.totals(attempts)
    require(cost["engine_accounting_complete"] is True, "原始成本证据未闭合")
    require(cost["new_engine_calls"] == result["new_engine_calls"] and
            abs(cost["new_engine_seconds"] - result["new_engine_seconds"]) < 1e-6,
            "原始成本与批次回执不一致")
    return {"source": str(result_path), "result_sha256": sha(result_path),
            "status": result["status"], "engine_accounting_complete": True,
            "new_engine_calls": cost["new_engine_calls"],
            "new_engine_seconds": cost["new_engine_seconds"]}


def prepare(queue_path, family_id):
    require(os.name == "nt", "准入只在原 Windows 运行")
    import psutil
    queue = read(queue_path)
    require(queue["schema"] == "rstudio-family-queue/1", "队列格式不匹配")
    rows = [x for x in queue["families"] if x["id"] == family_id]
    require(len(rows) == 1 and rows[0]["dispatch"] == "READY", "此家族未开放估计")
    entry = rows[0]
    plan_path, config_path = Path(entry["plan"]), Path(entry["config"])
    require(sha(plan_path) == entry["plan_sha256"] and sha(config_path) == entry["config_sha256"],
            "冻结候选改变")
    plan, config = read(plan_path), read(config_path)
    require(plan["required_stage_runner"] == "WINDOWS_RSTUDIO_CLAUDER_MPLUSAUTOMATION",
            "队列不能改用直接 exe 或独立 Rscript")
    require(sha(entry["driver"]) == entry["driver_sha256"], "R driver 改变")
    require(not Path(config["channel"]).exists() and not Path(config["result_file"]).exists(),
            "原作业已存在，须接回原 ID")
    work = Path(config["progress_file"]).parent
    require(not (work / "BATCH_PLAN_BINDING.json").exists(), "已有启动绑定，不能重新准入")
    if (Path(queue["state_dir"]) / "STOP").exists():
        return {"status": "STOPPED", "family": family_id}
    # 系统资源只采用 Windows 的实际读数；不看 Mac 或 WSL 的可用量。
    import ctypes
    from ctypes import wintypes
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in ("total_phys", "avail_phys", "total_page", "avail_page",
                                                   "total_virt", "avail_virt", "extended")]
    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)), "Windows 内存读取失败")
    limits = plan["single_model_base"]["resources"]
    external = [p.info["pid"] for p in psutil.process_iter(["pid", "name"])
                if str(p.info.get("name", "")).lower() == "mplus.exe"]
    observed = {"available_gib": memory.avail_phys / 1024**3,
                "commit_available_gib": memory.avail_page / 1024**3,
                "cpu_percent": psutil.cpu_percent(interval=1), "mplus_pids": external}
    if (external or observed["available_gib"] < limits["minimum_available_gib"] or
            observed["commit_available_gib"] < limits["minimum_commit_available_gib"] or
            observed["cpu_percent"] > limits["max_cpu_percent"]):
        return {"status": "WAIT_RESOURCES", "family": family_id, "observed": observed}
    require(psutil.disk_usage(str(plan_path.anchor)).free >= 1024**3, "Windows 结果盘空间不足")
    for name, expected in plan["code_sha256"].items():
        require(sha(plan_path.parent / name) == expected, "代码改变: " + name)
    costs = [closed_cost(source) for source in entry.get("cost_sources", [])]
    admitted = rebase(plan, costs)
    directory = plan_path.parent.parent / "queue_admission"
    directory.mkdir(exist_ok=False)
    # 原 coordinator 从计划的相邻目录加载已固定 helpers，不复制整套代码。
    admitted_path = plan_path.with_name("QUEUE_PLAN.json")
    driver_path = config_path.with_name("QUEUE_DRIVER.json")
    arguments = config["arguments"]
    require(arguments.count("--plan") == 1, "缺少唯一计划参数")
    arguments[arguments.index("--plan") + 1] = str(admitted_path)
    write_once(admitted_path, admitted)
    write_once(driver_path, config)
    receipt = {"status": "ADMITTED", "family": family_id, "at": datetime.now(timezone.utc).isoformat(),
               "config": str(driver_path), "driver": entry["driver"], "driver_sha256": entry["driver_sha256"],
               "original_plan_sha256": entry["plan_sha256"], "admitted_plan_sha256": sha(admitted_path),
               "observed": observed, "cost_sources": costs,
               "historical_calls": admitted["prior_named_engine_calls"],
               "historical_seconds": admitted["prior_named_engine_seconds"], "new_engine_calls": 0}
    write_once(directory / "ADMISSION.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True)
    parser.add_argument("--family", required=True)
    args = parser.parse_args()
    try:
        reply = prepare(args.queue, args.family)
    except Exception as exc:
        reply = {"status": "HOLD_ADMISSION", "family": args.family, "error": str(exc)}
    print(json.dumps(reply, ensure_ascii=True, allow_nan=False))
    sys.exit(0 if reply["status"] in ("ADMITTED", "WAIT_RESOURCES", "STOPPED") else 2)
