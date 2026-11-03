"""队列不能漏计旧尝试、重置家族额度或改动原计划。"""
import copy
from pathlib import Path
import tempfile
import unittest

import rstudio_queue_admission as queue


class QueueAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"prior_named_engine_calls": 146, "prior_named_engine_seconds": 16844.34228039952,
                     "per_model_seconds": 240, "max_new_engine_calls": 78, "max_new_engine_seconds": 18720,
                     "members": [{"id": "same-model", "data_sha256": "original"}],
                     "single_model_base": {"resources": {"minimum_available_gib": 1.6}}}
        self.cost = {"source": "oldest/result.json", "engine_accounting_complete": True,
                     "new_engine_calls": 7, "new_engine_seconds": 837.1107531001326}

    def test_rebase_preserves_original_and_every_scientific_budget(self):
        before = copy.deepcopy(self.plan)
        result = queue.rebase(self.plan, [self.cost])
        self.assertEqual(self.plan, before)
        self.assertEqual(result["prior_named_engine_calls"], 153)
        self.assertAlmostEqual(result["prior_named_engine_seconds"], 17681.453033499653)
        for key in ("per_model_seconds", "max_new_engine_calls", "max_new_engine_seconds", "members"):
            self.assertEqual(result[key], before[key])

    def test_open_cost_cannot_admit_next_family(self):
        with self.assertRaises(ValueError):
            queue.rebase(self.plan, [{**self.cost, "engine_accounting_complete": False}])

    def test_same_source_cannot_be_counted_twice(self):
        with self.assertRaises(ValueError):
            queue.rebase(self.plan, [self.cost, self.cost])

    def test_unknown_and_nonfinite_costs_cannot_become_zero(self):
        for value in (None, float("nan"), float("inf"), -1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                queue.rebase(self.plan, [{**self.cost, "new_engine_seconds": value}])

    def test_claim_receipt_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "ADMISSION.json"
            queue.write_once(target, {"status": "ADMITTED"})
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                queue.write_once(target, {"status": "ADMITTED_AGAIN"})
            self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
