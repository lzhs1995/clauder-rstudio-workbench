# Quadratic curves on an explicit log scale

Use `scripts/ch7_quadratic_curves.R` for the derivative of a declared quadratic
contrast, after choosing the exact model, terms, covariance and x scale.
It neither reads a dataset nor estimates a model, installs packages or writes files.
The data function uses base R; rendering requires an existing `ggplot2` installation.

## Scale and covariance contract

For a contrast containing `b_linear*x + b_quadratic*x^2`, the returned derivative is

```text
d(x) = b_linear + 2*b_quadratic*x
Var[d(x)] = V_linear,linear + 4*x*V_linear,quadratic + 4*x^2*V_quadratic,quadratic
```

The cross-covariance term changes sign for negative x. The two supported scales are:

- `binary_log_odds`: derivative of log odds for the declared outcome against its reference.
- `multinomial_log_probability_ratio`: derivative of `log(P(outcome)/P(reference))`.

Neither is a probability-scale marginal effect or an average marginal effect.
A directory or field named "ClassProb" does not establish the mathematical scale.
The same formula is valid for a selected multinomial contrast, but deriving a
probability effect requires all relevant category probabilities and derivatives.

Supply uniquely named coefficients and a square, named covariance matrix.
`terms = c(linear = "...", quadratic = "...")` binds both parameters by name;
coefficient order and matrix row/column order may differ. Nuisance parameters may
be present. The supplied entire covariance matrix is checked, then the two mapped
terms are selected. Their numerical presence does not prove correct TECH1/TECH3
mapping, a valid reference category or the intended model fit.

`source_id` is a logical evidence identifier. `covariance_type` is an explicit
caller declaration, such as `cluster_HC0`; it is preserved, never inferred.
`variable_scale` records the actual x scale (original, centered, standardized,
units and baseline as applicable). Merely renaming a variable does not convert
its scale or the coefficients. Establish that the quadratic coefficient really
multiplies the square of this same x; an orthogonal polynomial, changed
standardization or additional x interactions needs a different derivation.

Missing/non-finite coefficients, parameters or x values are rejected. Covariance
rows and columns must have unique matching names; after name alignment the
matrix must be exactly symmetric, with non-negative diagonal and eigenvalues at
the supplied precision. Negative curve variance and numeric overflow are also
rejected. No missing triangle is filled, no asymmetry is averaged, no variance is
clipped, and no cluster covariance is replaced by an ordinary covariance.
Rounded or nearly singular exports can fail this strict check: inspect the
original precision and diagnosis; do not repair the matrix silently.

## Explicit interval rule

- `ci_rule = "normal_quantile"` computes `qnorm(1-(1-ci_level)/2)` without
  rounding; `critical_value` must remain `NULL`.
- `ci_rule = "fixed_critical"` preserves an explicit positive value, including
  a historical `1.645`. `ci_level` is then only the declared nominal level.
  The metadata and plot label state that this nominal coverage is not certified;
  the actual critical value and its implied standard-normal coverage are retained.

For example, `qnorm(.95)` and `1.645` give slightly different bounds. Reproducing
an explicit historical rule must not silently switch between them. These are
pointwise normal-approximation intervals, not simultaneous bands, t intervals,
bootstrap intervals or evidence that model uncertainty has been fully addressed.

## Synthetic example

Run from the skill root, or resolve the script against that root explicitly:

```r
source("scripts/ch7_quadratic_curves.R")
beta <- c(exposure_linear = 0.3, exposure_squared = 0.05)
V <- matrix(c(0.04, 0.006, 0.006, 0.0025), 2,
            dimnames = list(names(beta), names(beta)))
curve <- ch7_quadratic_curve_data(
  coefficients = beta, vcov = V,
  terms = c(linear = "exposure_linear", quadratic = "exposure_squared"),
  x_grid = seq(-3, 2, length.out = 51),
  scale = "binary_log_odds", source_id = "synthetic_contrast_A",
  covariance_type = "synthetic_covariance",
  variable = "exposure", variable_scale = "centered units; baseline declared",
  outcome = "event", reference = "no_event",
  ci_level = 0.90, ci_rule = "fixed_critical", critical_value = 1.645
)
curve$data
plot <- ch7_quadratic_curve_plot(curve)
```

`curve$data` contains x, estimate, variance, standard error and interval bounds.
`semantics` retains source, terms, scale, covariance declaration and CI rule;
`parameters` retains the selected coefficients/covariance; `quality` explicitly
leaves model identity, historical-plot acceptance and real-data-swap acceptance
unverified. The original inputs and x-grid order are preserved. Rendering sorts
only its own data copy and returns a ggplot with semantic/quality attributes;
export size, fonts, display and file writing remain the caller's responsibility.
No term is automatically selected by significance and no x range is inferred.

## Verification boundary

`test_ch7_quadratic_curves()` uses synthetic coefficients only. It checks known
values including a nonzero cross covariance and negative x, rename/reorder
invariance, 90/95% intervals, explicit critical values, unmodified inputs,
invalid mappings/covariances and ggplot layer payloads. It runs once through the
existing family CI registry; no Mplus or browser is needed.

This interface does not replace the already completed archived-CSV redraws or
prove historical figure numbers, manuscript adoption, arbitrary covariate
combinations, a new data source or the complete RStudio/Mplus execution chain.
Use the [source/variable contract](chapter7-source-variable-contract-20261104.md)
and [replay map](chapter7-replay-map.md) for those separate evidence layers.
