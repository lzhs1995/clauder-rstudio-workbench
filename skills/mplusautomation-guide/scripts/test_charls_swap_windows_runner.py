"""外层准入的合成回归；不启动 R、Mplus、Stata 或远程命令。"""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("charls_swap_windows_runner.py")
SPEC = importlib.util.spec_from_file_location("charls_swap_windows_runner", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RunnerAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.source_dir = self.folder / "protected_sources"
        self.source_dir.mkdir()
        self.package = self.folder / "package"
        self.package.mkdir()
        self.root = self.folder / "isolated_run"
        self.runtime = {}
        for name in ("python", "rscript", "driver", "engine"):
            path = self.package / (name + (".R" if name == "driver" else ".exe"))
            path.write_text("synthetic inert file " + name)
            self.runtime[name] = {"path": str(path), "sha256": runner.sha256(path)}
        self.python_patch = patch.object(runner.sys, "executable", self.runtime["python"]["path"])
        self.python_patch.start()
        self.addCleanup(self.python_patch.stop)
        driver = SCRIPT.with_name("charls_apim_swap_driver.R")
        self.runtime["driver"] = {"path": str(driver), "sha256": runner.sha256(driver)}
        sources = {}
        for role in ("harmonized", "demographic", "health"):
            path = self.source_dir / (role + ".dta")
            path.write_text("person_id,value\nsynthetic,1\n")
            sources[role] = {"path": str(path), "sha256": runner.sha256(path)}
        self.config = {"schema": runner.SCHEMA, "ready": True, "worker": "W1", "request_id": runner.REQUEST,
                       "purpose": "synthetic technical source swap", "root": str(self.root),
                       "models": deepcopy(runner.MODELS), "scientific_contract": {"fixture": True},
                       "sources": sources, "protected_roots": [str(self.source_dir)], "files": self.runtime,
                       "code_files": [{"path": str(p), "sha256": runner.sha256(p)} for p in
                                      list(p for p in SCRIPT.parent.iterdir() if p.suffix in (".py", ".R") and not p.name.startswith("test_"))
                                      + [SCRIPT.parent.parent / "assets" / "charls_apim_swap_config_v2.R"]],
                       "budget": {"max_total_bytes": 1000000000, "max_single_file_bytes": 999999999,
                                  "min_c_free_bytes": 10 * runner.GIB, "min_ram_available_bytes": 3 * runner.GIB,
                                  "reserve_bytes": runner.MIN_RESERVE, "run_growth_upper_bound_bytes": 1000000,
                                  "growth_bound_basis": "synthetic budget boundary fixture"}}
        self.request_dir = self.package / "requests"
        self.request_dir.mkdir()
        self.grant_dir = self.package / "grants"
        self.grant_dir.mkdir()
        self.request_path = self.request_dir / "synthetic_request.json"
        self.request = {key: deepcopy(self.config[key]) for key in ("worker", "request_id", "purpose", "root", "models")}
        self.request.update(est_minutes=1, est_ram_gb=1, xdev_command="synthetic inert command",
                            hard_cap={key: self.config["budget"][key] for key in runner.CAP_KEYS})
        self.request_path.write_text(json.dumps(self.request))
        self.config["request"] = {"path": str(self.request_path), "sha256": runner.sha256(self.request_path)}
        self.config["grant_authority"] = {"granted_by": "synthetic supervisor pane and session"}
        self.grant = {key: deepcopy(self.config[key]) for key in ("worker", "request_id", "purpose", "root", "models")}
        self.grant.update(approved=True, request_name=self.request_path.stem,
                          request_sha256=self.config["request"]["sha256"], hard_cap=deepcopy(self.request["hard_cap"]),
                          granted_by=self.config["grant_authority"]["granted_by"], granted_taipei="2020-01-01T08:00:00+08:00")
        self.config_path = self.package / "private_config.json"
        self.grant_path = self.grant_dir / self.request_path.name
        self.resources = {"native_platform": "Windows", "ram_available_bytes": 5 * runner.GIB,
                          "c_free_bytes": 20 * runner.GIB, "engines": []}
        self.persist()

    def persist(self):
        # 只冻结配置和授权，绝不自动重写请求或修复其绑定SHA。
        self.config_path.write_text(json.dumps(self.config))
        self.config_hash = runner.sha256(self.config_path)
        self.grant.setdefault("config_sha256", self.config_hash)
        self.grant_path.write_text(json.dumps(self.grant))
        self.grant_hash = runner.sha256(self.grant_path)

    def preflight(self, resources=None):
        self.persist()
        return runner.preflight(self.config_path, self.config_hash, self.grant_path, self.grant_hash,
                                resources=self.resources if resources is None else resources)

    def test_complete_synthetic_preflight_is_read_only(self):
        _, report = self.preflight()
        self.assertEqual(report["status"], "PREFLIGHT_PASS_NOT_STARTED")
        self.assertFalse(self.root.exists())

    def test_unready_and_incomplete_configuration_rejected(self):
        self.config["ready"] = False
        with self.assertRaisesRegex(runner.AdmissionError, "config_not_ready"):
            self.preflight()
        self.config["ready"] = True
        self.config["code_files"] = []
        with self.assertRaisesRegex(runner.AdmissionError, "code_files_empty"):
            self.preflight()

    def test_grant_fields_and_exact_models_bound(self):
        for key, value in (("worker", "W2"), ("request_id", "other"), ("purpose", "another"),
                           ("root", str(self.folder / "another")), ("models", runner.MODELS[:1]), ("approved", False)):
            with self.subTest(key=key):
                saved = self.grant[key]
                self.grant[key] = value
                with self.assertRaises(runner.AdmissionError):
                    self.preflight()
                self.grant[key] = saved

    def test_changed_grant_and_config_hashes_denied(self):
        with self.assertRaisesRegex(runner.AdmissionError, "hash_mismatch"):
            runner.preflight(self.config_path, "a" * 64, self.grant_path, self.grant_hash, resources=self.resources)
        with self.assertRaisesRegex(runner.AdmissionError, "hash_mismatch"):
            runner.preflight(self.config_path, self.config_hash, self.grant_path, "b" * 64, resources=self.resources)

    def test_missing_grant_models_or_null_source_denied(self):
        del self.grant["models"]
        with self.assertRaisesRegex(runner.AdmissionError, "missing_field:models"):
            self.preflight()
        self.grant["models"] = deepcopy(runner.MODELS)
        self.config["sources"]["health"]["sha256"] = None
        with self.assertRaisesRegex(runner.AdmissionError, "missing_field:sha256"):
            self.preflight()

    def test_exact_two_ordered_models(self):
        self.config["models"] = list(reversed(runner.MODELS))
        with self.assertRaisesRegex(runner.AdmissionError, "exactly_two"):
            self.preflight()

    def test_existing_attempt_directory_never_reused(self):
        self.root.mkdir()
        (self.root / "STARTED.json").write_text("unknown prior attempt")
        with self.assertRaisesRegex(runner.AdmissionError, "observe_original_attempt"):
            self.preflight()
        self.assertEqual((self.root / "STARTED.json").read_text(), "unknown prior attempt")

    def test_atomic_intent_create_new_does_not_overwrite(self):
        self.root.mkdir()
        path = self.root / "STARTED.json"
        runner.write_new_json(path, {"attempt": "first"})
        with self.assertRaises(FileExistsError):
            runner.write_new_json(path, {"attempt": "second"})
        self.assertEqual(runner.load_json(path)["attempt"], "first")

    def test_output_root_source_overlap_denied(self):
        self.config["root"] = str(self.source_dir / "run")
        self.grant["root"] = self.config["root"]
        with self.assertRaisesRegex(runner.AdmissionError, "overlaps_protected"):
            self.preflight()

    def test_symlink_output_root_denied(self):
        real = self.folder / "real"
        real.mkdir()
        try:
            self.root.symlink_to(real, target_is_directory=True)
        except OSError:
            self.skipTest("host does not permit synthetic symlinks")
        with self.assertRaisesRegex(runner.AdmissionError, "symlink|reparse"):
            self.preflight()

    def test_model_resources_are_windows_and_idle(self):
        for key, value in (("engines", [{"pid": 42, "name": "Mplus.exe"}]),
                           ("engines", [{"pid": 43, "name": "StataMP.exe"}]),
                           ("ram_available_bytes", 3 * runner.GIB - 1),
                           ("c_free_bytes", 10 * runner.GIB), ("native_platform", "WSL")):
            with self.subTest(key=key, value=value):
                resources = {**self.resources, key: value}
                with self.assertRaises(runner.AdmissionError):
                    self.preflight(resources)

    def test_charls_never_inherits_three_gb_stata_budget(self):
        self.config["budget"]["max_total_bytes"] = 3000000000
        with self.assertRaisesRegex(runner.AdmissionError, "invalid_integer:max_total_bytes"):
            self.preflight()

    def test_budget_limits_are_strict_and_no_null_or_bool(self):
        for key, value in (("max_single_file_bytes", 1000000000), ("run_growth_upper_bound_bytes", None),
                           ("run_growth_upper_bound_bytes", True), ("run_growth_upper_bound_bytes", 800000000)):
            with self.subTest(key=key, value=value):
                saved = self.config["budget"][key]
                self.config["budget"][key] = value
                with self.assertRaises(runner.AdmissionError):
                    self.preflight()
                self.config["budget"][key] = saved

    def test_snapshot_copies_and_freezes_before_use(self):
        self.root.mkdir()
        original = {key: Path(item["path"]).read_bytes() for key, item in self.config["sources"].items()}
        copied = runner.copy_sources(self.config, self.root)
        for key, item in copied.items():
            self.assertTrue(runner.inside(item["path"], self.root))
            self.assertEqual(Path(item["path"]).read_bytes(), original[key])
            self.assertEqual(Path(self.config["sources"][key]["path"]).read_bytes(), original[key])
            # 清理仅合成夹具，在Windows恢复测试文件权限以便TemporaryDirectory善后。
            Path(item["path"]).chmod(0o600)
        with self.assertRaises(FileExistsError):
            runner.copy_sources(self.config, self.root)

    def test_source_change_rejected_before_copy(self):
        Path(self.config["sources"]["health"]["path"]).write_text("changed")
        with self.assertRaisesRegex(runner.AdmissionError, "file_hash_mismatch"):
            self.preflight()

    def test_csv_source_and_incomplete_runtime_bundle_denied(self):
        original = self.config["sources"]["health"]
        csv = self.source_dir / "health.csv"
        csv.write_text("synthetic,fixture")
        self.config["sources"]["health"] = {"path": str(csv), "sha256": runner.sha256(csv)}
        with self.assertRaisesRegex(runner.AdmissionError, "source_format_must_be_dta"):
            self.preflight()
        self.config["sources"]["health"] = original
        self.config["code_files"] = [item for item in self.config["code_files"] if Path(item["path"]).name != "workflow.R"]
        with self.assertRaisesRegex(runner.AdmissionError, "exact_bundle"):
            self.preflight()

    def test_parent_traversal_rejected(self):
        with self.assertRaisesRegex(runner.AdmissionError, "parent_traversal"):
            runner.reject_alias(self.root / ".." / "protected_sources")

    def test_process_birth_and_exe_guard(self):
        expected = {"pid": 7, "birth_epoch": 1234.0, "exe": self.runtime["rscript"]["path"]}
        self.assertEqual(runner.verify_identity(expected, lambda pid: expected), expected)
        for key, value in (("birth_epoch", 1235.0), ("exe", self.runtime["engine"]["path"])):
            with self.subTest(key=key):
                with self.assertRaisesRegex(runner.AdmissionError, "process_identity_changed"):
                    runner.verify_identity(expected, lambda pid: {**expected, key: value})

    def test_duplicate_json_keys_rejected(self):
        self.config_path.write_text('{"ready":false,"ready":true}')
        with self.assertRaisesRegex(runner.AdmissionError, "duplicate_json_key"):
            runner.load_json(self.config_path)

    def test_gate_is_single_use_and_requires_same_attempt(self):
        _, report = self.preflight()
        self.root.mkdir()
        copied = runner.copy_sources(self.config, self.root)
        identities = {11: {"pid": 11, "birth_epoch": 100.0, "exe": self.runtime["rscript"]["path"]},
                      12: {"pid": 12, "birth_epoch": 99.0, "exe": self.runtime["python"]["path"]}}
        runner.write_new_json(self.root / "RUN_BINDING.json", {"attempt_id": "one", **report})
        binding_hashes = {"config_sha256": self.config_hash, "grant_sha256": self.grant_hash,
                          "request_sha256": self.config["request"]["sha256"]}
        runner.write_new_json(self.root / "STARTED.json", {"attempt_id": "one", **binding_hashes})
        runner.write_new_json(self.root / "driver_request.json", {"attempt_id": "one"})
        runner.write_new_json(self.root / "PROCESS.json", {"attempt_id": "one", "driver": identities[11], "supervisor": identities[12],
                             "driver_request_sha256": runner.sha256(self.root / "driver_request.json"), **binding_hashes})
        with self.assertRaisesRegex(runner.AdmissionError, "attempt_mismatch"):
            runner.gate_fit(self.root, "two", self.resources, lambda pid: identities[pid])
        result = runner.gate_fit(self.root, "one", self.resources, lambda pid: identities[pid])
        self.assertEqual(result["models"], runner.MODELS)
        with self.assertRaises(FileExistsError):
            runner.gate_fit(self.root, "one", self.resources, lambda pid: identities[pid])
        for item in copied.values():
            Path(item["path"]).chmod(0o600)

    def test_platform_check_never_launches_a_process_on_mac(self):
        with patch.object(runner.os, "name", "posix"), patch.object(runner.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(runner.AdmissionError, "windows_native_runtime_required"):
                runner.launch(self.config_path, self.config_hash, self.grant_path, self.grant_hash)
            popen.assert_not_called()

    def test_request_bytes_changed_without_rebinding_are_rejected(self):
        self.request_path.write_text(json.dumps({**self.request, "purpose": "tampered"}))
        with self.assertRaisesRegex(runner.AdmissionError, "file_hash_mismatch"):
            self.preflight()
        self.assertFalse(self.root.exists())

    def test_request_missing_wrong_hash_and_duplicate_keys(self):
        original = self.request_path.read_bytes()
        self.request_path.unlink()
        with self.assertRaisesRegex(runner.AdmissionError, "file_missing"):
            self.preflight()
        self.request_path.write_bytes(original)
        self.config["request"]["sha256"] = "a" * 64
        with self.assertRaisesRegex(runner.AdmissionError, "hash_mismatch"):
            self.preflight()
        self.request_path.write_text('{"worker":"W1","worker":"W2"}')
        self.config["request"]["sha256"] = runner.sha256(self.request_path)
        with self.assertRaisesRegex(runner.AdmissionError, "duplicate_json_key"):
            self.preflight()

    def test_request_relative_root_internal_and_symlink_paths(self):
        descriptor = deepcopy(self.config["request"])
        self.config["request"]["path"] = "relative.json"
        with self.assertRaisesRegex(runner.AdmissionError, "absolute"):
            self.preflight()
        self.root.mkdir()
        internal = self.root / self.request_path.name
        internal.write_bytes(self.request_path.read_bytes())
        self.config["request"] = {**descriptor, "path": str(internal)}
        with self.assertRaisesRegex(runner.AdmissionError, "request_must_be_outside"):
            self.preflight()
        alias = self.package / "request_alias.json"
        try:
            alias.symlink_to(self.request_path)
        except OSError:
            return  # 本平台不支持链接时，上述两项仍已经验证。
        self.config["request"] = {**descriptor, "path": str(alias)}
        with self.assertRaisesRegex(runner.AdmissionError, "symlink|reparse"):
            self.preflight()

    def test_request_semantics_and_estimates_must_match(self):
        for key, value in (("worker", "W2"), ("request_id", "another"), ("purpose", "other"),
                           ("models", list(reversed(runner.MODELS))), ("root", str(self.folder / "elsewhere")),
                           ("est_minutes", True), ("est_minutes", 0), ("est_ram_gb", -1),
                           ("est_ram_gb", "1"), ("xdev_command", " ")):
            with self.subTest(key=key, value=value):
                changed = {**self.request, key: value}
                self.request_path.write_text(json.dumps(changed))
                self.config["request"]["sha256"] = runner.sha256(self.request_path)
                with self.assertRaises(runner.AdmissionError):
                    runner.validate_request(self.config, self.config_path)

    def test_request_cap_keys_types_and_values_are_exact(self):
        for caps in ({}, {**self.request["hard_cap"], "unknown": 1},
                     {**self.request["hard_cap"], "reserve_bytes": True},
                     {**self.request["hard_cap"], "max_total_bytes": 1}):
            with self.subTest(caps=caps):
                self.request_path.write_text(json.dumps({**self.request, "hard_cap": caps}))
                self.config["request"]["sha256"] = runner.sha256(self.request_path)
                with self.assertRaisesRegex(runner.AdmissionError, "request_cap"):
                    runner.validate_request(self.config, self.config_path)

    def test_grant_required_binding_fields_and_issuer(self):
        valid = deepcopy(self.grant)
        for key in ("request_name", "request_sha256", "config_sha256", "hard_cap", "granted_by", "granted_taipei"):
            with self.subTest(missing=key):
                changed = deepcopy(valid)
                del changed[key]
                self.grant_path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(runner.AdmissionError, "missing_field:" + key):
                    self.check_grant_bytes()
        for key, value in (("request_name", "wrong"), ("request_sha256", "b" * 64),
                           ("config_sha256", "c" * 64), ("granted_by", "another session"),
                           ("granted_by", "")):
            with self.subTest(key=key):
                self.grant_path.write_text(json.dumps({**valid, key: value}))
                with self.assertRaises(runner.AdmissionError):
                    self.check_grant_bytes()

    def check_grant_bytes(self, now=None):
        # 原件篡改负例不调用persist；只改变外部预期grant SHA，保留内部全部绑定。
        digest = runner.sha256(self.grant_path)
        return runner.validate_grant(self.config, {"path": str(self.grant_path), "sha256": digest}, digest,
                                     config_path=self.config_path, config_hash=self.config_hash, now=now)

    def test_grant_filename_and_mutable_root_are_rejected(self):
        original = self.grant_path
        self.grant_path = self.grant_dir / "wrong_name.json"
        self.grant_path.write_bytes(original.read_bytes())
        with self.assertRaisesRegex(runner.AdmissionError, "filename"):
            self.check_grant_bytes()
        self.root.mkdir()
        self.grant_path = self.root / self.request_path.name
        self.grant_path.write_bytes(original.read_bytes())
        with self.assertRaisesRegex(runner.AdmissionError, "grant_must_be_outside"):
            self.check_grant_bytes()

    def test_grant_taipei_timestamp_is_valid_and_not_future(self):
        now = datetime(2021, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(self.check_grant_bytes(now)["granted_taipei"], self.grant["granted_taipei"])
        for value in ("", 12, "nonsense", "2020-01-01T00:00:00", "2020-01-01T00:00:00+00:00",
                      "2022-01-01T08:00:00+08:00"):
            with self.subTest(value=value):
                self.grant_path.write_text(json.dumps({**self.grant, "granted_taipei": value}))
                with self.assertRaises(runner.AdmissionError):
                    self.check_grant_bytes(now)

    def test_grant_caps_cannot_be_ignored_or_understate_growth(self):
        for key in runner.CAP_KEYS:
            for delta in (-1, 1):
                with self.subTest(key=key, delta=delta):
                    caps = {**self.grant["hard_cap"], key: self.grant["hard_cap"][key] + delta}
                    self.grant_path.write_text(json.dumps({**self.grant, "hard_cap": caps}))
                    with self.assertRaisesRegex(runner.AdmissionError, "grant_cap_|grant_growth_estimate"):
                        self.check_grant_bytes()
        for caps in ({}, {**self.grant["hard_cap"], "extra": 1},
                     {**self.grant["hard_cap"], "max_total_bytes": True},
                     {**self.grant["hard_cap"], "max_total_bytes": None},
                     {**self.grant["hard_cap"], "max_total_bytes": "1"}):
            with self.subTest(caps=caps):
                self.grant_path.write_text(json.dumps({**self.grant, "hard_cap": caps}))
                with self.assertRaises(runner.AdmissionError):
                    self.check_grant_bytes()

    def test_checked_json_parses_the_hashed_bytes_only(self):
        # 模拟核SHA后路径内容被替换；只能解析本次已核验的读取结果。
        original = self.config_path.read_bytes()
        with patch.object(Path, "read_bytes", return_value=original) as read:
            _, value = runner.load_checked_json({"path": str(self.config_path), "sha256": self.config_hash})
        self.assertEqual(read.call_count, 1)
        self.assertEqual(value, self.config)
        with self.assertRaisesRegex(runner.AdmissionError, "nonfinite_json"):
            runner.parse_json(b'{"estimated":NaN}')

    def test_fit_gate_rechecks_request_before_admission(self):
        _, report = self.preflight()
        self.root.mkdir()
        hashes = {key: report[key] for key in ("config_sha256", "grant_sha256", "request_sha256")}
        runner.write_new_json(self.root / "RUN_BINDING.json", {"attempt_id": "one", **report})
        runner.write_new_json(self.root / "STARTED.json", {"attempt_id": "one", **hashes})
        runner.write_new_json(self.root / "driver_request.json", {"attempt_id": "one"})
        owner = {"attempt_id": "one", **hashes, "driver_request_sha256": runner.sha256(self.root / "driver_request.json")}
        runner.write_new_json(self.root / "PROCESS.json", owner)
        self.request_path.write_text(json.dumps({**self.request, "purpose": "changed after start"}))
        with self.assertRaisesRegex(runner.AdmissionError, "file_hash_mismatch"):
            runner.gate_fit(self.root, "one", self.resources)
        self.assertFalse((self.root / "FIT_ADMITTED.json").exists())
        owner["request_sha256"] = "d" * 64
        (self.root / "PROCESS.json").write_text(json.dumps(owner))
        with self.assertRaisesRegex(runner.AdmissionError, "attempt_hash_binding_mismatch:request_sha256"):
            runner.gate_fit(self.root, "one", self.resources)
        self.assertFalse((self.root / "FIT_ADMITTED.json").exists())


if __name__ == "__main__":
    unittest.main()
