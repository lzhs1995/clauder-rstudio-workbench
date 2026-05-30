from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from clauder_workbench.fanout import (
    _minimal_yaml,
    build_submit_code,
    load_fanout_contract,
    merge_gate,
    plan_fanout,
    poll_once,
    run_fanout,
    state_is_complete,
    worker_status,
)

CONTRACT_TEMPLATE = """task_key: t_demo
transport: mcp-stdio
session_name: default2
poll_interval_sec: 5
job_timeout_min: 30
max_parallel: 2
artifacts:
  output_root: {root}
resource_gate:
  memory_threshold: 85
workers:
  - id: w1
    code_file: C:/tmp/w1.R
    env:
      NEW47_MEDIATOR: w1
    expected_state: state_w1.json
    expected_manifest: manifest_w1.csv
    expected_validation: validation_w1.csv
  - id: w2
    code_file: C:/tmp/w2.R
    expected_state: state_w2.json
    expected_manifest: manifest_w2.csv
    expected_validation: validation_w2.csv
"""


def _write_contract(root: Path) -> Path:
    text = CONTRACT_TEMPLATE.format(root=str(root).replace("\\", "/"))
    path = root / "task.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _complete_worker(root: Path, wid: str) -> None:
    (root / f"state_{wid}.json").write_text('{"stage":"complete"}', encoding="utf-8")
    (root / f"manifest_{wid}.csv").write_text(f"id,v\n{wid},1\n", encoding="utf-8")
    (root / f"validation_{wid}.csv").write_text(f"id,ok\n{wid},TRUE\n", encoding="utf-8")


