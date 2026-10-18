# Archived numerical replay and Windows runtime

Use this route when the user authorizes frozen DAT/INP replay while original
data transformations or row identities remain unrecovered. Record three
separate results: archived numerical agreement, original-source reproduction,
and scientific adoption. Missing upstream provenance does not block the first
route once it is authorized, and exact numerical agreement does not close the
other two.

## Freeze the replay before fitting

- Bind exact DAT, INP, historical OUT, executable and producer-script hashes.
  Use a fresh, short local output root. Keep historical artifacts read-only.
  Repoint only declared file locations; retain all equations, controls,
  covariances, seeds, bootstrap counts, estimator and precision settings.
- Separate the manuscript model list from the full template grid. Existing
  `[[init]]` templates may contain original output paths; do not execute those
  paths during inventory. Preserve the complete template and compilation map.
- Declare comparisons before fitting: row keys, integer counts, printed-value
  tolerances, bootstrap endpoint treatment, version banners and diagnostics.
  Same printed numbers are not proof of bit-identical internal solutions.
- Fit representatives from each requested family through the bound RStudio
  and `MplusAutomation::runModels()`, then `readModels()` on exact OUT paths.
  Reproducing a historical identification or standard-error warning is a
  successful failure reproduction, not an inferentially valid estimate.

Count source paths separately from distinct contents. One archived batch had
six DAT paths but four DAT hashes. A single frozen copy per hash saved storage;
the final integrity audit still checked all six original paths. Keep current
R scripts and same-named archive variants separately bound to their own hashes.

## Separate compute time, resource waits and sleep

Record timestamps, CPU service, output growth, Windows available RAM/commit,
worker and child RSS/private peaks, and sampling gaps. Large wall-clock gaps
can reflect Modern Standby or lid closure. Verify Windows power events and
AC/battery status before calling them slow estimation. A configured
`PROCESSORS` count does not establish actual parallel work: inspect CPU service
and thread counts by phase, without changing statistical settings.

For an unattended authorized batch, the bundled
[`windows_awake_guard.py`](../scripts/windows_awake_guard.py) requests
`ES_CONTINUOUS | ES_SYSTEM_REQUIRED` in a separate Windows process. It keeps
only the system awake, requires the owner PID **and creation time**, writes a
heartbeat, and releases its request when the owner ends or `stop.request` is
created in its own output directory. The directory must be new. The helper
does not change the power plan, use away mode, or prevent deliberate user
sleep/lid actions. If forcibly terminated, Windows ends its request, but a
completion receipt is not guaranteed. Do not infer that sleep was impossible
merely because a guard existed.

Create an owner file from the actual running worker (not an old PID):

```python
owner = {"owner": {"pid": worker.pid, "created": worker.create_time()}}
owner_path.write_text(json.dumps(owner), encoding="utf-8")
subprocess.Popen([sys.executable, "windows_awake_guard.py",
                  "--owner-file", str(owner_path), "--output", str(new_guard_dir)])
```

`worker` is a verified `psutil.Process`; `owner_path` and `new_guard_dir` belong
to the isolated batch. Use native Windows Python with `psutil` installed.
Capture stdout/stderr and verify `identity.json` before relying on the guard;
retain `completion.json` and its `released` result. Keep the helper beside the
bundled `mplus_queue.py`: its bounded atomic-replace retry tolerates transient
Windows reader locks without dropping the awake request. A stopped owner cannot be
replaced by another process with the same PID. For R `ps`, `ps_handle(time=)`
requires POSIXt; alternatively obtain a fresh handle and explicitly compare
`as.numeric(ps_create_time(handle))` with the recorded epoch seconds.

See Microsoft's [SetThreadExecutionState contract](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate): CPU/disk activity alone need not reset the idle timer.

If samples still show shared gaps, inspect power events and AC/DC status even
when the helper heartbeat exists. In an archived APIM batch, three workers
shared a roughly 32-minute gap while Windows recorded Modern Standby and lid
events on battery power. An active system-only request did not prove continuous
computation. Microsoft's [PowerSetRequest documentation](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-powersetrequest)
also describes the limited lifetime of system/execution requests in Modern
Standby on DC power; do not infer an indefinite battery guarantee from either API.

When the authorized unattended workflow needs an additional display request,
use a separate, owner-bound helper with
`ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED`, a finite expiry,
heartbeat and cooperative stop. The bundled system-only helper above does
not currently expose this mode; a project-specific implementation needs its
own validation. Check the API's nonzero result and retained flags, renew only
the same verified lease while work remains, and release the calling thread's
request at expiry, owner exit or task completion. Record the actual expiry in
the handoff. This does not change the power plan, override deliberate sleep or
lid closure, or demonstrate a speedup. A single successful heartbeat is only
request-state evidence; continue checking sample continuity and power events.

