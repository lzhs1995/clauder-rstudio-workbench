# Candidate compilation, likelihood reuse and saved precision

## Preserve the scientific contract while compiling

Freeze source hashes and write candidate inputs separately. Record every change:
data/cohort, scaling, controls, estimator, clustering and probe assignments.
Preserve original labeled paths, constraint names/equations and endogenous
residual relations; validate these independently before estimating. A compiled
input is not a scientifically approved specification.

Classify PWITH pair by pair. One statement may contain separate endogenous–
endogenous and exogenous–exogenous pairs; deleting the whole statement can remove
required residual relations. Distinguish this from an actual cross-role pair.
Normalize covariance pairs before counting; diagonal mentions, duplicate syntax
and unique free parameters are different quantities.

Some legacy USEVARIABLES lists end implicitly at DEFINE. A compiler must stop at
section boundaries, then emit an explicit semicolon. Stable-partition raw NAMES
variables before DEFINE-created variables without changing DAT column order.

Share immutable DAT files where cohort and column definitions match. Use paths
relative to the model directory and verify resolution from the actual execution
location. Long absolute paths can exceed Mplus input line limits; in the tested
candidate dialect, lines were wrapped at 85 characters and checked at <=90.
Do not apply text wrapping inside quoted paths or split tokens blindly.

Physical phase subsetting changes the interpretation relative to survey-domain
analysis. State the selected population and preserve the distinction; deleting
SUBPOPULATION is not evidence that domain inference has been recovered. Likewise,
TYPE=COMPLEX/MLR delta intervals do not replace BC or cluster-bootstrap intervals.

## Establish reuse by parameter identity

A static likelihood signature should bind DAT hash, active variables, DEFINE,
ANALYSIS, regression/covariance relations and repeated-label equality groups.
Exclude MODEL CONSTRAINT formulas only after verifying that they define NEW
outputs without constraining estimated parameters. Reject syntax the restricted
canonicalizer cannot interpret, including unsupported fixed/start expressions.

Matching signatures justify a reuse experiment, not automatic result reuse.
Independently estimate representative aliases and compare sample, objective,
free estimates, SEs and covariance after permutation by physical parameter keys.
Labels and derived effects can differ even when the fitted likelihood matches.
Retain each model/effect identity; recompute and validate its own derived effects.
Never manufacture alias OUTs or count reused likelihoods as independently run fits.

The Chapter 4 static check grouped 612 candidates into 372 signatures: 252
singletons and 120 triples, with a possible 240 avoided fits. Numerical reuse
was still unverified at this checkpoint; this is not a measured speedup.

Subsequent independent fits of two representative pairs confirmed equal saved
loglikelihoods. One pair matched exactly; the other differed by at most 4e-9 in
free estimates, 1e-9 in SE and 1e-11 in printed covariance, after matching physical
parameter identities. Independent Python arithmetic confirmed these differences.
This supports the restricted signature's reuse plan, not a universal theorem
about superficially similar Mplus syntax. All identity-specific derived effects
still require reconstruction. Counting the two verification-only repeats gives
374 planned independent fits for 612 identities, a net 238 avoided fits rather
than the original theoretical 240. This is fit-count reduction, not measured
end-to-end wall-time acceleration.

## Read the actual RESULTS layout

Read RESULTS SAVING INFORMATION in each OUT. With STANDARDIZED enabled, the
observed layout has eight vectors: unstandardized estimate/SE, STDYX estimate/SE,
STDY estimate/SE and STD estimate/SE, followed by fit-summary fields. Do not reuse
a helper assuming two vectors. Check lengths and field names against that OUT;
do not hard-code this layout for all estimators or software versions.

Use TECH1 numbering for parameter identities. In the observed path model,
alpha identifies intercepts, beta identifies directed regression paths and psi
identifies residual variances/covariances. This is not a universal latent or
categorical model mapping. Preserve equality identities and all relevant groups.

The tested MplusAutomation TECH1 additional-parameter object was empty even
though the raw OUT numbered additional parameters. Inspect and parse the raw
PARAMETER SPECIFICATION FOR THE ADDITIONAL PARAMETERS block; an empty parsed
component does not prove absence. Match estimates and SEs to named printed rows
before releasing a precision export. Buffer a complete model until checks pass.

