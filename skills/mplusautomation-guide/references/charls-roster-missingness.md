# Child-roster identity before moderation or imputation

Use this when a family-level exposure or moderator is derived from child records.
Reuse valid parent-model outputs, but verify the child universe before extending
their interpretation from available reports to every listed child.

## Source identity

A legacy script can first require two valid child responses and then drop missing
child rows. Recomputing its mean and SD exactly proves that available-report
definition, not complete living-child coverage. Hash the source and compare keys,
values and the respondent scope separately.

Do not concatenate the household roster and a family-module child loop merely
because their row identifiers look different. The same co-resident child can
occur in both. Prefer an explicit constructed-child to household-member crosswalk;
do not deduplicate on sex and birth year, since twins and genuine shared values
exist. Verify the crosswalk's actual fields against both raw modules.

In the 2011 CHARLS audit, the local constructed `child.dta` supplied `childID` and
`HHmemberID`. Sex, birth year and non-household residence matched the raw sources.
The questionnaire directs household children past CB049–CB063 to CB064. CB048
belongs to a deceased-child loop; CB052 is the living-child birth-calendar item.
A generic label such as “solar or lunar calendar” is insufficient to identify
the correct loop. Check the question's surrounding routing rules.

An official listed child can have every selected response missing, so “any
nonmissing response” is not an exhaustive roster detector. Conversely, an old
valid-response row can lack a key in the constructed file. Preserve both versions
and report exact differences. Do not force equality, silently replace the cohort,
or infer the cause of a source discrepancy without evidence.

## Define absence before imputing

- No sons and one-sex-only families create structurally undefined contrasts.
  Do not impute an oldest-son contrast for an all-daughter family.
- Missing contact, sex or birth year is a different issue. Preserve child-level
  missingness and derive the family contrast after any justified imputation.
- A tied earliest birth year is ambiguous rank. Do not break ties by row order
  or use an unknown/incompatible birth month to manufacture ordering.
- If a missingness table uses mutually exclusive priority categories, state that
  these are not independent prevalences of each missing field.
- An ordinal contact score's absolute differences depend on its numeric coding;
  dividing by its mean adds dependence on the scale origin. Register scale choice
  by meaning, not by which version yields significance.

## Scoped model entry and reuse

The audit retained the published 3,006-person trajectory cohort and generated
separate complete-case pilot entries with verified roster scope. Four entries
contained 2,726, 2,156, 2,510 and 2,369 people. They are data-ready scopes, not
estimates or complete MI families. Their child-count and age distributions differ
from excluded participants; a complete-case pilot does not establish unbiased
population inference. Keep original baseline missing flags when distinguishing
complete cases from legitimate cross-wave source recovery.

Preserve existing trajectory scaling and missing masks; record the moderator's
sample-specific centering and scale explicitly. Reuse additive core/resource MI
results only for their existing purpose. A future latent interaction requires a
justified compatible imputation or joint model; convergence and small FMI from
an additive model do not supply that justification.

Independent verification should reread raw files, not merely rerun the producer.
The audit used pandas/Stata and R/haven and matched 42,084 person fields within
double precision. Private records, IDs, DAT and RDS remain local; publish only
aggregate checks and code. Do not add an Mplus run to settle a roster identity
problem or rerun an unchanged failed CFPS specification.

## From verified entries to bounded interaction pilots

Freeze the estimand, data hashes, controls, lower-order terms and runtime limits
before fitting. In the follow-up, each verified complete-case scope received a
same-sample parent and one `SX XWITH Z0` interaction. Both models retained the
baseline indicator paths `x1 y1 ON z0`; consequently the Z0-to-latent-intercept
coefficient is conditional on those paths, not the total baseline association.
The observed baseline contrast is not interchangeable with a third latent growth
intercept. Preserve this distinction in filenames, tables and interpretation.

Use the no-interaction parent as the common source for two separately specified
interaction starts. Perturb nonvariance parent starts and give the interaction
opposite signed starts. Do not resume two almost identical interaction endpoints
and call them independent starts. A second start is a diagnostic call, never a
second imputation. Predeclare numerical comparison tolerances and retain any
failure; do not introduce successively tighter checks after the batch ends.

