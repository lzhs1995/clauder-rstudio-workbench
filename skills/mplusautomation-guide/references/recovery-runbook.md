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


## Poll failures and checkpoint-boundary scheduling

An October 18 observation returned `addin is not running` for one original
income-MI job, with `isError=false`, while two other original-job polls returned
fresh progress. A sequential retry of the failed job returned its continuing
conditional-fit progress. Neither the service nor the statistical worker was
restarted, and no job was resubmitted. Concurrent observation was present, but
the trace did not establish it as the cause. Preserve the failed response,
successful retry, original ID and timestamps instead of reporting a diagnosed
cause from coincidence.

Use sequential observation requests to one assigned RStudio session while its
statistical workers remain parallel. A healthy poll of another job does not
make the failed reply successful. Conversely, a failed observation does not
invalidate checkpoints or terminate an estimator. Check the text and content
as well as the wrapper flag. Read small durable progress files and verify
owner PID/creation time when the API is ambiguous. Retry the original ID with
a bounded observation policy; do not manufacture a terminal response, clear
the job registry or resubmit merely to obtain a cleaner status display.

New submissions still require current resource and transport admission. A
transport proof expiring while original jobs are running does not require
restarting them. Refresh the genuine native short-call/async proof for new
work, retain the old proof, and consume the real original terminals separately.

Admission freshness includes orchestration latency. One combination submission
passed its resource snapshot, but the snapshot was older than the existing
120-second limit when its background R began. The worker stopped before
creating its owner/watch or reading and combining the MIDS. Preserve the real
native error; verify absence of statistical artifacts and unchanged checkpoint
hashes before classifying this as an unstarted admission failure. Close that
actual job, archive the attempt, and take a new measured resource snapshot
after slow harness setup and immediately before a new submission. Do not edit
the old timestamp, relax the age limit or label a preparatory failure as failed
imputation. A retry is justified by evidence that the statistical step did not
start, not merely by a missing successful response.

### Release memory at a complete statistical checkpoint

When two FCS lanes occupy memory needed to combine already completed scopes,
prefer an explicit handoff at a complete-block boundary. In this workflow the
statistical worker already had a request hook before the next scope entry.
The supervisor checked that the remaining original scope had no lease, fit
log or checkpoint, verified the running source hashes, and wrote one durable
handoff request. Current blocks continued; the hook acted only before the
unstarted block. The original seeds, observations, random chains, fit budgets
and statistical code were unchanged.

The legacy lane wrapper labels a caught stop as a failure. Preserve that raw
record and classify the exact planned-handoff marker separately, with the
request and unstarted-block evidence. Consumers must keep this source waiting,
not turn it into a scientific failure or success. Real fitting errors and
timeouts remain failures. After the original job's actual terminal is consumed,
close its existing guard and verify process exit before admitting a replacement
execution segment. A request file alone is not proof that memory was released.

Combine the original blocks and check all members before inference. If the
frozen mixing rule requires more iterations, resume the same MIDS checkpoint,
random state and optimization cache within the cumulative original time limit.
Do not replace members, introduce a new seed or pool only successful draws.
Separate an unstarted original block from a failed block eligible for recovery.

Budget additional workers from measured complete-worker peaks plus an explicit
calibration allowance, preserving the existing Mplus reserve. Check Windows
available physical memory and commit immediately before submission, as well as
the number of live owned workers. Waiting consumers can exit with durable
family states and later resume under the same global call/time budget; they
need not retain an idle R process until every imputation source arrives. Keep
one Mplus owner across those segments. Never reclaim unrelated research or
security processes as a shortcut.

