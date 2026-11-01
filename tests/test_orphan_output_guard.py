"""恢复决策与独立采用回执；合成文件、短暂 Python 进程，无 R/Mplus 调用。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(os.environ.get("ORPHAN_GUARD_SCRIPTS",
                             Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts"))
sys.path.insert(0, str(SCRIPTS))
import orphan_output_guard as guard


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OrphanGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source, self.work = self.root / "source", self.root / "work"
        self.member = "SYNTHETIC_MI01_A"
        self.src = self.source / "models" / self.member
        self.dst = self.work / "models" / self.member
        self.src.mkdir(parents=True)
        self.dst.mkdir(parents=True)
        content = {
            "model.inp": b"DATA: FILE=data.dat;\nMODEL: y ON x;\n",
            "data.dat": b"1 2\n3 4\n",
            "model.out": b"Mplus VERSION 9\nTHE MODEL ESTIMATION TERMINATED NORMALLY\nH0 Value -5.25\n",
            "estimates.dat": b"1.25 0.25\n",
            "tech3.dat": b"0.0625\n",
        }
        for name, data in content.items():
            (self.src / name).write_bytes(data)
            (self.dst / name).write_bytes(data)
        self.inputs = {name: sha(self.src / name) for name in ("model.inp", "data.dat")}
        dump(self.src / "job.json", {"hashes": self.inputs, "cap_seconds": 240})
        dump(self.src / "engine_receipt.json", {"wall_seconds": 1})
        dump(self.source / "contracts/RUN_CONTRACT.json", {"primary_sequence": [self.member]})
        self.marker = {"pid": 2147483646, "created": time.time() - 1,
                       "at": guard.now(), "inputs": self.inputs}
        dump(self.dst / "ENGINE_STARTED.json", self.marker)
        self.originals = {p: sha(p) for p in self.dst.iterdir()}

    def tearDown(self):
        self.tmp.cleanup()

    def assess(self, **kwargs):
        return guard.assess_member(self.source, self.work, self.member, sys.executable, **kwargs)

    def adopt(self, **kwargs):
        return guard.adopt_member(self.source, self.work, self.member, sys.executable, **kwargs)

    def add_result(self):
        dump(self.dst / "RESULT.json", {
            "member": self.member, "status": "PASS_IDENTICAL",
            "engine_exit_code": 0, "engine_state": "EXITED", "inputs": self.inputs,
            "wall_seconds": 1, "removed_input_copies": [],
            "compare": {name: {"sha_new": sha(self.dst / name)} for name in guard.OUTPUTS},
        })

    def test_completed_orphan_adopts_without_fabricating_exit_code(self):
        result = self.adopt()
        self.assertEqual(result["decision"], "OUTPUTS_ADOPTED", result)
        self.assertIsNone(result["engine_exit_code"])
        self.assertIsNone(result["budget_remaining"])
        self.assertEqual(result["engine_calls"], 0)
        self.assertFalse((self.dst / "RESULT.json").exists())
        self.assertTrue(all(path.exists() and sha(path) == digest for path, digest in self.originals.items()))

    def test_second_adoption_reuses_same_receipt_bytes(self):
        first = self.adopt()
        target = Path(first["adoption"])
        before = target.read_bytes()
        self.assertEqual(self.adopt()["decision"], "ADOPTION_ALREADY_RECORDED")
        self.assertEqual(before, target.read_bytes())

    def test_existing_adoption_with_fabricated_exit_is_rejected(self):
        first = self.adopt()
        target = Path(first["adoption"])
        doc = json.loads(target.read_text())
        doc["engine_exit_code"] = 0
        dump(target, doc)
        self.assertEqual(self.adopt()["decision"], "HOLD")

    def test_legacy_start_without_input_hashes_stays_on_hold(self):
        marker = dict(self.marker)
        marker.pop("inputs")
        dump(self.dst / "ENGINE_STARTED.json", marker)
        result = self.adopt()
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("input hashes", result["reason"])
        self.assertTrue((self.dst / "model.out").exists())
        self.assertFalse((self.work / "recovery_adoptions").exists())

    def test_changed_source_is_not_moved_or_reestimated(self):
        (self.src / "data.dat").write_text("5 6\n7 8\n")
        result = self.adopt()
        self.assertEqual(result["decision"], "HOLD")
        self.assertTrue(all(path.exists() and sha(path) == digest for path, digest in self.originals.items()))

    def test_stale_result_cannot_skip_new_validation(self):
        self.add_result()
        (self.dst / "estimates.dat").write_text("999 0.25\n")
        result = self.assess()
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("saved receipt", result["reason"])

    def test_verified_finished_result_is_reused(self):
        self.add_result()
        result = self.assess()
        self.assertEqual(result["decision"], "REUSE_VERIFIED_RESULT", result)
        self.assertEqual(result["engine_exit_code"], 0)

    def test_active_original_python_fixture_is_observed_not_killed(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.8)", "model.inp"], cwd=self.dst)
        try:
            import psutil
            self.marker.update(pid=process.pid, created=psutil.Process(process.pid).create_time())
            dump(self.dst / "ENGINE_STARTED.json", self.marker)
            result = guard.adopt_member(self.source, self.work, self.member, psutil.Process(process.pid).exe())
            self.assertEqual(result["decision"], "WAIT_FOR_ORIGINAL_ENGINE", result)
            self.assertIsNone(process.poll())
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None:
                process.wait(timeout=5)

    def test_unreadable_process_is_unknown(self):
        result = self.adopt(probe=lambda *args: {"state": "UNKNOWN", "reason": "AccessDenied"})
        self.assertEqual(result["decision"], "HOLD")
        self.assertIsNone(result["engine_exit_code"])

    def test_live_process_with_wrong_declared_executable_is_not_adopted(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)", "model.inp"], cwd=self.dst)
        try:
            import psutil
            self.marker.update(pid=process.pid, created=psutil.Process(process.pid).create_time())
            dump(self.dst / "ENGINE_STARTED.json", self.marker)
            result = guard.adopt_member(self.source, self.work, self.member, self.root / "not-the-engine.exe")
            self.assertEqual(result["decision"], "HOLD")
            self.assertIsNone(process.poll())
        finally:
            process.wait(timeout=5)

    def test_pid_reuse_does_not_target_current_process(self):
        import psutil
        self.marker.update(pid=os.getpid(), created=psutil.Process().create_time() - 100)
        dump(self.dst / "ENGINE_STARTED.json", self.marker)
        result = self.assess()
        self.assertEqual(result["decision"], "ADOPTABLE_SAVED_OUTPUTS", result)
        self.assertIn("reused", result["process"]["reason"])

    def test_output_must_terminate_normally(self):
        (self.dst / "model.out").write_bytes(b"Mplus VERSION 9\n*** ERROR\n")
        self.assertEqual(self.adopt()["decision"], "HOLD")

    def test_nonfinite_numeric_output_refused(self):
        for value in (b"NaN 0.25\n", b"1.0e999 0.25\n", b"bad 1.25 0.25\n", b""):
            with self.subTest(value=value):
                (self.dst / "estimates.dat").write_bytes(value)
                self.assertEqual(self.adopt()["decision"], "HOLD")

    def test_missing_runtime_input_is_not_reconstructed_as_proof(self):
        (self.dst / "data.dat").unlink()
        self.assertEqual(self.adopt()["decision"], "HOLD")
        self.assertFalse((self.dst / "data.dat").exists())

    def test_outputs_older_than_launch_refused(self):
        os.utime(self.dst / "tech3.dat", (1, 1))
        self.assertEqual(self.adopt()["decision"], "HOLD")

    def test_hardlinked_output_is_not_independent(self):
        (self.dst / "tech3.dat").unlink()
        os.link(self.src / "tech3.dat", self.dst / "tech3.dat")
        self.assertEqual(self.adopt()["decision"], "HOLD")

    def test_recovery_lock_prevents_second_writer(self):
        with guard.recovery_lock(self.work):
            with self.assertRaises(OSError):
                self.adopt()
        self.assertFalse((self.work / "recovery_adoptions").exists())

    def test_report_cannot_overwrite_original_source(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "orphan_output_guard.py"),
                                 "--source", str(self.source), "--work", str(self.work),
                                 "--member", self.member, "--engine", sys.executable,
                                 "--report", str(self.src / "new-report.json")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.src / "new-report.json").exists())


if __name__ == "__main__":
    unittest.main()
