#!/usr/bin/env python3
"""mplusautomation-guide 家族注册表：校验、生成人读视图、核真实数据回执。

只用标准库。子命令：
  check [--strict] [--github]   校验 families.json、生成视图与回执；回执过期只警告（--strict 时算错误）
  render [--check]              生成 references/family-registry.md 与 SKILL.md 家族表；--check 只比对
  receipt-template FAMILY DATASET ROUTE   打印一份白名单回执骨架，code_sha256 按当前文件计算
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
REGISTRY = SKILL_ROOT / "families.json"
REGISTRY_DOC = SKILL_ROOT / "references" / "family-registry.md"
SKILL_MD = SKILL_ROOT / "SKILL.md"
RECEIPT_DIR = SKILL_ROOT / "assets" / "real_data_receipts"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

TOP_KEYS = {"schema_version", "description", "routes", "adapters", "datasets", "execution", "tests", "families"}
CODE_STATUS = ("none", "doc_only", "template", "configurable")
EVIDENCE_KINDS = ("synthetic_compile", "native_synthetic", "real_data_swap", "historical_replay")
EVIDENCE_STATUS = ("pass", "archived_readback_only", "pending", "not_started", "not_applicable")
DATA_FORMATS = ("csv", "dta", "archived_dat", "in_memory")
ADAPTER_STATUS = ("implemented", "planned")
TEST_ARGS = ("skill_root", "scripts_dir", "out_dir", "engine", "python")
FAMILY_KEYS = {"aliases", "label_zh", "summary", "routes", "code_status", "data_formats", "docs",
               "acceptance_doc", "tests", "evidence", "freshness_files", "thesis_refs", "gaps"}
RECEIPT_REQUIRED = {"schema_version", "family", "dataset", "route", "generated_taipei", "data_sha256",
                    "code_sha256", "rows", "columns", "verdict", "evidence_logical_name"}
RECEIPT_OPTIONAL = {"platform", "output_sha256", "column_names", "missing_by_column", "comparisons"}
# 本机路径（Mac/Linux 用户目录、Windows 盘符、WSL 共享路径）
PRIVATE_PATH = re.compile(r"/Users/[^\s/]+|/home/[^\s/]+|[A-Za-z]:[\\/]|\\\\wsl")
SHA256 = re.compile(r"[0-9a-f]{64}")
SKILL_MARK = ("<!-- family-registry:start -->", "<!-- family-registry:end -->")
TAIPEI = timezone(timedelta(hours=8))
EVIDENCE_LABEL = {"pass": "pass", "archived_readback_only": "readback", "pending": "pending",
                  "not_started": "—", "not_applicable": "n/a"}


def load(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text_file(path: Path) -> str:
    """按 LF 换行计算哈希，避免 Windows 检出的 CRLF 造成假过期。"""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _strings(value, where="families.json"):
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key, where)
            yield from _strings(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{where}[{index}]")


def _defines(path: Path, name: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".R":
        return re.search(rf"(?m)^{re.escape(name)}\s*<-\s*function\b", text) is not None
    return re.search(rf"(?m)^def {re.escape(name)}\(", text) is not None


def _rel_file(rel, where, errors, root=SKILL_ROOT, must_exist=True) -> Path | None:
    """路径必须相对 skill 根、不得越界，且（默认）文件存在。"""
    if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in Path(rel).parts or "\\" in rel:
        errors.append(f"{where}: invalid relative path {rel!r}")
        return None
    path = root / rel
    if must_exist and not path.is_file():
        errors.append(f"{where}: missing file {rel}")
        return None
    return path


def _entry(spec, where, errors, root):
    if not isinstance(spec, str) or ":" not in spec:
        errors.append(f"{where}: entry must be 'file:function', got {spec!r}")
        return
    rel, name = spec.rsplit(":", 1)
    path = _rel_file(rel, where, errors, root)
    if path is not None and not _defines(path, name):
        errors.append(f"{where}: {rel} does not define {name}")


def _workflow_mentions(workflow: str, test: dict, root_repo: Path) -> bool:
    text = (root_repo / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    if test["lang"] == "R":
        # R 测试由注册表驱动脚本统一调用，workflow 必须调用该脚本
        return "run_family_ci_tests.R" in text
    return Path(test["path"]).name in text or Path(test["path"]).stem in text


def validate(reg: dict, root: Path = SKILL_ROOT, repo: Path = REPO_ROOT) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)。errors 让 CI 失败；warnings 只提示。"""
    errors: list[str] = []
    warnings: list[str] = []
    if set(reg) != TOP_KEYS:
        errors.append(f"top-level keys must be {sorted(TOP_KEYS)}, got {sorted(reg)}")
        return errors, warnings
    if reg["schema_version"] != 1:
        errors.append("schema_version must be 1")
    for where, text in _strings(reg):
        if PRIVATE_PATH.search(text):
            errors.append(f"{where}: local absolute path is not allowed in a public registry")
    for rid, route in reg["routes"].items():
        for spec in route.get("entry_functions", []):
            _entry(spec, f"routes.{rid}", errors, root)
        if route.get("config_example"):
            _rel_file(route["config_example"], f"routes.{rid}.config_example", errors, root)
        for doc in route.get("docs", []):
            _rel_file(doc, f"routes.{rid}.docs", errors, root)
    for aid, adapter in reg["adapters"].items():
        if adapter.get("status") not in ADAPTER_STATUS:
            errors.append(f"adapters.{aid}: status must be one of {ADAPTER_STATUS}")
        if adapter.get("status") == "implemented" and not adapter.get("entry_functions"):
            errors.append(f"adapters.{aid}: implemented adapter needs entry_functions")
        for spec in adapter.get("entry_functions", []):
            _entry(spec, f"adapters.{aid}", errors, root)
        for fmt in adapter.get("formats", []):
            if fmt not in DATA_FORMATS:
                errors.append(f"adapters.{aid}: unknown format {fmt}")
        for doc in adapter.get("docs", []):
            _rel_file(doc, f"adapters.{aid}.docs", errors, root)
    for did, dataset in reg["datasets"].items():
        if dataset.get("variable_map_template"):
            _rel_file(dataset["variable_map_template"], f"datasets.{did}", errors, root)
        for doc in dataset.get("docs", []):
            _rel_file(doc, f"datasets.{did}.docs", errors, root)
    for eid, layer in reg["execution"].items():
        for rel in layer.get("scripts", []) + layer.get("docs", []):
            _rel_file(rel, f"execution.{eid}", errors, root)
    _validate_tests(reg["tests"], errors, root, repo)
    _validate_families(reg, errors, warnings, root)
    return errors, warnings


