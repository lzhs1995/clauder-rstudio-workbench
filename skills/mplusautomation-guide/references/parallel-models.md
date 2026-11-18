# Parallel Models From Manuscript Tables

Compile the work graph before estimation. A source script's textual order is
provenance, not proof of a dependency. For example, ten measurement scales with
four growth shapes produce forty estimation nodes after their common data are
ready. A five-column direct-effects table can depend on five separate estimates.
A moderation table may first require factor scores, a specified cut point, and
an ID join before its interaction variants can run independently.

## Contracts and Ownership

Use stable model IDs and retain every source invocation and table row/column
mapping. Keep data preparation, estimation, transformations, and table rendering
as distinct node types. Do not infer statistical independence or change a
model's missing-data rules merely because it appears in a different table.

The included `scripts/mplus_queue.py` implements a local SQLite queue with
exclusive claims, input hashes, dependency predicates, original worker PID plus
creation time, and append-only events. Use a local unsynchronized directory;
SQLite WAL is not intended for network or cloud-synchronized workspaces.
Dependencies may require `estimation_ok` or `savedata_ok`. A failed prerequisite
blocks its consumers. A saved-data error is retained even if all replications
finished estimation.

The queue also supports an explicit `deferred` terminal state. Use it for a
no-history, non-converged, or overlong attempt that was intentionally archived
under the success-first policy. `deferred` is neither `completed` nor an
ordinary runtime `failed`: it is excluded from success counts, blocks dependent
nodes, and remains visible in the table reconciliation manifest.

An enqueue JSON contains `id`, `script`, `fingerprint`, `input`, `output`,
`input_sha256`, `input_files` (path/hash records), `dependencies`, `processors`,
`memory_gib`, `priority`, and a source `record`. Add a `savedata_contract` for
imputation output counts and expected rows. All mutable paths must be below the
queue root. Same names are insufficient for cache reuse; validate statistical
inputs, data hashes, seeds and upstream versions.

For MplusAutomation `TYPE=IMPUTATION`, the main `.dat` is a list of filenames.
The queue expands that list and hashes every member before registration. Keep
all input data in the isolated model directory. Unsupported DATA wildcards
must be expanded and reviewed explicitly; do not silently hash only the index.
Use `import-request --request <json>` to register a completed result atomically.
Never enqueue it as claimable work before importing it. Set
`reuse_identical_inputs: true` to bind a new namespace to an identical registered
input set, including a pending or running estimate; the consumer waits and copies
the validated result after that original attempt ends. This is cache reuse,
not an independent stochastic replication.

Source adapters must use logical full paths and stable call/iteration IDs. A
basename alone cannot identify models in different GMM directories. Do not
pre-evaluate every branch of an R `if` or loop. Safely split compound statements
into persistent substeps, or keep their model calls synchronous while the other
queue workers proceed. Replaying a half-executed loop with new ordinals can
duplicate estimates. Terminal failures must publish a validation file even
when Mplus never created an `.out`; downstream objects must become blocked.

Use `scripts/mplus_queue_worker.R` inside each real ClaudeR `execute_r_async`
call. Its configuration supplies `root`, `library`, `python`, `mplus`, and
`queue_script`. Submit and register workers with the parent workbench's
`async-guard`, retain their original job IDs, and poll those IDs. The queue is
disabled by default. Its CLI provides `init`, `enqueue`, `enable`, `disable`,
`status`, `claim`, `finish`, and `producers-done`; workers normally own the claim
and finish operations. It never submits a ClaudeR job itself and cannot claim
native MCP transport evidence.

CLI worker actions also publish `state_<worker>.json`,
`manifest_<worker>.csv`, and `validation_<worker>.csv` for the parent workbench's
file gate. A drained queue containing failed assigned estimates is marked
`completed_with_model_failures`, not `complete`. These artifacts do not replace
polling the original native async jobs or the manuscript comparison gate.

The worker file defines `queue_worker()` but is not a complete top-level
program. A launcher must `source()` it and then call the function with the
reviewed configuration; invoking it with `Rscript --file` alone can exit
successfully without registering a worker or claiming a task. Accept a worker
only after its registration row, heartbeat, claim record and owned Mplus child
are all observable.

## Resource Admission

Budget preparation, R workers, Mplus, and rendering together. Current working
set is not a peak estimate: on Windows inspect private/committed memory and
historical peak working set too. High memory pressure can make a small Mplus
process slow because other processes are paging. Do not stop unrelated user
applications without authorization.

