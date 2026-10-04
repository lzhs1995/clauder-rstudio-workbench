#!/usr/bin/env python3
"""Read-only checker for the required NotebookLM Clash Verge rule.

Clash Verge exports are commonly YAML, while the Windows profile export used
by the MacBook setup can be JSON.  The checker therefore validates the parsed
``proxy-groups`` and ``rules`` collections first and only falls back to line
matching when a profile is not parseable.  It never prints profile contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml


RULE_VALUE = "DOMAIN-SUFFIX,notebooklm.google.com,链式代理-Gemini"
RULE = f"- {RULE_VALUE}"
GROUP = "链式代理-Gemini"


def _parse_profile(raw: str) -> tuple[str, dict | None]:
    """Return the detected format and parsed mapping, without changing input."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return "json", parsed
    except json.JSONDecodeError:
        pass
    try:
        parsed = yaml.safe_load(raw)
        if isinstance(parsed, dict):
            return "yaml", parsed
    except yaml.YAMLError:
        pass
    return "text", None


def _as_rule(value: object) -> str:
    """Normalize a parsed rule or a textual rule to its value form."""
    return str(value).strip().lstrip("-").strip()


def _line_numbers(lines: list[str], needle: str) -> list[int]:
    return [i + 1 for i, line in enumerate(lines) if needle in line]


def check_profile(path: Path, platform: str) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    lines = raw.splitlines()
    profile_format, parsed = _parse_profile(raw)
    parsed_groups = []
    parsed_rules = []
    if parsed is not None:
        parsed_groups = parsed.get("proxy-groups", []) or []
        parsed_rules = parsed.get("rules", []) or []
    group_values = [
        item.get("name") for item in parsed_groups
        if isinstance(item, dict) and item.get("name") is not None
    ]
    rule_values = [_as_rule(item) for item in parsed_rules]
    if parsed is not None:
        rule_count = sum(item == RULE_VALUE for item in rule_values)
        group_count = sum(value == GROUP for value in group_values)
        google_indexes = [
            i for i, item in enumerate(rule_values)
            if "DOMAIN-KEYWORD,google," in item
        ]
        parsed_rule_index = next(
            (i for i, item in enumerate(rule_values) if item == RULE_VALUE), None
        )
        rule_line_numbers = _line_numbers(lines, RULE_VALUE)
        broad_line_numbers = _line_numbers(lines, "DOMAIN-KEYWORD,google,")
    else:
        rule_line_numbers = [
            i for i, line in enumerate(lines, start=1)
            if line.strip().lstrip("-").strip().startswith(RULE_VALUE)
        ]
        group_line_numbers = [
            i for i, line in enumerate(lines, start=1)
            if line.strip() == f"- name: {GROUP}"
        ]
        broad_line_numbers = [
            i for i, line in enumerate(lines, start=1)
            if "DOMAIN-KEYWORD,google," in line and line.strip().startswith("-")
        ]
        rule_count = len(rule_line_numbers)
        group_count = len(group_line_numbers)
        parsed_rule_index = rule_line_numbers[0] - 1 if rule_line_numbers else None
        google_indexes = [line - 1 for line in broad_line_numbers]
    reasons = []
    if not rule_count:
        reasons.append("exact NotebookLM rule is missing")
    if rule_count > 1:
        reasons.append("exact NotebookLM rule appears more than once")
    if not group_count:
        reasons.append("target proxy group is missing")
    if parsed_rule_index is not None and google_indexes and parsed_rule_index > google_indexes[0]:
        reasons.append("NotebookLM rule appears after the broad Google rule")
    return {
        "platform": platform,
        "profile": str(path),
        "profile_format": profile_format,
        "profile_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "required_rule": RULE,
        "required_rule_value": RULE_VALUE,
        "rule_count": rule_count,
        "group_count": group_count,
        "rule_line": rule_line_numbers[0] if rule_line_numbers else None,
        "broad_google_rule_line": broad_line_numbers[0] if broad_line_numbers else None,
        "status": "PASS" if not reasons else "BLOCKED",
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=("windows", "macos"))
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = check_profile(args.profile, args.platform)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
