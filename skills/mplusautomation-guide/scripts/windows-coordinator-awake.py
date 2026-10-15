"""临时覆盖协调器全生命周期的空闲保护；不改电源方案，不阻止用户合盖/主动睡眠。"""
import argparse, ctypes, datetime, json, os, time
from pathlib import Path
import psutil

def same_owner(pid,created):
    try:
        p=psutil.Process(pid)
        return p.is_running() and abs(p.create_time()-created)<.01
    except (psutil.NoSuchProcess,psutil.AccessDenied):
        return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--owner-pid',type=int,required=True)
    ap.add_argument('--owner-created',type=float,required=True)
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--max-seconds',type=int,default=7200)
    a=ap.parse_args()
    if os.name!='nt': raise RuntimeError('Windows runtime required')
    if a.max_seconds<=0 or a.max_seconds>14400: raise ValueError('Bounded1..14400 second lifetime required')
    if not same_owner(a.owner_pid,a.owner_created): raise RuntimeError('Owner identity not live; no power request')
    fn=ctypes.windll.kernel32.SetThreadExecutionState
    fn.argtypes=[ctypes.c_uint];fn.restype=ctypes.c_uint
    start=time.monotonic();previous=fn(0x80000003)
    if not previous: raise ctypes.WinError()
    def receipt(status,**extra):
        d={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':status,'guard_pid':os.getpid(),'guard_created':psutil.Process().create_time(),'owner_pid':a.owner_pid,'owner_created':a.owner_created,'flags':'ES_CONTINUOUS|ES_SYSTEM_REQUIRED|ES_DISPLAY_REQUIRED','elapsed_seconds':time.monotonic()-start,'max_seconds':a.max_seconds,**extra}
        a.receipt.parent.mkdir(parents=True,exist_ok=True)
        tmp=a.receipt.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2),encoding='utf-8');os.replace(tmp,a.receipt)
    try:
        receipt('ACTIVE',previous_state=previous)
        while same_owner(a.owner_pid,a.owner_created) and time.monotonic()-start<a.max_seconds:
            time.sleep(10)
            receipt('ACTIVE')
    finally:
        cleared=fn(0x80000000)
        receipt('RELEASED',clear_return=cleared,owner_still_alive=same_owner(a.owner_pid,a.owner_created))

if __name__=='__main__':main()
