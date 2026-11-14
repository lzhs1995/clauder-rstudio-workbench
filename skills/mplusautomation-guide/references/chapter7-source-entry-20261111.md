# Chapter 7 configurable source entry

`scripts/ch7_source_entry_20261111.R` provides one configuration entry for
LPA/LCA, LTA and mover–stayer LTA. It calls the existing
`ch7_mixture_object()` and `mplusModeler(run = 0)` to prepare inputs. It never
starts Mplus. Licensed native estimation, convergence, scientific acceptance
and comparison with prior results remain separate evidence layers.

```sh
Rscript scripts/ch7_source_entry_20261111.R config.json fresh-output-dir
```

In RStudio the same interface is:

```r
source("scripts/ch7_source_entry_20261111.R")
prepared <- ch7_source_entry("config.json", "fresh-output-dir", skill_root = ".")
```

The config may also be an R list. The returned `models` list names each model's
absolute `input` and `data` paths for the authorized execution layer. The
written manifest uses relative paths. Every model gets its own
`<model_id>/model.inp`, `source.dat`, and future `model.out`/`posterior.dat`.
An existing output directory is rejected. Preparation failure preserves partial
artifacts; resuming estimation never means silently regenerating them.

For the chapter's Mac-to-Windows validation, estimation must use the assigned
Windows RStudio/ClaudeR session, MplusAutomation and Mplus, under the project's
request/grant and process-budget controls. A local compile-only Rscript command
does not establish that runtime chain. The entry deliberately has no `run=TRUE`
or direct-executable switch.

## New source, variables, waves, K and combinations

Use `schema_version=1`, `mode="new_source"`, and these fields:

| Field | Contract |
|---|---|
| `source` | `path`, expected `sha256`, `format` (`csv` or `dta`), `encoding`, source `id`, `row_grain="person_wide"`, explicit `missing_codes`; optional `column_missing_codes` keyed by selected source names |
| `sample` | `rule="all_rows"`, `row_order="source"`; complex selection must be prepared upstream and hash-bound as a separate source |
| `transformations` | `status="none"` or `"precomputed"`, plus `description` of the scale and upstream method; no automatic standardization, thresholding, truncation or imputation |
| `waves` | Ordered records `{wave, label, time}` with unique IDs and strictly increasing numeric times |
| `mapping` | Records `{wave, role, source, target, type, scale}`; unique source names, Mplus target names and wave/role pairs |
| `id_target` | Separate Mplus column name for the source ID |
| `models` | Explicit records `{id, family, wave_ids, roles, classes, invariant, transitions, starts, estimator, processors}`; optional `seed`, `optseed`, `stayer` |

`family` is `lpa`, `lta` or `mslta`. LCA uses `family="lpa"` with only
categorical indicators. `type` is `continuous`, `binary` or `categorical`;
the latter two currently require observed 0/1 support. The current measurement
generator writes one threshold per binary indicator and does not support ordinal
or nominal multi-category measurements. It rejects unsupported coding instead
of silently reducing it to a binary model.

`wave_ids` chooses an ordered subset of the declared waves. `roles` chooses an
ordered indicator combination, present in every selected wave. Their order
defines the corresponding measurement positions across waves; invariant models
require the same type pattern. Time intervals are recorded, but an ordinary
discrete-time LTA does not turn those intervals into a continuous-time model.
`classes` is the explicitly chosen K for that model, shared across its waves.
Varying K between models is supported; different K within one longitudinal
model is not. This entry does not select K or assign semantic class names.

Every new-source and Step-3 model must explicitly declare logical `transitions`.
For four-wave LTA measurement invariance and Step-1, use `transitions=FALSE`:
the generated MODEL contains the class-specific measurements and no latent
`cN ON cN-1` regressions. `invariant=TRUE` shares measurement labels across
waves; `invariant=FALSE` gives each wave separate labels. Thus four-class
invariant/free measurement and the ref.cat.4 Step-1 structure can be declared
with `classes=4`, the appropriate `invariant`, and `transitions=FALSE`.
The final category K is the chain's reference category; this does not infer a
semantic class ordering from data or reproduce historical seeds automatically.

Use `transitions=TRUE` for LTA transition estimation, Step-3 and MS-LTA.
MS-LTA without transitions is rejected because its mover/stayer constraints
define transitions. In a single-wave LPA/LCA record the flag is still explicit
but adds no longitudinal regression. Omitting the flag from this configuration
entry is rejected. Direct callers of the older `ch7_mixture_object()` R API
retain its default `TRUE`; the new argument is appended to preserve positional
calls. Archived replay has no new flag and continues preserving original input.

`seed` writes `STSEED`, the random-start seed; `optseed` writes `OPTSEED`.
They are distinct settings. `estimator` supports ML/MLR. The model's declared
starts, invariance and processor count are preserved. No covariance or scale
transformation is added. `stayer` accepts finite named `intercept` and `slope`
logits, and retains the documented approximation to an identity transition;
it is not an exact structural-zero claim.

