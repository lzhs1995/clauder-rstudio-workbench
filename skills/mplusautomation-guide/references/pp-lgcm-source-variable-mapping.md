# Parallel-process growth: source and variable mapping

`parallel_growth_model_syntax()` in `scripts/growth_time_basis.R` compiles a
bounded **two-process covariance LGCM**. It reuses `growth_model_syntax()` for
each process and returns `model`, `variables`, `processes`, and `factors`.
Pass its combined alias-to-source `variables` mapping and `model` to
`scripts/model_mapping.R`'s `mplus_from_mapping()`.

The function declares every pair of distinct growth factors with `WITH`,
including pairs within and between processes. Each factor is regressed on its
process's selected covariates, defaulting to all mapped covariates. These are
factor residual covariances in the conditional model. It does not add directed paths between growth factors or
observed-variable residual pairs.

## Mapping contract

`processes` is a named list with exactly two entries. Each entry contains:

| Field | Meaning |
|---|---|
| `variables` | Named character vector, `Mplus_alias = source_column`, in wave order. |
| `waves` | At least three finite, strictly increasing numeric observation times; one per variable. |
| `factors` | Explicit factor aliases: two for linear, three for quadratic or piecewise growth. |
| `shape` | Optional `linear` (default), `quadratic`, or `piecewise`. |
| `knot` | Required only for piecewise growth, on that process's original time scale and strictly inside its endpoints. |
| `adjust_for` | Optional character vector of declared covariate aliases; omitted means all covariates, `character()` means none for this process. |

`covariates` is an optional named character vector with the same
alias-to-source convention. Every declared covariate must be used by at least one
process; unknown or repeated `adjust_for` aliases are rejected. Observed aliases,
factor names, and covariate aliases
must be unambiguous across both processes. Mplus aliases are case-insensitive,
start with a letter, and contain at most eight letters, digits, or underscores.
The source columns must exist and map one-to-one; `mplus_from_mapping()` accepts
numeric columns, preserves rows, values and `NA`, and rejects infinite or wholly
missing mapped columns.

Wave order is the order in each process's `variables` vector, paired with its
`waves`; it is not inferred from source column order or names. The two processes
may have different observation schedules. Each process's first wave is centered
at zero. For example, `c(2011, 2013, 2018)` gives fixed linear loadings `0, 2, 7`.
There is **no automatic division by the last time or normalization to 0–1**.
Quadratic and piecewise bases use this same centered time unit.

The returned `variables` vector determines the selected DAT column order and
Mplus aliases. It can reorder the original data frame deliberately. Verify the
written `NAMES` against the actual exported DAT order; do not copy the original
data frame's column order into `NAMES` independently.

## Compile a synthetic example without Mplus

Run from the skill directory with R and MplusAutomation installed. This example
creates only synthetic data and writes INP/DAT with `run = 0L`.

```r
source("scripts/growth_time_basis.R")
source("scripts/model_mapping.R")
stopifnot(requireNamespace("MplusAutomation", quietly = TRUE))

# 同一合成样本的两个过程与一个协变量；不使用真实研究值。
t <- seq_len(40L)
data <- data.frame(
  score_a1 = sin(t), score_a2 = sin(t) + t / 100,
  score_a3 = sin(t) + t / 50,
  score_b1 = cos(t), score_b2 = cos(t) + t / 80,
  score_b3 = cos(t) + t / 40, baseline = t / 40
)
processes <- list(
  first = list(
    variables = c(a1 = "score_a1", a2 = "score_a2", a3 = "score_a3"),
    waves = c(0, 2, 7), factors = c("ia", "sa"), shape = "linear"
  ),
  second = list(
    variables = c(b1 = "score_b1", b2 = "score_b2", b3 = "score_b3"),
    waves = c(0, 3, 7), factors = c("ib", "sb"), shape = "linear"
  )
)
syntax <- parallel_growth_model_syntax(
  processes, covariates = c(base = "baseline")
)
object <- mplus_from_mapping(
  data, syntax$variables, syntax$model,
  analysis = "ESTIMATOR = ML; PROCESSORS = 1;",
  title = "Synthetic two-process covariance growth"
)

# 新临时目录防止覆盖旧件；仅编译，不调用引擎。
compile_only <- function(object) {
  directory <- tempfile("pp-lgcm-compile-")
  dir.create(directory)
  old <- getwd()
  on.exit(setwd(old), add = TRUE)
  setwd(directory)
  MplusAutomation::mplusModeler(
    object, modelout = "model.inp", dataout = "data.dat",
    run = 0L, check = FALSE, hashfilename = FALSE,
    writeData = "always", quiet = TRUE,
    Mplus_command = "FORBIDDEN_IN_COMPILE_EXAMPLE", killOnFail = FALSE
  )
  stopifnot(file.exists("model.inp"), file.exists("data.dat"))
  directory
}
example_dir <- compile_only(object)
example_dir
```

To adjust only the first process for the declared `base` covariate:

```r
# 协变量以别名选择；空向量明确表示该过程不加协变量。
processes$first$adjust_for <- c("base")
processes$second$adjust_for <- character()
first_adjusted <- parallel_growth_model_syntax(
  processes, covariates = c(base = "baseline")
)
```

## Change source columns without changing the declared model

Replace each mapping's source-column values while preserving the intended role,
wave order, time unit, factor names, shape, and covariates. Reordering columns in
the data frame alone must not reorder waves. Changing aliases is also possible;
compare the generated syntax after mapping those aliases back to the same roles.

For an `original` / `renamed_reordered` compile check, keep the same synthetic
rows and numerical values, rename and reorder source columns, and update the
mappings. Verify every exported role column, missing-value position, fixed time
loading, factor pair and covariate path. A missing wave/role must be rejected;
output-file existence alone is insufficient. See [`test_pp_lgcm_compile_20261108.R`](../scripts/test_pp_lgcm_compile_20261108.R)
for the executable paired check, using `test_pp_lgcm_compile(output_dir, skill_root)`.

## What this entry does not cover

Source acquisition, construct scoring, direction changes, standardization,
category encoding, eligibility, missing-data treatment and DAT preparation belong
to the study script or its source-specification adapter. This entry takes the
resulting numeric table; it does not define a new `source_spec` interface or read
private files itself. A prebuilt DAT must retain its declared column schema.

All generated time loadings are fixed. Free latent-basis loadings (`*`), a third
process, directed growth-factor regressions, within-wave residual correlations,
latent interactions, known-class models and multiple imputation are outside this
entry. In particular, a free-loading starting value is not a fixed time score.
Production PP-LGCM families may require those structures and constraints; this
covariance template is not their equivalent replacement.

Changing a time unit also changes slope scales and can require corresponding
parameter transformations; changing a loading constraint, residual pair or
covariate can change the model. Keep those choices explicit in the study
specification. Compile success establishes mapping and syntax construction only;
it does not establish Mplus execution, model identification, admissible estimates,
or cross-study measurement equivalence. See
[cross-dataset growth-model migration](cross-dataset-migration.md) for the broader
acceptance boundary.
