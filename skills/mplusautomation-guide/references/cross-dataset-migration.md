# Cross-dataset growth-model migration

Use this workflow when an established research framework moves to a different
panel study. A successful column rename proves only mapping correctness; it does
not establish measurement equivalence, suitable growth form, or class validity.

## Research specification

Keep a study-specific configuration alongside the analysis, rather than embedding
private paths or study measurement rules in this skill. Record:

- Dataset and input hashes; historical-snapshot or current-data analysis lane.
- Construct definitions and source columns by wave, score direction and range,
  family aggregation, eligible sample, covariates and missing-data treatment.
- Actual observation times, chosen growth forms and any explicit piecewise knot.
- Requested model families and outcomes, including novel branches with no history.
- Explicit MODEL/ANALYSIS syntax, class enumeration/selection criteria, and
  classification-error treatment for downstream models.

`scripts/growth_time_basis.R` supplies linear, quadratic and continuous piecewise
loadings for irregular times. It requires the researcher to supply a knot, and
does not select one from significance or insert syntax into existing models.
Check that each observed variable appears exactly once in each loading vector.

## Recover evidence before estimating

Hash source scripts, analysis data, Mplus inputs/outputs and manuscript files.
Compare Word package hashes separately from normalized table content and embedded
media hashes. Identical manuscript objects establish shared content, not which R
script generated it. Search script contents beyond filenames: mixed-study files
can contain the missing analysis in a late section.

Map manuscript rows through multiple fit statistics, sample size, parameter
labels and model specification. AIC/BIC rounded-value matches are candidates;
retain all matching models until other evidence distinguishes them. Keep
ambiguous and unmatched cases visible. Never infer execution provenance solely
from a matching output directory or model basename.

Compare the historical Mplus DATA files to today's analysis data numerically,
with explicit names/order, missing codes and a documented write-precision
tolerance. Character identifiers may have been converted to factor indices by
old code: a nonidentifier match does not validate cross-file joins. Preserve the
identifier crosswalk when rebuilding; never join using unexplained encoded IDs.

## Two execution lanes

**Historical reconstruction:** preserve the historical data and actual embedded
input specification; validate or reuse successful results with evidence. Repair
runtime/path issues separately from statistical revisions.

**Current-data continuation:** use audited current data, an explicit study
specification and separate model directories. Missing historical output is not a
reason to defer an authorized new analysis. Resolve changed samples or measurement
before reusing old estimates. A statistical correction invalidates dependent
results and triggers a distinct version, not an overwrite.

Class models require admissible variances, reliable standard errors, repeated
best likelihood, adequate class sizes and substantive interpretation. Record
alternative/failed fits without choosing measurement definitions by significance.
Multiple-imputation outputs can lack the ordinary termination marker; check
requested/completed counts, results and warnings together. Estimation success,
saved-data completeness and downstream eligibility are separate states.

Associating two latent trajectory classifications over the same observation
period is not a temporal transition, even if implemented using an LTA-style
likelihood. Preserve classification error and describe the estimand accurately.

## Migration acceptance

Verify the mapping utility with renamed inputs and changed data; test irregular
time handling and invalid configurations. Then validate representative licensed
models from every model family actually used in the new study. Compare data,
specifications, parameters, class labels and manuscript display values. Record
which model families remain unvalidated; a single synthetic linear model does
not certify GMM, imputation or class-association workflows.

Keep dataset-specific instruments and interpretation in the worked example.
Cross-study comparisons must acknowledge different measures, periods and samples;
raw coefficients on different scales are not directly interchangeable.