Renewal writes are not proof that the request remains active. After renewing,
check the same helper's PID/creation time, a fresh heartbeat, retained flags,
stderr and any completion receipt. In a Windows replay, a successful lease
update was followed one second later by a heartbeat replacement error and
helper exit. The old implementation mislabeled the exception as a stop request;
preserve stderr and record the actual terminal cause instead of trusting the
default completion label. Restart only the failed helper after verifying its
exit; keep model workers and the main R session alive.

For a project-specific helper, bound retries for transient Windows sharing
errors and release its execution-state request if the error persists. Test
replacement against a real temporary Windows handle that denies deletion,
then verify the launched helper's fresh heartbeat. That tests the sharing
mechanism, not which program caused the original failure. Startup verification
and a later clean release are separate lifecycle checks. A renewed JSON file
alone establishes neither.

## Diagnose heterogeneous CPU scheduling before changing affinity

When an engine receives substantially less than one core of CPU time despite
spare aggregate capacity, inspect per-core load and the actual Windows CPU
topology. [GetSystemCpuSetInformation](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-system_cpu_set_information)
reports `EfficiencyClass`; higher values designate faster, less energy-efficient
processors. Do not assume that a fixed logical-CPU range represents the faster
class on another machine, or infer an engine's execution core from aggregate
per-core utilization alone.

For authorized scheduling work, use the same identity-bound ongoing engines
in an original-affinity → candidate-affinity → restored-affinity comparison.
Record original masks, CPU/I/O deltas, interval lengths and competing load;
preserve data, inputs, versions and all statistical settings. In one replay,
three engines received about 79–80% of a core before, about 99% under the
measured faster-class affinity, and about 71–73% after restoration, across
three 30-second windows. Output writes continued. This supports a CPU-service
improvement for those windows, not an equal-model wall-clock speedup or a
portable affinity recommendation. Output bytes are not iteration counts.

If adopting a temporary policy, bind it to verified task workers and their
owned engines, with original masks, finite expiry, heartbeat and cooperative
stop recorded outside the model directories. Verify a newly launched child's
actual affinity before claiming inheritance. Restore parent workers before
current children so new children do not inherit the temporary policy during
shutdown. Recheck PID and creation time before restoration, including engines
whose worker has since ended. Preserve other sessions and global power policy.

Keep the whole-host slot limit and RAM/commit admission contract in force.
Do not repeatedly shrink the CPU set in response to load created by the task
itself. An isolated comparison's successful restoration does not prove that
a later long-running guard has completed its own restore path; observe and
record that lifecycle separately, and retain an identity-bound recovery path
for abnormal helper exit.

## Use measured admission budgets

Calibrate representative **worker plus child** peaks before revising a
conservative budget. Record physical and commit reserves separately. RSS sums
can double-count shared pages; private allocation is not resident RAM. Make
the reason and version of a revised budget explicit rather than lowering a
threshold until a job starts. Do not generalize a small APIM footprint to
MI, latent interactions or another data set.

Hold a shared atomic admission lock across queues; account for external Mplus
jobs, pending reservations and observed allocation. Loading a second R worker
has its own cost before Mplus starts. Gate that loading, then gate model
launches. Release reservations on verified terminal transitions. An alive
standby job is waiting, not a reason to submit another worker.

Run the host preflight **before creating a postprocessing R process**, including
the measured cost of that process in the loading budget. Repeat admission
inside the worker before loading analysis/graphics packages. Otherwise even
an idle admission loop consumes memory that the model queues may need. Report
sampled RSS as samples, not as a continuously observed lifetime peak.

If an authorized secondary worker remains at the pre-package admission stage
while estimation needs the reserve, verify its PID/creation time, stage and
absence of analysis outputs. Request its supported cooperative stop, then
observe the actual terminal response and process exit before archiving its
guard record. Keep its figures pending and preserve the unsuccessful attempt.
Check capacity again outside R before a fresh attempt; do not reuse a control
directory or stop a worker that has already entered analysis merely because an
earlier observation showed a hold. The model queues and full task remain active.

Reclaim only authorized, verified inactive workloads. Measure the effect on
Windows available RAM and commit. WSL cache reduction or working-set trimming
does not establish an equivalent Windows capacity gain; repeated purges can
cause cold reads and paging. Retain other sessions, unsaved documents and
unknown services. See [Windows resource coordination](windows-resource-coordination.md).