class FanoutTests(unittest.TestCase):
    def test_minimal_yaml_parses_nested_workers(self) -> None:
        data = _minimal_yaml(CONTRACT_TEMPLATE.format(root="C:/r"))
        self.assertEqual(data["task_key"], "t_demo")
        self.assertEqual(len(data["workers"]), 2)
        self.assertEqual(data["workers"][0]["id"], "w1")
        self.assertEqual(data["workers"][0]["env"]["NEW47_MEDIATOR"], "w1")
        self.assertEqual(data["artifacts"]["output_root"], "C:/r")
        self.assertEqual(data["max_parallel"], 2)

    def test_state_is_complete_variants(self) -> None:
        self.assertTrue(state_is_complete({"stage": "complete"}))
        self.assertTrue(state_is_complete({"status": "done"}))
        self.assertTrue(state_is_complete({"complete": True}))
        self.assertFalse(state_is_complete({"stage": "running"}))
        self.assertFalse(state_is_complete({}))

    def test_build_submit_code_bakes_env_and_source(self) -> None:
        worker = {"id": "w1", "code_file": "C:/tmp/w1.R", "env": {"K": "v"}}
        code = build_submit_code(worker)
        self.assertIn('Sys.setenv("K" = "v")', code)
        self.assertIn('source("C:/tmp/w1.R"', code)

    def test_plan_validates_and_advises(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_write_contract(root))
            plan = plan_fanout(contract)
            self.assertTrue(plan["ok"])
            self.assertEqual(plan["worker_count"], 2)
            self.assertEqual(plan["requested_max_parallel"], 2)

    def test_plan_reports_missing_fields(self) -> None:
        contract = {"workers": [{"id": "x"}], "_contract_path": "x"}
        plan = plan_fanout(contract)
        self.assertFalse(plan["ok"])
        self.assertTrue(any("code_file" in p for p in plan["problems"]))

    def test_poll_and_merge_gate_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_write_contract(root))

            poll = poll_once(contract)
            self.assertFalse(poll["all_complete"])
            self.assertEqual(set(poll["pending"]), {"w1", "w2"})

            _complete_worker(root, "w1")
            gate = merge_gate(contract)
            self.assertFalse(gate["ok"])
            self.assertFalse(gate["all_complete"])
            self.assertTrue(gate["violations"])

            _complete_worker(root, "w2")
            gate2 = merge_gate(contract)
            self.assertTrue(gate2["ok"])
            self.assertTrue(gate2["all_complete"])
            self.assertEqual(gate2["violations"], [])

    def test_worker_status_requires_all_three_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_write_contract(root))
            w1 = contract["workers"][0]
            # only state complete, no manifest/validation -> not complete
            (root / "state_w1.json").write_text('{"stage":"complete"}', encoding="utf-8")
            status = worker_status(contract, w1)
            self.assertTrue(status["state_complete"])
            self.assertFalse(status["complete"])

    def test_run_fanout_submits_and_completes_with_fake_transport(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_write_contract(root))
            submitted: list[str] = []

            def submit_fn(code: str) -> dict:
                # simulate the worker producing its durable three-file output on submit
                wid = "w1" if "w1" in code else "w2"
                _complete_worker(root, wid)
                submitted.append(wid)
                return {"ok": True, "job_id": f"job_{wid}", "text": f"Job job_{wid} started"}

            registered: list[tuple[str, str]] = []
            result = run_fanout(
                contract,
                submit_fn=submit_fn,
                max_parallel=2,
                poll_interval_sec=0,
                sleep_fn=lambda s: None,
                register_fn=lambda wid, jid: registered.append((wid, jid)),
                max_iterations=5,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["transport_class"], "MCP_STDIO_OK")
            self.assertEqual(set(result["done"]), {"w1", "w2"})
            self.assertEqual(set(submitted), {"w1", "w2"})
            self.assertEqual(len(registered), 2)

    def test_run_fanout_reports_submit_failure(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_write_contract(root))

            def submit_fn(code: str) -> dict:
                return {"ok": False, "job_id": None, "text": "error: no session"}

            result = run_fanout(
                contract,
                submit_fn=submit_fn,
                max_parallel=2,
                poll_interval_sec=0,
                sleep_fn=lambda s: None,
                max_iterations=3,
            )
            self.assertFalse(result["ok"])
            self.assertTrue(result["failed"])

    def test_run_fanout_ignores_stale_prior_outputs_by_default(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_write_contract(root))
            # 模拟上一轮遗留的"完成"产出（很旧）
            _complete_worker(root, "w1")
            _complete_worker(root, "w2")
            old = time.time() - 7200
            for name in root.glob("*"):
                if name.name != "task.yaml":
                    os.utime(name, (old, old))

            submitted: list[str] = []

            def submit_fn(code: str) -> dict:
                wid = "w1" if "w1" in code else "w2"
                _complete_worker(root, wid)  # 本轮写入新产出
                submitted.append(wid)
                return {"ok": True, "job_id": f"job_{wid}", "text": f"Job job_{wid} started"}

            result = run_fanout(
                contract, submit_fn=submit_fn, max_parallel=2,
                poll_interval_sec=0, sleep_fn=lambda s: None, max_iterations=5,
            )
            # 默认不复用旧产出：两个 worker 都被重新提交
            self.assertEqual(set(submitted), {"w1", "w2"})
            self.assertTrue(result["ok"])

    def test_run_fanout_reuse_existing_skips_complete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_write_contract(root))
            _complete_worker(root, "w1")  # w1 已完成
            submitted: list[str] = []

            def submit_fn(code: str) -> dict:
                wid = "w1" if "w1" in code else "w2"
                _complete_worker(root, wid)
                submitted.append(wid)
                return {"ok": True, "job_id": f"job_{wid}", "text": f"Job job_{wid} started"}

            result = run_fanout(
                contract, submit_fn=submit_fn, max_parallel=2, reuse_existing=True,
                poll_interval_sec=0, sleep_fn=lambda s: None, max_iterations=5,
            )
            self.assertEqual(submitted, ["w2"])  # 仅 w2 被提交
            self.assertIn("w1", result["done"])
            self.assertTrue(result["ok"])

    def test_merge_gate_rejects_stale_with_max_age_h(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            text = CONTRACT_TEMPLATE.format(root=str(root).replace("\\", "/"))
            text = text.replace("artifacts:\n", "artifacts:\n  max_age_h: 1\n")
            path = root / "task.yaml"
            path.write_text(text, encoding="utf-8")
            contract = load_fanout_contract(path)
            _complete_worker(root, "w1")
            _complete_worker(root, "w2")
            old = time.time() - 7200
            for name in root.glob("*"):
                if name.name != "task.yaml":
                    os.utime(name, (old, old))
            gate = merge_gate(contract)
            self.assertFalse(gate["ok"])
            self.assertTrue(any("stale" in v for v in gate["violations"]))

    def test_minimal_yaml_fails_fast_on_block_scalar(self) -> None:
        bad = "workers:\n  - id: w1\n    code: |\n      source('x.R')\n"
        with self.assertRaises(ValueError):
            _minimal_yaml(bad)

    def test_fanout_run_blocks_native_wrapper_transport(self) -> None:
        # fanout-run only submits via mcp-stdio; asking it to act as a native
        # wrapper must BLOCK and point to the native fanout-plan path.
        import io
        from contextlib import redirect_stdout
        from clauder_workbench import cli

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = _write_contract(root)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["fanout-run", "--contract", str(contract),
                               "--transport", "native-wrapper"])
            self.assertEqual(rc, cli.BLOCK)
            doc = json.loads(buf.getvalue())
            self.assertEqual(doc["decision"], "BLOCK")
            self.assertEqual(doc["transport_class"], "BLOCKED")
            self.assertTrue(any("native-wrapper" in r or "fanout-plan" in r
                                for r in doc["reasons"]))


class FanoutSchemaPackagingTests(unittest.TestCase):
    REPO = Path(__file__).resolve().parents[1]
    SHARED = REPO / "shared" / "schemas" / "fanout-contract.schema.json"
    SHIPPED = (REPO / "skills" / "clauder-rstudio-workbench" / "schemas"
               / "fanout-contract.schema.json")

    def test_schema_ships_with_skill(self) -> None:
        self.assertTrue(self.SHIPPED.exists(),
                        "fanout-contract.schema.json must ship inside the skill so "
                        "installed runtimes have it (installer only copies skills/).")

    def test_shipped_schema_matches_shared_source(self) -> None:
        # guard against drift between the shared source and the shipped copy
        self.assertEqual(
            self.SHIPPED.read_text(encoding="utf-8"),
            self.SHARED.read_text(encoding="utf-8"),
        )
        # both must be valid JSON
        json.loads(self.SHIPPED.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
