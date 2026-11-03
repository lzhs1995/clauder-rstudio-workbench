"""真实 Python 子进程的批次恢复测试；所有数据与输出合成，Mplus 调用为零。"""
from contextlib import redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import psutil

SCRIPTS = Path(os.environ.get("DURABLE_MPLUS_SCRIPTS",
                             Path(__file__).resolve().parents[1] / "skills/mplusautomation-guide/scripts"))
sys.path.insert(0, str(SCRIPTS))
import durable_mplus_worker as worker
from verify_saved_batch import verify_batch


OUT = b"Mplus VERSION 9 (SYNTHETIC TEST)\nTHE MODEL ESTIMATION TERMINATED NORMALLY\nH0 Value -5.25\n"
ESTIMATES = b"1.25 0.25\n"
TECH3 = b"0.0625\n"
FAKE = r'''from pathlib import Path
import json,os,sys,time
root=Path.cwd()
settings=json.loads((root/'fixture.json').read_text())
with (root/'fake_starts.log').open('a') as stream:
    stream.write(str(os.getpid())+'\n')
(root/'FAKE_STARTED').write_text(str(os.getpid()))
def wait_release():
    deadline=time.monotonic()+45
    while not (root/'FAKE_RELEASE').exists():
        if time.monotonic()>deadline:raise SystemExit(23)
        time.sleep(.02)
if settings.get('wait_before'):wait_release()
text='Mplus VERSION 9 (SYNTHETIC TEST)\nTHE MODEL ESTIMATION TERMINATED NORMALLY\nH0 Value -5.25\n'
if settings.get('invalid_output'):text='*** ERROR synthetic failure\n'
(root/'model.out').write_bytes(text.encode())
(root/'estimates.dat').write_bytes(b'1.25 0.25\n')
(root/'tech3.dat').write_bytes(b'0.0625\n')
(root/'FAKE_OUTPUTS_READY').write_text('ready')
if settings.get('wait_after'):wait_release()
raise SystemExit(settings.get('exit_code',0))
'''


