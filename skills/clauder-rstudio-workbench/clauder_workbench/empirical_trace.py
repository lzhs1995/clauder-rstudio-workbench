"""Portable empirical trace contract v1. No statistical execution or tolerance repair.

Maintained in thesis-refiner; domain skill bundles carry the same versioned file
so receipt checks remain available without an R/Stata session or extra package.
"""
from __future__ import annotations
import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path


class TraceError(ValueError):
    pass


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def checked_file(ref):
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise TraceError("HASHED_FILE_REFERENCE_REQUIRED")
    path = Path(ref["path"])
    if not path.is_absolute() or not path.is_file() or digest(path) != ref["sha256"]:
        raise TraceError("FILE_MISSING_OR_CHANGED")
    return path


def rows(ref):
    with checked_file(ref).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise TraceError("UNIQUE_CSV_COLUMNS_REQUIRED")
        result = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in result):
            raise TraceError("MALFORMED_CSV_ROW")
        return reader.fieldnames, result


def keyed(ref, keys):
    columns, values = rows(ref)
    if not keys or not set(keys) <= set(columns):
        raise TraceError("EXPLICIT_SAMPLE_KEYS_REQUIRED")
    index = {}
    for value in values:
        key = tuple(value[k] for k in keys)
        if any(not k.strip() for k in key) or key in index:
            raise TraceError("MISSING_OR_DUPLICATED_SAMPLE_KEY")
        index[key] = value
    return columns, index


def sample_fingerprint(ref, keys):
    _, index = keyed(ref, keys)
    encoded = json.dumps(sorted(index), ensure_ascii=False, separators=(",", ":")).encode()
    return {"n": len(index), "membership_sha256": hashlib.sha256(encoded).hexdigest()}


def compare_csv(spec):
    left_columns, left = keyed(spec["actual"], spec["keys"])
    right_columns, right = keyed(spec["expected"], spec["keys"])
    if set(left) != set(right):
        raise TraceError("SAMPLE_MEMBERSHIP_MISMATCH")
    numeric = spec.get("numeric_columns")
    if not numeric or not set(numeric) <= set(left_columns) & set(right_columns):
        raise TraceError("NUMERIC_COLUMNS_MISSING")
    required = ("storage_precision", "display_rounding", "ci_method", "draws_requested", "draws_saved", "absolute_tolerance", "relative_tolerance")
    if any(k not in spec for k in required):
        raise TraceError("NUMERICAL_CONTRACT_INCOMPLETE")
    absolute, relative = Decimal(str(spec["absolute_tolerance"])), Decimal(str(spec["relative_tolerance"]))
    if not absolute.is_finite() or not relative.is_finite() or absolute < 0 or relative < 0:
        raise TraceError("INVALID_NUMERIC_TOLERANCE")
    max_error = Decimal(0)
    missing = {column: 0 for column in numeric}
    for key in left:
        for column in numeric:
            x, y = left[key][column], right[key][column]
            if x == "" or y == "":
                if x != y:
                    raise TraceError("MISSINGNESS_MISMATCH")
                missing[column] += 1
                continue
            try:
                actual, expected = Decimal(x), Decimal(y)
            except InvalidOperation as exc:
                raise TraceError("NON_NUMERIC_RESULT") from exc
            if not actual.is_finite() or not expected.is_finite():
                raise TraceError("NONFINITE_RESULT")
            error = abs(actual - expected)
            max_error = max(max_error, error)
            if error > absolute + relative * abs(expected):
                raise TraceError("NUMERICAL_MISMATCH")
    return {"rows": len(left), "columns": numeric, "missing_counts": missing,
            "max_absolute_error": str(max_error), "tolerance_modified": False}