The actual CHARLS follow-up completed four parents and eight interaction calls
in about 595 seconds of engine/launcher wall time, with one engine slot. All four
families passed their two-start pilot checks; all four interaction intervals
crossed zero. This proves neither absence of moderation nor complete MI
inference. The existing additive 20/40-imputation results remain additive results.
Their small missing fraction or FMI cannot establish interaction compatibility.
Do not launch unchanged failed CFPS specifications because a different CHARLS
sample now yields a legal pilot.

Read saved parameter vectors and TECH3 covariance directly, independently of the
R table producer. Bind path identities to raw TECH1, reconstruct the triangular
covariance, and verify standard errors before calculating conditional slopes.
For `bss + dc*z`, retain the `2*z*Cov(bss,dc)` term. Label plotted intervals as
pointwise complete-case Wald intervals, not pooled MI or simultaneous bands.
Check original outcome-missing masks and original baseline control completeness
when choosing the pilot population; previously recovered values need not redefine
the original complete-case comparator.

Publish files by explicit statistical role. `estimates.dat` and `tech3.dat` can
contain aggregate model parameters, while a neighboring `data.dat` contains
individual records. A blanket extension allowlist or CSV-row-count heuristic
cannot distinguish them. Keep the per-file role, hash and original-source hash,
redact local user paths, and independently replay the downloaded public package.
Do not duplicate the raw participant data to make the public verifier runnable.

## Audit the control's item definition before choosing MI

A nonmissing harmonized score need not mean every item was observed. The local
2011 CHARLS ADL construction sums available items when at least one is observed.
Raw db010–db015, including the documented skip rule, reproduced its item coding.
Of 3,006 participants, 2 had partial-item totals and 20 had all six items missing;
none of those 20 totals could be recovered from the same-wave raw items. Retain
the official definition and item-completeness flags. Do not silently turn partial
totals into complete totals, fill all-missing scores with zero, or call an official
partial-sum definition a coding error without a scientific reason.

In the four verified moderator scopes, residual missing core controls were only
ADL (18, 15, 18 and 18 participants). Small counts do not establish ignorability
or compatibility with an interaction model. Existing additive MI does not become
interaction-compatible because its diagnostics are favorable.

Test exact software combinations on synthetic data before expanding a queue:

- In Mplus 9, the tested single-level Bayes interaction with an ordinal control
  and `PREDICTOR=OBSERVED` was accepted, but its short chains did not converge
  and produced no usable imputations. Syntax acceptance is not MI validation.
- The tested two-level version explicitly rejected `PREDICTOR=OBSERVED`.
  This is a restriction on that combination, not a claim that all two-level
  Bayes interactions are unsupported. Removing the option can change an
  observed category predictor into its underlying latent-response predictor.
- Joint ordinal-control MLR reproduced the conditional model's complete-data
  structural paths to about 0.000004 reference SE. Adding missing ADL required
  Monte Carlo integration. Two fixed-seed 5,000-point synthetic runs reached
  their four-minute limits; neither yielded usable missing-control inference.
  Preserve both outputs. Do not turn a concrete interface correction into
  unlimited point/iteration escalation or automatically admit real data.

Record the exact error, estimator, predictor treatment, clustering, actual job ID
and runtime. A model with small RSS and increasing CPU time need not be memory
bound. Timeout accounting includes polling and process cleanup; report the
observed overhead instead of silently enlarging the original budget.

When inspecting synthetic cluster-robust covariance, its score rank is at most
the number of clusters minus one. A 50-parameter model with 40 clusters cannot
have a full-rank robust covariance. Do not misclassify this algebraic limit as
structural nonidentification or relax the real-data inference checks. A synthetic
interface test is not a scientific acceptance result.

See the official [PREDICTOR option](https://www.statmodel.com/HTML_UG/chapter16V8.htm),
[imputation documentation](https://www.statmodel.com/HTML_UG/chapter11V8.htm) and
[version history](https://www.statmodel.com/verhistory.shtml). The retained raw
Mplus output establishes which exact combination was rejected in this test.
