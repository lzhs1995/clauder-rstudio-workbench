# Windows PP-LGCM recovery runbook

This runbook records the recovery pattern used for the four isolated
`absolutive`, `relative`, `relative2` and `relative3` scripts. It is a
reproduction aid, not a claim that the manuscript tables are already
equivalent.

## Before resuming

1. Preserve the queue with a native Windows SQLite backup. Do not copy a live
   WAL database through a Linux SQLite library.
2. Inspect each worker and coordinator by PID, creation time, executable,
   parent chain, working directory and task ownership. A stale JSON heartbeat
   is evidence to inspect, not permission to delete a live process.
3. Read all four RDS checkpoints one at a time under the memory gate. Record
   their SHA-256, byte size, statement/model position, packages, RNG and object
   count. Do not edit a checkpoint while an Mplus child is running.
4. Reconcile a dead idle worker registration inside one `BEGIN IMMEDIATE`
   transaction. Retire only the exact `(worker, PID, creation time)` row after
   confirming it owns no running task. Save the pre-change database backup and
   event record.

Check physical disk allocation as well as logical file sizes. On Windows,
NTFS compression can recover space from sealed, inactive checkpoint backups
while preserving their paths and bytes. Restrict this to an explicit archive
list, record before/after allocation and SHA-256, and stop once the chosen
disk reserve is restored. Do not compress an active checkpoint or remove its
only recovery copy. This is a Windows storage operation, not a portable
requirement for macOS.

If sealed checkpoint compression is exhausted, inventory immutable artifacts
in the isolated reproduction run before considering deletion or lower disk
reserves. Eligible examples are closed recovery SQLite snapshots, an older
run namespace with no pending/running tasks, and `.dat`/`.out` artifacts whose
task is terminal. Bind the last category to queue task IDs, recheck the state
and unchanged file size/mtime before compression, and hash every file before
and after. Exclude the active SQLite/WAL, current checkpoints, live logs,
pending/running model directories, and original research files. NTFS transparent
compression preserves filenames and logical bytes, so existing readers can
continue using the verified paths. Record allocated bytes, not only logical
sizes, and stop at an explicit free-space target or a resource hold.

Account for many small imputation data files: an inventory limited to files
larger than 1 MiB missed roughly 3.5 GiB of eligible files in one recovery.
Keep the recovery evidence and distinguish a disk admission hold from a dead
worker. When the original worker remains alive and reports `disk_hold`, restored
space should wake the same job; restarting RStudio or submitting another worker
would not fix the storage cause.

Do not equate a large RDS inventory with recoverable disk space. Deferred render
objects saved by `saveRDS()` may already be gzip compressed (header `1f8b`);
check encoding and allocated size before proposing further compression. Keep
unrendered objects and current checkpoints intact. Record host free-space changes
separately from bytes reclaimed by this task: paging and other workloads may
consume or release space while the statistical queue is idle.

## Resume and supervise

Use one native `execute_r_async` job for the coordinator and retain its original
job ID. Record the async guard pre-submit and register evidence before polling.
The coordinator must use an atomic directory lock containing PID and creation
time. A lock directory left by a dead process is archived only after identity
review; never infer liveness from the directory's existence alone.

If RStudio has a different PID/creation time, its old async IDs are historical
evidence, not resumable handles. Prove the new native session with a short
sync/async smoke and archive the old job identities. An orphaned `running`
task is eligible for recovery only after its worker and matching Mplus process
are confirmed absent, input and consumed-file hashes still match, and any
partial attempt is copied to an immutable hash-verified archive. A successful
output should be validated rather than rerun. For an incomplete output,
record the exact old row and a transactional recovery event before requeueing
the unchanged logical task; keep its previous attempt archive intact.

Checkpoint state and display sidecars can have different schemas. Compare
documented fields: a sidecar `statement` is not automatically a checkpoint
`next_statement`. Preserve both and inspect a discrepancy; never skip source
statements by copying a display value into the RDS. Confirm package presence
without eagerly loading every saved package during the read-only audit, which
can consume memory needed by the next checkpoint.

At restart, seed the coordinator with finished outcomes only when a successful
checkpoint read audit still matches the actual checkpoint SHA-256. Preserve
the recorded failures, blocked steps and reuse counts. This avoids loading
large environments for scripts that already reached their end. A display
sidecar alone must never authorize skipping a script. Reject missing or
duplicate script entries, unsuccessful audits and changed hashes.

For large checkpoint audits, prefer a short-lived process per changed
checkpoint. In the PP-LGCM recovery, a read-only validator retained about
378 MiB of private memory after a completed read and garbage collection.
A fresh process avoids carrying that allocation into the next read, but
still has to pass the unchanged memory gate under the current host load.
Retain the completed audit and hash, verify process exit, and continue only
the remaining read. Do not recycle a live estimator or another user's session
for this purpose. Record the replacement validation job separately from the
unchanged model worker and coordinator job IDs.

