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
16-logical-CPU workstation: start at one, cap at three, reserve 1.5 GiB, admit
below 90% predicted memory, hold at 90% CPU/memory, and reserve 10 GiB disk. Five
healthy 30-second samples below 85% memory and 75% CPU add one slot. The sum of
declared Mplus processors must stay within twelve. These are starting values,
not universal Mac/Windows requirements; calibrate the profile to the host and
representative model peaks before production use.

Override the numerical thresholds with `resource_policy` in the queue root's
`config.json`: `memory_hold_percent`, `memory_resume_percent`, `reserve_gib`,
`cpu_hold_percent`, `cpu_resume_percent`, `disk_reserve_gib`, and
`processor_budget`. Admission subtracts all running tasks' declared memory
reservations as well as the next task's budget. This deliberately conservative
rule protects against simultaneous claims before Mplus has allocated its memory.

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
