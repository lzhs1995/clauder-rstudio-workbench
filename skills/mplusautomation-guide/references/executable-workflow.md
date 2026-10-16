# Executable four-family workflow

## Working snapshot versus validated release

A historical release manifest identifies the files hashed at that time. After
editing the skill, verify its entries and retain that manifest as historical
evidence. Record current content in a separately labelled working snapshot; a
hash-complete snapshot does not certify native fits, statistical inference or
renamed-data migration. Bind validation receipts to the exact runner/config/input
and engine versions they tested. Do not carry a prior PASS to changed code.

For a manuscript reproduction, track source closure, numerical agreement,
display semantics, inference and manuscript adoption independently. A complete
paragraph index is a navigation aid, not full-clause acceptance. Consolidate
remaining decisions against the user's requirements before extending audit scope.
If historical row identity is not recoverable, state that limitation; replaying
an archived DAT and running a current CSV are different provenance contracts.

An existing OUT without `output_binding.rds` is rejected as `UNBOUND_OUTPUT`,
even if it terminated normally. For deliberate import, verify the originating
run, exact INP and DAT hashes, engine and OUT identity before writing a binding.
An interrupted fit that finished before its receipt was saved needs this explicit
recovery check; it must not be silently adopted or rerun.

## Entry and current support

Load `scripts/workflow.R` in the intended RStudio session. It loads `results.R`
relative to the source file, including when called from a local environment or
durable async worker. No global workspace is cleared and no packages are installed.

```r
source(file.path(skill_root, "scripts/workflow.R"), local = TRUE)
source(file.path(skill_root, "assets/example_config.R"), local = TRUE)
write_apim_example_data(data_path)
cfg <- example_apim_config(data_path, output_dir, mplus_executable, python_executable)
run_apim_workflow(cfg, stages = c("check", "prepare", "compile"))
# Submit long stages through the ClaudeR native async workbench.
run_apim_workflow(cfg, stages = c("fit", "parse", "effects", "render", "validate"))
```

`skill_root`, data, engine, Python and output paths are supplied by the caller.
The example contains no real participants or hardcoded user directory.

| Capability | Executable support |
|---|---|
| APIM | Two distinguishable members; actor/partner direct paths |
| APIMeM | Two mediators; all eight directed X→M→Y products; direct and total effects |
| APIMoM | X→Y moderation by either member's W, four products and recipient-specific coefficients |
| APIMeMoM | b-path moderation by either member's W, conditional products and contrasts |
| Inference | COMPLEX/MLR with explicit cluster ID; ML/row-BC mode validated with independent synthetic fits |
| Samples | Explicit complete-case policy per model; optional exact-value filters |
| Scale | None, pooled centering or pooled z across the selected two-member sample |
| Outputs | Traceable CSV/RDS, numeric plot data, SVG/PNG/PDF, Word tables |
| Unsupported in this entry | FIML with incomplete Y, categorical outcomes, categorical moderator coding, shared moderator columns, equation-specific control sets, latent interactions, a-path moderation, equality-constrained models, external bootstrap execution |

The unsupported entries remain methods/extensions documented elsewhere in this
skill. Do not route them through this entry or claim this initial runner replaces
every historical Chapter 4 specification. Expand support with separate numerical
calibration. Parameterizing a four-family example is not scientific certification.
For exact reproduction from reviewed study templates, use the separate
[template-preserving route](template-preserving-workflow.md). It retains constraint
steps and complete model bodies; it does not make the simplified runner support
those specifications or bypass study-specific source prerequisites.

## Configuration contract

Every model has a unique `id`, exact `family`, two-column `x` and `y` mappings,
and a `testing_family`. Mediation adds `m`; moderation adds `w` and named `probes`.
Optional `controls` are a list of two-member column pairs, entered in both outcome
equations and both mediator equations. No variable-name heuristic selects controls.

Probe values are **explicit values on the prepared W scale**, not automatically
±SD. Each probe is `(W_member1, W_member2)`; the first two named probes define the
reported contrast as second minus first. These are simultaneous probe scenarios,
not an implicit one-variable-at-a-time moderation claim. Keep their interpretation
in the report. With moderation, unconditional indirect/total expressions refer to
W1=W2=0; report them with that reference condition.

