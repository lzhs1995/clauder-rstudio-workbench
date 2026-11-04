"""mplusautomation-guide 家族注册表、白名单回执与公开边界扫描的合同测试。"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


registry = _load("mplus_family_registry_test", ROOT / "skills" / "mplusautomation-guide" / "scripts" / "family_registry.py")
boundary = _load("public_boundary_scan_test", ROOT / ".github" / "scripts" / "public_boundary_scan.py")
# 测试用本机路径用拼接构造，避免本文件自身触发边界扫描
LOCAL_PATH = "/Us" + "ers/someone/study/data.csv"


def _good_receipt(family="APIM", code=None):
    return {
        "schema_version": 1, "family": family, "dataset": "CHARLS", "route": "apim_v2_config",
        "generated_taipei": "2026-11-05T01:00:00+08:00", "platform": {"os": "Windows", "r": "4.5.2", "mplus": "9"},
        "data_sha256": "a" * 64, "code_sha256": code or {"scripts/workflow.R": "b" * 64},
        "output_sha256": {"effects": "c" * 64}, "rows": 120, "columns": 12, "column_names": ["x1", "x2"],
        "missing_by_column": {"x1": 3}, "comparisons": {"verdict": "PASS", "items": 40, "max_abs_diff": 0.0004},
        "verdict": "PASS", "evidence_logical_name": "charls apim swap",
    }


class RegistryContractTests(unittest.TestCase):
    def setUp(self):
        self.reg = registry.load()

    def errors_for(self, reg):
        return registry.validate(reg)[0]

    def test_shipped_registry_is_valid(self):
        errors, _ = registry.validate(self.reg)
        self.assertEqual(errors, [])

    def test_generated_views_are_current(self):
        self.assertEqual(registry.stale_renders(self.reg), [])

    def test_every_script_test_is_registered(self):
        registered = {t["path"] for t in self.reg["tests"].values()}
        on_disk = {f"scripts/{p.name}" for p in (registry.SKILL_ROOT / "scripts").glob("test_*")}
        self.assertLessEqual(on_disk, registered)

    def test_unknown_route_rejected(self):
        reg = copy.deepcopy(self.reg)
        reg["families"]["APIM"]["routes"].append("no_such_route")
        self.assertTrue(any("unknown route" in e for e in self.errors_for(reg)))

    def test_configurable_family_needs_ci_test(self):
        reg = copy.deepcopy(self.reg)
        reg["families"]["APIM"]["tests"] = ["apim_native_acceptance"]
        self.assertTrue(any("at least one CI test" in e for e in self.errors_for(reg)))

    def test_local_path_rejected(self):
        reg = copy.deepcopy(self.reg)
        reg["families"]["APIM"]["summary"] = "see " + LOCAL_PATH
        self.assertTrue(any("local absolute path" in e for e in self.errors_for(reg)))

    def test_missing_doc_and_parent_escape_rejected(self):
        reg = copy.deepcopy(self.reg)
        reg["families"]["APIM"]["docs"] = ["references/does-not-exist.md", "../README.md"]
        errors = self.errors_for(reg)
        self.assertTrue(any("missing file" in e for e in errors))
        self.assertTrue(any("invalid relative path" in e for e in errors))

    def test_ci_claim_must_match_workflow_text(self):
        reg = copy.deepcopy(self.reg)
        reg["tests"]["template_contracts_py"]["ci"] = "mplus-guide-registry.yml"
        self.assertTrue(any("does not invoke" in e for e in self.errors_for(reg)))

    def test_mplus_test_cannot_claim_hosted_ci(self):
        reg = copy.deepcopy(self.reg)
        reg["tests"]["apim_native_acceptance"]["ci"] = "mplus-guide-family-tests.yml"
        reg["tests"]["apim_native_acceptance"]["function"] = "run_matrix"
        self.assertTrue(any("needs Mplus" in e for e in self.errors_for(reg)))

    def test_evidence_pass_needs_ci_or_file(self):
        reg = copy.deepcopy(self.reg)
        reg["families"]["APIM"]["evidence"]["synthetic_compile"]["source"] = "apim_native_acceptance"
        self.assertTrue(any("not run by any CI" in e for e in self.errors_for(reg)))

    def test_real_data_pass_needs_whitelisted_receipt(self):
        reg = copy.deepcopy(self.reg)
        reg["families"]["APIM"]["evidence"]["real_data_swap"] = {"status": "pass", "source": "assets/example_config_v2.R"}
        self.assertTrue(any("assets/real_data_receipts" in e for e in self.errors_for(reg)))


class ReceiptWhitelistTests(unittest.TestCase):
    def test_good_receipt_accepted(self):
        self.assertEqual(registry.validate_receipt(_good_receipt()), [])

    def test_template_matches_whitelist(self):
        template = registry.receipt_template(registry.load(), "APIM", "CHARLS", "apim_v2_config")
        self.assertEqual(set(template), registry.RECEIPT_REQUIRED | registry.RECEIPT_OPTIONAL)

    def test_estimate_fields_have_no_place(self):
        for key, value in {"estimates": {"x1->y1": 0.31}, "coefficients": [0.2], "bic": 1234.5}.items():
            receipt = _good_receipt()
            receipt[key] = value
            self.assertTrue(any("outside the public whitelist" in e for e in registry.validate_receipt(receipt)), key)

    def test_comparisons_limited_to_counts_and_max_diff(self):
        receipt = _good_receipt()
        receipt["comparisons"]["ll"] = -1234.5
        self.assertTrue(registry.validate_receipt(receipt))

    def test_noninteger_counts_rejected(self):
        receipt = _good_receipt()
        receipt["missing_by_column"] = {"x1": 0.25}
        self.assertTrue(any("missing_by_column" in e for e in registry.validate_receipt(receipt)))
        receipt = _good_receipt()
        receipt["rows"] = 12.5
        self.assertTrue(any("rows" in e for e in registry.validate_receipt(receipt)))

    def test_local_path_rejected(self):
        receipt = _good_receipt()
        receipt["evidence_logical_name"] = LOCAL_PATH
        self.assertTrue(any("local absolute path" in e for e in registry.validate_receipt(receipt)))


class ReceiptFreshnessTests(unittest.TestCase):
    def _skill(self, directory: Path, text: bytes):
        (directory / "scripts").mkdir()
        (directory / "assets" / "real_data_receipts").mkdir(parents=True)
        (directory / "scripts" / "workflow.R").write_bytes(text)
        reg = {"families": {"APIM": {"freshness_files": ["scripts/workflow.R"]}}}
        return reg

    def test_unchanged_code_is_fresh_even_with_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = self._skill(root, b"a <- 1\r\nb <- 2\r\n")
            code = {"scripts/workflow.R": hashlib.sha256(b"a <- 1\nb <- 2\n").hexdigest()}
            (root / "assets" / "real_data_receipts" / "APIM__CHARLS__20261105.json").write_text(json.dumps(_good_receipt(code=code)))
            errors, stale, by_family = registry.check_receipts(reg, root)
            self.assertEqual((errors, stale), ([], []))
            self.assertEqual(by_family["APIM"], ["APIM__CHARLS__20261105.json"])

    def test_changed_code_only_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = self._skill(root, b"a <- 2\n")
            code = {"scripts/workflow.R": hashlib.sha256(b"a <- 1\n").hexdigest()}
            (root / "assets" / "real_data_receipts" / "APIM__CHARLS__20261105.json").write_text(json.dumps(_good_receipt(code=code)))
            errors, stale, _ = registry.check_receipts(reg, root)
            self.assertEqual(errors, [])
            self.assertTrue(any("changed since this receipt" in w for w in stale))

    def test_bad_receipt_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = self._skill(root, b"a <- 1\n")
            bad = _good_receipt()
            bad["coefficients"] = [0.1]
            (root / "assets" / "real_data_receipts" / "APIM__CHARLS__20261105.json").write_text(json.dumps(bad))
            errors, _, _ = registry.check_receipts(reg, root)
            self.assertTrue(errors)


class PublicBoundaryScanTests(unittest.TestCase):
    def test_flags_local_path_and_estimate(self):
        self.assertTrue(boundary.scan_line("references/x.md", "data at " + LOCAL_PATH))
        self.assertTrue(boundary.scan_line("references/x.md", "the archived LL" + "=-1234.567 was reproduced"))

    def test_ignores_counts_and_logical_references(self):
        self.assertEqual(boundary.scan_line("references/x.md", "31 models, 520 class rows; LL/BIC 见本机证据"), [])
        self.assertEqual(boundary.scan_line("references/x.md", "转移概率与三步法 Step-3"), [])

    def test_precise_decimals_only_reported_in_docs(self):
        self.assertTrue(boundary.scan_line("references/x.md", "value 0.12345"))
        self.assertEqual(boundary.scan_line("scripts/x.R", "tolerance <- 0.00050001"), [])


if __name__ == "__main__":
    unittest.main()
