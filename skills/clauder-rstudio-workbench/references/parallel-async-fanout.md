---
name: parallel-async-fanout
description: One RStudio session, N child R workers via ClaudeR execute_r_async, file-poll to completion, and a self-merging gate — the high-leverage way to run long, embarrassingly-parallel R jobs.
---

# Parallel Async Fan-out

> One RStudio session drives N child R worker processes at once and merges the
> results autonomously. This is ClaudeR's highest-leverage capability: a single
> agent can fan out (e.g.) 7 bootstrap replicates / mediators / models in
> parallel, poll durable files for progress, and gate the merge — instead of
> running them one at a time and blocking the session.

This reference describes the executable fan-out harness commands. Markdown is
advisory; the harness exit codes and JSON evidence are the real gate.

## When to use

- The work decomposes into independent units that each run for minutes (bootstrap
  resamples, per-mediator decompositions, per-model fits, simulation seeds).
- Each unit can write its own durable outputs to a shared `output_root`.
- You want the orchestration (submit, poll, timeout, merge) to be reproducible and
  evidence-gated rather than hand-driven.

If the units share mutable state or must run sequentially, do **not** fan out.

## Transport evidence boundary (read this first)

Fan-out can be driven two ways, and they carry different proof:

| Mode | Who submits | Evidence label | Command path |
|---|---|---|---|
| `mcp-stdio` | the harness itself, via an independent Python MCP stdio client | `MCP_STDIO_OK` | `fanout-run` |
| `native-wrapper` | the agent, via its own `mcp__r_studio__` wrapper | native wrapper evidence + `async-guard register-job` | `fanout-plan` → agent submits → `fanout-poll` / `merge-gate` |

**`fanout-run` always labels its evidence `MCP_STDIO_OK`.** It must never claim it
used the agent's native wrapper. If you pass `--transport native-wrapper` to
`fanout-run` it BLOCKs and tells you to use the plan/poll path instead. This
prevents an agent from laundering a Python-stdio submission into a "native MCP"
completion claim.

## The worker three-file contract

Every worker must write three durable artifacts into `output_root`:

- `state_<id>.json` — JSON with a `stage`/`status` field reaching `complete`
  (also accepts `completed`/`done`/`success`/`pass`, or `complete: true`).
- `manifest_<id>.csv` — what the worker produced (≥1 data row).
- `validation_<id>.csv` — the worker's self-checks (≥1 data row).

A worker counts as **done** only when the state says complete **and** both CSVs
exist **and** (during `fanout-run`) the files are *fresh* — written after this run
started. Stale outputs from a previous run never count by default; pass
`--reuse-existing` to opt into resume semantics, or set `artifacts.max_age_h` in
the contract so `merge-gate` rejects old outputs.

> Write artifacts atomically (temp file + rename) so the poller never reads a
> half-written manifest/validation.

During `fanout-run`, the harness also polls `get_async_result` with each
worker's original `job_id` and records the replies in `progress_log`. After the
file gate completes it collects each result with the same id into
`final_collect_log`; it never resubmits merely because a job is still running.

## Contract (`task.yaml`)

```yaml
task_key: cmaverse_msat_decomp        # stable id for this fan-out
transport: mcp-stdio                  # informational default
session_name: default2                # connect_session target before submit
poll_interval_sec: 30
job_timeout_min: 180
max_parallel: 3                        # optional; omit to get planning advice
artifacts:
  output_root: C:/runs/2026-05-30     # absolute, or relative to this file
  max_age_h: 24                        # optional: merge-gate rejects older outputs
resource_gate:
  memory_threshold: 85
workers:
  - id: msat_c12_2
    code_file: C:/runs/workers/submitted_msat_c12_2.R
    env:                               # baked into the submit wrapper as Sys.setenv
      NEW47_MEDIATOR: msat_c12_2
    expected_state: state_msat_c12_2.json        # relative to output_root
    expected_manifest: manifest_msat_c12_2.csv
    expected_validation: validation_msat_c12_2.csv
  - id: msat_c12_3
    code_file: C:/runs/workers/submitted_msat_c12_3.R
    expected_state: state_msat_c12_3.json
    expected_manifest: manifest_msat_c12_3.csv
    expected_validation: validation_msat_c12_3.csv
```

