# Analytic computation for an observed binary moderator

Use this when an authorized model interacts a continuous Gaussian latent
variable with a **known binary covariate**, and numerical integration is the
computational bottleneck. Establish equivalence for the actual model before
changing its representation. This does not apply automatically to a continuous
moderator, two latent variables, categorical outcomes, or a newly dichotomized
score.

## Preserve the conditional model

For growth factors eta, indicators y, covariates C and observed G in {0,1}, write

```
eta = a + gamma*G + Gamma*C + (B0 + D*G)*eta + epsilon
y   = Lambda*eta + e
A_g = inverse(I - B0 - D*g)
mu_g(C) = Lambda*A_g*(a + gamma*g + Gamma*C)
Sigma_g = Lambda*A_g*Psi*transpose(A_g)*transpose(Lambda) + Theta
```

For fixed g this is a conditional Gaussian model. A fully observed
`KNOWNCLASS` representation can express it without the original `XWITH`
integration. It is not latent-class discovery or a replacement of a continuous
construct by class membership.

In the tested two-process model, only `IY ON IX`, `SY ON IX` and `SY ON SX`
vary with G. Their class-1 minus class-0 coefficients are the three original
interactions. Four class-specific **structural intercepts** absorb the four
G main effects. They are not unconditional growth-factor means.

Preserve all other equalities explicitly: measurement loadings, indicator
intercepts, factor/indicator residual variances and covariances, other structural
paths and control coefficients. Generic multigroup defaults can silently relax
these constraints. Confirm shared and intentionally distinct parameter IDs in
each class's TECH1 output; compare the total number of free parameters.

Keep the original missing-indicator patterns and the same conditional FIML
model. Retain the real cluster ID even when a cluster contains both G values.
Splitting cluster IDs by class changes the robust covariance. If G is imputed,
use that member's actual completed G and preserve the original MI scope; this
computational identity does not establish imputation compatibility.

## Likelihood and covariance mapping

With the two known-class probabilities fixed at 0.5, the joint output likelihood
includes `-N*log(2)`. Remove that parameter-independent constant when comparing
to the original conditional likelihood. Verify the constant for the actual
sample and software rather than treating all reported likelihoods as directly
comparable. Do not infer an ordinary or scaled LRT from this identity alone.

Construct a full-rank linear map J from the known-class coefficients back to
the original coefficients:

```
q_original = J * q_class
V_original = J * V_class * transpose(J)
```

Map group main effects and every interaction as differences. Retain the
cross-covariances when forming SEs, group contrasts and pooled MI tests.
Comparing only interaction coefficients or printed p-values is insufficient.

## Calibrate once, then apply a bounded family contract

1. Reuse a legal no-interaction parent. Compare all saved parameters, SEs,
   robust TECH3 and conditional likelihood against the equivalent known-class
   parent. Include actual cross-group clusters when present.
2. Check a nonzero-interaction synthetic pair. A no-interaction comparison
   cannot catch all mistakes in the group-difference map. Check all parameters
   and the full covariance, not just the three interactions.
3. Label a fit initialized from the counterpart's terminal estimates as a
   local implementation check, not an independent-start check or speed benchmark.
4. Admit the actual family under its frozen budget, legality, start-agreement
   and complete-member rules. A first inadmissible member can stop the family;
   do not extend the queue merely because computation is now cheap.

Preserve first-stage and reader failures separately. For example, NumPy boolean
JSON serialization or an assertion that wrongly requires intentionally distinct
paths to share a parameter ID can be repaired by reading existing output. They
do not justify another Mplus fit.

## What the Windows PP-LGCM case established

The 2026-10-17 calibration compared 128 real-data parent parameters, including
226 cross-resource households, and 39 synthetic parameters with three nonzero
interactions. Maximum parameter differences were approximately 0.000272 and
0.000117 of a reference SE; complete robust covariance comparisons also passed.
These are case-specific observations, not universal acceptance thresholds.

Three authorized CFPS resource models previously reached their 240-second
XWITH budgets without estimates. The calibrated known-class computations
finished in about 21–25 seconds with roughly 202 MiB peak process-tree RSS.
All three nevertheless had negative SY residual variance. Their families
remained incomplete; no zero-variance repair, favorable member replacement or
pooled scientific claim followed. The bounded calibration plus three research
calls used about 97 seconds including engine-launcher overhead.

This distinguishes a computational bottleneck from an inadmissible result.
Normal termination, positive observed covariance or a large SE around a
negative residual variance does not make that latent-variable solution valid.
It also does not establish absence of an effect or global nonidentification.

Use the existing complete-family and source-scope rules in
[bounded-research-reopening.md](bounded-research-reopening.md). A completed
register for baseline-difference-by-resource paths does not cover every
intercept-by-resource or dynamic hypothesis in an original paper.

## Sources and evidence

- [Mplus interaction types](https://www.statmodel.com/HTML_UG/chapter17V8.htm)
- [Mplus KNOWNCLASS](https://www.statmodel.com/HTML_UG/chapter15v8.htm)
- [Mplus analysis types](https://www.statmodel.com/HTML_UG/chapter16V8.htm)

The conditional-model algebra above is the project's derivation; software
support for multiple groups alone is not evidence of its implementation.
The project evidence package includes raw inputs/outputs, parameter RESULTS,
TECH3, the two calibration records and a public saved-parameter replay. It
excludes individual analysis data; public replay does not recompute the
individual-data likelihood or refit Mplus.

[Fixed project evidence](https://github.com/lzhs1995/PP-lcgm-paper/tree/c7c03f6b9e4aa00267b5533071af4c0fc58ca64d/cfps_mean_h41_knownclass_20261017)
