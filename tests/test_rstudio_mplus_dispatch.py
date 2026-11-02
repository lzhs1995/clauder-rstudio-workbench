"""MplusAutomation 派发边界：不启动真实 R 或 Mplus。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts/rstudio_mplus_dispatch.py"
spec = importlib.util.spec_from_file_location("dispatch_under_test", SOURCE)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.channel = self.root / "channel"
        self.channel.mkdir()
        self.owner = {"r_pid": 123, "r_created": 456.0}
        d.write_new(self.channel / "R_OWNER.json", self.owner)
        self.input = self.root / "source.inp"
        self.input.write_text("TITLE: synthetic protocol fixture;\nDATA: FILE=data.dat;\n")
        self.contract = self.root / "contract.json"
        d.write_new(self.contract, {"schema": "pp-scientific-single-pilot/1", "member": "fixture_MI01",
                                   "new_engine_calls_maximum": 1, "cap_seconds": 0.2,
                                   "inputs": {"model.inp": {"path": str(self.input), "sha256": d.digest(self.input)}}})
        self.work = self.root / "work"
        self.output = self.root / "output"
        self.guard = patch.object(d, "ancestry_to_owner", return_value=[])
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def prepare(self):
        return d.prepare_request(self.channel, self.contract, self.work, self.output, self.root)

    def test_slow_writer_never_exposes_partial_request(self):
        target = self.root / "concurrent.json"
        entered, finish = threading.Event(), threading.Event()
        original_dump = json.dump
        errors = []

        def slow_dump(value, stream, **kwargs):
            stream.write(" ")
            stream.flush()
            entered.set()
            if not finish.wait(5):
                raise TimeoutError("test reader did not finish")
            original_dump(value, stream, **kwargs)

        def publish():
            try:
                d.write_new(target, {"complete": True})
            except Exception as error:
                errors.append(error)

        with patch.object(d.json, "dump", side_effect=slow_dump):
            writer = threading.Thread(target=publish)
            writer.start()
            try:
                self.assertTrue(entered.wait(5))
                self.assertFalse(target.exists())
            finally:
                finish.set()
                writer.join(5)
        self.assertFalse(writer.is_alive())
        self.assertFalse(errors)
        self.assertEqual(d.read(target), {"complete": True})

    def test_publication_never_replaces_an_existing_receipt(self):
        target = self.root / "original.json"
        d.write_new(target, {"original": 1})
        before = target.read_bytes()
        with self.assertRaises(FileExistsError):
            d.write_new(target, {"replacement": 2})
        self.assertEqual(target.read_bytes(), before)

    def complete_fixture(self, state="EXITED"):
        request_path = self.prepare()
        request = d.read(request_path)
        folder = request_path.parent
        d.write_new(folder / "R_MPLUSAUTOMATION_CALL.json", {
            "function": "MplusAutomation::runModels", "r_pid": 123,
            "request_sha256": d.digest(request_path)})
        d.write_new(folder / "BRIDGE_IDENTITY.json", {
            "request_sha256": d.digest(request_path),
            "R_call_sha256": d.digest(folder / "R_MPLUSAUTOMATION_CALL.json")})
        d.write_new(folder / "R_WRAPPER_RETURN.json", {
            "status": "WRAPPER_RETURNED", "request_sha256": d.digest(request_path), "r_pid": 123})
        exported = Path(request["guard_export"])
        exported.mkdir()
        (exported / "model.inp").write_bytes(self.input.read_bytes())
        (exported / "model.out").write_text("protocol fixture; not a model fit\n")
        d.write_new(exported / "ENGINE_RECEIPT.json", {
            "engine_exit_confirmed": True, "actual_engine_calls": 1, "state": state,
            "elapsed_seconds": 0.2, "cap_seconds": 0.2, "exit_code": 0 if state == "EXITED" else 124})
        d.write_new(exported / "EXPORT_MANIFEST.json", {
            "files": d.files(exported), "individual_inputs_exported": False})
        return request_path, exported

    def test_prepare_preserves_exact_input_without_data_copy(self):
        request = d.read(self.prepare())
        self.assertEqual(Path(request["target"]).read_bytes(), self.input.read_bytes())
        self.assertFalse((Path(request["target"]).parent / "data.dat").exists())
        self.assertEqual(request["cap_seconds"], 0.2)

    def test_repeat_request_does_not_reclaim_or_overwrite(self):
        first = self.prepare()
        original = first.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "原领取"):
            self.prepare()
        self.assertEqual(first.read_bytes(), original)

    def test_changed_input_refused_before_claim(self):
        self.input.write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "输入哈希"):
            self.prepare()
        self.assertFalse(self.work.exists())

    def test_changed_owner_refused(self):
        request_path = self.prepare()
        (self.channel / "R_OWNER.json").write_text('{}')
        with self.assertRaisesRegex(RuntimeError, "owner_file"):
            d.verify_request(request_path)

    def test_cmd_expansion_characters_refused(self):
        with self.assertRaises(ValueError):
            d.command_text(self.root / "%USERPROFILE%/python.exe", SOURCE, self.contract)

    def test_unsafe_member_refused(self):
        value = d.read(self.contract)
        value["member"] = "../foreign"
        self.contract.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_missing_R_call_cannot_invoke_guard(self):
        request_path = self.prepare()
        with self.assertRaises(FileNotFoundError):
            d.invoke(request_path, d.read(request_path)["target"])
        self.assertFalse((request_path.parent / "BRIDGE_CLAIM").exists())

    def test_success_keeps_original_manifest_and_exact_final_set(self):
        request_path, exported = self.complete_fixture()
        original = (exported / "EXPORT_MANIFEST.json").read_bytes()
        self.assertEqual(d.finish_request(request_path), 0)
        self.assertEqual((self.output / "GUARD_EXPORT_MANIFEST.json").read_bytes(), original)
        manifest = d.read(self.output / "EXPORT_MANIFEST.json")
        actual = d.files(self.output)
        del actual["EXPORT_MANIFEST.json"]
        self.assertEqual(actual, manifest["files"])

    def test_timeout_keeps_consumed_call_and_cap(self):
        request_path, _ = self.complete_fixture("TIMEOUT")
        self.assertEqual(d.finish_request(request_path), 2)
        receipt = d.read(self.output / "ENGINE_RECEIPT.json")
        self.assertEqual((receipt["state"], receipt["actual_engine_calls"], receipt["cap_seconds"]),
                         ("TIMEOUT", 1, 0.2))

    def test_unlisted_export_rejected_before_copy(self):
        request_path, exported = self.complete_fixture()
        (exported / "data.dat").write_text("fixture only")
        with self.assertRaisesRegex(RuntimeError, "导出集合"):
            d.finish_request(request_path)
        self.assertFalse(self.output.exists())

    def test_replaced_R_call_evidence_refused(self):
        request_path, _ = self.complete_fixture()
        (request_path.parent / "R_MPLUSAUTOMATION_CALL.json").write_text('{}')
        with self.assertRaisesRegex(RuntimeError, "证据改变"):
            d.finish_request(request_path)

    def test_unknown_exit_refused(self):
        request_path, exported = self.complete_fixture()
        receipt = d.read(exported / "ENGINE_RECEIPT.json")
        receipt["engine_exit_confirmed"] = False
        (exported / "ENGINE_RECEIPT.json").write_text(json.dumps(receipt))
        manifest = d.read(exported / "EXPORT_MANIFEST.json")
        manifest["files"]["ENGINE_RECEIPT.json"] = {
            "bytes": (exported / "ENGINE_RECEIPT.json").stat().st_size,
            "sha256": d.digest(exported / "ENGINE_RECEIPT.json")}
        (exported / "EXPORT_MANIFEST.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RuntimeError, "退出或调用数未知"):
            d.finish_request(request_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
