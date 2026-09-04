#!/usr/bin/env python3
"""Repository copy of the skill-creator quick validation gate."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


MAX_SKILL_NAME_LENGTH = 64


def validate_skill(skill_path: str) -> tuple[bool, str]:
    skill_md = Path(skill_path) / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"
    content = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid or missing YAML frontmatter"
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        return False, f"Invalid YAML in frontmatter: {error}"
    if not isinstance(frontmatter, dict):
        return False, "Frontmatter must be a YAML dictionary"
    allowed = {"name", "description", "license", "allowed-tools", "metadata"}
    unexpected = set(frontmatter) - allowed
    if unexpected:
        return False, f"Unexpected frontmatter keys: {', '.join(sorted(unexpected))}"
    if "name" not in frontmatter or "description" not in frontmatter:
        return False, "Frontmatter requires name and description"
    name = frontmatter["name"]
    description = frontmatter["description"]
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return False, "Skill name must be lowercase hyphen-case"
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, "Skill name is too long"
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        return False, "Description must be a non-empty string of at most 1024 characters"
    if "<" in description or ">" in description:
        return False, "Description cannot contain angle brackets"
    if re.search(r"(?m)^ {0,3}\[TODO:[^\n]*\]\s*$", content[match.end():]):
        return False, "Skill contains an unfinished TODO"
    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        raise SystemExit(1)
    valid, message = validate_skill(sys.argv[1])
    print(message)
    raise SystemExit(0 if valid else 1)
