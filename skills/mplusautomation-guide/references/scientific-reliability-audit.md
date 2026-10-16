# Scientific reliability after reproduction

## Cross-stage sample identity

Use character fid/cid/year keys to compare records across DAT files, after checking
within-file uniqueness and source hashes. Distinct rows in stage partitions do
not imply independent clusters. The Chapter 4 full samples partitioned 9,121 rows
but shared 559 spouse clusters between stages; rank-observed samples partitioned
4,423 rows with 262 shared clusters. Stage-difference SEs require their covariance
or a joint cluster procedure, not an independent-sample formula.

All 612 candidate models and 279 main manuscript items were linked to six actual
selection sets. 132 rank models select exactly those rows where both spouse rank
codes are in 1/2/3; excluded rows have both ranks missing. Every 2016/2018/2020/2022
wave has included and excluded records, so a wholly unmeasured wave is not the
explanation. This still does not establish missing-at-random or the source survey
skip rule. Do not present code availability as population representativeness.
Read `reports/SAMPLE_IDENTITY_SCOPE_REVIEW.md` and the linked ledgers. Preserve
the historical 72-model sample-difference category separately from these current
132 restricted-sample model identities.

## Adjudicate frozen source conflicts without inventing history

Re-read the actual DOCX XML cell and verify manuscript, OUT, GH5 and replay-script
hashes. Inventory item IDs are not XML table numbers: in Chapter 4, table-15 is
XML table 16 and table-20 is XML table 21. Preserve neighboring rows and merged
cell coordinates. Compare exact 90/95 endpoints and the tested quantile rules
before blaming rounded zero endpoints or a copied symbol.

Two frozen partial-significance markers contradicted both bound historical and
current reproduction outputs. One historical 95% interval excluded zero; the
other 90% interval included zero. Mark those frozen claims unusable for current
adoption, without copying old significance markers into the final manuscript.
This disposition can be made while the exact historical editing cause remains
unknown. A March 11 manuscript filename and March 13/15 replay-script filenames
do not prove which script generated the manuscript or establish a manual typo.

Read sample counts from each row: one conflict had historical/reproduced N
3579/1247, the other 5449/5449. Do not borrow another sibling model's N or confuse
the old reproduction with the new unified candidate sample. Equal N is not
equal row identity. Generate report counts from the ledger, then independently
read them back; Python CSV booleans may reach R as strings and require explicit
normalization. Evidence: `reports/FROZEN_SOURCE_CONFLICT_ADJUDICATION.md`,
`ledger/frozen_source_conflict_adjudication.csv` and native readback validation.

## Separate evidence from adoption

Record output completion (`Ending Time`), the exact normal-termination marker,
estimation diagnostics, reproduction agreement and scientific adoption in separate
fields. A missing normal marker requires investigation; alone it does not establish
nonconvergence. An ending timestamp or a full table is not a normal-termination
test. Never upgrade a result simply because all files exist.

Numerical agreement can reproduce an unidentified model and unreliable SEs.
Read the complete raw estimation diagnostic block, with OUT hash and line numbers,
in addition to requested `readModels()` warnings. Exclude the input echo and
distinguish final-solution diagnostics from discarded-start diagnostics. Parse
the full nonidentification parameter set; the first named parameter alone may not
describe the unidentified direction. A configured regex list is a screen, not
proof that every possible diagnostic has been classified.

Classify warning meaning before assigning an adoption consequence. A MODINDICES
request ignored because of nonlinear MODEL CONSTRAINT means that requested
diagnostic was not produced; it does not by itself invalidate estimation. A
TYPE=COMPLEX subpopulation warning about USEOBSERVATIONS concerns the variance
design and needs a target-population/domain decision before changing syntax.
Missing-X exclusions concern the actual analysis sample. Preserve raw warning
blocks, line numbers, file hashes and overlapping per-model categories; keep
non-starred estimation diagnostics alongside them. Unknown warnings remain
unclassified review items. An input-line truncation warning must not be silently
cleared just because the displayed excerpt resembles a comment.