The first successful 40-chain combination recorded a process peak of about
0.496 GiB. This enabled replacing its initially unmeasured 1-GiB worker allowance
with the maximum eligible measured peak plus an explicit 0.15-GiB calibration
allowance, while preserving the 1.2-GiB Mplus reserve. Eligibility requires the
same combination code and chain iteration count, genuine completed/native
receipts, exited ownership and no larger original checkpoint footprint. File
size is only a scope screen, not a claim that RAM scales linearly with serialized
bytes. If no comparable completed run exists, retain the conservative unmeasured
allowance. Record the source receipt hashes and the new live memory/commit
sample; never revise an old snapshot or a model's statistical acceptance rule.

### Check the complete evaluation scope before diagnosing a collision

`source(..., local=TRUE)` retains the ClaudeR progress environment, but it can
evaluate assignments in the caller's environment. An initial inspection saw
`for (d in ...)` and suspected a collision with the wrapper's receipt directory.
Reading the complete file showed an existing `local({ ... })` wrapper: the
suspected collision did not occur. Record that correction; do not present the
added child environment as a demonstrated bug repair. For a source that lacks
its own isolation, a child environment can provide explicit binding isolation:

```r
worker_env <- new.env(parent = environment())
worker_env$MI_SCOPE <- scope
worker_env$MI_STOP_ITER <- target_iteration
source(combination_script, local = worker_env)
```

The child can resolve the original progress callback while its temporary
bindings cannot overwrite the wrapper's receipt path. Keep statistical code
unchanged and record the wrapper hash. A syntax check alone is not end-to-end
acceptance: require the actual native terminal, receipt at the intended path,
unchanged original checkpoint hashes and the full combination disposition.

These are execution and recovery practices. They do not establish missingness
assumptions, exact compatibility of working FCS with latent interactions, or
completion of the original four moderations and full H4. This workflow does
not install an unattended service that restarts RStudio globally.


## Verification recovery without restarting successful estimates

This Windows CHARLS case continued the October 18 API recovery documented
above. Separate the foreground API, background estimation, imputation, and
result verification. A failure in the last layer does not authorize repeating
successful Mplus estimates or regenerating imputed data.

### Observed chronology and unsuccessful attempts

| Stage | Observed evidence | Disposition |
| --- | --- | --- |
| Native API read | A synchronous process census returned an HTTP error inside a tool response whose `isError` was false; later polls of the original job IDs returned advancing stages. | Preserve the error and original IDs; prefer targeted owned-PID reads. No R restart or duplicate submission. The census was not proved to be the sole cause. |
| First Python verifier | The shell command exited 143, produced no PASS, and a Windows process check found no matching surviving verifier. | Record command failure; do not invent a kill cause or rerun the completed models. |
| Detached verifier without useful output | The wrapper was alive but its captured output did not locate the wait. | Archive the exact wrapper and verify owner/child identity before a controlled stop. Add explicit child logs and import-stage markers. |
| Instrumented imports | A bounded traceback showed pandas importing `platform.machine`, waiting in the Windows version subprocess. A process-local candidate bypassed that wait, but the complete dependency test still timed out. | The stack locates a wait; it does not prove CMD AutoRun, security software, or memory pressure is its unique cause. Do not publish the candidate as a complete repair. |
| Reduced Python dependencies | Removing pandas still left waits in NumPy module loading and SciPy extension loading. The bounded attempt ended after about 1,203 seconds with failure and no independent PASS. A targeted thread snapshot showed `PageIn` and little accumulated CPU. | Keep the actual timeout. Do not retry the same dependency startup indefinitely or interpret it as statistical nonconvergence. |
| Native R alternative | Read saved parameter vectors, TECH1 identities and TECH3 covariance directly in a separate ClaudeR background R job, with progress per family and member block. | Accept only after actual native completion and independent numerical checks; changing the verifier must not change the statistical contract. |

Use bounded `faulthandler` diagnostics and explicit child log files to identify
loading versus numerical work. Record process creation time, accumulated CPU,
working set/private bytes, stage age and the last saved artifact. A low-CPU
snapshot is not proof of deadlock. Avoid a whole-process census in the main
R HTTP thread when targeted Windows reads can answer the ownership question.

### PID identity must fail closed