def _validate_tests(tests: dict, errors: list[str], root: Path, repo: Path) -> None:
    for tid, test in tests.items():
        where = f"tests.{tid}"
        path = _rel_file(test.get("path"), where, errors, root)
        if test.get("lang") not in ("R", "python"):
            errors.append(f"{where}: lang must be R or python")
            continue
        if not isinstance(test.get("needs_mplus"), bool):
            errors.append(f"{where}: needs_mplus must be true or false")
        bad_os = [o for o in test.get("ci_os", []) if o not in ("Linux", "macOS", "Windows")]
        if bad_os:
            errors.append(f"{where}: ci_os values must be Linux, macOS or Windows; got {bad_os}")
        bad_args = [a for a in test.get("args", []) if a not in TEST_ARGS]
        if bad_args:
            errors.append(f"{where}: unknown args {bad_args}; allowed {TEST_ARGS}")
        if path is not None and test.get("function") and not _defines(path, test["function"]):
            errors.append(f"{where}: {test['path']} does not define {test['function']}")
        workflow = test.get("ci")
        if workflow is None:
            continue
        if test.get("needs_mplus"):
            errors.append(f"{where}: a test that needs Mplus cannot run on hosted CI")
        if test["lang"] == "R" and not test.get("function"):
            errors.append(f"{where}: CI R tests need a function name for the registry runner")
        if not (repo / ".github" / "workflows" / workflow).is_file():
            errors.append(f"{where}: CI workflow {workflow} does not exist")
        elif not _workflow_mentions(workflow, test, repo):
            errors.append(f"{where}: {workflow} does not invoke {test['path']}")
    registered = {t.get("path") for t in tests.values()}
    for path in sorted((root / "scripts").glob("test_*")):
        rel = f"scripts/{path.name}"
        if rel not in registered:
            errors.append(f"scripts test {rel} is not registered in families.json tests")


