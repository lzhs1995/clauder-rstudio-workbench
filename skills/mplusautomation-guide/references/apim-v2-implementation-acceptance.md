# Chapter 4 APIM v2 implementation and acceptance

This reference records the reusable Chapter 4 implementation. It is a
technical skill acceptance record; it does not release dissertation claims or
replace unresolved historical data provenance.

## Reusable workflow

The v2 runner is selected by `schema_version = 2` in `run_apim_workflow()`.
The caller supplies a CSV (or an explicitly hashed archived DAT), row and
cluster identifiers, two ordered member columns, sample filters, complete-case
policy, transformations, equation controls, equality groups, moderator
declarations, probes/contrasts, inference and an isolated output root.

The implementation then performs these stages:

1. **Check and snapshot.** `apim_v2_config.R` validates the complete contract.
   `apim_v2_io.py` rejects overlapping source/run roots, symlinks, junctions and
   hardlinks, then snapshots source bytes and records SHA-256 hashes.
2. **Prepare.** `apim_v2_models.R` reads the snapshot, filters the declared
   sample, converts pair columns in the declared order, writes `data.dat`, and
   saves selected rows, exclusions, variable/product dictionaries, transform
   moments and probe mappings.
3. **Compile.** A six-axis grid is represented by a real MplusAutomation
   `[[init]]` block. `compile_template_bundle.R` uses the installed
   `processInit()`/`createModels()` parser, verifies the complete filename set,
   and preserves complete templates byte-for-byte apart from the relocated
   output directory. Each expanded INP is hash-bound to its preparation.
4. **Estimate.** `mplus_queue.py` and `mplus_queue_worker.R` persist requests in
   SQLite, claim each request with a worker identity, run the explicit Mplus 9
   executable through `MplusAutomation::runModels()`, monitor the owned worker
   and Mplus descendants, and publish one output binding per model. Existing
   completed outputs are imported only when input/output/engine fingerprints
   match; stale or orphan reservations require explicit reconciliation.
5. **Read and map.** `results.R` reads `readModels()` output and RESULTS SAVING
   blocks, maps repeated equality labels to the unique free parameter, and
   maps means/variances and covariance identities by semantic keys. For native
   row BC, requested/completed draws and the printed BC endpoints are retained.
6. **Effects and presentation.** The effect dictionary names direct, indirect,
   total, simple-slope, conditional-a, conditional-indirect, conditional-total and contrast
   expressions. `effects.csv`/RDS is produced before SVG/PNG/PDF conditional
   figures and Word/HTML tables. The display layer never filters effects by
   significance.
7. **Independent checks.** `validate_apim_v2_native.py` recursively expands
   `MODEL CONSTRAINT` expressions and compares them with the saved effects,
   while `validate_benchmark.py` independently reconstructs queue intervals
   and overlap. Both write durable JSON receipts.

## Model and inference scope

The accepted synthetic matrix contains two APIM, two APIMeM, three APIMoM and
three b-path APIMeMoM scenarios for each of two data/member/sample mappings.
The MLR contract is `TYPE = COMPLEX; ESTIMATOR = MLR` with the declared dyad
cluster. The BC contract is `TYPE = GENERAL; ESTIMATOR = ML` with 1,000 native
row bootstrap draws and `CINTERVAL(BCBOOTSTRAP)`. The BC route is a row
bootstrap contract and does not claim cluster-bootstrap inference.

The moderator implementation covers paired continuous W, shared binary W and
shared categorical W with explicit treatment coding and K−1 products. The
native acceptance matrix above covers moderation of the b path in APIMeMoM.

## APIMeMoM moderated paths

An APIMeMoM design may set `moderated_paths` to `"b"` (default), `"a"` or
`"ab"`; any other family that sets the field is rejected at check time.

