"""单次已登记科研试跑：独立 Windows 监督、永久领取、原始数据留在主机。

此入口只运行合同中的一个成员，不是已有结果复现 worker，也不作完整 MI 验收。
Mac 断连不影响 Windows 子进程；本监督器若被外部杀死，保留未知记录，禁止自动重跑。
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def require(condition, message="单模型合同核验失败"):
    """python -O 不能取消运行闸门。"""
    if not condition:
        raise ValueError(message)


def run(contract_path, work, output, helpers):
    contract_path, work, output, helpers = map(lambda p: Path(p).resolve(), (contract_path, work, output, helpers))
    contract = json.loads(contract_path.read_bytes())
    require(contract["schema"] == "pp-scientific-single-pilot/1", '运行合同核验失败（run_scoped_pilot.py:27）')
    require(contract["authorization"] and contract["new_engine_calls_maximum"] == 1, '运行合同核验失败（run_scoped_pilot.py:28）')
    synthetic = contract.get("synthetic") is True
    require(synthetic or os.name == "nt", "Scientific engines run on Windows only")
    require(work != output and work not in output.parents and output not in work.parents, '运行合同核验失败（run_scoped_pilot.py:31）')
    for name, expected in contract["helper_sha256"].items():
        require(hashlib.sha256((helpers / name).read_bytes()).hexdigest() == expected, name)
    sys.path.insert(0, str(helpers))
    import durable_mplus_worker as w
    import psutil

    if synthetic:
        require(contract["synthetic_fixture"] == "NO_RESEARCH_DATA", '运行合同核验失败（run_scoped_pilot.py:39）')
    require(w.digest(Path(__file__)) == contract["runner_sha256"], '运行合同核验失败（run_scoped_pilot.py:40）')
    cap = w.number(contract["cap_seconds"], "engine cap")
    prior = w.number(contract["historical_engine_seconds"], "prior seconds", zero=True)
    require(math.isclose(contract["new_plus_historical_seconds_ceiling"], prior + cap), '运行合同核验失败（run_scoped_pilot.py:43）')
    engine = Path(contract["engine"])
    require(engine.is_absolute() and w.digest(engine) == contract["engine_sha256"], '运行合同核验失败（run_scoped_pilot.py:45）')
    inputs = {n: (Path(row["path"]), row["sha256"]) for n, row in contract["inputs"].items()}
    require(set(inputs) == {"model.inp", "data.dat"}, '运行合同核验失败（run_scoped_pilot.py:47）')
    for name, (source, expected) in inputs.items():
        require(source.is_absolute() and w.digest(source) == expected, name)
    work.mkdir(exist_ok=True)
    if output.exists():
        raise RuntimeError("Output snapshot already exists; reconcile it without rerunning")

    with w.file_lock(work / ".pilot.lock"), w.awake():
        if (work / "CLAIM.json").exists():
            raise RuntimeError("Original engine claim exists; observe its receipt/process, never resubmit")
        if not synthetic:
            observed = w.memory_state()
            observed["cpu_percent"] = psutil.cpu_percent(interval=1)
            external = []
            for process in psutil.process_iter(["pid", "name"]):
                if str(process.info.get("name", "")).lower() == engine.name.lower():
                    external.append(process.info)
            observed["mplus_processes"] = external
            w.atomic_json(work / "RESOURCE_ADMISSION.json", {"at": w.now(), **observed})
            limits = contract["resources"]
            require(not external, "Another Mplus engine is present; no new claim")
            require(observed["available_gib"] >= limits["minimum_available_gib"], '运行合同核验失败（run_scoped_pilot.py:68）')
            require(observed["commit_available_gib"] >= limits["minimum_commit_available_gib"], '运行合同核验失败（run_scoped_pilot.py:69）')
            require(observed["cpu_percent"] <= limits["max_cpu_percent"], '运行合同核验失败（run_scoped_pilot.py:70）')
        model = work / "model"
        model.mkdir(exist_ok=False)
        for name, (source, expected) in inputs.items():
            shutil.copy2(source, model / name)
            require(w.digest(model / name) == expected, '运行合同核验失败（run_scoped_pilot.py:75）')
        shutil.copy2(contract_path, work / "EXECUTION_CONTRACT.json")
        claim = {**w.process_record(), "member": contract["member"], "contract_sha256": w.digest(contract_path)}
        w.atomic_json(work / "CLAIM.json", claim, new=True)
        command = [str(engine)]
        if synthetic:
            fake = Path(contract["synthetic_script"])
            require(w.digest(fake) == contract["synthetic_script_sha256"], '运行合同核验失败（run_scoped_pilot.py:82）')
            command += [str(fake)]
        command.append("model.inp")
        proc, created, code = None, None, None
        error, cleanup_error, peak_rss = None, None, 0
        state, marker = "LAUNCH_FAILED", None
        start = time.monotonic()
        try:
            with (work / "engine.stdout.log").open("xb") as stdout, (work / "engine.stderr.log").open("xb") as stderr:
                proc = subprocess.Popen(command, cwd=model, stdin=subprocess.DEVNULL,
                                        stdout=stdout, stderr=stderr, **w.detached_args())
            created = psutil.Process(proc.pid).create_time()
            marker = {"pid": proc.pid, "created": created, "host": w.host(), "at": w.now(),
                      "engine_sha256": contract["engine_sha256"], "supervisor": claim}
            w.atomic_json(work / "ENGINE_STARTED.json", marker, new=True)
            state = "EXITED"
            with (work / "PROCESS_SAMPLES.jsonl").open("x", encoding="utf-8") as samples:
                while True:
                    elapsed = time.monotonic() - start
                    code = proc.poll()
                    if elapsed >= cap:
                        state = "TIMEOUT"
                        if code is None:
                            w.stop_owned(proc, created)
                        break
                    if code is not None:
                        break
                    row = {"at": w.now(), "elapsed_seconds": elapsed, "pid": proc.pid,
                           "out_bytes": (model / "model.out").stat().st_size if (model / "model.out").exists() else 0}
                    try:
                        process = psutil.Process(proc.pid)
                        row.update(rss=process.memory_info().rss, cpu_seconds=sum(process.cpu_times()[:2]), threads=process.num_threads())
                        peak_rss = max(peak_rss, row["rss"])
                    except psutil.NoSuchProcess:
                        continue
                    samples.write(json.dumps(row) + "\n")
                    samples.flush()
                    w.atomic_json(work / "PROGRESS.json", {"stage": "ENGINE_RUNNING", "member": contract["member"], **row})
                    time.sleep(min(2, max(0, cap - (time.monotonic() - start))))
            code = proc.wait(timeout=15)
        except BaseException as exc:
            state, error = "SUPERVISOR_ERROR", repr(exc)
            try:
                if proc is not None and proc.poll() is None and created is not None:
                    w.stop_owned(proc, created)
                    code = proc.wait(timeout=15)
            except BaseException as cleanup:
                cleanup_error = repr(cleanup)
        elapsed = time.monotonic() - start
        if proc is not None and code is None:
            code = proc.poll()
        if state == "EXITED" and elapsed > cap:
            state = "TIMEOUT"
        confirmed = proc is None or code is not None
        receipt = {"schema": "pp-scientific-pilot-engine/1", "at": w.now(), "member": contract["member"],
                   "state": state, "exit_code": code, "engine_exit_confirmed": confirmed,
                   "actual_engine_calls": int(proc is not None), "elapsed_seconds": elapsed,
                   "peak_rss_bytes": peak_rss, "cap_seconds": cap, "historical_engine_seconds": prior,
                   "observed_plus_historical_seconds": prior + elapsed,
                   "inputs": {n: h for n, (_, h) in inputs.items()}, "engine_sha256": contract["engine_sha256"],
                   "contract_sha256": w.digest(contract_path), "synthetic": synthetic,
                   "error": error, "cleanup_error": cleanup_error, "scientific_acceptance": "NOT_EVALUATED"}
        w.atomic_json(work / "ENGINE_RECEIPT.json", receipt, new=True)
        if not confirmed:
            raise RuntimeError("Engine exit remains unknown; no export, no new claim")
        for name, (_, expected) in inputs.items():
            require(w.digest(model / name) == expected, "Input changed during execution")
        output.mkdir(exist_ok=False)
        allowed = {"model.inp", "model.out", "estimates.dat", "tech3.dat"}
        for name in allowed:
            if (model / name).exists():
                shutil.copy2(model / name, output / name)
        for name in ("EXECUTION_CONTRACT.json", "CLAIM.json", "ENGINE_STARTED.json", "ENGINE_RECEIPT.json",
                     "RESOURCE_ADMISSION.json", "PROCESS_SAMPLES.jsonl", "engine.stdout.log", "engine.stderr.log"):
            if (work / name).exists():
                shutil.copy2(work / name, output / name)
        exported = {p.name: {"bytes": p.stat().st_size, "sha256": w.digest(p)} for p in output.iterdir()}
        w.atomic_json(output / "EXPORT_MANIFEST.json", {"schema": "pp-single-pilot-export/1", "files": exported,
                      "individual_inputs_exported": False, "source_work": str(work), "engine_exit_confirmed": True}, new=True)
        print(json.dumps(receipt), flush=True)
        return 0 if state == "EXITED" and code == 0 else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for argument in ("contract", "work", "output", "helpers"):
        parser.add_argument("--" + argument, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.contract, args.work, args.output, args.helpers))