def _validate_families(reg: dict, errors: list[str], warnings: list[str], root: Path) -> None:
    names: dict[str, str] = {}
    for fid, fam in reg["families"].items():
        where = f"families.{fid}"
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", fid):
            errors.append(f"{where}: family id must be letters, digits or underscore")
        if set(fam) != FAMILY_KEYS:
            errors.append(f"{where}: keys must be {sorted(FAMILY_KEYS)}; diff {sorted(set(fam) ^ FAMILY_KEYS)}")
            continue
        for name in [fid] + fam["aliases"]:
            key = name.casefold()
            if key in names:
                errors.append(f"{where}: name {name!r} already used by {names[key]}")
            names[key] = fid
        for route in fam["routes"]:
            if route not in reg["routes"]:
                errors.append(f"{where}: unknown route {route}")
        if fam["code_status"] not in CODE_STATUS:
            errors.append(f"{where}: code_status must be one of {CODE_STATUS}")
        for fmt in fam["data_formats"]:
            if fmt not in DATA_FORMATS:
                errors.append(f"{where}: unknown data format {fmt}")
        for rel in fam["docs"] + fam["freshness_files"] + ([fam["acceptance_doc"]] if fam["acceptance_doc"] else []):
            _rel_file(rel, where, errors, root)
        for tid in fam["tests"]:
            if tid not in reg["tests"]:
                errors.append(f"{where}: unknown test {tid}")
        ci_tests = [t for t in fam["tests"] if reg["tests"].get(t, {}).get("ci")]
        if fam["code_status"] == "configurable":
            if not any(reg["routes"].get(r, {}).get("entry_functions") for r in fam["routes"]):
                errors.append(f"{where}: configurable family needs a route with entry functions")
            if not ci_tests:
                errors.append(f"{where}: configurable family needs at least one CI test")
        if fam["code_status"] != "none" and not fam["docs"]:
            errors.append(f"{where}: families with code need docs")
        _validate_evidence(fid, fam, reg, errors, root)


def _validate_evidence(fid: str, fam: dict, reg: dict, errors: list[str], root: Path) -> None:
    evidence = fam["evidence"]
    where = f"families.{fid}.evidence"
    if set(evidence) != set(EVIDENCE_KINDS):
        errors.append(f"{where}: kinds must be exactly {EVIDENCE_KINDS}")
        return
    for kind in EVIDENCE_KINDS:
        item = evidence[kind]
        status, source = item.get("status"), item.get("source")
        if status not in EVIDENCE_STATUS:
            errors.append(f"{where}.{kind}: status must be one of {EVIDENCE_STATUS}")
            continue
        if status not in ("pass", "archived_readback_only"):
            continue
        if not source:
            errors.append(f"{where}.{kind}: {status} needs a source (test id or skill file)")
        elif kind == "real_data_swap":
            # 真实换源的 pass 只能由白名单回执作证
            path = _rel_file(source, f"{where}.{kind}", errors, root)
            if path is not None and Path(source).parent != Path("assets/real_data_receipts"):
                errors.append(f"{where}.{kind}: source must be a receipt under assets/real_data_receipts/")
            elif path is not None:
                receipt = json.loads(path.read_text(encoding="utf-8"))
                if receipt.get("family") != fid or receipt.get("verdict") != "PASS":
                    errors.append(f"{where}.{kind}: receipt must be a PASS receipt for {fid}")
        elif source in reg["tests"]:
            if not reg["tests"][source].get("ci"):
                errors.append(f"{where}.{kind}: test {source} is not run by any CI workflow")
        else:
            _rel_file(source, f"{where}.{kind}", errors, root)


