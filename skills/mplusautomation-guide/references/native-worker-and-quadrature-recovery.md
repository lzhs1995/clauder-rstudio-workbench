# Native RStudio recovery and bounded latent-interaction execution

This record supplements the existing recovery runbook. It documents a Windows
CHARLS batch after the CFPS scoped manuscript closeout; it does not reopen failed
CFPS specifications or establish that the original four moderation families or
full H4 have been tested.

## Recover the actual job, not a guessed process name

The live native ClaudeR background worker was `Rterm.exe`. A preflight accepting
only `Rscript.exe` was too narrow. Accept documented R worker executable names,
then bind the native job ID, submitting agent, exact code, RStudio session,
worker PID, creation time and parent chain. A name alone is insufficient in
either direction. Preserve other RStudio sessions.

The first startup attempt returned a nonzero setup status before any model
reservation or Mplus call. Its Python stderr was not captured. The overly narrow
name test was a verified defect, but it is not a uniquely established explanation
of that first exception. Preserve the original failure and this uncertainty.

The recovery used a bounded handshake: the native worker wrote its PID before
loading packages and waited up to 120 seconds for its own preflight receipt.
Windows-native Python, invoked through the authorized shell, checked the real
native owner and selected available CPUs. The native R interface's rejection of
generic system commands was respected; no dynamic-call bypass was used.

A production handshake must include the job/attempt identity and creation time
in the permit, use an exclusive attempt directory, and reject a permit from an
old attempt. Polling the same native job continues through normal `running`
states. A bridge error or an outer `isError: false` response is not a terminal
worker result. Read-only reconciliation must precede any replacement submission.

## Separate the phases and their budgets

Record startup, preflight/resource wait, engine launch, engine termination,
readback, pooling and native terminal consumption separately. An estimator cap
starts at the actual engine child, not at a progress announcement or package
load. A shell tool returning a session ID is also not a completed preflight:
wait for its exit code before the dependent submission.

The model adapter used the direct child handle, awake-time budget, preserved
stdout/stderr, exact input/data hashes and an atomic two-slot admission mutex.
Unknown Mplus processes cause a hold and are not killed. Failed members stop
their dependent family; another independently eligible family can continue.
Never replace a failed imputation or combine a successful subset as the planned
complete family.

Frequent progress is append-only. Critical admission and terminal receipts use
bounded Windows file-replacement retries. A live monitor records real model
CPU, RSS/private memory, host physical/commit headroom and owner identities;
it does not equate a stagnant UI with nonconvergence. Keep numerical and
resource errors separate.

An owned awake helper needs an explicit stop request and a bounded wait before
the native worker exits, followed by inspection of its release receipt. A
process ending does not prove that its helper wrote `completion.json`. Do not
claim tested recovery after parent crash or deliberate sleep from this normal
shutdown test.

## Improve throughput without selecting results

For the same scaled three-process model, the old STANDARD trapezoid rule timed
out. A new bounded contract changed the quadrature rule to GAUSSHERMITE(7), used
two independent parent-based starts, then checked 15 points from the respective
7-point solutions. These refinements are not new independent starts.

All four complete-case indicator calibrations passed independent raw
TECH1/RESULTS/TECH3 checks. SD used four calls/508 free parameters; the remaining
three used a scaled parent plus four interaction calls each, 634 parameters per
indicator. Each interaction fit had 127 free parameters. The numerical checks
compared all coefficients, standard errors, the full robust covariance matrix
and saved/printed likelihoods. Saved likelihoods have limited printed precision;
do not call them an independently measured high-precision optimum.

The preset 0.05-reference-SE and covariance tolerances are project quality
criteria, not universal statistical theorems. The rule change is a different
numerical approximation and requires precision checks; it is not a license to
reduce integration accuracy until a coefficient is significant. No variance
was fixed to zero to obtain these results.

In this host sample, other logical CPUs were heavily loaded while physical and
commit headroom remained. Only verified owned Mplus children were raised from
Normal to Above Normal, with original values recorded and surviving children
restored on monitor shutdown. Do not use Realtime, stop unknown tasks, or claim
a controlled speedup from uncontrolled before/after timings.

## Readers and MI must preserve the scientific boundary

Mplus RESULTS and TECH3 are free-format streams. A rectangular `loadtxt`
assumption failed; whitespace-stream parsing recovered the existing output.
Readback or import repairs require no re-estimation. Match TECH1 parameter
identities, not just array positions, and preserve the failed readback record.

