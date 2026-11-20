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

Poll text is diagnostic output, not a process-status protocol. A successful R
program may print `Async job error:`, `Job ... not found`, `unknown`, or JSON
that resembles a status report. None of those strings declares a terminal job
or overrides a separately verified status. Conversely, a successful MCP call
does not by itself prove that its background R process has exited.

The resource-bound poller accepts terminal status only when it is explicitly
bound to the original `job_id`. It first checks the MCP response's
`structuredContent`. For a legacy ClaudeR bridge that returns only text, it
performs a short, read-only `execute_r` check in the same MCP connection and
selected RStudio session. This check reads the existing ClaudeR namespace entry
`.claude_bg_jobs[[job_id]]$final`; it does not collect the job again, kill a
process, assign outputs, or change the cache. A random marker separates this
probe's JSON from ordinary output. The cached `metadata.job_id` must match,
`status` must be `complete`, and `success` must be an explicit boolean. ClaudeR
writes that final cache after its background process is no longer alive;
`success: true` confirms successful termination and `success: false` confirms
failed termination. The harness normalizes them to `completed` and `error`.
An explicit structured `cancelled` status is also terminal; a deleted cache
entry after cancellation is not proof of cancellation.

Missing or mismatched identity, missing final cache, unsupported cache shape,
and polling without independently verified terminal evidence leave the process
status unknown. Communication-error or not-found text alone cannot release the
reservation. The original job ID and its full resource reservation remain active,
and later polls reuse that ID. A verified successful terminal status still
requires all three durable artifacts before the worker counts as done. A
verified terminal error or cancellation releases its reservation and marks the
worker failed. No stdout prefix, arbitrary nonempty reply, timeout, or complete
artifact set alone releases a reservation when process exit is unconfirmed.

## Contract (`task.yaml`)

```yaml
task_key: cmaverse_msat_decomp        # stable id for this fan-out
transport: mcp-stdio                  # informational default
session_name: default2                # connect_session target before submit
poll_interval_sec: 30
job_timeout_min: 180
max_parallel: 3                        # optional; omit to get planning advice
artifacts:
  output_root: C:/runs/fanout          # directory readable by the Python poller
  max_age_h: 24                        # optional: merge-gate rejects older outputs
resource_gate:
  worker_mem_gib: 1                    # physical memory reserved per worker
  worker_commit_gib: 1                 # commit headroom reserved per worker
  worker_processors: 1                 # logical processors/threads per worker
  worker_output_gib: 1                 # output space reserved per worker
  reserve_mem_gib: 1
  reserve_commit_gib: 1
  reserve_processors: 1
  reserve_output_gib: 2
  sample_max_age_sec: 60
  worker_output_root: C:/runs/fanout  # absolute path on the actual R worker host
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

All byte budgets above use GiB (`2^30` bytes). The shown values are the defaults:
each worker reserves 1 GiB physical memory, 1 GiB commit, one logical processor,
and 1 GiB output space; the host retains 1 GiB physical memory, 1 GiB commit,
one logical processor, and 2 GiB output space. Choose larger worker budgets for
larger jobs. Worker budgets must be positive finite numbers, processor budgets
must be integers, and reserves must be nonnegative. Booleans, NaN and infinity
are not budgets. Defaults are applied by the runtime; schema defaults describe
them and do not themselves modify a JSON document.

`session_name` selects one RStudio session for the whole batch. A CLI
`--session-name` overrides it consistently for sampling and submission; the
legacy per-worker `session` field does not route workers to other sessions.
If present, it must match the effective batch session; a mismatch holds admission.

## Commands

```powershell
# 1. Validate the contract and get parallelism advice + per-worker submit code
.\harness\run.ps1 fanout-plan --contract task.yaml

