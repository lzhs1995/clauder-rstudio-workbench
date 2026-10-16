# Finite-cluster covariance and bootstrap contracts

An SE ratio resembling a familiar correction is a diagnostic clue. Establish the
documented formula, then compare at the same parameter point before changing any
candidate inference. Optimizer stopping differences, score centering, Hessian
normalization and printed covariance precision can otherwise be confounded.

## Documented variance formula

Asparouhov (2005), *Sampling weights in latent variable modeling*, printed page
425, equation (5), gives the inverse-Hessian sandwich with scores summed within
clusters, centered within strata, and multiplied by `n_h/(n_h-1)` in each stratum.
Official PDF: https://www.statmodel.com/download/webnotes/mplusnote72.pdf

For one stratum with equal weights, let `U_g` be the total score of spouse cluster
`g`, `Ubar = sum(U_g)/G`, and `A` the total observed negative Hessian. Then

`V = A^-1 [G/(G-1) * sum_g (U_g-Ubar)(U_g-Ubar)'] A^-1`.

If code uses the average Hessian `H=A/N`, include the additional `1/N^2`.
The factor multiplies covariance; SEs scale by its square root. Do not replace
it with `N/(N-1)` or regression's extra `(N-1)/(N-P)` factor. Use actual selected
clusters, not rows, full-data clusters or the original household count. A singleton
stratum requires explicit handling; division by `G-1` is not valid for `G=1`.

At an exact optimum total scores are zero. At a saved engine point they need not
be: explicitly center scores before comparing with Mplus. Check all free
parameters, SEs, and off-diagonal covariances normalized by `SE_j*SE_k`.
Printed TECH3 has limited precision; retain the saved RESULTS SEs separately.

Chapter 4's same-point check covered six actual `(N,G)` sets:
`(9121,4073), (3641,1833), (5480,2799), (4423,1933), (1247,652), (3176,1543)`.
Six models / 573 free parameters passed native R and independent Python matrix
checks: maximum relative SE difference `9.96573e-8`, maximum standardized
covariance difference `4.26348e-6`. This supports the convention in those checks;
it does not certify all 612 engine fits or silently revise existing inference.

Evidence under `scientific_audit_20261002/`:
`evidence/cluster_correction_official_sources.json`,
`experiments/cluster_correction_same_point/scope_centered/`,
`validation/cluster_correction_centered_summary.json`.
Keep the original uncentered checks and candidates as historical evidence.

## Two different whole-cluster resampling designs

First distinguish ordinary record bootstrap from either whole-cluster design.
The source-corrected Chapter 4 historical contract has 360 ML bootstrap inputs
(72 mediation, 288 conditional mediation), all requesting BCBOOTSTRAP intervals,
with no CLUSTER or ANALYSIS TYPE=COMPLEX declaration. These support 205 manuscript
items. A wide couple row retains both members when resampled; ordinary row
bootstrap does not thereby preserve dependence between repeated annual rows of
the same couple. Do not conflate within-row pairing with cross-wave clustering,
or transfer a direct-model MLR/FID validation to these bootstrap intervals.
Parse TYPE inside ANALYSIS, not a later PLOT TYPE=PLOT3. Completed replicates,
CI type, sampling unit and scientific adoption must remain separate fields.

Mplus's documented complex-survey bootstrap draws `K_h-1` PSUs with replacement
within each stratum and assigns replicate weights `w_i * f * K_h/(K_h-1)`, where
`f` is the PSU's selection multiplicity. A one-PSU stratum is self-representing.
See Asparouhov and Muthen (2010), section 2.1, printed page 4:
https://www.statmodel.com/download/Resampling_Methods5.pdf

Chapter 4's preserved external bootstrap draws `G` spouse clusters with
replacement and retains all rows from each selected spouse cluster. Both preserve
within-cluster dependence, but they are different finite-sample algorithms.
Never relabel the existing 1000/5000-replicate evidence as native Mplus bootstrap,
replace it in place, or claim draw-for-draw equivalence. Record the independent
sampling unit, strata, draw count, weights, seeds and repeated-cluster identity.
Changing designs requires a separate named sensitivity run.

Since Mplus 8.3, the technical note simplifies TYPE=COMPLEX bootstrap syntax with
`BOOTSTRAP=...` and explicitly specifies `ESTIMATOR=ML`, rather than the MLR used
without bootstrap: https://www.statmodel.com/download/tech_note_for_bootstrap.pdf
This documents bootstrap SE support. It does not itself verify BC endpoints,
GH5 export or MplusAutomation parsing for the current model/version. Validate
those separately against the raw output before reporting BC results.

Save source PDFs, relevant rendered pages, retrieval location and SHA-256.
Legacy PDF font encoding may break text extraction: an empty search cannot prove
the formula is absent. Inspect the rendered page. An old technical appendix is
supporting history, not sufficient evidence of every current engine behavior.
