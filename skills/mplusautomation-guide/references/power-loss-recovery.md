# Recovering After Power Loss

Network loss, sleep and process termination require different responses. A local
worker may continue without the agent connection. After a reboot, old job IDs,
monitor timestamps and queue `running` rows are historical evidence. Inspect
current processes by PID plus creation time before claiming an estimate is live.

## Preserve and reconcile

1. Keep admissions disabled during reconciliation. Archive the queue database,
   WAL and SHM sidecars, configuration, checkpoints, logs and interrupted model
   directories. Once writers are absent, obtain a consistent SQLite backup and
   verify database integrity. Hash copied files; never discard the WAL merely
   because the main database exists.
2. Load each RDS checkpoint separately and release it before loading the next.
   Verify its statement position, stable model IDs, object environment, package
   attachments, random state and working directory. File existence and a valid
   RDS header alone do not establish readability.
3. Recheck completed outputs against recorded hashes and diagnostic contracts,
   including requested/completed imputations and required saved data. Distinguish
   estimation success, statistical warnings and saved-data failures. Reused rows
   do not represent independent new estimates.
4. For each abandoned claim, prove its old owner is gone and verify every input
   hash, including all members of an imputation index. If the output is complete,
   validate and reconcile it. If incomplete, archive the partial files and record
   the interruption before transactionally returning only that task to pending.
Retire dead worker registrations without deleting their audit history.

An orphaned `running` row can also hold the queue's declared memory reservation
after its worker has exited. This is a scheduling failure, not evidence that
the model is still estimating. Preserve a SQLite backup first, verify the
worker PID and all descendants are gone, and invoke the queue's normal `finish`
or revalidation command; let the saved `.out` parser publish `failed` or
`valid`. Keep the original output hash and the transition reason in the
recovery record.

The supplied queue currently has no generic `recover` CLI action. Use a reviewed,
run-specific reconciliation adapter with an explicit expected task list; do not
issue a blanket `running -> pending` update against unknown live processes.
An R checkpoint preserves the script state, not Mplus's internal estimation
state. A terminated model usually needs to restart from its preserved inputs;
do not promise recovery of arbitrary iterations or split the requested multiple
imputation analysis to salvage partial work.

## Restart and observe

Re-establish the dedicated RStudio session and run the parent workbench's native
smoke in the current agent tool layer. Register new async IDs and archive the
old IDs. Resume the coordinator from readable checkpoints and start one estimator
with the normal resource gate. Additional workers may remain lightweight until
sustained memory, CPU and disk headroom permits activation. Reboot does not imply
ample free memory: restored browsers and other applications can consume it.

If resource admission holds, report that the queue is restored but no Mplus
estimate has started. Keep polling the same jobs, display the hold reason and
fresh timestamps, and let the existing workers resume when resources recover.
Do not lower safety thresholds merely to produce a running PID or terminate
unrelated applications. A recovered scheduler is not a completed replication.

## Checkpoint publication

Write the complete new checkpoint to a distinct temporary file in the same
directory. Flush it, then atomically replace the previous checkpoint. Copying
over the existing file can leave it truncated after an interruption. In the
verified Windows Python path, `os.fsync` required opening the temporary file in
`r+b` mode; `rb` produced a bad-file-descriptor error. Verify successful replacement
and failure preservation on the actual OS, including invocation from R.

An atomic replacement reduces a partial-overwrite window; it is not a guarantee
against hardware/storage failure. Keep independent recovery snapshots. Reload
an updated coordinator only at a verified checkpoint boundary; editing its R
source does not change a function already loaded by an async process.

## Evidence from the Windows recovery

The real recovery preserved 142 files (about 1.69 GB), loaded all four RDS
checkpoints, and found no hash changes across 387 terminal output records. Two
unfinished model claims had intact input sets and were requeued. Windows atomic
publication tests and an R-to-Python publication check passed. This proves those
recovery steps; resumed model completion, manuscript comparison and macOS power
loss recovery require their own evidence. Do not share participant data or
machine-specific paths with this reusable guide.

## Follow-up: Windows readers and coordinator failures

The resumed Windows coordinator later stopped while publishing a small state
JSON, although its Mplus worker continued. Atomic replacement alone does not
handle a Windows reader opened without delete sharing. Retry transient
`PermissionError` for a bounded interval (the local adapter uses 15 seconds with
0.05–0.5 second backoff); retain both old and temporary files if retries exhaust.
Do not replace atomic publication with delete-then-copy. A test using an actual
Windows read handle blocked replacement, then released it and verified success.

Monitor the coordinator's PID and creation time as well as Mplus workers. A live
estimate and fresh overall monitor timestamp do not prove that future models
are still being prepared. Preserve top-level coordinator errors in durable logs;
reconcile its last checkpoint before submitting a replacement job. Existing
estimation workers need not be stopped for this repair.

The bundled queue now applies bounded replacement retry to JSON and worker CSV
publication. Use the same `atomic_replace()` for a live monitor's text report;
fixing only the checkpoint writer leaves the display vulnerable to the same
sharing-lock failure. The queue default retry window is five seconds. Its test
suite includes an actual Windows handle without delete sharing, plus permanent
failure preservation and non-permission errors that must fail immediately.
Read text manifests explicitly as UTF-8: the Windows locale may otherwise select
GBK and reject a valid manifest containing Chinese paths.

On takeover by a different agent or by a single executor, archive unavailable
collaboration state separately from the statistical queue. Never treat a missing
callback as a reason to resubmit a live model. Record new ownership, real async
IDs, process creation times and the next recovery action. The collector can
continue after the chat disconnects; it does not restart Windows, reopen RStudio
or guarantee an automatic restart after reboot.

If collaboration is unavailable and the user authorizes solo execution, keep
the statistical queue moving with the available executor. A handshake or callback
failure is collaboration state, not an estimation failure. Independently verify
a collaborator's saved artifacts when useful; a new handshake is not required
to inspect existing evidence.

When the Addin briefly times out, retry a short health call to the assigned port
and compare its session PID before restarting anything. A successful short call
does not replace a new async smoke when the session identity has changed. After
resume, distinguish active estimation, suspended wall time, and a terminated
process. Keep a per-run checkpoint separate from other projects in a shared
workspace so their queue totals cannot be mistaken for this task's status.

Disk exhaustion can truncate an in-place script edit as well as a model output.
Stage edits on a volume with space, retain the pre-edit contents, verify the
complete temporary file, then replace the destination. Recover space from owned
reproducibility artifacts without deleting source data or active model files.
On NTFS, compressing inactive text copies can preserve their logical paths and
contents; verify their hashes afterward. This is a Windows storage option, not
a prerequisite for macOS. Never disable disk admission limits to hide exhaustion.
