"""独立核对 APIM v2 资源基准的队列区间与原生结果。"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate(root: str) -> dict:
    base = Path(root)
    db = sqlite3.connect(base / "queue.sqlite")
    claims = {}
    finishes = {}
    for kind, at, payload in db.execute(
        "SELECT kind, at, payload FROM events WHERE kind IN ('claimed','finished') ORDER BY sequence"
    ):
        data = json.loads(payload)
        model = data["id"]
        if kind == "claimed":
            claims[model] = (parse_time(at), data["worker"])
        else:
            finishes[model] = parse_time(at)
    if set(claims) != set(finishes) or not claims:
        raise AssertionError("queue claim/finish set mismatch")
    intervals = [
        {"model_id": model, "worker": claims[model][1],
         "started": claims[model][0].isoformat(), "finished": finishes[model].isoformat(),
         "seconds": (finishes[model] - claims[model][0]).total_seconds()}
        for model in sorted(claims)
    ]
    overlap_pairs = []
    for i, left in enumerate(intervals):
        ls, le = parse_time(left["started"]), parse_time(left["finished"])
        for right in intervals[i + 1:]:
            rs, re = parse_time(right["started"]), parse_time(right["finished"])
            seconds = (min(le, re) - max(ls, rs)).total_seconds()
            if seconds > 0:
                overlap_pairs.append({"left": left["model_id"], "right": right["model_id"], "seconds": seconds})
    measurements = []
    for path in base.rglob("resource_measurement.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        measurements.append({"path": str(path), "peak_private_gib": data["peak_private_gib"],
                             "peak_rss_gib": data["peak_rss_gib"],
                             "measured_engine": data["measured_engine"], "engine_exited": data["engine_exited"]})
    if not all(x["measured_engine"] and x["engine_exited"] for x in measurements):
        raise AssertionError("unverified engine measurement")
    result = {
        "status": "PASS",
        "calls": len(intervals),
        "intervals": intervals,
        "overlap_pairs": overlap_pairs,
        "max_overlap_seconds": max((x["seconds"] for x in overlap_pairs), default=0.0),
        "resource_measurements": measurements,
        "independent_queue_evidence": True,
    }
    (base / "benchmark_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"intervals", "resource_measurements"}}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    validate(parser.parse_args().root)