## Increase concurrency using a bounded original-model trial

When a measured two-slot cap leaves CPU capacity available, a third independent
model may improve throughput. First measure worker loading, engine allocation,
whole-host available RAM and commit, and competing workloads. Preserve the
statistical inputs, executable versions and declared processor settings.
Partition the remaining manifest into disjoint lanes with the same model IDs;
do not add specifications or refit accepted models to test scheduling.

Prepare the replacement runtime while existing workers continue. Request their
supported completed-model boundary, then verify actual job termination, output
hashes, independent comparisons and released helpers/leases. Freeze the trial
IDs from the first untouched rows **after that boundary**: an active worker may
have naturally claimed a provisional candidate during preparation. Selection
must not depend on fit results. Use exclusive control directories and a
one-model limit per trial lane before activating the full remaining manifest.

Require actual simultaneous owned-engine observations, all trial comparisons,
resource samples above the predeclared reserves, and clean technical completion.
A count of submitted R jobs does not establish concurrent Mplus execution.
Start the observer before a very short trial model can finish. Retain failures
and fall back to the previous admission policy for untouched work when the
trial fails; never overwrite an attempted model. Trial feasibility alone is
not a speedup estimate: compare equivalent active computation separately from
loading, readback, resource waits and sleep gaps.

In one Windows archived-APIM run, three original models passed 8,998 printed
value comparisons and the three engines were observed together. Across 283
resource samples, physical availability stayed above 1.88 GiB and commit
headroom above 10.08 GiB. This qualified that run's third slot; these values
are observations, not portable thresholds or a recommendation for other model
families. The remaining queue still requires per-model admission.

A later four-slot trial in that same archived run passed 17,160 printed-value
comparisons from four previously untouched original models. Four distinct owned
engines were observed together; 552 samples retained at least 2.09 GiB available
physical memory and 8.53 GiB commit headroom. All workers, helper processes and
reservations ended before adoption. This extended feasibility for that frozen
runtime only. A four-slot setting does not establish a fourfold speedup, and
the full queue must continue accounting for other Mplus workloads and R loading.

## Make admission failures recoverable

Keep a short shared admission transaction separate from a coordinator's
single-watcher lifetime lock. A second watcher for the same output directory
should be refused; independent workers requesting a shared model slot need a
bounded contention policy.

On Windows, reading a byte locked by another process can itself fail. Do not
use `read(1)` to inspect a shared lock file before entering the acquisition
loop. Initialize its lock byte before workers start, or inspect file size
without reading the locked range. Keep broad process queries outside the
critical section; check names and parents first, then query only the process
identities needed for admission. Bound lock acquisition and atomic-replace
retries, and preserve the final error.

Record each acquire/release subprocess's status, full stdout/stderr, attempt
number and elapsed time. `processx::run(error_on_status = FALSE)` requires an
explicit status check. Confirm release, or a verified already-absent claim,
before advancing to the next model. A duplicate claim is an ownership error,
not a transient lock failure to suppress. Preserve the original exception and
any callr error artifact before cleaning an async job's registry entry.

Test real Windows contention in separate processes, including a reader that
temporarily prevents replacement. Also exercise the R caller's failure path:
a temporary sharing failure may retry, while an ownership error must stop.
Only switch a frozen driver at a completed-model boundary. Retain completed
OUT/readback/comparison receipts and resume unfinished identities without
refitting successful models. Distinguish a recovered original error from a
newly reproduced mechanism when the earlier subprocess stderr was lost.

## Pin running helpers before updating a managed skill

A managed skill directory can be replaced by its installer. A long batch
should use an isolated, versioned copy of the required helper files and their
imported local modules, with hashes and source commit recorded separately
from the native runtime/package versions. Bind postprocessing probes to the
same fixed dependency set. Updating the installed guide must not silently
change a running model's coordinator or admission rules.

To change a frozen runtime, validate the replacement files first. Use an
existing cooperative completed-model boundary, and verify the completed
OUT/readback/comparison, released reservation, worker exit and owned sidecar
exit. Then create a new worker/control attempt with the replacement bindings.
Preserve the previous driver/configuration and failed attempts. Require
verified output hashes before skipping successful models, and record the new
real async IDs and native fitting progress. A planned boundary exit is not a
failed statistical estimate or a reason to pause the overall reproduction.

For a managed update, back up the installed manifest and use the manager's
supported single-skill operation. Verify the resulting enabled projections
against the tested source manifest and recheck the pinned runtime hashes.
Record unrelated skill records and enabled flags without changing them. Do
not scan or update every installed repository to update one skill, or bypass
the manager by editing its database. Restore any temporary manager window or
debug listener to its prior state. A window closing does not prove that its
WebView children have exited: use verified identities and actual Windows
capacity, rather than crediting their RSS as already released memory.

