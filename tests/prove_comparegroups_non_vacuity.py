#!/usr/bin/env python3
"""Prove that comparegroups-guide gates are load-bearing through their R entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
COMMON = REPO / "skills" / "comparegroups-guide" / "scripts" / "comparegroups_common.R"
GATE = REPO / "tests" / "non_vacuity_comparegroups_gate.R"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(common: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("Rscript") or "Rscript", str(GATE), str(common)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=120,
    )


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"mutation target count is {text.count(old)}, expected 1: {old}")
    return text.replace(old, new)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    original_hash = digest(COMMON)
    original = COMMON.read_text(encoding="utf-8")
    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="comparegroups-non-vacuity-") as tmp:
        root = Path(tmp)

        control = run(COMMON)
        results.append({"case": "control", "exit_code": control.returncode, "expected": 0})

        renamed_text = original.replace("cg_count_pattern", "cg_count_xml_pattern")
        if renamed_text == original:
            raise RuntimeError("semantics-preserving rename was not applied")
        renamed = root / "renamed.R"
        renamed.write_text(renamed_text, encoding="utf-8")
        mutation = run(renamed)
        results.append({"case": "semantics_preserving_rename", "exit_code": mutation.returncode, "expected": 0})

        excisions = {
            "attrition_unique_baseline": (
                "if (length(duplicate_ids)) {",
                "if (FALSE && length(duplicate_ids)) {",
            ),
            "attrition_every_id_has_baseline": (
                "if (length(missing_baseline_ids)) {",
                "if (FALSE && length(missing_baseline_ids)) {",
            ),
            "structured_failure_detail": (
                'detail <- ifelse(passed, "", sprintf("expected=%s; actual=%s", expected, actual))',
                'detail <- rep("", length(passed))',
            ),
            "batch_safe_output_dir": (
                'if (any(unsafe)) cg_stop("Batch output_dir must be a safe relative path")',
                'if (FALSE && any(unsafe)) cg_stop("Batch output_dir must be a safe relative path")',
            ),
            "v10_numeric_group_compatibility": (
                '} else if (identical(cg_scalar(spec$spec_version), "1.0") && is.numeric(x)) {',
                '} else if (FALSE && identical(cg_scalar(spec$spec_version), "1.0") && is.numeric(x)) {',
            ),
            "declared_group_level_nonempty": (
                'if (length(empty)) cg_stop("Declared grouping levels have no observations: %s", paste(empty, collapse = ", "))',
                'if (FALSE && length(empty)) cg_stop("Declared grouping levels have no observations: %s", paste(empty, collapse = ", "))',
            ),
            "variant_declared_group_level_nonempty": (
                '      if (length(empty)) {\n        cg_stop(\n          "Variant %s has declared grouping levels with no observations: %s",',
                '      if (FALSE && length(empty)) {\n        cg_stop(\n          "Variant %s has declared grouping levels with no observations: %s",',
            ),
            "fractional_digits_rejected": (
                'if (!cg_is_integer_number(value) || value < 0L || value > 8L) errors <- c(errors, sprintf("defaults.%s must be an integer from 0 to 8", name))',
                'if (FALSE || value < 0L || value > 8L) errors <- c(errors, sprintf("defaults.%s must be an integer from 0 to 8", name))',
            ),
            "unknown_analysis_field_rejected": (
                'cg_unknown_field_errors(spec$analysis, analysis_fields, "analysis"),',
                'character(),',
            ),
            "docx_no_vertical_grid": (
                "three_line = exact_horizontal && vertical == 0L && internal_horizontal == 0L",
                "three_line = exact_horizontal && internal_horizontal == 0L",
            ),
            "docx_no_extra_horizontal": (
                "all(top_by_row[-allowed_top_rows] == 0L) &&\n    all(bottom_by_row[-allowed_bottom_rows] == 0L)",
                "TRUE",
            ),
            "variant_stem_outputs": (
                "if (is.null(spec$analysis$variants) || !length(spec$analysis$variants)) {",
                "if (TRUE) {",
            ),
            "skill_version_metadata": (
                "cg_skill_versions <- function() list(comparegroups_guide = comparegroups_guide_version)",
                "cg_skill_versions <- function() list()",
            ),
            "manifest_entry_coverage": (
                "manifest_entries_complete <- manifest_paths_safe && setequal(manifest$path, expected_output_manifest_paths)",
                "manifest_entries_complete <- TRUE",
            ),
            "manifest_bytes_match": (
                "ok <- !length(missing) && manifest_paths_safe && manifest_bytes_match && manifest_entries_complete",
                "ok <- !length(missing) && manifest_paths_safe && manifest_entries_complete",
            ),
        }
        for name, (old, new) in excisions.items():
            candidate = root / f"{name}.R"
            candidate.write_text(replace_once(original, old, new), encoding="utf-8")
            completed = run(candidate)
            results.append({"case": f"excision_{name}", "exit_code": completed.returncode, "expected": "nonzero"})

    restored_hash = digest(COMMON)
    pass_control = results[0]["exit_code"] == 0
    pass_mutation = results[1]["exit_code"] == 0
    pass_excisions = all(item["exit_code"] != 0 for item in results[2:])
    pass_restore = original_hash == restored_hash
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS" if pass_control and pass_mutation and pass_excisions and pass_restore else "FAIL",
        "control_pass": pass_control,
        "semantics_preserving_mutation_pass": pass_mutation,
        "all_excisions_redden": pass_excisions,
        "restore_byte_identical": pass_restore,
        "original_sha256": original_hash,
        "restored_sha256": restored_hash,
        "results": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
