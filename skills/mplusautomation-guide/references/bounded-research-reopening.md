# Bounded research reopening after manuscript closeout

Use this when the author explicitly reopens unfinished hypotheses. Preserve the
accepted manuscript and its closeout state; create a separate research root and
execution contract. A new research request does not invalidate an earlier
scoped delivery, and a successful pilot does not complete the larger study.

## Reuse and scope

- Read prior model receipts and the exact input/data identities before running.
  An unchanged failed specification is evidence to reuse, not an automatic retry.
- Distinguish latent baseline factors, observed baseline measurements and factor
  scores. Keep the requested estimand; do not substitute zero residual variance,
  class membership or a different outcome merely to obtain a legal result.
- Register all planned branch/resource combinations. Separate direct-path
  heterogeneity from a three-way interaction, retain lower-order terms, and test
  group differences directly. Do not condition eligibility on a significant
  average interaction or compare subgroup stars.
- A register written after a pilot is prospective for later work, not a claim of
  preregistration before seeing that pilot. Document its timestamp and scope.
- Single-member feasibility, a complete MI family, pooled inference and manuscript
  adoption are separate milestones. Do not average p-values, discard failed MI
  members, or predict an unrun model from another model's small FMI.

## Budget and admission

Freeze total and per-category limits, per-attempt timeouts and a small recovery
reserve. Count failed attempts and syntax-only repairs. A conservative ledger may
charge the full Rscript plus Mplus subprocess wall clock; identify that accounting
instead of calling it precise Mplus CPU time.

Inspect Windows physical and commit headroom, CPU and existing engine ownership.
MCP data preparation can overlap one estimating engine. More engine workers need
measured headroom and a coordinator that actually reserves resources atomically;
do not add workers merely because a model runs slowly. Release only owned process
trees, verified by PID and creation time, at the agreed cap. Polling granularity
and shutdown cause a small recorded timeout overrun; include it in the ledger.

In the 2026-10-15 pilot, eight attempts cost about 19.2 minutes including runner
overhead. The two CFPS derivative trials still had negative SY residual variance;
H4.1 had one legal member, H4.2 hit its ten-minute cap. Three CHARLS linear models
were legal after one input syntax repair. This supports bounded triage, not a
claim that complete moderation or H4 inference was achieved. Available Windows
memory at engine admission was roughly 3 GiB; the failed statistical branch was
not demonstrated to be a RAM shortage. This was a single engine lane with
parallel R preparation, not a multi-engine speed benchmark.

## Input and progress failures

- Token checks must consume complete numeric start values, including scientific
  notation. An exponent `e` is not an undeclared variable. Keep a negative control
  with a genuinely unknown variable so a repair does not disable validation.
- Emit each separately labelled Mplus regression as its own semicolon-terminated
  statement: `sy ON ix (bis); sy ON sx (bss);`. Multiple parenthesized labels on
  a single statement can cause an input error before estimation.
- A runner exit code of zero does not prove estimation success. Read raw Mplus
  errors before interpreting missing saved parameters as a parser failure. Keep
  the failed directory and perform a syntax-only repair in a fresh directory.
- When using ClaudeR async, source with `local=TRUE`. Otherwise a real engine can
  advance while MCP still displays only `stage=started`, because the sourced code
  lost the injected progress callback. An engine heartbeat and MCP stage are
  distinct observations. Correct the next submission; do not rerun finished
  estimates merely to repair a progress display.

## External-study measurement gate

Contact frequency and emotional closeness are adjacent constructs, not identical
measures. An ordinal frequency score is not an annual count. Audit wave-specific
residence codes before assigning a co-resident child the highest frequency:
the same numeric code can mean adjacent housing in one wave and co-residence in
another. Ambiguous near-neighbor residence does not establish daily meetings.

For CESD, inspect actual item labels and codes. Items can move between modules
or change variable numbers. Record reversal and item-completeness rules. A legacy
score that agrees on complete responses can still use a different partial-item
rule; do not describe changed missingness as proof that all legacy totals were
wrong. Rebuild the cohort for the new age/wave contract rather than importing
old age-50, constant-child-count or class-analysis selections.

Keep the source boundary explicit when reusing already filtered child-long data.
Recomputing aggregates is not a complete reconstruction of every original roster.
Resolve birth-rank ties without arbitrary row order. Preserve household identity;
one participant per household does not establish complex survey weighting.

An independent pandas/Stata check must promote float32 columns to float64 before
group means and SDs when comparing against R doubles. In the pilot, apparent
differences of about 4e-7 disappeared at double precision; do not silently relax
a substantive data tolerance or alter data to accommodate reader precision.

