from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from clauder_workbench import fanout

# Load the standalone CMAverse skill scripts by path (they are not part of the
# clauder_workbench package).
REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "cmaverse-paired-mval" / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


make_contract = _load("make_worker_contract")
cma_validate = _load("cmaverse_validate")


class MakeWorkerContractTests(unittest.TestCase):
    def _args(self, tmp, **over):
        ns = make_contract.parse_args([
            "--worker-file", str(SCRIPTS.parent / "assets" / "worker_template.R"),
            "--output-root", str(Path(tmp) / "out"),
            "--run-id", "RUN1",
            "--max-parallel", "7",
            "--mediators", "msat_c12_2,msat_c12_3",
            "--groups", "sy_female,sy_male",
            "--nboot", "10",
            "--seed", "12345",
            "--out", str(Path(tmp) / "task.yaml"),
        ])
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    def test_contract_keys_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = make_contract.build_contract(self._args(tmp))
            self.assertEqual(len(c["workers"]), 2)
            self.assertEqual(c["meta"]["expected_validation_rows"], 4)
            self.assertIn("output_root", c["artifacts"])
            for w in c["workers"]:
                for key in ("id", "code_file", "env",
                            "expected_state", "expected_manifest", "expected_validation"):
                    self.assertIn(key, w)

    def test_roundtrip_through_minimal_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self._args(tmp)
            self.assertEqual(make_contract.main(_argv_from(args)), 0)
            text = Path(args.out).read_text(encoding="utf-8")
            parsed = fanout._minimal_yaml(text)
            self.assertEqual(fanout._validate_contract(parsed), [])
            # paths normalized to forward slashes (no doubled backslashes)
            w = parsed["workers"][0]
            self.assertNotIn("\\\\", w["code_file"])
            self.assertNotIn("\\", w["env"]["NEW47_OUTPUT_ROOT"])

    def test_roundtrip_through_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self._args(tmp)
            self.assertEqual(make_contract.main(_argv_from(args)), 0)
            c = fanout.load_fanout_contract(args.out)
            w = c["workers"][1]
            resolved = fanout.resolve_worker_path(c, w, "expected_state")
            self.assertTrue(str(resolved).endswith("state_msat_c12_3.json"))


