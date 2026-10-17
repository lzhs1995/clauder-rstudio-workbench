"""真实故障形状的身份回归；不修改主机进程。"""
import importlib.util
from pathlib import Path
import psutil
import unittest

SCRIPTS=Path(__file__).parents[1]/'skills'/'mplusautomation-guide'/'scripts'


def load(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


ownership=load('process_ownership')
coordinator=load('windows_coordinator')


class Process:
    def __init__(self,pid,created,parent,name='Mplus.exe'):
        self.pid,self.created,self.parent,self.label=pid,created,parent,name
        self.descendants=[];self.priority=32;self.writes=[]
    def create_time(self): return self.created
    def ppid(self): return self.parent
    def name(self): return self.label
    def children(self,recursive): assert recursive;return self.descendants
    def nice(self,value=None):
        if value is not None: self.writes.append(value);self.priority=value
        return self.priority


def tree():
    root=Process(10,100,0,'Rterm.exe')
    cmd=Process(20,200,10,'cmd.exe')
    engine=Process(30,201,20)
    # 旧父 PID 30 被新 Mplus 复用；UI 比 root 新，却比伪父更旧。
    ui=Process(40,150,30,'desktop.exe')
    leaf=Process(50,250,40)  # leaf 比新 Mplus 更新，必须检查中间边。
    root.descendants=[cmd,engine,ui,leaf]
    table={p.pid:p for p in [root,cmd,engine,ui,leaf]}
    def factory(pid):
        if pid not in table: raise psutil.NoSuchProcess(pid)
        return table[pid]
    return root,table,factory


def test_reused_intermediate_parent_excludes_entire_branch():
    root,table,factory=tree()
    assert [p.pid for p in ownership.verified_descendants(root,factory)]==[20,30]
    assert not ownership.is_verified_descendant(table[50],dict(pid=10,created=100),factory)


def test_scheduler_does_not_modify_falsely_attributed_mplus():
    root,table,factory=tree()
    coordinator.apply_owned(dict(pid=10,created=100),{'priority':32768},dict(processes={}),lambda _:None,factory)
    assert table[30].writes==[32768]
    assert table[50].writes==[]
    assert table[40].writes==[]


def test_unverifiable_ancestry_is_excluded():
    for fault in ['missing','denied','cycle','reused','owner_reused','depth']:
        root,table,factory=tree();ref=dict(pid=10,created=100)
        if fault=='missing': del table[20]
        if fault=='cycle': table[20].parent=30;table[20].created=201
        if fault=='reused': table[20].created=202
        if fault=='owner_reused': ref['created']=99
        original=factory
        def guarded(pid):
            if fault=='denied' and pid==20: raise psutil.AccessDenied(pid)
            return original(pid)
        assert not ownership.is_verified_descendant(table[30],ref,guarded,max_depth=1 if fault=='depth' else 64),fault


def test_identity_change_during_recheck_is_rejected():
    root,table,factory=tree();calls={}
    def changing(pid):
        calls[pid]=calls.get(pid,0)+1
        if pid==20 and calls[pid]>1: return Process(20,202,10,'cmd.exe')
        return factory(pid)
    assert not ownership.is_verified_descendant(table[30],dict(pid=10,created=100),changing)


def test_parent_change_after_rollback_saved_prevents_mutation():
    root,table,factory=tree()
    def persist(_): table[30].parent=999
    coordinator.apply_owned(dict(pid=10,created=100),{'priority':32768},dict(processes={}),persist,factory)
    assert table[30].writes==[]


def test_equal_timestamp_parent_child_is_valid():
    root,table,factory=tree();table[20].created=201
    assert ownership.is_verified_descendant(table[30],dict(pid=10,created=100),factory)


def test_owner_is_not_its_own_descendant():
    root,table,factory=tree()
    assert not ownership.is_verified_descendant(root,dict(pid=10,created=100),factory)


def test_name_filter_precedes_expensive_ancestry_queries():
    root,table,factory=tree()
    ui=table[40];root.descendants=[table[20],table[30],ui]
    def no_parent_query(): raise AssertionError('Unused desktop candidate was inspected')
    ui.ppid=no_parent_query
    assert [p.pid for p in ownership.verified_descendants(root,factory,names={'mplus.exe'})]==[30]


def test_r_json_creation_time_roundoff_preserves_real_ownership():
    root,table,factory=tree()
    root.created=1792221223.0601568
    table[20].created=root.created+1;table[30].created=root.created+2
    ref=dict(pid=10,created=1792221223.0601566)
    assert ownership.is_verified_descendant(table[30],ref,factory)
    coordinator.apply_owned(ref,{'priority':32768},dict(processes={}),lambda _:None,factory)
    assert table[30].writes==[32768]
    assert not ownership.is_verified_descendant(table[30],dict(ref,created=root.created-.001),factory)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name,fn in globals().items()
                              if name.startswith('test_') and callable(fn))
