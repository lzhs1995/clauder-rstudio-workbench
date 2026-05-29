#!/usr/bin/env python3
"""Validate CMAverse paired-mval results across mediators and groups.

This is a Python gate over the per-mediator ``validation_<mediator>.csv`` files
the R workers emit. It does NOT re-run R; it checks that every mediator x group
row exists and passes the structural checks: full cmest, 17 effects, 159 data
columns, ref mval 0/1, no duplicate / wrong-mediator rows, that M=0 and M=1 used
the SAME bootstrap indices (``m0_boot_hash == m1_boot_hash``), and that the
controlled-direct-effect delta deliverable is present with full inference
(``has_delta_cde`` + ``delta_cde_pe/se/ci_low/ci_high/pval/scale/contrast``).
The effect/column counts are case-study defaults and are overridable. Relaxing
any check (``--no-count-check`` / ``--no-pairing-check`` / ``--no-delta-cde-check``)
marks the run ``weak_validation`` and disqualifies it from a formal success claim.

Exit codes (aligned with the clauder-rstudio-workbench harness):
    0  PASS           - every expected row present and passing
    3  USAGE/MISSING  - a validation CSV is missing or unreadable
    5  CONTRACT_FAILED- rows present but one or more checks failed
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_MISSING = 3
EXIT_FAILED = 5

BOOL_TRUE = {"true", "t", "1", "yes"}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output-root", required=True,
                   help="Level dir holding <mediator>/validation_<mediator>.csv (the contract's artifacts.output_root).")
    p.add_argument("--mediators", required=True, help="Comma-separated mediator ids.")
    p.add_argument("--groups", required=True, help="Comma-separated group ids.")
    p.add_argument("--expected-effects", type=int, default=17,
                   help="Expected effect count per cmest (case study: 17).")
    p.add_argument("--expected-ncol", type=int, default=159,
                   help="Expected $data column count (case study: 159).")
    p.add_argument("--no-count-check", action="store_true",
                   help="Skip the effect-count and data-ncol checks (dataset-specific). Sets weak_validation=true; not for formal success claims.")
    p.add_argument("--no-pairing-check", action="store_true",
                   help="Skip the paired_same_bootstrap/boot-hash check (legacy CSVs only). Sets weak_validation=true.")
    p.add_argument("--no-delta-cde-check", action="store_true",
                   help="Skip the delta_cde deliverable check. Sets weak_validation=true; not for formal success claims.")
    p.add_argument("--json", action="store_true", help="Emit a JSON report to stdout.")
    return p.parse_args(argv)


def split_csv(value):
    return [x.strip() for x in value.split(",") if x.strip()]


def as_bool(value):
    return str(value).strip().lower() in BOOL_TRUE


def check_row(row, mediator, groups_seen, expected_effects, expected_ncol,
              check_counts, check_pairing, check_delta):
    """Return a list of failure strings for one validation row (one group)."""
    fails = []
    g = (row.get("group") or "").strip()
    if not g:
        return ["row missing group"]
    # mediator identity: a stale/copied CSV must not pass for the wrong mediator
    row_med = (row.get("mediator") or "").strip()
    if row_med and row_med != mediator:
        fails.append(f"{g}: row mediator {row_med!r} != {mediator!r}")
    if g in groups_seen:
        fails.append(f"{g}: duplicate validation row")
    groups_seen.add(g)
    if not as_bool(row.get("m0_is_full_cmest")):
        fails.append(f"{g}: m0 not a full cmest")
    if not as_bool(row.get("m1_is_full_cmest")):
        fails.append(f"{g}: m1 not a full cmest")
    # ref mval must be exactly 0 / 1 (empty / missing is a failure)
    if (row.get("m0_ref_mval") or "").strip() != "0":
        fails.append(f"{g}: m0 ref mval != 0 (got {row.get('m0_ref_mval')!r})")
    if (row.get("m1_ref_mval") or "").strip() != "1":
        fails.append(f"{g}: m1 ref mval != 1 (got {row.get('m1_ref_mval')!r})")
    # the core scientific invariant: M=0 and M=1 share the same bootstrap indices
    if check_pairing:
        h0 = (row.get("m0_boot_hash") or "").strip()
        h1 = (row.get("m1_boot_hash") or "").strip()
        if "m0_boot_hash" not in row or "m1_boot_hash" not in row:
            fails.append(f"{g}: missing m0_boot_hash/m1_boot_hash columns "
                         "(worker must record bootstrap-index hashes; use --no-pairing-check only for legacy CSVs)")
        elif not h0 or not h1:
            fails.append(f"{g}: empty boot hash (m0={h0!r}, m1={h1!r}); "
                         "cannot prove M=0/M=1 used the same bootstrap indices")
        elif h0 != h1:
            fails.append(f"{g}: m0_boot_hash != m1_boot_hash ({h0!r} vs {h1!r}); "
                         "M=0 and M=1 came from different bootstrap resamples")
        # paired_same_bootstrap is auxiliary: if present it must agree, but the
        # hash equality above is the authoritative check.
        if "paired_same_bootstrap" not in row:
            fails.append(f"{g}: missing paired_same_bootstrap column")
        elif not as_bool(row.get("paired_same_bootstrap")):
            fails.append(f"{g}: paired_same_bootstrap is not TRUE "
                         "(M=0/M=1 not from the same bootstrap indices)")
    if check_counts:
        for col, want, label in (
            ("m0_effect_n", expected_effects, "m0 effect count"),
            ("m1_effect_n", expected_effects, "m1 effect count"),
            ("m0_data_ncol", expected_ncol, "m0 data ncol"),
            ("m1_data_ncol", expected_ncol, "m1 data ncol"),
        ):
            raw = (row.get(col) or "").strip()
            try:
                got = int(float(raw))
            except (TypeError, ValueError):
                fails.append(f"{g}: {label} not numeric (got {raw!r})")
                continue
            if got != want:
                fails.append(f"{g}: {label} = {got}, expected {want}")
    # the scientific deliverable: the paired-mval-enabled controlled direct
    # effect delta (CDE at M=1 minus CDE at M=0) with full inference.
    if check_delta:
        if "has_delta_cde" not in row:
            fails.append(f"{g}: missing has_delta_cde column "
                         "(worker must emit delta_cde; use --no-delta-cde-check only to relax, weak)")
        elif not as_bool(row.get("has_delta_cde")):
            fails.append(f"{g}: has_delta_cde is not TRUE (delta_cde not produced)")
        else:
            for col in ("delta_cde_pe", "delta_cde_se",
                        "delta_cde_ci_low", "delta_cde_ci_high", "delta_cde_pval"):
                raw = (row.get(col) or "").strip()
                if col not in row:
                    fails.append(f"{g}: missing {col} column")
                    continue
                try:
                    float(raw)
                except (TypeError, ValueError):
                    fails.append(f"{g}: {col} not numeric (got {raw!r})")
            for col in ("delta_cde_scale", "delta_cde_contrast"):
                if col not in row:
                    fails.append(f"{g}: missing {col} column")
                elif not (row.get(col) or "").strip():
                    fails.append(f"{g}: {col} is empty")
    return fails


def validate(args):
    mediators = split_csv(args.mediators)
    groups = split_csv(args.groups)
    root = Path(args.output_root)
    report = {
        "output_root": str(root),
        "mediators": mediators,
        "groups": groups,
        "expected_rows": len(mediators) * len(groups),
        "per_mediator": {},
        "missing": [],
        "failures": [],
        "weak_validation": bool(args.no_count_check or args.no_pairing_check
                                or args.no_delta_cde_check),
    }

    for m in mediators:
        csv_path = root / m / f"validation_{m}.csv"
        entry = {"path": str(csv_path), "rows": 0, "groups_seen": [], "failures": []}
        if not csv_path.exists():
            report["missing"].append(str(csv_path))
            entry["status"] = "missing"
            report["per_mediator"][m] = entry
            continue
        try:
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except OSError as exc:
            report["missing"].append(f"{csv_path}: {exc}")
            entry["status"] = "unreadable"
            report["per_mediator"][m] = entry
            continue

        groups_seen = set()
        for row in rows:
            fails = check_row(row, m, groups_seen, args.expected_effects,
                              args.expected_ncol, not args.no_count_check,
                              not args.no_pairing_check, not args.no_delta_cde_check)
            entry["failures"].extend(f"{m}/{f}" for f in fails)
        entry["rows"] = len(rows)
        entry["groups_seen"] = sorted(groups_seen)
        missing_groups = [g for g in groups if g not in groups_seen]
        for g in missing_groups:
            entry["failures"].append(f"{m}/{g}: missing validation row")
        entry["status"] = "pass" if not entry["failures"] else "fail"
        report["failures"].extend(entry["failures"])
        report["per_mediator"][m] = entry

    total_rows = sum(e["rows"] for e in report["per_mediator"].values())
    report["actual_rows"] = total_rows
    if report["missing"]:
        report["decision"] = "MISSING"
        report["exit_code"] = EXIT_MISSING
    elif report["failures"] or total_rows != report["expected_rows"]:
        if total_rows != report["expected_rows"]:
            report["failures"].append(
                f"row count {total_rows} != expected {report['expected_rows']}")
        report["decision"] = "CONTRACT_FAILED"
        report["exit_code"] = EXIT_FAILED
    else:
        report["decision"] = "PASS"
        report["exit_code"] = EXIT_PASS
    return report


def main(argv=None):
    args = parse_args(argv)
    report = validate(args)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"[{report['decision']}] {report['actual_rows']}/{report['expected_rows']} rows "
              f"across {len(report['mediators'])} mediators"
              + (" (WEAK: gate relaxed, not for formal claims)" if report["weak_validation"] else ""))
        for path in report["missing"]:
            print(f"  MISSING: {path}")
        for fail in report["failures"][:50]:
            print(f"  FAIL: {fail}")
        if len(report["failures"]) > 50:
            print(f"  ... and {len(report['failures']) - 50} more failures")
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