A recovery launcher may wait for those durable validation results and then
start the singleton coordinator. Its readiness check must require every
script and matching hashes, including the unfinished script; a partially
written audit must not unlock recovery. Recheck the files at launch, consume
only a stop marker owned by this maintenance operation, restore the previous
queue admission setting, and publish the actual native async job ID. Report
validation wait and estimation progress as different stages.

When a checkpoint waits for a queued producer, read only its small state JSON.
Treat both `pending` and `running` as a lightweight wait. Reload the large RDS
only after the queue reaches a terminal state or the state is unknown. The
coordinator's execution completion marker must allow terminal model failures;
failures remain visible in the queue and require a separate retry and
scientific review. Keep `run_attempts_complete.json` separate from the final
manuscript comparison marker.

Run a headless monitor under a kernel singleton lock. It may restart its own
collector after a verified crash and sufficient disk, with bounded error-log
rotation. It never starts, kills or resubmits R/Mplus work. A supervisor samples
its heartbeat and writes a small status JSON so an interactive agent does not
need to poll continuously.

Distinguish an individual collector crash from loss of the whole Windows user
session. In a measured PP-LGCM incident, Winlogon event 7002 (logoff) appeared
seconds after the last monitor report, followed later by event 7001 (logon).
RStudio, its workers, Mplus and the independent monitor supervisor were all
gone, while the system boot timestamp was unchanged. Save the event IDs, UTC
timestamps and boot time before attributing the interruption to a reboot or a
slow model. A user-session monitor supervisor cannot survive that logoff and
cannot restore statistical jobs merely by restarting its display. After a new
login, prove the new RStudio PID, preserve orphaned attempts, and recover from
the durable queue/checkpoints. Service or scheduled-task recovery would be a
separate installation; do not claim it exists because a collector watchdog is
running.

For Windows SQLite snapshots, explicitly close both backup connections. The
`sqlite3.Connection` context manager controls transactions; it does not close
the handle. Use `contextlib.closing` so a completed audit does not leave its
snapshot locked. A synthetic manuscript/queue test should finish and remove
its temporary files without requiring garbage collection or process exit.

## Evidence gates

For every terminal task require matching output, `validation.json`,
`model_status.json`, execution log and input hashes. Classify failures from the
Mplus output (`NO CONVERGENCE`, invalid `DEFINE`, zero variance, SAVEDATA
syntax, imputation incompleteness, and so on) before deciding whether a retry
is scientifically justified. A table is ready only when every output path is
available and the raw estimates, warnings, fit statistics and displayed path
labels have been compared with the manuscript source.

The Windows run used a three-worker cap, processor and memory admission,
direct dependency priorities, native monitor recovery and immutable queue
snapshots. Its live evidence currently contains active estimates and terminal
failures; therefore the guide remains `draft` until model failures and all
manuscript table cells are reconciled.

## Controlled stop and deferred archive

When the success-first triage selects a no-history attempt for deferral, first
disable queue admission so no replacement claim races the review. Verify the
recorded worker PID and creation time, the configured Mplus executable, the
working directory and the exact input filename. Confirm the Mplus process is a
descendant of that worker. Copy every file in the model directory to a
date-stamped deferred archive and compare SHA-256 hashes before stopping
anything. Terminate the exact Mplus PID, wait for it to exit, then terminate the
same worker only if it is still the verified owner and has no Mplus descendant.
Publish `defer` through the queue CLI so `validation.json`, `model_status.json`
and the append-only event record state `estimation_ok=false`; never edit the
SQLite row by hand. Recheck that no process still contains the input path, then
re-enable the queue at a measured worker limit.

The archive is evidence of an interrupted attempt, not a usable estimate. Keep
its input, partial output, execution log, request and input manifest together;
later retries must use a new attempt directory and must not overwrite this
record.


## Live RStudio, unresponsive HTTP, and ambiguous async submission

The October 18 CHARLS income continuation exposed three distinct failures.
Do not collapse them into “RStudio is closed” or “the model failed.”

1. The assigned R process remained alive with the same creation time and a
   listener on port 8787, while an HTTP execution request timed out after 30
   seconds. The Viewer still displayed “Running.” The inspected bridge's
   `check_addin_status()` used a two-second GET and caught all exceptions as
   `False`; its tool layer then reported “addin is not running.” A failed
   health probe therefore did not establish process death. The initial cause
   of the HTTP stall was not uniquely determined; memory pressure and CPU
   contention must not be asserted as its cause without additional evidence.
