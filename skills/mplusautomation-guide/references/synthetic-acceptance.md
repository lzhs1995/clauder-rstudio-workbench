# Independent synthetic acceptance

Synthetic acceptance is independent of unresolved historical study provenance.
Use this route to test the skill without real participants, historical CSVs or a
dissertation workspace. The tests invoke a licensed Mplus installation; compilation
alone is not acceptance. Use the companion workbench to bind a live RStudio session
and submit long jobs as durable async workers.

## Configuration and template matrix

The native acceptance scripts take caller-supplied output, skill, engine and Python
paths. `test_native_acceptance.R` defines `run_matrix()`, `run_templates()` and
`run_benchmark()`; load it with `source(..., local=TRUE)` in the async worker.
Required R packages are MplusAutomation, digest, jsonlite, ps, processx, ggplot2,
officer, flextable and svglite. Native Windows Python needs psutil. Supply the
licensed Mplus executable explicitly; the skill does not install or redistribute it.

```r
source(file.path(skill, "scripts/test_native_acceptance.R"), local = TRUE)
for (suite in c("base_mlr", "base_bc", "migration_mlr", "migration_bc")) {
  run_matrix(suite, matrix_root, skill, engine, python)
}
run_templates(template_root, skill, engine, python)
```

Use a fresh matrix root for changed code. Each suite runs APIM, APIMeM, APIMoM and
b-path APIMeMoM. MLR uses an explicit pair cluster; BC uses ML with 1,000 native row
bootstrap draws, which does not account for repeated rows as a cluster bootstrap.
The two seed-fixed synthetic datasets have 400 records and 200 pair labels each.
Migration changes numerical data, source names, ID vocabulary, member order and
moderator probes through configuration. Native bootstrap randomness remains under
the engine's default policy, so repeated BC intervals need not be identical.

The template fixture preserves different controls in the two member equations,
paired residual covariances, derived products and free versus equal b paths. It
executes two models, verifies equality and parameter counts, and retains both input
and result hashes. It is not an execution of the private Chapter 4 templates.

## Validate observable outputs

Run `scripts/validate_workflow_outputs.py OUTPUT_ROOT` with native Windows Python.
It independently reconstructs all directed products and contrasts, reads probes
from the actual INP, and checks MLR endpoints or the native printed BC interval table.
The fixed formula tolerance is 2e-6 for SAVEDATA rounding; native printed point/SE
checks use a half-unit at the printed third decimal. Do not enlarge tolerances after
observing a failure.

Inspect plot-data coverage, variable/member dictionaries and the selected-row ledger.
Review SVG/PNG/PDF figures and Word tables, including page widths, repeated table
headers, numeric formatting, inference captions and every configured effect. Finite
sample estimates are not required to equal population-generating coefficients.
The example Word format rounds effects to three decimal places and p-values to
four; a displayed 0.0000 is a rounded value, not an assertion that p is exactly zero.
Use the numeric CSV for precise values, and the member/path dictionary to interpret
the compact parameter labels used in the example plots.

An output-only repair needs its own receipt and numerical-code comparison. Preserve
the first output; do not rerun Mplus merely to change page layout. A change to model,
data, precision parsing or effect computation requires the relevant numerical tests.

## Recovery and resource behavior

Use a fresh `attempt` string when resuming a stopped matrix worker, so observation
logs stay separate. `prepare_only=TRUE` stops at a durable interruption checkpoint
and waits; an authorized controller can verify no owned Mplus process, cancel that
worker and resume with `prepare_only=FALSE`. Compare input hashes before and after.
This tests interruption between compile and fit, not arbitrary mid-estimation recovery.

Completed OUTs are reused only under their original input/configuration bindings.
Test changed configuration, tampered OUT, missing precision results and unbound OUT
as negative cases, restoring the synthetic fixture after each test. They must not
trigger silent refits or adoption.

`run_benchmark()` copies one synthetic conditional-mediation input/data into four
independent directories, alternating observation and AboveNormal coordination.
Both methods retain the same estimator, bootstrap count and engine. Keep CPU/memory
samples, child identities, timings and restoration outcomes. Four observations are
a small local comparison, not a general performance guarantee. If the directional
benefit is inconsistent, keep default scheduling.

The migration BC fixture also applies and restores scheduling to its own running
conditional-mediation Mplus child. No affinity, external task, RStudio session or
system power policy is changed. Resource holds preserve results and retry within a
bounded interval; diagnose repeated holds instead of relaunching successful models.

## Delivery

Bind claims to exact implementation and fixture hashes, native tool receipts,
engine/package versions, numerical checks and visual review. Share only synthetic
examples and sanitized summaries; retain local process identities and paths in local
evidence. Technical skill acceptance and historical manuscript reproduction have
independent completion states.