In the source-corrected Chapter 4 inventory, all-template and manuscript counts
differ: 72 versus 60 missing-X warnings. The screen found option-only warnings in
445 of 781 existing outputs, including 352 manuscript dependencies. These are
screen-specific counts, not scientific acceptance or a general property of Mplus.

For lifecycle/domain comparisons, bind TYPE, ESTIMATOR, CLUSTER, USEOBSERVATIONS,
SUBPOPULATION, WEIGHT and STRATIFICATION to the actual input. Distinguish exact
cluster-key overlap before model exclusions from effective cluster counts. The
corrected historical inventory contains 168 COMPLEX/MLR/FID manuscript models
(8 direct, 160 moderation) without declared weights or stratification. Its stage
DATs share 615 and 623 FID keys, not spouse-pair keys. All 168 Ns reconcile after
missing-X exclusions; 128 cluster counts match the pre-exclusion frame. Investigate
the remaining 40 through their effective samples, not by assuming data errors.
Separate domain variance, cross-domain covariance, and effect scale: stage-specific
standardization also changes the comparison. Significant in one domain and not
another is not a test of their difference. Undeclared survey weights limit claims
of full survey-design inference, without alone invalidating a conditional estimand.

The remaining 40 rank models were subsequently reconciled by applying their actual
DEFINE assignments and missing predictor/interaction masks: all N, exclusion and
FID counts match, with 664/1564 effective stage FIDs and 273 shared keys. Missing
outcomes were absent in this check; do not generalize its complete-variable mask
to FIML. When parsing USEVARIABLES, recognize the next section boundary as well as
semicolons instead of accidentally consuming DEFINE text.

Bind statistical cautions to exact manuscript claims. A within-stage moderator
H-minus-L conditional-indirect contrast is not a between-stage Fy-minus-Sy test.
Age-defined group comparisons do not alone identify within-couple evolution or
separate age, period and cohort effects. Keep hypotheses, descriptive patterns,
direct contrast evidence and causal interpretation separate; archive proposed
wording with the original paragraph and manuscript hash without modifying sources.

Check actual lifecycle test architecture separately from family names such as
"multiple group". The corrected 612-input inventory has 204 total and 204 per
stage, with 408 USEOBSERVATIONS-filtered stage fits and no GROUPING/MODEL TEST
declarations. The total models include lifetime as a covariate; that is not a
path-by-lifetime interaction or a direct between-stage contrast. A negative
lexical search for familiar R test functions cannot exclude custom code, aliases
or external scripts. Bind an actual joint contrast and its covariance before
accepting between-stage significance claims; preserve those search limitations.

Comparison categories often apply precedence (data before sample before parameter
structure). Preserve that historical label, but add independent overlapping flags.
Audit parameter gaps in every model, including ones labeled numerically identical.
Distinguish freely estimated coefficients, fixed values and derived constraints;
row counts in parameter tables are not counts of free parameters. Reconcile raw
OUT against parser output before attributing a missing row to the engine.

## Data and controlled verification

Identical DAT hashes do not prove identical effective samples. Check USEVARIABLES,
USEOBSERVATIONS, missing codes, DEFINE transformations, interactions and estimated
means/variances for predictors. Verify identity-key uniqueness before joining old
and new data; report added/deleted records and changes on common records separately.
Do not infer a software-version cause from a historical/current contrast confounded
by changed data or input. Label observations, hypotheses and controlled findings.

Version experiments need isolated executables and output roots, explicit
MplusAutomation `Mplus_command`, a frozen input-diff contract, engine versions
from actual OUT and identical data hashes. A no-bootstrap fit can diagnose
parameterization or sample handling, but cannot replace the intended bootstrap CI.
Retain original confidence-level rules; exploratory 90%-only effects remain so.
Define full testing families before BH/BY sensitivity, including nonsignificant
tests, and use full-precision inference sources rather than rounded OUT p-values.