The queue's initial profile is intentionally conservative for a 16 GiB,
16-logical-CPU workstation: start at one, cap at three, reserve 1.5 GiB of
physical memory, hold new claims at 90% CPU, and reserve 10 GiB disk. The sum
of declared Mplus processors must stay within twelve. Five healthy samples at
least 30 seconds apart add one slot, up to the stored cap. These are starting
values, not universal Mac/Windows requirements; calibrate the profile to the
host and representative model peaks before production use.

### Explicit autoscale modes

Select the expansion rule with `resource_policy.autoscale_mode` in the queue
root's `config.json`:

```json
{
  "resource_policy": {
    "autoscale_mode": "candidate_measured"
  }
}
```

The accepted values are exactly `candidate_measured` and `legacy_compatible`.
Omitting the field selects `candidate_measured`; `legacy_compatible` takes effect
only when explicitly configured. `null`, non-string values,
case changes, or surrounding whitespace are invalid. An APIM flag or a queue
directory name does not select a mode. Both modes adjust the local slot limit;
every eventual claim still passes its separate admission checks.

`legacy_compatible` retains the percentage and byte-headroom expansion routes.
A sample qualifies when CPU is below `cpu_resume_percent` (default 75%), disk
meets `disk_reserve_gib`, and the host memory, CPU and disk measurements are
verified. Memory qualifies when its percentage is below `memory_resume_percent`
(default 85%), or when available physical memory minus running reservations
and `scale_up_step_gib` (default 0.5 GiB) meets `reserve_gib`. If
`commit_reserve_gib` is configured, free commit minus those reservations and
the step must meet that reserve on both routes; missing commit data refuses
the sample. This byte route allows expansion despite a high memory percentage
when enough bytes remain. This mode does not require a ready model; it compares
sample timestamps with the previous sample and adds no separate age check
against the current clock. The resource provider's own validation still applies.
The legacy percentage shortcut can qualify a sample even when physical byte
headroom does not cover the reserve. It therefore does not satisfy the measured
byte-headroom expansion contract and must not be used to establish that contract
for a new batch.

`candidate_measured` examines the next dependency-ready, non-reused, in-scope
model in the same dispatch order as `claim`. It calls `admission_reason` for
that candidate at the prospective slot limit, accounting for running budgets,
physical memory, configured commit reserve, CPU, declared processors, disk and
execution-class limits. CPU must also be below `cpu_resume_percent`. An empty
ready set cannot produce a healthy sample. Sample age must be between zero
and `windows_profile_max_age_sec` (default 300 seconds), inclusive: samples
older than that limit or from any future time reset `healthy`
without advancing `last_sample`. Other failed checks reset `healthy` and keep
the existing limit. Samples less than 30 seconds after the prior accepted
sample do not accumulate health. Memory percentage is diagnostic for this mode;
it does not use the legacy percentage shortcut or `scale_up_step_gib`.

Both modes record their actual `autoscale_mode` in `resources` events. A failed
expansion check does not stop running models. `candidate_measured` names the
queue's expansion rule; it does not select the separate strict host-reservation
API described below.

### Behavior migration

The default expansion rule has changed from the former main implementation to
`candidate_measured`. With no mode field, new Queue objects now require a ready
candidate and physical byte headroom; configured commit headroom is checked
separately. Empty ready sets, insufficient available bytes, and samples outside
the age window above do not grow the limit. This matches the measured expansion
rule already used by the managed workflow; it does not change model inputs,
existing limits or the APIM calibration requirement.

To preserve the old expansion behavior deliberately, set this explicit option
in the queue's `config.json` before its original owner opens the queue:

```json
{
  "resource_policy": {
    "autoscale_mode": "legacy_compatible"
  }
}
```

This compatibility option keeps the old percentage shortcut and is not evidence
that the measured byte-headroom expansion contract has been met. Ordinary claims
still perform their own byte checks in either mode; an expansion sample is not
permission to launch a model.

Installing the new main package does not change a running queue's configuration
or reload its already-loaded Python/R code. A running object retains its loaded
implementation and selected mode. Reconcile the original owner's active work,
configuration and code-loading boundary before adopting the new default; retain
original task/job identities and do not replay a running estimate. On reopening,
a configuration with no mode field selects `candidate_measured`, while an
explicit legacy choice remains legacy. Health-history registration and the
same-database old-object guard below apply only in implementations that contain
them; they cannot impose those rules on an older client.

### Initialization and health history