`cluster` and `row_id` are read as text, preserving long IDs. Duplicate record IDs,
missing IDs, unrecognized numeric values, overlapping roles, zero pooled SD, invalid
model families and unsupported inference strings fail before estimation. Missing
values are removed only under the explicitly selected complete-case policy.
Keep the resulting excluded-row ledger; it does not establish ignorability.

Source column names are mapped to short Mplus aliases (`x1`, `x2`, `m1`, etc.).
The variable dictionary separates source names, member role and Mplus name.
Center/scale values, selected row IDs and source-file hashes remain durable.

For a variable grid, `build_apim_model_grid()` in the example asset accepts lists
of paired X/Y/M/W columns and the selected families. It expands only applicable
combinations (APIM ignores M/W; APIMeM uses M; APIMoM uses W; APIMeMoM uses both).
Supply the testing-family name and probe values explicitly, review the returned
model list, then assign it to `cfg$models`. Common probes apply to every selected
W on its prepared scale; edit each model's probes when moderators need different
values. Expansion is a proposed execution inventory, not permission to interpret
every generated hypothesis as confirmatory or to choose only significant results.

## Native row-bootstrap BC mode

Select this mode explicitly; it does not replace the MLR cluster contract:

```r
cfg$inference <- "row_ML_BCbootstrap"
cfg$bootstrap <- list(
  draws = 1000L,
  resampling_unit = "row",
  seed_policy = "engine_default_not_user_controlled"
)
```

The compiler emits GENERAL/ML, BOOTSTRAP and CINTERVAL(BCBOOTSTRAP), omits
CLUSTER, and requests TECH1 plus unstandardized SAVEDATA RESULTS. The recorded
pair ID count remains descriptive; it does not make this a cluster bootstrap.
No BSEED/STSEED/MCSEED is invented as a bootstrap seed. The selected policy
discloses that this entry does not control native bootstrap randomness.

The native BC helper in `scripts/results.R` verifies the echoed ML/BC declaration,
the absence of clustering, and equal requested/completed draws. It joins exact
parameter keys or typed MODEL INDIRECT keys (`pred/outcome/summary` or
`pred/intervening/outcome`) and preserves native printed 90/95/99% endpoints.
It rejects duplicate keys, absent effects, nonfinite endpoints and unmapped group
dimensions. MplusAutomation 1.2 can return indirect CI columns as character;
only complete numeric literals are converted. A BC interval need not contain
the original point estimate. No normal-formula fallback is used.

```r
source(file.path(skill_root, "scripts/results.R"), local = TRUE)
parsed <- MplusAutomation::readModels(out_path,
  what = c("input", "parameters", "indirect", "summaries"))
ci <- apim_native_bc_intervals(parsed, readLines(out_path), effect_keys,
  component = "indirect_specific", requested = 1000L)
```

`component` also accepts `parameters` and `indirect_overall`. These read-only
helpers can inspect historical results without adopting their source chain or
rerunning a model. The runner still constructs its products through MODEL
CONSTRAINT. It does not translate every historical MODEL INDIRECT specification.

Point estimates/SEs in runner effects still require verified SAVEDATA/TECH1
mapping. Endpoints carry `interval_precision=native_OUT_printed`; GH5 precision
has not been reconstructed by this helper. `p`, BH and BY use the normal Wald
ratio with the native bootstrap SE and are explicitly labelled as such. They
are not BC p-values or tests obtained by inverting the asymmetric interval.
The plot axis and Word note identify the actual inference method.

Native acceptance on 2026-10-15 covers four model families under both MLR and
row-BC, and a second dataset with new values, names, IDs and reversed member
mapping: 16 fits, including eight with 1,000 completed bootstrap draws each.
The two-vector BC precision layout, 336 effect rows, native intervals and exported
plot/table data passed independent numerical checks. Word tables use fixed-width
landscape pages; a layout-only repair preserved the earlier fits and numerical
functions. See [synthetic acceptance](synthetic-acceptance.md) for fixtures and
limits. The earlier 20 BC / 23 MLR compilation checks and eight archived BC
readbacks remain supplementary evidence, not substitutes for native acceptance.

