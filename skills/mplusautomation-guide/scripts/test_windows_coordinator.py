"""以假进程检验调度所有权与回滚；不修改真实进程。"""
import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
import windows_coordinator as w


class Process:
    def __init__(self,pid,name,created):
        self.pid,self.label,self.created=pid,name,created
        self.priority=32;self.affinity=[0,1,2,3];self.descendants=[];self.mutations=[];self.before_write=None
    def name(self): return self.label
    def create_time(self): return self.created
    def children(self,recursive): assert recursive;return self.descendants
    def nice(self,value=None):
        if value is not None:
            if self.before_write: self.before_write()
            self.mutations.append(('priority',value));self.priority=value
        return self.priority
    def cpu_affinity(self,value=None):
        if value is not None:
            if self.before_write: self.before_write()
            self.mutations.append(('affinity',value));self.affinity=value
        return self.affinity


def run(output):
    checks={}
    def check(name,condition): assert condition,name;checks[name]=True
    owner=Process(10,'Rscript.exe',100.0);child=Process(11,'Mplus.exe',101.0)
    foreign=Process(12,'Mplus.exe',102.0);other=Process(13,'rsession-utf8.exe',103.0)
    owner.descendants=[child,other]
    table={p.pid:p for p in [owner,child,foreign,other]}
    ref=w.identity(owner);factory=table.__getitem__;state=dict(processes={});saved=[]
    persist=lambda s:saved.append(copy.deepcopy(s))
    target={'priority':32768,'affinity':[0,1]}
    child.before_write=lambda:check('rollback_persisted_before_mutation',bool(saved) and bool(saved[0]['processes']))
    w.apply_owned(ref,target,state,persist,factory)
    check('owned_child_modified',child.priority==32768 and child.affinity==[0,1])
    check('foreign_Mplus_untouched',foreign.mutations==[])
    check('RStudio_untouched',other.mutations==[])
    count=len(child.mutations);w.apply_owned(ref,target,state,persist,factory)
    check('idempotent_next_poll',len(child.mutations)==count)
    child.priority=16384;w.apply_owned(ref,target,state,persist,factory)
    check('later_user_change_not_reapplied',child.priority==16384)
    restored=w.restore_owned(state,persist,factory)
    check('restore_preserves_user_priority',child.priority==16384)
    check('restore_owned_affinity',child.affinity==[0,1,2,3])
    child.priority=32768;child.created+=10
    w.restore_owned(state,persist,factory)
    check('restore_refuses_reused_pid',child.priority==32768)
    count=len(child.mutations);wrong=dict(ref,created=999)
    try: w.apply_owned(wrong,target,dict(processes={}),persist,factory)
    except RuntimeError: rejected=True
    else: rejected=False
    check('wrong_owner_identity_rejected',rejected and len(child.mutations)==count)
    # 协调器崩溃可能发生在setter成功后、applied状态落盘前。
    child.created=101;child.affinity=[0,1]
    pending=copy.deepcopy(saved[0]);w.restore_owned(pending,persist,factory)
    check('planned_state_crash_recovery',child.priority==32 and child.affinity==[0,1,2,3])
    # 已经为目标值不应在恢复时引入变化。
    child.priority=32768;state=dict(processes={});w.apply_owned(ref,{'priority':32768},state,persist,factory)
    count=len(child.mutations);w.restore_owned(state,persist,factory)
    check('already_target_has_no_owned_change',len(child.mutations)==count)
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);w.event(root,dict(event='sample',at='sample_time'))
        check('sample_timestamp_preserved',json.loads((root/'actions.jsonl').read_text())['at']=='sample_time')
    result=dict(status='PASS_FAKE_PROCESS_CONTRACT_TESTS',checks=checks,real_process_mutations=0,
                script_sha256=hashlib.sha256(Path(w.__file__).read_bytes()).hexdigest(),
                native_Mplus_coordination_acceptance=False,throughput_improvement_verified=False)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    print('CHECKS',len(checks))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);run(p.parse_args().output)
