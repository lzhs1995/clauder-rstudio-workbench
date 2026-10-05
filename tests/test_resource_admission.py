from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).parents[1] / "skills" / "mplusautomation-guide" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("resource_admission_test", SCRIPT_DIR / "resource_admission.py")
MODULE = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(MODULE)


def test_pages_input_without_output_paging_is_not_a_hold() -> None:
    assert MODULE.paging_io_pressure({"pages_input_sec": 900.0, "pages_output_sec": 0.0,
                                      "disk_read_latency_sec": 0.08}) is False


def test_output_paging_and_disk_latency_hold_together() -> None:
    assert MODULE.paging_io_pressure({"pages_input_sec": 60.0, "pages_output_sec": 1200.0,
                                      "disk_read_latency_sec": 0.06}) is True
