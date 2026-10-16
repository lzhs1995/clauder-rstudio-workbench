# Source provenance and bootstrap precision

## Audit the data before optimizing the model queue

Search plausible local source paths and inspect compact metadata before calling a
historical-data gap irretrievable. A half-finished Stata dataset can preserve exact
IDs and excluded observations that a final CSV lacks. Read it without executing
the original do-file, which may contain unrelated models and destructive exports.
Freeze source byte hashes, infer the export mapping from the actual script, and
independently verify its missing-value count, selected exact IDs, renamed fields,
dummy codes and numerical export precision. A short decimal export of float32
values need not be binary-identical; state a measured tolerance separately from
exact string identity. Restrict macro resolution to definitions preceding the
specific statement; a greedy search for `missings tag` can capture an earlier,
unrelated statement. Do not overwrite an already-preserved string ID during
numeric rename projection.

Normalize cross-language Boolean fields explicitly: Python CSV `True`/`False`
can enter R as character rather than logical. Validate the allowed tokens and use
`tolower(as.character(x)) == 'true'` before `!x` or branch evaluation. One audit
runner failed before its first Mplus call on this mistake; preserve the failed
attempt, confirm no new OUT exists, and only then submit a corrected attempt.

In the Chapter 4 case, the current half-finished source had 9,748 rows, of which
9,121 exactly met the saved complete-case rule. All 98 CSV fields were reproduced;
the local CSV equaled the frozen CSV. Sibling order was deliberately omitted from
the complete-case rule. Its 4,577-row source exactly reproduced both spouses'
saved values; the forward/one-step-backward filling code added **zero** records.
Current sibling-complete records numbered 4,423, distinct from 4,397 in the old
9,028-row model data. Do not copy stale counts from comments.

Canonicalize exact spouse PIDs before counting couples across years. In this case,
9,121 couple-year records represented 4,073 couples, including 2,721 repeated
couples. A rounded DAT couple token had previously given an incorrect count.
Verify which raw PID is actually the partner: `pid_c_` did not match, whereas
`pid_partner_` and the explicit couple PID pair did. Household and couple clusters
were not interchangeable: some couples changed FID and some FIDs contained more
than one couple. A resampling-unit decision requires this dependence audit; adding
CLUSTER alone does not create clustered ordinary bootstrap.

The complete 9,748-row source supplied unique constrained candidates for all
9,028 historical DAT rows; 94 were excluded by the current complete-case rule.
This advances identity tracing, but does not prove the exact historical raw
version or that a historical OUT consumed a particular extant DAT.

## Missingness and upper winsorization in Stata

Stata numeric missing values compare greater than finite real values. A condition
like `replace transformed = upper if transformed > upper & raw != .` can turn a
missing transformation into the upper cutoff when `raw` exists. Test missingness
of the **transformed** variable itself; where appropriate use `!missing(...)` or
`< .` to exclude extended missing codes too. Verify every survey year is assigned
in the transformation, and inspect distinct values by year after each step.

The Chapter 4 script omitted the 2022 assignment for household CPI-adjusted income.
Its upper-winsor condition then changed all 1,576 nonmissing 2022 household-income
records to the same upper cutoff; 1,517 survived complete-case selection. Python
and independent R reproduced the stored transformed values and logs for all
9,748 rows exactly, including float32 storage. `centile` cutoffs in this script
matched Weibull/type-6 quantiles. This is a controlled finding for this script,
not an assumption about every Stata percentile command.

Repair only sandbox candidates. Separate adding the missing year's transformation
with frozen cutoffs from recalculating cutoffs on all eligible years. Recalculate
the declared centering/scaling and freeze all other variables for a controlled
contrast. A later full analysis must also revisit the population, resampling unit,
and any moderator constants inherited from older samples. Never transplant current
income values into an old sample without an explicit identity/data contract.

## GH5 precision, constants and BC intervals