For the age/income/age-gap/fy pilot, 110 free plus 70 additional parameters gave
180 positions and 1,460 saved numbers (8*180+20). The additional parameters
include deterministic probe constants. Full TECH3 singularity can therefore be
structural and is not by itself an identification failure. Review the free
parameter block, constraints and raw diagnostics separately. TECH3 is printed
precision; computations from it retain that rounding limitation.

TECH1 may return matrices directly or under a group such as X. Normalize the
actual schema before extracting; do not assume a single fixed list depth.
The observed TECH3 parser supplies only the lower triangle and leaves the upper
triangle NA. Verify that the diagonal/lower triangle are finite and the upper
triangle is entirely absent, then mirror the lower triangle for permutation or
matrix operations. A direct max(abs(A-B)) otherwise returns NA; na.rm=TRUE can
hide a genuinely incomplete matrix. Preserve failed comparison evidence and
rerun post-processing only, without re-estimating Mplus.

The ten completed pilots/aliases subsequently passed 1,404 one-to-one mappings:
TECH1 ID, physical parameter, saved unstandardized estimate/SE and printed OUT
row. Every difference was within the OUT three-decimal rounding interval.
The example above's layout is therefore validated within this ten-model scope;
it is not a validated exporter for all future model types.

Standardized vectors contain 999 missing/unavailable sentinels in this output.
Decode them according to the output's field convention rather than treating
them as coefficients or globally replacing every numeric 999 in source data.
Saved numeric precision does not turn MLR/delta uncertainty into bootstrap
uncertainty, nor resolve data, sample or model-identification questions.

## Evidence and remaining checks

Task-relative evidence in scientific_audit_20261002:

- validation/unified_input_contract.json and unified_input_contract_checks.csv:
  612 candidates, three DAT files, 9,480 original labeled paths retained.
- validation/unified_likelihood_groups.json: static grouping only; numerical
  equivalence and deduplication flags remain false.
- evidence/unified_pilot_progress.csv: eight terminal attempt records with
  expected N/clusters and parsed outputs, all scientific_released=false.
- experiments/unified_declared_controls_v1/models/
  mod_apimem_total_age-incc-ag-clo_step1_fy/candidate.out and results.dat:
  raw TECH1 and RESULTS layout example; full export validation remains pending.

Follow-up evidence: validation/unified_precision_checks.csv,
unified_alias_equivalence_checks.csv and unified_pilot_alias_independent.json;
scripts/export_unified_precision.R, compare_unified_aliases.R and
validate_unified_pilot_alias.py. The follow-up supersedes the pending export
status for these ten outputs only. The two workers and coordinators were
independently absent by their recorded PIDs; no successful coordinator finalizer
is inferred from that absence.

## Reconstruct each alias's own effects

Read labels from that alias's actual candidate INP and bind each to the
representative's directed physical parameter. Re-evaluate the candidate's NEW
assignments with its repaired probe constants; do not copy the representative's
derived values or reuse old expanded expressions containing historical moments.
Use the preserved MODEL INDIRECT expressions only where their labeled paths
remain verified. Include nonsignificant paths and constants in the audit ledger;
exclude actual constants only when defining the testing family.

Sparse forward derivatives can evaluate the restricted arithmetic dialect
without importing a large symbolic stack. Reject unsupported syntax and cycles.
Validate gradients with independent finite differences and re-evaluate all
candidate expressions in native R. Evaluate delta SE from the corresponding
permuted free-parameter covariance. Printed TECH3 plus saved point precision is
an approximation to engine-internal arithmetic; retain the approximation in
column names and do not promote a component of rounding error to a complete
uncertainty bound. Covariance rounding alone omits coefficient rounding and
uncertainty hidden by printed zero entries.

