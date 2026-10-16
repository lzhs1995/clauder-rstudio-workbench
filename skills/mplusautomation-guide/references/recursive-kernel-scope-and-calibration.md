# Recursive Gaussian kernel: scope before speed

For the subsequent all-family correction and full 279/209 manuscript binding,
see [full-scope-review-and-adoption.md](full-scope-review-and-adoption.md).
The 83-fit and 67-fit counts below remain historical engine-calibration checkpoints;
the full-kernel candidate is a distinct evidence layer, not expanded Mplus evidence.

## Complete effect propagation without changing inference meaning

Expand the frozen effect contract at full-precision kernel points and retain
sparse gradients keyed to the physical parameter order. Determine constants
from the symbolic contract: a numerically zero gradient alone does not prove
an expression constant. Independently expand INP constraints in R and compare
symbolic derivatives with the Python forward derivatives before propagation.

The full Chapter 4 propagation covered 612 models / 35,268 effects, including
5,388 constants and 29,880 nonconstant rows. Seven native chunks plus independent
Python endpoint/p readback passed; maximum endpoint difference was 7.106e-15.
The 255 earlier independent representative effects differed by at most 3.934e-7
in endpoints at the slightly different refined fit points. See
`validation/full_kernel_effect_inference_checks.json` and
`reports/FULL_KERNEL_EFFECT_INFERENCE_REVIEW.md`.

Nonconstant rows are not unique hypotheses: apply the frozen symbolic and
likelihood-unit mapping before full-family correction. This propagation remains
uncorrected spouse-cluster observed-information delta, not BC or manuscript release.
Keep live engine snapshots separately frozen: the 298-fit snapshot at
`snapshots/unified_20261004_02` reused 83 hash-verified caches and left 215 pending
precision exports when the 20-model export admission check held for low RAM.
Do not overwrite the old 83-fit evidence or expand a frozen manifest as the queue advances.

## Analytic covariance expansion

Analytic observed information can replace repeated numerical differentiation
after independent validation. Include regression/covariance cross derivatives
and off-diagonal covariance multiplicities; do not silently substitute expected
information or omit cross-block score dependence. Sum row scores by spouse ID
before forming the sandwich meat. Five structural representatives matched
independent lavaan Hessians/scores, maximum relative SE difference 2.733e-9.

All 612 systems then produced covariance matrices, each bound to its exact point,
input, data and sandwich-source hashes. Seven native chunks and a separate matrix
readback verified 59,058 parameter dimensions, finite symmetric positive definite
matrices and zero standardized covariance differences within 372 reuse groups.
See `recursive_gaussian_sandwich.R`, `validate_analytic_sandwich.R`,
`validation/full_kernel_covariance_checks.json` and
`reports/FULL_KERNEL_COVARIANCE_REVIEW.md` under the audit root.

The convention remains observed information and uncorrected spouse-cluster meat.
Numerical covariance coverage is not full effect/BC coverage or proof of model
assumptions. Preserve the engine's finite-sample convention as a separate check.

## Full point-estimation coverage after representative validation

Seven native R chunks subsequently solved all 612 frozen systems, writing 59,058
free-parameter records. Independent readback verified input/data binding, unique
model coverage, positive residual blocks and average scores (maximum 1.044e-13).
The 83 previously calibrated kernel vectors matched exactly. All 372 proposed
likelihood groups matched by physical parameter and conditional LL; parameter
and LL differences within the declared reuse groups were zero in this run.
This validates point-level reuse under the frozen contracts, not arbitrary
bootstrap-draw reuse, shared seeds or complete covariance equivalence.

Keep point outputs separate from engine output and from bootstrap state.
`fit_full_recursive_kernel.R` writes isolated parameters and chunk manifests;
`validate_full_kernel_points.py` checks them without fitting. See
`validation/full_kernel_point_checks.json` and `reports/FULL_KERNEL_POINT_REVIEW.md`.
Do not call this 612 Mplus reruns or erase the 12 engine stopping-precision
exceptions. Full-scope covariance, BC and manuscript adoption remain separate gates.

Treat syntax support, sample equivalence, point/likelihood calibration, covariance
validation, bootstrap validity and manuscript adoption as separate gates.

## Audit the full inventory

Parse every regression edge and free residual covariance pair, then compare each
relationship with independently produced source-path and control ledgers. Counts
alone cannot detect swapped variables. Reject unsupported syntax explicitly.
The Chapter 4 audit checked 612 inputs, 54,198 edges and 972 covariance pairs.
288 inputs include products constructed from endogenous variables: computational
support does not make these ordinary fixed exogenous regressors or establish
causal interpretation. Review the estimating equations and intended estimand.

Replay DEFINE operations against actual DAT files in their original order. IF/EQ
recoding needs an explicit restricted grammar: preserve missing/unmatched values
rather than initializing them to zero. The initial parser correctly left 132
rank models unsupported; keep that initial evidence after extending the parser.
Check selected row identities, spouse clusters and N, not just variable names.
Compare completed outputs with actual Mplus N. Chapter 4 has six selected samples;
all 612 data contracts and 83 completed output samples matched, with no missing Y
after X exclusions. This observed fact permits the current complete-Y calculation;
it is not permission to replace FIML with listwise deletion on future data.

## Diagnose numerical differences without moving tolerances