class CmaverseValidateTests(unittest.TestCase):
    HEADER = ("mediator,group,m0_is_full_cmest,m1_is_full_cmest,"
              "m0_effect_n,m1_effect_n,m0_data_ncol,m1_data_ncol,"
              "m0_ref_mval,m1_ref_mval,m0_boot_hash,m1_boot_hash,"
              "paired_same_bootstrap")
    # legacy CSV without the pairing-proof columns
    LEGACY_HEADER = ("mediator,group,m0_is_full_cmest,m1_is_full_cmest,"
                     "m0_effect_n,m1_effect_n,m0_data_ncol,m1_data_ncol,"
                     "m0_ref_mval,m1_ref_mval")

    def _write(self, root, mediator, rows, header=None):
        d = Path(root) / mediator
        d.mkdir(parents=True, exist_ok=True)
        (d / f"validation_{mediator}.csv").write_text(
            "\n".join([header or self.HEADER] + rows) + "\n", encoding="utf-8")

    def _run(self, root, **over):
        argv = ["--output-root", str(root),
                "--mediators", "msat_c12_2,msat_c12_3",
                "--groups", "sy_female,sy_male"]
        for k, v in over.items():
            argv += [f"--{k}", str(v)] if v is not True else [f"--{k}"]
        return cma_validate.validate(cma_validate.parse_args(argv))

    def test_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,h1,TRUE",
                    f"{m},sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
                ])
            r = self._run(tmp)
            self.assertEqual(r["decision"], "PASS")
            self.assertEqual(r["exit_code"], 0)
            self.assertEqual(r["actual_rows"], 4)
            self.assertFalse(r["weak_validation"])

    def test_fail_on_ncol(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "msat_c12_2", [
                "msat_c12_2,sy_female,TRUE,TRUE,17,17,158,159,0,1,h1,h1,TRUE",
                "msat_c12_2,sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
            ])
            self._write(tmp, "msat_c12_3", [
                "msat_c12_3,sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,h1,TRUE",
                "msat_c12_3,sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
            ])
            r = self._run(tmp)
            self.assertEqual(r["exit_code"], cma_validate.EXIT_FAILED)
            self.assertTrue(any("data ncol" in f for f in r["failures"]))

    def test_fail_on_mval(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,0,0,h1,h1,TRUE",
                    f"{m},sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
                ])
            r = self._run(tmp)
            self.assertEqual(r["exit_code"], cma_validate.EXIT_FAILED)
            self.assertTrue(any("ref mval != 1" in f for f in r["failures"]))

    def test_fail_on_empty_mval(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,,1,h1,h1,TRUE",
                    f"{m},sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
                ])
            r = self._run(tmp)
            self.assertEqual(r["exit_code"], cma_validate.EXIT_FAILED)
            self.assertTrue(any("ref mval != 0" in f for f in r["failures"]))

    def test_fail_on_wrong_mediator(self):
        with tempfile.TemporaryDirectory() as tmp:
            # msat_c12_3's file contains rows tagged with the wrong mediator
            self._write(tmp, "msat_c12_2", [
                "msat_c12_2,sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,h1,TRUE",
                "msat_c12_2,sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
            ])
            self._write(tmp, "msat_c12_3", [
                "msat_c12_2,sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,h1,TRUE",
                "msat_c12_2,sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
            ])
            r = self._run(tmp)
            self.assertEqual(r["exit_code"], cma_validate.EXIT_FAILED)
            self.assertTrue(any("row mediator" in f for f in r["failures"]))

    def test_fail_on_duplicate_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,h1,TRUE",
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,h1,TRUE",
                ])  # sy_female twice, sy_male absent
            r = self._run(tmp)
            self.assertEqual(r["exit_code"], cma_validate.EXIT_FAILED)
            self.assertTrue(any("duplicate validation row" in f for f in r["failures"]))

    def test_fail_on_pairing_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,hX,FALSE",
                    f"{m},sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
                ])
            r = self._run(tmp)
            self.assertEqual(r["exit_code"], cma_validate.EXIT_FAILED)
            self.assertTrue(any("paired_same_bootstrap is not TRUE" in f
                                for f in r["failures"]))

    def test_fail_on_missing_pairing_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,0,1",
                    f"{m},sy_male,TRUE,TRUE,17,17,159,159,0,1",
                ], header=self.LEGACY_HEADER)
            r = self._run(tmp)
            self.assertEqual(r["exit_code"], cma_validate.EXIT_FAILED)
            self.assertTrue(any("missing paired_same_bootstrap" in f
                                for f in r["failures"]))

    def test_no_pairing_check_passes_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,0,1",
                    f"{m},sy_male,TRUE,TRUE,17,17,159,159,0,1",
                ], header=self.LEGACY_HEADER)
            r = self._run(tmp, **{"no-pairing-check": True})
            self.assertEqual(r["decision"], "PASS")
            self.assertTrue(r["weak_validation"])

    def test_missing_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "msat_c12_2", [
                "msat_c12_2,sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,h1,TRUE",
                "msat_c12_2,sy_male,TRUE,TRUE,17,17,159,159,0,1,h2,h2,TRUE",
            ])
            r = self._run(tmp)  # msat_c12_3 missing
            self.assertEqual(r["exit_code"], cma_validate.EXIT_MISSING)
            self.assertTrue(r["missing"])

    def test_missing_group_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,17,17,159,159,0,1,h1,h1,TRUE",
                ])  # sy_male row absent
            r = self._run(tmp)
            self.assertEqual(r["exit_code"], cma_validate.EXIT_FAILED)
            self.assertTrue(any("missing validation row" in f for f in r["failures"]))

    def test_no_count_check_passes_wrong_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for m in ("msat_c12_2", "msat_c12_3"):
                self._write(tmp, m, [
                    f"{m},sy_female,TRUE,TRUE,99,99,1,1,0,1,h1,h1,TRUE",
                    f"{m},sy_male,TRUE,TRUE,99,99,1,1,0,1,h2,h2,TRUE",
                ])
            r = self._run(tmp, **{"no-count-check": True})
            self.assertEqual(r["decision"], "PASS")
            self.assertTrue(r["weak_validation"])


def _argv_from(ns):
    return [
        "--worker-file", ns.worker_file,
        "--output-root", ns.output_root,
        "--run-id", ns.run_id,
        "--max-parallel", str(ns.max_parallel),
        "--mediators", ns.mediators,
        "--groups", ns.groups,
        "--nboot", str(ns.nboot),
        "--seed", str(ns.seed),
        "--out", ns.out,
    ]


if __name__ == "__main__":
    unittest.main()