The installed R `ps` API requires a POSIXt creation timestamp. Passing a numeric
Unix epoch to `ps_handle()` raised `time must be a time stamp (POSIXt)`.
The previous `tryCatch(..., error=function(e) FALSE)` incorrectly converted
that programming error into “process absent,” which could admit a duplicate
coordinator. Use the actual recorded timestamp type:

```r
created <- as.POSIXct(owner$created, origin = "1970-01-01", tz = "UTC")
handle <- ps::ps_handle(owner$pid, created)
alive <- ps::ps_is_running(handle)
```

Unexpected handle/access errors must block admission and remain visible;
only an explicitly identified missing or mismatched process may be treated
as absent. Native checks in this case returned true for the live PID and its
actual creation time, and false for the same PID with a different creation
time. Archive the original executing source before changing future launchers.
Editing a source file does not change an already-loaded worker and is not a
reason to restart it.

`ps_kill()` returning is also not an exit receipt. A first immediate check
still observed the owned process. Wait for bounded exit confirmation and
recheck identity and descendants before releasing ownership or starting a
replacement. Retain the unsuccessful stop attempt and final exit proof.
Never stop by process name alone or touch another project's RStudio.

### Measure comparable workers, preserve statistical work

A completed original imputation block supplied a measured private-byte peak
of 633,282,560 bytes (about 0.590 GiB). Its paired block had the same scope,
statistical source hashes, chain count and iteration target. Before using
that measurement, verify native completion, async-guard closure, actual
process exit, and checkpoint hash. This justified replacing a cross-scope
startup estimate with a same-scope measurement, while retaining the explicit
1.2 GiB Mplus reserve and 0.15 GiB unmeasured-worker allowance. Active peers'
possible growth was still reserved separately.

The resulting admission budget was about 1.940 GiB; the actual final Windows
sample showed 2.195 GiB available. That sample also exceeded the older
threshold, so do not claim the calibration alone caused the successful
launch. These are case measurements, not universal defaults. Keep original
chains, seeds, MIDS/RNG checkpoints, fitting rules and cumulative time limits.

A single attempted WSL cache reclamation timed out. Windows available memory
changed from about 1.751 to 1.857 GiB, but the retained WSL cache observation
did not establish successful eviction. Do not report this fluctuation as
memory reclaimed by the task, conflate private commit with physical RAM, or
repeat global cache eviction while active work must reload files.

### Evidence contract for the alternative verifier

The alternative must independently parse native saved parameters and TECH3,
map labels through TECH1, verify input/output/source hashes and imputation
membership, and recompute within/between/total covariance, Rubin intervals,
direct group differences, supported conditional slopes, finite-cluster
sensitivity and the registered multiplicity family. It must not call the
production pooling function or synthesize a PASS receipt. Preserve incomplete
families and their original failures; no partial-family pooling.

The public replay must read the files actually extracted from the release
ZIPs and verify their manifest, rather than silently use private model paths.
Keep the Python implementation as an optional independent route if useful,
but identify which implementation actually completed on this Windows host.
Native async submission, terminal reply, exit/guard closure, private result
checks and public replay have distinct receipts.

This is a recovery procedure for the assigned session and owned workers.
It does not establish an installed global unattended self-healing service,
successful repair of every Python dependency, or completed original latent
moderation and H4 hypotheses.


## Reuse verified bytes during result replay