## Reconcile a Windows restart before resuming

Bind the assigned RStudio session explicitly before querying old async IDs: a
new agent may initially route to another live port. A missing job on that port
does not establish termination. Compare the bound R PID and creation time,
Windows boot time, old worker identities and current Mplus ownership. When a
restart is verified, retain the old IDs as history and run the workbench's
native synchronous/asynchronous smoke on the new session.

Freeze a recovery inventory before changing state. Hash-copy the stopped
control directory, interrupted attempts and completed outputs awaiting a
consumer check. Validate a complete OUT/readback rather than repeating its
estimate. Preserve an incomplete attempt separately before starting a new
attempt with unchanged input/data/executable bindings. Never overwrite the
only copy of the interrupted output.

Dead admission leases can block an otherwise healthy worker. Under the same
admission lock, recheck each recorded owner by PID and creation time, archive
only the verified dead owner's claim, and append a recovery event. Keep
unrelated Mplus processes alive and count them against the existing whole-host
limit. A fresh boot may change the limiting resource: report a slot hold, RAM
hold and active estimation separately from current measurements. Do not
attribute post-restart free memory to an earlier cleanup without evidence.

Use fresh worker/control directories and register the new real async IDs.
Keep the frozen model driver and its resource contract unchanged when only
the recovery launcher needs repair. The general
[power-loss recovery guide](power-loss-recovery.md) also covers durable queues
and checkpoints; a run-specific lease reconciliation must not be presented
as a generic queue recovery command.

## Preserve the async progress function's environment

### Recover a missing submission response before retrying

An async start timeout can occur after the R server created the worker. Treat
that outcome as unknown, retain the complete response, and inspect the same
bound session's job registry and durable attempt directories before submitting
again. In the tested ClaudeR fork, `.claude_bg_jobs` in the `ClaudeR` namespace
holds the original code, agent ID, session binding, process and progress path.
This is an internal, version-specific recovery surface: inspect the installed
implementation before using it. Match the exact submitted code, owning agent,
session and submission time; a similar filename is insufficient.

When a unique matching job exists, recover its original ID, record the actual
registry observation and poll that job through the native result tool. Save
its terminal response immediately and inspect any callr error before cleanup.
Do not label a communication error as terminal or clear the registry entry
merely because the client never received the ID. Retry only after evidence
establishes that dispatch did not occur, or after reconciling the completed or
failed original attempt. If several matches exist, retain them and resolve
their ownership and outputs before any new submission.

The tested bridge returned error text with `isError: false`, and its short
health probe sometimes reported the addin absent while an HTTP request to the
same PID succeeded. Inspect the response text and actual progress as well as
the outer flag. Prefer serial requests to a busy single R session when concurrent
health probes fail; independent OS/file checks can still run concurrently.
Reconnect to the assigned session and use the supported HTTP fallback without
restarting live model workers. Two timed-out short smoke submissions were
recovered this way; this proves recovery behavior, not a new Mplus estimate.

Inspect the timeout on the actual request path. A tested bridge used a short
generic POST timeout while synchronous execution had a different allowance.
After recovering the ambiguous jobs, a task-private copy with a longer POST
wait passed an actual independent MCP stdio sync/async chain. Installed files,
active MCP configuration and R sessions stayed unchanged. Bind that copy and
the raw responses, label the route `MCP_STDIO_OK`, and retain the failed native
gate separately. This verifies a working route, not a repaired native wrapper
or faster estimation. Keep the existing freshness and artifact checks.

Use the bound session's `R.home()`, package path and PID when running runtime
checks. A validator hard-coded to another R installation does not test that
session's runtime. If a regression fails before its dummy processes become
ready, distinguish startup timing from the cleanup/liveness assertions. Any
revised startup allowance needs an explicit bounded attempt and preserved
failure logs; retain all behavioral assertions, clean up only the test-owned
processes, and verify the original research processes remain alive. Do not
report the original short-timeout attempt as passed.

### Keep the worker callback in scope

ClaudeR makes `clauder_progress()` available in the asynchronous evaluation
environment. A helper loaded with the default `source(..., local = FALSE)`
can define its functions in the global environment instead; those functions
may then fail to find the injected progress callback. In the worker job, load
helpers into its current environment and check the callback before creating
attempt directories or starting Mplus:

