# Latent products: calibration, complete covariance and full MI

Use this reference when adding a continuous latent `XWITH` product to an
already accepted growth model. It applies to the shared Windows RStudio /
ClaudeR / MplusAutomation scientific scripts, whether the agent runs on
Windows or controls that session from a Mac. Transport does not change the
estimand, numerical gates or pooling method; see the
[two-entry workflow](rstudio-two-entry-workflow.md).

## Freeze the model before calibrating it

Keep the original sample, saved imputations, data hashes, controls, measurement
loadings, residual structure and low-order paths. Remove an old product and
its paths explicitly when the new model replaces it. A start value marked
`*` is not a fixed parameter marked `@`. Count and identify every free
parameter from TECH1; normal termination alone does not prove the intended
model ran.

For the accepted CHARLS SD M1 extension, one model contains both
`IX XWITH IZ -> IY` and `IX XWITH IZ -> SY`, retaining `SY ON IY`. Its 126
parent parameters plus two product paths make 128. M2 instead contains only
`IX XWITH SZ -> SY`, retaining the same parent structure, for 127 parameters.
The direct SY coefficient and a propagated total association answer different
questions; do not replace the registered target after looking at results.

Calibrate each new structure with its own predefined alternative starts and
integration comparison. Each GH15 start must come from its corresponding
accepted GH7 endpoint. A shared start for later imputations must use an actual
accepted high-precision endpoint, not the input values that preceded it.
Source hashes and the parameter-to-start map make that distinction reviewable.
The M2 full batch retained nine admissions: the accepted parent P0, four
single-endpoint acceptances (A7/B7/A15/B15), and four comparisons
(A7–B7, A7–A15, B7–B15, A15–B15). Bind the closed pilot ledger separately;
its remaining allowance does not fund or reset a new full-batch budget.

## Propagate correlated products with nonzero means

For the supported acyclic model, fix observed controls at zero and write the
linear growth factors as below. At a different fixed value `c`, replace
`alpha` by `alpha + Gamma c` consistently.

```text
A  = (I - B)^(-1)
f0 = A(alpha + epsilon),  E(epsilon) = 0,  Cov(epsilon) = Psi
mu = A alpha,             G0 = A Psi A'
Q  = f0[a] * f0[b],        g = A d
f  = f0 + g Q
```

This construction requires joint-Gaussian innovations and no product feedback
to its own inputs: `g[a] = g[b] = 0`. The product has no independently estimated
innovation variance or additional regression equation. Reject unsupported
feedback or extra product paths rather than applying this formula to them.
Check both TECH1 parameter IDs and values: a free coefficient estimated at
zero is not a declared structural zero.

For correlated factors with nonzero means, use the complete moments:

```text
cQ = mu[a] G0[,b] + mu[b] G0[,a]
vQ = G0[a,a] G0[b,b] + G0[a,b]^2
     + mu[a]^2 G0[b,b] + mu[b]^2 G0[a,a]
     + 2 mu[a] mu[b] G0[a,b]
Cov(f) = G0 + cQ g' + g cQ' + vQ g g'
Sigma  = Lambda Cov(f) Lambda' + Theta
```

The final measurement formula also retains the model's declared residual
orthogonality assumptions. In M1, propagation through `SY ON IY` gives
`g[SY] = d1s + bsyiy*d1i`; omitting that term changes the covariance check.
In the supported M2 structure, only SY receives the product and has no
outgoing growth-factor path, so `g = d`. Its IX/SZ covariance and mean terms
still remain. These checks concern model-implied covariance conditional on
the fixed controls, not empirical marginal covariance or a mean-model audit.

Recover fixed loadings at the frozen input precision after checking agreement
with the rounded TECH1 printout. Keep free loadings at their saved high
precision. Inspect residual/factor covariance rank and positive definiteness,
as well as the full parameter covariance; these are different matrices.

## Compare all parameters and the complete covariance

Require independent saved-output acceptance for both endpoints before a
numerical comparison. Recheck the accepted source hashes, exact exported file
set, execution claim, frozen plan, executed input and data identity. Construct
unique `(matrix, row, column)` keys from TECH1; normalize symmetric PSI/THETA
orientation and apply the same semantic permutation to estimates, SEs and
both covariance axes. Parameter numbers alone are not cross-model identities.

The verified case retained its predefined limits: absolute LL difference
including both printed rounding intervals at most `.01`; every estimate
difference divided by its reference SE at most `.05`; every relative SE
difference at most `.05`; and every covariance difference divided by the
reference SE outer product at most `.05`. Preserve the registered limits;
these observed contracts are not universal defaults for every study. Check
all cells, not only the interaction paths or the covariance diagonal.