A new ordinary queue may declare `parallel_cap` (an integer from one to
`processor_budget`) and `initial_parallel_limit` (one to that cap) in
`config.json` before its first database initialization. Omitted values keep
the defaults of three and one. Existing ordinary queues retain their stored
limits, even if their event table is empty; changing these declarations does
not migrate the queue's limit or cap. APIM v2 retains its separate cap of one
or two and requires calibration when declaring an initial limit above one.
A declared slot count does not reserve host capacity.

The first-settings check, default values, configuration validation, optional
`historical_success_policy` validation and autoscale-mode registration commit
in one SQLite write transaction. A failed first initialization leaves settings
empty, so fixing the configuration or historical manifest and retrying still
applies the declared starting limit and cap. Concurrent initializers wait for
that transaction and cannot return partially initialized settings. A failed
validation of an existing queue rolls back the attempted mode change too.

The database stores `settings.autoscale_mode`. First registration on an older
database, or switching between modes, clears only the accumulated `healthy`
count as part of mode registration. That mode-registration step preserves
`limit`, `cap`, `last_sample`, the resource snapshot and task rows; the existing
APIM initialization rules still apply independently. Reopening with the same
mode preserves its healthy count. A previous mode's four healthy samples
cannot be carried into the other mode to add a slot after just one sample.

Before a tick writes, it acquires the queue's SQLite write lock and checks
that the database mode still matches its Queue object's mode. If another
instance registered a different mode, the old object's tick fails without
changing settings or events. The original owner must reopen its Queue object
with the intended configuration before ticking again. This check does not
upgrade already-loaded older implementations or provide mode coordination for
clients that do not implement it. It does not change claim semantics or stop
an active estimate.

### Claims and shared host reservations

Set numerical thresholds under `resource_policy`: `reserve_gib`,
`commit_reserve_gib`, `cpu_hold_percent`, `cpu_resume_percent`,
`disk_reserve_gib`, and `processor_budget`. Ordinary claim admission uses byte
headroom; `memory_hold_percent` is not a claim gate. `memory_resume_percent`
and `scale_up_step_gib` affect only `legacy_compatible` expansion. When a commit
reserve is configured, missing commit data refuses admission. Admission charges
running tasks' declared memory reservations plus the next task's budget. This
conservative rule covers simultaneous claims before Mplus has allocated memory.
Observed-private-memory credit remains opt-in; private/commit bytes are not
proof of physical resident bytes.

Expansion does not reserve host capacity. Participating queues must share the
existing `host_reservation_path`; ordinary `Queue.claim` then calls the legacy
`HostReservations.acquire()` inside that registry's SQLite write transaction.
It counts other participating queues and can refuse a claim after a successful
expansion sample. Without that configured registry, ordinary claims use their
local queue checks. Unregistered tasks and input measurements taken before the
registry transaction remain limitations of the legacy host protocol. A tick
result is not proof of whole-host capacity or real process overlap.

### Separate measured host API

`scripts/apim_v2_io.py` also exposes
`HostReservations.configure_measured_policy()` and
`HostReservations.acquire_measured()`, backed by `scripts/host_measured.py` in
the same reservation database. The host owner explicitly registers a policy
with separate physical-memory, commit, processor and per-volume growth budgets,
including reserves and unmanaged-workload growth. Registration requires an
explicit verified-growth declaration and evidence hash; the API does not
independently verify the evidence represented by that declaration.

The measured acquire path takes the database write lock before its default
Windows native sampler runs, then checks independent physical and commit
headroom, processor capacity and output-volume growth. It accounts for existing
reservations, including legacy rows; an unmapped legacy output budget or an
unverified owner blocks admission. Unknown or orphaned reservations are kept,
without automatic release. A duplicate reservation is not permission to launch
another process, and the result does not itself authorize execution. Synthetic
samplers and owner probes are test seams, not JSON or ordinary CLI inputs.

Ordinary `Queue.claim` still calls `acquire()`, not `acquire_measured()`. These
APIs are not connected to the PowerShell worker pools. Installing the files,
selecting `candidate_measured`, or passing synthetic tests does not enable
strict host admission for either path, control unrelated applications, or
establish native Windows or licensed-model acceptance.

When the queue runs under WSL on a Windows host, configure
`windows_memory_profile` in `config.json` to a fresh JSON snapshot produced by
the Windows-side profiler. The queue then uses Windows free physical memory and
commit data, and rejects a claim with `host_memory_unverified` when the profile
is missing or older than `windows_profile_max_age_sec` (default 300 seconds).
WSL's own `psutil.virtual_memory()` view is never accepted as a Windows
admission signal. This prevents an apparently healthy WSL VM from launching an
Mplus job while the Windows host is already paging. A profile is evidence for
admission only; it does not terminate or reprioritize unrelated processes.

