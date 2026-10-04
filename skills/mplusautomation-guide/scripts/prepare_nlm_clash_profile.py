#!/usr/bin/env python3
"""Create an isolated Clash Verge profile with the required NotebookLM rule."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from check_nlm_clash_rule import GROUP, RULE, RULE_VALUE, check_profile


GROUP_BLOCK = """- name: 链式代理-Gemini
  proxies:
  - 链式代理
  type: select
"""


def prepare(source: Path, destination: Path, platform: str) -> dict:
    raw = source.read_text(encoding="utf-8-sig")
    profile_format = "yaml"
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("JSON profile must be an object")
        profile_format = "json"
    except json.JSONDecodeError:
        parsed = None

    if parsed is not None:
        groups = parsed.setdefault("proxy-groups", [])
        if not any(isinstance(item, dict) and item.get("name") == GROUP for item in groups):
            groups.append({"name": GROUP, "proxies": ["链式代理"], "type": "select"})
        rules = parsed.setdefault("rules", [])
        if RULE_VALUE not in [str(item).strip().lstrip("-").strip() for item in rules]:
            broad_index = next(
                (
                    i for i, item in enumerate(rules)
                    if "DOMAIN-KEYWORD,google," in str(item)
                ),
                None,
            )
            insert_at = broad_index if broad_index is not None else 0
            rules.insert(insert_at, RULE_VALUE)
        raw = json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"
    else:
        if f"- name: {GROUP}" not in raw:
            marker = "# 详情请参考：YouTube@IPCheese视频\n# 规则部分"
            if marker not in raw:
                marker = "rules:"
            if marker not in raw:
                raise ValueError("cannot locate rules section marker")
            raw = raw.replace(marker, GROUP_BLOCK + "\n" + marker, 1)
        if RULE_VALUE not in raw:
            broad = "- DOMAIN-KEYWORD,google,链式代理"
            if broad not in raw:
                raise ValueError("cannot locate broad Google rule")
            raw = raw.replace(
                broad,
                RULE + "\n" + broad,
                1,
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(raw, encoding="utf-8-sig" if profile_format == "yaml" else "utf-8", newline="")
    result = check_profile(destination, platform)
    result["source_format"] = profile_format
    result["source_profile"] = str(source)
    result["destination_profile"] = str(destination)
    result["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=("windows", "macos"))
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = prepare(args.source, args.destination, args.platform)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
