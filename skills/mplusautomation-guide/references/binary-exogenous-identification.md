# Binary exogenous moments and identification diagnostics

Use this procedure when Mplus reports a singular/non-positive derivative-product
matrix and the named parameters belong to an explicitly modeled exogenous
mean/covariance block containing binary variables. Bind every diagnostic to the
actual INP/OUT/DAT/GH5 hashes before reusing it across script versions.

## Separate the mechanisms

For a variable with support {a,b}, `z² − (a+b)z + ab = 0`. Its centered first and
second moment columns are dependent. With nonsingular covariance, Gaussian
mean/covariance scores are transformations of these centered sufficient
statistics. Consequently the empirical score outer product can be singular even
when the substantive conditional regression design has full column rank.

This observation explains a possible score-rank warning. It does **not** by itself
establish that all path coefficients are unidentified, nor does it validate a
complete Hessian, robust variance estimate, indirect-effect CI or causal claim.
Keep these evidence layers separate in the adoption ledger:

1. Actual modeled-variable roles, including variables pulled into a distribution
   model through WITH statements or left implicit after a specification edit.
2. Rank of centered first/second moments for each distinct data/role group,
   singular values and tolerance, binary support and polynomial residuals.
3. Rank of each substantive regression design with intercept, and residual-block
   eigenvalues with allowance for printed OUT rounding.
4. Target-effect identification/inference, bootstrap sampling unit and cross-wave
   dependence; these require additional evidence beyond the first three layers.

Do not automatically remove the distribution block to suppress a warning. A
conditional-exogenous diagnostic changes the statistical contract and may change
missingness or sample handling across engines. Compare the same data and target
equations in an isolated diagnostic only when execution is authorized. A
no-bootstrap diagnostic cannot replace intended bootstrap intervals.

## Numerical and parser checks

- Center moment columns again before normalization. Accumulation error in an
  almost-zero column must not be rescaled into an artificial independent column.
- When binary support is balanced, its centered square can be identically zero;
  retain that dependency in the parameter-count/rank reconciliation.
- Preserve thresholds and smallest singular values. A binary-identity fixture,
  balanced-binary fixture and continuous-perturbation control detect these issues.
- Normalize whitespace before identifying `WITH` blocks in OUT. Multiple spaces
  must not silently remove a residual covariance from the positive-definite check.
- Preserve the original condition-number text; remove trailing punctuation before
  numeric conversion of Fortran D notation.
- Byte equality and semantic equality are different receipts. A removed duplicate
  `VARIABLE:` header can explain a hash difference, but does not authorize bypassing
  the source-hash check or importing an old role dictionary blindly.

## Verified case and limits

The corrected Chapter 4 source audit inspected 72 historical mediation models:
six data/role groups, 14 exogenous distribution variables, 119 moment parameters,
rank 115 and four binary identities per group (DW1F/DW1M/HKF/HKM). All 288
substantive designs were full rank and all 144 printed residual blocks remained
positive under a .001 spectral rounding bound. Four **previous** no-bootstrap
experiments were rebound to source hashes; none were newly executed. This narrowed
the diagnosis, while historical data identity, cluster/bootstrap inference and
manuscript adoption remained open. These are case counts, not acceptance thresholds.

Evidence relative to the dissertation analysis workspace:
`ch4_source_correction_20261006/ROUND6_FINDINGS.md`,
`historical_mediation_identification_models.csv`,
`mediation_identification_guard.json`, and `round6_validation.json` in that folder.

Large RData provenance searches should likewise separate clues from evidence:
streaming length-prefixed strings avoids loading multi-GB workspaces, but proves
neither top-level objects nor data-frame rows. Record source hashes, bytes scanned,
EOF and limits. Do not regenerate a missing workspace to fill a provenance gap.
