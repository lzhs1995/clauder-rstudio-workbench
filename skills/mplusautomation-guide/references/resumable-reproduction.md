# Resuming a Mplus replication

## Freeze the intended comparison

Distinguish continuation of an existing model manifest from a uniform rerun on
new data. They can require different estimation work. Preserve the user's chosen
baseline and record exceptions by model identity. A generated template inventory
is not the manuscript execution manifest.

For each model, preserve the original INP and DAT hashes, historical OUT identity,
expected GH5, sample and source script/template versions. Use the historical OUT
input echo to check whether a same-name INP actually represents the fitted model.
Record software versions. Equal current DAT hashes do not establish what data
existed at an earlier historical run if no contemporaneous hash was recorded.

## Recover from evidence, not an old status label

An OUT may have completed after the last audit. Reconcile actual files before
using a stored pending list. A file containing only input echo remains incomplete;
an `Ending Time` establishes an ended output, not normal convergence. A successful
return from `runModels()` also does not establish statistical validity.
On Windows, MplusAutomation 1.2 can return normally after `system(intern=TRUE)`
emits a nonzero-exit warning. With `showOutput=FALSE`, its captured console text
is discarded. Preserve the actual command output and exit status separately,
using an invocation-scoped wrapper rather than editing the package namespace.
Test both zero and nonzero command returns. An empty Windows application-event
query cannot explain or clear a recorded Mplus failure.
For MplusAutomation 1.2, `readModels(what="gh5")` can fail while assigning a
class to a still-NULL model container. Request `c("parameters", "gh5")` so the
container exists before GH5 reading. Adding only `summaries` does not fix this
ordering in 1.2. Verify with a real file before classifying GH5s as damaged.

Keep separate fields for:

| Dimension | Evidence |
|---|---|
| Execution | Owned process identity, attempt log, OUT ending, input/output hashes |
| Parsing | Nonempty required parameter/summary/indirect sections and readable GH5 |
| Diagnostics | Normal termination, fatal errors, warnings and raw identification blocks |
| Reproduction | Input pairing, sample, parameter keys, numerical values and manuscript sources |

Keep an already-ended model out of the estimation queue while investigating its
statistical warning. Retain failed attempts; retry only after an explained change
or confirmed interruption. Never satisfy a missing fresh result using a historical
OUT or GH5.

## Continuous scheduling

Prefer one persistent dispatcher that checkpoints after each model, rather than
manually submitting a succession of fixed small batches. Register the native job
ID and keep polling it. A dispatcher lock must include PID and creation time;
neither an old PID nor a live process with the same executable name proves ownership.
Persist the child identity before monitoring it. If a parent disappears, inspect
its still-live child before starting a replacement.
After the child has exited, reconcile its durable runner result with the OUT
before changing a stale `running` attempt. Missing runner evidence requires
inspection for surviving Mplus descendants. A retry exception must name the
model, prior attempt and output hash, explain the change, and expire after that
one retry. Do not convert a failed attempt into an unlimited retry loop.

An attempt directory should own one INP, its correctly named DAT, OUT/GH5 and logs.
Preserve prior attempts. Short paths avoid Windows path-length failures. For large
repeated DATs on the same volume, read-only use of a verified hard link can avoid
duplicate storage; do not modify a linked input or use it for generated output.

Monitor the R child and its Mplus descendants while `runModels()` blocks, and emit
stage/message/time progress through the dispatcher. Retain CPU changes, observed
private memory and output changes. A slow bootstrap or quiet OUT is not by itself
grounds for cancellation.
If wall-clock elapsed time suddenly increases, compare successive process-sample
timestamps before treating the model as stalled. A machine sleep can suspend both
estimation and monitoring; confirm it with operating-system power events when
available. After resume, verify the same PID/creation-time chain and renewed CPU
activity. Keep sleep time distinct from observed computation, and do not restart a
surviving model solely because its elapsed time includes that gap.

Resource admission should consider available physical memory, Windows commit and
disk headroom. Document the initial worker allowance separately from measured peak
usage, retain reserves, and raise the allowance when observations exceed it.
Thresholds depend on the machine and model; do not copy a particular project's
numbers as a universal default. Shared resources and other live sessions remain
outside the model worker's ownership.

Post-processing can have a different peak from estimation because it retains many
parsed models or bootstrap arrays. Measure its child process tree separately and
use a worker-specific allowance with headroom. Do not infer its memory budget from
one successful Mplus model. Skip already-verified rendering groups on continuation.

When new results arrive over many hours, a separate lightweight comparison observer
can check them incrementally. Bind it to the original dispatcher job ID, PID and
creation time, give it its own exclusive lock and resource admission, and stop for
inspection if that identity changes. It must never submit estimation models. Index
completed comparisons by model ID and OUT hash, use distinct batch directories, and
retain the input-status snapshot used by each batch. Persist the first native async
terminal response immediately: retrieving it may consume the job's registry entry,
so a later `No job` response is not evidence that the original job failed.

## Verification after resumption

Cache parsed objects using both input and output identities. Compare parameters
using explicit keys, reject duplicate or missing keys, and report missing sections.
A finite value becoming NA must count as a difference even though subtraction
produces NA. Missing columns and fit-statistic fields must also count; intersecting
column names alone silently loses this evidence. Preserve the numeric deltas and fit statistics; classify bootstrap,
data, sample and software differences without inventing a tolerance that makes
the comparison pass.