| Value | Products (equation, path label) | W main effects | Conditional effects |
| --- | --- | --- | --- |
| `b` | m_k × W_h in y_j, `z{j}{k}{h}` | y equations | `simple_slope`; indirect a × b(W) |
| `a` | x_k × W_h in m_v, `u{v}{k}{h}` | m equations | `conditional_a`; indirect a(W) × b |
| `ab` | both sets | y and m equations | both kinds; indirect a(W) × b(W) |

Here a(W) = a{v}{k} + Σh u{v}{k}h·W_h is defined once per X member, M member
and probe (kind `conditional_a`, no Y target), and b(W) = b{j}{v} + Σh
z{j}{v}h·W_h. The conditional indirect effect expands their product, so under
`ab` it is not a single index of moderated mediation. The direct effect c is not
moderated, and the conditional total effect is c plus the conditional indirect
effects. Without b-path products no `simple_slope` is listed. Contrasts are
differences between probe-specific conditional indirect effects. The a-path
products are recorded in `product_dictionary_a.csv`; the default `b` output
files are unchanged.

Acceptance status: the compile-level contract tests pass. With the default `b`,
the INP, `data.dat`, path, product and effect dictionaries of the example
configuration are byte-identical to main 33ab350 (10 models, 46 files, 0
differences).
The `a`/`ab` tests check product placement, W main effects, effect kinds and
the MODEL CONSTRAINT formula identity under assigned path values, and a mutated
formula is caught. Native Windows Mplus synthetic acceptance of `a` and `ab`
(MLR and row BC) is in progress. Until its receipt is recorded here, treat
`a`/`ab` as compile-verified only.

## Native acceptance record

The isolated acceptance roots contain the full artifacts and hashes:

| Route | Models/calls | Result |
| --- | ---: | --- |
| A mapping, MLR | 10 | native fit, parse/effects/render PASS |
| A mapping, row BC | 10 | native fit, 1,000/1,000 draws, parse/effects/render PASS |
| B renamed/reordered mapping, MLR | 10 | native fit, parse/effects/render PASS |
| B renamed/reordered mapping, row BC | 10 | native fit, 1,000/1,000 draws, parse/effects/render PASS |
| complete supplied `[[init]]` template | 2 | native fit and independent validation PASS |
| one-slot benchmark | 4 | 4/4 native fits; no overlap |
| two-slot benchmark | 4 | 4/4 native fits; two measured overlap pairs |

The four 10-model roots each pass independent formula/output-binding validation
for 296 effects. The complete-template root passes 8 effects. The benchmark
roots each pass 16 effects. The two-slot benchmark is an observed local result,
not a general speed guarantee; the queue retains one slot as the default unless
the calibration and current headroom admit two.

The native RStudio jobs used for the final complete-template and benchmark
routes were `0d611db1`, `b99393ee` and `0b22276f`; the A/B MLR and BC matrix
receipts are retained in the local acceptance roots and their guarded evidence
records. Package/runtime versions, engine hash, resource measurements, queue
events and session information are stored beside each root.

## Migration and historical boundary

Changing data paths, variable names, member order, sample selection or probes is
supported through the configuration and migration fixture. The original thesis
files and historical 612-model replay remain read-only and are not silently
replaced by synthetic acceptance. A historical DAT is admitted only after its
bytes, declared columns and no-transformation contract are verified; scientific
adoption still requires the separate provenance and manuscript gates.

## Reproduce the acceptance shape

Use the fixture with a new output root and an explicit Mplus executable:

```r
source(file.path(skill, "scripts", "workflow.R"), local = TRUE)
source(file.path(skill, "assets", "example_config_v2.R"), local = TRUE)
cfg <- example_apim_config_v2(data_csv, run_root, mplus9, windows_python,
                              renamed = FALSE,
                              inference = "spouse_cluster_MLR_delta")
run_apim_workflow(cfg)
```

For a complete existing template, add a named `template_bundles` entry with
the source SHA-256 and the full expected filename set. Do not point a template
or source inside its output root. For a changed specification, use a fresh root
instead of mutating a completed one.
