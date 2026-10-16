# Execution and Validation

Use the workbench connection, native-smoke and resource gates before formal jobs.
List sessions, bind the intended one, and keep synchronous calls short. A timeout
does not show that the addin died. Probe the same session and inspect its worker
before restarting anything. Never replace the local fork with upstream merely
because upstream has a newer version number.

Submit long work once through execute_r_async. Call clauder_progress(stage,
message) before each model and processing phase; poll the same job ID. Save the
job mapping and unique absolute runModels log path per worker. Process memory,
CPU deltas and child-process identity supplement the log, especially while
bootstrap output is buffered.

```r
MplusAutomation::runModels(
  target = isolated_inp,
  Mplus_command = configured_mplus_executable,
  logFile = unique_absolute_log,
  replaceOutfile = "always",
  killOnFail = FALSE
)
```

This command is for an input owned by the current run. Do not recursively run a
historical project tree. Existing output existence or modification time alone
does not prove successful completion. Before scheduling a restart, check the
owned worker/process and its final output, and retain any incomplete attempt.

Validation has separate levels:

1. Execution: current-run logs, process completion, fresh OUT and expected sidecars.
2. Parsing: nonempty parameters and required summaries/indirect/GH5 sections.
3. Diagnostics: normal termination, convergence and all model warnings/errors.
4. Reproduction: matched INP/DAT identities, N, parameter labels, estimates, SEs,
   CIs and original table/plot numeric sources.
5. Scientific adoption: data-population validity, identified target effects,
   defensible uncertainty and manuscript-level claims. See
   [scientific-reliability-audit.md](scientific-reliability-audit.md).

Keep an ending timestamp and the literal normal-termination marker in separate
fields. Exact reproduction may preserve unreliable standard errors; neither
parsing nor reproduction is a scientific-adoption pass.

For MplusAutomation 1.2 request `what=c("parameters","summaries","warn_err")`.
The parser selector is `warn_err`; asking for `warnings` and `errors` can leave
those objects absent. Absence of an unrequested object means unchecked, not zero.
The bundled `scripts/inspect_output.R` demonstrates this check.

Also inspect the raw estimation diagnostic block. Version 1.2's parser can omit
the non-positive-definite first-order-derivative warning if it is not preceded by
a recognized WARNING or termination line. The helper retains that raw block in
`raw_diagnostics`; an empty parsed errors list does not override it.

`MODINDICES` ignored with BOOTSTRAP is an input warning. Non-positive-definite
derivative matrices and potential nonidentification are model diagnostics that
must stay visible even if estimates and figures are available. A no-bootstrap
diagnostic is not a replacement for an authorized bootstrap model.

Bootstrap and Mplus-version differences can affect intervals. Store numeric
deltas and classify them alongside input/version changes; do not invent equality
or acceptable tolerances. Historical OUT/GH5 caches must never fill missing
new-model results in a purported full rerun.

## Harness receipt pitfalls observed during a scientific audit

### Raw variables must precede DEFINE-created variables

When adding controls, stable-partition USEVARIABLES into variables present in
NAMES followed by newly created DEFINE variables. Appending a raw control after
an interaction causes Mplus input rejection. Assert unchanged variable membership,
equations and DAT bytes for an ordering-only repair; do not reorder NAMES or DAT
columns as a shortcut. Preserve rejected INP/OUT/logs and give the retry a new
attempt identity. In the Chapter 4 control diagnostic, two of seven attempts
produced outputs and five were rejected for this ordering error. Retry only the
five rejected attempts; completed outputs still require their own diagnostic
review. Input rejection is not evidence that the scientific specification fails.

The five order-only retries subsequently completed with normal markers, unchanged
DAT hashes and matching parent sample sizes. Three retained the expected warning
that 4,698 records with missing exogenous variables were excluded (N=4,423).
Do not turn a narrow diagnostic screen returning false into “no warnings.” Search
explicit warning/error markers and diagnostic phrases, retaining adjacent lines;
the bare word `ERROR` also matches “Standard errors” and “Root Mean Square Error.”
Evidence: `scientific_audit_20261002/validation/control_diagnostics_v2_terminal.json`
and `evidence/control_raw_diagnostic_lines.csv` under the same audit root.

### Progress scope and process closure