A partial comparison is a dated snapshot. Build current summaries by joining each
model's audit hash to its matching completed comparison, including incremental
batches; do not add raw row counts or present an earlier snapshot as today's audit.
Keep figure-validation timestamps separate when model estimation has advanced since
the last figure check. A comparison observer finishing is not full replication
acceptance, and a successful retry does not by itself explain the first failure.
Compare historical and rerun diagnostic blocks separately: a warning inherited from
the reference and a newly appearing identification diagnostic require distinct
records. Refresh input-echo, sample-difference and diagnostic reports at finalization
so they cover the final model set. For harness CSV row checks, use a supported
artifact type such as `csv_rows::...csv,min_rows=N` and inspect the returned reason;
an arbitrary type label may only prove that the file exists.

Rebuild figures from the rerun's numeric data. Record each manuscript item's
dependencies and retain diagnostics alongside its generated output. For deterministic
CSV comparisons, verify labels and row/column order as well as values. A new plot
file or a successfully parsed DOCX does not prove its numeric content matches.
Compare Word table cells in row/column order, retaining merged-cell structure,
and compare SVG labels alongside plotting data. Verify companion artifacts from
the manuscript index as well as the main exported file. Validate each model and
worker identity exactly once; row counts alone do not detect duplicate entries.

Exercise duplicate startup, interrupted output, stale pending metadata, changed
input hashes, ambiguous artifact names and missing standard errors with small
fixtures. Full replication acceptance still requires the real model and artifact
evidence; helper tests alone are not that acceptance.

## Candidate sample correction and stale output recovery

Use the verified manifest's explicit sample field and DATA FILE together. A name
such as `apimem_total_age-incc-clo_fy_step1` contains both `total` and `fy`; the
first matching token is not a sample contract. Before launch, check every generated
input against the sample, expected N/clusters, DAT hash and input hash. A correct
template example does not establish that every loop substitution is correct.

After an input correction, a previously ended OUT may describe the wrong data.
Compare the complete normalized input echo with the current INP and inspect N,
clusters, errors, saved results and the recorded OUT hash before reuse. With
Mplus input warnings, `INPUT READING TERMINATED NORMALLY` can be absent; the first
top-level `*** WARNING` or `*** ERROR` marks the end of the echo. Preserve the
diagnostic separately. Validate this parser on warned and un-warned real outputs.
Current DAT identity is still not proof of an unrecorded historical DAT.

Inventory all existing outputs, including those written after the last progress
checkpoint. Archive only invalid or interrupted attempts and retain the current
input plus the old OUT echo as evidence of the difference. A corrected INP next to
a stale OUT must fail reuse even when the OUT contains Ending Time. Keep completed
valid fits out of the retry set. Test this behavior using a genuine stale-sample
output, a truncated output and a same-name changed input before resuming.

Bind automatic post-processing to the estimation worker's PID and creation time,
and require the full manifest plus independent validation before reading results.
Use a separate lock and state file; it must not submit models. In R `ps`, convert a
numeric creation time to `POSIXct` before passing it to `ps_handle(pid, time)`.
If the bound worker exits incomplete, record an error instead of following a
replacement PID or treating a partial CSV as complete.
# Verified recovery boundary: JSON probes and retained progress

For a resumed Windows RStudio queue, separate external probe stdout and stderr,
check exit status and nonempty stdout before JSON decoding, then validate required
fields and PID plus creation time. Save each attempt's stdout/stderr and receipt;
use bounded retries for transient transport failures. Never admit a model using
an earlier successful resource probe after the current probe fails.

Load already verified progress records before iterating the manifest. Retain their
original timings and output hashes; write the entire manifest-ordered inventory
through a temporary file and rename. Replaying validation must not reset progress
to one row or re-estimate an already valid model. Use an atomic runner lock,
per-attempt resource directory and exact worker identity for dependent finalizers.
An old async handle is not a live queue; verify its terminal state and records
before recovery. Rebind post-processing explicitly, preserving its old failure.

Chapter 4 recovery on 2026-10-05 verified 200 valid records and 172 missing models.
Seven native R probe tests passed (empty, truncated, nonzero exit, missing field,
valid JSON, transient retry, real Python stdout/stderr separation). This validates
the repaired boundary; it does not prove which external call caused the original
premature-EOF failure. The recovery queue must still pass full result validation.

WSL interop sockets are runtime identities: a stale WSL_INTEROP socket can hang a
Windows Python launch while another current socket works. Inspect available
channels and validate a short Windows version probe; do not permanently hardcode
a socket number or terminate unrelated Windows/WSL research processes.

When restoring scientific status, join later quantile, historical replay and
adjudication receipts before regenerating a dashboard. Old free-text review fields
may predate completed work. Chapter 4 already had Type3/7 and PA slice replay, 38
sample-explained frozen discrepancies and two rejected manuscript symbols; a later
overview incorrectly reopened that work. Hash the receipts and preserve separate
historical-semantic, final-inference and manuscript-adoption states. Resolving a
historical display rule never authorizes copying historical values into the paper.