Adoption ledgers must connect each effect/table cell to models, data and CI sources.
Use explicit reasons for main text, qualified main text, sensitivity/supplement,
or held results. `Pending review` is a work state. Do not mark scientific closure
while source populations, target-effect identification or bootstrap validity remain
unresolved. Preserve source manuscripts and offer isolated replacements/wording.

## Verified case and limits (2026-10-02, Chapter 4)

In one 612-output audit, all outputs ended, but only 540 had the normal-termination
marker. The other 72 were mediation fits with identification/SE diagnostics even
though their estimates matched historical outputs at reported precision. Across
all models, 360 had relevant derivative/SE diagnostics. These are case-specific
counts, not general Mplus failure rates or proof that an upgrade caused the issue.

Evidence relative to the dissertation R-analysis workspace:
`scientific_audit_20261002/evidence/inventory_summary.json`,
`evidence/diagnostic_events.json`, `ledger/models.csv`, and
`HANDOFF_2026-10-02_ch4_scientific_audit.md`.

## Subsequent controlled and source checks (2026-10-03 UTC)

- In the same case, all 30,600 missing parameter rows were absent in raw OUT,
  comprising 27,288 covariances, 1,656 means and 1,656 variances. Every model's
  missing-row count reconciled with its free-parameter change. These were not
  merely parser omissions or fixed-zero rows. Use `parameter_gaps_raw_checked.csv`
  and `parameter_structure_summary.json`, not the original precedence labels.
- In an isolated no-bootstrap sibling-order conditional-mediation example,
  identical INP/DAT run in 8.11 and 9 produced N=9,028 versus 4,397. Removing
  exogenous WITH/PWITH distribution modeling while retaining endogenous residual
  covariances gave N=4,397 and identical reported coefficients in both versions.
  Analogous age-gap/support examples lost the problematic SE diagnostics under
  the conditional-exogenous specification. This establishes behavior in those
  controlled diagnostics, not a blanket version cause or a validated bootstrap
  replacement. `evidence/diagnostic_contrasts.csv` records each factor and hashes.
- The sibling example retained a binary-variable warning even after exogenous
  WITH/PWITH removal: DW1F/DW1M remained in USEVARIABLES without any regression
  role. A further two-engine diagnostic removed only these two unused variables;
  the warning disappeared. Audit variable roles after a covariance change,
  including implicit dependent variables. Removing unused variables is different
  from adding them as confounders; whether the original regression omitted needed
  controls remains a separate substantive question.
- Count and classify warnings beyond MODINDICES. The full audit also found 168
  TYPE=COMPLEX subpopulation warnings, 132 missing-X exclusions, and one run with
  only 999 of 1,000 requested draws. Check `Number of bootstrap draws` followed by
  Requested/Completed; a failed header match means unchecked, not zero draws.
  A completed draw count does not establish the correct resampling unit.
- The source CSV contained 22-digit concatenated couple/year IDs. Current DAT
  tokens matched a 15-significant-digit numeric writer. Using both spouse orders
  linked 8,934 historical records uniquely within the current source; 4,426 of
  those links needed reversed spouse order. A naive ID join found only 4,508.
  Preserve identifiers as strings, use validated integer IDs plus a crosswalk for
  Mplus, and test both within-version uniqueness and cross-version stability.
  The historical unrounded source was unavailable, so this remains a constrained
  identity reconstruction, not proof of the full historical PID or consumed data.

## Input rewriting and resource accounting pitfalls

Mplus accepts both `!` line comments and `!* ... *!` block comments. Remove or
parse whole blocks before stripping line comments. Stripping `!.*` first can
activate the block's MODEL INDIRECT code and leave an invalid `*` terminator.
An actual diagnostic failed for this reason; its inputs/output were retained and
only unfinished cases were regenerated in a new attempt directory. Review the
effective syntax, not just a byte diff of a comment-stripped file.

