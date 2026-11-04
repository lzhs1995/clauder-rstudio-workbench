#!/usr/bin/env python3
"""公开仓库边界扫描：只看 PR 新增行，找疑似估计值、本机路径与精确小数，只发警告。

这是启发式检查：命中不一定违规，没命中也不保证合规；结论由人审确认。
用法：python .github/scripts/public_boundary_scan.py <base> <head> [--path 前缀 ...] [--github]
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import PurePosixPath

PRIVATE_PATH = re.compile(r"/Users/[A-Za-z0-9_.-]+|[A-Za-z]:[\\/]+Users[\\/]|\\\\wsl(?:\.localhost)?\\|/home/(?!runner\b)[a-z0-9_-]+/")
ESTIMATE_KEYS = (r"(?:LL|loglik\w*|log-likelihood|aBIC|BIC|AIC|SE|S\.E\.|CI|OR|beta|β|coef\w*|estimate[sd]?|"
                 r"entropy|Entropy|系数|标准误|置信区间|似然|类别比例|转移概率)")
ESTIMATE = re.compile(r"(?<![A-Za-z])" + ESTIMATE_KEYS + r"(?![A-Za-z])[^\n\d]{0,12}?(-?\d+(?:\.\d+)?)")
PRECISE = re.compile(r"(?<![\w.])-?\d+\.\d{3,}(?![\w.]|e-)")
SKIP_SUFFIX = {".png", ".pdf", ".rds", ".dta", ".zip", ".gz"}
MAX_ANNOTATIONS = 20


def scan_line(path: str, text: str) -> list[str]:
    hits = [f"local path {m.group(0)!r}" for m in PRIVATE_PATH.finditer(text)]
    for m in ESTIMATE.finditer(text):
        # 三位以内的整数多为编号或计数，不报
        if not re.fullmatch(r"-?\d{1,3}", m.group(1)):
            hits.append(f"estimate-like value {m.group(0)[:60]!r}")
    if PurePosixPath(path).suffix == ".md":
        # 代码里的容差与阈值常有多位小数，只在文档里报
        hits += [f"precise decimal {m.group(0)!r}" for m in PRECISE.finditer(text)]
    return hits


def added_lines(base: str, head: str, prefixes: list[str]):
    diff = subprocess.run(["git", "diff", "-U0", f"{base}...{head}", "--", *prefixes],
                          capture_output=True, text=True, check=True).stdout
    path, number = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
            continue
        header = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if header:
            number = int(header.group(1))
            continue
        if path and line.startswith("+"):
            yield path, number, line[1:]
            number += 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("--path", action="append", default=[], help="only scan these path prefixes")
    parser.add_argument("--github", action="store_true", help="emit GitHub warning annotations")
    args = parser.parse_args(argv)
    findings = []
    for path, number, text in added_lines(args.base, args.head, args.path):
        if PurePosixPath(path).suffix.lower() in SKIP_SUFFIX:
            continue
        findings += [(path, number, hit) for hit in scan_line(path, text)]
    for index, (path, number, hit) in enumerate(findings):
        message = f"PROGRAM rule 9 candidate: {hit}; public files must not contain thesis estimates, IDs, local paths or descriptive statistics beyond counts"
        if args.github and index < MAX_ANNOTATIONS:
            print(f"::warning file={path},line={number}::{message}")
        else:
            print(f"WARNING {path}:{number}: {message}")
    print(f"public boundary scan: {len(findings)} candidate(s) in added lines (warning only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
