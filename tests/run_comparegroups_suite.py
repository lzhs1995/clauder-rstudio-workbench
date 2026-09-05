#!/usr/bin/env python3
"""Run comparegroups-guide gates without allowing one command to mask another."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def run(name: str, command: list[str], env: dict[str, str]) -> dict[str, object]:
    print(f"SUITE_START name={name} command={command!r}", flush=True)
    completed = subprocess.run(command, cwd=REPO, env=env, check=False)
    print(f"SUITE_END name={name} exit_code={completed.returncode}", flush=True)
    return {"name": name, "command": command, "exit_code": completed.returncode}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-python", action="store_true", help="run the repository-wide Python suite")
    parser.add_argument("--report", type=Path, help="optional durable JSON report path")
    args = parser.parse_args()

    rscript = shutil.which("Rscript")
    if not rscript:
        print("Rscript is required", file=sys.stderr)
        return 2

    env = os.environ.copy()
    package_root = str(REPO / "skills" / "clauder-rstudio-workbench")
    env["PYTHONPATH"] = package_root + os.pathsep + env.get("PYTHONPATH", "")
    version_probe = subprocess.run(
        [rscript, "-e", 'cat(R.version.string, "\\n", as.character(packageVersion("compareGroups")), "\\n", sep="")'],
        cwd=REPO,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    version_lines = version_probe.stdout.splitlines()
    r_runtime = {
        "probe_exit_code": version_probe.returncode,
        "r_version": version_lines[0] if len(version_lines) >= 1 else "",
        "comparegroups_version": version_lines[1] if len(version_lines) >= 2 else "",
    }
    python_target = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
        "-v",
    ] if args.full_python else [sys.executable, "-m", "unittest", "tests.test_comparegroups_guide", "-v"]

    commands = [
        ("python", python_target),
        ("r", [rscript, "tests/test_comparegroups_guide.R"]),
        ("non_vacuity", [sys.executable, "tests/prove_comparegroups_non_vacuity.py"]),
        ("skill_workbench", [sys.executable, ".github/scripts/quick_validate.py", "skills/clauder-rstudio-workbench"]),
        ("skill_cmaverse", [sys.executable, ".github/scripts/quick_validate.py", "skills/cmaverse-paired-mval"]),
        ("skill_comparegroups", [sys.executable, ".github/scripts/quick_validate.py", "skills/comparegroups-guide"]),
        ("privacy", [sys.executable, "-m", "unittest", "tests.test_discovery_redaction_v044", "-v"]),
    ]
    results = [run(name, command, env) for name, command in commands]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "full_python": args.full_python,
        "r_runtime": r_runtime,
        "decision": "PASS" if version_probe.returncode == 0 and all(item["exit_code"] == 0 for item in results) else "FAIL",
        "results": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