## Delivery

Publish aggregate reports, exact model inputs/outputs, parameter covariance and
hash manifests through an explicit per-file selection. Keep DAT, RDS, individual
scores and identifiers local. Split archives at the agreed size limit. Separate
failed attempts, adopted pilots and unrun registered models in the report.
No new NLM rounds are required merely to release a diagnostic report; a new
manuscript candidate still follows the manuscript review workflow.
# Completing an authorized MI family after a usable pilot

When the author authorizes the next family, retain the earlier pilot and
freeze a new batch contract. Check its input/data/output identities and reuse
the usable first imputation. A second-start check is a diagnostic duplicate,
not another imputation. Fill only missing member numbers; never replace a
failed member with a favorable start or call a partial family complete.

Pool the coefficient vector and full within-imputation covariance. For a
two-path group-difference hypothesis, use a documented pooled Wald/D1 test,
and form group contrasts with the cross-covariance terms. Do not average
P values or compare group stars. If only one of twelve registered tests is
available, an interim Bonferroni bound with denominator twelve can be
reported; it is not the completed family's Holm result. State the original
FCS compatibility limitations even when all members are legal and FMI is
small. Completion of one H4.1 specification does not complete H4.2 or all
dynamic moderation branches.

Measure preparation, admission, engine runtime and output validation
separately. In the Windows follow-up, ten engine/launcher calls used about
378 seconds with roughly 193 MiB peak process-tree RSS, but end-to-end work
took longer. Neither the smaller engine total nor an uninstrumented
inter-call delay establishes total duration or a memory bottleneck. Avoid
restarting fast valid models to address overhead outside the engine.

For external-cohort baseline controls, compare raw same-wave responses with
harmonized fields before silently substituting them. A source may be
complete yet disagree with the baseline response. Recover documented
same-wave fallbacks (for example reported age when birth year is missing),
retain actual missing values and record disagreements. Do not assume
reported valid-child count equals total living-child count. Keep genuine
negative household income, distinguish earnings from total income, and
separate core adjustment from resource sensitivity sets. Preserve original
trajectory missing masks for FIML; structural absence of a sex/rank contrast
is not an ordinary missing covariate. An additive-model imputation plan must
not silently become the plan for latent interactions.

## Diagnose MI cost before increasing engine concurrency

Separate time spent imputing covariates from Mplus estimation. A live R process
with several GiB available can be compute-bound; do not call this memory
exhaustion or close unrelated applications. Log individual conditional fits,
not only the first iteration of a twenty-chain batch. A first checkpoint after
all chains can leave a long computation opaque and costly to recover.

Before fitting a complex model for a sparse missing covariate, check legitimate
source recovery. In the CHARLS extension, one missing baseline sex value had
concordant responses in two later raw interviews and the harmonized source.
The analysis copy records this as longitudinal source recovery, retains the
original baseline missing mask and hashes, and leaves genuinely observed cells
untouched. This is not a general license to fill a time-varying baseline
covariate from follow-up, or to assume a harmonized field is always correct.

If conditional-fit inputs are identical across MI draws, cache **only** the
deterministic fit. Hash every fit argument; redraw parameters, conditional random
effects and PMM donors on every invocation. Never cache the completed values or
reuse one draw as multiple imputations. In an isolated worker, function copies
can wrap the fit without modifying the installed package. Verify uncached,
cold-cache and warm-cache outputs and final RNG states under the same seed.
The tested ADL case made 400 fresh imputation calls with one fit and 399 cache
hits; this optimization does not prove MAR or substantive-model compatibility.
Check convergence, observed-cell preservation, donor support and actual model
pooling MCSE separately. Retain failed or deliberately ended diagnostics.

## Windows recovery details from the extension

- A transient `PermissionError` during heartbeat publication must not kill a
  healthy model. Retry atomic replacement within a bounded interval; preserve
  the prior state and log deferred noncritical heartbeats. Critical receipts
  must still fail visibly if publication remains impossible. Save a traceback,
  because a bare error number does not identify the failing operation.
- Keep the infrastructure-interrupted attempt. Resume in a distinct attempt
  directory after verifying no owned engine remains. This is different from
  retrying an inadmissible statistical specification without a new rationale.
- Persist PID plus creation time. `ps::ps_handle(pid, time)` requires POSIXt,
  not a JSON numeric timestamp. Alternatively obtain a live handle and compare
  creation times with a documented tolerance for JSON precision. Do not treat
  a type error as proof that the coordinator has died.