def dump(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


class DurableMplusWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="durable-mplus-synthetic-")
        self.root = Path(self.temporary.name).resolve()
        self.source, self.work = self.root / "source", self.root / "work"
        self.plan_path = self.root / "plan.json"
        self.fake = self.root / "synthetic_engine.py"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.members = ["SYNTHETIC_MI01_A", "SYNTHETIC_MI02_A"]
        self.children, self.streams = [], []
        self.configure()

    def configure(self, *, members=2, cap=12, max_calls=None, max_seconds=None, settings=None, prior_calls=0, prior_seconds=0):
        self.members = self.members[:members]
        contract = {"primary_sequence": self.members, "max_mplus_calls": len(self.members),
                    "total_engine_seconds": cap * len(self.members), "per_model_seconds": cap,
                    "minimum_available_gib": 1.2, "minimum_commit_available_gib": 2,
                    "max_cpu_percent": 85, "resource_wait_seconds": 30}
        dump(self.source / "contracts/RUN_CONTRACT.json", contract)
        dump(self.source / "TEST_FIXTURE.json", {"synthetic": True})
        for index, member in enumerate(self.members):
            src = self.source / "models" / member
            src.mkdir(parents=True, exist_ok=True)
            (src / "model.inp").write_bytes(b"DATA: FILE=data.dat;\nMODEL: y ON x;\n")
            (src / "data.dat").write_bytes(b"1 2\n3 4\n")
            dump(src / "fixture.json", (settings or {}) if index == 0 else {})
            (src / "model.out").write_bytes(OUT)
            (src / "estimates.dat").write_bytes(ESTIMATES)
            (src / "tech3.dat").write_bytes(TECH3)
            dump(src / "engine_receipt.json", {"wall_seconds": 0.1, "synthetic": True})
            dump(src / "job.json", {"cap_seconds": cap, "hashes": {
                name: worker.digest(src / name) for name in ("model.inp", "data.dat", "fixture.json")}})
        self.plan = {"schema": worker.SCHEMA, "source": str(self.source), "engine": str(Path(sys.executable).resolve()),
                     "engine_sha256": worker.digest(sys.executable), "synthetic_script": str(self.fake),
                     "authorization": "Synthetic engineering regression only; zero participant data or Mplus calls",
                     "poll_seconds": 0.05, "budget": {"prior_engine_starts": prior_calls,
                     "prior_engine_seconds": prior_seconds, "max_engine_starts": max_calls or len(self.members),
                     "max_total_engine_seconds": max_seconds or cap * len(self.members)}}
        dump(self.plan_path, self.plan)

    def tearDown(self):
        # 先释放本测试合成引擎，再仅清理明确绑定到本临时目录的 Python 子进程。
        for member in self.members:
            directory = self.work / "models" / member
            if directory.exists():
                (directory / "FAKE_RELEASE").write_text("release")
        for proc in self.children:
            if proc.poll() is None:
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        for marker_path in list((self.work / "models").glob("*/ENGINE_STARTED.json")) + list((self.work / "attempts").glob("*/CLAIM.json")):
            try:
                marker = read(marker_path)
                proc = psutil.Process(marker["pid"])
                if (abs(proc.create_time() - marker["created"]) < 1e-3
                        and any(str(self.root) in argument for argument in proc.cmdline())):
                    proc.kill()
                    psutil.wait_procs([proc], timeout=5)
            except (psutil.Error, OSError, ValueError, KeyError):
                pass
        for stream in self.streams:
            stream.close()
        evidence = os.environ.get("DURABLE_MPLUS_TEST_EVIDENCE")
        if evidence:
            # 所有夹具均为合成数据；保留失败现场及正例原回执，避免断言后只剩 rc。
            shutil.copytree(self.root, Path(evidence) / self._testMethodName)
        self.temporary.cleanup()

    def run_worker(self, *, with_plan=True):
        output = self.root / ("direct-worker-%03d.log" % len(list(self.root.glob("direct-worker-*.log"))))
        with output.open("w", encoding="utf-8") as stream, redirect_stdout(stream):
            return worker.Worker(self.work, self.plan_path if with_plan else None, synthetic=True).run()

    def child(self, command, label):
        stream = (self.root / (label + ".log")).open("wb")
        self.streams.append(stream)
        proc = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        self.children.append(proc)
        return proc

    def launch_worker(self, label="coordinator"):
        return self.child([sys.executable, "-B", str(SCRIPTS / "durable_mplus_worker.py"), "run",
                           "--work", str(self.work), "--plan", str(self.plan_path), "--synthetic-test"], label)

    def wait_path(self, path, *, timeout=20):
        end = time.monotonic() + timeout
        while not path.exists() and time.monotonic() < end:
            time.sleep(0.02)
        self.assertTrue(path.exists(), "Missing " + str(path) + "\n" + self.logs())
        return path

    def logs(self):
        return "\n".join(p.read_text(errors="replace")[-4000:] for p in self.root.glob("*.log"))

    def starts(self):
        return sum(len(p.read_text().splitlines()) for p in (self.work / "models").glob("*/fake_starts.log"))

    def test_serial_batch_and_repeat_resume_reuse_outputs(self):
        self.assertEqual(self.run_worker(), 0)
        receipt = read(self.work / "STATUS.json")
        self.assertEqual(receipt["stage"], "BATCH_VERIFIED")
        self.assertEqual(receipt["budget"]["recorded_new_engine_starts"], 2)
        self.assertTrue(receipt["synthetic"])
        before = {str(p): p.read_bytes() for p in (self.work / "models").glob("*/RESULT.json")}
        self.assertEqual(self.run_worker(with_plan=False), 0)
        self.assertEqual(self.starts(), 2)
        self.assertTrue(all(Path(p).read_bytes() == value for p, value in before.items()))
        independent = verify_batch(self.source, self.work)
        self.assertEqual(independent["status"], "BATCH_OUTPUTS_VERIFIED", independent["errors"])

    def test_coordinator_crash_keeps_original_engine_and_remaining_batch(self):
        self.configure(settings={"wait_before": True})
        first = self.launch_worker()
        dest = self.work / "models" / self.members[0]
        self.wait_path(dest / "FAKE_STARTED")
        claim = read(self.work / "attempts" / self.members[0] / "CLAIM.json")
        engine = read(dest / "ENGINE_STARTED.json")
        first.kill()
        first.wait(timeout=5)
        self.assertTrue(psutil.pid_exists(engine["pid"]))
        second = self.launch_worker("resumed-coordinator")
        self.wait_path(self.root / "resumed-coordinator.log")
        (dest / "FAKE_RELEASE").write_text("release")
        # 外层测试需涵盖两个成员与 Windows 文件核验；每个引擎的 12 秒 cap 不变。
        self.assertEqual(second.wait(timeout=60), 0, self.logs())
        self.assertEqual(self.starts(), 2)
        self.assertEqual(claim, read(self.work / "attempts" / self.members[0] / "CLAIM.json"))
        self.assertEqual(engine, read(dest / "ENGINE_STARTED.json"))

    def test_live_and_terminated_guardian_with_boot_clock_jitter(self):
        # 保留真实活进程和已退出但尚持有 Popen 句柄的两种状态，覆盖两端实际差异。
        release = self.root / "unreaped-guardian-release"
        ready = self.root / "unreaped-guardian-ready"
        command = ("from pathlib import Path\nimport sys,time\nPath(sys.argv[2]).touch()\n"
                   "while not Path(sys.argv[1]).exists(): time.sleep(.02)\n")
        proc = self.child([sys.executable, "-c", command, str(release), str(ready),
                           "guardian", str(self.work), self.members[0]], "unreaped-guardian")
        self.wait_path(ready)
        observed = psutil.Process(proc.pid)
        claim = {"pid": proc.pid, "created": observed.create_time(), "exe": observed.exe(),
                 "host": worker.host(), "boot_time": psutil.boot_time() + .000256}
        self.assertTrue(worker.live_guardian(claim, self.work, self.members[0]))
        release.write_text("release")
        deadline = time.monotonic() + 10
        while worker.live_guardian(claim, self.work, self.members[0]) and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertFalse(worker.live_guardian(claim, self.work, self.members[0]))
        proc.wait(timeout=5)

    def test_live_unreadable_guardian_still_holds(self):
        claim = worker.process_record()
        observed = psutil.Process()
        with mock.patch.object(psutil.Process, "cmdline", side_effect=psutil.AccessDenied(observed.pid)):
            with self.assertRaisesRegex(worker.Rejected, "Guardian process is unreadable"):
                worker.live_guardian(claim, self.work, self.members[0])

    def test_guardian_permission_error_during_exit_is_reobserved(self):
        release, ready = self.root / "exiting-release", self.root / "exiting-ready"
        code = "from pathlib import Path\nimport sys,time\nPath(sys.argv[2]).touch()\nwhile not Path(sys.argv[1]).exists():time.sleep(.01)\n"
        proc = self.child([sys.executable, "-c", code, str(release), str(ready), "guardian", str(self.work), self.members[0]], "exiting")
        self.wait_path(ready)
        observed = psutil.Process(proc.pid)
        claim = {"pid": proc.pid, "created": observed.create_time(), "exe": observed.exe(), "host": worker.host()}
        def exiting_error(_process):
            release.touch()
            raise psutil.AccessDenied(proc.pid)
        with mock.patch.object(psutil.Process, "cmdline", exiting_error):
            self.assertFalse(worker.live_guardian(claim, self.work, self.members[0]))
        proc.wait(timeout=5)

    def test_guardian_empty_identity_during_exit_is_reobserved(self):
        # 复现 CI 竞态：终态前一瞬 cmdline 读成空列表，原进程随即退出，不应判身份不符。
        release, ready = self.root / "empty-identity-release", self.root / "empty-identity-ready"
        code = "from pathlib import Path\nimport sys,time\nPath(sys.argv[2]).touch()\nwhile not Path(sys.argv[1]).exists():time.sleep(.01)\n"
        proc = self.child([sys.executable, "-c", code, str(release), str(ready), "guardian", str(self.work), self.members[0]], "empty-identity")
        self.wait_path(ready)
        observed = psutil.Process(proc.pid)
        claim = {"pid": proc.pid, "created": observed.create_time(), "exe": observed.exe(), "host": worker.host()}
        def exiting_empty(_process):
            release.touch()
            return []
        with mock.patch.object(psutil.Process, "cmdline", exiting_empty):
            self.assertFalse(worker.live_guardian(claim, self.work, self.members[0]))
        proc.wait(timeout=5)

    def test_live_guardian_with_other_identity_is_rejected(self):
        # 负对照：同 PID 与创建时间但命令不是原 guardian，且进程仍活，必须拒绝。
        release, ready = self.root / "other-identity-release", self.root / "other-identity-ready"
        code = "from pathlib import Path\nimport sys,time\nPath(sys.argv[2]).touch()\nwhile not Path(sys.argv[1]).exists():time.sleep(.01)\n"
        proc = self.child([sys.executable, "-c", code, str(release), str(ready), "other"], "other-identity")
        self.wait_path(ready)
        observed = psutil.Process(proc.pid)
        claim = {"pid": proc.pid, "created": observed.create_time(), "exe": observed.exe(), "host": worker.host()}
        try:
            with self.assertRaisesRegex(worker.Rejected, "Live guardian identity differs"):
                worker.live_guardian(claim, self.work, self.members[0])
        finally:
            release.touch()
            proc.wait(timeout=5)

    def test_second_coordinator_cannot_change_running_batch(self):
        self.configure(members=1, settings={"wait_before": True})
        first = self.launch_worker()
        dest = self.work / "models" / self.members[0]
        self.wait_path(dest / "FAKE_STARTED")
        second = self.launch_worker("second-coordinator")
        self.assertEqual(second.wait(timeout=10), 75)
        self.assertIsNone(first.poll())
        self.assertEqual(self.starts(), 1)
        (dest / "FAKE_RELEASE").write_text("release")
        self.assertEqual(first.wait(timeout=15), 0, self.logs())

    def test_duplicate_guardians_have_one_permanent_engine_claim(self):
        self.configure(members=1)
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        with worker.file_lock(self.work / ".batch-worker.lock"):
            owner.initialize()
            owner.prepare(self.members[0])
        command = [sys.executable, "-B", str(SCRIPTS / "durable_mplus_worker.py"), "guardian",
                   "--work", str(self.work), "--member", self.members[0]]
        first, second = self.child(command, "guardian1"), self.child(command, "guardian2")
        codes = [first.wait(timeout=15), second.wait(timeout=15)]
        self.assertEqual(sorted(codes), [0, 75], self.logs())
        self.assertEqual(self.starts(), 1)
        self.assertEqual(self.run_worker(), 0)
        self.assertEqual(self.starts(), 1)

    def test_original_cap_survives_coordinator_crash(self):
        self.configure(members=1, cap=4, settings={"wait_before": True})
        first = self.launch_worker()
        dest = self.work / "models" / self.members[0]
        self.wait_path(dest / "FAKE_STARTED")
        claim = read(self.work / "attempts" / self.members[0] / "CLAIM.json")
        first.kill()
        first.wait(timeout=5)
        second = self.launch_worker("resumed-cap")
        self.assertEqual(second.wait(timeout=15), 2, self.logs())
        receipt = read(self.work / "attempts" / self.members[0] / "ENGINE_EXIT.json")
        self.assertEqual(receipt["engine_state"], "TIMEOUT")
        self.assertNotEqual(receipt["engine_exit_code"], 0)
        self.assertEqual(receipt["cap_seconds"], 4)
        self.assertEqual(receipt["guardian"], claim)
        self.assertEqual(self.starts(), 1)
        self.assertFalse((dest / "RESULT.json").exists())

    def test_saved_orphan_without_exit_receipt_adopts_and_holds_budget(self):
        self.configure(settings={"wait_after": True})
        first = self.launch_worker()
        dest = self.work / "models" / self.members[0]
        self.wait_path(dest / "FAKE_OUTPUTS_READY")
        claim = read(self.work / "attempts" / self.members[0] / "CLAIM.json")
        first.kill()
        first.wait(timeout=5)
        supervisor = psutil.Process(claim["pid"])
        self.assertAlmostEqual(supervisor.create_time(), claim["created"], places=3)
        supervisor.kill()
        psutil.wait_procs([supervisor], timeout=5)
        (dest / "FAKE_RELEASE").write_text("release")
        marker = read(dest / "ENGINE_STARTED.json")
        try:
            psutil.wait_procs([psutil.Process(marker["pid"])], timeout=5)
        except psutil.NoSuchProcess:
            pass
        self.assertEqual(self.run_worker(), 2)
        path = self.work / "recovery_adoptions" / (self.members[0] + ".json")
        adopted = read(path)
        self.assertIsNone(adopted["engine_exit_code"])
        self.assertIsNone(adopted["budget_remaining"])
        self.assertFalse((dest / "RESULT.json").exists())
        self.assertEqual(self.starts(), 1)
        original_adoption = path.read_bytes()
        self.assertEqual(self.run_worker(), 2)
        self.assertEqual(path.read_bytes(), original_adoption)
        self.assertEqual(self.starts(), 1)

    def test_changed_saved_output_is_preserved_and_never_reestimated(self):
        self.assertEqual(self.run_worker(), 0)
        target = self.work / "models" / self.members[0] / "estimates.dat"
        target.write_bytes(b"999 0.25\n")
        self.assertEqual(self.run_worker(), 2)
        self.assertEqual(target.read_bytes(), b"999 0.25\n")
        self.assertEqual(self.starts(), 2)
        self.assertFalse((self.work / "archive").exists())

    def test_changed_source_holds_without_touching_old_results(self):
        self.assertEqual(self.run_worker(), 0)
        result = self.work / "models" / self.members[0] / "RESULT.json"
        before = result.read_bytes()
        (self.source / "models" / self.members[0] / "data.dat").write_bytes(b"9 9\n")
        self.assertEqual(self.run_worker(), 2)
        self.assertEqual(result.read_bytes(), before)
        self.assertEqual(self.starts(), 2)

    def test_call_budget_stays_exhausted_after_resume(self):
        self.configure(max_calls=1)
        self.assertEqual(self.run_worker(), 2)
        self.assertEqual(self.starts(), 1)
        self.assertEqual(self.run_worker(with_plan=False), 2)
        self.assertEqual(self.starts(), 1)

    def test_total_time_budget_stays_exhausted_after_resume(self):
        self.configure(max_seconds=12)
        self.assertEqual(self.run_worker(), 2)
        self.assertEqual(self.starts(), 1)
        self.assertEqual(self.run_worker(with_plan=False), 2)
        self.assertEqual(self.starts(), 1)

    def test_prior_budget_is_charged_before_any_new_engine(self):
        self.configure(prior_calls=2)
        self.assertEqual(self.run_worker(), 2)
        self.assertEqual(self.starts(), 0)

    def test_modified_binding_cannot_reset_budget(self):
        self.configure(max_calls=1)
        self.assertEqual(self.run_worker(), 2)
        binding = self.work / "BATCH_BINDING.json"
        changed = read(binding)
        changed["budget"]["max_engine_starts"] = 2
        dump(binding, changed)
        self.assertEqual(self.run_worker(with_plan=False), 2)
        self.assertIn("cannot be reset", read(self.work / "STATUS.json")["reason"])
        self.assertEqual(self.starts(), 1)

    def test_finite_numbers_do_not_override_error_or_nonzero_exit(self):
        for settings in ({"invalid_output": True}, {"exit_code": 7}):
            with self.subTest(settings=settings):
                # 不重用工作目录；不同失败各自留证。
                self.work = self.root / ("invalid-out" if "invalid_output" in settings else "nonzero-exit")
                self.configure(settings=settings)
                self.assertEqual(self.run_worker(), 2)
                self.assertEqual(self.starts(), 1)
                self.assertFalse((self.work / "models" / self.members[0] / "RESULT.json").exists())

    def test_execution_receipt_change_invalidates_previous_success(self):
        self.assertEqual(self.run_worker(), 0)
        path = self.work / "attempts" / self.members[0] / "ENGINE_EXIT.json"
        changed = read(path)
        changed["wall_seconds"] = 0
        dump(path, changed)
        self.assertEqual(self.run_worker(), 2)
        self.assertIn("receipt changed", read(self.work / "STATUS.json")["reason"])
        self.assertEqual(self.starts(), 2)

    def test_over_cap_exit_receipt_is_not_accepted_before_result_publication(self):
        self.assertEqual(self.run_worker(), 0)
        member = self.members[0]
        dest = self.work / "models" / member
        receipt_path = self.work / "attempts" / member / "ENGINE_EXIT.json"
        receipt = read(receipt_path)
        receipt["wall_seconds"] = receipt["cap_seconds"] + 1
        dump(receipt_path, receipt)
        # 仅在合成夹具中模拟退出回执已有、RESULT 尚未发布的窗口。
        (self.root / "prior_synthetic_result.json").write_bytes((dest / "RESULT.json").read_bytes())
        (dest / "RESULT.json").unlink()
        before = {name: (dest / name).read_bytes() for name in ("model.inp", "model.out", "estimates.dat", "tech3.dat")}
        self.assertEqual(self.run_worker(), 2)
        self.assertIn("exceeds its original cap", read(self.work / "STATUS.json")["reason"])
        self.assertFalse((dest / "RESULT.json").exists())
        self.assertEqual(read(receipt_path), receipt)
        self.assertEqual(self.starts(), 2)
        self.assertEqual({name: (dest / name).read_bytes() for name in before}, before)

    def test_guardian_exit_observed_after_deadline_is_not_success(self):
        # 受控单调时钟精确覆盖“轮询空窗中已退出”的边界，不用短 sleep 猜机器速度。
        for elapsed, expected_rc in ((1.0, 0), (13.0, 2)):
            with self.subTest(elapsed=elapsed):
                self.work = self.root / ("clock-" + str(int(elapsed)))
                controller = worker.Worker(self.work, self.plan_path, synthetic=True)
                controller.initialize()
                member = self.members[0]
                controller.prepare(member)
                child = mock.Mock(pid=2147483000)
                child.poll.return_value = child.wait.return_value = 0
                identity = mock.Mock(pid=2147483000)
                identity.create_time.return_value = 1700000000.0
                identity.exe.return_value = str(Path(sys.executable).resolve())
                with mock.patch.object(worker.subprocess, "Popen", return_value=child), \
                        mock.patch.object(worker.psutil, "Process", return_value=identity), \
                        mock.patch.object(worker.time, "monotonic", side_effect=[100.0, 100.0 + elapsed, 100.0 + elapsed]), \
                        mock.patch.object(worker, "stop_owned") as stop:
                    rc = worker.main(["guardian", "--work", str(self.work), "--member", member])
                self.assertEqual(rc, expected_rc)
                receipt = read(self.work / "attempts" / member / "ENGINE_EXIT.json")
                self.assertEqual(receipt["engine_exit_code"], 0)
                self.assertEqual(receipt["engine_state"], "EXITED" if expected_rc == 0 else "TIMEOUT")
                self.assertEqual(receipt["wall_seconds"], elapsed)
                stop.assert_not_called()

    def test_legacy_directory_never_becomes_new_authority(self):
        self.work.mkdir()
        original = self.work / "worker.lock"
        original.write_text("legacy owned work")
        status = self.work / "STATUS.json"
        status.write_text("original legacy progress")
        before = {p.name: p.read_bytes() for p in self.work.iterdir()}
        self.assertEqual(self.run_worker(), 2)
        self.assertEqual({p.name: p.read_bytes() for p in self.work.iterdir()}, before)
        self.assertEqual(self.starts(), 0)

    def test_missing_prior_budget_is_not_assumed_zero(self):
        del self.plan["budget"]["prior_engine_seconds"]
        dump(self.plan_path, self.plan)
        self.assertEqual(self.run_worker(), 2)
        self.assertEqual(self.starts(), 0)

    def test_peer_d1_over_cap_orphan_is_not_adopted(self):
        self.configure(members=1)
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        owner.initialize()
        member = self.members[0]
        intent = owner.prepare(member)
        dest = self.work / "models" / member
        dump(dest / "ENGINE_STARTED.json", {"pid": 2147483000, "created": time.time() - 30,
            "host": worker.host(), "inputs": intent["inputs"], "attempt_id": intent["attempt_id"],
            "engine_sha256": owner.binding["engine_sha256"]})
        for name in worker.OUTPUTS:
            (dest / name).write_bytes((self.source / "models" / member / name).read_bytes())
        before = {p.name: p.read_bytes() for p in dest.iterdir()}
        with self.assertRaisesRegex(worker.Rejected, "cap"):
            owner.collect_member(member, intent)
        self.assertFalse((self.work / "recovery_adoptions" / (member + ".json")).exists())
        self.assertEqual({p.name: p.read_bytes() for p in dest.iterdir()}, before)
        self.assertEqual(self.starts(), 0)

    def test_peer_d2_stop_before_claim_does_not_spend_unique_start(self):
        self.configure(members=1)
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        owner.initialize()
        owner.prepare(self.members[0])
        (self.work / "STOP").touch()
        self.assertNotEqual(worker.guardian(self.work, self.members[0]), 0)
        self.assertFalse((self.work / "attempts" / self.members[0] / "CLAIM.json").exists())
        self.assertEqual(self.starts(), 0)
        (self.work / "STOP").unlink()
        self.assertEqual(self.run_worker(), 0)
        self.assertEqual(self.starts(), 1)

    def test_peer_d2_stop_finishes_current_member_then_resumes_remaining(self):
        self.configure(settings={"wait_before": True})
        first = self.launch_worker()
        dest = self.work / "models" / self.members[0]
        self.wait_path(dest / "FAKE_STARTED")
        (self.work / "STOP").touch()
        time.sleep(.25)
        self.assertIsNone(first.poll(), self.logs())
        self.assertFalse((self.work / "attempts" / self.members[0] / "ENGINE_EXIT.json").exists())
        (dest / "FAKE_RELEASE").touch()
        self.assertEqual(first.wait(timeout=30), 2, self.logs())
        self.assertTrue((dest / "RESULT.json").exists())
        self.assertEqual(self.starts(), 1)
        (self.work / "STOP").unlink()
        self.assertEqual(self.run_worker(), 0)
        self.assertEqual(self.starts(), 2)

    def test_peer_d3_expired_admission_can_recheck_same_reserved_intent(self):
        self.configure(members=1)
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        owner.initialize()
        intent = owner.prepare(self.members[0])
        original = (self.work / "attempts" / self.members[0] / "INTENT.json").read_bytes()
        # 只替换观测接口；本例不进入 Windows API 或引擎。
        owner.binding["synthetic"] = False
        owner.binding["resource_contract"]["resource_wait_seconds"] = .05
        owner.binding["poll_seconds"] = .02
        intent["admission_deadline"] = time.time() - 1
        with mock.patch.object(worker, "memory_state", return_value={"available_gib": 0, "commit_available_gib": 0}), \
                mock.patch.object(worker.psutil, "cpu_percent", return_value=0), \
                mock.patch.object(worker.psutil, "process_iter", return_value=[]):
            with self.assertRaises(worker.Rejected):
                owner.admit(self.members[0], intent)
        with mock.patch.object(worker, "memory_state", return_value={"available_gib": 100, "commit_available_gib": 100}), \
                mock.patch.object(worker.psutil, "cpu_percent", return_value=0), \
                mock.patch.object(worker.psutil, "process_iter", return_value=[]):
            owner.admit(self.members[0], intent)
        self.assertEqual((self.work / "attempts" / self.members[0] / "INTENT.json").read_bytes(), original)
        self.assertFalse((self.work / "attempts" / self.members[0] / "CLAIM.json").exists())
        self.assertEqual(owner.budget()["reserved_calls"], 1)
        self.assertEqual(self.starts(), 0)

    def test_peer_d5_process_disappearance_leaves_durable_hold(self):
        with mock.patch.object(worker.Worker, "run_member", side_effect=psutil.NoSuchProcess(2147483000)):
            self.assertEqual(self.run_worker(), 2)
        self.assertEqual(read(self.work / "STATUS.json")["stage"], "HOLD")
        self.assertEqual(self.starts(), 0)

    def test_peer_d4_export_keeps_data_on_windows_and_preserves_original_results(self):
        self.assertEqual(self.run_worker(), 0)
        before = {member: (self.work / "models" / member / "RESULT.json").read_bytes() for member in self.members}
        # 未声明文件不能因处在工作目录就被整目录带回。
        (self.work / "models" / self.members[0] / "participant_extra.csv").write_text("synthetic-private,1\n")
        output = self.root / "return"
        self.assertEqual(worker.main(["export", "--work", str(self.work), "--out", str(output)]), 0)
        self.assertEqual(verify_batch(self.source, output)["status"], "BATCH_OUTPUTS_VERIFIED")
        self.assertFalse(any(p.name in {"data.dat", "fixture.json", "participant_extra.csv"} for p in output.rglob("*")))
        for member in self.members:
            self.assertTrue((self.work / "models" / member / "data.dat").exists())
            self.assertEqual((self.work / "models" / member / "RESULT.json").read_bytes(), before[member])
            self.assertEqual((output / "models" / member / "RESULT.json").read_bytes(), before[member])
        original_bytes = (output / "RETURN_INPUT_EXCLUSIONS.json").read_bytes()
        original = json.loads(original_bytes)
        for key in ("result_sha256", "inputs"):
            bad = json.loads(json.dumps(original))
            if key == "result_sha256":
                bad["members"][self.members[0]][key] = "0" * 64
            else:
                bad["members"][self.members[0]][key]["data.dat"] = "0" * 64
            dump(output / "RETURN_INPUT_EXCLUSIONS.json", bad)
            self.assertEqual(verify_batch(self.source, output)["status"], "REVIEW_REQUIRED")
        # 恢复完整原字节，避免 JSON 重新排版留下与导出清单不符的测试快照。
        (output / "RETURN_INPUT_EXCLUSIONS.json").write_bytes(original_bytes)
        for relative, item in read(output / "EXPORT_MANIFEST.json")["files"].items():
            self.assertEqual(hashlib.sha256((output / relative).read_bytes()).hexdigest(),
                             item["sha256"], relative)
        self.assertEqual(self.starts(), 2)

    def test_peer_d4_failed_batch_exports_diagnostics_without_input_data(self):
        self.configure(members=1, settings={"invalid_output": True})
        self.assertEqual(self.run_worker(), 2)
        output = self.root / "failed-return"
        self.assertEqual(worker.main(["export", "--work", str(self.work), "--out", str(output)]), 0)
        self.assertTrue((output / "models" / self.members[0] / "model.out").exists())
        self.assertFalse(any(p.name in {"data.dat", "fixture.json"} for p in output.rglob("*")))
        self.assertEqual(verify_batch(self.source, output)["status"], "REVIEW_REQUIRED")
        self.assertTrue((self.work / "models" / self.members[0] / "data.dat").exists())

    def test_peer_n2_export_waits_for_live_orphan_then_allows_exited_diagnostics(self):
        self.configure(members=1, settings={"wait_after": True})
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        owner.initialize()
        member = self.members[0]
        intent = owner.prepare(member)
        dest, attempt = self.work / "models" / member, self.work / "attempts" / member
        dump(attempt / "CLAIM.json", {"pid": 2147483000, "created": 1, "host": worker.host()})
        proc = subprocess.Popen([sys.executable, str(self.fake), "model.inp"], cwd=dest)
        self.children.append(proc)
        self.wait_path(dest / "FAKE_OUTPUTS_READY")
        dump(dest / "ENGINE_STARTED.json", {"pid": proc.pid, "created": psutil.Process(proc.pid).create_time(),
             "inputs": intent["inputs"], "engine_sha256": owner.binding["engine_sha256"]})
        before = (dest / "model.out").read_bytes()
        output = self.root / "return-after-orphan"
        with self.assertRaisesRegex(worker.Rejected, "engine is still active"):
            worker.export_results(self.work, output)
        self.assertFalse(output.exists())
        self.assertIsNone(proc.poll())
        self.assertEqual((dest / "model.out").read_bytes(), before)
        (dest / "FAKE_RELEASE").touch()
        proc.wait(timeout=10)
        self.assertEqual(worker.export_results(self.work, output)["stage"], "OUTPUTS_EXPORTED")
        self.assertFalse((output / "models" / member / "data.dat").exists())
        self.assertFalse((output / "models" / member / "RESULT.json").exists())
        self.assertEqual(read(output / "EXPORT_MANIFEST.json")["numerical_validation"], "REQUIRED_SEPARATELY")
        self.assertEqual(self.starts(), 1)

    def test_peer_n2_missing_start_and_unknown_exit_refuse_export(self):
        self.configure(members=1)
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        owner.initialize()
        member = self.members[0]
        owner.prepare(member)
        attempt = self.work / "attempts" / member
        dump(attempt / "CLAIM.json", {"pid": 2147483000, "created": 1, "host": worker.host()})
        output = self.root / "unmarked-return"
        with self.assertRaisesRegex(worker.Rejected, "Engine-start record is missing"):
            worker.export_results(self.work, output)
        dump(attempt / "ENGINE_EXIT.json", {"engine_exit_confirmed": False})
        with self.assertRaisesRegex(worker.Rejected, "Engine-start record is missing"):
            worker.export_results(self.work, output)
        self.assertFalse(output.exists())
        self.assertEqual(self.starts(), 0)

    def test_peer_n2_unreadable_original_engine_refuses_export(self):
        self.configure(members=1)
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        owner.initialize()
        member = self.members[0]
        owner.prepare(member)
        dump(self.work / "models" / member / "ENGINE_STARTED.json", {"pid": 4242, "created": 1})
        output = self.root / "unreadable-return"
        with mock.patch.object(worker.psutil, "Process", side_effect=psutil.AccessDenied(4242)):
            with self.assertRaisesRegex(worker.Rejected, "engine state is unreadable"):
                worker.export_results(self.work, output)
        self.assertFalse(output.exists())

    def test_peer_d6_missing_marker_reports_matching_live_process_without_killing(self):
        self.configure(members=1)
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        owner.initialize()
        member = self.members[0]
        intent = owner.prepare(member)
        dest = self.work / "models" / member
        command = "from pathlib import Path\nimport time\nPath('UNMARKED_READY').touch()\nwhile not Path('UNMARKED_RELEASE').exists():time.sleep(.02)\n"
        proc = subprocess.Popen([sys.executable, "-c", command, "model.inp"], cwd=dest)
        self.children.append(proc)
        self.wait_path(dest / "UNMARKED_READY")
        with self.assertRaises(worker.Rejected):
            owner.collect_member(member, intent)
        notes = list((self.work / "attempts" / member).glob("UNMARKED_ENGINE_OBSERVATION_*.json"))
        self.assertEqual(len(notes), 1)
        self.assertIn(proc.pid, [p["pid"] for p in read(notes[0])["matching_processes"]])
        self.assertIsNone(proc.poll())
        (dest / "UNMARKED_RELEASE").touch()
        proc.wait(timeout=5)

    def test_peer_d7_failed_termination_preserves_unknown_exit_and_budget(self):
        self.configure(members=1)
        owner = worker.Worker(self.work, self.plan_path, synthetic=True)
        owner.initialize()
        member = self.members[0]
        owner.prepare(member)
        child = mock.Mock(pid=2147483000)
        child.poll.return_value = None
        child.wait.side_effect = subprocess.TimeoutExpired("synthetic-engine", 15)
        identity = mock.Mock(pid=2147483000)
        identity.create_time.return_value = 1700000000.0
        identity.exe.return_value = str(Path(sys.executable).resolve())
        with mock.patch.object(worker.subprocess, "Popen", return_value=child), \
                mock.patch.object(worker.psutil, "Process", return_value=identity), \
                mock.patch.object(worker.time, "monotonic", side_effect=[100.0, 113.0, 114.0]), \
                mock.patch.object(worker, "stop_owned"):
            self.assertEqual(worker.main(["guardian", "--work", str(self.work), "--member", member]), 2)
        receipt = read(self.work / "attempts" / member / "ENGINE_EXIT.json")
        self.assertIsNone(receipt["engine_exit_code"])
        self.assertFalse(receipt["engine_exit_confirmed"])
        self.assertEqual(owner.budget()["unsettled_members"], [member])
        self.assertFalse((self.work / "models" / member / "RESULT.json").exists())

    def test_peer_d8_byte_identical_output_has_matching_status(self):
        self.configure(members=1)
        self.assertEqual(self.run_worker(), 0)
        self.assertEqual(read(self.work / "models" / self.members[0] / "RESULT.json")["status"], "PASS_IDENTICAL")

    @unittest.skipUnless(os.name == "nt", "Native Windows memory API")
    def test_windows_resource_observation_is_real(self):
        observed = worker.memory_state()
        self.assertGreater(observed["available_gib"], 0)
        self.assertGreater(observed["commit_available_gib"], 0)


if __name__ == "__main__":
    unittest.main()