The October 19 follow-up recovered independent verification through actual
ClaudeR background R jobs. The private reader checked 158 calls and recomputed
seven complete 20-member families from saved parameters and TECH3. A second
job checked the actual extracted public ZIP and reproduced the same seven
families. Neither job started Mplus. The package and its explanatory files
were subsequently checked byte-for-byte by anonymous download from
[the fixed publication](https://github.com/lzhs1995/PP-lcgm-paper/tree/70822535f744283164a8496fe75e011c4192800a/charls_corrected_h42_models_20261018).
This supplies the completed R fallback evidence; it does not turn the earlier
Python import timeouts into successful Python verification.

Small-file I/O can become a separate bottleneck after estimation. In a
targeted snapshot, the owned packager's read counters advanced while its CPU
counter barely changed; private allocation was about 53 MiB and Windows still
had about 2.27 GiB available. This establishes continuing reads, not a unique
diagnosis of storage hardware, antivirus, paging or the original API failure.
An owned builder that is still advancing must not cause a model resubmission.

The accepted public R replay used a bounded, per-job raw-byte cache. It read
2,779 payload files and served 1,639 later read requests from those exact
bytes, retaining 97,466,386 bytes under a 256-MiB limit. Retained payload bytes
are not the R process's total private memory or RSS. Admission reserved
0.45 GiB for the reader as well as the existing 1.2-GiB Mplus headroom. These
are measured case settings, not universal machine requirements. Private and
public checks have different workloads, so their elapsed times are not a
controlled speed benchmark.

Use this pattern only for sealed artifacts:

1. Require real producer completion, owner exit, matching input identities
   and a completely built package. The first appearance of a manifest during
   extraction does not mean extraction has finished.
2. Validate paths and expected lengths. Read a file's exact bytes, check its
   SHA-256 against the manifest, and reuse those same bytes for parsing. In R,
   `digest(raw_bytes, serialize=FALSE)` hashes file content; the default
   serialization hash is a different quantity. Preserve encoding, line
   endings, missing values and numeric parsing semantics.
3. Bind temporary I/O adapters in a child evaluation environment. Keep the
   independent TECH1/TECH3 reader and statistical calculations unchanged;
   do not replace the production pooling function with a cached result or
   mask readers in the foreground session. Verify actual parameter, covariance,
   interval, contrast and multiplicity parity after changing the I/O route.
4. Bound aggregate retained bytes, leave room for parser copies and R itself,
   report file-count progress, and release the cache with the worker. Record
   cache hits separately from statistical acceptance. For oversized inputs,
   retain a bounded streaming path rather than remove a resource gate.
5. Use a new cache for changed inputs, manifests or attempts. Do not cache
   live `.out`, checkpoint or queue files as if immutable. In a release check,
   the same bytes already read for `ZIP entry == extracted file` can also be
   hashed for the manifest check; a second filesystem read is unnecessary.

The original incomplete family and its timeout remained in the release. The
cache improved how saved evidence was consumed; it did not supply a missing
MI member, change an estimate, or complete the original four latent
moderations and full H4.


## Recover an owned result reader without restarting its job

The next income-family replay kept the same native ClaudeR job throughout.
It verified all 2,962 sealed payload hashes, then independently recomputed
four complete 40-member families. The final receipt was PASS. The raw-byte
cache retained 115,097,244 bytes, served 1,817 cache hits and stayed under its
256-MiB bound. Peak process private allocation was 283,049,984 bytes; cache
payload size and process allocation remain different quantities.

A slow but advancing parameter phase was investigated without resubmission.
The owned reader used about 236 MiB private with about 1.8 GiB available on
Windows. In a five-second sample it accrued about 0.28 CPU seconds and its
file-read counters did not change. A subsequent per-core sample found logical
cores 8–15 saturated while 0–7 had spare capacity. This distinguishes an
observed scheduling opportunity from an unsupported claim that all slowness
was caused by RAM, disk, Python imports or the RStudio API.

After matching PID and creation time to the actual job owner, only that
reader was bound to the currently less-busy core set and raised from Normal
to Above Normal. The last pre-change poll showed `sd_INC 25 of 40` at
06:05:34 UTC; the change was recorded at 06:06:45 and all four families
completed at 06:07:16. These observations support the usefulness of this
intervention in this run. They are not a randomized or equal-work benchmark:
affinity and priority changed together, and host load could also change.
Do not publish a universal acceleration factor or a universal `0–7` rule.

For similar recovery:

1. Inspect the existing job ID, stage, owner creation time, CPU deltas,
   per-core load, private/RSS memory and I/O. Preserve original failures.
2. When a specific owned worker is advancing and a less-busy eligible core
   set exists, record its original priority/affinity before a process-local
   adjustment. Never use Realtime, modify another session, or change model
   specifications to make a resource optimization appear successful.
3. Continue the same job. Require the same numerical and file checks and
   consume its real native terminal. Restore settings if the process will
   remain alive; otherwise verify its exit. Do not leave a global affinity
   setting or an unowned restoration watchdog.
4. Keep API recovery, numerical acceptance and scheduling evidence separate.
   This operation does not repair the previously timed-out Python imports
   or establish a global unattended self-healing service.

Resource admission must also describe the actual phase. The first public
replay check retained simultaneous engine-plus-reader reservations and held
at 1.386 GiB available. All owned estimates and private readers had already
exited, no engine lock remained and no host Mplus was running. A separate
serial-replay contract therefore retained the original 1.2-GiB total floor
and 2-GiB commit floor, with a 0.45-GiB reader allowance and no simultaneous
engine reservation. The comparable private reader's observed peak was below
that allowance. At actual submission availability had risen to 1.963 GiB,
which also exceeded the old threshold: do not attribute launch to the changed
budget alone. Archive the original hold and both contracts. This phase
transition does not loosen the original estimation admission rule.

The published result package still preserves the failed family in the
registered twelve-test set. Successful recovery of a result reader does not
complete the original CFPS latent moderations or full H4.


## Distinguish startup latency, unstarted admission and estimator failure

A CHARLS interaction member reached its 240-second awake wall limit after
Mplus first appeared around 208 seconds. The last sample contained only about
26 seconds of Mplus CPU. Its output said `INPUT READING TERMINATED NORMALLY`,
but had no normal model termination or usable TECH3. Preserve this as a real
timed-out attempt; input acceptance is not estimation success. The trace proves
late engine creation, not a unique explanation of that delay or model
non-identification. Another latent-interaction timeout in the same project
had sustained computational work and does not inherit this diagnosis.

An isolated, bounded recovery kept the input and DAT byte-identical, retained
the original starts, 30-point integration and statistical constraints, and
scheduled only the identified Rscript/descendants on currently available CPU
cores. It finished in 111 seconds and passed independent checks of 88 saved
parameters, standard errors and TECH3 covariance. This is an observed recovery,
not a controlled speedup benchmark: host conditions also changed. Launch and
loading time remained inside the budget; no time was retroactively excluded.

### Resume an unstarted member without replacing an imputation

The continuation completed ten further members before its next member stayed
below the unchanged physical-memory admission floor. The supervisor had not
inserted a call reservation or launched Rscript/Mplus for that member. The
legacy R loop returned `MEMBER_FAILED:...:NOT_RUN_RESOURCE_OR_BUDGET`; the
underlying `not_run.json` correctly said `RESOURCE_HOLD`. Keep both records and
classify the event as unstarted admission, rather than a failed statistical
estimate. Do not count it as an engine call or replace its imputation.

1. Consume the actual original native terminal, close its existing guard and
   confirm owner exit by PID plus creation time and absence of the engine lock.
2. Preserve the original call/state snapshot and `not_run.json`. Check that
   no engine receipt, output or unresolved SQLite reservation exists for the
   candidate. Reuse its already generated, hash-matching input and original
   imputation. Successful members remain untouched.
3. Reclaim authorized idle resources and measure Windows physical/commit
   headroom. In this incident, one R garbage collection and own-pane history
   cleanup did not establish meaningful recovery. A Task Manager close request
   also lacked exit proof; `psutil.wait()` raised `AccessDenied`. Do not treat
   permission failure as exit, repeat the action indefinitely, or attribute a
   later host-memory increase to it. Capture the attempted action before a
   potentially failing wait and classify the exception explicitly.
4. Register a new execution segment only after actual admission, retaining the
   original cumulative call/time ledger. The existing successful outputs and
   original seeds are reused; a new wrapper ID is not a new statistical draw.
5. Require all original members before pooling. Here the recovered family
   reached 20/20 and independent raw-parameter/TECH3 Rubin calculations passed.
   The direct group-difference interval crossed zero. Execution recovery does
   not guarantee significance or complete the original latent-moderation H4.

A runtime replacement can consume a finite call slot even when much time
remains. In this case the last original member required one explicitly recorded
supervisor-reviewed operational amendment, 176 to 177 cumulative calls, with
the original 10800-second total and 240-second per-call caps unchanged. Apply
such an amendment only within the user's existing scope/authority, after the
remaining successful members and owner exit are verified. Keep the original
contract, failed call and new contract hashes. Do not generalize this case into
automatic budget escalation; no further retries were admitted.

Preserve the existing distinction between a failed native response, a live
background job and an estimator result. Poll the original job while it lives;
start a replacement segment only after its actual terminal and ownership are
reconciled. These observations extend the earlier Addin/rebinding and ambiguous
submission cases; they do not install a global unattended restart service.


## Preserve live Windows output without changing the Mplus model

An inspected MplusAutomation 1.3 Windows `runModels()` calls
`system(..., intern=TRUE, wait=TRUE)` and prints the returned text afterwards.
`showOutput=TRUE` therefore does not establish live iteration visibility.
Keep the installed package unchanged. A tested local adapter supplied an
exclusive `.cmd` as `Mplus_command`:

```bat
@echo off
"C:\licensed\Mplus.exe" "%~1" 1>"mplus_stdout.log" 2>"mplus_stderr.log"
exit /b %ERRORLEVEL%
```

Use an actual resolved executable and an exclusive model directory. A bare
`detectMplus()` result such as `Mplus` must first be resolved with `Sys.which()`;
normalizing it against the working directory can select a same-named directory.
Reject directories, missing executables, existing outputs and changed input
hashes. Keep `killOnFail=FALSE` and leave termination to the identity-bound
supervisor; do not use MplusAutomation's image-wide failure cleanup.

The native ClaudeR synthetic test retained 35 growing byte snapshots while the
owned Mplus process was alive. The final interrupted log contained 38 EM/FS
iterations. Each live prefix was checked against its timestamp, PID/creation
identity, SHA-256 and the final bytes. This is empirical live-output evidence
for this Windows engine, not a promise that every engine/runtime flushes at
the same frequency. Raw partial output must survive a timeout.

The screen heading was `ITER LOGLIKELIHOOD`, not the literal phrase
`TECHNICAL 8`. The original observer's false trace flag was retained. A separate
parser used the actual header, complete rows and Fortran D-exponent numbers;
it checked truncated tails, unrelated parameter rows and real live prefixes.
Do not use a missing heading substring as proof of no iterations, or infer
convergence merely because iteration rows exist.

The model did **not** finish normally. Its `.out` stopped after input reading;
the dependent second synthetic case was not run. The genuine native terminal
reported an R failure even though the outer tool flag was `isError=false`.
The owned engine, background worker and observer exited, and the original
guard was closed. No successful full-parameter equivalence was claimed.

The timeout threshold was first observed at approximately 120.65 seconds,
while the R call returned at approximately 144.66 seconds. Record the
deadline, detection, termination request, confirmed exit and R return
separately. Potentially slow metadata/file operations must not precede the
deadline check. Validate deadline enforcement with isolated controllable
processes before deploying it; a bounded policy is not a hard real-time
guarantee. This prototype did not establish a production-ready supervisor.

The initial design repeatedly loaded MplusAutomation in nested Rscript
processes. One attempt exhausted its startup limit without creating Mplus.
A single recorded revision loaded the package once in the existing ClaudeR
background worker and reused unchanged prepared inputs. Preserve the failed
startup and separate loading/estimation budgets. Avoid extrapolating a speedup
from different host conditions, and do not reopen failed research models just
to obtain better logs.

An earlier ambiguous native submission was recovered by matching the exact
code in ClaudeR's actual job registry and polling its original ID. It was not
resubmitted. These observations extend the recovery procedure above; they do
not install an unattended global restart service or close scientific gaps.


## Bounded MplusAutomation integration: distinguish admission, engine and wrapper

Follow the preceding live-output recovery section before this integration. The
verified sequence was native ClaudeR async -> one R worker loading MplusAutomation
1.3 -> `runModels(exact.inp, recursive=FALSE, replaceOutfile='never',
killOnFail=FALSE, Mplus_command=exact_launcher.cmd)` -> a Python controller ->
the actual licensed Mplus executable as its **direct child**. The cmd launcher
returns the controller's `%ERRORLEVEL%`; it is not the process being timed/killed.

Keep five states separate: native transport failure, R/package loading, resource
admission hold, launched-engine termination, and output/reader validation.
In the 2026-10-19 integration the first R worker loaded successfully, but Windows
available memory reached 1.152 GiB against the frozen 1.2 GiB floor. The adapter
returned `NOT_RUN_RESOURCE_HOLD`, exit75, with **zero engine calls**.
`runModels()` emitted a warning, not an R exception. A subsequent generic
`stopifnot(process_exited)` obscured the resource cause. Preserve that original
failure; dispatch on `status` before dereferencing engine-only fields.

After consuming the original native job and verifying its worker absent, check
the current session and release only owned, unneeded allocations. In this case a
single main-session `gc()` and a Windows census found no leftover model workers;
the next measured availability was1.316 GiB. That noisy change is not a measured
amount reclaimed by `gc()`. Protect other live RStudio sessions and active MCPs.
Re-admission used a new attempt directory with identical input/data hashes and
unchanged thresholds. The first attempt's receipt, warning and terminal R error
remain intact. A resource hold never counts as a failed statistical estimate.

The admitted synthetic regression ran licensed Mplus9 exactly once. The direct
child exited0 in2.1145 seconds. `readModels(exact.out)` found normal estimation;
all three estimates and SE matched independent conditional-normal ML formulas
(residual variance uses SSE/n) within half the printed0.001 unit. This validates
this small normal-completion route, not equivalence for LMS/Bayes or all models.

A separate **Python fake engine**, explicitly not Mplus, tested timeout through
the same `runModels()` launcher. Its4-second limit was detected at4.0557 seconds,
exit confirmed at4.2020 seconds, and its flushed stdout survived. The cmd returned
124; `runModels()` again only warned, with no R error. Require the controller
receipt and valid `.out`; do not use absence of R errors or `isError:false` as
model acceptance. No fake result was adopted. The real native completion marker
was collected; both async guards closed and both protected sessions retained
their original PID/creation time.

Separate phase clocks. The successful recovery worker loaded packages in62.7793
seconds. The fake adapter used18.5353 seconds before engine launch, including
admission wait; total fake `runModels()` wall time was36.7034 seconds. Therefore a
4-second engine deadline is **not** a4-second R/API turnaround guarantee. The
loading budget here was advisory, not a proved hard kill deadline.

The controller retains the actual `Popen` handle, starts a monotonic deadline
before launch, redirects stdout/stderr directly to files, and keeps process scans
and log parsing out of the deadline path. Timeout targets only its direct child,
then waits for confirmed exit. Production use still needs explicit parent-crash,
descendant/Windows Job Object and durable-queue ownership handling; this prototype
has not replaced the production queue. Never market one synthetic success as
unattended recovery for every failure mode.

Evidence: `PP-lcgm-paper/mplus_bounded_adapter_20261019`, with original hold,
native job receipts, launcher/controller, synthetic inputs, output, independent
closed-form checks and portable packet verification. No CFPS/CHARLS fit or new MI
was executed. Full four-moderation inference and full H4 remain incomplete.