Optional task `dispatch_priority` overrides `priority`; `execution_class` and
`resource_policy.max_running_by_class` limit how many members of a costly class
can run simultaneously. Dependencies and resource budgets are checked after
ordering. Diagnose ready-but-not-admissible work with
[performance-diagnosis.md](performance-diagnosis.md) before increasing limits.

For a producer that blocks inside a compound R statement, configure
`producer_state_files` so each queue claim refreshes the pending prerequisite
priority from small state JSON. Include both ordinary and compound waits.
This releases source preparation sooner without replaying a half-finished
statement or preempting active estimates. It does not overcome a resource hold.
The monitor should report the actual admission reason, including
`predicted_memory`, even when measured system use is below its hold percentage.

For the native-wrapper path, a lightweight R standby can be submitted once and
poll resources before loading the analysis packages. Count its base R overhead
in the host budget. Require sustained spare memory and CPU, then call the same
queue worker in that process; retain the original native job ID. Exit without
claiming an estimate if the queue drains first. This permits a third estimator
to join later without relabeling an external stdio submission as a native call.

Do not multiply multi-worker and `PROCESSORS` parallelism blindly. Preserve
model settings during replication; changing processor settings belongs in an
explicit computational variant with numerical comparison. Do not split the
imputation count to manufacture independent jobs; Mplus must still perform the
specified combined analysis.

When a limit is reached, hold new admissions and let running estimates drain.
Do not reclaim an unknown running task or use `killOnFail=TRUE`; on Windows its
cleanup may kill other Mplus processes. A replacement worker must not adopt a
still-running task. Investigate original PID ownership and output first.

### Windows paging telemetry

Collect Windows `Pages Input/sec`, `Pages Output/sec`, disk latency and model
CPU together. Page input includes mapped-file reads; a nonzero rate, or an
uncalibrated threshold of 100 pages/sec, does not prove thrashing and must not
become an extra permanent admission gate. Keep raw values and mark missing
counters unknown. Compare progress/elapsed time for equivalent model settings
before attributing slow estimates to paging. Physical and commit headroom still
need separate budgets. See Microsoft's [memory guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-server/performance/ram-virtual-memory-pagefile-management).

A dead worker's `running` row can retain its declared memory reservation and
make the queue appear resource-starved. Prove that the worker PID and every
child are gone, back up SQLite with its WAL/SHM context, then use the queue's
own `finish` or revalidation path so the output parser decides whether the
attempt is failed or valid. Verify `integrity_check` afterward; do not edit
`running` rows directly or mark an estimate successful by hand.

## Recovery and Evidence

For a legacy sequential driver, complete and preserve the active estimate before
transferring ownership. Check the worker's PID and creation time, pause it only
at a verified boundary with no active Mplus descendants, and archive the old
outputs before activating a replacement. Do not edit a loaded function and
assume the running R process has adopted it.

R checkpoints must restore package attachments as well as objects and random
state. On Windows, pass the executable to `system2()` without pre-quoting it;
quote its arguments individually. Write long-job logs to durable files to avoid
blocking older ClaudeR builds on unconsumed output pipes.

Use a file for `system2(stdout=...)` when reading JSON replies. R's captured
console output can split long physical lines, inserting a newline inside a JSON
string. The helper reads the response file directly and keeps stderr separate;
its CLI also emits indented JSON for already-loaded callers. Keep this repair
at the I/O boundary rather than altering model filenames or data.

Show queue counts, reused estimates, active models, source tables, job IDs,
Mplus PIDs, CPU deltas, memory, and resource/dependency waiting reasons. A quiet
buffered `.out` is not enough to declare a model hung while CPU continues moving.
Desktop monitoring is distinct from automatic chat notifications.

Validate real overlapping process lifetimes and advancing CPU counters. Compare
the same model/data settings serially and concurrently, checking numeric
parameters rather than full R objects whose filename attributes differ. Report
wall time and resource peaks; process overlap alone does not prove speedup.
Mark table output provisional if required estimates, saved files or diagnostics
remain unresolved. Merge by explicit table keys, never completion order.

Local fixtures exercise queue ownership, resource holds, changed inputs,
imputation contracts, and simultaneous claims. Licensed Mplus integration must
be run separately; fixture CI does not establish Mac/Windows licensed-runtime
parity or manuscript replication success.
