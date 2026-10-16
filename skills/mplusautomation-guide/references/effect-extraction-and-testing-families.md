# Effect extraction and complete testing families

## Typed, named extraction

Check the schema of each `readModels()` component independently. In the tested
MplusAutomation build, the unstandardized parameter table was numeric while
`indirect$unstandardized$overall` and `$specific` contained numeric-looking
character columns. Explicitly convert estimate, SE and p-value, reject conversion
failures, then perform arithmetic. A working parameter parser does not validate
the indirect parser. Preserve the actual package version in `sessionInfo()`.

GH5 may name a covariance `A WITH B` while the OUT table names `B WITH A`.
Permit exactly one symmetric fallback for WITH; do not reverse directed ON paths.
Check uniqueness, remove the literal `(equality/label)` annotation when present,
and validate point, SE and p against the named printed row. Map specific indirect
effects by predictor, mediator and outcome, and independently check coefficient
products; an ordinal label such as `Specific indirect 1` is insufficient alone.

A long worker executes the code loaded at submission. Editing the disk script
does not repair a running worker. Cache lightweight parsed models, allow useful
models to finish, retain the terminal failure list, and rerun only those IDs with
a separately named repair progress file. Merge attempts by model ID and retain
both histories. Do not re-estimate Mplus merely to repair post-processing.

## Parameter numbering and precision boundaries

Prefer actual numbered GH5 statements or TECH1 to an inferred order. Match every
saved point and SE to its named OUT row before using RESULTS precision. Additional
NEW parameters follow declaration order, which can differ from assignment order.
`Number of Free Parameters` does not include every saved derived parameter.

A one-iteration, isolated TECH1 probe can establish numbering for that structure;
its estimates are not analysis results. In a continuous path-model probe the
alpha/beta/psi ordering was verified, but orphan observed variables in sibling
models appeared in a separate leading parameter block. Covariance-coverage order
alone therefore does not establish universal matrix order. Keep failed inferred
maps as diagnostics and use the independently numbered GH5 map where available.
Latent, categorical and equality-constrained models need their own mapping rules.

An original OUT without `RESULTS SAVING INFORMATION` has no corresponding native
RESULTS precision to recover through that route. Report this explicitly instead
of crashing at a string split or borrowing estimates from another run. Printed
p-values give rounding intervals, not exact probabilities; a printed 0.000 is
not proof of zero probability. Preserve precision uncertainty in downstream
multiple-comparison sensitivity.

Buffer an entire model's proposed rows and append them to the aggregate only
after all mapping and numerical checks pass. Otherwise a failed model can leave
partially trusted rows in a seemingly complete file. Write source hashes once per
model rather than rehashing a large RESULTS file for every parameter.

## Freeze the family before adjustment

Build the effect inventory from the actual INP equations and declared research
scope, including nonsignificant results. A contract constructed during an audit
is a **post hoc audit contract frozen before adjustment**, not preregistration.
Record family and sample membership, model ID, effect expression, source data,
parameter paths, constant status, canonical zero hypothesis and aliases.

Symbolic polynomial expansion can detect expressions whose zero nulls differ
only by a nonzero constant. Count that null once within a model while preserving
the separate estimates and confidence intervals. A continuous/binary high-minus-
low indirect contrast can be a nonzero multiple of an index of moderated
mediation. Do not double-count these aliases or discard their distinct effect
scales. Do not collapse effects across different outcomes or samples merely
because their labels match. Exclude genuine fixed constants, not effects merely
because a computed bootstrap SD happens to vanish.

Three-category effect-coded `IM...` terms can represent deviations from an
effect-coded reference, not a continuous moderation index or high-minus-low
contrast. Read the expressions. Reconstruct AA/AP/PA/PP from the actual spouse
paths and interaction DEFINE statements, not AAM/PAM suffixes. In a verified
case, `hi0pam1 = a_A2 * b_P1` traces Xf→Mf→Ym (AP), whereas
`hi1aam1 = a_P1 * b_A1` traces Xf→Mm→Ym (PA).