Sources must be numeric, except explicitly declared missing tokens. Source IDs
must be unique nonmissing exact integers within the IEEE double integer range.
CSV IDs must use integer literals; decimal and scientific notation are rejected
before numeric conversion, including strings that would silently round to an
integer. Normalize such identifiers explicitly in the source preparation step.
DTA numeric columns retain their original double values without a display-string
round trip.
The ID is retained and declared with `IDVARIABLE`. After estimation, the chain
reader independently checks its actual savedata format, ID uniqueness and
values; numeric input validation alone does not prove lossless CPROB export.
The generated DAT uses `.` for missing values and is read back against its
declared NAMES order. ID tokens and their numeric values must match exactly;
ID checks never use a numerical tolerance. Other numeric columns use
17-significant-digit decimal tokens, checked exactly against the source double's
formatted representation; numerical readback is checked at machine precision
to allow the platform's decimal-to-double parser rounding. No rows are filtered
by the entry.

To change the source, supply a new `source.path` and its independently computed
SHA256. To rename source columns, change `mapping.source`; to rename Mplus
variables, change `mapping.target`. To change waves, K or combinations, change
the model's `wave_ids`, `classes` or `roles`. Each change produces a fresh root
and a new manifest, not a claim of historical reproduction.

An executable synthetic example is available with:

```sh
Rscript assets/ch7_source_example_20261111.R fresh-demo-root
```

It creates a synthetic CSV and full JSON config using
`ch7_native_fixture_20261111.R`, then prepares five model inputs with this entry.
The config contains no research data and can be edited to explore combinations.
Example execution is compile-only and does not establish native acceptance.

## Fresh Step-1 to Step-3

Use `mode="step3_from_output"`, a `step1` record, and explicit Step-3 `models`.
The `step1` fields are `out`, `savedata`, `out_sha256`, `savedata_sha256`, `id`,
`nominal_map`, `latent`, and `classes`; optional `keep` declares extra savedata
projection columns. For example:

```r
step1 <- list(
  out = "step1/model.out", savedata = "step1/posterior.dat",
  out_sha256 = digest::digest("step1/model.out", algo = "sha256", file = TRUE),
  savedata_sha256 = digest::digest("step1/posterior.dat", algo = "sha256", file = TRUE),
  id = "SID", nominal_map = c(n1 = "MLCC1", n2 = "MLCC2"),
  latent = c("c1", "c2"), classes = 2L)
config <- list(schema_version = 1L, mode = "step3_from_output", step1 = step1,
  models = list(list(id = "step3", family = "lta", classes = 2L,
    invariant = TRUE, transitions = TRUE, starts = "0", estimator = "MLR", processors = 1L)))
```

`nominal_map` names the new nominal indicators and maps them to the savedata
most-likely class columns in the corresponding Step-1 CLASSES order. It must not
use the joint pattern column. The entry calls `ch7_step3_from_step1()` to extract
the actual printed classification logits, preserve their reference category and
direction, and project the current savedata by ID. It never substitutes an old
CPROB file or manually supplied error matrix. Each compiled consumer gets a
`PASS_COMPILED_LINEAGE` receipt; this is not a claim that its Step-3 model was
estimated. The original Step-1/Step-3 native receipts and warnings remain needed.

The return object's `chains` contains private in-memory lineage and parsed
source information for project validation. Only the sanitized lineage receipt
is written into the root manifest. Do not publish raw data, model outputs or
private chain objects from real runs.

## Archived historical replay

Use `mode="historical_replay"` and model records containing only `id`, `inp`,
`inp_sha256`, `dat`, and `dat_sha256`. The paired original input and data must
already have been audited and frozen. This mode copies DAT bytes unchanged and
replaces only the DATA FILE and SAVEDATA FILE values with `source.dat` and
`posterior.dat`. It preserves all other input bytes, including CRLF, comments,
starts, seeds, nominal logits, processor count and historical diagnostics.

The parser rejects duplicate FILE declarations, imputation lists, external
include statements and additional output-file targets. It does not rerun source
cleaning or apply new-source binary checks to an archived Step-3 DAT. No saved
outputs are copied. The private run must compare fresh OUT values against the
original baseline at its printing precision before claiming reproduction.

If an archived processor setting exceeds the runtime grant, resolve that
conflict explicitly before estimation; this mode will not silently change it.
Likewise, source-path identity, new estimation, numeric replay agreement and
manuscript acceptance are different claims.

## Verification and remaining scope

`test_ch7_source_entry_20261111.R` verifies source values and hashes, renamed and
reordered columns, target renaming, 2/3/4 waves, K/indicator combinations,
CSV/DTA, explicit missing values, invalid ID/type/mapping rejection, exact
non-path replay bytes, and Step-1-derived Step-3 compilation. The test traces
MplusAutomation's engine functions to fail immediately if invoked. All its data
and output-shaped fixtures are synthetic; successful fixture parsing is not
licensed native engine evidence.

Runtime manifests bind the actual source hash, mapping, wave order, prepared
input/data hashes, dependency code hashes and package versions. They contain no
source absolute paths or person-level values. Input DAT and all real estimation
outputs remain private project artifacts. The native receipt, warning inventory,
new-entry versus W2 plot comparison and original-model fresh replay comparison
must be recorded independently by the calling workflow.