An input guard must distinguish an entire variance statement `SY@0;` from a
zero covariance within `IY WITH ... SY@0;`. A substring match incorrectly
rejects the latter. Correcting the guard before launch changes neither model.

For this subsequent interaction batch, the earlier additive auxiliary MI was
not silently relabelled interaction-compatible. A fresh, bounded ADL-only
working MI added the 25 observed X-by-Z products and their missingness flags.
All 80 exported datasets passed independent preservation checks. This is a
conditional working imputation model, not proof of MAR or exact substantive
compatibility with a latent interaction. A deterministic one-variable fit cache
retains fresh parameter/donor draws; it does not count cached fits as independent
imputations.

Complete-case numerical calibration, complete MI estimates, pooled inference,
the original hypothesis coverage, manuscript adoption, guide publication and
local skill installation have separate completion states. The present full-MI
model queue was still active when this draft was written; its eventual outcome
must be supplied by terminal receipts, not inferred from CC success.


Mplus documents STANDARD and GAUSSHERMITE integration in the [official Chapter 16](https://www.statmodel.com/HTML_UG/chapter16V8.htm). The local evidence hashes and scope are in [the evidence manifest](charls-gh-recovery-evidence-20261019.json).

## Followup: foreground process diagnostics can block the interface

The execution agent repeated a failure pattern already documented in the
recovery runbook: a broad `ps::ps()` enumeration and per-process CPU/affinity
queries were submitted through synchronous foreground R. The call returned an
HTTP error with outer `isError: false`; short native probes then said the addin
was not running, and a Windows HTTP fallback timed out. This was a diagnostic
placement error, not evidence that the statistical models failed.

Targeted native Windows handles showed the same RStudio and background-worker
PIDs still alive, TCP8787 still accepted connections, and the original Mplus
jobs continued growing CPU/output evidence. The operator did not restart R,
replace a job, edit the bridge, or touch the other RStudio session.

The owned RStudio parent, executable, creation time and window were verified.
An initial Escape PostMessage proved only message delivery. A later attempt
temporarily restored and acquired that same window, checked foreground identity
before sending Ctrl+2 and Escape, then restored the earlier window/focus state.
This was limited to the operator's known read-only diagnostic. Do not apply it
to an unknown user analysis or infer that posting a key means recovery.

Subsequent HTTP execution returned200/success with the original R PID. Rebinding
the existing native session then returned a real R response, and polling the
original two job IDs showed further completed members. The sequence proves
same-session recovery; it does not uniquely isolate natural completion,
PostMessage, console interruption or binding refresh as the cause.

Routine foreground probes must stay short. Broad process inventories belong
in a bounded external helper with immediate start/PID evidence. Keep interface,
estimation and durable-output states separate. Preserve actual failed probes,
ownership/interrupt intent, HTTP success and native success instead of recording
only a final green status.

## Measure the stage before tuning resources

The completed batch contained 80 main imputation fits plus four start checks.
Existing stage logs measured 268 seconds of compilation/setup, 11713 seconds
inside runModels (including wrapper/admission/launch/engine), and 203 seconds
of result readback across 84 calls. Their per-call medians were 3, 137 and 2
seconds. Engine awake time summed to 11084.29 seconds; two concurrent queues
spanned 6271 wall seconds from first compilation to last pooling.

This was an observational stage audit, not a controlled speed benchmark.
Do not add parallel queue durations to report batch elapsed time, subtract
sleep-excluding engine time from wall time and assign the remainder to one
cause, or claim a memory bottleneck from a single free-memory snapshot.
Readback was a small part of this batch; removing statistical checks would
not address the dominant estimation cost. Reuse actual stage evidence and
preserve the frozen model/numerical contract when deciding the next change.

The same-batch aggregate evidence is published at [charls_latent_interaction_models_delivery_20261019](https://github.com/lzhs1995/PP-lcgm-paper/tree/579c7a4f73948cbc7b5ef5167fa2b72e7a2a5495/charls_latent_interaction_models_delivery_20261019). `RUNTIME_RECOVERY.md` and `RUNTIME_RECOVERY_EVIDENCE.json` preserve the sequence; the model packages separately identify complete working-MI families and any stopped families. Original CFPS moderation coverage and full H4 remain incomplete.
