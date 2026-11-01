#!/usr/bin/env python3
"""只读核验符合 saved-batch 合同的 Mplus 输出；不导入 worker，不启动 R/Mplus。

输入合同决定成员集合。成功回执、输入来源、当前输出字节、正常终止和数值
必须同时成立。数据副本已由 worker 删除时，只核其复制回执与原始数据的绑定，
不把这一点写成已独立重读 Windows 运行时数据。
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat


NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?\Z")
NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")
DATE_LINE = re.compile(r"\s*\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)?\s*\Z", re.I)
TIME_LINE = re.compile(r"\s*(?:Beginning Time|Ending Time|Elapsed Time):")
NORMAL = "THE MODEL ESTIMATION TERMINATED NORMALLY"
OUTPUTS = ("model.out", "estimates.dat", "tech3.dat")


class Rejected(ValueError):
    pass


def identity(s):
    # Windows stat/fstat 的 ctime 语义不同；这里只用可比较字段。
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def snapshot(path):
    path = Path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        raise Rejected(f"Not a regular non-symlink file: {path}")
    if before.st_size > 128 * 1024 * 1024:
        raise Rejected(f"File exceeds bounded reader: {path}")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        first = os.fstat(handle.fileno())
        data = handle.read(128 * 1024 * 1024 + 1)
        last = os.fstat(handle.fileno())
    after = path.lstat()
    if not identity(before) == identity(first) == identity(last) == identity(after):
        raise Rejected(f"File changed while reading: {path}")
    if len(data) != first.st_size:
        raise Rejected(f"Short or growing read: {path}")
    pin = {"path": str(path.resolve()), "bytes": len(data),
           "sha256": hashlib.sha256(data).hexdigest(),
           "device": first.st_dev, "inode": first.st_ino,
           "mtime_ns": str(first.st_mtime_ns)}
    return data, pin


def document(path):
    data, pin = snapshot(path)
    return json.loads(data.decode("utf-8-sig")), pin


def safe_name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise Rejected(f"Unsafe member/input name: {value!r}")
    return value


def normalized_out(data):
    # 只排除已声明的时钟行；不消除拟合结果、警告、模型语义或数值差异。
    lines = data.decode("latin-1").splitlines()
    normal = sum(line.strip() == NORMAL for line in lines)
    errors = [line for line in lines if re.match(r"\s*\*{3}\s*ERROR\b", line)]
    if normal != 1 or errors:
        raise Rejected("Output lacks one normal termination or contains an Mplus ERROR")
    return [line for line in lines if not DATE_LINE.fullmatch(line) and not TIME_LINE.match(line)]


def numeric_values(data):
    tokens = data.decode("ascii").split()
    if not tokens:
        raise Rejected("Empty numeric output")
    values = []
    for token in tokens:
        if not NUMBER.fullmatch(token):
            raise Rejected("Non-numeric token in numeric output")
        value = float(token.replace("D", "E").replace("d", "e"))
        if not math.isfinite(value):
            raise Rejected("Non-finite numeric output")
        values.append(value)
    return values


def verify_member(source, returned, member, tolerance, provenance_only):
    src, dst = source / "models" / member, returned / "models" / member
    job, job_pin = document(src / "job.json")
    result, result_pin = document(dst / "RESULT.json")
    if result.get("member") != member:
        raise Rejected("Result member binding differs")
    if result.get("engine_exit_code") != 0 or result.get("engine_state") != "EXITED":
        raise Rejected("Engine did not exit successfully")
    if result.get("status") not in ("PASS_IDENTICAL", "PASS_NUMERIC"):
        raise Rejected("Worker receipt is not a successful result")
    expected = job.get("hashes", {})
    runtime_inputs = {k: v for k, v in expected.items() if k not in provenance_only}
    if not expected or "model.inp" not in expected or result.get("inputs") != runtime_inputs:
        raise Rejected("Staged input hashes do not exactly match the original job")
    pins = [job_pin, result_pin]
    removed = result.get("removed_input_copies", [])
    if not isinstance(removed, list) or len(removed) != len(set(removed)):
        raise Rejected("Invalid removed-input list")
    if not set(removed).issubset(set(expected) - {"model.inp"}):
        raise Rejected("Removed-input list names an undeclared input or model.inp")
    removed_not_reread = []
    excluded, excluded_not_reread = {}, []
    exclusions_path = returned / "RETURN_INPUT_EXCLUSIONS.json"
    if exclusions_path.exists() or exclusions_path.is_symlink():
        exclusions, exclusion_pin = document(exclusions_path)
        binding, binding_pin = document(returned / "BATCH_BINDING.json")
        if not isinstance(exclusions, dict) or not isinstance(exclusions.get("members"), dict) or not isinstance(binding, dict):
            raise Rejected("Invalid returned input-exclusion document")
        entry = exclusions["members"].get(member, {})
        if not isinstance(entry, dict):
            raise Rejected("Invalid member input-exclusion record")
        excluded = entry.get("inputs", {})
        if (exclusions.get("schema") != "mplus-return-input-exclusions/1"
                or exclusions.get("binding_sha256") != binding_pin["sha256"]
                or entry.get("result_sha256") != result_pin["sha256"]
                or binding.get("jobs", {}).get(member, {}).get("inputs") != runtime_inputs
                or not isinstance(excluded, dict) or not set(excluded).issubset(set(runtime_inputs) - {"model.inp"})
                or any(runtime_inputs[name] != pin for name, pin in excluded.items())):
            raise Rejected("Returned input-exclusion receipt is not bound to the original result and inputs")
        pins.extend((exclusion_pin, binding_pin))
    for name, digest in expected.items():
        safe_name(name)
        _, original_pin = snapshot(src / name)
        pins.append(original_pin)
        if original_pin["sha256"] != digest:
            raise Rejected(f"Original input differs from its job: {name}")
        if name in provenance_only:
            # 明确声明的 JSON 起点映射/来源元数据仍核原 SHA，但不冒充引擎读入文件。
            continue
        copy = dst / name
        if copy.exists() or copy.is_symlink():
            _, copied_pin = snapshot(copy)
            pins.append(copied_pin)
            if copied_pin["sha256"] != digest:
                raise Rejected(f"Returned input differs: {name}")
        elif name in removed:
            removed_not_reread.append(name)
        elif name in excluded:
            excluded_not_reread.append(name)
        else:
            raise Rejected(f"Returned input is missing without a removal receipt: {name}")
    comparison = {}
    for name in OUTPUTS:
        original_bytes, original_pin = snapshot(src / name)
        returned_bytes, returned_pin = snapshot(dst / name)
        pins += [original_pin, returned_pin]
        if (original_pin["device"], original_pin["inode"]) == (returned_pin["device"], returned_pin["inode"]):
            raise Rejected(f"Returned output aliases the original file: {name}")
        recorded_hash = result.get("compare", {}).get(name, {}).get("sha_new")
        if recorded_hash != returned_pin["sha256"]:
            raise Rejected(f"Current output differs from its saved receipt: {name}")
        item = {"original_sha256": original_pin["sha256"],
                "returned_sha256": returned_pin["sha256"],
                "byte_identical": original_bytes == returned_bytes}
        if name == "model.out":
            old, new = normalized_out(original_bytes), normalized_out(returned_bytes)
            item["normalized_identical"] = old == new
            if old != new:
                # 输出变化需逐项审阅，不能只因两个数值副文件接近就自动通过。
                raise Rejected("Non-clock model.out differences need explicit review")
        else:
            old, new = numeric_values(original_bytes), numeric_values(returned_bytes)
            if len(old) != len(new):
                raise Rejected(f"Numeric output length differs: {name}")
            difference = max(abs(a - b) for a, b in zip(old, new))
            item.update(count=len(new), max_absolute_difference=difference)
            if difference > tolerance:
                raise Rejected(f"Numeric output exceeds declared tolerance: {name}")
        comparison[name] = item
    original_receipt, original_receipt_pin = document(src / "engine_receipt.json")
    pins.append(original_receipt_pin)
    wall = result.get("wall_seconds")
    if not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall < 0:
        raise Rejected("Invalid engine duration")
    return {"member": member, "status": "OUTPUTS_VERIFIED",
            "wall_seconds": wall,
            "original_wall_seconds": original_receipt.get("wall_seconds"),
            "original_cap_seconds": job.get("cap_seconds"),
            "probe_cap_seconds": result.get("probe_cap_seconds"),
            "provenance_only_inputs_verified": sorted(set(expected) & provenance_only),
            "input_copy_bytes_no_longer_available_for_independent_read": removed_not_reread,
            "input_copy_bytes_excluded_from_return": excluded_not_reread,
            "compare": comparison, "pins": pins}


def verify_batch(source, returned, tolerance=1e-6, provenance_only=()):
    source, returned = Path(source).resolve(), Path(returned).resolve()
    if source == returned:
        raise Rejected("Source and returned batch must be different directories")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise Rejected("Invalid tolerance")
    provenance_only = {safe_name(name) for name in provenance_only}
    if any(not name.endswith(".json") for name in provenance_only):
        raise Rejected("Provenance-only exceptions must be explicitly named JSON metadata")
    contract, contract_pin = document(source / "contracts/RUN_CONTRACT.json")
    members = [safe_name(x) for x in contract["primary_sequence"]]
    if not members or len(members) != len(set(members)):
        raise Rejected("Empty or duplicate expected-member set")
    model_root = returned / "models"
    if model_root.is_symlink():
        raise Rejected("Returned model root is a symlink")
    present = {p.name for p in model_root.iterdir() if p.is_dir() or p.is_symlink()} if model_root.exists() else set()
    errors = []
    if present != set(members):
        errors.append({"scope": "member_set", "missing": sorted(set(members) - present),
                       "extra": sorted(present - set(members))})
    rows = []
    for member in members:
        try:
            dst = model_root / member
            if dst.is_symlink() or dst.resolve() == (source / "models" / member).resolve():
                raise Rejected("Returned member aliases an original or symlink")
            # JSON 元数据若在真实 INP 中被引用，也不能排除出引擎文件集合。
            inp, _ = snapshot(source / "models" / member / "model.inp")
            if any(name.lower().encode("ascii") in inp.lower() for name in provenance_only):
                raise Rejected("A declared provenance-only file is referenced by model.inp")
            rows.append(verify_member(source, returned, member, tolerance, provenance_only))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append({"scope": member, "error": str(exc)})
    report = {"schema": "pp-lgcm-independent-output-readback/1",
              "at": datetime.now(timezone.utc).isoformat(),
              "source": str(source), "returned": str(returned),
              "contract_pin": contract_pin, "numeric_absolute_tolerance": tolerance,
              "declared_provenance_only_files": sorted(provenance_only),
              "expected_members": len(members), "verified_members": len(rows),
              "status": "BATCH_OUTPUTS_VERIFIED" if not errors else "REVIEW_REQUIRED",
              "fault_recovery_acceptance": "SEPARATE_EVIDENCE_REQUIRED",
              "new_engine_calls": 0, "errors": errors, "members": rows}
    # 再核全部已读文件的身份；活跃/改变中的结果不得发布为静态验收。
    for pin in [contract_pin] + [p for row in rows for p in row["pins"]]:
        try:
            s = Path(pin["path"]).stat()
            unchanged = identity(s) == (pin["device"], pin["inode"], pin["bytes"], int(pin["mtime_ns"]))
        except OSError:
            unchanged = False
        if not unchanged:
            report["errors"].append({"scope": "final_stability", "path": pin["path"]})
            report["status"] = "REVIEW_REQUIRED"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--returned", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--absolute-tolerance", type=float, default=1e-6)
    parser.add_argument("--provenance-only-file", action="append", default=[],
                        help="Named JSON metadata in job hashes, verified at source but not read by Mplus")
    args = parser.parse_args()
    report = verify_batch(args.source, args.returned, args.absolute_tolerance, args.provenance_only_file)
    # 新报告专用路径，不覆写旧验收。
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({k: report[k] for k in
                     ("status", "expected_members", "verified_members", "new_engine_calls", "errors")},
                    ensure_ascii=False))
    return 0 if report["status"] == "BATCH_OUTPUTS_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