The 612-model manuscript subset uses 16 of the full candidate inventory's 18
templates. Its inference split is 252 COMPLEX/MLR and 360 ML/BC models. A comment
mentioning constraints is not an executed equality constraint: no repeated single
parameter labels were found in that subset. Its 288 conditional-mediation inputs
comment out MODEL INDIRECT with `!* ... *!` and define effects in MODEL CONSTRAINT.
Strip block comments before diagnosing active syntax. A new equivalent compiler
also needs the actual equation-specific controls, shared/categorical moderators,
exogenous covariance structure and sample/scale rules; changing only inference
cannot reproduce those models.

Method references: [Mplus ANALYSIS/BOOTSTRAP](https://www.statmodel.com/HTML_UG/chapter16V8.htm),
[Mplus OUTPUT/CINTERVAL](https://www.statmodel.com/HTML_UG/chapter18V8.htm),
[MplusAutomation parameter/CI fields](https://michaelhallquist.github.io/MplusAutomation/reference/extractModelParameters.html).
Use `readModels()` in current code; the last page documents the legacy field
layout still observed in local MplusAutomation 1.2.

## Execution and recovery

`stages` selects check, prepare, compile, fit, parse, effects, render or validate.
Dependent stages require earlier artifacts. `check` has no output side effects.
The full workflow is the default; callers can stop after compilation to inspect
the generated `[[init]]` template and expanded INP before running Mplus.

The contract binds configuration, source data, engine, MplusAutomation and runner
source hashes. A changed contract requires a new output directory. The manifest
retains input and DAT hashes; output-hash mismatches are rejected. Completed fits
can be reused; failed or incomplete OUT files are retained and require an explicit
archival/recovery decision, never silent overwrite. An atomic directory lock binds
the worker PID and creation time; a lock is not itself proof of a living worker.

The runner uses one local Mplus slot and checks Windows RAM, commit and disk via
fresh probes. It declines to launch when another Mplus process is observed and
returns `RESOURCE_HOLD`. The calling coordinator can resume the unchanged contract
after review. This admission observation is not a machine-wide transactional lock;
independent schedulers must coordinate before concurrent production use.

All fits use exact INP paths and `killOnFail=FALSE`. No historical result directory,
default recursive scan, program termination or package upgrade is involved.

## Result precision and release boundaries

Parsing reads all Mplus sections, verifies N and clusters, and combines TECH1
parameter numbering with SAVEDATA RESULTS. The eight-vector standardized layout
for MLR (or two-vector unstandardized layout for the BC development branch)
must be proved by the output header and expected vector length; unsupported
layouts fail rather than silently shifting coefficients. Estimates and SEs must
match printed output within its three-decimal rounding interval.

The common effects table binds model ID, effect label, kind, source/intermediate/
recipient role, probe, N/G, estimate, SE, intervals, test family and method.
All configured effects are rendered, regardless of significance. BH/BY are computed
over the configured family's reported tests; the current entry does not infer
cross-model likelihood equivalence or symbolic alias deduplication. For duplicated
hypotheses or the Chapter 4 complete testing-unit contract, use the audited full-
scope adjustment pipeline rather than treating these example-family adjustments
as a substitute.

For independent arithmetic and file-coverage verification, run
`scripts/validate_workflow_outputs.py <output_dir> [--render-root <layout_only_output>]` using the configured Python.
It reconstructs directed effects from the saved free coefficients, independently
reads probe values from the expanded INP, checks 90/95 endpoints and each model's
plot-data coverage. It also checks plot-data identity and Word cell values/page width. It cannot certify study assumptions or replace visual inspection.

`validation.json` certifies numeric and coverage checks only. Visual review and
scientific release remain separate and are never automatically set to passed.
Normal termination does not establish causal mediation, identification adequacy,
correct handling of endogenous products, or generalizability after exclusions.

## Migration and acceptance

Use `write_apim_example_data(..., renamed=TRUE)` with
`example_apim_config(..., renamed=TRUE)` to test a second column/ID vocabulary.
No runner edits should be necessary. The documented acceptance matrix includes both inference methods and a changed-data
round: 16 real Mplus fits, saved precision validation, all requested plot/table
formats and independent effect-formula checks. Template generation alone
does not meet this gate. Keep unsuccessful development attempts separately.
