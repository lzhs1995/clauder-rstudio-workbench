from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clauder_workbench.fanout import (
    lint_contract_workers,
    load_fanout_contract,
    plan_fanout,
    run_fanout,
)
from clauder_workbench.worker_lint import (
    lint_worker_file,
    lint_worker_text,
)

# --- F1: sink() worker lint --------------------------------------------------

CLEAN_WORKER = """suppressPackageStartupMessages(library(CMAverse))
cat('start\\n'); flush.console()
res <- cmest(...)
saveRDS(res, 'out.rds')
cat('done\\n'); flush.console()
"""

SINK_WORKER = """suppressPackageStartupMessages(library(CMAverse))
sink('worker.log', split = TRUE)
res <- cmest(...)
saveRDS(res, 'out.rds')
sink()
"""

COMMENTED_SINK_WORKER = """# never call sink() here -- it hangs the Rterm
cat('start\\n'); flush.console()
res <- cmest(...)   # do not use sink() to capture output
saveRDS(res, 'out.rds')
"""


class WorkerLintTextTests(unittest.TestCase):
    def test_clean_worker_has_no_issues(self) -> None:
        self.assertEqual(lint_worker_text(CLEAN_WORKER), [])

    def test_sink_worker_is_flagged(self) -> None:
        issues = lint_worker_text(SINK_WORKER, name="w.R")
        self.assertTrue(issues)
        self.assertTrue(all("sink()" in i for i in issues))
        # both the opening and closing sink() calls are flagged
        self.assertEqual(len(issues), 2)

    def test_sink_in_comments_is_ignored(self) -> None:
        self.assertEqual(lint_worker_text(COMMENTED_SINK_WORKER), [])

    def test_lint_worker_file_clean_and_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            clean = root / "clean.R"
            clean.write_text(CLEAN_WORKER, encoding="utf-8")
            dirty = root / "dirty.R"
            dirty.write_text(SINK_WORKER, encoding="utf-8")
            self.assertTrue(lint_worker_file(clean)["ok"])
            res = lint_worker_file(dirty)
            self.assertFalse(res["ok"])
            self.assertTrue(res["issues"])

    def test_lint_worker_file_missing_is_error_not_issue(self) -> None:
        res = lint_worker_file("C:/tmp/does_not_exist_worker.R")
        self.assertFalse(res["ok"])
        self.assertEqual(res["issues"], [])
        self.assertIn("not found", res["error"])


CONTRACT = """task_key: t_lint
transport: mcp-stdio
session_name: default2
poll_interval_sec: 5
job_timeout_min: 30
max_parallel: 2
artifacts:
  output_root: {root}
workers:
  - id: w1
    code_file: {w1}
    expected_state: state_w1.json
    expected_manifest: manifest_w1.csv
    expected_validation: validation_w1.csv
"""


def _write_contract(root: Path, worker_path: Path) -> Path:
    text = CONTRACT.format(
        root=str(root).replace("\\", "/"),
        w1=str(worker_path).replace("\\", "/"),
    )
    p = root / "task.yaml"
    p.write_text(text, encoding="utf-8")
    return p


