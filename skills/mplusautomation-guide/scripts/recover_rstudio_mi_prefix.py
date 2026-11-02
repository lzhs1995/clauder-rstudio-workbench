"""核收已停止的 MI 前缀，在原家族内准备未启动阶段；不调用 R 或 Mplus。

--reader-root 提供本研究已验证的 read_rstudio_income_batch 及依赖。
脚本保留原代码、结果和成本；新尝试复用不可变代码硬链接，不复制数据。
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    for name in ("original", "reader-root", "attempt", "coordinator-source"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("plan-sha256", "config-sha256", "result-sha256", "coordinator-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--resource-wait-seconds", type=int, default=1800)
    args = parser.parse_args()
    require(os.name == "nt", "仅在原 Windows 准备")
    original, attempt = args.original.resolve(), args.attempt.resolve()
    require(original in attempt.parents and not attempt.exists(), "仅在原家族内新建一次恢复状态")
    require(120 <= args.resource_wait_seconds <= 1800, "资源等待必须有界")
    sys.path.insert(1, str(args.reader_root))
    import psutil
    import read_rstudio_income_batch as route
    sys.path.insert(1, str(original / "code"))
    from engine_attempt_accounting import inspect_attempt, totals

    plan_path, config_path = original / "code/BATCH_PLAN.json", original / "code/DRIVER_CONFIG.json"
    result_path = original / "results/BATCH_RESULT.json"
    for path, pin in ((plan_path, args.plan_sha256), (config_path, args.config_sha256),
                      (result_path, args.result_sha256), (args.coordinator_source, args.coordinator_sha256)):
        require(sha(path) == pin, "原输入或补丁 SHA 改变: " + str(path))
    old, config, result = read(plan_path), read(config_path), read(result_path)
    require(old.get("required_stage_runner") == route.ROUTE, "必须保留 RStudio 路线")
    require(result["status"] == "HOLD_NO_EXPORT" and result["detail"]["runner_exit_code"] == 4,
            "本入口只恢复资源等待后未启动的阶段；超时模型另行裁定")
    require(result["batch_plan_sha256"] == args.plan_sha256, "终态引用其他计划")
    for name, pin in old["code_sha256"].items():
        require(sha(original / "code" / name) == pin, "原代码改变: " + name)
    owner_path, terminal_path = original / "rstudio_channel/R_OWNER.json", original / "rstudio_channel/R_DRIVER_RESULT.json"
    binding_path = original / "run/BATCH_PLAN_BINDING.json"
    owner, terminal, binding = read(owner_path), read(terminal_path), read(binding_path)
    require(terminal["status"] == "BATCH_HOLD" and terminal["coordinator_exit_code"] == 2,
            "原协调器尚未按资源 HOLD 退出")
    require(terminal["r_owner"] == owner and owner["config_sha256"] == args.config_sha256, "原 R 身份不同")
    package = owner["MplusAutomation_contract"]
    require(config["mplusautomation"] == old["mplusautomation"], "原包合同不同")
    require(config["coordinator_sha256"] == old["code_sha256"]["run_income_rstudio_batch.py"], "协调器不同")
    for key in ("file_sha256", "function_sha256", "version"):
        require(package[key] == old["mplusautomation"][key], "实际加载包不同")
    require(route.windows_path(package["library"]) == route.windows_path(old["mplusautomation"]["library"]), "包路径不同")
    for item in ({"pid": owner["r_pid"], "created": owner["r_created"]}, binding["owner"]):
        try:
            process = psutil.Process(item["pid"])
            if math.isclose(process.create_time(), item["created"], rel_tol=0, abs_tol=.001):
                try:
                    process.wait(timeout=0)
                except psutil.TimeoutExpired:
                    raise ValueError("原 worker 或协调器仍运行")
        except psutil.NoSuchProcess:
            pass
    require(not [p.info for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "mplus.exe"],
            "已有 Mplus 运行，先接回其原状态")
    original_files = route.pool.file_set(original / "results")
    export = read(original / "results/BATCH_EXPORT_MANIFEST.json")
    require({k: v for k, v in original_files.items() if k != "BATCH_EXPORT_MANIFEST.json"} == export["files"],
            "原结果文件集或 SHA 改变")
    source_pins = {p.relative_to(original).as_posix(): sha(p) for p in
                   (plan_path, config_path, result_path, owner_path, terminal_path, binding_path)}
    route.pool.reader.READER = original / "code/calibrated_reader.py"
    attempts, imported, fits, completed = [], [], {}, []
    gap = False
    for node in old["members"]:
        ident = node["id"]
        directory = original / "results/members" / ident
        if node["mode"] == "new":
            attempts.append(inspect_attempt(ident, original / "run" / ident, directory, old["per_model_seconds"]))
        if not directory.exists():
            gap = True
            continue
        require(not gap, "已完成成员不是连续前缀")
        files = route.pool.file_set(directory)
        require({k: v for k, v in files.items() if k != "EXPORT_MANIFEST.json"} == read(directory / "EXPORT_MANIFEST.json")["files"],
                "成员文件集或 SHA 改变")
        require("data.dat" not in files, "个体输入混入导出")
        receipt = read(directory / "ENGINE_RECEIPT.json")
        require(receipt["engine_sha256"] == old["engine_sha256"] and receipt["cap_seconds"] == old["per_model_seconds"], "引擎或 cap 不同")
        require(receipt["inputs"]["data.dat"] == node["data_sha256"], "插补身份不同")
        require(receipt["contract_sha256"] == sha(directory / "EXECUTION_CONTRACT.json"), "原执行合同不同")
        evidence = route.verify_stage(node, directory, receipt, owner)
        fit = route.pool.reader.evaluate(directory)
        require(fit["status"] == "PASS_SINGLE_MODEL" and all(fit["checks"].values()), "原成员未通过: " + ident)
        require(fit["free_parameters"] == old["expected_parameters"], "参数数量不同")
        require(set(route.pool.aliases(fit)) == set(route.pool.canonical_aliases(old["parameter_aliases"])), "参数身份不同")
        if node["mode"] == "import":
            require(files == node["import_files"], "原校准导入改变")
        compact = re.sub(r"\s+", "", (directory / "model.inp").read_text(encoding="ascii")).upper()
        require("KNOWNCLASS=CG(C12=0C12=1);" in compact and "GAUSSHERMITE(" + str(node["integration_points"]) + ")" in compact,
                "分组或积分设置不同")
        if node["mode"] == "import" or node["integration_points"] == 7:
            require(sha(directory / "model.inp") == node["input_sha256"], "固定输入不同")
        if node["integration_points"] == 15:
            lower = fits[node["start_source_id"]]
            require(route.pool.compare_quadrature(lower, fit, old["comparison_tolerances"])["status"] == "PASS", "积分核验未通过")
            if node["mode"] == "new":
                template = Path(node["template_path"])
                require(sha(template) == node["template_sha256"], "GH15 模板改变")
                generated, _ = route.pool.fitted_starts(template.read_text(encoding="ascii"), lower)
                require(generated.encode("ascii") == (directory / "model.inp").read_bytes(), "GH15 未承接同 MI 的 GH7 解")
        fits[ident] = fit
        completed.append({"member": ident, "mi": node["mi"], "primary": node["primary"], "route": evidence})
        imported.append({"member": ident, "source_directory": str(directory), "source_node": node, "files": files})
    budget = totals(attempts)
    require(budget["engine_accounting_complete"] and budget["new_engine_calls"] == result["new_engine_calls"] == terminal["MplusAutomation_invocations"],
            "原调用数或退出尚未闭合")
    require(math.isclose(budget["new_engine_seconds"], result["new_engine_seconds"], rel_tol=0, abs_tol=1e-6), "原成本不同")
    require(len(imported) == result["members_completed"] and 0 < len(imported) < len(old["members"]), "已完成前缀不同")
    require(old["members"][len(imported)]["id"] == result["detail"]["member"], "暂停节点不同")
    accepted = {node["member"] for node in imported}
    require(all(a["state"] == "NO_START_EVIDENCE" for a in attempts if a["member"] not in accepted), "未来成员已有启动或未知意图")
    audit = {"status": "PASS_ACCEPTED_PREFIX_REUSABLE", "at": datetime.now(timezone.utc).isoformat(),
             "original_job_id": old["name"], "source_plan_sha256": args.plan_sha256,
             "source_files": source_pins, "source_results_files": original_files,
             "source_R_owner": owner, "source_R_terminal": terminal, "original_coordinator_binding": binding,
             "completed_stages": completed, "recovery_imports": imported, "budget": budget,
             "engine_attempts": attempts, "first_unstarted_member": old["members"][len(imported)]["id"],
             "new_mplus_calls": 0, "full_MI_pooling_performed": False, "review_mode": "solo_self_review"}
    deadline = datetime.fromisoformat(binding["created_at"]).timestamp() + old["max_coordinator_wall_seconds"]
    remaining_wall = math.floor(deadline - datetime.now(timezone.utc).timestamp())
    remaining_calls = old["max_new_engine_calls"] - budget["new_engine_calls"]
    require(remaining_wall > remaining_calls * old["per_model_seconds"], "原期限不足；不更新期限")
    attempt.mkdir(parents=True)
    code = attempt / "code"
    code.mkdir()
    (code / "recovery").mkdir()
    write(code / "recovery/AUDIT.json", audit)
    audit_sha = sha(code / "recovery/AUDIT.json")
    for name in old["code_sha256"]:
        if name == "run_income_mi_batch.py":
            (code / name).write_bytes(args.coordinator_source.read_bytes())
        else:
            os.link(original / "code" / name, code / name)
    plan = copy.deepcopy(old)
    plan.update(name=old["name"] + "-recovery-01", at=datetime.now(timezone.utc).isoformat(),
                max_new_engine_calls=remaining_calls,
                max_new_engine_seconds=old["max_new_engine_seconds"] - budget["new_engine_seconds"],
                prior_named_engine_calls=old["prior_named_engine_calls"] + budget["new_engine_calls"],
                prior_named_engine_seconds=old["prior_named_engine_seconds"] + budget["new_engine_seconds"],
                max_coordinator_wall_seconds=remaining_wall, resource_wait_seconds=args.resource_wait_seconds)
    for node, item in zip(plan["members"], imported):
        node.update(mode="import", import_directory=item["source_directory"], import_files=item["files"],
                    input_sha256=item["files"]["model.inp"]["sha256"])
        if item["source_node"]["mode"] == "new":
            node["recovered_stage"] = {"original_node": item["source_node"], "original_job_id": old["name"],
                                       "audit_sha256": audit_sha, "r_owner": owner}
    plan["code_sha256"]["run_income_mi_batch.py"] = args.coordinator_sha256
    base = plan["single_model_base"]
    base.update(historical_engine_calls=plan["prior_named_engine_calls"], historical_engine_seconds=plan["prior_named_engine_seconds"],
                new_plus_historical_seconds_ceiling=plan["prior_named_engine_seconds"] + old["per_model_seconds"])
    plan["recovery"] = {"source_job_id": old["name"], "source_plan_sha256": args.plan_sha256,
                        "audit_sha256": audit_sha, "audit_relative_path": "recovery/AUDIT.json",
                        "absolute_original_deadline": datetime.fromtimestamp(deadline, timezone.utc).isoformat(),
                        "source_calls": budget["new_engine_calls"], "source_seconds": budget["new_engine_seconds"],
                        "only_unstarted_nodes_eligible": True, "original_job_not_resubmitted": True}
    route.validate_recovery_plan(plan, old, audit)
    require(plan["single_model_base"]["resources"] == old["single_model_base"]["resources"], "未授权降低资源门槛")
    config = copy.deepcopy(config)
    config.update(coordinator=(code / "run_income_rstudio_batch.py").as_posix(),
                  arguments=["--plan", (code / "BATCH_PLAN.json").as_posix(), "--work", (attempt / "run").as_posix(), "--output", (attempt / "results").as_posix()],
                  channel=(attempt / "rstudio_channel").as_posix(), progress_file=(attempt / "run/PROGRESS.json").as_posix(),
                  result_file=(attempt / "results/BATCH_RESULT.json").as_posix(), maximum_driver_seconds=remaining_wall + 180)
    write(code / "BATCH_PLAN.json", plan)
    write(code / "DRIVER_CONFIG.json", config)
    require(route.pool.file_set(original / "results") == original_files, "准备期间原结果改变")
    for name, pin in source_pins.items():
        require(sha(original / name) == pin, "原来源被改变")
    report = {"status": "PREPARED_ONLY_UNSTARTED_STAGES", "at": datetime.now(timezone.utc).isoformat(),
              "attempt": str(attempt), "plan": str(code / "BATCH_PLAN.json"), "plan_sha256": sha(code / "BATCH_PLAN.json"),
              "config": str(code / "DRIVER_CONFIG.json"), "config_sha256": sha(code / "DRIVER_CONFIG.json"),
              "driver": str(code / "run_rstudio_mplus_batch.R"), "driver_sha256": sha(code / "run_rstudio_mplus_batch.R"),
              "audit_sha256": audit_sha, "imported_stages": len(imported), "completed_primary_MI": sum(n["primary"] for n in completed),
              "source_calls": budget["new_engine_calls"], "source_seconds": budget["new_engine_seconds"],
              "remaining_calls": remaining_calls, "remaining_seconds": plan["max_new_engine_seconds"],
              "first_unstarted_member": audit["first_unstarted_member"], "absolute_deadline": plan["recovery"]["absolute_original_deadline"],
              "resource_wait_seconds": args.resource_wait_seconds, "resource_limits": base["resources"],
              "original_files_unchanged": True, "new_mplus_calls": 0, "data_copies": 0,
              "shared_code_hardlinks": len(old["code_sha256"]) - 1, "review_mode": "solo_self_review"}
    write(attempt / "PREPARATION.json", report)
    print("XDEV_JSON " + json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
