"""Windows 资源诊断与可审计回收；--apply 必须来自当前任务授权。"""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import time
import psutil

class PERF(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ['CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable','SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize']]+[(n,wintypes.DWORD) for n in ['HandleCount','ProcessCount','ThreadCount']]

def snapshot():
    p=PERF();p.cb=ctypes.sizeof(p)
    ok=ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(p),p.cb)
    return dict(time=time.time(),memory=psutil.virtual_memory()._asdict(),performance_bytes={n:getattr(p,n)*p.PageSize for n in ['CommitTotal','CommitLimit','PhysicalAvailable','SystemCache','KernelTotal','KernelPaged','KernelNonpaged']} if ok else {})

def trim_file_cache():
    # -1/-1 是一次性清理，不修改永久缓存上限；权限不足时明确记录，不自动提权。
    class LUID(ctypes.Structure):_fields_=[('LowPart',wintypes.DWORD),('HighPart',wintypes.LONG)]
    class LUID_ATTR(ctypes.Structure):_fields_=[('Luid',LUID),('Attributes',wintypes.DWORD)]
    class TOKEN_PRIV(ctypes.Structure):_fields_=[('PrivilegeCount',wintypes.DWORD),('Privileges',LUID_ATTR*1)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);adv=ctypes.WinDLL('advapi32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    adv.OpenProcessToken.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.POINTER(wintypes.HANDLE)]
    adv.LookupPrivilegeValueW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR,ctypes.POINTER(LUID)]
    adv.AdjustTokenPrivileges.argtypes=[wintypes.HANDLE,wintypes.BOOL,ctypes.POINTER(TOKEN_PRIV),wintypes.DWORD,ctypes.POINTER(TOKEN_PRIV),ctypes.POINTER(wintypes.DWORD)]
    kernel.SetSystemFileCacheSize.argtypes=[ctypes.c_size_t,ctypes.c_size_t,wintypes.DWORD]
    token=wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(),0x20|0x8,ctypes.byref(token)):return dict(status='NO_PRIVILEGE',error=ctypes.get_last_error())
    try:
        requested=TOKEN_PRIV();requested.PrivilegeCount=1
        if not adv.LookupPrivilegeValueW(None,'SeIncreaseQuotaPrivilege',ctypes.byref(requested.Privileges[0].Luid)):
            return dict(status='LOOKUP_FAILED',error=ctypes.get_last_error())
        requested.Privileges[0].Attributes=2;old=TOKEN_PRIV();size=wintypes.DWORD()
        ctypes.set_last_error(0)
        if not adv.AdjustTokenPrivileges(token,False,ctypes.byref(requested),ctypes.sizeof(old),ctypes.byref(old),ctypes.byref(size)) or ctypes.get_last_error():
            return dict(status='NO_PRIVILEGE',error=ctypes.get_last_error())
        try:
            ok=kernel.SetSystemFileCacheSize(ctypes.c_size_t(-1).value,ctypes.c_size_t(-1).value,0)
            return dict(status='REQUEST_SUCCEEDED' if ok else 'REQUEST_FAILED',error=ctypes.get_last_error() if not ok else 0)
        finally:adv.AdjustTokenPrivileges(token,False,ctypes.byref(old),0,None,None)
    finally:kernel.CloseHandle(token)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--output',required=True)
    args=parser.parse_args();report=dict(before=snapshot(),actions=[])
    if args.apply:
        # 仅关闭不承载研究数据或编辑文档的工具；正常窗口关闭已尝试的情况可直接释放这些辅助程序。
        allow={'taskmgr.exe','systemsettings.exe','widgets.exe','widgetservice.exe'}
        for p in psutil.process_iter(['name','create_time']):
            if p.info['name'].lower() not in allow:continue
            action=dict(pid=p.pid,name=p.info['name'],create_time=p.info['create_time'],method='terminate_non_document_utility')
            try:
                current=psutil.Process(p.pid)
                if current.create_time()!=action['create_time'] or current.name()!=action['name']:raise RuntimeError('IDENTITY_CHANGED')
                current.terminate();current.wait(timeout=3);action['status']='EXITED'
            except (psutil.Error,RuntimeError) as e:action['status']=type(e).__name__
            report['actions'].append(action)
        report['actions'].append(dict(method='transient_system_file_cache_trim',**trim_file_cache()))
        time.sleep(3)
    report['after']=snapshot()
    report['available_delta_mib']=(report['after']['memory']['available']-report['before']['memory']['available'])/2**20
    report['limitations']='RSS, private commit, OS cache and physical availability are distinct. Host delta includes other running tasks. No research process termination, global working-set purge, service disablement or pagefile change.'
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