class FanoutSinkGateTests(unittest.TestCase):
    def test_lint_contract_blocks_sink_worker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            w = root / "w1.R"
            w.write_text(SINK_WORKER, encoding="utf-8")
            contract = load_fanout_contract(_write_contract(root, w))
            lint = lint_contract_workers(contract)
            self.assertFalse(lint["ok"])
            self.assertTrue(lint["issues"])

    def test_lint_contract_missing_file_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(
                _write_contract(root, Path("C:/tmp/missing_worker.R"))
            )
            lint = lint_contract_workers(contract)
            # file-not-found is reported as an error but is NOT a hard block
            self.assertTrue(lint["ok"])
            self.assertEqual(lint["issues"], [])
            self.assertTrue(lint["errors"])

    def test_plan_fanout_flags_sink_worker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            w = root / "w1.R"
            w.write_text(SINK_WORKER, encoding="utf-8")
            contract = load_fanout_contract(_write_contract(root, w))
            plan = plan_fanout(contract)
            self.assertFalse(plan["ok"])
            self.assertTrue(any("sink()" in p for p in plan["problems"]))

    def test_run_fanout_blocks_sink_worker_before_submit(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            w = root / "w1.R"
            w.write_text(SINK_WORKER, encoding="utf-8")
            contract = load_fanout_contract(_write_contract(root, w))
            submitted: list[str] = []

            def submit_fn(code: str) -> dict:
                submitted.append(code)
                return {"ok": True, "job_id": "j", "text": "started"}

            result = run_fanout(
                contract, submit_fn=submit_fn, max_parallel=1,
                poll_interval_sec=0, sleep_fn=lambda s: None, max_iterations=3,
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["transport_class"], "BLOCKED")
            self.assertEqual(submitted, [])  # never submitted

    def test_run_fanout_runs_clean_worker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            w = root / "w1.R"
            w.write_text(CLEAN_WORKER, encoding="utf-8")
            contract = load_fanout_contract(_write_contract(root, w))

            def submit_fn(code: str) -> dict:
                (root / "state_w1.json").write_text('{"stage":"complete"}', encoding="utf-8")
                (root / "manifest_w1.csv").write_text("id,v\nw1,1\n", encoding="utf-8")
                (root / "validation_w1.csv").write_text("id,ok\nw1,TRUE\n", encoding="utf-8")
                return {"ok": True, "job_id": "j", "text": "started"}

            result = run_fanout(
                contract, submit_fn=submit_fn, max_parallel=1,
                poll_interval_sec=0, sleep_fn=lambda s: None, max_iterations=5,
            )
            self.assertTrue(result["ok"])
            self.assertIn("w1", result["done"])


# --- F2: auto-scale dynamic concurrency --------------------------------------

MULTI_CONTRACT = """task_key: t_scale
transport: mcp-stdio
session_name: default2
poll_interval_sec: 5
job_timeout_min: 30
max_parallel: 1
artifacts:
  output_root: {root}
resource_gate:
  memory_threshold: 85
workers:
{workers}
"""


def _multi_contract(root: Path, n: int) -> Path:
    rows = []
    for i in range(1, n + 1):
        rows.append(
            f"  - id: w{i}\n"
            f"    code_file: C:/tmp/w{i}.R\n"
            f"    expected_state: state_w{i}.json\n"
            f"    expected_manifest: manifest_w{i}.csv\n"
            f"    expected_validation: validation_w{i}.csv"
        )
    text = MULTI_CONTRACT.format(
        root=str(root).replace("\\", "/"),
        workers="\n".join(rows),
    )
    p = root / "task.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def _complete(root: Path, wid: str) -> None:
    (root / f"state_{wid}.json").write_text('{"stage":"complete"}', encoding="utf-8")
    (root / f"manifest_{wid}.csv").write_text(f"id,v\n{wid},1\n", encoding="utf-8")
    (root / f"validation_{wid}.csv").write_text(f"id,ok\n{wid},TRUE\n", encoding="utf-8")


class AutoScaleTests(unittest.TestCase):
    def test_low_memory_scales_up(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_multi_contract(root, 4))

            def submit_fn(code: str) -> dict:
                for i in range(1, 5):
                    if f"w{i}" in code:
                        _complete(root, f"w{i}")
                        return {"ok": True, "job_id": f"j{i}", "text": "started"}
                return {"ok": False, "job_id": None, "text": "no match"}

            result = run_fanout(
                contract, submit_fn=submit_fn, max_parallel=1, auto_scale=True,
                mem_probe_fn=lambda: 10.0,  # plenty of headroom
                poll_interval_sec=0, sleep_fn=lambda s: None, max_iterations=20,
            )
            self.assertTrue(result["ok"])
            self.assertTrue(result["auto_scale"])
            self.assertEqual(result["start_max_parallel"], 1)
            self.assertEqual(result["max_parallel_cap"], 4)
            self.assertTrue(any(e["action"] == "scale_up" for e in result["scale_log"]))
            self.assertGreater(result["max_parallel"], 1)

    def test_high_memory_throttles(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_multi_contract(root, 3))
            # start at 3, but memory is pinned high -> should throttle, never scale up
            def submit_fn(code: str) -> dict:
                for i in range(1, 4):
                    if f"w{i}" in code:
                        _complete(root, f"w{i}")
                        return {"ok": True, "job_id": f"j{i}", "text": "started"}
                return {"ok": False, "job_id": None, "text": "no match"}

            result = run_fanout(
                contract, submit_fn=submit_fn, max_parallel=3, auto_scale=True,
                mem_probe_fn=lambda: 95.0,  # over threshold
                poll_interval_sec=0, sleep_fn=lambda s: None, max_iterations=20,
            )
            self.assertTrue(result["auto_scale"])
            # no scale_up entries when memory is always over threshold
            self.assertFalse(any(e["action"] == "scale_up" for e in result["scale_log"]))

    def test_unknown_memory_holds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_multi_contract(root, 2))

            def submit_fn(code: str) -> dict:
                for i in range(1, 3):
                    if f"w{i}" in code:
                        _complete(root, f"w{i}")
                        return {"ok": True, "job_id": f"j{i}", "text": "started"}
                return {"ok": False, "job_id": None, "text": "no match"}

            result = run_fanout(
                contract, submit_fn=submit_fn, max_parallel=1, auto_scale=True,
                mem_probe_fn=lambda: None,  # probe unavailable
                poll_interval_sec=0, sleep_fn=lambda s: None, max_iterations=20,
            )
            self.assertTrue(result["ok"])
            # never scaled up because memory was unknown
            self.assertFalse(any(e["action"] == "scale_up" for e in result["scale_log"]))

    def test_cap_respects_max_parallel_cap(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            contract = load_fanout_contract(_multi_contract(root, 6))

            def submit_fn(code: str) -> dict:
                for i in range(1, 7):
                    if f"w{i}" in code:
                        _complete(root, f"w{i}")
                        return {"ok": True, "job_id": f"j{i}", "text": "started"}
                return {"ok": False, "job_id": None, "text": "no match"}

            result = run_fanout(
                contract, submit_fn=submit_fn, max_parallel=1, auto_scale=True,
                max_parallel_cap=2, mem_probe_fn=lambda: 5.0,
                poll_interval_sec=0, sleep_fn=lambda s: None, max_iterations=30,
            )
            self.assertEqual(result["max_parallel_cap"], 2)
            self.assertLessEqual(result["max_parallel"], 2)


if __name__ == "__main__":
    unittest.main()