The follow-up snapshot contains 16 independent fits representing 14 likelihoods,
from which 24 model identities and 1,435 effect rows were reconstructed. Raw
engine comparison remains limited to effect identities actually estimated;
aliases without independent OUTs are reconstructed, not independently fitted.
No full-family adjustment or scientific release follows from this partial table.
Scripts: reconstruct_unified_effects.py and validate_unified_reconstruction.R;
scope and check files: validation/unified_reconstructed_effect_scope.json,
unified_reconstructed_effect_checks.csv and unified_reconstruction_native_checks.csv.

The two sibling pilots explicitly exclude 4,698 (total) and 2,394 (fy) records
with missing exogenous variables. Their retained N are 4,423 and 1,247. Preserve
these warnings even when expected sample counts match. A terminal job, parsed
output and expected N do not constitute manuscript adoption or independently
verified worker/coordinator closure.


## Maintain a resumable unified-candidate queue

When a long candidate queue is interrupted by a manifest or progress-schema bug,
preserve the failed job, identify any output that was actually completed, and
verify its OUT hash, ending marker, parsed RDS, sample size and cluster count
before removing it from the pending queue. Do not rerun that completed model.
The repaired manifest must contain explicit `expected_N` and
`expected_clusters` columns, stable input/DAT hashes and a distinct queue
version. Register a new async job only after the guard has passed; a stale
`pre_submitted` record is not an active estimate and must not be submitted a
second time.

For a running queue, read the unchanged job id and the durable progress CSV.
Each completed row must be checked against the frozen manifest and the current
OUT hash; a row with `parsed_ok` is still only an execution/reading record.
Keep `scientific_released=false` until the candidate's data, estimand, cluster
assumption, diagnostics, interval type, testing family and manuscript mapping
have all been reviewed. Snapshot completed rows in batches rather than hashing
all outputs after every progress message, because Windows file access can make
an otherwise harmless audit compete with the active Mplus worker.

The 2026-10-03 queue-v2 recovery retained one completed v1 model and estimated
the remaining 363 representatives under the same isolated candidate contract.
Its progress and validation files are task evidence only; they do not license
reusing the remaining likelihood-group results without a physical-parameter
mapping and an independent numerical equivalence check.

## Freeze completed outputs before precision review

When a queue is still estimating, make a byte-stable completed snapshot from the
pilot, alias, recovered, and current progress ledgers. Recheck each selected
OUT hash, Ending Time, expected N, and expected cluster count before writing the
snapshot. Record the progress-file hashes and source-script hashes in the
snapshot manifest. The snapshot is a review input; it is not a replacement for
the live queue and must never be used to infer that unfinished candidates have
finished.

Export `RESULTS SAVING INFORMATION`, TECH1, and the printed lower-triangle
TECH3 covariance in small chunks to a separate review root. The exporter should
write `precision_parameters.csv`, `precision_covariance.csv`, and a parsed RDS
per model, then verify the source OUT hashes again before closing the chunk.
Keep a chunk completion record with the model range, parameter count, elapsed
time, memory observation, and source-manifest hash. A representative precision
cache can cover alias identities only after the identity-specific INP labels and
NEW expressions have been re-evaluated.

Reconstruct effects from each candidate's own labels and constraints using the
representative's physical parameter map and covariance; compare available
identities with an independent finite-difference or native-R calculation. Keep
the reconstructed effect table and checks under the same isolated snapshot.
Their estimates and delta intervals are numerical audit evidence, not BC or
cluster-bootstrap inference, and do not set `scientific_released=true`.

For a new data-sensitivity candidate, prepare identity-specific input copies for
every alias as well as estimated representatives. A 372-fit inventory covering
612 model identities still needs 612 label/constraint contracts for reconstruction.
Store those copies separately from the live estimator's input directories, check
each alias sample against its representative, and verify representative copies
have identical hashes. Changing only a DATA FILE reference must leave the rest
of each identity's syntax unchanged.

Use the same estimator and extraction pipeline on both sides of a sensitivity
comparison. Compare new Mplus/TECH3-derived effects with the frozen Mplus/TECH3
baseline; using an independently optimized kernel baseline can mix solver
differences with the intended data change. Exercise complete-family adjustment,
alias mapping and CSV/plot generation on a separately labeled baseline-self
fixture. Its zero difference tests the pipeline, not the substantive candidate.