- A waiting coordinator must check the other coordinator's lifetime, not only
  the gap between two engine processes. Engine locks prevent duplicate starts
  but a lock refusal is not an estimated model or a scientific failure.
- Reconcile a never-claimed receipt separately from a completed engine receipt.
  If no reservation, engine receipt or output exists, preserve the earlier
  scheduling receipt and allow first execution after ownership is clear. Do
  not cache `NOT_RUN` forever, and do not overwrite a genuine attempted model.
- Use absolute batch paths for every receipt. Move an accidentally generated
  receipt back to the isolated batch only after verifying ownership; never
  clean an unrelated directory by pattern.
- A vanilla `Rscript` does not inherit the foreground `.libPaths()`. Set the
  isolated package library explicitly and record the actual worker package
  version. Do not rerun valid estimates solely to make historical version
  metadata match a later worker configuration.

## Multi-variable MI and conditional-model follow-up

Do not carry an all-fit cache from a one-missing-variable experiment into
multivariable FCS. Other imputed predictors change between iterations, so the
conditional-fit inputs change. Reusing an old fit would change the statistical
procedure; keeping every fit can grow memory without useful cache hits. In the
CHARLS resource extension, two independent twenty-chain workers completed
twenty iterations each, with 2,400 explicitly timed, uncached conditional fits.
They produced forty actual imputations. Separate seeds, checkpoints, original
data identities and convergence diagnostics were verified before combining.

Parallel MI workers and parallel Mplus engines are different resource decisions.
The second MI worker was admitted using current Windows physical and commit
headroom; the model engine retained one owner and waited for the other
coordinator's true terminal state. Log each conditional fit and checkpoint each
iteration. A completed worker is not permission to pool before every required
worker and the combined diagnostics pass. Do not confuse the sum of engine
seconds with end-to-end imputation, waiting and readback time.

For skewed money variables, distinguish numeric conditioning from changing the
estimand. This extension linearly rescaled raw household amounts for PMM,
matched each imputed score back to an observed raw donor, and only then derived
the prespecified analysis transforms. It retained real negative income and zero
consumption. Preserve observed values and original outcome missing masks, and
report additive-FCS compatibility separately from future interaction models.
Forty chains and favorable PSRF do not prove MAR or substantive compatibility.

A new conditional H4.1 specification can differ scientifically from an earlier
failed E0/E1 model: record the exact added interaction and retained main effects.
Use legal initial values without transferring inference from their source
population. Keep the original admissibility gates and stop a family at the first
unusable imputation. In the follow-up, two new families had usable first members
and second-start checks but failed at member two. Neither a successful pilot
nor nine adjudicated families became a complete MI result. Retain the failed
outputs; do not replace members, fix variances solely to force completion, or
interpret failure as evidence of no association.

## Distinguish idle standby from slow estimation

When an engine finishes quickly but the next receipt appears much later, check
the Windows System log before blaming Mplus, R, memory or the network. In this
extension, Kernel-Power event 506 recorded Modern Standby due to Idle Timeout
at 13:43:39 UTC; event 507 recorded keyboard wake at 14:10:39 UTC. This interval
matched the approximately 1,622-second post-engine gap. The same model's
engine/launcher ran for about 23 seconds and the queue resumed without rerunning
it. Earlier unexplained gaps remain unexplained unless their own logs are checked.

Protect the entire authorized coordinator lifetime, including preparation,
readback and pooling, rather than only the Mplus child. New workflows should use
the shared [`windows_awake_guard.py`](../scripts/windows_awake_guard.py), which
verifies owner PID plus creation time and releases the request when the owner
exits or its stop request arrives. Bind it to the bounded coordinator lifecycle;
the awake helper itself is not an estimation timeout. This shared helper requests
system availability without keeping the display on. The historical PP-LGCM
helper also requested display availability and had a separate lifetime cap;
its receipts remain valid historical evidence, but it is not a second reusable
implementation. Existing running batches retain their frozen local helper.
Neither approach changes the global power plan or overrides intentional
lid-close/sleep actions. Record API success, live heartbeat and final released
receipt. Do not
claim that a successful call guarantees survival of explicit sleep, power loss,
or every battery/Modern Standby policy.

Microsoft documents the [execution-state flags and user-sleep
boundary](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate)
and [Modern Standby/DC request
limitations](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-powersetrequest).
An administrator-only `powercfg /requests` failure is not proof that the API
request failed; retain the API return and bounded guard evidence without asking
for elevation merely to print that diagnostic.