2. During a scoped stop of the assigned HTTP service, discovery selected
   another live R session. After restarting the original port, `list_sessions`
   showed the bridge still connected to that other session. Explicitly binding
   the assigned session restored the intended route. A successful discovery
   listing alone does not prove the selected service or research ownership.
3. A subsequent native `execute_r_async` returned a communication error, but
   the RStudio execution log already contained a new job ID and the exact
   submitted script. Polling that original ID returned live model progress.
   Resubmitting on the error alone would have created a duplicate coordinator.

### Recovery order

- Save the transport error and timestamp. Freeze new submissions, while
  independently observing existing workers through small durable progress,
  checkpoint and terminal files. Check PID **and creation time**, executable,
  parent chain and isolated run root. An inaccessible API does not cancel a
  worker. A listener, Viewer label, discovery record and healthy execution
  endpoint are separate observations.
- Use one bounded short native call and a direct Windows HTTP diagnostic on
  the assigned port. Record connection refusal, connect/read timeout, HTTP
  status, empty response and remote R error separately. HTTP diagnostics are
  not evidence of native MCP success. Avoid accumulating unbounded probes.
- In this incident, both owned imputation workers had already exited and all
  four scopes had independently verified 40-imputation artifacts. Restarting
  only the assigned ClaudeR HTTP service through its Viewer controls was
  therefore justified. Preserve the RStudio process and unsaved documents;
  keep **Fresh start on restart unchecked**. This is not permission to restart
  a live estimator, another session, or the R process. If workers remain live,
  preserve them and their evidence; do not infer safety from a stale UI label.
- Record the stopped state, restart the same port, then call `list_sessions`
  and explicitly `connect_session` to the assigned name. Verify the expected
  PID in a short R call before any mutation or submission. Recheck discovery
  after service loss because automatic fallback may select another project.
- Read the old job using its original ID. In the verified incident the R PID
  and creation time were unchanged, and the original completed imputation job
  remained readable after the HTTP restart. Save its genuine terminal reply
  and close its existing async guard. Do not recreate an inbox, job registry,
  callback or success receipt by hand. The background-job registry is inside
  the ClaudeR namespace; assuming it is in `.GlobalEnv` previously produced a
  diagnostic lookup error, not evidence that the job was missing.
- For a timeout or communication error **during submission**, treat acceptance
  as unknown. Inspect the actual execution log and background registry before
  considering another submission. Match the intended code/run root, unique
  job ID, worker identity and durable ownership lock. Poll and register that
  original ID if accepted. Preserve the failed response alongside the recovery
  receipt; do not fabricate a successful submission response. If identity is
  ambiguous, investigate instead of choosing an arbitrary job.
- Recheck Windows resource admission immediately before launching genuinely
  unsubmitted work. Keep the original input hashes, imputation membership,
  scientific settings, single-owner lock and runtime budget. After verified
  FCS exit, this batch moved only its model coordinator and verified descendants
  to the released CPU set. Such a change needs an ownership/affinity record and
  observed timing; it is not by itself a causal speed benchmark.

### Required proof and limits

Recovery acceptance requires the expected session binding and PID, a real
native short-call result, original-job readback when available, one registered
coordinator, and genuine downstream Mplus execution/output validation. A
successful request or “Running” label alone is insufficient. The first income
parent actually completed in Mplus 9 and passed its model gate after recovery;
the remaining family estimates were still in progress when this case was
recorded. This proves a recovered execution chain, not complete MI inference,
four complete dynamic moderations, or full H4.

The evidence includes the original error, R execution-log job identity,
unchanged R PID/creation time, original imputation terminal reply, recovered
native poll, async-guard registration, model ownership record and actual
Mplus output hash. Keep private UI captures local: a window-bounds screenshot
can accidentally capture an overlapping unrelated application. Public skill
documentation should carry the recovery procedure and aggregate facts, not
unreviewed desktop screenshots, credentials, personal records or local IDs.


## Continued background progress during repeated read-side failures

Treat read-side HTTP failure and worker failure as separate events. In a later
bounded CHARLS batch, native polling reported both communication errors and
the generic `addin is not running` message, and an independent Windows root
GET also timed out. Meanwhile the original worker advanced through all four
branches and saved 16 Mplus attempts. After its durable terminal appeared,
polling the original job returned the complete native terminal without an
HTTP restart, Escape, R restart or duplicate submission. Twelve diagnostic
fits were admissible; four interactions reached their predeclared time caps.
Recovery of the interface does not change those scientific dispositions.

Prefer known owned PIDs and bounded external Windows diagnostics over a
whole-process census inside the main R HTTP service thread. A synchronous
process inspection coincided with this incident, but the trace did not prove
it was the unique cause. Keep that uncertainty. Preparing a recovery action
is not executing or validating it: an unused foreground-interrupt candidate
must not be documented as a successful repair. Recheck the original job
before acting on a prepared restart, especially after durable completion.

