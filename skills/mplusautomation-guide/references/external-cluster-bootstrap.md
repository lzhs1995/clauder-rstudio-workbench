# External cluster bootstrap and validated computation

Ordinary row bootstrap does not preserve repeated observations of a couple.
When the declared estimand calls for couple-level resampling, sample G couples
with replacement from G observed couples, retaining every eligible record of
each selected couple. Repeated selections are distinct bootstrap copies;
keep both source-couple and copy-cluster identities. Variable record counts are
expected when clusters have different sizes. Do not force every replicate back
to the original row count or relabel this procedure as survey-PSU bootstrap.

Freeze the estimation sample before sampling. Explicitly state whether reference
scales, winsorization thresholds, controls and probe positions stay fixed or are
re-estimated. These define different inferential targets. Save the seed schedule,
selected source-cluster indices, successes, failures and each fitted parameter
vector. Never silently replace a failed replicate with another seed.

## Validate the likelihood before accelerating it

A continuous observed recursive Gaussian model can sometimes factor into
conditional multivariate regressions. This must be established from the actual
input: all modeled variables observed, no missing active values for this kernel,
no within-block reciprocal regressions, a directed acyclic order of blocks,
unrestricted positive-definite within-block residual covariance, and no omitted
cross-block residual correlations or parameter constraints. Latent, categorical,
mixture, missing-data and constrained models need separate methods.

Different regressors in equations with correlated residuals require joint ML;
independent OLS is generally not the same estimator. One valid conditional
maximization algorithm alternates generalized least squares coefficients using
the current residual precision matrix and residual covariance divided by N.
Check monotone likelihood, positive covariance spectra, coefficient convergence
and all free parameters. Reusing sufficient cross-products changes computation,
not the declared likelihood, only when these conditions hold.

Require a baseline comparison with the actual Mplus input/output and full saved
parameter precision. Also compare with an independently implemented SEM solver,
including weighted versus explicitly expanded cluster samples. A close log
likelihood alone does not establish matching parameter identities or SEs.

In the Chapter 4 pilot, `apimem_total_age-incc-clo_step1` had 9,121 records,
4,073 couples and 110 free parameters. The R kernel differed from saved Mplus
coefficients by at most 1.671e-5, with LL differing by -0.000228 from the
three-decimal Mplus print. Independent lavaan BFGS gave maximum parameter
difference 2.647e-7 and LL difference about 1.02e-10. Three whole-couple draws
(9,064, 9,197 and 9,124 rows) matched the independent solver within 2.586e-7.
This is a one-model numerical validation, not a general replacement of Mplus.

The first lavaan NLMINB comparison converged but exceeded the prespecified
1e-5 parameter tolerance (1.418e-5). Tightening tolerances caused a nonconvergence
flag. Keep those failed attempts; do not relax validation merely to pass. A
different optimizer resolved this case and independently met the original gate.

## Preserve interval semantics

An external BC interval must specify the strict-less-than or tie convention for
bias correction, quantile algorithm, requested/successful counts, and whether an
acceleration term is present. BC is not BCa. Do not derive a bootstrap SD from a
one-sided CI width; use the empirical standard deviation of the actual draws.
Retain 90% and 95% intervals separately. Inspect finite tail support, quantile
sensitivity and independent-seed or split-sample stability near boundaries.
Split-half checks are diagnostics, not proof of Monte Carlo convergence.

Kernel point validation does not validate an asymptotic sandwich covariance.
Compare bootstrap and MLR/delta intervals as different procedures; do not label
external R draws as native Mplus draws. Do not apply full-family multiplicity
correction to a pilot or silently promote pilot results to manuscript adoption.

Task evidence: `scientific_audit_20261002/experiments/recursive_gaussian_kernel_v1/`
contains the baseline parameter comparison, `lavaan_validation.csv`,
`cluster_resample_validation.csv`, and saved source/copy identities. Scripts
`pilot_recursive_gaussian_kernel.R`, `validate_recursive_gaussian_lavaan.R`,
`validate_cluster_kernel_resamples.R` implement the separate checks. A resumable
bootstrap pilot and independent endpoint validator use the same audit directory;
inspect their actual terminal evidence before claiming bootstrap completion.

The first 1,000-replicate run subsequently completed with 1,000 successes;
all selected cluster identities were replayed from saved seeds. Its 32 effects
included one BC-versus-delta 95% classification difference and two split-half
classification differences. The smallest adjusted tail had only about 5.07
effective draws. Thus success counts and exact endpoint reconstruction do not
establish adequate Monte Carlo precision. Increase draws and use an independent
seed for the complete pilot effect set before deciding a boundary result.
The measured replicate compute sum was 456.610 seconds, excluding transport,
serialization and verification; it is not a controlled Mplus speedup factor.

## Profile bookkeeping before changing the statistical algorithm

Profiling the first independent-seed batch found repeated `unique`/`vapply`
cluster checks and per-parameter data-frame construction consumed substantial
time. A cluster frequency vector indexed back to source rows gives exactly the
same weights as expanding all selected cluster rows. Precompute equation layout
and cross-product slices, return numeric parameter vectors, and construct the
output table after fitting. Ten actual replicate comparisons covered 1,100
parameters with maximum difference 3.553e-15; their row weights were identical.
Keep the same ML stopping tolerance and covariance checks. Bind the optimized
solver hash into resumable state; never mix changed algorithms silently.

The independent 5,000-replicate run kept all 32 effects, with 5,000 successes.
Compute time summed to 576.005 seconds, median replicate 0.104 seconds, versus
456.610 seconds for the earlier 1,000-replicate implementation. These are
observed R implementation timings for this model and workload, not controlled
Mplus-version comparisons. Different run sizes/seeds and bookkeeping overhead
must remain explicit. Separate run directories preserve the original draw state.

## Monte Carlo uncertainty is a separate gate

Two halves of a 5,000-draw run can agree while an independent seed or a precision
bound still identifies a boundary. In this example, both half-run 95% classes
agreed, but the new seed changed two classifications relative to the 1,000-draw
run. Conservative simultaneous Monte Carlo bounds left three 95% classifications
unresolved. Do not keep drawing until a preferred significance label appears.

One diagnostic constructs Clopper–Pearson bounds for the bias fraction using
one independent half, and binomial order-statistic bounds using the other half.
Transform bias-fraction bounds through the BC probability formula; account for
both probability estimation and quantile error. Reverse the halves, allocate
the numerical failure budget across every effect/endpoint/direction, and retain
the directional bounds before intersecting them. Random estimated probabilities
must not be treated as fixed when evaluated on the same sample without an
appropriate joint argument. Here the split makes the two stages independent.
Infinite order-statistic limits and empty intersections remain explicit failures
of precision, not values to clamp to the observed minimum/maximum.

These bounds concern an ideal-bootstrap endpoint conditional on the fixed data,
model and point estimate, assuming independent bootstrap replicates. They are
not confidence bands for research parameters, proof of bootstrap validity,
causal identification, or FDR control. See `check_cluster_BC_monte_carlo.R` and
the independent SciPy implementation `validate_BC_monte_carlo.py`; inspect
their actual saved validation before claiming a numeric pass.
