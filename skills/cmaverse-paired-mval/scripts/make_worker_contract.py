#!/usr/bin/env python3
"""Generate a clauder-rstudio-workbench fan-out task.yaml for a CMAverse
paired-mval run: one worker per mediator, env-driven, writing the three-file
contract (state/manifest/validation) the fan-out harness polls.

The emitted contract is consumed by:
    clauder-workbench fanout-plan  --contract task.yaml
    clauder-workbench fanout-run   --contract task.yaml --max-parallel N
    clauder-workbench merge-gate   --contract task.yaml

No credentials are ever written. The optional upload step is controlled by an
env flag only; account details must come from the environment at run time.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Environment-variable prefix used by the reference worker. Override with
# --env-prefix when porting to another project/script version.
DEFAULT_PREFIX = "NEW47"


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker-file", required=True,
                   help="Path to the paired-mval R worker (single mediator).")
    p.add_argument("--output-root", required=True,
                   help="Base output dir; workers write under <root>/<run-id>/max_parallel_<N>/<mediator>/.")
    p.add_argument("--run-id", required=True, help="Run identifier (folder name).")
    p.add_argument("--max-parallel", type=int, default=1,
                   help="Concurrency level recorded in the worker env and path.")
    p.add_argument("--mediators", required=True,
                   help="Comma-separated mediator ids (one worker each).")
    p.add_argument("--groups", required=True, help="Comma-separated group ids.")
    p.add_argument("--nboot", type=int, default=10)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--upload-enabled", choices=["true", "false"], default="false")
    p.add_argument("--env-prefix", default=DEFAULT_PREFIX,
                   help=f"Env var prefix the worker reads (default {DEFAULT_PREFIX}).")
    p.add_argument("--session", default=None,
                   help="Optional RStudio session name to bind each worker to.")
    p.add_argument("--no-require-native-smoke", action="store_true",
                   help="Do not require a clauder-workbench native-smoke parent evidence before fan-out gates. "
                        "Use only for diagnostic MCP-stdio smoke runs.")
    p.add_argument("--out", default="task.yaml", help="Output contract path.")
    p.add_argument("--format", choices=["yaml", "json"], default="yaml")
    return p.parse_args(argv)


def split_csv(value):
    return [x.strip() for x in value.split(",") if x.strip()]


def build_contract(args):
    mediators = split_csv(args.mediators)
    groups = split_csv(args.groups)
    if not mediators:
        raise SystemExit("--mediators is empty")
    if not groups:
        raise SystemExit("--groups is empty")

    worker_file = str(Path(args.worker_file).resolve()).replace("\\", "/")
    prefix = args.env_prefix
    output_root = str(Path(args.output_root).resolve()).replace("\\", "/")
    # output_root for the fan-out contract is the level dir; worker paths are
    # relative to it: <mediator>/state_<mediator>.json etc. Absolute paths keep
    # the R worker (cwd-relative) and merge-gate (contract-relative) in sync.
    level_dir = f"{output_root}/{args.run_id}/max_parallel_{args.max_parallel}"

    workers = []
    for m in mediators:
        env = {
            f"{prefix}_MEDIATOR": m,
            f"{prefix}_NBOOT": str(args.nboot),
            f"{prefix}_SEED": str(args.seed),
            f"{prefix}_GROUPS": ",".join(groups),
            f"{prefix}_RUN_ID": args.run_id,
            f"{prefix}_MAX_PARALLEL": str(args.max_parallel),
            f"{prefix}_OUTPUT_ROOT": output_root,
            f"{prefix}_UPLOAD_ENABLED": args.upload_enabled,
        }
        worker = {
            "id": m,
            "code_file": worker_file,
            "env": env,
            "expected_state": f"{m}/state_{m}.json",
            "expected_manifest": f"{m}/manifest_{m}.csv",
            "expected_validation": f"{m}/validation_{m}.csv",
        }
        if args.session:
            worker["session"] = args.session
        workers.append(worker)

    expected_validation_rows = len(mediators) * len(groups)
    contract = {
        "task_key": f"cmaverse_paired_mval_{args.run_id}",
        "max_parallel": args.max_parallel,
        "requires_native_smoke": not args.no_require_native_smoke,
        "native_smoke": {
            "max_age_min": 60,
        },
        "artifacts": {
            "output_root": level_dir,
            "max_age_h": 24,
        },
        "meta": {
            "nboot": args.nboot,
            "groups": ",".join(groups),
            "expected_validation_rows": expected_validation_rows,
        },
        "workers": workers,
    }
    return contract


def to_yaml(obj, indent=0):
    """Minimal YAML emitter matching the fan-out minimal parser's accepted
    subset (scalars, nested maps, list-of-dict, env map). Avoids block scalars,
    anchors, and flow collections."""
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                lines.append(f"{pad}{k}:")
                lines.extend(to_yaml(v, indent + 1))
            elif isinstance(v, list):
                if v and isinstance(v[0], dict):
                    lines.append(f"{pad}{k}:")
                    for item in v:
                        item_lines = to_yaml(item, indent + 2)
                        # turn first line into a "- " list entry
                        first = item_lines[0].lstrip()
                        lines.append(f"{'  ' * (indent + 1)}- {first}")
                        lines.extend(item_lines[1:])
                else:
                    lines.append(f"{pad}{k}: [{', '.join(_scalar(x) for x in v)}]")
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
    return lines


def _scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # quote strings that could be misread
    if s == "" or any(c in s for c in ":#") or s.strip() != s:
        return json.dumps(s)
    return s


def main(argv=None):
    args = parse_args(argv)
    contract = build_contract(args)
    out_path = Path(args.out)
    if args.format == "json":
        out_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    else:
        out_path.write_text("\n".join(to_yaml(contract)) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({len(contract['workers'])} workers, "
          f"expected {contract['meta']['expected_validation_rows']} validation rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
