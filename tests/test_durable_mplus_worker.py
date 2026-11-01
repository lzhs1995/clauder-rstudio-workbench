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

    @unittest.skipUnless(os.name == "nt", "Native Windows memory API")
    def test_windows_resource_observation_is_real(self):
        observed = worker.memory_state()
        self.assertGreater(observed["available_gib"], 0)
        self.assertGreater(observed["commit_available_gib"], 0)


if __name__ == "__main__":
    unittest.main()