For a sourced async script that uses injected `clauder_progress`, use
`source(path, local=TRUE)` in the environment containing the helper, or explicitly
pass the helper into a chosen environment. `local=FALSE` can hide the helper from
the sourced code, leaving only start/final messages despite actual computation.
Require intermediate native MCP-visible progress for meaningful long phases;
CPU activity is useful supporting evidence, not a substitute for stage reporting.

A native terminal result does not prove the resource coordinator has exited.
Check the owned worker and coordinator by PID plus creation time and preserve
their terminal receipts. Short input failures may fall between resource samples;
record unobserved CPU/RSS as unknown, not zero. A one-second owned-child discovery
interval can capture short models without repeatedly rescanning unrelated work.

In this control run both coordinator terminal files were absent, but read-only
process inspection proved that both workers and both coordinators no longer
existed. Record this as independently verified process closure, not as a successful
coordinator finally-block receipt or a known cause of its missing file. Reusable
lesson: persist process identity at launch and do not depend on child finalizers
as the only shutdown evidence.

Small CSV/hash/linear-quantile validators need not import pandas/NumPy/SciPy.
Two observed Windows validators had low CPU time and approximately 0.55/1.01 GiB
private memory; their imports were avoidable. Use csv/hashlib/statistics/math when
they cover the calculation, independently check numerical agreement, and measure
memory before claiming savings. When deliberately replacing a running validator,
record its command, PID, creation time, resource state and terminal status first;
do not terminate a similarly named process or any RStudio/Mplus session. A timeout
alone is not evidence of failure and is not a reason to repeat an estimate.

Interpret CPU per wall second against the configured processor count. Seven
observed single-processor Mplus diagnostic processes sustained roughly 0.99 CPU
seconds per wall second, with sampled peak private memory below 0.48 GiB. Low
whole-machine CPU percentage therefore did not mean these jobs were idle. Keep
this evidence local to the measured models; it neither proves memory adequacy
for larger bootstrap jobs nor demonstrates that increasing PROCESSORS speeds up
this estimator. Benchmark a representative unchanged input before generalizing.

Low CPU in an auxiliary worker may be scheduling starvation. One owned probe
validator had only about 63 MiB private memory, a Ready thread, and inherited
`below_normal` priority. After binding its exact command/PID/creation time and
restoring `normal`, it completed. Preserve the observation and prior setting;
do not blame RAM or terminate/restart the worker solely because a poll is quiet.
For a task-specific Windows self-priority wrapper, declare ctypes HANDLE argument
and return types explicitly and check SetPriorityClass/GetPriorityClass results.
Only change the owned process; leave Mplus, other chapters and global scheduling
policy intact. No REALTIME/HIGH elevation is needed for a small validation worker.

Propagate the observed worker-plus-Mplus peak budget into the next model's
admission check and into a new queue's initial budget. Writing worker_budget.json
without reading it, or resetting it to a smaller default in a fresh coordinator,
does not implement adaptive admission. Subtract only the current worker's actual
resident/private allocation from the corresponding RAM/commit budget; preserve
explicit system reserves. In the Chapter 4 follow-up, the probe itself inherited
BelowNormal; restoring only its own priority to Normal was recorded as
probe_prior_priority=16384 and probe_priority=32. A normal-priority helper is not
permission to raise all Windows processes or stop other chapters.

Validate a queue's full record schema before the first estimate, not only its
row count, input hashes and R parseability. A generated manifest omitted
expected_N/expected_clusters; Mplus completed the first model, but data.frame()
then failed with "arguments imply differing number of rows: 1, 0". Recover that
completed OUT/RDS against the independent sample contract, preserve the failed
queue, and submit only the remaining models with a new attempt identity. Do not
repeat the successful fit to repair its progress row. The corrected runner checks
required columns, complete values and positive expected sample/cluster counts.
On Windows, specify UTF-8 explicitly when reading Chinese-commented R scripts;
the process locale may otherwise choose GBK and abort a preparation helper.

### Harness arguments

For the local Workbench harness, `--parent-evidence` takes evidence file paths,
not bare evidence IDs. `doctor` checks configuration and is not a `preflight`
receipt. A separate MCP stdio preflight remains `MCP_STDIO_OK`; retain real native
smoke evidence as the parent for a native-wrapper claim. Use the supported CSV
artifact kinds `manifest`, `validation` or `csv_rows` so row checks run. Invented
artifact-kind names fall back to generic file checks and a 1-KiB durable threshold,
which can incorrectly reject a small, valid validation table. Preserve failed
receipts, correct the contract, and report a phase-specific evidence PASS without
calling the entire scientific analysis complete.