```r
# worker_helper_path and config_path are declared durable paths in this job.
stopifnot(exists("clauder_progress", mode = "function", inherits = TRUE))
source(worker_helper_path, local = TRUE)
run_replay_batch(config_path)
```

Check callback visibility inside the entry function too. If an earlier
launcher failed, prove its terminal state and inspect whether it wrote an
attempt or launched Mplus before submitting corrected code. A successful
standalone progress smoke does not establish the lexical environment of a
subsequently sourced helper. This loading pattern was exercised by native
Windows ClaudeR jobs that subsequently reported real fitting progress.

## Recover consumers without refitting producers

Before skipping a model, verify input/data/executable bindings, completed OUT,
saved readback and comparison receipts. A partial OUT is not a completed fit.
Save a failed attempt and repair the first failed stage: an R extraction error
after a finished Mplus estimate normally needs readback recovery only.

`readModels()` uses dotted names in its parameter list:

```r
fit <- readRDS(model_rds)
est <- fit$parameters[["unstandardized"]]
ci <- fit$parameters[["ci.unstandardized"]]
stopifnot(is.data.frame(est), is.data.frame(ci))
# Select exact paramHeader + param identities, then require one matching row.
```

A sanitized CSV basename such as `ci_unstandardized.csv` is not the R list
field. Validate object type before row counts: `stopifnot(nrow(NULL) == 1)`
does not reject the empty logical condition. Use same-label point/CI joins;
preserve GH5 versus printed-OUT precision and the declared bootstrap subset,
strictness of comparisons and quantile type. Independently recalculate plot
data from raw OUT/GH5 before rendering complete figure groups. Keep corrected
figures isolated until manuscript adoption is authorized and scientifically
supported. See [display producer contracts](display-producer-contracts.md).

For several complete figures sharing models, read each verified RDS once per
batch and cache that model's OUT/RDS hashes. Bind every extracted row to the
same model hashes, then independently check the expected row keys and raw
OUT/GH5 values before rendering sequentially. A revised extractor must have
its own accepted filename and hash; preserve the prior version and unchanged
numerical/role checks. Claim the optimization only after a new complete data
group has actually passed those checks, not merely after `source()` succeeds.

## Count actual delivered artifacts

Use the complete manuscript object index alongside any repair queue. A repair
subset is not the full figure/table scope; PNG figure entries must not become
tables merely because their IDs do not end in `.svg`. Keep model dependency
coverage, available display rows, complete groups and delivered artifacts as
separate counts.

For each complete figure, require the frozen expected row identities and all
promised export formats with nonempty files and matching hashes. A full data
group with only SVG exported is still missing artifacts. Conversely, three
formats of a partial preview do not complete the group. Check the actual SVG
coordinates and labels and visually inspect the raster and rendered PDF.
Resolve inherited SVG styles: svglite may omit an inline black stroke because
its stylesheet already supplies it. Negative controls should alter a point,
color or bootstrap contract and update the artifact hash, so semantic checks
must detect the fault independently of hash mismatch.

Rendering can outlast a synchronous HTTP request. Save per-format start/error/
completion receipts, inspect output growth and the bound session's execution
history, and confirm the original call's terminal state before resubmitting.
Resume only missing exports from the saved plot object. Neither a timeout nor
a temporarily zero-byte SVG justifies rerunning Mplus.

## Finish acceptance before reserving the next group

A producer's terminal response and a formal deliverable check are separate
steps. Save the actual terminal response when it arrives, verify durable
outputs and process exit, then finish the numerical, geometric, visual and
formal checks. Only afterward reserve the next group under the same workbench
task key. Alternatively use genuinely independent task keys with the required
evidence for each; do not change a key merely to evade an active-job guard.

A premature next-group reservation can make the previous group's completion
check report an active in-flight record even though its data and figures are
valid. Preserve that refusal. Reconcile only a reservation proven to have no
assigned job ID, dispatch or attempt artifacts, rerun the formal check on the
unchanged deliverables, and then reserve the next group. Do not clear a live
job, repeat extraction/rendering, or rerun Mplus to make the completion gate
pass. Keep corrected completion evidence distinguishable from the original
failure, and count accepted artifacts by unique manuscript identity and
verified hashes rather than by the number of jobs archived.

Between batches, reuse a verified readiness inventory and subtract IDs in the
latest hash-linked acceptance chain. Recheck the selected producers at execution
and reject overlaps before submission and acceptance. This avoids rescanning
all old figures for each batch; it does not replace the final full-coverage and
unique-artifact audit or remove models from the authorized scope.

For complete conditional tables and delayed browser shutdown, follow
[table and browser acceptance](complete-table-and-browser-acceptance.md).
