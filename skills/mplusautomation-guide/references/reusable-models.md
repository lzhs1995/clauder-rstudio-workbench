# Reuse a model with new data and column names

Keep three layers separate: study specifications (data, mapping, measurement
times, coding and model syntax), portable R/MplusAutomation execution and
result extraction, and platform adapters (executable, paths, process identity,
resource probes and plotting backends). Replacing data should normally affect
the study layer. Changing measurement times, missing-data assumptions or
structural paths is a scientific model revision, not a filename substitution.

Use `scripts/model_mapping.R` with `scripts/mplus_workflow.R` when a new study
retains an explicitly specified model but changes its input data or column
names. `mplus_from_mapping()` accepts a data frame, a named character vector
(`Mplus alias = source column`), and explicit MODEL and ANALYSIS syntax. Its
output is an ordinary `MplusAutomation::mplusObject` accepted by
`run_mplus_model()`. It does not submit work on its own.

```r
source(file.path(guide, "scripts/model_mapping.R"))
source(file.path(guide, "scripts/mplus_workflow.R"))
columns <- c(y0 = "score_wave1", y1 = "score_wave2", y2 = "score_wave3")
object <- mplus_from_mapping(
  data = study_data, variables = columns,
  model = "i s | y0@0 y1@1 y2@2;",
  analysis = "ESTIMATOR=ML; PROCESSORS=1;",
  title = "Three-wave linear growth example"
)
# Use the approved queue/resource admission before estimating a real study.
result <- run_mplus_model(object, run_root, model_id, command = mplus_command)
```

The example assumes equally spaced observations and linear growth. Those
choices are not defaults for a new study. Supply reviewed loadings and syntax
for unequal spacing, quadratic/piecewise trajectories, parallel processes,
covariates or interactions. Source variable names may be long or non-ASCII;
aliases must be unique ignoring case, start with a letter and use at most eight
ASCII letters/digits/underscores. The mapper preserves rows, values and NA.
Categorical coding, missing-value sentinels, standardization, sampling weights
and imputations must be prepared explicitly. This helper handles one numeric
data frame; pooled multiple-imputation workflows still require the documented
staged-data and imputation-count contract.

Save the mapping and reviewed syntax alongside the study's input manifest.
Use a new model ID/run directory when data or scientific specifications change.
The fingerprint changes with the mapped model object; a renamed source column
is not permission to reuse an estimate from different data. Keep source-file
hashes separately, because identical numeric data with different source names
can intentionally produce the same Mplus data and syntax.

For a reuse check, run a small synthetic longitudinal data set, rename and
reorder its source columns, and repeat with the revised mapping. Compare
parameter identities, estimates and standard errors, not only file counts.
Use a third altered data set to confirm that the mapper actually uses new
values. This establishes the mapping/execution path, not validity of another
study's model or manuscript equivalence.