# 2a. mcp-stdio mode: harness submits all workers and polls to completion
.\harness\run.ps1 fanout-run --contract task.yaml --max-parallel 3 `
    --first-artifact-timeout-min 10 --job-timeout-min 180

#     dry-run validates + samples worker resources without submitting jobs
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

- `fanout-plan`: `0 PASS` (valid and admitted) / `3 BLOCK` (resource HOLD)
  / `5 CONTRACT_FAILED` (invalid contract). `--no-advise` performs structure-only
  validation without sampling and grants no resource permission.
- `fanout-run`: `0 PASS` (all done) / `3 BLOCK` (a worker failed/timed out, or
  resource admission holds, or `native-wrapper` requested). Evidence
  `transport_class = MCP_STDIO_OK`. A dry run samples resources without submitting
  jobs and also returns BLOCK on resource HOLD.
- `fanout-poll`: `0 PASS` (all complete) / `2 WARN` (still pending).
- `merge-gate`: `0 PASS` / `5 CONTRACT_FAILED` (not all complete) / `3 BLOCK`
  (all complete but with violations such as stale outputs).

Every `fanout-run` poll atomically writes
`<output_root>/fanout_runtime_status.json` and emits a flushed
`FANOUT_PROGRESS` line containing the original job ids. Use
`--progress-file <absolute.json>` to select another durable status path.

When a task-local native wrapper is unavailable because its tool registry was
frozen at task creation, `--defer-native-smoke` permits an explicitly authorized
MCP stdio computation with a Windows or macOS orchestrator, subject to the
worker-host resource checks below. It does not bypass resource HOLD. The command returns WARN even
when the scientific workers pass, records `NATIVE-SMOKE-DEFERRED`, and leaves
strict completion blocked until fresh four-step `NATIVE_MCP_OK` evidence is
attached. The default remains strict and blocks before submission.

## Dynamic concurrency

Plan and run use the actual worker host's available physical memory, commit
headroom, logical processor budget and output-volume free bytes. Each dimension
has its own measured value, reservation and reason. Memory percentage remains
diagnostic: even at 90% used, sufficient byte headroom can admit several workers.
Unknown, malformed, stale or unbound worker-host samples hold new admission at
zero; they do not mean that the machine can run only one worker.

For each dimension, the remaining budget is the measured availability minus
the configured host reserve minus the **full declared budget of every running
worker in this batch**. The next worker must fit all four dimensions. The
physical and commit calculations conservatively subtract full reservations
without crediting current resident use; output reservations similarly allow
for later growth. Logical processor capacity is the observed logical count
less its reserve and running-worker thread reservations. These are batch-local
reservations: other queues or agents have no shared lease with this scheduler.
Do not describe this as host-wide or cross-queue reservation.

Admission is separate from the target concurrency: a hold permits **zero new
submissions**, including when no worker is running. The target slot count is
retained so fresh safe readings can refill it. Existing jobs retain their
original IDs and continue to be polled during a hold; transport errors do not
resubmit them. The byte and configured backlog gates below still apply when
another required resource dimension is unknown.

Without an explicit `max_parallel`, `fanout-plan` recommends the minimum of
worker count, three and the number of additional workers that fit. An explicit
`max_parallel` remains visible as `recommended_max_parallel`; the separate
`admitted_parallel` reports the requested count bounded by current capacity.
A structurally valid contract or a requested count is not resource permission.
The plan preserves `ok` for structural validity and exposes `admission_ok`
separately. When admission is on HOLD, `admitted_parallel` is zero and the CLI
returns BLOCK; submit no new worker even if the requested count is positive.

`fanout-run` retains the existing concurrency controls: without `--auto-scale`,
`--max-parallel` is a fixed ceiling; with it, the value is the starting ceiling,
and `--max-parallel-cap` limits growth. Every new submission must pass the four
resource checks, including submissions below an explicit ceiling. A contract
may require several consecutive healthy samples before raising the ceiling by
one. Admission holds stop new launches and let existing workers drain; they
never kill a running job merely to lower concurrency. Decisions and sample
details are retained in `scale_log` and the per-submission `admission_log` in the run evidence.

The legacy `memory_threshold`, `memory_scale_up_percent` and
`memory_hold_percent` keys are accepted as diagnostic values only. They no
longer impose a percentage gate on fanout. Explicit CPU percentage thresholds
are also retained as diagnostic values only; the logical processor/thread
budget is enforced. The worker probe collects the four resource dimensions and
identity without extra CPU-usage sampling. A supplied diagnostic percentage may
be displayed, but missing diagnostics do not replace a valid byte sample.
The legacy `min_disk_free_gb_scale_up` and `min_disk_free_gb_hold` thresholds
remain additional checks in GiB despite their `gb` names, using bytes from the
worker's output volume. Configured upload-backlog checks remain separate.

An existing task with a frozen percentage policy is not silently migrated by
this change. Preserve its runtime and accepted contract, or explicitly revise
the contract before starting a new batch. The standalone `resource-gate`
command and monitor policies are separate interfaces; their percentage rules
are not changed by this fanout admission update.

For the existing Mac CMAverse chain, preserve its accepted runtime and frozen
contract: start at 1, cap at 3, sample every 30 seconds, and require five
consecutive samples with memory below 70%, CPU below 75%, disk above 200 GB,
and upload backlog below 2 before adding one slot. Memory at/above 80%, CPU
at/above 90%, disk below 150 GB, or backlog at/above 2 holds new admissions.
These are that existing task's admission rules, not the current fanout byte
policy or permission to migrate the task. Hard safety cancellation remains the
monitor's separate responsibility. A new batch under the current harness must
satisfy the worker-host byte checks, including the macOS commit limitation below.

### Bind sampling to the worker host

The Python orchestrator and the RStudio worker host may differ. Local Python
`psutil`, CPU count or disk usage cannot establish resources on another host.
The harness obtains its sample through `execute_r` in the selected RStudio
session, records the actual host and R PID, and checks that binding again in
the same MCP connection used for submission. A changed identity or unavailable
host sample holds new work. No local-host fallback replaces an unknown worker
host. Samples expire after `resource_gate.sample_max_age_sec` (60 seconds by
default). The target probe is a short synchronous read capped by a 10-second
MCP timeout; its Windows commit subprocess has a 3-second timeout. A Python
timeout causes HOLD and does not prove a remote read has been cancelled.
This update has injected-probe test coverage; it does not establish
live Windows qualification.

The current probe has no commit-headroom source for a **macOS worker host**.
Its commit availability remains unknown, so plan and run keep admission on HOLD
at zero until a supported, valid target sample exists. A Mac acting as the
Python orchestrator for a Windows or Linux RStudio target is a different case:
admission uses that target's resources, not the Mac's. Neither
`--defer-native-smoke` nor an explicit `max_parallel` grants a slot when a
resource dimension is unknown. `fanout-plan --no-advise` only checks contract
structure; it does not sample resources, lift HOLD, or authorize submission.

The output volume is sampled on the R host. `resource_gate.worker_output_root`
is an absolute path there. If omitted, the unchanged `artifacts.output_root`
string is resolved by R on that host, not by Python for resource admission.
For cross-host polling, `artifacts.output_root` must be a local readable mapping
of the same durable outputs and `worker_output_root` must name their actual
destination on the worker host. A missing/nonabsolute target path or a sample
for another output path holds admission. The harness does not verify a cross-host
mount mapping or transfer files; the task owner must establish that mapping. The R worker's own
driver must write to that destination, and its code/input paths must already
be available on the worker host.

For example, a Mac poller can read a mounted output directory while the
Windows worker writes to the corresponding directory on its output volume:

```yaml
artifacts:
  output_root: /Volumes/worker-results/fanout
resource_gate:
  worker_output_root: D:/worker-results/fanout
```

The two paths must refer to the same outputs; the harness does not create this
mapping. Retain the actual target's byte sample and each original job ID across
polls. A plan's sample does not grant an indefinite reservation for later runs.

This auto-scaling path belongs to `fanout-run`'s Python MCP stdio mode. The
agent-native wrapper path is still explicit: plan the workers, submit through
the native tool layer, register real job ids with `async-guard`, then use
`fanout-poll` and `merge-gate`. A resource sample from an independent stdio
connection remains that evidence class; it cannot prove agent-native wrapper
execution. The agent remains responsible for honoring the current admission
decision before its own native submissions. The merge gate is unchanged.

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
