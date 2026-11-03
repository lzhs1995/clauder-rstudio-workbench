"""在 Windows PowerShell 5.1 执行真实取回预检；所有目录与内容均为合成夹具。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


CLIENT = Path(os.environ.get("REMOTE_BATCH_CLIENT",
    Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts/remote_batch_client.py"))
spec = importlib.util.spec_from_file_location("return_preflight_client", CLIENT)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@unittest.skipUnless(os.name == "nt", "Windows PowerShell is required")
class WindowsReturnPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pp-return-synthetic-")
        self.root = Path(self.temp.name).resolve()
        self.work, self.export = self.root / "run", self.root / "return"
        self.member = "SYNTHETIC_MI01_A"
        binding = {"schema": "mplus-durable-plan/1", "synthetic": True, "members": [self.member],
                   "jobs": {self.member: {"inputs": {"model.inp": "a" * 64, "data.dat": "b" * 64}}}}
        for directory in (self.work, self.export):
            write_json(directory / "BATCH_BINDING.json", binding)
        data = self.work / "models" / self.member / "data.dat"
        data.parent.mkdir(parents=True)
        data.write_text("SYNTHETIC INPUT ONLY\n")
        output = self.export / "models" / self.member / "model.out"
        output.parent.mkdir(parents=True)
        output.write_text("SYNTHETIC OUTPUT ONLY\n")
        write_json(self.export / "RETURN_INPUT_EXCLUSIONS.json", {
            "schema": "mplus-return-input-exclusions/1",
            "binding_sha256": hashlib.sha256((self.export / "BATCH_BINDING.json").read_bytes()).hexdigest()})
        self.write_manifest()

    def tearDown(self):
        if os.environ.get("REMOTE_RETURN_TEST_EVIDENCE"):
            shutil.copytree(self.root, Path(os.environ["REMOTE_RETURN_TEST_EVIDENCE"]) / self._testMethodName)
        self.temp.cleanup()

    def write_manifest(self):
        files = {p.relative_to(self.export).as_posix(): {"bytes": p.stat().st_size,
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in self.export.rglob("*") if p.is_file() and p.name != "EXPORT_MANIFEST.json"}
        write_json(self.export / "EXPORT_MANIFEST.json", {"schema": "mplus-output-export/1",
                   "source_work": str(self.work), "directory": str(self.export), "files": files,
                   "input_copies_excluded": True})

    def invoke(self, directory, work, *, accepted, error=None):
        prefix = "function Expand([string]$Value) { [Environment]::ExpandEnvironmentVariables($Value) }\n"
        prefix += "function Emit($Value) { Write-Output ('XDEV_JSON ' + ($Value | ConvertTo-Json -Compress -Depth 20)) }\n"
        label = "check-%02d" % len(list(self.root.glob("check-*.ps1")))
        script = self.root / (label + ".ps1")
        script.write_text(prefix + client.return_preflight_script(str(directory), work, "1" * 32), encoding="utf-8-sig")
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        proc = subprocess.run([str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(script)], capture_output=True, timeout=30,
            env={**os.environ, "PP_TEST_WORK_ROOT": str(self.work)})
        (self.root / (label + ".stdout")).write_bytes(proc.stdout)
        (self.root / (label + ".stderr")).write_bytes(proc.stderr)
        if accepted:
            self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors="replace"))
            lines = [line[10:] for line in proc.stdout.decode(errors="replace").splitlines()
                     if line.startswith("XDEV_JSON ")]
            self.assertEqual(len(lines), 1)
            result = json.loads(lines[0])
            self.assertTrue(result["allowed"])
            return result
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn(b"XDEV_JSON ", proc.stdout)
        if error:
            self.assertIn(error.encode(), proc.stderr)

    def test_valid_export_and_generic_result_are_distinct(self):
        result = self.invoke(self.export, str(self.work), accepted=True)
        self.assertEqual(result["kind"], "mplus-output-export/1")
        self.assertEqual(result["manifest_sha256"], hashlib.sha256((self.export / "EXPORT_MANIFEST.json").read_bytes()).hexdigest())
        generic = self.root / "ordinary-results"
        generic.mkdir()
        (generic / "summary.txt").write_text("synthetic summary")
        self.assertEqual(self.invoke(generic, None, accepted=True)["kind"], "generic")

    def test_original_run_without_optional_plan_field_is_refused(self):
        self.invoke(self.work, None, accepted=False)

    def test_parent_directory_and_environment_alias_are_refused(self):
        self.invoke(self.root, "%PP_TEST_WORK_ROOT%\\", accepted=False, error="RETURN_OVERLAPS_MPLUS_WORK")

    def test_parent_of_research_work_is_refused_even_without_plan_field(self):
        path = self.work / "BATCH_BINDING.json"
        binding = json.loads(path.read_text())
        binding["synthetic"] = False  # 模拟科研标签；内容仍全部合成，绝不运行模型。
        write_json(path, binding)
        self.invoke(self.root, None, accepted=False, error="RETURN_CONTAINS_MPLUS_TREE")

    def test_manifest_cannot_authorize_input_data_copy(self):
        (self.export / "models" / self.member / "data.dat").write_text("SYNTHETIC INPUT COPY\n")
        self.write_manifest()
        self.invoke(self.export, None, accepted=False, error="MPLUS_INPUT_COPY_REFUSED")

    def test_unlisted_extra_file_is_refused(self):
        (self.export / "extra.txt").write_text("undeclared synthetic content")
        self.invoke(self.export, None, accepted=False, error="MPLUS_EXPORT_FILESET_DIFFERS")

    def test_changed_export_bytes_are_refused(self):
        (self.export / "models" / self.member / "model.out").write_text("SYNTHETIC XUTPUT ONLY\n")
        self.invoke(self.export, None, accepted=False, error="MPLUS_EXPORT_FILE_HASH_DIFFERS")

    def test_declared_work_must_match_export_source(self):
        self.invoke(self.export, str(self.root / "other-run"), accepted=False, error="MPLUS_EXPORT_WORK_DIFFERS")


if __name__ == "__main__":
    unittest.main()