Validate symbolic expansion independently by substituting multiple coefficient
sets in R and comparing original and expanded expressions. This verifies algebra,
not the substantive appropriateness of the model or the correctness of captions.
The Chapter 4 audit checked 35,268 effects across 612 models using 70,536 R
substitutions; maximum absolute discrepancy was 4.45e-16 or less.

Compute BH/BY only after reconciling every eligible null in the frozen family.
Preserve the exact p-value source, rounding uncertainty where applicable, and
90%/95% conventions. A BH/BY-adjusted Wald p-value is not an adjusted BC interval.
The four-candidate BC type-3 agreement does not establish full-target validity:
validate every target endpoint, retain exceptions, and investigate quantile ranks
and float storage without choosing whichever interval supports significance.
Passing any correction cannot release models with unresolved data, sample,
identification or dependence problems.

## Rebuild testing units after changing the probe contract

Changing sample/scale/probe constants can change exact zero-null equivalence
without changing any effect label. Recompute the full candidate equations before
reusing a historical canonical-test column or BH/BY denominator. Freeze this
post hoc audit rule before adjustment and use no fitted p-values to select it.

In the unified Chapter 4 candidate, all 612 model identities and 35,268 effects
were retained and 70,536 independent R substitutions verified the expansion.
Literal within-model unique nulls became 26,664, versus 26,424 historically.
The 240 membership changes occur in 60 child-moderator models: 160 reflect phase
means that differ from zero on the common full-sample scale; 80 arise from a
full-sample mean literal near 4.08e-17. Preserve these as different explanations.
Do not call a floating residual a substantive scientific change, and do not
silently merge mathematically different hypotheses using an arbitrary tolerance.
Keep exact and any scientifically justified ideal-centering sensitivity separate;
never change running INPs just to make a testing-family count convenient.

Where multiple model identities share one verified fitted likelihood, identical
physical-parameter nulls can recur across identities. Restrict cross-identity
grouping to the same declared testing family, the same full likelihood signature
(including data/sample/options), and the same physical-parameter polynomial
(ON paths in this audited dialect) up to a nonzero constant. A common label, coefficient or p-value is
insufficient. Keep every display identity and its effect scale; choose the
canonical test deterministically without seeing p-values. Distinct units are
not statistically independent tests.

The candidate contract identified 2,400 additional repeated null counts across
equivalent model identities, leaving 24,264 testing units. Four independent R
coefficient scenarios checked proportionality in all 4,416 duplicate groups.
Approximate nulls were not merged. This is an analysis-specific contract, not a
universal instruction to collapse tests across different models or samples.

Assess availability against the entire frozen unit inventory for each family.
Only adjust a family after every required canonical unit has a finite valid
p-value. Partial results in another family must not reduce its denominator.
The first expanded snapshot supplied six complete families and 2,064 units;
their BH/BY values matched R p.adjust, while the other six families stayed
unadjusted. MLR/delta p-values from saved points and printed TECH3 remain
approximate and do not become BC intervals or scientific adoption after FDR
adjustment. Preserve all aliases and their p-value agreement checks.

Evidence under scientific_audit_20261002: ledger/unified_effect_contract.csv,
unified_null_change_explanations.csv, unified_testing_units.csv,
unified_family_coverage.csv; validation/unified_native_effect_contract_001_612.csv,
unified_testing_units_native_summary.json, unified_complete_family_adjustments_native.csv,
and unified_family_validation_current.json. Historical ledgers were hash-checked
and preserved.

## Bind candidate evidence to the manuscript inventory

Keep three sources distinct: the frozen manuscript's actual cell, the audited
prior reproduction, and the newly fitted candidate. Comparing the latter two
does not resolve a frozen-cell/source disagreement. Preserve historical N,
prior-reproduction N, candidate N/clusters, named effect identity, data/input
hashes, point/SE and both 90%/95% interval sources side by side.

A common effect label does not establish a common estimand when scale or probe
position changed. If data repair, control equations, sample, scaling and
uncertainty changed together, label a different CI classification as a joint
specification comparison, not attribution to one repair. A prior printed-zero
endpoint remains unresolved at that precision. Exclude fixed constants from
testing comparisons, and distinguish effect-record counts from unique tests.
Never relabel an old BC interval or a constructed table SE as the new cluster
MLR/delta result.

