"""Exercise v0.6.1 correctness checks against isolated semantic mutations."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMMON = REPO / "skills/comparegroups-guide/scripts/comparegroups_common.R"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    original = COMMON.read_text(encoding="utf-8")
    original_hash = hashlib.sha256(COMMON.read_bytes()).hexdigest()
    mutations = {
        "sample_size_groups": (
            "count_columns <- intersect(colnames(available), dimnames(array)[[3L]])",
            'count_columns <- setdiff(colnames(available), c("method", "select"))',
            "count_groups_are_real",
        ),
        "variable_identity": (
            "variable_for_row <- rep(variables, row_counts)",
            "variable_for_row <- rep(variables[[1L]], sum(row_counts))",
            "duplicate_label_bmi",
        ),
        "automatic_variants": (
            "child$data <- cg_validate_variant_data(child$data, spec, child$id)",
            "child$data <- child$data",
            "automatic_empty_group",
        ),
        "unit_duplicates": (
            "if (!is.null(id) && anyDuplicated(data[c(id, time)]))",
            "if (FALSE)",
            "duplicate_id_time",
        ),
        "missing_id": (
            'if (anyNA(data[[id]]) || any(!nzchar(trimws(as.character(data[[id]])))))',
            "if (FALSE)",
            "missing_id",
        ),
        "missing_time": (
            'if (anyNA(data[[time]]) || any(!nzchar(trimws(as.character(data[[time]])))))',
            "if (FALSE)",
            "missing_time",
        ),
        "independent_ids": (
            'if (repeated && identical(cg_scalar(spec$analysis$panel_mode, "cross_section"), "cross_section"))',
            "if (FALSE)",
            "cross_section_repeated_ids",
        ),
        "validation_checkset": (
            "validation_complete && semantic$display && semantic$numeric && semantic$variants",
            "semantic$display && semantic$numeric && semantic$variants",
            "validation_complete",
        ),
        "numeric_semantics": (
            "validation_complete && semantic$display && semantic$numeric && semantic$variants",
            "validation_complete && semantic$display && semantic$variants",
            "numeric_semantics",
        ),
        "display_semantics": (
            "validation_complete && semantic$display && semantic$numeric && semantic$variants",
            "validation_complete && semantic$numeric && semantic$variants",
            "display_semantics",
        ),
        "variant_semantics": (
            "validation_complete && semantic$display && semantic$numeric && semantic$variants",
            "validation_complete && semantic$display && semantic$numeric",
            "variant_numeric_semantics",
        ),
    }
    results = []
    with tempfile.TemporaryDirectory(prefix="comparegroups-correctness-mutations-") as temp:
        candidates = {"control": (original, None), "equivalent_rename": (original.replace("cg_csv_matches", "cg_csv_equal"), None)}
        for name, (old, new, check) in mutations.items():
            if original.count(old) != 1:
                raise RuntimeError(f"Expected one mutation target for {name}")
            candidates[name] = (original.replace(old, new), check)
        for name, (source, expected_failure) in candidates.items():
            path = Path(temp) / f"{name}.R"
            path.write_text(source, encoding="utf-8")
            run = subprocess.run(["Rscript", "tests/test_comparegroups_correctness.R", str(path)],
                                 cwd=REPO, capture_output=True, text=True, timeout=180, check=False)
            passed = run.returncode == 0 if expected_failure is None else (
                run.returncode != 0 and f"CORRECTNESS {expected_failure} FAIL" in run.stdout
            )
            results.append({"case": name, "pass": passed, "exit_code": run.returncode,
                            "expected_failure": expected_failure, "stdout": run.stdout, "stderr": run.stderr})
            print(f"CORRECTNESS_MUTATION {name} {'PASS' if passed else 'FAIL'}", flush=True)
    unchanged = original_hash == hashlib.sha256(COMMON.read_bytes()).hexdigest()
    passed = unchanged and all(item["pass"] for item in results)
    report = {"decision": "PASS" if passed else "FAIL", "source_sha256": original_hash,
              "source_unchanged": unchanged, "cases": len(results), "results": results}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"CORRECTNESS_MUTATION_TOTAL {sum(item['pass'] for item in results)}/{len(results)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
