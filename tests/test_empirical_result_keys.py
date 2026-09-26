"""Synthetic result-assembly failures; no R/Stata or study data are executed."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/clauder-rstudio-workbench"))
from clauder_workbench.empirical_trace import audit_table, checked_file, TraceError


class ResultKeysTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "result.csv"
        self.rows = "model,term,p,n\nm1,a,0.10,12\nm1,b,0.20,12\nm2,a,0.30,15\nm2,b,0.40,15\n"
        self.table = {"artifact": self.write(self.rows), "row_keys": ["model", "term"],
                      "required_columns": ["p", "n"], "expected_n": 4,
                      "expected_rows": [["m1", "a"], ["m1", "b"], ["m2", "a"], ["m2", "b"]],
                      "expected_cell_rows": [{"key": ["m2", "a"], "values": {"p": "0.30", "n": 15}}]}

    def write(self, text):
        self.path.write_text(text)
        return {"path": str(self.path), "sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
                "bytes": self.path.stat().st_size}

    def test_order_independent_complete_keys(self):
        self.table["artifact"] = self.write("\n".join([self.rows.splitlines()[0], *reversed(self.rows.splitlines()[1:])]) + "\n")
        self.assertEqual(audit_table(self.table)["rows"], 4)

    def test_recycled_p_vector_expands_rows_and_is_rejected(self):
        self.table["artifact"] = self.write(self.rows + "m1,a,0.20,12\nm1,a,0.30,12\n")
        with self.assertRaisesRegex(TraceError, "DUPLICATED_SAMPLE_KEY"):
            audit_table(self.table)

    def test_same_count_different_terms_is_rejected(self):
        self.table["artifact"] = self.write(self.rows.replace("m1,b", "m1,c"))
        with self.assertRaisesRegex(TraceError, "TABLE_ROWS_MISSING_OR_EXTRA"):
            audit_table(self.table)

    def test_correct_p_vector_bound_to_wrong_row_is_rejected(self):
        self.table["artifact"] = self.write(self.rows.replace("m2,a,0.30", "m2,a,0.40").replace("m2,b,0.40", "m2,b,0.30"))
        with self.assertRaisesRegex(TraceError, "DENOMINATOR_LABEL"):
            audit_table(self.table)

    def test_ambiguous_or_incomplete_contracts_fail(self):
        cases = [dict(row_key="model"), dict(row_keys=["model", "model"]),
                 dict(expected_rows=None), dict(expected_rows=[["m1", "a"]] * 4),
                 dict(expected_rows=["m1/a"]), dict(expected_n=True)]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(TraceError):
                audit_table({**self.table, **changes})

    def test_size_is_checked_and_does_not_replace_hash(self):
        checked_file(self.table["artifact"])
        for bad in (True, -1, self.path.stat().st_size + 1):
            with self.subTest(bytes=bad), self.assertRaisesRegex(TraceError, "FILE_SIZE_MISMATCH"):
                checked_file({**self.table["artifact"], "bytes": bad})
        self.path.write_text(self.rows.replace("0.30", "0.31"))
        with self.assertRaisesRegex(TraceError, "FILE_MISSING_OR_CHANGED"):
            checked_file(self.table["artifact"])


if __name__ == "__main__":
    unittest.main()