Build review rows for every required manuscript item, including rows whose
candidate is still pending. Verify order, model/effect identity and each old/new
numeric field against its proper source. Bind companion coverage to the relevant
main item without claiming that its Word/SVG/PDF artifact has been rerendered.
In the 67-fit checkpoint, 121 candidate identities/4,750 effects supported 1,172
of 5,328 display rows across the preserved 279 main items and 209 companions;
16 main items had all their display rows ready. This established review-data
coverage, not manuscript adoption or original-figure visual acceptance.

Task evidence: ledger/model_adoption_stage5.csv, item_adoption_stage6.csv,
companion_adoption_stage5.csv and unified_vs_prior_effect_review.csv;
validation/unified_adoption_review_checks.json. The two independently implemented
binding/readback scripts are build_unified_adoption_review.py and
validate_unified_adoption_review.py.

For items whose candidate rows are complete, retain a separate item-level
inference review: list old interval sources, candidate N/clusters for each
model, unchanged/changed 95% classes, unresolved boundaries and constants.
Keep exact display-row and model/effect keys for every exception. A path
displayed in both a figure and a table counts twice as a display row, not as
two hypotheses. Do not use this summary to overwrite scientific release flags.
In this task, `scripts/review_ready_items.py` produces
`ledger/ready_item_inference_review.csv` and
`ledger/ready_item_interval_changes.csv`; the first is an editorial review
queue, and the second retains the numerical evidence needed to inspect it.
Neither substitutes for a direct comparison against frozen manuscript cells.

Evidence: the task-local `scientific_audit_20261002/ledger/effect_contract.csv`,
`validation/native_effect_contract_all.csv`, per-model `evidence/effect_cache/`,
`validation/parameter_numbering_checks.csv` and `BC_endpoint_discrepancies.csv`.

## Match the displayed point, interval and path together

Use anchored whole-parameter matches, for example `^(HI1AAM1|HI1A1M)$`.
Unanchored `HI` also matches `VHI`; unanchored `LO` also matches `VLO`.
Normalizing either name to the same extracted substring before a join can create
many-to-many records. Taking the first row then hides the mismatch. Check join
cardinality and retain the original full parameter name for both point and CI.

A verified Chapter 4 PA example displayed a VHI point at approximately +2SD
with an HI interval at approximately +1SD, while its low point was LO at -1SD.
The displayed high-minus-low difference consequently did not represent the
declared TIE=HI−LO contrast. Neither a correct OUT parser nor a complete file
inventory detects this: compare every table/plot row to one named effect and
its probe expression. State the actual moderator values, not just H/L.

Word companion tables may use long or wide schemas, and different precision.
Inspect headers; do not assume a `sample` column exists. Preserve cell location
and original text, use the actual printing tolerance, and distinguish ambiguous
numerical matches from verified semantic identity. A conditional table SE in one
post-processor was constructed as `(upper90 - estimate)/1.645`; with asymmetric
BC intervals this is not the empirical bootstrap SD. Trace its generating code
before presenting it as a model SE.

Map mediation table labels from predictor→mediator→outcome, with an explicit
definition of whether husband/wife means the source or the outcome person.
The tested friendly-name dictionary assigned some AP/PP labels to different
actual paths. Check the original label transformation as well as numerical
matches, and include all nonsignificant paths in the repair.

GH5 plot availability does not imply bootstrap availability. Of 600 GH5 files in
this audit, only 360 contained bootstrap draws; 240 other models used RESULTS
with independently validated matrix numbering. Preserve normal versus BC CIs.
For the tested normal outputs, critical constants 1.645, 1.96 and 2.5758 reproduced
all audited target intervals at printed precision. Full 143,160-row-endpoint
checks retained one nuisance residual-variance boundary exception, and one
nuisance Wald p exceeded the nominal half-print tolerance by 4.43e-7. Do not
generalize these constants to every software version or disguise these exceptions.
The direct models' printed P/Z sensitivity bounds retained a documented 1e-6
numerical guard; they are not recovered exact engine probabilities.