Freeze INP/OUT/DAT hashes and compare the entire free parameter vector, conditional
log likelihood and scores. Predeclare tolerances. Chapter 4 used parameter error
<1e-4 and printed LL error <0.0006: 71 of 83 passed directly, 12 retained exception
labels. Do not loosen the threshold to turn those labels into passes.

Independently optimize exception models and structurally important representatives.
Here the 12 exceptions plus five completed conditional-mediation outputs received
17 independent lavaan BFGS checks. Maximum parameter difference was 5.015e-6 and
LL difference 1.528e-9. Kernel average scores were near zero (maximum 9.251e-14),
with slightly better unrounded LL than the saved Mplus point, consistent with
optimizer stopping precision. Preserve the Mplus point and exception evidence.
Differences in residual variances, covariance, intercepts or controls must not be
described as equally large changes in all research paths.

Neither these checks nor a single successful cluster-bootstrap pilot validates
all robust covariance matrices, SEs, bootstrap intervals, or all 612 models.
Next validate cluster scores, bread/meat conventions and effect gradients with
an independent implementation before adopting alternative-kernel inference.

## Chunked verification and immutable checkpoints

Verify small explicit model subsets in the live R session; bind each chunk to
source hashes. Merge only after checking disjoint coverage and identical source
versions. A partial validator must never overwrite the full-validation target.
Archive earlier snapshots before updating counts; distinguish fits, unique
likelihoods, model identities, effects and manuscript display rows.

Chapter 4's 83 fits / 81 likelihoods map to 137 identities and 5,370 effects.
Only six complete families (2,064 units) received BH/BY adjustment. There are
1,278 available display rows out of 5,328, and 16 fully populated main items;
these are candidate coverage, not manuscript adoption. Keep the historical
67-fit / 4,750-effect / 1,172-display-row evidence independently verifiable.

Evidence root: `scientific_audit_20261002/`. Consult
`validation/recursive_kernel_calibration_checkpoint.json`,
`validation/recursive_kernel_contract_independent.json`,
`experiments/recursive_kernel_calibration/`, and
`validation/unified_family_validation_current.json`. Scope/data/calibration
scripts and per-chunk native checks are saved there. All scientific-release
flags remain false at this checkpoint.

## First cluster sandwich calibration

The saved 110-parameter mediation pilot subsequently passed a separate score and
covariance implementation check on 9,121 observations / 4,073 spouse clusters.
Analytic conditional-density row scores agreed with unscaled lavaan scores to
1.171e-13. A forward-difference Hessian had relative error 4.503e-5; central
differences reduced this to 2.162e-9. Diagnose differentiation error before
changing model equations or loosening tolerances.

With H the average observed negative Hessian and U_g the sum of row scores in
spouse cluster g, use V = H^-1 (sum_g U_g U_g') H^-1 / N^2. This check explicitly
uses no finite-sample correction. Cluster after computing row scores; treating
each row as its own cluster changes the uncertainty calculation. Independently
assembled lavaan scores/Hessian gave maximum relative SE error 1.478e-9.
See `experiments/cluster_sandwich_pilot/validation.csv`, `parameter_SE.csv` and
`validation_matrices.rds`; the latter binds original context/fit and script hashes.
Original bootstrap state was read-only and hashes remained unchanged.

This validates one pilot implementation against another package under the stated
convention. It does not validate all 612 models, establish asymptotic adequacy,
resolve endogenous-product interpretation, or equate robust-normal intervals with
BC bootstrap intervals. Generalize and check representative structures before
using the kernel for full-scope inference.

The next representative expansion covered five models / 484 parameters across
mediation, direct effects, moderation and conditional mediation, including rank
recoding and endogenous products. All five passed source-hash and matrix readback;
maximum relative SE error was 2.739e-9. Also compare covariance differences divided
elementwise by sqrt(V_jj V_kk): this catches cross-parameter discrepancies that
diagonal SE checks alone miss. Maximum standardized covariance error here was
7.811e-9, and all five covariance matrices were positive definite. See
`validation/cluster_sandwich_representative_checks.csv` and
`reports/CLUSTER_SANDWICH_SCOPE_REVIEW.md`. Five representatives do not cover every
model or all six selected sample sets; retain that limit explicitly.

## Validate effects separately from covariance

Expand MODEL CONSTRAINT definitions recursively with cycle detection, preserving
fixed probe constants and exact physical path labels. Compare symbolic chain-rule
gradients with central differences, then propagate both independently checked
covariance matrices through all requested effects, including constants. The five
representatives produced 255 effects (23 constants); gradient discrepancy was
at most 1.428e-12 and 90/95 endpoint discrepancy at most 4.904e-11. Constant
expressions are not random-effect tests. Do not adjust an incomplete family.

Keep independent-implementation agreement separate from agreement with Mplus.
The original Mplus points/printed TECH3 differ from the refined solver point and
unadjusted cluster sandwich. SE-ratio medians close to sqrt(G/(G-1)) suggest a
finite-cluster correction, but ratios vary for small/cancelling effects. Verify
the engine convention and precision before attributing every difference to a
single factor or silently applying it. These are delta candidates, never BC.
Evidence: `reports/CLUSTER_EFFECT_SCOPE_REVIEW.md`,
`validation/cluster_sandwich_effect_checks.csv` and
`validation/cluster_effect_Mplus_SE_ratio_diagnostic.csv`.
