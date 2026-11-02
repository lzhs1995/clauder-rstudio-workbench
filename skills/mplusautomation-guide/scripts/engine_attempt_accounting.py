"""读取单调用监督器的原始成本证据；未知退出不变成零成本或已知上界。

本模块不启动、停止或收养引擎，也不判断统计结果能否采用。
只有确切成本全部闭合时，汇总才允许下一个批次沿用数值预算。
"""
import hashlib
import json
import math
from pathlib import Path


def _number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _save_original(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("原成本证据已改变，保留旧件并停止")
    else:
        with path.open("xb") as stream:
            stream.write(raw)


def inspect_attempt(member, work, output, cap_seconds, evidence_root=None):
    """同时识别原直接监督目录与 RStudio adapter 的 guard 子目录。"""
    if not _number(cap_seconds) or cap_seconds <= 0:
        raise ValueError("需要原单模型正数 cap")
    work, output = Path(work), Path(output)
    locations = {"work": work, "guard": work / "guard",
                 "guard_export": work / "guard_export", "export": output}
    names = ("CLAIM.json", "ENGINE_STARTED.json", "ENGINE_RECEIPT.json",
             "RSTUDIO_REQUEST_CLAIM.json")
    evidence, parsed, issues = [], {}, []
    for location, root in locations.items():
        if root.is_symlink():
            issues.append(location + ":SYMLINK_REFUSED")
            continue
        for name in names:
            path = root / name
            try:
                if not path.exists():
                    continue
                if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
                    raise ValueError("成本回执必须是小型普通文件")
                raw = path.read_bytes()
                row = {"location": location, "name": name, "path": str(path),
                       "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                evidence.append(row)
                if evidence_root is not None:
                    saved = Path(evidence_root) / member / location / name
                    _save_original(saved, raw)
                    row["saved_path"] = str(saved)
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError("成本回执不是 JSON 对象")
                parsed[(location, name)] = value
            except (OSError, ValueError, UnicodeError) as error:
                issues.append(location + "/" + name + ":" + repr(error))

    receipts = [value for (location, name), value in parsed.items()
                if name == "ENGINE_RECEIPT.json"]
    valid = [value for value in receipts
             if value.get("member") == member
             and type(value.get("actual_engine_calls")) is int
             and value["actual_engine_calls"] in (0, 1)
             and _number(value.get("elapsed_seconds"))
             and type(value.get("engine_exit_confirmed")) is bool]
    receipt_count = sum(row["name"] == "ENGINE_RECEIPT.json" for row in evidence)
    has_started = any(name == "ENGINE_STARTED.json" for location, name in parsed)
    if has_started and valid and any(value["actual_engine_calls"] == 0 for value in valid):
        issues.append("ENGINE_STARTED 与零调用回执冲突")
    complete_receipt_set = (valid and len(valid) == receipt_count
                            and all(value == valid[0] for value in valid)
                            and not issues)
    has_evidence = bool(evidence or issues or output.exists())
    actual_calls, elapsed, observed = None, None, 0.0
    if complete_receipt_set:
        receipt = valid[0]
        actual_calls = receipt["actual_engine_calls"]
        observed = float(receipt["elapsed_seconds"])
        if receipt["engine_exit_confirmed"]:
            elapsed = observed
            state = "EXACT_TERMINAL_COST"
        else:
            state = "EXIT_UNKNOWN_COST_OPEN"
    elif not has_evidence:
        actual_calls, elapsed, state = 0, 0.0, "NO_START_EVIDENCE"
    else:
        # 有 STARTED 或一致的有效回执可证明调用发生；不凭 CLAIM 猜测是否真正启动。
        if has_started or (valid and all(value["actual_engine_calls"] == 1 for value in valid)):
            actual_calls = 1
        if valid:
            observed = max(float(value["elapsed_seconds"]) for value in valid)
        state = "INCOMPLETE_OR_CONFLICTING_COST_EVIDENCE"
    exact = actual_calls is not None and elapsed is not None
    return {"member": member, "state": state, "actual_engine_calls": actual_calls,
            "elapsed_seconds": elapsed, "observed_elapsed_seconds": observed,
            "reserved_calls": actual_calls if actual_calls is not None else 1,
            "reserved_seconds": elapsed if exact else max(float(cap_seconds), observed),
            "reservation_is_elapsed_upper_bound": False,
            "accounting_complete": exact, "evidence": evidence, "issues": issues}


def totals(entries):
    values = list(entries)
    calls_known = all(value["actual_engine_calls"] is not None for value in values)
    seconds_known = all(value["elapsed_seconds"] is not None for value in values)
    calls = sum(value["actual_engine_calls"] or 0 for value in values)
    seconds = math.fsum(value["elapsed_seconds"] or 0.0 for value in values)
    closed = calls_known and seconds_known and all(value["accounting_complete"] for value in values)
    return {"new_engine_calls": calls if calls_known else None,
            "new_engine_seconds": seconds if seconds_known else None,
            "confirmed_new_engine_calls": calls,
            "confirmed_finished_engine_seconds": seconds,
            "observed_engine_seconds_lower_bound": math.fsum(
                value["observed_elapsed_seconds"] for value in values),
            "reserved_engine_calls": sum(value["reserved_calls"] for value in values),
            "reserved_engine_seconds": math.fsum(value["reserved_seconds"] for value in values),
            "engine_accounting_complete": closed,
            "followup_budget_eligible": closed}


def require_closed_budget(result):
    """新格式的未闭合账本不得被后续计划当作零成本；旧格式仍须有确切数值。"""
    calls, seconds = result.get("new_engine_calls"), result.get("new_engine_seconds")
    if (type(calls) is not int or calls < 0 or not _number(seconds)
            or result.get("engine_accounting_complete", True) is not True
            or result.get("followup_budget_eligible", True) is not True):
        raise ValueError("原调用成本未闭合，不能据此创建后续数值预算")
    return calls, float(seconds)
