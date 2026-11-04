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
HUNK = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# git 的 C 风格引号路径里可能出现的转义
ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


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


def unquote_git_path(raw: str) -> str | None:
    """解开 git 的 C 风格引号路径，如 "b/\\345\\205\\254.md"（八进制是 UTF-8 字节）；格式不对返回 None。"""
    if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        return None
    body, out, index = raw[1:-1], bytearray(), 0
    while index < len(body):
        char = body[index]
        if char != "\\":
            out += char.encode("utf-8")
            index += 1
        elif body[index + 1:index + 2] in ESCAPES:
            out.append(ESCAPES[body[index + 1]])
            index += 2
        elif re.fullmatch(r"[0-7]{3}", body[index + 1:index + 4]):
            out.append(int(body[index + 1:index + 4], 8))
            index += 4
        else:
            return None
    return out.decode("utf-8", errors="replace")


def _target_path(raw: str) -> str | None:
    """`+++ ` 之后的目标路径；删除的文件返回 None。解析不了时保留原文，文件照样扫描。"""
    if raw.endswith("\t"):
        # 路径含空格时 git 在文件头末尾加一个制表符
        raw = raw[:-1]
    if raw == "/dev/null":
        return None
    if raw.startswith('"'):
        raw = unquote_git_path(raw) or raw
    return raw[2:] if raw.startswith("b/") else raw


def parse_added_lines(diff: str):
    """逐个 hunk 按行数计数取新增行，正文以 +++ 开头也不会被误当成文件头。"""
    path, number, old_left, new_left = None, 0, 0, 0
    for line in diff.split("\n"):
        if (old_left > 0 or new_left > 0) and line[:1] in ("+", "-", " ", "\\"):
            if line.startswith("+"):
                if path:
                    yield path, number, line[1:]
                number, new_left = number + 1, new_left - 1
            elif line.startswith("-"):
                old_left -= 1
            elif line.startswith(" "):
                number, old_left, new_left = number + 1, old_left - 1, new_left - 1
            continue
        # 计数用完或遇到非 hunk 行：回到文件头解析
        old_left = new_left = 0
        if line.startswith("diff --git "):
            path = None
        elif line.startswith("+++ "):
            path = _target_path(line[4:])
        elif header := HUNK.match(line):
            old_left = int(header.group(1) if header.group(1) is not None else 1)
            number = int(header.group(2))
            new_left = int(header.group(3) if header.group(3) is not None else 1)


def added_lines(base: str, head: str, prefixes: list[str], cwd=None):
    # 固定输出格式，不受本机 quotePath、noprefix、颜色、外部 diff 等配置影响
    # --text：仓库里的 .gitattributes（如 -diff）不能把文件挤出扫描
    command = ["git", "-c", "core.quotePath=false", "diff", "--text", "--no-color", "--no-ext-diff", "--no-textconv",
               "--src-prefix=a/", "--dst-prefix=b/", "-U0", f"{base}...{head}", "--", *prefixes]
    diff = subprocess.run(command, capture_output=True, check=True, cwd=cwd).stdout
    yield from parse_added_lines(diff.decode("utf-8", errors="replace"))


def _escape(value: str, prop: bool = False) -> str:
    value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return value.replace(":", "%3A").replace(",", "%2C") if prop else value


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
            print(f"::warning file={_escape(path, True)},line={number}::{_escape(message)}")
        else:
            print(f"WARNING {path}:{number}: {message}")
    print(f"public boundary scan: {len(findings)} candidate(s) in added lines (warning only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
