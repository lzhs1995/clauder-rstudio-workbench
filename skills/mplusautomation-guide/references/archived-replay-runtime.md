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
