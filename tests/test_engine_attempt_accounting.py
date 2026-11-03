"""调用成本的可移植反例；无真实引擎或研究数据。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts/engine_attempt_accounting.py"
spec = importlib.util.spec_from_file_location("engine_attempt_accounting", SOURCE)
costs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(costs)


class CostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.work, self.output = self.root / "work", self.root / "output"
        self.work.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, root, name, value):
        root.mkdir(exist_ok=True)
        (root / name).write_text(json.dumps(value), encoding="utf-8")

    def receipt(self, **changes):
        return {"member": "m1", "actual_engine_calls": 1,
                "engine_exit_confirmed": True, "elapsed_seconds": 3.25, **changes}

    def inspect(self):
        return costs.inspect_attempt("m1", self.work, self.output, 10, self.root / "saved")

    def test_absent_attempt_is_zero(self):
        result = costs.totals([self.inspect()])
        self.assertEqual(costs.require_closed_budget(result), (0, 0))

    def test_dangling_evidence_cannot_reopen_zero_cost_budget(self):
        for name in ("CLAIM.json", "ENGINE_STARTED.json", "ENGINE_RECEIPT.json",
                     "RSTUDIO_REQUEST_CLAIM.json"):
            with self.subTest(name=name):
                path = self.work / name
                try:
                    path.symlink_to(self.root / "missing-receipt")
                except OSError as error:
                    self.skipTest(f"Symlinks unavailable: {error}")
                try:
                    item = self.inspect()
                    self.assertFalse(item["accounting_complete"])
                    self.assertNotEqual(item["state"], "NO_START_EVIDENCE")
                    with self.assertRaises(ValueError):
                        costs.require_closed_budget(costs.totals([item]))
                    self.assertTrue(path.is_symlink())
                finally:
                    path.unlink()

    def test_direct_and_guard_terminal_receipts_without_export_are_counted(self):
        for relative in (".", "guard"):
            with self.subTest(relative=relative):
                self.write(self.work / relative, "ENGINE_RECEIPT.json", self.receipt())
                result = costs.totals([self.inspect()])
                self.assertEqual(costs.require_closed_budget(result), (1, 3.25))

    def test_unknown_exit_does_not_publish_cap_as_exact_elapsed_time(self):
        self.write(self.work, "ENGINE_RECEIPT.json", self.receipt(engine_exit_confirmed=False))
        item = self.inspect()
        result = costs.totals([item])
        self.assertEqual(result["new_engine_calls"], 1)
        self.assertIsNone(result["new_engine_seconds"])
        self.assertEqual(result["reserved_engine_seconds"], 10)
        self.assertFalse(item["reservation_is_elapsed_upper_bound"])
        with self.assertRaises(ValueError):
            costs.require_closed_budget(result)

    def test_claim_alone_keeps_both_costs_unknown(self):
        self.write(self.work, "RSTUDIO_REQUEST_CLAIM.json", {"request": "synthetic"})
        result = costs.totals([self.inspect()])
        self.assertIsNone(result["new_engine_calls"])
        self.assertIsNone(result["new_engine_seconds"])
        self.assertEqual(result["reserved_engine_calls"], 1)
        self.assertFalse(result["followup_budget_eligible"])

    def test_duplicate_exports_do_not_double_count(self):
        for root in (self.work, self.work / "guard", self.work / "guard_export", self.output):
            self.write(root, "ENGINE_RECEIPT.json", self.receipt())
        self.assertEqual(costs.require_closed_budget(costs.totals([self.inspect()])), (1, 3.25))

    def test_disagreeing_receipts_refuse_exact_cost(self):
        self.write(self.work, "ENGINE_RECEIPT.json", self.receipt())
        self.write(self.output, "ENGINE_RECEIPT.json", self.receipt(elapsed_seconds=0))
        result = costs.totals([self.inspect()])
        self.assertEqual(result["new_engine_calls"], 1)
        self.assertIsNone(result["new_engine_seconds"])
        self.assertFalse(result["followup_budget_eligible"])

    def test_started_marker_disagrees_with_zero_calls(self):
        self.write(self.work, "ENGINE_RECEIPT.json", self.receipt(actual_engine_calls=0))
        self.write(self.work, "ENGINE_STARTED.json", {"pid": 123})
        item = self.inspect()
        self.assertEqual(item["actual_engine_calls"], 1)
        self.assertFalse(item["accounting_complete"])

    def test_nonfinite_and_wrong_member_receipts_do_not_close_cost(self):
        for value in (self.receipt(member="other"), self.receipt(elapsed_seconds=float("nan"))):
            with self.subTest(value=value):
                self.write(self.work, "ENGINE_RECEIPT.json", value)
                result = costs.totals([self.inspect()])
                self.assertFalse(result["followup_budget_eligible"])
                json.dumps(result, allow_nan=False)

    def test_changed_receipt_preserves_saved_bytes(self):
        self.write(self.work, "ENGINE_RECEIPT.json", self.receipt())
        self.inspect()
        path = self.root / "saved/m1/work/ENGINE_RECEIPT.json"
        before = path.read_bytes()
        self.write(self.work, "ENGINE_RECEIPT.json", self.receipt(elapsed_seconds=0))
        self.assertFalse(self.inspect()["accounting_complete"])
        self.assertEqual(path.read_bytes(), before)

    def test_legacy_numeric_cost_requires_finite_values(self):
        self.assertEqual(costs.require_closed_budget({"new_engine_calls": 2, "new_engine_seconds": 3.5}), (2, 3.5))
        for fields in ({"new_engine_calls": None, "new_engine_seconds": 0},
                       {"new_engine_calls": 0, "new_engine_seconds": float("inf")},
                       {"new_engine_calls": 1, "new_engine_seconds": 2, "followup_budget_eligible": False}):
            with self.assertRaises(ValueError):
                costs.require_closed_budget(fields)


if __name__ == "__main__":
    unittest.main()