The complete bootstrap check covered 547,416 endpoints, including MODEL INDIRECT.
All 136 exceptions were nuisance means/variances/covariances and compatible with
float32 rounding intervals changing ranks near the point estimate. This bounds
lost rank information; it does not recover the original double-precision draws.
There were no exceptions among the audited target effects. The complete-family
BH/BY calculations passed 66 independent R `p.adjust` checks; they still did not
release the source-income or repeated-couple inference gates.

For large pandas ledgers, avoid one retained Series/DataFrame group per effect;
use lightweight tuples or a compact keyed index. Access columns such as `sample`
with brackets because attribute notation can resolve to a DataFrame method.

### Controlled replay of AP/PP selection

The follow-up audit replayed the original `merge(..., sort=FALSE)` plus unanchored
regex and first-row selection in isolated R, without sourcing the destructive
original plotting script. All 684 AP/PP companion rows reproduced their point,
two interval endpoints and constructed SE. In child-moderator models the AP
script incorrectly selected `HI0A1M/LO0A1M` instead of the corresponding P path;
the PP script similarly selected `HI1A1M/LO1A1M`. This changed path class in
54 AP rows and 60 PP rows. Separately, 132 AP/PP rows selected VHI/VLO. Do not
describe every discrepancy as the PA point/interval mixing defect: these are
distinct, potentially overlapping mechanisms.

Scope summary tables by the manuscript item's outcome. In this audit, three
reproduced summary files each contained all four outcomes and were linked from
12 separate manuscript tables. Bind each item's 24 relevant combinations and
144 cells rather than treating every row of the shared file as belonging to
each item. The 1,728 scoped symbols matched named TIE type-3 interval decisions;
the original type-7 calculation is a separate convention check. Likewise, a
correct significance summary does not validate the parameters selected for its
accompanying plot.

The all-model replay compared type 3 and type 7 on the same actual GH5 draws:
2 of 2,304 TIE classifications differed across 288 models. The 1,728 cells above
are scoped **reproduced exports**, not the frozen manuscript's displayed cells.
All match full-draw type 3; one differs from full-draw type 7. Exact source replay
resolved that discrepancy: the PA code selects `V3:length(bcboot_data.df)` after
a merge, combining a shifted starting column with a pre-merge numeric endpoint.
It drops the final nine draws. All 576 PA symbols match this original slice:
574 use 991 draws and two use 990. Full-draw type 7 changes one symbol. Its lower
95% endpoint is approximately -0.00003098 under full-draw type 3, +0.00005314
under full-draw type 7, and -0.00001541 under original-slice type 7. Reproducing
the bug proves fidelity, not the correctness of the interval procedure. Select
bootstrap columns by verified names/identities, assert draw counts before and
after joins, and keep any corrected convention in a separate candidate.

Read the frozen DOCX XML separately and bind document hash, table numbering,
row, column and outcome. Here 12 manuscript tables display 1,044 effect cells;
684 of the 1,728 candidate cells are absent, not nonsignificant. There are 40
frozen-versus-reproduced symbol differences (39 sibling, one parental support).
They span 25 historical models; 38 are compatible with printed historical CIs,
but only 17 are decisive at printed precision. Compatibility does not identify
the original producer or resolve an endpoint printed as zero. Preserve the
document's real symbol dictionary and its 90%/95% distinction. This ledger uses
zero-based `table-N`; frozen XML table numbering is N+1. Never apply that offset
to another document without checking its inventory.

Evidence in `scientific_audit_20261002`: `validation/PA_draw_slice_reconciliation.json`,
`validation/PA_original_function_all.csv`, `validation/frozen_summary_reconciliation.json`,
and `ledger/frozen_summary_difference_sources.csv`. Subsequent exact original-function
replay of the 25 historical GH5 files reproduced 38 of the 40 frozen symbols;
all 38 belong to models previously classified as sample differences. An independent
standard-library Python BC/linear-quantile replay agreed within 1.53e-16. This
binds historical results to those symbols; it does not prove sample size alone
caused every numerical change or release the historical estimates for reuse.