## Pool the complete admitted family

Pool only after all planned imputations pass. Preserve each robust covariance
matrix and align the complete estimate vector and covariance before Rubin
pooling. Keep within-, between- and total-imputation matrices, scalar intervals,
degrees of freedom and MCSE/SE available for independent reconstruction.

M1's two registered product coefficients use a joint two-df D1 test plus their
separate scalar intervals. `mitml::testConstraints(method = "D1")` uses its
average-RIV construction; a Wald statistic formed from Rubin's total covariance
is not that D1 test. M2's single registered coefficient uses scalar Rubin
inference. Save the actual package version and function source/hash when
independently reproducing the method, including its constraint-derivative
convention. The verified M1 and M2 cases reported infinite complete-data df as
primary and 437 complete-data df as sensitivity; retain the study's own declared
df choice. The sensitivity's final pooled df need not equal its complete-data df.

Do not pool a successful subset, average imputation p-values or fill missing
family tests with invented p-values. An unfinished fixed family remains
unfinished; a partial result cannot be labelled its completed Holm adjustment.
ADL working MI with observed product auxiliaries was retained in this case;
exact substantive-model congeniality and MAR were not established by numerical
acceptance. A completed extension does not repair an unrelated CFPS branch.

## Evidence and cost boundary: 2026-11-04

M1 reused its accepted MI01 and completed MI02–20: 19 new calls,
1,273.1365357 engine seconds, 20 accepted imputations and 128 parameters.
Saved-output verification covered 6,125 checks; independent full Rubin/D1
readback covered another 306. Counts describe these artifacts, not general
proof that every model supported by the guide is correct.

By 10:52 UTC, M2 also completed 20/20 imputations and all 127-parameter Rubin
pooling: MI01 reused its accepted A15 endpoint; MI02–20 added 19 calls and
1,233.2910747 engine seconds. The original ADL working MI and data hashes were
reused without new imputation. All 7,218 saved-output checks and 292 independent
pooling checks passed; pooling through Windows RStudio/ClaudeR added no Mplus
calls. MI02–20 each used one GH15 run with the frozen shared MI01 A15 start;
MI01's four-point calibration does not establish a global optimum for every MI.

The registered scalar target, its primary and Barnard–Rubin sensitivity
estimates, intervals, raw p-values and MCSE/SE ratios were independently
reconciled against the saved study artifacts. Retain those numerical results
in the study evidence; the reusable guide records the execution and acceptance
method. A nonsignificant result does not establish absence of an association.
At this snapshot, M1's joint test and M2's scalar test completed 2/12 registered
tests; no final Holm adjustment was computed. Partial calibration of M4 does
not count as full-MI completion. The working-MI and CFPS limitations above
still apply.

Keep pilot and full-batch budgets separate and retain all prior failed costs.
One observed R JSON round trip changed a historical elapsed value from
`204.6378506999462` to `204.637850699946`. A bounded `1e-9`-second tolerance
was applied only to historical accounting fields, with the original failure
and change preserved. It did not loosen statistical thresholds or input/data
hash checks. A missing exit receipt means unknown cost, not a new zero budget.
See [engine cost accounting](engine-cost-accounting.md) and the separate
[batch-versus-pilot timing evidence](queue-efficiency.md#separate-batch-throughput-from-calibration-time).

## Separate gender-case boundary: 2026-11-06

In a separate gender working-MI continuation, both M1 and M2 completed
independent Windows verification of all 20 saved members, pooling through the
original Windows RStudio/ClaudeR session, and independent pooled-output
readback. M1 retained its joint two-df D1 test and scalar intervals; M2 retained
its sole registered scalar Rubin target. Each kept its own predeclared primary
and sensitivity degrees of freedom. Mac collection was still pending, so these
are Windows acceptances, not Mac returned-output acceptances.

The earlier SD results do not transfer to this different sample. Each accepted
family remains bound to its own model, saved imputations and source hashes.
The fixed family was now 5/12 complete, without a partial Holm adjustment;
working-MI limitations and unrelated research boundaries remained unchanged.

M4's A7 audit recovered from a Windows path-representation failure by reading
the same saved output with a separately named adapter. That recovery did not
rerun A7 or establish the remaining calibration points, complete MI or pooling.
Its successor entries bind the accepted A7 audit to its original source SHA
and later stages to their own frozen auditor; a prepared or running successor
is not an accepted result. See the
[Windows saved-output route](remote-output-acceptance.md#windows原件独审与原rstudio合并).
