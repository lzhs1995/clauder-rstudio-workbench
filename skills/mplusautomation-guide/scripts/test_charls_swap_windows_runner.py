"""外层准入的合成回归；不启动 R、Mplus、Stata 或远程命令。"""
from copy import deepcopy
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
        self.grant = {key: deepcopy(self.config[key]) for key in ("worker", "request_id", "purpose", "root", "models")}
        self.grant["approved"] = True
        self.config_path = self.package / "private_config.json"
        self.grant_path = self.package / "formal_grant.json"
        self.resources = {"native_platform": "Windows", "ram_available_bytes": 5 * runner.GIB,
                          "c_free_bytes": 20 * runner.GIB, "engines": []}
        self.persist()

    def persist(self):
        self.config_path.write_text(json.dumps(self.config))
        self.grant_path.write_text(json.dumps(self.grant))
        self.config_hash = runner.sha256(self.config_path)
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
        binding_hashes = {"config_sha256": self.config_hash, "grant_sha256": self.grant_hash}
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


if __name__ == "__main__":
    unittest.main()