Two frozen cells remain inconsistent with the bound historical original rule:
`table-15`, frozen row 27/column 3 (`edu-hw-sibg-clo_step1_fy`, `TIE1AAM2`) is
90%-only in the manuscript but 95% under that historical rule; `table-20`, row
12/column 7 (`edu-hw-dw1-eco_step1_sy`, `TIE0PAM1`) is 90%-only in the manuscript
but nonsignificant under the historical rule. Retain them as table/source
discrepancies, not sample-change explanations or licensed automatic manuscript
edits. Evidence: `validation/frozen_historical_replay_checks.json` and
`ledger/frozen_historical_source_disposition.csv` in the same audit root.

Display-repair candidates must retain exact model/effect keys, matching point/SE/CI
sources, original values, item scope, and an explicit non-release status. Verify
them independently against the numeric ledger and source hashes before rendering.
Coverage of 279 items and 209 companions does not resolve data, identification,
dependence or multiplicity gates; never upgrade scientific adoption because the
candidate file exists or its copied numbers agree.

### Audit structural roles before changing parameterization

A dictionary of labeled effects omits unlabeled adjustment regressions. Parse
all MODEL statements, including multiline `ON`, paired `PWITH`, cross-product
`WITH`, explicit means/variances, and DEFINE interaction factors. Strip block
comments before line comments. Preserve every endogenous residual covariance;
flag mixed endogenous/exogenous covariance separately rather than silently
classifying it as removable. Compare parsed variables and labeled edges against
independent existing ledgers, and require zero unparsed statements for this
restricted input dialect. This is not a general-purpose Mplus parser.

In the Chapter 4 scan, 612 input hashes, 27,894 variable memberships and 9,480
labeled edges matched the independent ledgers. The full scan included 46,518
regression edges and 35,292 explicitly requested covariance pairs. The 144
distribution-only variables were DW1F/DW1M in 72 models. This identifies a
structural question, not a causal answer: whether parental support belongs in
these regressions requires a substantive control-variable contract. Do not
delete it merely because warnings disappear. Syntactic covariance-pair counts
are also not the same as free-parameter counts or missing OUT parameter rows.

Normalize unordered WITH pairs, separate diagonal mentions and deduplicate
non-diagonal relations before semantic interpretation. Here the 35,292 syntax
pairs contain 4,284 diagonal mentions and 14,292 duplicate non-diagonal mentions,
leaving 16,716 unique relations: 972 endogenous residual and 15,744 exogenous
distribution relations. A cross-product WITH combined with repeated PWITH can
otherwise create a false claim of several distinct residual covariances. Do not
infer mediator–outcome residual correlations from that expansion. Evidence:
`validation/covariance_role_normalization.json` and `ledger/unique_covariance_roles.csv`.

Evidence: `ledger/full_model_role_contract.csv`, `full_variable_roles.csv`,
`full_regression_edges.csv`, `full_covariance_roles.csv`, and
`validation/roles_and_display_crosscheck.json` in the task audit. All original
models remain unchanged and scientific adoption remains on hold.

### Recover a lost async response without duplicate submission

A failed `execute_r_async` response does not establish that no job started.
Check the exact R parent and child process identity, task-specific durable files,
and recent `clauder_async_progress_<job_id>_*.rds` paths in the bound R session's
`tempdir()`. Read these as RDS, not text. Recover the real job ID and poll it;
never manufacture an ID or submit another copy based on a communication error.

A terminal poll can itself consume the result before its response is lost.
If a later poll says `not_found`, reconcile complete durable outputs, independent
coverage/values and the owned worker PID before closing the guard. Label a lost
terminal response honestly; file/process verification is not a recovered native
console receipt. In one verified replay, the 684-row output passed native R
checks and the worker had exited; no duplicate job was submitted.

WSL `UtilAcceptVsock ... accept4 failed 110` is an interoperability failure, not
an R analysis failure. Read-only probing found `/run/WSL/2_interop` usable in
this environment, and a command-local `env WSL_INTEROP=/run/WSL/2_interop` restored
the approved Windows Python. Discover and verify a live socket on the current
machine; do not hard-code this socket globally, restart WSL/RStudio, or reinstall
Mplus to repair the transport. Keep HTTP fallback evidence distinct from native
MCP evidence, and protect other sessions and processes.