Also separate client hook latency from HTTP, R and Mplus time. Repeated
ten-second hook timeout messages were observed with RTK and cross-agent
evidence hooks configured. The configuration alone does not identify which
hook timed out or prove that it caused the HTTP stall. Diagnose each with
bounded captured payloads and retain the evidence checks; do not disable a
security or collaboration guard to make the display look healthy. Continue
using RTK explicitly for supported shell commands while investigating its
automatic rewriting path.


## Foreground preparation can hide a live Addin

In a Windows CHARLS run on 2026-10-18, a synchronous `execute_r` request
compiled eight model inputs from existing parameter files. The call returned
`R Error: HTTP error communicating with RStudio`; subsequent native calls
reported that the Addin was not running. The tool wrapper nevertheless had
`isError: false`. A direct Windows HTTP health request also reached its ten
second read timeout. These were failed API checks, not successful execution
receipts, and the process discovery record alone did not prove HTTP health.

Durable evidence showed a different state at each layer. The foreground PID
and creation time were unchanged, input `job.json` files advanced from two
to eight, and two existing background jobs continued to update their model
and conditional-fit counters. Once preparation finished, native execution
worked on the same foreground PID; the original Mplus job returned its real
terminal output and the original imputation job remained running. No service
restart, statistical resubmission, or data regeneration was needed. The
foreground request was still executing after its response had been lost.
This observation does not identify the underlying reason that preparation was
slow, and does not establish memory pressure as the root cause.

Use these recovery rules:

1. Treat batch input compilation and parameter parsing as potentially long
   work. Submit them asynchronously with `source(..., local=TRUE)`, emit a
   stage for each family, and save a distinct `INPUT_ONLY_NOT_ESTIMATED`
   terminal. Calling a step “preparation” does not make it safe for the
   foreground HTTP execution window.
2. Inspect the actual tool text as well as its error flag. Preserve the raw
   error, expected session/port/PID/creation identity, last original job ID,
   and timestamped durable stages. Do not turn a health-check timeout into
   a diagnosis that RStudio has exited.
3. If a synchronous request has an ambiguous outcome, inspect its scoped
   outputs and ownership before repeating it. Already-generated input hashes
   and continuing progress can establish execution without establishing
   successful completion. Never start a replacement coordinator just because
   the API cannot poll the original one.
4. While the foreground is occupied, use the existing lightweight Windows
   watchdog records for the background estimates. Keep the owned Mplus and
   imputation workers intact. If durable work is advancing, a restart is
   not the first recovery step.
5. After responsiveness returns, bind the intended session explicitly if
   routing changed, verify the original PID/creation identity, consume the
   original async terminal, and reconcile the generated files. A new smoke
   test must not substitute for reading the real job. Missing or inconsistent
   outputs still require investigation; an HTTP recovery alone is not
   statistical acceptance.

This case complements the earlier Addin-only restart case in this runbook:
recovery action depends on the observed state. There is no blanket rule to
restart on every timeout. The implementation still does not claim a globally
installed unattended Addin-restart service.

### Admit a new imputation worker without starving Mplus

The same run found that checking only the existing Mplus minimum before
starting an additional R worker could leave the next model below that minimum.
Admission was tightened before the new worker started: preserve the original
Mplus headroom **plus** the measured incremental full imputation-worker peak
and an explicitly recorded allowance for its expanded design. Historical
full-worker peaks were used initially, then compared with the live new-worker
peak before admitting the second independent chain block. The allowance is
an assumption to calibrate, not a measured footprint or universal constant.

Use Windows available physical memory, commit headroom and CPU samples. Keep
the snapshot fresh at submission, release completed owned coordinators, and
do not close other research sessions to satisfy the gate. The two imputation
blocks retain different frozen seeds, original MIDS/RNG checkpoints, and
their full-family mixing rule. Parallel scheduling must not reuse random
draws, replace failed members, or equate successful conditional fits with
accepted inference.

Evidence for this incident is included in the
`charls_corrected_dynamic_mi_models_20261018` paper-repository package:
`recovery/INPUT_PREVIEW_NATIVE_RESPONSE.json`,
`INPUT_PREVIEW_HTTP_DIAGNOSTIC.json`, `FOREGROUND_DURING_PREVIEW.json`,
`SYNC_CALL_DURABLE_RECOVERY_PROGRESS.json`, `SYNC_RECOVERY_COMPLETE.json`,
and `ORIGINAL_INCOME_JOB_RECOVERED.json`. Its independent raw-parameter
verification covers 88 calls and four 20-member observed-baseline working-MI
families. This does not complete the original latent-moderation hypotheses
or full H4.