def validate_receipt(receipt, name: str = "receipt") -> list[str]:
    """白名单回执：多一个键都不行，所以估计值没有地方可写。"""
    errors: list[str] = []
    if not isinstance(receipt, dict):
        return [f"{name}: receipt must be a JSON object"]
    extra = set(receipt) - RECEIPT_REQUIRED - RECEIPT_OPTIONAL
    missing = RECEIPT_REQUIRED - set(receipt)
    if extra:
        errors.append(f"{name}: keys outside the public whitelist {sorted(extra)}")
    if missing:
        errors.append(f"{name}: missing keys {sorted(missing)}")
    if errors:
        return errors
    for where, text in _strings(receipt, name):
        if PRIVATE_PATH.search(text):
            errors.append(f"{where}: local absolute path is not allowed")
    if receipt["schema_version"] != 1:
        errors.append(f"{name}: schema_version must be 1")
    if receipt["verdict"] not in ("PASS", "FAIL"):
        errors.append(f"{name}: verdict must be PASS or FAIL")
    if not SHA256.fullmatch(str(receipt["data_sha256"])):
        errors.append(f"{name}: data_sha256 must be a lowercase sha256")
    hashes = list(receipt["code_sha256"].values()) if isinstance(receipt["code_sha256"], dict) else [None]
    hashes += list(receipt.get("output_sha256", {}).values()) if isinstance(receipt.get("output_sha256", {}), dict) else [None]
    if not receipt["code_sha256"] or not all(isinstance(h, str) and SHA256.fullmatch(h) for h in hashes):
        errors.append(f"{name}: code_sha256/output_sha256 must map names to sha256 values")
    for key in ("rows", "columns"):
        if not isinstance(receipt[key], int) or isinstance(receipt[key], bool) or receipt[key] < 0:
            errors.append(f"{name}: {key} must be a nonnegative integer")
    counts = receipt.get("missing_by_column", {})
    if not isinstance(counts, dict) or not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in counts.values()):
        errors.append(f"{name}: missing_by_column must map column names to nonnegative integer counts")
    comparisons = receipt.get("comparisons")
    if comparisons is not None:
        if not isinstance(comparisons, dict) or set(comparisons) - {"verdict", "items", "max_abs_diff"}:
            errors.append(f"{name}: comparisons may only contain verdict, items, max_abs_diff")
        else:
            if comparisons.get("verdict") not in (None, "PASS", "FAIL"):
                errors.append(f"{name}: comparisons.verdict must be PASS or FAIL")
            if "items" in comparisons and (not isinstance(comparisons["items"], int) or isinstance(comparisons["items"], bool)):
                errors.append(f"{name}: comparisons.items must be an integer count")
            if "max_abs_diff" in comparisons and not isinstance(comparisons["max_abs_diff"], (int, float)):
                errors.append(f"{name}: comparisons.max_abs_diff must be a number")
    if "column_names" in receipt and not all(isinstance(c, str) for c in receipt["column_names"]):
        errors.append(f"{name}: column_names must be strings")
    platform = receipt.get("platform", {})
    if not isinstance(platform, dict) or set(platform) - {"os", "r", "mplus"} or not all(isinstance(v, str) for v in platform.values()):
        errors.append(f"{name}: platform may only contain os, r, mplus strings")
    return errors


def check_receipts(reg: dict, root: Path = SKILL_ROOT) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """校验目录下全部回执；返回 (errors, stale_warnings, 每个家族的有效回执文件名)。"""
    errors: list[str] = []
    warnings: list[str] = []
    by_family: dict[str, list[str]] = {fid: [] for fid in reg["families"]}
    directory = root / "assets" / "real_data_receipts"
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f"{path.name}: invalid JSON ({error})")
            continue
        found = validate_receipt(receipt, path.name)
        if found:
            errors.extend(found)
            continue
        fid = receipt["family"]
        if fid not in reg["families"]:
            errors.append(f"{path.name}: unknown family {fid}")
            continue
        by_family[fid].append(path.name)
        expected = set(reg["families"][fid]["freshness_files"])
        recorded = receipt["code_sha256"]
        if set(recorded) != expected:
            warnings.append(f"{path.name}: code_sha256 files differ from {fid} freshness_files")
        for rel in sorted(expected & set(recorded)):
            target = root / rel
            if not target.is_file() or sha256_text_file(target) != recorded[rel]:
                warnings.append(f"{path.name}: {rel} changed since this receipt; rerun the real-data swap")
    return errors, warnings, by_family


def receipt_template(reg: dict, family: str, dataset: str, route: str, root: Path = SKILL_ROOT) -> dict:
    fam = reg["families"][family]
    return {
        "schema_version": 1, "family": family, "dataset": dataset, "route": route,
        "generated_taipei": datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "platform": {"os": "", "r": "", "mplus": ""},
        "data_sha256": "", "code_sha256": {rel: sha256_text_file(root / rel) for rel in fam["freshness_files"]},
        "output_sha256": {}, "rows": 0, "columns": 0, "column_names": [], "missing_by_column": {},
        "comparisons": {"verdict": "PASS", "items": 0, "max_abs_diff": 0},
        "verdict": "FAIL", "evidence_logical_name": "",
    }