YAML is parsed with PyYAML when available; otherwise a built-in minimal parser
handles this exact nested shape (scalars, nested maps, list-of-dict workers,
`env` maps). The minimal parser **fails fast** on block scalars (`code: |`),
anchors/aliases, and flow collections — install PyYAML (`pip install '.[fanout]'`)
if your contract needs those. JSON contracts (`task.json`) are also accepted.

## Commands

```powershell
# 1. Validate the contract and get parallelism advice + per-worker submit code
.\harness\run.ps1 fanout-plan --contract task.yaml

# 2a. mcp-stdio mode: harness submits all workers and polls to completion
.\harness\run.ps1 fanout-run --contract task.yaml --max-parallel 3 `
    --first-artifact-timeout-min 10 --job-timeout-min 180

#     dry-run validates + plans without submitting anything
.\harness\run.ps1 fanout-run --contract task.yaml --dry-run

#     resume a partially-finished run (skip already-complete workers)
.\harness\run.ps1 fanout-run --contract task.yaml --reuse-existing

# 2b. native-wrapper mode: first prove the current agent-native tool layer,
#     then submit each worker via mcp__r_studio__, record the real job_id, and poll/gate:
.\harness\run.ps1 native-smoke start --task-key cmaverse_msat_decomp --session-name default --agent codex --require-raw-file
# agent runs real native list_sessions / execute_r / execute_r_async / get_async_result
# and records each with native-smoke record plus --raw-file
.\harness\run.ps1 native-smoke complete --task-key cmaverse_msat_decomp
.\harness\run.ps1 async-guard register-job --task-key cmaverse_msat_decomp:msat_c12_2 --job-id <real_job_id>
.\harness\run.ps1 fanout-poll --contract task.yaml --parent-evidence <native_smoke_PASS.json>

# 3. Merge gate: passes only when ALL workers are complete with manifest+validation
.\harness\run.ps1 merge-gate --contract task.yaml --parent-evidence <native_smoke_PASS.json>
```

### Exit codes

- `fanout-plan`: `0 PASS` (valid) / `5 CONTRACT_FAILED` (missing fields).
- `fanout-run`: `0 PASS` (all done) / `3 BLOCK` (a worker failed/timed out, or
  `native-wrapper` requested). Evidence `transport_class = MCP_STDIO_OK`.
- `fanout-poll`: `0 PASS` (all complete) / `2 WARN` (still pending).
- `merge-gate`: `0 PASS` / `5 CONTRACT_FAILED` (not all complete) / `3 BLOCK`
  (all complete but with violations such as stale outputs).

## Dynamic concurrency

`fanout-run` treats `--max-parallel` as the starting concurrency ceiling. Without
`--auto-scale`, that ceiling stays fixed for the whole run. With `--auto-scale`,
the harness samples memory, CPU, free disk, and (when configured) the durable
upload queue each poll cycle. A contract may require several consecutive healthy
samples before concurrency rises by exactly one. Omitted v0.4.4 fields retain
the pre-v0.4.4 memory-only behavior and one-sample scale-up.

When any configured hold threshold is reached, `fanout-run` stops launching new
workers and lets existing workers drain; it never kills an already-running job
just to reduce concurrency. Each decision and the observed memory/CPU/disk/
backlog values are written to `scale_log` in the run result/evidence.

For the Mac CMAverse chain, the frozen policy is: start at 1, cap at 3, sample
every 30 seconds, and require five consecutive samples with memory below 70%,
CPU below 75%, disk above 200 GB, and upload backlog below 2 before adding one
slot. Memory at/above 80%, CPU at/above 90%, disk below 150 GB, or backlog at/
above 2 holds new admissions. These are admission rules; hard safety cancellation
remains the monitor's separate responsibility.

This auto-scaling path belongs to `fanout-run`'s Python MCP stdio mode. The
agent-native wrapper path is still explicit: plan the workers, submit through
the native tool layer, register real job ids with `async-guard`, then use
`fanout-poll` and `merge-gate`.

## Failure handling

- A submit that returns no `job_id` marks that worker failed and stops launching
  new workers (already-running workers are not auto-cancelled).
- `--first-artifact-timeout-min` fails a worker that produces no output file at
  all within the window — this catches a child R process that died silently right
  after submission, long before the much larger `--job-timeout-min`.
- `merge-gate` is the final autonomous-merge gate: it refuses to declare success
  unless every worker is complete, fresh (if `max_age_h` set), and has both CSVs.

→ Enforced by the harness commands `fanout-plan`, `fanout-run`, `fanout-poll`,
and `merge-gate`.
