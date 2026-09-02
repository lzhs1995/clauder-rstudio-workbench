from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from clauder_workbench.soak_monitor import _append_jsonl, _atomic_json, _json_safe


class MonitorJsonSafetyTests(unittest.TestCase):
    def test_circular_mapping_is_replaced_with_marker(self) -> None:
        value: dict[str, object] = {"ok": True}
        value["self"] = value
        safe = _json_safe(value)
        self.assertTrue(safe["ok"])
        self.assertIn("circular-reference", safe["self"])

    def test_checkpoint_and_jsonl_never_fail_on_circular_tool_result(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result: dict[str, object] = {"ok": True}
            result["cycle"] = result
            checkpoint = root / "checkpoint.json"
            events = root / "events.jsonl"
            _atomic_json(checkpoint, {"result": result})
            _append_jsonl(events, {"result": result})
            self.assertIn("circular-reference", checkpoint.read_text(encoding="utf-8"))
            row = json.loads(events.read_text(encoding="utf-8"))
            self.assertIn("circular-reference", row["result"]["cycle"])

    def test_circular_dataclass_is_walked_without_asdict_recursion(self) -> None:
        @dataclass
        class Node:
            child: object = None

        node = Node()
        node.child = node
        safe = _json_safe(node)
        self.assertIn("circular-reference", safe["child"])


if __name__ == "__main__":
    unittest.main()
