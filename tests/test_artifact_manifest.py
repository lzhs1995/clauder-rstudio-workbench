"""可移植结果包的自引用、字节改动和文件集变化必须被真实拒绝。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts/artifact_manifest.py"
SPEC = importlib.util.spec_from_file_location("artifact_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ArtifactManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "结果.txt").write_text("可复现结果\n", encoding="utf-8")

    def make(self):
        return MODULE.build(self.root)

    def edit(self, transform):
        target = self.root / "MANIFEST.json"
        data = json.loads(target.read_text())
        transform(data)
        target.write_text(json.dumps(data), encoding="utf-8")

    def test_roundtrip_and_external_pin(self):
        built = self.make()
        self.assertEqual(MODULE.verify(self.root, expected_sha256=built["manifest_sha256"])["files"], 1)
        with self.assertRaises(ValueError):
            MODULE.verify(self.root, expected_sha256="0" * 64)
        with self.assertRaises(FileExistsError):
            self.make()

    def test_tampered_payload(self):
        self.make()
        (self.root / "结果.txt").write_text("不同结果\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            MODULE.verify(self.root)

    def test_missing_and_extra_files(self):
        self.make()
        extra = self.root / "unlisted.txt"
        extra.write_text("extra")
        with self.assertRaises(ValueError):
            MODULE.verify(self.root)
        extra.unlink()
        (self.root / "结果.txt").unlink()
        with self.assertRaises(ValueError):
            MODULE.verify(self.root)

    def test_original_self_reference_failure(self):
        self.make()
        self.edit(lambda data: data["files"].append({"path": "MANIFEST.json", "bytes": 1, "sha256": "0" * 64}))
        with self.assertRaisesRegex(ValueError, "cannot hash itself"):
            MODULE.verify(self.root)

    def test_duplicate_and_parent_path(self):
        self.make()
        self.edit(lambda data: data["files"].append(dict(data["files"][0])))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            MODULE.verify(self.root)
        self.edit(lambda data: data["files"].__setitem__(0, {"path": "../escape", "bytes": 0, "sha256": "0" * 64}))
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            MODULE.verify(self.root)

    def test_symlink_is_not_payload(self):
        link = self.root / "alias"
        try:
            link.symlink_to("结果.txt")
        except OSError as error:
            self.skipTest(f"Symlinks unavailable: {error}")
        with self.assertRaises(ValueError):
            self.make()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipe")
    def test_fifo_without_writer_is_rejected_without_blocking(self):
        for operation in ("build", "verify"):
            with self.subTest(operation=operation):
                root = self.root / operation
                root.mkdir()
                (root / "payload.txt").write_text("synthetic payload")
                if operation == "verify":
                    MODULE.build(root)
                os.mkfifo(root / "stream")
                result = subprocess.run([sys.executable, str(SCRIPT), operation, str(root)],
                                        capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("regular file", json.loads(result.stdout)["error"])

    def test_stable_windows_stat_and_fstat_ctime_difference(self):
        original = MODULE.os.fstat

        def windows_handle_stat(fd):
            value = original(fd)
            fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")
            data = {name: getattr(value, name) for name in fields}
            data["st_ctime_ns"] += 11_038_500
            return SimpleNamespace(**data)

        with patch.object(MODULE.os, "fstat", side_effect=windows_handle_stat):
            built = self.make()
            self.assertEqual(MODULE.verify(self.root, expected_sha256=built["manifest_sha256"])["files"], 1)

    def test_real_file_mutation_during_hash_is_rejected(self):
        original = MODULE.os.fstat
        calls = 0

        def mutate_once(fd):
            nonlocal calls
            value = original(fd)
            calls += 1
            if calls == 1:
                with (self.root / "结果.txt").open("ab") as stream:
                    stream.write(b"changed")
            return value

        with patch.object(MODULE.os, "fstat", side_effect=mutate_once):
            with self.assertRaisesRegex(ValueError, "changed during hashing"):
                MODULE.file_digest(self.root / "结果.txt")


if __name__ == "__main__":
    unittest.main()
