"""双模式提案的可移植行为控制；全部数据/队列为临时合成件，不启动模型。"""
from __future__ import annotations

from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "mplusautomation-guide" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("queue_modes_under_test", SCRIPTS / "mplus_queue.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BASE = 2_000_000_000.0
MODES = ("legacy_compatible", "candidate_measured")
POLICY = dict(reserve_gib=1.5, commit_reserve_gib=1.5, processor_budget=12,
              cpu_hold_percent=90, cpu_resume_percent=75, disk_reserve_gib=10,
              windows_profile_max_age_sec=300, credit_observed_running_private=False)


def dump(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Clock:
    now = BASE
    def time(self):
        return self.now
    def __getattr__(self, key):
        return getattr(time, key)


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.clock = Clock()
        # 使用Python3.10已支持的清理API，避免TestCase.enterContext的3.11下限。
        for patcher in (patch.object(MODULE, "time", self.clock),
                        patch.object(MODULE, "resource_snapshot", side_effect=AssertionError("禁止真实采样"))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def config(self, name="q", mode="candidate_measured", **extra):
        root = self.root / name
        root.mkdir(exist_ok=True)
        policy = {**POLICY, **extra.pop("resource_policy", {})}
        if mode is not None:
            policy["autoscale_mode"] = mode
        dump(root / "config.json", {"resource_policy": policy, **extra})
        return root

    def queue(self, name="q", mode="candidate_measured", **extra):
        q = MODULE.Queue(self.config(name, mode, **extra))
        self.addCleanup(q.db.close)
        return q

    def sample(self, **extra):
        return dict(at=self.clock.now, memory_percent=25.0, available_gib=8.0,
                    total_gib=32.0, free_virtual_gib=16.0, cpu_percent=10.0,
                    disk_free_gib=100.0, source="UNIT_TEST_ONLY",
                    host_memory_unverified=False, host_cpu_unverified=False,
                    host_disk_unverified=False, **extra)

    def enqueue(self, q, item):
        folder = q.root / "models" / item["id"]
        folder.mkdir(parents=True)
        inp = folder / "model.inp"
        inp.write_text("TITLE: synthetic " + item.get("input_group", item["id"]) + ";\n", encoding="utf-8")
        script = folder / "never_run.R"
        script.write_text("stop('UNIT_TEST_ONLY must never execute')\n", encoding="utf-8")
        payload = {k:v for k,v in item.items() if k not in ("state", "input_group")}
        payload.update(input=str(inp), input_sha256=sha(inp), output=str(folder / (item["id"] + ".out")),
                       script=str(script), fingerprint="synthetic:" + item["id"])
        q.enqueue(payload)
        if item.get("state") == "running":
            q.db.execute("UPDATE tasks SET status='running',worker=NULL WHERE id=?", (item["id"],))
        return payload

    def settings(self, q):
        return {r[0]:json.loads(r[1]) for r in q.db.execute("SELECT key,value FROM settings")}

    def rows(self, q):
        return [tuple(r) for r in q.db.execute("SELECT * FROM tasks ORDER BY id")]

    def events(self, q):
        return [json.loads(r[0]) for r in q.db.execute("SELECT payload FROM events WHERE kind='resources' ORDER BY sequence")]

    def tick(self, q, **changes):
        sample = self.sample()
        sample.update(changes)
        q.tick(sample)
        return sample


def _task(name: str, **kwargs) -> dict:
    return {"id": name, "memory_gib": 1.0, "processors": 1,
            "dispatch_priority": 10, "execution_class": "mplus", **kwargs}

def _scenarios() -> list[dict]:
    """使用明确数值反例；任何断言均依赖 tick 实际执行后的状态。"""
    ready = _task("ready")
    missing = [{"id": "not_produced", "requires": "estimation_ok"}]
    cases = [
        dict(id="healthy_five_samples", tasks=[ready], grow=True,
             snapshot={"memory_percent": 99.0}),
        dict(id="sample_spacing", tasks=[ready], grow=True,
             offsets=[0, 5, 10, 15, 20, 30, 60, 90, 120],
             accepted=[True, False, False, False, False, True, True, True, True]),
        dict(id="stale_sample", tasks=[ready], invalid_offset=-301, grow=True),
        dict(id="future_sample", tasks=[ready], invalid_offset=6, grow=True),
        dict(id="empty_queue", tasks=[], candidate=None, reason="no_ready_tasks"),
        dict(id="dependency_only", tasks=[_task("blocked", dependencies=missing)],
             candidate=None, reason="no_ready_tasks"),
    ]
    # 高优先级阻塞项分别很大/很小，证明实际使用 ready 的大小作决定。
    for fits in (True, False):
        name = "fits" if fits else "oversized"
        candidate = _task("ready", memory_gib=1.0 if fits else 5.0)
        distractor = _task("blocked", memory_gib=50.0 if fits else 0.1,
                           dispatch_priority=0, dependencies=missing)
        budget = {"available_gib": 8.0 if fits else 4.0}
        verdict = dict(grow=fits, reason=None if fits else "predicted_memory")
        cases.append(dict(id=f"ready_skips_dependency_{name}",
                          tasks=[distractor, candidate], snapshot=budget, **verdict))
        # source/reuse 使用相同原始输入；reuse_task 由真实 enqueue 自动绑定。
        source = _task("source", state="running", input_group="identical")
        reuse = _task("reuse", memory_gib=50.0 if fits else 0.1,
                      dispatch_priority=0, input_group="identical", reuse_identical_inputs=True)
        cases.append(dict(id=f"ready_skips_reuse_{name}",
                          tasks=[source, reuse, candidate], snapshot=budget,
                          reuse_binding=True, **verdict))
        forbidden = _task("outside_scope", memory_gib=50.0 if fits else 0.1,
                          dispatch_priority=0)
        cases.append(dict(id=f"ready_skips_scope_{name}",
                          tasks=[forbidden, candidate], scope=["ready.out"],
                          snapshot=budget, **verdict))
    cases.extend([
        dict(id="reuse_only", tasks=[
            _task("source", state="running", input_group="identical"),
            _task("reuse", input_group="identical", reuse_identical_inputs=True)],
             reuse_binding=True, candidate=None, reason="no_ready_tasks"),
        dict(id="scope_only", tasks=[_task("outside_scope")], scope=["ready.out"],
             candidate=None, reason="no_ready_tasks"),
        dict(id="running_memory_reserved", tasks=[_task("running", state="running", memory_gib=2), ready],
             snapshot={"available_gib": 4.0}, reason="predicted_memory"),
        dict(id="commit_budget", tasks=[ready], snapshot={"free_virtual_gib": 2.0},
             reason="predicted_commit"),
        dict(id="processor_budget", tasks=[_task("running", state="running", processors=11),
                                          _task("ready", processors=2)], reason="processor_budget"),
        dict(id="class_limit", tasks=[_task("running", state="running"), ready],
             policy={"max_running_by_class": {"mplus": 1}}, reason="class_limit:mplus"),
        dict(id="cpu_resume_hold", tasks=[ready], snapshot={"cpu_percent": 80.0},
             reason="cpu_resume_hold"),
    ])
    return cases

class CandidateScenarios(Fixture):
    def check_scenario(self, spec):
        extra = {"resource_policy":spec.get("policy", {})}
        if "scope" in spec:
            path = self.root / "scope.json"
            dump(path, {"allowed_output_names":spec["scope"]})
            extra["historical_success_policy"] = dict(manifest=str(path), sha256=sha(path))
        q = self.queue(**extra)
        self.assertIsNone(q.host_reservation_path)
        q.set("healthy", 4 if "invalid_offset" in spec else 0)
        q.set("last_sample", BASE - 30)
        for item in spec["tasks"]:
            self.enqueue(q, item)
        before_tasks = self.rows(q)
        if spec.get("reuse_binding"):
            row = q.db.execute("SELECT payload FROM tasks WHERE id='reuse'").fetchone()
            self.assertEqual(json.loads(row[0])["reuse_task"], "source")
        offsets = spec.get("offsets", [0,30,60,90,120])
        steps = [(off,False,ok) for off,ok in zip(offsets,spec.get("accepted",[True]*len(offsets)))]
        if "invalid_offset" in spec:
            steps = [(30*i,True,True) for i in range(5)] + [(150+30*i,False,True) for i in range(5)]
        healthy, limit, last = 0, 1, BASE - 30
        for index,(offset,invalid,accepted) in enumerate(steps):
            with self.subTest(step=index):
                self.clock.now = BASE + offset
                old_events = self.events(q)
                old_resources = self.settings(q).get("resources")
                changes = dict(spec.get("snapshot", {}))
                changes["at"] = self.clock.now + (spec.get("invalid_offset", 0) if invalid else 0)
                sample = self.tick(q, **changes)
                events = self.events(q)
                self.assertEqual(len(events)-len(old_events), int(accepted))
                if invalid:
                    healthy = 0
                    self.assertEqual(events[-1]["scale_up_reason"], "resource_sample_time_unverified")
                    self.assertEqual(self.settings(q).get("resources"), old_resources)
                elif accepted:
                    last = sample["at"]
                    healthy = healthy + 1 if spec.get("grow") else 0
                    if healthy == 5:
                        limit += 1
                        healthy = 0
                    self.assertEqual(events[-1]["scale_up_task"], spec.get("candidate", "ready"))
                    self.assertEqual(events[-1]["scale_up_reason"], spec.get("reason"))
                    self.assertEqual(q.get("resources"), sample)
                self.assertEqual((q.get("limit"),q.get("healthy"),q.get("last_sample")),(limit,healthy,last))
                if accepted:
                    self.assertEqual(events[-1]["autoscale_mode"], "candidate_measured")
                    self.assertEqual((events[-1]["limit"],events[-1]["healthy"]),(limit,healthy))
        self.assertEqual(q.get("limit"), 2 if spec.get("grow") else 1)
        self.assertEqual(self.rows(q), before_tasks)
        self.assertEqual(q.db.execute("SELECT count(*) FROM workers").fetchone()[0], 0)
        self.assertEqual(q.db.execute("SELECT count(*) FROM events WHERE kind IN ('claimed','finished','worker_registered')").fetchone()[0],0)


# 将既有19个W1行为场景迁移成独立测试；不读取私有路径或AST基线。
for case in _scenarios():
    def check(self, spec=case):
        self.check_scenario(spec)
    setattr(CandidateScenarios, "test_" + case["id"], check)


class ModeContract(Fixture):
    def test_four_conflicts_select_explicit_mode(self):
        for mode in MODES:
            for name, ready, available, now in (
                ("empty", False, 8, BASE), ("physical",True,1,BASE),
                ("stale",True,8,BASE+400), ("future",True,8,BASE-10)):
                with self.subTest(mode=mode, conflict=name):
                    q = self.queue(mode+name, mode)
                    if ready:
                        self.enqueue(q, _task("ready"))
                    q.set("healthy", 4)
                    q.set("last_sample", BASE-30)
                    self.clock.now = now
                    self.tick(q, at=BASE, available_gib=available, memory_percent=50)
                    self.assertEqual(q.get("limit"), 2 if mode == MODES[0] else 1)
                    if mode == MODES[1]:
                        self.assertEqual(q.get("healthy"),0)
                        if name in ("stale","future"):
                            self.assertEqual(q.get("last_sample"),BASE-30)

    def test_default_measured_rejects_four_conflicts_with_reason_and_clock(self):
        for name, ready, available, now, reason, accepted_sample in (
            ("empty", False, 8, BASE, "no_ready_tasks", True),
            ("physical", True, 1, BASE, "memory_hold", True),
            ("stale", True, 8, BASE+400, "resource_sample_time_unverified", False),
            ("future10s", True, 8, BASE-10, "resource_sample_time_unverified", False)):
            with self.subTest(conflict=name):
                # 不写mode字段，即使目录名包含legacy也不能暗选模式。
                q = self.queue("legacy_compatible-"+name, None)
                if ready:
                    self.enqueue(q, _task("ready"))
                q.set("healthy", 4)
                q.set("last_sample", BASE-30)
                q.set("resources", {"synthetic":"prior"})
                self.clock.now = now
                sample = self.tick(q, at=BASE, available_gib=available, memory_percent=50)
                self.assertEqual((q.get("limit"),q.get("healthy")),(1,0))
                self.assertEqual(q.get("autoscale_mode"), "candidate_measured")
                event = self.events(q)[-1]
                self.assertEqual(event["autoscale_mode"], "candidate_measured")
                self.assertEqual(event["scale_up_reason"],reason)
                self.assertEqual(q.get("last_sample"), BASE if accepted_sample else BASE-30)
                self.assertEqual(q.get("resources"), sample if accepted_sample else {"synthetic":"prior"})

    def test_default_and_explicit_candidate_reject_all_future_samples(self):
        for mode in (None,"candidate_measured"):
            for offset in (1,5,10):
                with self.subTest(mode=mode,offset=offset):
                    q = self.queue(str(mode)+str(offset),mode)
                    self.enqueue(q,_task("ready"))
                    q.set("healthy",4)
                    q.set("last_sample",BASE-30)
                    q.set("resources",{"synthetic":"prior"})
                    self.tick(q,at=BASE+offset)
                    self.assertEqual((q.get("limit"),q.get("healthy")),(1,0))
                    self.assertEqual(q.get("last_sample"),BASE-30)
                    self.assertEqual(q.get("resources"),{"synthetic":"prior"})
                    self.assertEqual(self.events(q)[-1]["scale_up_reason"],"resource_sample_time_unverified")

    def test_mode_event_cannot_be_forged_by_sample(self):
        for mode in MODES:
            q = self.queue(mode, mode)
            self.tick(q, autoscale_mode="forged")
            self.assertEqual(self.events(q)[-1]["autoscale_mode"],mode)

    def test_invalid_enum_rolls_back_fresh_and_existing(self):
        for i,mode in enumerate(("", "Candidate_measured", "candidate_measured ", "unknown", None, True, 1, [], {})):
            for existing in (False,True):
                with self.subTest(mode=mode,existing=existing):
                    name = f"invalid{i}-{existing}"
                    if existing:
                        q = self.queue(name, MODES[0])
                        q.set("healthy",4)
                        before = self.settings(q)
                    else:
                        before = {}
                    root = self.config(name, MODES[0], resource_policy={"autoscale_mode":mode})
                    config = json.loads((root/"config.json").read_text())
                    config["resource_policy"]["autoscale_mode"] = mode
                    dump(root/"config.json",config)
                    with self.assertRaisesRegex(ValueError,"autoscale_mode"):
                        MODULE.Queue(root)
                    with closing(sqlite3.connect(root/"queue.sqlite")) as db:
                        actual = {k:json.loads(v) for k,v in db.execute("SELECT key,value FROM settings")}
                    self.assertEqual(actual,before)
                    if not existing:
                        recovered = self.queue(name,MODES[1],parallel_cap=2,initial_parallel_limit=2)
                        self.assertEqual((recovered.get("limit"),recovered.get("cap")),(2,2))

    def test_switch_resets_only_healthy_and_same_mode_keeps_history(self):
        for original,successor in (MODES,tuple(reversed(MODES))):
            name = original
            q = self.queue(name,original)
            self.enqueue(q,_task("running",state="running"))
            self.enqueue(q,_task("ready"))
            q.set("limit",2)
            q.set("cap",4)
            q.set("healthy",4)
            q.set("last_sample",BASE-30)
            q.set("enabled",True)
            q.set("resources",{"synthetic":"prior"})
            before = self.settings(q)
            tasks = self.rows(q)
            reopened = self.queue(name,original)
            self.assertEqual(self.settings(reopened),before)
            switched = self.queue(name,successor)
            self.assertEqual(self.settings(switched),{**before,"healthy":0,"autoscale_mode":successor})
            self.assertEqual(self.rows(switched),tasks)
            self.tick(switched)
            self.assertEqual((switched.get("limit"),switched.get("healthy")),(2,1))

    def test_unversioned_history_is_not_assumed_to_match_new_mode(self):
        q = self.queue()
        q.set("healthy",4)
        q.set("last_sample",BASE-30)
        q.db.execute("DELETE FROM settings WHERE key='autoscale_mode'")
        before = self.settings(q)
        reopened = self.queue()
        self.assertEqual(self.settings(reopened),{**before,"healthy":0,"autoscale_mode":MODES[1]})

    def test_stale_owner_cannot_tick_after_registered_switch(self):
        old = self.queue(mode=MODES[0])
        self.enqueue(old,_task("ready"))
        new = self.queue(mode=MODES[1])
        before = self.settings(new)
        events = self.events(new)
        with self.assertRaisesRegex(ValueError,"Autoscale mode changed"):
            self.tick(old)
        self.assertEqual(self.settings(new),before)
        self.assertEqual(self.events(new),events)
        self.tick(new)
        self.assertEqual(new.get("healthy"),1)

    def test_invalid_later_policy_rolls_back_mode_switch(self):
        old = self.queue(mode=MODES[0])
        old.set("healthy",4)
        before = self.settings(old)
        scope = self.root/"allowed.json"
        dump(scope,{"allowed_output_names":["ready.out"]})
        self.config(mode=MODES[1],historical_success_policy={"manifest":str(scope),"sha256":"0"*64})
        with self.assertRaisesRegex(ValueError,"Historical-success manifest changed"):
            MODULE.Queue(old.root)
        self.assertEqual(self.settings(old),before)
        self.config(mode=MODES[1],historical_success_policy={"manifest":str(scope),"sha256":sha(scope)})
        new = MODULE.Queue(old.root)
        self.addCleanup(new.db.close)
        self.assertEqual(new.get("healthy"),0)
        self.assertEqual(new.get("autoscale_mode"),MODES[1])

    def test_mode_registration_commit_failure_rolls_back(self):
        q = self.queue(mode=MODES[0])
        q.set("healthy",4)
        before = self.settings(q)
        self.config(mode=MODES[1])
        original = MODULE.sqlite3.connect
        class FailCommit:
            def __init__(self, db): object.__setattr__(self,"db",db)
            def __getattr__(self,key): return getattr(self.db,key)
            def __setattr__(self,key,value): setattr(self.db,key,value)
            def execute(self,sql,*args):
                if sql == "COMMIT": raise sqlite3.OperationalError("synthetic pre-COMMIT failure")
                return self.db.execute(sql,*args)
        with patch.object(MODULE.sqlite3,"connect",side_effect=lambda *a,**k:FailCommit(original(*a,**k))):
            with self.assertRaisesRegex(sqlite3.OperationalError,"pre-COMMIT"):
                MODULE.Queue(q.root)
        self.assertEqual(self.settings(q),before)
        self.assertEqual(self.queue(mode=MODES[1]).get("healthy"),0)

    def test_candidate_time_boundaries_and_cap(self):
        for offset,valid in ((-300,True),(-300.001,False),(0,True),(0.001,False)):
            with self.subTest(offset=offset):
                q = self.queue(str(offset))
                self.enqueue(q,_task("ready"))
                q.set("last_sample",BASE-400)
                q.set("healthy",4)
                self.tick(q,at=BASE+offset)
                self.assertEqual((q.get("limit"),q.get("healthy")),(2 if valid else 1,0))
        q = self.queue("cap",parallel_cap=2,initial_parallel_limit=2)
        self.enqueue(q,_task("ready"))
        for i in range(12):
            self.clock.now = BASE+i*30
            self.tick(q)
        self.assertEqual(q.get("limit"),2)

    def test_apim_mode_is_explicit_and_calibration_is_unchanged(self):
        for mode in (*MODES,None):
            name = str(mode)
            root = self.config(name,mode,apim_v2=True,parallel_cap=2,initial_parallel_limit=2,calibrated=False)
            with self.assertRaisesRegex(ValueError,"calibration"):
                MODULE.Queue(root)
            with closing(sqlite3.connect(root/"queue.sqlite")) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM settings").fetchone()[0],0)
            q = self.queue(name,mode,apim_v2=True,parallel_cap=2,initial_parallel_limit=2,calibrated=True)
            self.assertEqual((q.get("limit"),q.get("cap")),(2,2))
            self.assertEqual(q.get("autoscale_mode"), mode or MODES[1])

    def test_tick_does_not_grant_or_change_claim_legacy_boundary(self):
        import apim_v2_io
        for mode in MODES:
            for admitted in (False,True):
                name = mode+str(admitted)
                q = self.queue(name,mode,host_reservation_path=str(self.root/(name+"-host.sqlite")))
                self.enqueue(q,_task("ready"))
                q.set("enabled",True)
                q.db.execute("INSERT INTO workers VALUES(?,?,?,?,?)",("synthetic",12345,123.5,BASE,None))
                calls = []
                class Registry:
                    def __init__(self,path):
                        self.db = sqlite3.connect(path)
                    def acquire(self,*args):
                        calls.append(args)
                        return dict(admitted=admitted,reason="synthetic_host_hold")
                    def acquire_measured(self,*args,**kwargs):
                        raise AssertionError("tick proposal does not change strict host API")
                with patch.object(apim_v2_io,"HostReservations",Registry):
                    self.tick(q)
                    self.assertEqual(calls,[])
                    result = q.claim("synthetic",self.sample())
                self.assertEqual(len(calls),1)
                self.assertEqual(calls[0][:5],(str(q.root)+"|ready",12345,123.5,1.0,1))
                self.assertEqual(result["status"],"claimed" if admitted else "waiting")
                if not admitted:
                    self.assertEqual(result["reason"],"synthetic_host_hold")
                self.assertEqual(q.db.execute("SELECT status FROM tasks WHERE id='ready'").fetchone()[0],
                                 "running" if admitted else "pending")


if __name__ == "__main__":
    unittest.main()
