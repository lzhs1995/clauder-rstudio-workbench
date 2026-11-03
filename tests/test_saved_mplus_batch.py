"""针对实际误接受风险的合成负例；不读取研究数据，不运行引擎。"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import importlib.util

SCRIPT = Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts/verify_saved_batch.py"
SPEC = importlib.util.spec_from_file_location("verify_saved_batch", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
verify_batch = MODULE.verify_batch


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.returned = self.root / "source", self.root / "returned"
        self.member = "SYNTHETIC_MI01_A"
        self.src = self.source / "models" / self.member
        self.dst = self.returned / "models" / self.member
        self.src.mkdir(parents=True)
        self.dst.mkdir(parents=True)
        write_json(self.source / "contracts/RUN_CONTRACT.json",
                   {"primary_sequence": [self.member]})
        for name, value in {
            "model.inp": b"DATA: FILE=data.dat;\n",
            "data.dat": b"1 2 3\n4 5 6\n",
            "model.out": b"Mplus VERSION 9\n11/01/2026  08:00 PM\n"
                         b"THE MODEL ESTIMATION TERMINATED NORMALLY\n"
                         b"H0 Value -5.25\nElapsed Time: 00:00:01\n",
            "estimates.dat": b"1.25E+00 2.5D-01\n",
            "tech3.dat": b"6.25E-02\n",
        }.items():
            (self.src / name).write_bytes(value)
            if name != "data.dat":
                (self.dst / name).write_bytes(value)
        self.hashes = {name: digest(self.src / name) for name in ("model.inp", "data.dat")}
        write_json(self.src / "job.json", {"hashes": self.hashes, "cap_seconds": 240})
        write_json(self.src / "engine_receipt.json", {"wall_seconds": 1})
        self.receipt = {
            "member": self.member, "engine_exit_code": 0, "engine_state": "EXITED",
            "status": "PASS_IDENTICAL", "wall_seconds": 1, "probe_cap_seconds": 240,
            "inputs": self.hashes.copy(), "removed_input_copies": ["data.dat"],
            "compare": {name: {"sha_new": digest(self.dst / name)}
                        for name in ("model.out", "estimates.dat", "tech3.dat")},
        }
        self.save_receipt()

    def save_receipt(self):
        write_json(self.dst / "RESULT.json", self.receipt)

    def result(self):
        return verify_batch(self.source, self.returned)

    def test_complete_normal_result(self):
        result = self.result()
        self.assertEqual(result["status"], "BATCH_OUTPUTS_VERIFIED")
        self.assertEqual(result["members"][0]["input_copy_bytes_no_longer_available_for_independent_read"],
                         ["data.dat"])

    def test_non_normal_with_matching_sidecars_is_rejected(self):
        (self.dst / "model.out").write_bytes(b"*** ERROR\n")
        self.receipt["compare"]["model.out"]["sha_new"] = digest(self.dst / "model.out")
        self.receipt["status"] = "PASS_NUMERIC"
        self.save_receipt()
        self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")

    def test_error_summary_overrides_matching_normal_outputs(self):
        for summary, expected in (
                (b"0 ERROR(S) FOUND IN THE INPUT INSTRUCTIONS", "BATCH_OUTPUTS_VERIFIED"),
                (b"1 ERROR(S) FOUND IN THE INPUT INSTRUCTIONS", "REVIEW_REQUIRED"),
                (b"12 ERROR(S) FOUND IN THE\n INPUT INSTRUCTIONS", "REVIEW_REQUIRED")):
            with self.subTest(summary=summary):
                content = b"THE MODEL ESTIMATION TERMINATED NORMALLY\n" + summary + b"\n"
                for folder in (self.src, self.dst):
                    (folder / "model.out").write_bytes(content)
                self.receipt["compare"]["model.out"]["sha_new"] = digest(self.dst / "model.out")
                self.save_receipt()
                self.assertEqual(self.result()["status"], expected)

    def test_output_changed_after_receipt_is_rejected(self):
        (self.dst / "estimates.dat").write_bytes(b"999\n")
        self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")

    def test_invalid_numeric_outputs_cannot_match_each_other(self):
        for invalid in (b"", b"NaN", b"Inf", b"1e999", b"value=1.25"):
            with self.subTest(invalid=invalid):
                (self.src / "estimates.dat").write_bytes(invalid)
                (self.dst / "estimates.dat").write_bytes(invalid)
                self.receipt["compare"]["estimates.dat"]["sha_new"] = digest(self.dst / "estimates.dat")
                self.save_receipt()
                self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")

    def test_changed_original_data_invalidates_input_binding(self):
        (self.src / "data.dat").write_bytes(b"7 8 9\n")
        self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")

    def test_unknown_extra_member_is_not_accepted(self):
        (self.returned / "models" / "SYNTHETIC_MI01_B").mkdir()
        self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")

    def test_missing_expected_member_is_not_accepted(self):
        write_json(self.source / "contracts/RUN_CONTRACT.json",
                   {"primary_sequence": [self.member, "SYNTHETIC_MI02_A"]})
        self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")

    def test_changed_output_content_with_forged_receipt_requires_review(self):
        p = self.dst / "model.out"
        p.write_bytes(p.read_bytes().replace(b"H0 Value -5.25", b"H0 Value -6.75"))
        self.receipt["compare"]["model.out"]["sha_new"] = digest(p)
        self.save_receipt()
        self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")

    def test_only_clock_lines_may_change_without_review(self):
        p = self.dst / "model.out"
        p.write_bytes(p.read_bytes().replace(b"08:00 PM", b"09:00 PM").replace(b"00:00:01", b"00:00:04"))
        self.receipt["compare"]["model.out"]["sha_new"] = digest(p)
        self.save_receipt()
        self.assertEqual(self.result()["status"], "BATCH_OUTPUTS_VERIFIED")

    def test_hardlink_to_original_is_not_independent_output(self):
        target = self.dst / "model.out"
        target.unlink()
        os.link(self.src / "model.out", target)
        self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")

    def add_provenance_metadata(self):
        p = self.src / "normalized_slots.json"
        p.write_text('{"slot": "synthetic"}', encoding="utf-8")
        hashes = {**self.hashes, p.name: digest(p)}
        write_json(self.src / "job.json", {"hashes": hashes, "cap_seconds": 240})
        return p

    def test_metadata_needs_explicit_scoped_declaration(self):
        self.add_provenance_metadata()
        self.assertEqual(self.result()["status"], "REVIEW_REQUIRED")
        result = verify_batch(self.source, self.returned,
                              provenance_only=["normalized_slots.json"])
        self.assertEqual(result["status"], "BATCH_OUTPUTS_VERIFIED")

    def test_declared_metadata_hash_is_still_verified(self):
        p = self.add_provenance_metadata()
        p.write_text('{"slot": "changed"}', encoding="utf-8")
        result = verify_batch(self.source, self.returned,
                              provenance_only=["normalized_slots.json"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_runtime_input_cannot_be_declared_as_metadata(self):
        with self.assertRaises(ValueError):
            verify_batch(self.source, self.returned, provenance_only=["data.dat"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