def _link(rel: str, from_dir: str) -> str:
    """把相对 skill 根的路径换成从 from_dir 出发的 markdown 链接。"""
    target = Path(rel)
    up = Path(os.path.relpath(target, from_dir)) if from_dir else target
    return f"[{target.name}]({up.as_posix()})"


def _ev(item: dict) -> str:
    # 带限定说明的格子加 *，避免短表把有条件的结论读成无条件
    return EVIDENCE_LABEL[item["status"]] + ("*" if item.get("note") else "")


def render_doc(reg: dict) -> str:
    lines = [
        "# Model family registry",
        "",
        "<!-- Generated by scripts/family_registry.py render from families.json; do not edit by hand. -->",
        "",
        "Each family records its executable route, code status and evidence layer separately.",
        "`configurable` means a reviewed config compiler exists; `template` means a reviewed `[[init]]`",
        "template or external project driver is required; `doc_only` means the skill has guidance but",
        "no executable entry. Evidence values: `pass`, `readback` (archived outputs read and redrawn,",
        "no fresh estimation), `pending`, `—` (not started), `n/a`; `*` means the family section below",
        "states a limit on that evidence.",
        "",
        "For changing data sources or variables, follow",
        "[the source and variable swap contract](family-source-swap-contract.md).",
        "",
        "| Family | Code | Routes | Synthetic compile | Native synthetic | Real-data swap | Historical replay |",
        "|---|---|---|---|---|---|---|",
    ]
    for fid, fam in reg["families"].items():
        ev = fam["evidence"]
        lines.append(f"| {fid} | {fam['code_status']} | {', '.join(fam['routes'])} | " +
                     " | ".join(_ev(ev[k]) for k in EVIDENCE_KINDS) + " |")
    for fid, fam in reg["families"].items():
        lines += ["", f"## {fid}", "", f"{fam['label_zh']}：{fam['summary']}", ""]
        if fam["aliases"]:
            lines.append(f"- Aliases: {', '.join(fam['aliases'])}")
        lines.append(f"- Data formats: {', '.join(fam['data_formats'])}")
        for route in fam["routes"]:
            entries = reg["routes"][route]["entry_functions"]
            lines.append(f"- Route `{route}`: " + (", ".join(f"`{e}`" for e in entries) or "no entry function"))
        if fam["docs"]:
            lines.append("- Docs: " + ", ".join(_link(d, "references") for d in fam["docs"]))
        if fam["acceptance_doc"]:
            lines.append(f"- Acceptance: {_link(fam['acceptance_doc'], 'references')}")
        tests = [reg["tests"][t] for t in fam["tests"]]
        if tests:
            lines.append("- Tests: " + ", ".join(
                f"`{t['path']}` ({'needs Mplus' if t['needs_mplus'] else 'CI ' + t['ci'] if t['ci'] else 'local'})" for t in tests))
        for kind in EVIDENCE_KINDS:
            item = fam["evidence"][kind]
            note = f"; {item['note']}" if item.get("note") else ""
            source = f"; source `{item['source']}`" if item.get("source") else ""
            lines.append(f"- {kind}: {item['status']}{source}{note}")
        if fam["thesis_refs"]:
            lines.append(f"- Thesis: {', '.join(fam['thesis_refs'])}")
        for gap in fam["gaps"]:
            lines.append(f"- Gap: {gap}")
    lines += ["", "## Shared layers", ""]
    for aid, adapter in reg["adapters"].items():
        lines.append(f"- Adapter `{aid}` ({adapter['status']}; {', '.join(adapter['formats'])}): " +
                     ", ".join(_link(d, "references") for d in adapter["docs"]))
    for did, dataset in reg["datasets"].items():
        template = f"template {_link(dataset['variable_map_template'], 'references')}; " if dataset["variable_map_template"] else ""
        lines.append(f"- Dataset `{did}`: {template}" + ", ".join(_link(d, "references") for d in dataset["docs"]))
    for eid, layer in reg["execution"].items():
        lines.append(f"- Execution `{eid}`: " + ", ".join(f"`{s}`" for s in layer["scripts"]) + "; " +
                     ", ".join(_link(d, "references") for d in layer["docs"]))
    return "\n".join(lines) + "\n"


