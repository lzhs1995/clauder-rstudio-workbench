"""mplusautomation-guide 家族注册表、白名单回执与公开边界扫描的合同测试。"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
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
        "output_sha256": {"effects": "c" * 64}, "rows": 120, "columns": 2, "column_names": ["x1", "x2"],
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

    def test_any_absolute_path_shape_rejected_in_receipts(self):
        for value in ("/opt/study/real.dta", "~/study/real.dta", "see /tmp/run/out.csv", "\\\\nas01\\study\\real.dta"):
            receipt = _good_receipt()
            receipt["evidence_logical_name"] = value
            self.assertTrue(any("local absolute path" in e for e in registry.validate_receipt(receipt)), value)
        for value in ("ch4 apim / CHARLS swap", "w1/charls_apim_swap"):
            receipt = _good_receipt()
            receipt["evidence_logical_name"] = value
            self.assertEqual(registry.validate_receipt(receipt), [], value)
        receipt = _good_receipt()
        receipt["platform"] = {"os": "macOS 15/arm64", "r": "4.5.2", "mplus": "9"}
        self.assertEqual(registry.validate_receipt(receipt), [])

    def test_template_refuses_family_without_freshness_files(self):
        with self.assertRaises(ValueError):
            registry.receipt_template(registry.load(), "MED", "CFPS", "template_bundle")
        self.assertEqual(registry.main(["receipt-template", "MED", "CFPS", "template_bundle"]), 1)

    def test_nested_payload_rejected_in_every_allowed_field(self):
        # REVIEW-PR80-001 R1：允许的字段里塞对象或数组，也不能带出估计值或 ID（合成值）
        payload = {"estimates": [0.31], "individual_id": "SYNTHETIC_TEST_ID"}
        cases = {
            "evidence_logical_name": payload, "family": payload, "dataset": [payload], "route": payload,
            "generated_taipei": payload, "data_sha256": payload, "verdict": payload, "schema_version": payload,
            "rows": payload, "columns": [2], "column_names": payload, "missing_by_column": {"x1": payload},
            "platform": {"os": payload}, "comparisons": {"verdict": "PASS", "items": payload},
            "output_sha256": {"effects": payload}, "code_sha256": {"scripts/workflow.R": payload},
        }
        for key, value in cases.items():
            receipt = _good_receipt()
            receipt[key] = value
            self.assertTrue(registry.validate_receipt(receipt), key)
        receipt = _good_receipt()
        receipt["column_names"] = ["x1", payload]
        self.assertTrue(any("column_names" in e for e in registry.validate_receipt(receipt)))
        receipt = _good_receipt()
        receipt["comparisons"]["max_abs_diff"] = [0.31]
        self.assertTrue(any("max_abs_diff" in e for e in registry.validate_receipt(receipt)))

    def test_scalar_shapes_and_counts(self):
        for key, value in {"evidence_logical_name": "a\nb", "column_names": ["x1: 0.31", "x2"],
                           "schema_version": True, "rows": True, "output_sha256": {"effects": "C" * 64}}.items():
            receipt = _good_receipt()
            receipt[key] = value
            self.assertTrue(registry.validate_receipt(receipt), key)
        for mutate, text in [(lambda r: r.update(columns=3), "column_names has 2"),
                             (lambda r: r.update(column_names=["x1", "x1"]), "must not repeat"),
                             (lambda r: r.update(missing_by_column={"z9": 1}), "not in column_names"),
                             (lambda r: r.update(missing_by_column={"x1": 121}), "exceeds rows"),
                             (lambda r: r.pop("column_names"), "missing_by_column requires column_names"),
                             (lambda r: r["comparisons"].update(max_abs_diff=float("nan")), "finite"),
                             (lambda r: r["comparisons"].update(max_abs_diff=-1), "finite"),
                             (lambda r: r["comparisons"].pop("verdict"), "comparisons must be an object")]:
            receipt = _good_receipt()
            mutate(receipt)
            self.assertTrue(any(text in e for e in registry.validate_receipt(receipt)), text)

    def test_generated_time_must_be_a_real_taipei_time(self):
        for value in ("not-a-date", "2026-11-05T01:00:00Z", "2026-13-05T01:00:00+08:00", "2026-11-05"):
            receipt = _good_receipt()
            receipt["generated_taipei"] = value
            self.assertTrue(any("generated_taipei" in e for e in registry.validate_receipt(receipt)), value)

    def test_pass_cannot_contradict_comparisons(self):
        # REVIEW-PR80-001 R2 ②：顶层 PASS 与比较 FAIL 不得共存；FAIL 回执本身合法
        receipt = _good_receipt()
        receipt["comparisons"]["verdict"] = "FAIL"
        self.assertTrue(any("contradicts" in e for e in registry.validate_receipt(receipt)))
        receipt["verdict"] = "FAIL"
        self.assertEqual(registry.validate_receipt(receipt), [])

    def test_identity_must_be_registered(self):
        # REVIEW-PR80-001 R2 ①：未登记的数据源、路线，或不属于该家族的路线
        reg = registry.load()
        self.assertEqual(registry.validate_receipt(_good_receipt(), reg=reg), [])
        for key, value, text in [("dataset", "NO_SUCH_DATASET", "unknown dataset"),
                                 ("route", "NO_SUCH_ROUTE", "unknown route"),
                                 ("family", "NO_SUCH_FAMILY", "unknown family"),
                                 ("route", "external_project", "is not a route of family APIM")]:
            receipt = _good_receipt()
            receipt[key] = value
            self.assertTrue(any(text in e for e in registry.validate_receipt(receipt, reg=reg)), key)


class ReceiptFreshnessTests(unittest.TestCase):
    def _skill(self, directory: Path, text: bytes):
        (directory / "scripts").mkdir()
        (directory / "assets" / "real_data_receipts").mkdir(parents=True)
        (directory / "scripts" / "workflow.R").write_bytes(text)
        reg = {"families": {"APIM": {"freshness_files": ["scripts/workflow.R"], "routes": ["apim_v2_config"]}},
               "datasets": {"CHARLS": {}}, "routes": {"apim_v2_config": {}}}
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
            errors, stale, by_family = registry.check_receipts(reg, root)
            self.assertEqual(errors, [])
            self.assertTrue(any("changed since this receipt" in w for w in stale))
            # 过期的 PASS 回执不计入覆盖
            self.assertEqual(by_family["APIM"], [])

    def test_fail_receipt_is_kept_but_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = self._skill(root, b"a <- 1\n")
            failed = _good_receipt(code={"scripts/workflow.R": hashlib.sha256(b"a <- 1\n").hexdigest()})
            failed["verdict"] = "FAIL"
            failed["comparisons"]["verdict"] = "FAIL"
            (root / "assets" / "real_data_receipts" / "APIM__CHARLS__20261105.json").write_text(json.dumps(failed))
            self.assertEqual(registry.check_receipts(reg, root), ([], [], {"APIM": []}))

    def test_duplicate_keys_are_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = self._skill(root, b"a <- 1\n")
            text = json.dumps(_good_receipt())[:-1] + ', "verdict": "PASS"}'
            (root / "assets" / "real_data_receipts" / "APIM__CHARLS__20261105.json").write_text(text)
            errors, _, _ = registry.check_receipts(reg, root)
            self.assertTrue(any("duplicate keys" in e for e in errors))

    def test_bad_receipt_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = self._skill(root, b"a <- 1\n")
            bad = _good_receipt()
            bad["coefficients"] = [0.1]
            (root / "assets" / "real_data_receipts" / "APIM__CHARLS__20261105.json").write_text(json.dumps(bad))
            errors, _, _ = registry.check_receipts(reg, root)
            self.assertTrue(errors)


class StrictGateCliTests(unittest.TestCase):
    """在临时副本里跑 `family_registry.py check --strict`：合法 PASS 回执通过，负例必须 rc=1。"""
    RECEIPT = "assets/real_data_receipts/APIM__CHARLS__20261105.json"

    def run_case(self, mutate_receipt=None, workflow_text=None, strict=True):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            skill = repo / "skills" / "mplusautomation-guide"
            shutil.copytree(registry.SKILL_ROOT, skill, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / ".github" / "workflows", repo / ".github" / "workflows")
            reg = registry.load()
            for family in reg["families"].values():
                family["evidence"]["real_data_swap"] = {"status": "not_applicable"}
            reg["families"]["APIM"]["evidence"]["real_data_swap"] = {"status": "pass", "source": self.RECEIPT}
            receipt = registry.receipt_template(reg, "APIM", "CHARLS", "apim_v2_config", root=skill)
            receipt.update(data_sha256="a" * 64, rows=12, columns=2, column_names=["x1", "x2"],
                           output_sha256={"synthetic_output": "b" * 64}, verdict="PASS",
                           comparisons={"verdict": "PASS", "items": 2, "max_abs_diff": 0.0},
                           evidence_logical_name="synthetic test fixture")
            if mutate_receipt:
                mutate_receipt(receipt)
            (skill / self.RECEIPT).write_text(json.dumps(receipt), encoding="utf-8")
            (skill / "families.json").write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            for path, text in registry.render_outputs(reg, skill).items():
                path.write_text(text, encoding="utf-8", newline="\n")
            if workflow_text is not None:
                (repo / ".github" / "workflows" / "mplus-guide-family-tests.yml").write_text(workflow_text, encoding="utf-8")
            command = [sys.executable, "-B", str(skill / "scripts" / "family_registry.py"), "check"] + (["--strict"] if strict else [])
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)

    def assertRejected(self, result, text):
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(text, result.stdout)

    def test_valid_pass_receipt_passes_strict(self):
        result = self.run_case()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 errors, 0 warnings", result.stdout)

    def test_nested_estimate_and_id_rejected(self):
        payload = {"estimates": [0.31], "individual_id": "SYNTHETIC_TEST_ID"}
        self.assertRejected(self.run_case(lambda r: r.update(evidence_logical_name=payload)), "evidence_logical_name")
        self.assertRejected(self.run_case(lambda r: r.update(column_names={"x1": 0.31, "x2": 0.2})), "column_names")

    def test_unregistered_identity_and_bad_time_rejected(self):
        result = self.run_case(lambda r: r.update(dataset="NO_SUCH_DATASET", route="NO_SUCH_ROUTE", generated_taipei="not-a-date"))
        for text in ("unknown dataset", "unknown route", "generated_taipei", "valid PASS receipt for APIM"):
            self.assertRejected(result, text)

    def test_pass_with_failed_comparisons_rejected(self):
        self.assertRejected(self.run_case(lambda r: r["comparisons"].update(verdict="FAIL")), "contradicts")

    def test_fail_receipt_cannot_back_a_pass(self):
        def failed(receipt):
            receipt["verdict"] = "FAIL"
            receipt["comparisons"]["verdict"] = "FAIL"
        self.assertRejected(self.run_case(failed), "valid PASS receipt for APIM")

    def test_stale_pass_receipt_warns_then_fails_strict(self):
        def stale(receipt):
            receipt["code_sha256"]["scripts/workflow.R"] = "0" * 64
        self.assertEqual(self.run_case(stale, strict=False).returncode, 0)
        self.assertRejected(self.run_case(stale), "without a fresh PASS real-data swap receipt: APIM")

    def test_noop_workflow_with_runner_in_comment_rejected(self):
        # REVIEW-PR80-001 R3：合法 YAML，唯一步骤是 echo，runner 只出现在注释里
        noop = ('name: synthetic no-op\non: workflow_dispatch\njobs:\n  noop:\n    runs-on: ubuntu-latest\n'
                '    steps:\n      - run: echo "no tests executed"\n# run_family_ci_tests.R\n')
        self.assertRejected(self.run_case(workflow_text=noop), "does not invoke")

    def test_job_level_if_false_rejected(self):
        # RULING-PR80-001 第 1 项：job 级 if: false 的 workflow 必须被 strict 拒绝
        disabled = ("name: synthetic disabled job\non: workflow_dispatch\njobs:\n  synthetic:\n    if: false\n"
                    "    runs-on: ubuntu-latest\n    steps:\n      - run: Rscript skills/mplusautomation-guide/scripts/"
                    "run_family_ci_tests.R mplus-guide-family-tests.yml out\n")
        self.assertRejected(self.run_case(workflow_text=disabled), "does not invoke")


class WorkflowInvocationTests(unittest.TestCase):
    WORKFLOW = "mplus-guide-family-tests.yml"
    RUNNER = "Rscript skills/mplusautomation-guide/scripts/run_family_ci_tests.R mplus-guide-family-tests.yml out"

    def setUp(self):
        reg = registry.load()
        self.r_test, self.py_test = reg["tests"]["apim_v2_contract"], reg["tests"]["rstudio_queue_admission_py"]

    def invokes(self, steps, test=None):
        text = "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n" + steps
        return registry._workflow_invokes(text, self.WORKFLOW, test or self.r_test)

    def test_real_run_steps_count(self):
        self.assertTrue(self.invokes(f"      - name: x\n        run: |\n          set -e\n          FOO=1 {self.RUNNER} && echo ok\n"))
        folded = self.RUNNER.replace(" mplus-guide", "\n          mplus-guide")
        self.assertTrue(self.invokes(f"      - run: >-\n          {folded}\n"))
        self.assertTrue(self.invokes("      - run: python -m unittest test_rstudio_queue_admission -v\n", self.py_test))
        # Windows 风格路径在任何平台上判断一致
        windows_style = 'Rscript "skills\\mplusautomation-guide\\scripts\\run_family_ci_tests.R" mplus-guide-family-tests.yml out'
        self.assertTrue(self.invokes(f"      - run: {windows_style}\n"))
        # 单行条件里 then 后面的命令照样算调用
        self.assertTrue(self.invokes(f"      - run: if [ -d skills ]; then {self.RUNNER}; fi\n"))
        # 同一 workflow 里另有停用的 job，不影响启用 job 的调用
        text = ("jobs:\n  off:\n    if: false\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo off\n"
                f"  on:\n    runs-on: ubuntu-latest\n    steps:\n      - run: {self.RUNNER}\n")
        self.assertTrue(registry._workflow_invokes(text, self.WORKFLOW, self.r_test))

    def test_disabled_job_and_nested_text_are_not_invocations(self):
        # RULING-PR80-001 第 1 项：整个 job 写死 if: false，其中步骤都不执行
        for condition in ("false", "${{ false }}", "'false'"):
            text = (f"jobs:\n  synthetic:\n    if: {condition}\n    runs-on: ubuntu-latest\n"
                    f"    steps:\n      - run: {self.RUNNER}\n")
            self.assertFalse(registry._workflow_invokes(text, self.WORKFLOW, self.r_test), condition)
        # 其他键（如 with: script: |）正文里的 run: 行只是文本
        nested = ("      - uses: actions/github-script@v7\n        with:\n          script: |\n"
                  f"            run: {self.RUNNER}\n")
        self.assertFalse(self.invokes(nested))

    def test_text_that_does_not_execute_is_not_an_invocation(self):
        for steps in (f"      - run: echo {self.RUNNER}\n",
                      f"      - run: |\n          # {self.RUNNER}\n          echo hi\n",
                      f"      - name: {self.RUNNER}\n        run: echo hi\n",
                      f"      # - run: {self.RUNNER}\n      - run: echo hi\n",
                      f"      - name: x\n        if: false\n        run: {self.RUNNER}\n",
                      self.RUNNER.replace("mplus-guide-family-tests.yml", "other.yml").join(("      - run: ", "\n"))):
            self.assertFalse(self.invokes(steps), steps)
        for steps in ("      - run: python -m unittest discover -s scripts -p test_rstudio_queue_admission.py\n",
                      "      - run: echo python -m unittest test_rstudio_queue_admission\n"):
            self.assertFalse(self.invokes(steps, self.py_test), steps)


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

    def test_quoted_and_special_file_names_are_parsed(self):
        # REVIEW-PR80-001 R4：git 默认把中文名写成 "b/\345..."；路径含空格时文件头末尾有制表符
        diff = ('diff --git "a/\\345\\205\\254.md" "b/\\345\\205\\254.md"\n--- /dev/null\n'
                '+++ "b/\\345\\205\\254.md"\n@@ -0,0 +1 @@\n+one\n'
                'diff --git a/x y.md b/x y.md\n--- a/x y.md\n+++ b/x y.md\t\n@@ -1 +1 @@\n-old\n+two\n'
                'diff --git "a/q\\"t.md" "b/q\\"t.md"\n--- /dev/null\n+++ "b/q\\"t.md"\n@@ -0,0 +1 @@\n+three\n')
        self.assertEqual(list(boundary.parse_added_lines(diff)),
                         [("公.md", 1, "one"), ("x y.md", 1, "two"), ('q"t.md', 1, "three")])

    def test_added_line_starting_with_plus_signs_is_content(self):
        diff = ("diff --git a/x.md b/x.md\n--- a/x.md\n+++ b/x.md\n@@ -0,0 +1,2 @@\n"
                "+++ b/other.md\n+second\n@@ -5 +8 @@\n-old\n+new\n")
        self.assertEqual(list(boundary.parse_added_lines(diff)),
                         [("x.md", 1, "++ b/other.md"), ("x.md", 2, "second"), ("x.md", 8, "new")])

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_unicode_file_names_scanned_in_a_real_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                               cwd=tmp, check=True, capture_output=True)
            git("init", "-q")
            git("config", "core.quotePath", "true")
            (Path(tmp) / "base.txt").write_text("base\n", encoding="utf-8")
            git("add", "-A")
            git("commit", "-q", "-m", "base")
            for name in ("ascii.md", "公开边界.md"):
                (Path(tmp) / name).write_text("local " + LOCAL_PATH + "\n", encoding="utf-8")
            git("add", "-A")
            git("commit", "-q", "-m", "fixture")
            lines = list(boundary.added_lines("HEAD~1", "HEAD", [], cwd=tmp))
            self.assertEqual(sorted(path for path, _, _ in lines), ["ascii.md", "公开边界.md"])
            self.assertEqual(sum(len(boundary.scan_line(p, t)) for p, _, t in lines), 2)
            # 同一 PR 加 .gitattributes 的 -diff，文件仍要进入扫描
            (Path(tmp) / ".gitattributes").write_text("*.md -diff\n", encoding="utf-8")
            (Path(tmp) / "ascii.md").write_text("local " + LOCAL_PATH + "\nmore " + LOCAL_PATH + "\n", encoding="utf-8")
            git("add", "-A")
            git("commit", "-q", "-m", "attributes")
            lines = list(boundary.added_lines("HEAD~1", "HEAD", [], cwd=tmp))
            self.assertIn(("ascii.md", 2), [(p, n) for p, n, _ in lines])


if __name__ == "__main__":
    unittest.main()