For a resident R worker, separate total R-plus-Mplus peak allowance from the
incremental memory required to launch its next Mplus child. Do not count already
resident worker memory twice, and do not lower the OS reserve to bypass a wait.
Record RSS for physical admission and private commit for commit admission, with
measurement headroom. One-time WSL cache reclamation can lower guest Cached
without increasing observed Windows Available; do not report that as a measured
RAM gain. The Chapter 4 receipt `evidence/cache_reclamation_20261003.json` shows
that limit under concurrent workloads.

The subsequent current-source audit recovered the full 9,748-row intermediate
dataset and independently reproduced its 9,121-row export. It also established a
2022 household-income transformation defect and the exact couple-year structure.
See [source-data-and-bootstrap-precision.md](source-data-and-bootstrap-precision.md)
for source evidence, isolated repair boundaries and verified GH5 extraction rules.
Earlier statements about unavailable historical raw source remain limited to the
actual historical version; current full-source identity candidates are now complete.
## Reconcile the manuscript's method with the fitted design

### Bind probe values to the actual cohort and scale

“Current output” need not mean a common current cohort. In this reproduction,
moderation models used 9,121 records while many conditional models still used
9,028; their phase samples and standardization populations also differed. Audit
the exact DAT hash, NAMES schema, USEOBSERVATIONS and active missingness fields
for every model. Record separate tables for (a) probes appropriate to the existing
reproduction source and (b) a proposed common repaired cohort. Do not copy moments
between them. Verify physical data paths as well as deduplicated hash groups.

A common full-cohort moderator scale, with phase-specific probe locations, is a
design candidate; within-phase restandardization is another estimand contract.
Differences between their numeric coordinates are not changes in path effects.
Preserve binary and categorical effect-code levels. Keep the standard-deviation
denominator explicit, and separate changes beyond printed moment precision from
mere rounding. Propagated rounding bounds are not confidence intervals.

Discover the actual base-constant names before substitution. A common child-count
variable can appear under `w_*` in moderation and both `wm_*`/`wf_*` in conditional
mediation. Both member stems may map to the same `child_sd`. Keep `probe_stem` in
the key alongside model and variable, and verify every resulting constant, not
only one mean/SD per variable. In `wf_m`, the final `m` means mean; it does not
identify the male member. Read the `wf_` prefix. Exact effect identities remain
authoritative when labels have overloaded suffixes.

The local audit's first 396-moment check missed this alias coverage; the corrected
contract has 468 moment/stem rows for 5,388 constants across 528 models. Preserve
the failed-check explanation and supersede its completion claim. Evidence lives
under `scientific_audit_20261002/validation/probe_validation_recovery.md` and the
current/unified probe ledgers; neither candidate is a new Mplus fit or release.

Count both data records and unique cluster IDs, including overlap between phase
samples. Chapter 4 has 9,121 records from 4,073 couples; 559 couples occur in both
phases. Year dummies do not remove within-couple dependence. Significance in one
phase and not the other does not establish a phase difference. Ordinary bootstrap
does not become cluster bootstrap because year indicators or dyadic equations
are present; MLR/delta sensitivity is not a replacement for BC intervals.

Trace claimed controls through source coding, actual DAT values, USEVARIABLES
and ON equations. Presence in NAMES or a distribution model is not regression
adjustment. The audited 612 models omit all eight manuscript-described measurement
control columns and parent-child-count controls. Fitted parental support is binary,
although the manuscript describes three categories. Parent-age controls use
<60/60–79/80+ (reference <60); education and region each use one binary contrast.
Do not silently replace these with the richer categories described in prose.

Preserve original wording and prepare explicit candidates with adoption conditions.
Adding a control requires substantive justification as well as a sensitivity
comparison; unchanged estimates alone do not establish causal identification.
Also separate dyad distinguishability from a particular actor/partner path
difference, and an equal-weight effect-code slope mean from a sample-weighted mean.
Evidence: `scientific_audit_20261002/validation/method_contract_evidence.json`,
`validation/native_method_counts.csv`, and `ledger/method_wording_candidates.csv`
under the same audit root. These are case evidence, not universal sample counts.