def render_skill_block(reg: dict) -> str:
    lines = [SKILL_MARK[0],
             "| Family | Code | Synthetic | Native | Real-data swap | Historical | Start here |",
             "|---|---|---|---|---|---|---|"]
    for fid, fam in reg["families"].items():
        ev = fam["evidence"]
        start = _link(fam["docs"][0], "") if fam["docs"] else "—"
        lines.append(f"| {fid} | {fam['code_status']} | " + " | ".join(_ev(ev[k]) for k in EVIDENCE_KINDS) + f" | {start} |")
    lines.append("")
    lines.append("`*`: the evidence has a stated limit; see [family-registry.md](references/family-registry.md).")
    lines.append(SKILL_MARK[1])
    return "\n".join(lines)


def replace_skill_block(skill_text: str, block: str) -> str:
    start, end = skill_text.find(SKILL_MARK[0]), skill_text.find(SKILL_MARK[1])
    if start < 0 or end < start or skill_text.count(SKILL_MARK[0]) != 1:
        raise ValueError("SKILL.md must contain exactly one family-registry marker block")
    return skill_text[:start] + block + skill_text[end + len(SKILL_MARK[1]):]


def render_outputs(reg: dict, root: Path = SKILL_ROOT) -> dict[Path, str]:
    skill = (root / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    return {root / "references" / "family-registry.md": render_doc(reg),
            root / "SKILL.md": replace_skill_block(skill, render_skill_block(reg))}


def stale_renders(reg: dict, root: Path = SKILL_ROOT) -> list[str]:
    stale = []
    try:
        outputs = render_outputs(reg, root)
    except ValueError as error:
        return [f"SKILL.md ({error})"]
    for path, text in outputs.items():
        current = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.is_file() else None
        if current != text:
            stale.append(path.relative_to(root).as_posix())
    return stale


def _annotate(github: bool, level: str, message: str) -> None:
    print(f"::{level}::{message}" if github else f"{level.upper()}: {message}")


def _summary(reg: dict, by_family: dict[str, list[str]]) -> str:
    rows = ["### mplusautomation-guide real-data swap coverage", "",
            "| Family | real_data_swap | Receipts |", "|---|---|---|"]
    for fid, fam in reg["families"].items():
        rows.append(f"| {fid} | {fam['evidence']['real_data_swap']['status']} | {len(by_family.get(fid, []))} |")
    return "\n".join(rows) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--strict", action="store_true", help="treat stale or missing real-data receipts as errors (release gate)")
    check.add_argument("--github", action="store_true", help="emit GitHub annotations and a job summary")
    render = sub.add_parser("render")
    render.add_argument("--check", action="store_true")
    template = sub.add_parser("receipt-template")
    template.add_argument("family")
    template.add_argument("dataset")
    template.add_argument("route")
    args = parser.parse_args(argv)
    reg = load()
    if args.command == "receipt-template":
        print(json.dumps(receipt_template(reg, args.family, args.dataset, args.route), ensure_ascii=False, indent=1))
        return 0
    if args.command == "render":
        if args.check:
            stale = stale_renders(reg)
            for rel in stale:
                print(f"ERROR: {rel} is out of date; run python scripts/family_registry.py render")
            return 1 if stale else 0
        for path, text in render_outputs(reg).items():
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(SKILL_ROOT).as_posix()}")
        return 0
    errors, warnings = validate(reg)
    receipt_errors, stale, by_family = check_receipts(reg)
    errors += receipt_errors + [f"{rel} is out of date; run python scripts/family_registry.py render" for rel in stale_renders(reg)]
    missing = [fid for fid, fam in reg["families"].items()
               if fam["evidence"]["real_data_swap"]["status"] not in ("pass", "not_applicable")]
    if missing:
        warnings.append("families without a passing real-data swap receipt: " + ", ".join(missing))
    warnings += stale
    for message in errors:
        _annotate(args.github, "error", message)
    for message in warnings:
        _annotate(args.github, "error" if args.strict else "warning", message)
    if args.github and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(_summary(reg, by_family))
    print(f"family registry: {len(reg['families'])} families, {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