def audit_contract(contract):
    errors, partials, comparisons, samples = [], [], [], []
    try:
        if contract.get("schema_version") != 1 or not contract.get("task_id"):
            raise TraceError("TRACE_IDENTITY_REQUIRED")
        checked_file(contract.get("script"))
        for name in ("inputs", "outputs"):
            if not contract.get(name):
                raise TraceError("INPUT_OUTPUT_INVENTORY_REQUIRED")
            for artifact in contract[name]:
                checked_file(artifact)
        runtime = contract.get("runtime") or {}
        if any(k not in runtime for k in ("session_id", "job_id", "transport", "source_revision", "installed_version", "loaded_version")):
            raise TraceError("RUNTIME_LAYERS_MUST_BE_RECORDED")
        for sample in contract.get("samples", []):
            actual = sample_fingerprint(sample["artifact"], sample["keys"])
            if type(sample.get("expected_n")) is not int or sample["expected_n"] != actual["n"]:
                raise TraceError("SAMPLE_N_MISMATCH")
            if sample.get("same_members_as") and actual != sample_fingerprint(sample["same_members_as"], sample["keys"]):
                raise TraceError("SAMPLE_MEMBERSHIP_MISMATCH")
            if sample.get("membership_sha256") and actual["membership_sha256"] != sample["membership_sha256"]:
                raise TraceError("SAMPLE_FINGERPRINT_MISMATCH")
            samples.append(actual)
        if not samples:
            raise TraceError("EMPIRICAL_SAMPLE_CONTRACT_REQUIRED")
        for table in contract.get("tables", []):
            columns, index = keyed(table["artifact"], [table["row_key"]])
            if not set(table.get("required_columns", [])) <= set(columns):
                raise TraceError("TABLE_COLUMNS_MISSING")
            if table.get("expected_rows") is not None and set(index) != {(x,) for x in table["expected_rows"]}:
                raise TraceError("TABLE_ROWS_MISSING_OR_EXTRA")
            for row_name, fields in table.get("expected_cells", {}).items():
                if (row_name,) not in index or any(index[(row_name,)].get(k) != str(v) for k, v in fields.items()):
                    raise TraceError("TABLE_DENOMINATOR_LABEL_OR_MISSINGNESS_MISMATCH")
        for spec in contract.get("comparisons", []):
            comparisons.append(compare_csv(spec))
        for model in contract.get("models", []):
            checked_file(model.get("evidence"))
            axes = ("normal_termination", "standard_errors_valid", "draws_requested", "draws_saved", "replicate_convergence")
            if not model.get("id") or any(k not in model for k in axes):
                raise TraceError("MODEL_HEALTH_AXES_REQUIRED")
            if model["draws_requested"] is not None:
                if (type(model["draws_requested"]) is not int or type(model["draws_saved"]) is not int
                        or not 0 <= model["draws_saved"] <= model["draws_requested"]):
                    raise TraceError("SAVED_DRAWS_CONTRACT_INVALID")
            incomplete = (model["normal_termination"] is not True or model["standard_errors_valid"] is not True
                          or model["replicate_convergence"] not in {True, "not_applicable"}
                          or model["draws_saved"] != model["draws_requested"])
            if incomplete:
                if not model.get("accepted_partial") or not model.get("limitation"):
                    raise TraceError("MODEL_HEALTH_PARTIAL_NOT_PROPAGATED")
                partials.append({"model_id": model["id"], "limitation": model["limitation"]})
        reproduced = contract.get("full_reproduction") is True
        if reproduced:
            proof = json.loads(checked_file(contract.get("execution_receipt")).read_text())
            if (proof.get("mode") != "real" or proof.get("status") != "PASS" or proof.get("end_to_end") is not True
                    or proof.get("script_sha256") != contract["script"]["sha256"]
                    or not runtime["session_id"] or not runtime["job_id"]
                    or any(proof.get(k) != runtime[k] for k in ("session_id", "job_id"))
                    or proof.get("input_sha256s") != [x["sha256"] for x in contract["inputs"]]
                    or proof.get("output_sha256s") != [x["sha256"] for x in contract["outputs"]] or partials):
                raise TraceError("FULL_REPRODUCTION_NOT_PROVEN")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        errors.append(str(exc))
    return {"schema_version": 1, "pass": not errors, "errors": errors, "samples": samples,
            "comparisons": comparisons, "documented_partials": partials,
            "status": "OPEN" if errors else "CLOSED_WITH_DOCUMENTED_PARTIALS" if partials else "CLOSED",
            "full_reproduction": not errors and contract.get("full_reproduction") is True,
            "execution_performed_by_checker": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = audit_contract(json.loads(Path(args.input).read_text()))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    print(text, end="")
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
