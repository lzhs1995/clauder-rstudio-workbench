from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "mplusautomation-guide" / "scripts" / "mplus_queue.py"
SPEC = importlib.util.spec_from_file_location("mplus_queue_init_policy_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class HistoricalPolicyInitTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)

    def _config(self, root: Path, policy: dict, **settings) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "config.json").write_text(
            json.dumps({"historical_success_policy": policy, **settings}), encoding="utf-8"
        )

    def _manifest(self, root: Path, content: str | None = None) -> dict:
        root.mkdir(parents=True, exist_ok=True)
        manifest = root / "allowed.json"
        if content is None:
            content = json.dumps({"allowed_output_names": ["Synthetic.OUT"]})
        manifest.write_text(content, encoding="utf-8")
        return {"manifest": str(manifest), "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}

    def _bad_policy(self, root: Path, case: str) -> tuple[dict, type[Exception]]:
        if case == "missing_manifest":
            return {"manifest": str(root / "missing.json"), "sha256": "0" * 64}, FileNotFoundError
        if case == "wrong_digest":
            return {**self._manifest(root), "sha256": "0" * 64}, ValueError
        if case == "malformed_json":
            return self._manifest(root, '{"allowed_output_names":'), json.JSONDecodeError
        if case == "missing_names":
            return self._manifest(root, "{}"), KeyError
        if case == "invalid_names":
            return self._manifest(root, json.dumps({"allowed_output_names": ["nested/model.out"]})), ValueError
        raise AssertionError(case)

    def _settings(self, root: Path) -> dict:
        with contextlib.closing(sqlite3.connect(root / "queue.sqlite")) as database:
            return {key: json.loads(value) for key, value in database.execute("SELECT key,value FROM settings")}

    def _queue(self, root: Path):
        queue = MODULE.Queue(root)
        self.addCleanup(queue.db.close)
        return queue

    def _cli(self, root: Path, action: str = "init") -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), action, "--root", str(root)],
            capture_output=True, text=True, timeout=30,
        )

    def test_policy_validation_failures_leave_settings_empty(self) -> None:
        # 每类策略校验失败都不得把默认值或已声明的并发值留在数据库。
        for case in ("missing_manifest", "wrong_digest", "malformed_json", "missing_names", "invalid_names"):
            for declared in (False, True):
                with self.subTest(case=case, declared=declared):
                    root = self.tmp / f"{case}-{declared}"
                    policy, error = self._bad_policy(root, case)
                    declaration = {"parallel_cap": 2, "initial_parallel_limit": 2} if declared else {}
                    self._config(root, policy, **declaration)
                    with self.assertRaises(error):
                        MODULE.Queue(root)
                    self.assertEqual(self._settings(root), {})

    def test_corrected_policy_retry_applies_initial_declaration(self) -> None:
        # 先用默认并发失败，修正清单后必须仍按首次初始化接受新的声明。
        for case in ("missing_manifest", "wrong_digest", "malformed_json", "invalid_names"):
            with self.subTest(case=case):
                root = self.tmp / case
                policy, error = self._bad_policy(root, case)
                self._config(root, policy)
                with self.assertRaises(error):
                    MODULE.Queue(root)
                self._config(root, self._manifest(root), parallel_cap=2, initial_parallel_limit=2)
                queue = self._queue(root)
                self.assertEqual((queue.get("cap"), queue.get("limit")), (2, 2))
                self.assertEqual(queue.success_names, {"synthetic.out"})

    def test_cli_policy_failure_stays_empty_and_recovers(self) -> None:
        for case in ("missing_manifest", "wrong_digest"):
            with self.subTest(case=case):
                root = self.tmp / case
                policy, _ = self._bad_policy(root, case)
                self._config(root, policy)
                for action in ("init", "enable"):
                    failed = self._cli(root, action)
                    self.assertNotEqual(failed.returncode, 0, failed.stdout)
                    self.assertEqual(self._settings(root), {})
                self._config(root, self._manifest(root), parallel_cap=2, initial_parallel_limit=2)
                recovered = self._cli(root)
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                state = json.loads(recovered.stdout)
                self.assertEqual((state["cap"], state["limit"]), (2, 2))
                self.assertEqual((self._settings(root)["cap"], self._settings(root)["limit"]), (2, 2))

    def test_existing_queue_keeps_settings_and_revalidates_policy(self) -> None:
        for with_event in (False, True):
            with self.subTest(with_event=with_event):
                root = self.tmp / str(with_event)
                self._config(root, self._manifest(root))
                queue = self._queue(root)
                queue.set("enabled", True)
                if with_event:
                    queue.event("synthetic", {})
                before = self._settings(root)
                invalid, _ = self._bad_policy(root, "wrong_digest")
                self._config(root, invalid, parallel_cap=2, initial_parallel_limit=2)
                with self.assertRaisesRegex(ValueError, "Historical-success manifest changed"):
                    MODULE.Queue(root)
                self.assertEqual(self._settings(root), before)
                self._config(root, self._manifest(root), parallel_cap=2, initial_parallel_limit=2)
                reopened = self._queue(root)
                self.assertEqual((reopened.get("cap"), reopened.get("limit"), reopened.get("enabled")), (3, 1, True))
                self.assertEqual(reopened.success_names, {"synthetic.out"})

    def test_apim_cap_and_calibration_requirements_are_preserved(self) -> None:
        cases = (
            {"parallel_cap": 3, "initial_parallel_limit": 1},
            {"parallel_cap": 2, "initial_parallel_limit": 2, "calibrated": False},
        )
        for index, declaration in enumerate(cases):
            with self.subTest(declaration=declaration):
                root = self.tmp / str(index)
                self._config(root, self._manifest(root), apim_v2=True, **declaration)
                with self.assertRaises(ValueError):
                    MODULE.Queue(root)
                self.assertEqual(self._settings(root), {})
                self._config(root, self._manifest(root), apim_v2=True,
                             parallel_cap=2, initial_parallel_limit=2, calibrated=True)
                queue = self._queue(root)
                self.assertEqual((queue.get("cap"), queue.get("limit")), (2, 2))


if __name__ == "__main__":
    unittest.main()
