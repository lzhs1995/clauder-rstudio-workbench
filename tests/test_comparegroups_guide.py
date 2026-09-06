from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "comparegroups-guide"
SCRIPTS = SKILL / "scripts"
FIXTURE = REPO / "tests" / "fixtures" / "comparegroups_synthetic.csv"
SPEC = REPO / "tests" / "fixtures" / "comparegroups_synthetic.table-spec.json"
WORKBENCH_PACKAGE = REPO / "skills" / "clauder-rstudio-workbench"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@unittest.skipUnless(shutil.which("Rscript"), "Rscript is required")
class CompareGroupsGuideTests(unittest.TestCase):
    def run_r(self, script: str, *args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["Rscript", str(SCRIPTS / script), *map(str, args)],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )

    def test_skill_layout_and_openai_interface(self) -> None:
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "schemas" / "table-spec.schema.json").is_file())
        self.assertTrue((SKILL / "schemas" / "table-spec-1.1.schema.json").is_file())
        self.assertTrue((SKILL / "schemas" / "batch-manifest.schema.json").is_file())
        openai = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("interface:", openai)
        self.assertIn("$comparegroups-guide", openai)
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: comparegroups-guide", skill)
        self.assertNotIn("/Users/", skill)
        self.assertNotIn("C:/Users/", skill)

    def test_collection_installer_discovers_all_three_skills(self) -> None:
        sys.path.insert(0, str(WORKBENCH_PACKAGE))
        try:
            from clauder_workbench.installer import _skill_sources

            names = [path.name for path in _skill_sources(REPO)]
        finally:
            sys.path.pop(0)
        self.assertEqual(
            names,
            ["clauder-rstudio-workbench", "cmaverse-paired-mval", "comparegroups-guide"],
        )

    def test_schema_core_and_templates(self) -> None:
        schema = json.loads((SKILL / "schemas" / "table-spec.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["spec_version"]["const"], "1.0")
        self.assertEqual(set(schema["required"]), {"spec_version", "analysis_id", "input", "analysis", "blocks", "display", "outputs"})
        methods = schema["properties"]["blocks"]["items"]["properties"]["variables"]["items"]["properties"]["method"]["enum"]
        self.assertEqual(methods, ["normal", "nonnormal", "categorical"])
        templates = list((SKILL / "assets").glob("*.table-spec.json"))
        self.assertGreaterEqual(len(templates), 6)
        for template in templates:
            document = json.loads(template.read_text(encoding="utf-8"))
            self.assertIn(document["spec_version"], {"1.0", "1.1"})
            self.assertNotIn("/Users/", template.read_text(encoding="utf-8"))

    def test_schema_validates_templates_and_rejects_missing_fields(self) -> None:
        from jsonschema import Draft202012Validator

        schemas = {
            "1.0": json.loads((SKILL / "schemas" / "table-spec.schema.json").read_text(encoding="utf-8")),
            "1.1": json.loads((SKILL / "schemas" / "table-spec-1.1.schema.json").read_text(encoding="utf-8")),
        }
        for schema in schemas.values():
            Draft202012Validator.check_schema(schema)
        for template in (SKILL / "assets").glob("*.table-spec.json"):
            document = json.loads(template.read_text(encoding="utf-8"))
            validator = Draft202012Validator(schemas[document["spec_version"]])
            self.assertEqual(list(validator.iter_errors(document)), [])
        missing = json.loads(SPEC.read_text(encoding="utf-8"))
        del missing["blocks"]
        validator = Draft202012Validator(schemas["1.0"])
        self.assertTrue(any(error.validator == "required" for error in validator.iter_errors(missing)))

        batch_schema = json.loads((SKILL / "schemas" / "batch-manifest.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(batch_schema)
        batch = json.loads((SKILL / "assets" / "batch-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(batch_schema).iter_errors(batch)), [])

    def test_schema_1_1_defaults_are_optional_but_methods_remain_explicit(self) -> None:
        from jsonschema import Draft202012Validator

        schema = json.loads((SKILL / "schemas" / "table-spec-1.1.schema.json").read_text(encoding="utf-8"))
        document = json.loads((SKILL / "assets" / "attrition-auto.table-spec.json").read_text(encoding="utf-8"))
        variable = document["blocks"][0]["variables"][0]
        self.assertNotIn("digits", variable)
        self.assertNotIn("include_missing", variable)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(document)), [])
        del variable["method"]
        self.assertTrue(any(error.validator == "required" for error in Draft202012Validator(schema).iter_errors(document)))

    def test_skill_local_markdown_links_resolve(self) -> None:
        for document in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                self.assertTrue((document.parent / target).resolve().exists(), f"broken link in {document}: {target}")

    def test_public_material_has_no_private_paths_or_research_values(self) -> None:
        roots = [REPO / "README.md", REPO / "CHANGELOG.md", REPO / "docs", REPO / "skills"]
        files = []
        public_suffixes = {".md", ".R", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1"}
        for root in roots:
            files.extend(
                [root] if root.is_file()
                else [path for path in root.rglob("*") if path.is_file() and path.suffix in public_suffixes]
            )
        forbidden = ("/Users/" + "lzhs", "C:/Users/" + "LZHS", "access_" + "token=")
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                self.assertNotIn(marker, text, f"private marker in {path}")

    def test_end_to_end_dual_panel_outputs(self) -> None:
        input_hash = sha256(FIXTURE)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "outputs"
            run = self.run_r("run_comparegroups.R", "--spec", SPEC, "--output-root", output)
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertIn("COMPAREGROUPS_RUN_OK decision=PASS", run.stdout)
            validate = self.run_r("validate_comparegroups.R", "--output-root", output, "--stem", "Table_synthetic")
            self.assertEqual(validate.returncode, 0, validate.stdout)
            self.assertEqual(sha256(FIXTURE), input_hash)

            expected = {
                "Table_synthetic.docx",
                "Table_synthetic_display.csv",
                "Table_synthetic_numeric_long.csv",
                "Table_synthetic_objects.rds",
                "Table_synthetic_metadata.json",
                "validation.csv",
                "manifest.csv",
                "SHA256SUMS.txt",
            }
            self.assertEqual({p.name for p in output.iterdir()}, expected)

            with (output / "Table_synthetic_display.csv").open(encoding="utf-8") as handle:
                display = list(csv.DictReader(handle))
            variants = {row["variant"] for row in display}
            self.assertEqual(variants, {"primary_wave_1", "primary_wave_2", "compatibility_pooled"})
            self.assertIn("全样本", display[0])
            self.assertIn("p-value", display[0])
            self.assertTrue(any(row["row_label"] == "Category: 'Missing'" for row in display))

            with (output / "Table_synthetic_numeric_long.csv").open(encoding="utf-8") as handle:
                numeric = list(csv.DictReader(handle))
            selected = [
                row for row in numeric
                if row["variant"] == "primary_wave_1"
                and row["variable"] == "outcome"
                and row["statistic"] == "mean"
                and row["group"] == "[ALL]"
            ]
            self.assertEqual(len(selected), 1)
            self.assertAlmostEqual(float(selected[0]["value"]), 12.825, places=10)
            sample_sizes = [
                row for row in numeric
                if row["variant"] == "primary_wave_1"
                and row["variable"] == "outcome"
                and row["statistic"] == "n_available"
                and row["group"] == "[ALL]"
            ]
            self.assertEqual(len(sample_sizes), 1)
            self.assertEqual(float(sample_sizes[0]["value"]), 4.0)
            self.assertTrue(
                all(row["value"] not in {"", "NA", "NaN"} for row in numeric if row["statistic"] == "n_available")
            )

            metadata = json.loads((output / "Table_synthetic_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["spec_version"], "1.0")
            self.assertEqual(metadata["resolution"]["input_spec_version"], "1.0")
            self.assertEqual(metadata["input_sha256"], input_hash)
            self.assertTrue(metadata["panel"]["repeated_ids"])
            warning = metadata["variants"]["compatibility_pooled"]["warning"]
            self.assertIn("not independent", warning)

            with (output / "manifest.csv").open(encoding="utf-8") as handle:
                manifest = list(csv.DictReader(handle))
            for row in manifest:
                path = output / row["path"]
                self.assertEqual(sha256(path), row["sha256"])
            sums = (output / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
            self.assertTrue(any(line.endswith("  manifest.csv") for line in sums))

            with (output / "validation.csv").open(encoding="utf-8") as handle:
                validation = list(csv.DictReader(handle))
            self.assertEqual(
                set(validation[0]),
                {"check", "passed", "expected", "actual", "detail", "details"},
            )
            self.assertTrue(all(row["detail"] == "" for row in validation))

    def test_docx_has_three_line_borders_and_no_vertical_grid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "outputs"
            run = self.run_r("run_comparegroups.R", "--spec", SPEC, "--output-root", output)
            self.assertEqual(run.returncode, 0, run.stdout)
            with zipfile.ZipFile(output / "Table_synthetic.docx") as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            value = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
            top = [x for x in root.findall(".//w:top", ns) if x.get(value) == "single"]
            bottom = [x for x in root.findall(".//w:bottom", ns) if x.get(value) == "single"]
            vertical = [
                x for tag in ("left", "right", "insideV")
                for x in root.findall(f".//w:{tag}", ns)
                if x.get(value) == "single"
            ]
            self.assertGreater(len(top), 0)
            self.assertGreater(len(bottom), 0)
            self.assertEqual(vertical, [])

    def test_duplicate_variable_and_bad_method_are_blocked(self) -> None:
        base = json.loads(SPEC.read_text(encoding="utf-8"))
        base["blocks"][1]["variables"].append(dict(base["blocks"][0]["variables"][0]))
        base["blocks"][0]["variables"][0]["method"] = "unsupported"
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps(base), encoding="utf-8")
            result = self.run_r("audit_input.R", "--spec", bad, "--output", Path(tmp) / "audit.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid method", result.stdout)
        self.assertIn("duplicate variables", result.stdout)

    def test_numeric_unlabelled_category_requires_levels(self) -> None:
        base = json.loads(SPEC.read_text(encoding="utf-8"))
        base["blocks"] = [{
            "id": "categorical",
            "label": "Categorical",
            "variables": [{
                "name": "person_id", "type": "categorical", "method": "categorical",
                "digits": 2, "label": None, "include_missing": False,
                "reference": None, "levels": None,
            }],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "numeric-category.json"
            bad.write_text(json.dumps(base), encoding="utf-8")
            result = self.run_r("audit_input.R", "--spec", bad, "--output", Path(tmp) / "audit.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires explicit levels", result.stdout)

    def test_unknown_group_codes_and_overlapping_attrition_waves_are_blocked(self) -> None:
        group_spec = json.loads(SPEC.read_text(encoding="utf-8"))
        group_spec["spec_version"] = "1.1"
        group_spec["input"]["path"] = str(FIXTURE)
        group_spec["analysis"]["group"] = "person_id"
        group_spec["analysis"]["group_levels"] = [
            {"value": 1, "label": "One"},
            {"value": 2, "label": "Two"},
        ]
        group_spec["analysis"]["group_reference"] = "One"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unknown-group.json"
            path.write_text(json.dumps(group_spec), encoding="utf-8")
            result = self.run_r("audit_input.R", "--spec", path, "--output", Path(tmp) / "audit.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown grouping codes", result.stdout)

        attrition = json.loads((SKILL / "assets" / "attrition-auto.table-spec.json").read_text(encoding="utf-8"))
        attrition["input"]["path"] = str(FIXTURE)
        attrition["analysis"]["attrition"]["baseline_values"] = [1]
        attrition["analysis"]["attrition"]["followup_values"] = [1]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overlap.json"
            path.write_text(json.dumps(attrition), encoding="utf-8")
            result = self.run_r("audit_input.R", "--spec", path, "--output", Path(tmp) / "audit.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not overlap", result.stdout)

    def test_batch_stops_after_failure_and_preserves_completed_evidence(self) -> None:
        first = json.loads(SPEC.read_text(encoding="utf-8"))
        first["input"]["path"] = str(FIXTURE)
        second = json.loads(SPEC.read_text(encoding="utf-8"))
        second["analysis_id"] = "missing-input"
        second["input"]["path"] = "/definitely/not/a/real/input.csv"
        second["outputs"]["stem"] = "Table_missing"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_path = root / "first.json"
            second_path = root / "second.json"
            first_path.write_text(json.dumps(first), encoding="utf-8")
            second_path.write_text(json.dumps(second), encoding="utf-8")
            manifest = {
                "manifest_version": "1.0",
                "batch_id": "failure-contract",
                "jobs": [
                    {"id": "first", "spec_path": str(first_path), "output_dir": "01_first"},
                    {"id": "second", "spec_path": str(second_path), "output_dir": "02_second"},
                ],
            }
            manifest_path = root / "batch.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "batch-output"
            result = self.run_r("run_comparegroups_batch.R", "--manifest", manifest_path, "--output-root", output)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue((output / "01_first" / "Table_synthetic.docx").is_file())
            self.assertTrue((output / "batch_manifest.csv").is_file())
            self.assertTrue((output / "SHA256SUMS.txt").is_file())
            with (output / "batch_summary.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["status"] for row in rows], ["PASS", "FAIL"])
            with (output / "batch_validation.csv").open(encoding="utf-8") as handle:
                validation = list(csv.DictReader(handle))
            failed = [row for row in validation if row["passed"].lower() == "false"]
            self.assertTrue(failed)
            self.assertTrue(all(row["detail"] for row in failed))

    def test_export2word_compatibility_mode(self) -> None:
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        spec["input"]["path"] = str(FIXTURE)
        spec["analysis"]["panel_mode"] = "cross_section"
        spec["analysis"]["subset"] = "wave == 1"
        spec["display"]["compatibility_export2word"] = True
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "compatibility.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            output = Path(tmp) / "outputs"
            result = self.run_r("run_comparegroups.R", "--spec", spec_path, "--output-root", output)
            self.assertEqual(result.returncode, 0, result.stdout)
            compatibility = output / "Table_synthetic_export2word_compatibility.docx"
            self.assertTrue(compatibility.is_file())
            with zipfile.ZipFile(compatibility) as archive:
                self.assertIn("word/document.xml", archive.namelist())


if __name__ == "__main__":
    unittest.main()
