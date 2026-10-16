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

Reclaim only authorized, verified inactive workloads. Measure the effect on
Windows available RAM and commit. WSL cache reduction or working-set trimming
does not establish an equivalent Windows capacity gain; repeated purges can
cause cold reads and paging. Retain other sessions, unsaved documents and
unknown services. See [Windows resource coordination](windows-resource-coordination.md).

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