Audit custom BC p-value formulas independently of interval reproduction. Selecting
a tail by the original estimate's sign and doubling it can exceed 1 after bias
correction. With `q = Phi(Phi^-1(M/B)-2*z0)`, distinguish that implementation from
the diagnostic two-tail expression `2*min(q,1-q)`. Do not merely clip invalid values
or call either expression calibrated for a dependent sample without checking the
resampling design. In 72 historical mediation models, 7 of 576 specific-indirect
values exceeded 1; 5 belonged to plotted paths. This does not prove those p-values
were printed in the manuscript or invalidate the corresponding CIs by itself.

Empirical `M/B` at zero and R type-7 interpolated quantiles are not exact finite-B
inverses. Four near-threshold p/CI disagreements in that inventory were explained
by inverting the same linear quantile at zero and applying the BC transformation.
Retain the declared primary criterion, confidence level, interpolation and tie
convention. Zero ties, degenerate draws, infinite z0 and nonfinite results require
explicit handling. Keep historical values, diagnostic alternatives and adopted
inference separate; a local interval inversion check is not a new estimation or
evidence that clustered uncertainty is valid.

When broadening this diagnostic, enumerate raw OUT additional labels and bind each
to its non-STDYX GH5 column. Stream one model at a time and separate constant
bootstrap parameters before evaluating bias corrections. In the 288 conditional
models, 17568 additional labels comprised 3168 constants and 14400 regular cases;
the same formula flagged 105 values above 1 and 26 threshold mismatches. Only 4
flagged parameters were referenced by plotted points/intervals. A broad diagnostic
application does not establish that every screened p was computed or published by
the producer script. Distinguish R type-7 diagnostic intervals from native printed
OUT intervals and retain point-versus-CI label bindings.

Do not infer HDF5 storage precision from an R `numeric` class. Inspect the dataset
type and element size: the tested Mplus 9 `bootstrap_data/parameters` stores 4-byte
floats. It preserves much more information than the printed three decimals, but
must be labeled native float32, not engine float64. Keep source hashes and label
the best available numerical precision honestly.

Map GH5 statements to OUT parameter names and roles rather than row positions.
Raw rows, derived indirect effects and MODEL CONSTRAINT constants coexist. A
fixed moderator probe may have SD=0 and an OUT p-value placeholder of 1. Dividing
a nonzero constant by zero produces a spurious computed p=0. Exclude fixed or
degenerate rows from testing families; do not interpret 0/0 either. In four tested
candidates, all 526 mapped testable Wald p-values computed from bootstrap SDs
matched printed OUT precision after these rows were excluded. Unmapped indirect
effects still require their own path and interval alignment.

`SAVEDATA: RESULTS ARE ...` can preserve more significant digits than GH5. Parse
the actual `RESULTS SAVING INFORMATION` layout: point estimates and SEs precede
summary statistics. Do not split the vector using the number of **free**
parameters: MODEL CONSTRAINT additions can also be saved. The tail length changes
with the estimator (MLR adds scaling information and can add a condition number).
Read all whitespace-delimited tokens; the final physical line may have fewer than
ten fields, so a rectangular `loadtxt` assumption fails. Bind the numbered
parameters to a verified TECH1/GH5 map and check every mapped estimate and SE
against its named OUT row. GH5 statement labels may append `(equality/label)`;
remove that annotation before tokenizing path names. Identical numbering alone
is not sufficient when the model specification changes.

In 20 controlled income/cluster diagnostic outputs, the existing bootstrap GH5
numbered maps plus OUT-name/estimate/SE checks bound 2,840 saved parameter rows.
Five direct-effect outputs still required an independent TECH1 map, so their
comparison remained explicitly at printed precision. Never label those unresolved
rows as full-precision simply because a RESULTS file exists.

