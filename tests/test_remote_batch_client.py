"""只运行本机假 xdev：验证中断、重复提交、错误绑定和独立取回，不调用 Windows/Mplus。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


CLIENT = Path(os.environ.get("REMOTE_BATCH_CLIENT",
                            Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts/remote_batch_client.py"))
FAKE = r'''
import hashlib, json, os, pathlib, re, sys, time
root = pathlib.Path(os.environ["FAKE_XDEV_HOME"])
control = json.loads((root / "control.json").read_text())
args = sys.argv[1:]
with (root / "calls.jsonl").open("a") as f:
    f.write(json.dumps(args) + "\n")
rp = root / "remote.json"
remote = json.loads(rp.read_text()) if rp.exists() else {}
def save():
    tmp = rp.with_suffix(".tmp")
    tmp.write_text(json.dumps(remote))
    os.replace(tmp, rp)
def digest(data):
    return hashlib.sha256(data).hexdigest()
def export_package():
    files = {"models/member/model.out": b"synthetic stopped output\n"}
    entries = {name: dict(sha256=digest(data), bytes=len(data)) for name, data in files.items()}
    body = json.dumps(dict(schema="mplus-output-export/1", files=entries), sort_keys=True).encode()
    return files, body
op = args[0]
if op == "health":
    print("XDEV_HEALTH OK" if control.get("health", True) else "XDEV_HEALTH STALE")
    sys.exit(0 if control.get("health", True) else 3)
elif op == "push":
    data = pathlib.Path(args[1]).read_bytes()
    remote.setdefault("payload", {})[args[2]] = digest(data)
    save()
    if control.get("push_fail"):
        print("XDEV_PUSH_FAILED rc=124 job=100", file=sys.stderr)
        sys.exit(124)
    print(f"XDEV_PUSHED {args[2]} sha256={digest(data)} bytes={len(data)} job=100")
elif op == "detach":
    name, path = args[1:]
    if control.get("collision"):
        remote.update(name=name, body="someone else's body")
        save()
        print("XDEV_DETACH_FAILED rc=3 job=101 NAME_EXISTS", file=sys.stderr)
        sys.exit(3)
    if "body" in remote:
        print("DUPLICATE DETACH", file=sys.stderr)
        sys.exit(99)
    remote.update(name=name, body=pathlib.Path(path).read_text(), waits=0)
    save()
    if control.get("slow_detach"):
        time.sleep(control["slow_detach"])
    if control.get("lost_ack"):
        print("XDEV_WAITING id=101", file=sys.stderr)
        sys.exit(124)
    print(f"XDEV_DETACHED {name} dir=C:\\xdev\\jobs\\{name} pid=123 job=101")
elif op == "run":
    script = pathlib.Path(args[1]).read_text()
    check = re.search(r"# XDEV_RETURN_PREFLIGHT_V1 ([a-f0-9]+)", script)
    if check:
        if control.get("return_preflight_deny"):
            print("MPLUS_EXPORT_REQUIRED", file=sys.stderr)
            sys.exit(2)
        token = "0" * 32 if control.get("return_preflight_wrong_token") else check[1]
        kind = "mplus-output-export/1" if control.get("mplus_export") else "generic"
        pin = digest(export_package()[1]) if control.get("mplus_export") else None
        print("XDEV_JSON " + json.dumps(dict(schema="xdev-return-preflight/1", token=token,
              allowed=True, kind=kind, manifest_sha256=pin)))
        sys.exit(0)
    binding = re.search(r"# XDEV_BATCH_OBSERVE_V1 ([a-f0-9]+)", script)[1]
    name = re.search(r"name='([^']+)'", script)[1]
    body = remote.get("body", "")
    matches = bool(body) and ("'" + body.replace("'", "''") + "'") in script
    if control.get("bad_binding"):
        matches = False
    result = dict(schema="xdev-batch-binding-observation/1", binding_id=binding, name=name,
                  exists=bool(body), matches=matches, body_sha256=digest(body.encode()),
                  dir="C:\\xdev\\jobs\\" + name)
    print("XDEV_JSON " + json.dumps(result))
    print("XDEV_RC job=102 rc=0", file=sys.stderr)
elif op == "wait":
    remote["waits"] += 1
    save()
    if remote["waits"] <= control.get("running_waits", 1):
        print(f"XDEV_STILL_RUNNING {args[1]} (later: xdev wait {args[1]})")
        sys.exit(124)
    rc = control.get("remote_rc", 0)
    print(f"XDEV_STATE {args[1]} DONE rc={rc} finished=2026-11-01T00:00:00Z")
    sys.exit(rc & 255)
elif op == "pull-dir":
    target = pathlib.Path(args[2])
    target.mkdir(parents=True, exist_ok=True)
    if control.get("mplus_export"):
        files, manifest_body = export_package()
        files["EXPORT_MANIFEST.json"] = manifest_body
        change = control.get("export_change_after_preflight")
        if change == "extra":
            files["models/member/data.dat"] = b"synthetic late input copy\n"
        elif change == "missing":
            del files["models/member/model.out"]
        elif change == "changed":
            files["models/member/model.out"] = b"changed stopped output\n"
    else:
        files = {"RESULT.json": b'{"starts": 1, "synthetic": true}\n'}
    for name, data in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        h = "0" * 64 if control.get("bad_hash") else digest(data)
        print(f"  {h}  {name}")
    print(f"XDEV_PULLED_DIR {target} files={len(files)} remote_files={len(files)}")
else:
    raise SystemExit("unexpected operation")
'''


@unittest.skipUnless(os.name == "posix", "This suite exercises the Mac/POSIX xdev client.")
class ClientContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.client = CLIENT
        self.fake = self.root / "fake-xdev"
        self.fake.write_text("#!" + sys.executable + "\n" + FAKE)
        self.fake.chmod(0o700)
        self.control = {}
        self.write_control()
        self.env = {**os.environ, "FAKE_XDEV_HOME": str(self.root)}
        self.launcher = self.root / "含 空格.ps1"
        self.launcher.write_text("'synthetic launcher'\nexit 0\n", encoding="utf-8")
        self.payload = self.root / "input.txt"
        self.payload.write_text("synthetic only", encoding="utf-8")
        self.state = self.root / "state"
        self.output = self.root / "returned"
        self.plan = self.root / "plan.json"
        self.plan.write_text(json.dumps({
            "schema": "xdev-batch-plan/1", "name": "test-batch",
            "launcher": str(self.launcher), "return_dir": r"%LOCALAPPDATA%\xdev\work\test\results",
            "output_dir": str(self.output),
            "payload": [{"local": str(self.payload), "remote": r"%LOCALAPPDATA%\xdev\work\test\input.txt"}]
        }, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write_control(self):
        (self.root / "control.json").write_text(json.dumps(self.control))

    def command(self, *args, timeout=5):
        return [sys.executable, "-B", str(self.client), "--state", str(self.state),
                "--xdev", str(self.fake), "--client-timeout", str(timeout), *args]

    def run_client(self, *args, expected=0, timeout=5):
        result = subprocess.run(self.command(*args, timeout=timeout), env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def read_state(self):
        return json.loads((self.state / "TASK.json").read_text())

    def calls(self):
        path = self.root / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def submit(self, expected=0, **kwargs):
        return self.run_client("submit", "--plan", str(self.plan), expected=expected, **kwargs)

    def finish(self, rc=0):
        self.run_client("wait", "--max", "1", expected=124)
        self.run_client("wait", "--max", "1", expected=rc)

    def test_one_submit_wait_resume_collect_and_timing(self):
        self.submit()
        self.finish()
        self.run_client("collect")
        self.run_client("verify-collection")
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)
        state = self.read_state()
        self.assertEqual(state["status"], "COLLECTED")
        self.assertEqual(state["numerical_validation"], "REQUIRED_SEPARATELY")
        for path in state["phases"]:
            result = json.loads((Path(path) / "RESULT.json").read_text())
            self.assertGreaterEqual(result["elapsed_seconds"], 0)
            self.assertEqual(result["stdout_sha256"], hashlib.sha256((Path(path) / "stdout.txt").read_bytes()).hexdigest())

    def test_pinned_mplus_export_collects_exact_declared_files(self):
        self.control["mplus_export"] = True
        self.write_control()
        self.submit()
        self.finish()
        self.run_client("collect")
        self.run_client("verify-collection")
        self.assertEqual(self.read_state()["collection_state"], "FILES_VERIFIED")
        self.assertEqual(set(json.loads((self.state / "COLLECTION.json").read_text())["files"]),
                         {"EXPORT_MANIFEST.json", "models/member/model.out"})

    def assert_export_change_refused(self, change):
        # 预检后才改变返回目录；伪 xdev 对实际搬运的所有字节仍给出正确 SHA。
        self.control.update(mplus_export=True, export_change_after_preflight=change)
        self.write_control()
        self.submit()
        self.finish()
        self.run_client("collect", expected=2)
        state = self.read_state()
        self.assertEqual(state["status"], "FINISHED")
        self.assertEqual(state["collection_state"], "EXPORT_CHANGED_AFTER_PREFLIGHT")
        detail = state["last_export_rejection"]
        self.assertEqual(detail["directory"], str(self.output.resolve()))
        self.assertEqual(detail["extra_files"], ["models/member/data.dat"] if change == "extra" else [])
        self.assertEqual(detail["missing_files"], ["models/member/model.out"] if change == "missing" else [])
        self.assertEqual(detail["changed_files"], ["models/member/model.out"] if change == "changed" else [])
        self.assertEqual(detail["actual_manifest_sha256"], detail["expected_manifest_sha256"])
        self.assertTrue(detail["at"] and detail["reason"])
        self.assertFalse((self.state / "COLLECTION.json").exists())
        self.assertTrue((self.output / "EXPORT_MANIFEST.json").exists())
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)
        self.assertEqual(sum(row[0] == "pull-dir" for row in self.calls()), 1)

    def test_post_preflight_added_input_is_not_accepted_as_export(self):
        self.assert_export_change_refused("extra")
        self.assertTrue((self.output / "models/member/data.dat").exists())

    def test_post_preflight_missing_output_is_not_accepted_as_export(self):
        self.assert_export_change_refused("missing")

    def test_post_preflight_changed_output_is_not_accepted_as_export(self):
        self.assert_export_change_refused("changed")

    def test_duplicate_submit_never_calls_detach_twice(self):
        self.submit()
        calls = self.calls()
        self.submit(expected=2)
        self.assertEqual(calls, self.calls())

    def test_unknown_detach_reconciles_exact_body_without_resubmit(self):
        self.control["lost_ack"] = True
        self.write_control()
        self.submit(expected=124)
        self.assertEqual(self.read_state()["submission"], "UNKNOWN")
        self.run_client("wait", expected=2)
        self.run_client("reconcile")
        self.finish()
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)
        self.assertEqual(self.read_state()["detachment_attempts"], 1)

    def test_local_timeout_keeps_remote_task_and_recovers(self):
        self.control["slow_detach"] = 3
        self.write_control()
        # 故障只注入 detach，避免繁忙机器上 0.25 秒全局预算先在 health 阶段到期。
        harness = self.root / "timeout_detach_only.py"
        harness.write_text(
            "import importlib.util\n"
            f"spec=importlib.util.spec_from_file_location('tested_client',{str(CLIENT)!r})\n"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
            "original=m.Client.call\n"
            "def call(self,phase,arguments):\n"
            " old=self.client_timeout\n"
            " if phase=='detach':self.client_timeout=1.0\n"
            " try:return original(self,phase,arguments)\n"
            " finally:self.client_timeout=old\n"
            "m.Client.call=call\n"
            "raise SystemExit(m.main())\n"
        )
        self.client = harness
        self.submit(expected=124)
        self.run_client("reconcile")
        self.finish()
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)
        phase = Path(self.read_state()["phases"][2]) / "RESULT.json"
        self.assertTrue(json.loads(phase.read_text())["local_wait_timed_out"])

    def test_name_collision_cannot_adopt_other_job(self):
        self.control["collision"] = True
        self.write_control()
        self.submit(expected=3)
        self.run_client("reconcile", expected=2)
        self.run_client("wait", expected=2)
        self.assertEqual(self.read_state()["submission"], "REJECTED")

    def test_original_launcher_can_change_but_frozen_body_is_reused(self):
        self.control["lost_ack"] = True
        self.write_control()
        self.submit(expected=124)
        self.launcher.write_text("'new development version'\nexit 1\n")
        self.payload.write_text("new development payload")
        self.run_client("reconcile")
        self.finish()
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)

    def test_tampered_frozen_launcher_refuses_recovery(self):
        self.control["lost_ack"] = True
        self.write_control()
        self.submit(expected=124)
        Path(self.read_state()["launcher_snapshot"]).write_text("tampered")
        calls = self.calls()
        self.run_client("reconcile", expected=2)
        self.assertEqual(calls, self.calls())

    def test_tampered_return_hash_refuses_collection(self):
        self.control["bad_hash"] = True
        self.write_control()
        self.submit()
        self.finish()
        self.run_client("collect", expected=2)
        self.assertEqual(self.read_state()["collection_state"], "HASH_OR_FILESET_MISMATCH")
        self.assertNotEqual(self.read_state()["status"], "COLLECTED")

    def test_preexisting_output_is_preserved(self):
        self.submit()
        self.finish()
        self.output.mkdir()
        (self.output / "user.txt").write_text("keep")
        self.run_client("collect", expected=2)
        self.assertEqual((self.output / "user.txt").read_text(), "keep")
        self.assertFalse(any(row[0] == "pull-dir" for row in self.calls()))

    def test_mplus_work_overlap_rejected_before_any_submission(self):
        plan = json.loads(self.plan.read_text())
        plan["mplus_work_dir"] = r"%LOCALAPPDATA%\xdev\work\test\run"
        for returned in (r"%LOCALAPPDATA%/xdev/work/test/RUN", r"%LOCALAPPDATA%\xdev\work\test",
                         r"%LOCALAPPDATA%\xdev\work\test\run\models"):
            plan["return_dir"] = returned
            self.plan.write_text(json.dumps(plan))
            self.submit(expected=2)
            self.assertFalse(self.state.exists())
            self.assertEqual(self.calls(), [])

    def test_remote_return_refusal_prevents_data_transfer(self):
        self.control["return_preflight_deny"] = True
        self.write_control()
        self.submit()
        self.finish()
        self.run_client("collect", expected=2)
        self.assertEqual(self.read_state()["collection_state"], "RETURN_PREFLIGHT_REFUSED")
        self.assertFalse(any(row[0] == "pull-dir" for row in self.calls()))
        self.assertFalse(self.output.exists())
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)

    def test_unrelated_return_preflight_receipt_cannot_authorize_pull(self):
        self.control["return_preflight_wrong_token"] = True
        self.write_control()
        self.submit()
        self.finish()
        self.run_client("collect", expected=2)
        self.assertFalse(any(row[0] == "pull-dir" for row in self.calls()))
        self.assertFalse(self.output.exists())

    def test_failed_remote_job_preserves_actual_exit_and_collects_diagnostics(self):
        self.control["remote_rc"] = 9
        self.write_control()
        self.submit()
        self.finish(rc=9)
        self.run_client("collect", expected=9)
        self.assertEqual(self.read_state()["remote_exit_code"], 9)
        self.assertEqual(self.read_state()["status"], "COLLECTED")

    def test_negative_remote_exit_code_not_lost_in_shell_encoding(self):
        self.control["remote_rc"] = -9
        self.write_control()
        self.submit()
        self.finish(rc=1)
        self.assertEqual(self.read_state()["remote_exit_code"], -9)

    def test_collected_file_change_is_detected_without_new_pull(self):
        self.submit()
        self.finish()
        self.run_client("collect")
        (self.output / "RESULT.json").write_text("changed")
        calls = self.calls()
        self.run_client("collect", expected=2)
        self.assertEqual(calls, self.calls())

    def test_aliased_windows_payload_paths_rejected_before_side_effects(self):
        plan = json.loads(self.plan.read_text())
        plan["payload"].append({"local": str(self.payload), "remote": r"%LOCALAPPDATA%/xdev/work/test/INPUT.txt"})
        self.plan.write_text(json.dumps(plan))
        self.submit(expected=2)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.calls(), [])

    def test_same_state_lock_rejects_second_client(self):
        self.control["slow_detach"] = 0.8
        self.write_control()
        process = subprocess.Popen(self.command("submit", "--plan", str(self.plan)),
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            end = time.monotonic() + 4
            while not (self.state / "TASK.json").exists() and time.monotonic() < end:
                time.sleep(0.02)
            self.run_client("status")  # 等待/传输期间仍能只读状态。
            self.run_client("wait", expected=2)
            out, err = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, out + err)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)

    def test_timing_does_not_invent_engine_or_queue_durations(self):
        self.submit()
        result = self.run_client("timings")
        timing = json.loads(result.stdout)
        self.assertIsNone(timing["windows_engine_seconds"])
        self.assertIsNone(timing["windows_queue_seconds"])
        self.assertEqual(timing["local_call_counts"]["detach"], 1)
        self.assertGreater(timing["local_call_seconds"]["push"], 0)

    def test_phase_directory_left_before_journal_append_does_not_block_observation(self):
        self.submit()
        count = len(self.read_state()["phases"])
        leftover = self.state / f"phase-{count:03d}-reconcile"
        leftover.mkdir()
        (leftover / "INTENT.json").write_text('{"unfinished_old_directory": true}')
        self.run_client("reconcile")
        self.assertTrue((leftover / "INTENT.json").exists())
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)

    def test_exit_after_observation_script_is_frozen_can_resume_without_resubmit(self):
        self.control["lost_ack"] = True
        self.write_control()
        self.submit(expected=124)
        # 模拟查询脚本已落盘、阶段意图尚未创建时退出；残留证据必须原样保留。
        harness = self.root / "exit_after_observation_script.py"
        harness.write_text(
            "import importlib.util, os\n"
            f"spec=importlib.util.spec_from_file_location('tested_client',{str(CLIENT)!r})\n"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
            "original=m.exclusive_bytes\n"
            "def freeze(path,body):\n"
            " original(path,body)\n"
            " if path.name.startswith('binding-observe-'):os._exit(73)\n"
            "m.exclusive_bytes=freeze\n"
            "raise SystemExit(m.main())\n"
        )
        self.client = harness
        self.run_client("reconcile", expected=73)
        remnants = {path: path.read_bytes() for path in self.state.glob("binding-observe-*.ps1")}
        self.assertEqual(len(remnants), 1)
        self.client = CLIENT
        self.run_client("reconcile")
        self.assertTrue(all(path.read_bytes() == body for path, body in remnants.items()))
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)
        self.assertEqual(sum(row[0] == "run" for row in self.calls()), 1)

    def test_failed_health_can_resume_same_frozen_plan_without_duplicate_submit(self):
        self.control["health"] = False
        self.write_control()
        self.submit(expected=3)
        self.assertFalse((self.root / "remote.json").exists())
        self.control["health"] = True
        self.write_control()
        self.run_client("retry-preflight")
        self.finish()
        self.assertEqual(sum(row[0] == "health" for row in self.calls()), 2)
        self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)

    def test_preflight_retry_refuses_after_any_detach_attempt(self):
        self.control["lost_ack"] = True
        self.write_control()
        self.submit(expected=124)
        calls = self.calls()
        self.run_client("retry-preflight", expected=2)
        self.assertEqual(calls, self.calls())

    def test_preflight_retry_refuses_unknown_push(self):
        self.control["push_fail"] = True
        self.write_control()
        self.submit(expected=124)
        calls = self.calls()
        self.run_client("retry-preflight", expected=2)
        self.assertEqual(calls, self.calls())
        self.assertEqual(self.read_state()["detachment_attempts"], 0)

    def test_client_process_exit_after_detach_intent_recovers_original(self):
        # 等确实已在远端提交、尚未写本地确认的信号，再结束本机客户端。
        # 繁忙主机上的固定四秒等待可能仍停在 health/push，不能冒充 detach 故障。
        ready = self.root / "detach-confirmation-ready"
        harness = self.root / "hold_before_local_confirmation.py"
        harness.write_text(
            "import importlib.util,time\nfrom pathlib import Path\n"
            f"spec=importlib.util.spec_from_file_location('tested_client',{str(CLIENT)!r})\n"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
            "original=m.Client.call\n"
            "def call(self,phase,arguments):\n"
            " result=original(self,phase,arguments)\n"
            " if phase=='detach' and result[0]==0:\n"
            f"  Path({str(ready)!r}).touch()\n"
            "  time.sleep(30)\n"
            " return result\n"
            "m.Client.call=call\nraise SystemExit(m.main())\n"
        )
        self.client = harness
        process = subprocess.Popen(self.command("submit", "--plan", str(self.plan)),
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            end = time.monotonic() + 20
            while not ready.exists() and process.poll() is None and time.monotonic() < end:
                time.sleep(0.02)
            self.assertTrue(ready.exists(), "Fault injection never reached the intended detach boundary")
            self.assertIn("body", json.loads((self.root / "remote.json").read_text()))
            self.assertEqual(self.read_state()["submission"], "INTENT")
            process.kill()
            process.communicate(timeout=2)
            self.client = CLIENT
            self.run_client("reconcile")
            self.finish()
            self.assertEqual(sum(row[0] == "detach" for row in self.calls()), 1)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()
