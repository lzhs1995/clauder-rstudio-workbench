# Scientific checks beyond artifact identity

## Interaction figures

Identical SVG text identifies a candidate source, not scientific acceptance.
Word expands CSS and converts polylines to paths. PyMuPDF can ignore svglite
stylesheet defaults and produce black rectangles. Preserve that diagnostic;
expand supported styles in isolated copies, then compare numeric geometry,
colors, line widths, dash patterns, labels and rendered pages independently.

Bind each graph through its export block, data object and preceding readModels
call. Reused object names and suffixes can conceal a different intercept/slope
model. Resolve X, W and Z from actual ON labels and XWITH definitions before
assigning axes and legends.

For Y = b0 + b1*X + b2*W + b3*Z + b4*X*W + b5*X*Z + b6*W*Z + b7*X*W*Z,
the conditional slope is b1+b4*W+b5*Z+b7*W*Z, and the conditional intercept
is b0+b2*W+b3*Z+b6*W*Z. Correct slope labels do not prove correct vertical
position. A 0/1 moderator must not become -1/+1 only in the intercept formula;
retain WZ regardless of significance. A common baseline normalized to zero
must be described as a conditional reference, not an unconditional prediction.

For direct moderation, audit factor order as well as slope labels. Character
groups `High` and `Low` sort alphabetically: named colors combined with unnamed
legend labels can reverse the displayed group meanings. Set explicit 0/1 factor
levels and bind every legend label to that level. Verify LOW/HIGH additional
parameters against the actual MODEL CONSTRAINT expressions. Preserve firstborn
versus oldest-child semantics in axes even when both outputs use internal S4.
Check the final combined color/linetype legend visually; a correct line in the
panel does not guarantee a correct legend key.

## Multiple-imputation likelihood comparisons

Before declaring target outputs missing, bind each table row by its interaction
estimate/SE and both marginal-interaction estimate/SE pairs across the full
existing main-model inventory. Then verify with native readModels and actual
ON/XWITH syntax. Manuscript X/W labels may swap intercept and slope: the
PP-LGCM audit recovered all 25 exact LRT pairs after correcting 12 such target
selections. Preserve the superseded missing-target audit as forensic history.

Audit all targets and each null/alternative pair: used fields, participants,
data, estimator, distribution declarations, restrictions, parameter counts,
convergence and positive scaling correction. Adding observed means/variances
only to the alternative changes the likelihood. Do not repair negative
statistics with absolute values. Reuse valid alternatives and estimate only
the required comparable nulls.

Compare imputation sets by participant and all used fields. Exact permutations
preserve symmetric pooling; document the permutation and retain the earlier
index-mismatch diagnostic. Current sidecars are weaker evidence than immutable
execution receipts.

For an explicitly selected D2 method, preserve implementation/version,
complete-data statistics, pooled F, degrees of freedom and p-value. One
imputation's successful prototype is not final MI inference. Do not average
p-values.

Normal termination alone is insufficient. Inspect warning blocks for saddle
points, negative residual variances and nonpositive information matrices.
Missing-x exclusions need sample accounting, not automatic rejection; verify
the same retained sample in null, alternative and main models. A negative raw
D2 F can arise from between-imputation dispersion, but it must never mask
invalid estimates. Preserve the computational result and exclude it from
reportable inference when estimation diagnostics fail.

Record requested and effective estimators separately. Mplus may explicitly
reject MLF with TYPE=COMPLEX and fall back to MLR. The printed Estimator and
fallback warning establish what actually ran; a requested-input difference
does not itself prove a different effective estimator. Other warnings remain.

Build an explicit interpretation matrix: valid pooled model comparison,
three-way interaction threshold, and at least one conditional two-way
interaction threshold. Distinguish p<.05 primary findings from p<.10 exploratory
findings. Do not infer a difference from one significant simple slope and one
nonsignificant simple slope, and do not describe nonsignificance as no effect.

MplusAutomation 1.3 compareModels(show="diff") can fail with undefined
bayes_outputs. The local verified workaround is show=c("summaries","diff");
read diffTest$MLR_LL and verify with an independent formula. Pin background
library paths explicitly; isolated foreground libraries may not be defaults.

## Sample availability and binary-score lineage

Validate scale scoring before treating successful reproduction as scientific
acceptance. Read raw item labels and response codes, reconstruct the score by
participant, and compare it with the actual model input. A reverse-coded
negative item and an unreversed positive item can reproduce every historical
output while invalidating the construct. In the CFPS 2012 audit, the erroneous
score matched all 3,274 final participants; correcting the item reversal changed
2,593 scores. The manuscript alpha matched the correctly scored items, not the
score used in analysis. Alpha reported in prose therefore did not validate the
model input. Check whether the erroneous score also predicts imputed variables:
if so, replacing only the outcome columns in existing MI datasets is insufficient.

Audit every wave independently before limiting a repair to baseline. Check raw
item labels, complete-item scoring, official totals where available, and exact
missingness. Recompute reliability on the stated analytic denominator. A uniform
score translation leaves baseline-standardized values unchanged; a wrongly
reversed item does not. Preserve the original score scale and explicitly describe
any equivalent translated scale in the manuscript.