Bias-corrected CIs require the software's quantile convention. For the four tested
1,000-draw candidates, BC probabilities `pnorm(2*z0 + qnorm(alpha))`, with
`z0 = qnorm(mean(draw < estimate))` and R quantile **type 3**, matched all 3,336
mapped printed CI endpoints. Types 1, 6 and 7 did not. Retain the cross-check
matrix and validate on the full target set before generalizing; do not silently
choose whichever convention best supports significance. Preserve 90% versus 95%
rules. Empirical bootstrap Wald p, BC intervals and adjusted BH/BY results are
different quantities. Full testing families must include eligible nonsignificant
effects, but exclude constants and avoid duplicate aliases.

Ordinary Mplus bootstrap does not establish validity for repeated couple-years.
`BSEED` belongs to Bayesian estimation documentation and `OPTSEED` concerns
optimization starts; neither is evidence of independent ordinary bootstrap samples.
Use a documented resampling mechanism and save external samples/seeds if needed.

Cluster-robust MLR with delta-method intervals is an independent sensitivity route,
not clustered BC bootstrap. Verify both unchanged ML point estimates and the
actual reported number of clusters after missing-X exclusions. The Chapter 4
corrected-data examples returned 4,073 couple clusters (1,933 for sibling-complete
rows), or 3,957 connected family/person components (1,921 sibling-complete).
All ten checks preserved point estimates, and the four mediation examples had
target-SE median ratios around 1.19–1.21 versus unclustered ML; some unadjusted
Wald flags changed. This establishes dependence sensitivity in those examples,
not restored CFPS population design, full-family correction, or main-text release.

## Resource and termination evidence

Poll the original async job and observe CPU service on owned Mplus descendants.
During the tested sequential bootstrap, the owned Mplus processes received roughly
one CPU-second per wall-second after performance-core/AboveNormal coordination;
this supports good single-core service, not a multi-core speedup claim. Record
actual sampling and budget peaks. Guard against double-counting the resident R
worker in incremental memory admission.

A coordinator's Python `finally` block is not guaranteed to run if the enclosing
Windows job tree terminates with its R worker. An absent coordinator-terminal
file is not proof the coordinator is still running. Verify PID plus creation time,
the parent job's terminal result and any surviving adjusted children, then save an
independent process-closure receipt. Do not kill a reused PID or another chapter's
process. A Windows-open log can return PermissionError; inspect its identity and
sample sidecars before assuming a crash.

Evidence in the dissertation R-analysis workspace:
`scientific_audit_20261002/evidence/source_provenance_summary.json`,
`evidence/family_income_bug_summary.json`,
`validation/native_source_bootstrap_checks.csv`,
`validation/bootstrap1000_precision_checks.csv`, and
`validation/bootstrap1000_BC_algorithm_checks.csv`.
# Rank source extensions and identity orientation

An exact identity match does not validate a derived source value. The two
reverse-key candidates were subsequently checked against explicit source actor/
partner IDs and the original 2010 adult questionnaire. For one person, age 28,
one sibling aged 26, and zero coresident siblings imply oldest (1), while the
extension stores middle (2). The other person's coresident sibling age remained
unverified. Both candidate rows therefore remain unadopted. Do not force a value
from an incomplete age roster, and do not extrapolate a discrepancy in an
alternate source to every value in the current validated source. Preserve source
hashes and the failed comparison as evidence, not just successful matches.

Before repeating source reconstruction, read existing provenance evidence. A
larger alternate source is not automatically a better replacement: Chapter 4's
26,090-row extension matched 4,363 current records, versus 4,423 for the validated
4,577-row source. Exact forward keys recovered no new rank values. Two current
missing records matched only after swapping exact nine-digit spouse IDs while
preserving the four-digit year; actor/partner values must then swap too before
mapping to female/male roles. Save such candidates separately with adoption false
until source generation and applicability are verified.

Analytic DAT surrogate IDs need not equal original 22-character CID strings.
Use the validated source identity crosswalk; zero direct matches is not evidence
that original records do not exist. Never coerce long identities to floating
point to manufacture matches. Original comment counts (e.g. 5,161) can differ
from observed source counts (5,171); comments are not execution logs. See
`reports/EXTENDED_RANK_SOURCE_REVIEW.md` and its evidence ledgers.
