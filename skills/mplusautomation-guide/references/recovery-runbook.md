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