For rank-based child contrasts, separate source reconstruction from rank validity.
Check that stored flags select an age maximum among eligible children, then retain
same-age ties as measurement uncertainty. A baseline tie with equal closeness can
produce different contrasts in later waves when the child-specific values diverge.
Keep the historical child identity and availability gate fixed in the primary
reconstruction; do not silently replace one selected child with a tied-child mean.
An eldest-son contrast may compare the oldest son with all other children,
including daughters, rather than only with younger sons.

A missing predictor absent from IMPUTE does not by itself prove case deletion.
Inspect the printed dependent/independent-variable contract and all saved MI
members: unique participant IDs, original observations, fields actually filled,
and missingness intentionally retained. Preserve that selective-imputation
specification during an isolated measurement repair unless a separate documented
statistical change is authorized. New imputations need their own readback.

Before regenerating MI, compare every producer input column with the selected
current analysis dataset. Replacing just the known erroneous scale in a legacy
input can retain older rank values, missingness and standardization. Archive that
candidate as superseded and build a new isolated input from the fully selected
dataset when full-column alignment fails. Never claim a historical saved-MI
roundtrip passed when its adjacent producer input has since changed. Use exact
participant identity, original observed values, intentionally retained missingness,
categorical domains and printed numeric precision in the readback contract.
Preserve the TECH8 PSR sequence: the presence of saved imputations does not prove
that the last printed diagnostic satisfies the intended convergence rule.

Propagate measurement errors through actual selected fields and MI/factor-score
dependencies. A pure-closeness model need not be re-estimated solely because CESD
was corrected, but its selected inputs, participant set, source specification and
diagnostics must match the corrected analysis version. An old manuscript match
can coexist with a different current-data result; keep both versions and explicitly
select the current source-bound estimate for a rebuilt current-data manuscript.

For externally joined factor scores, distinguish modeled USEVARIABLES from bare
AUXILIARY fields that are only carried into SAVEDATA. An old outcome in a saved
auxiliary column need not invalidate the factor-score estimate, but it must not
be copied into a corrected downstream dataset. Check auxiliary statistical
options, DEFINE, sample-selection, weighting and grouping before making this
distinction. Export only the verified participant key and needed scores.

Bind each consumer to its exact R output block and actual readModels source.
Filename prefixes can conceal a switch between absolute and relative contrasts.
Inspect whether standardized variables are merely computed or actually assigned
back to the joined score columns. Preserve raw scores, mean splits and median
splits as different contracts; for the documented binary rule, values equal to
the threshold belong to the low group. Record the threshold sample and R quantile
type. A first-imputation comparison is representative evidence, not validation
of all saved imputations or the final corrected merge.

Reconstruct sample flow from executable filters and compare participant sets,
not only totals. Distinguish baseline missingness, all-wave missingness and
having at least one usable wave. Read the exact counting expression: a child
count after dropping missing closeness may also omit children with missing sex.
Equal counts across waves do not establish identical children across waves.

For a two-stage binary moderator, identical model syntax and a median-cutpoint
comment do not establish identical input. Compare the actual binary columns
across main-model and LRT datasets after resolving imputation order. A change
in factor scores can change binary classification even when both producers
use a median threshold. Do not attach a pooled LRT to a main-model figure until
this identity check passes. In the CFPS follow-up, all four historical pairs
passed initial nesting checks, but two failed main-data identity and a third
had negative S1 variance in every null-model imputation. Only the fourth passed
the combined historical D2 checks. Significant D2 candidates alone were
insufficient.

## Raster and Word verification

Some SVG rasterizers drop dashed line patterns. Verify the PNG fallback as
well as the SVG; the local rsvg renderer preserved patterns that PyMuPDF lost.
If several drawings share a paragraph, do not append an identical note to the
next heading once per drawing. Insert one independent note per figure group.
After extending a caption, bind the figure paragraph and intervening empty
paragraphs to the caption and inspect the exported PDF. Recheck source hashes,
Word object counts, and unchanged table XML after each isolated revision.

## Submission sequencing

A failed resource admission must stop dependent submission. Inspect the exit
code before calling R; R must revalidate a fresh receipt. Preserve timestamped
admission attempts, including failures. Parallel orchestration must not turn
a failed precondition into a best-effort submission.


### Binary support, score coverage, and native Windows path checks (2026-10-01)

- A binary moderator supports conditional effects at 0 and 1. A dense 0.05 plotting grid must not be interpreted as observed intermediate groups or a continuous Johnson–Neyman region. Preserve fitted model equations while reporting endpoint contrasts.
- Preserve the source R join semantics. An external score source can omit participants with all source indicators missing; verify the exact omitted PID set against current indicators, retain MI rows through the documented left join, and preserve missing scores. Never silently fill them with zero or drop those rows.
- Python file creation is insufficient proof that Windows R or Mplus can read a path. Use short isolated model directories and verify all file paths and hashes from the assigned native R session. The PP-LGCM 264-character template paths failed R file.exists and were superseded by short-path v2.
