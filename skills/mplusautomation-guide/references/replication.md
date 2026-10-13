# Historical Replication

Manifest fields should identify source hash and module, model ID, input hashes,
predecessors, `.inp`, `.out`, exported table/figure and manuscript location.
Dates and filenames are clues, not sufficient proof.

## Script Segmentation

Use R's parser. Bare brace blocks can be split into statements while preserving
functions, loops and conditionals. Review transformations and test a small slice
first. Parsing is not a general security sandbox: inspect namespace-qualified
writes, dynamic paths, native commands and Mplus `FILE` clauses explicitly.

After a failed assignment, do not leave an older temporary object available for
the next model. Mark dependent work blocked rather than estimating from stale
objects. Keep a traceable source-to-adapted-code difference record.

## Multiple Imputation

- Identify the producer, schema, missing codes, seed, saved column order and
  requested imputation count.
- Freshly generated imputations and historical-draw replication answer different
  questions. Keep their run IDs and result comparisons separate.
- Keep `.out` and its saved data together. `readModels()` can locate saved data
  relative to the output file; copying just `.out` can select unrelated data.
- Validate requested/completed counts, per-imputation diagnostics, successful
  fit-statistic counts and finite estimates/standard errors.
- Imputation-only producers need a separate validation path: they may correctly
  save complete datasets without a `MODEL RESULTS` section. Validate the saved
  file list, row counts, schema and imputed columns rather than rejecting them
  as a failed structural model.
- Reproduce historical pooling as written and document its limitations. The
  mean of per-imputation p-values is not automatically a valid pooled test.

## Trials and Historical Specifications

If all executable branches are requested, retain abandoned experiments and
execute them in separate namespaces. Their saved data must not replace a
successful main-analysis predecessor.

Log infrastructure repairs such as a reversed filename suffix. Where R and
historical `.inp` disagree, create a distinct historical comparison. Do not
silently change an `ON` path, estimator or constraint to match a manuscript.

Record estimated, needs-review, estimation-error, R-error, dependency-blocked,
generated-only and not-attempted states. A failed predecessor does not make
unexecuted downstream models count as reproduced.

## Manuscript Reconciliation

Compare parameter keys before rounded cells: group, outcome, predictor,
interaction definition, estimate and standard error. A table's `I` or `S`
label may be wrong even when its value matches an output. Baseline sample
counts can also differ legitimately from a model using partially observed
parallel trajectories.
