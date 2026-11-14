# Chapter 7 model-object figure adapters

`scripts/ch7_figures_20261111.R` consumes a MplusAutomation `readModels()`
object and an explicit mapping. Its data functions return ordinary long tables;
its plot functions return ggplot objects. They do not estimate models, install
packages, read research files, save figures or choose K.

## Explicit mapping

`mapping` is a list with a logical `source_id` and these data frames:

| Field | Required columns | Meaning |
|---|---|---|
| `variables` | `variable,label` | Latent-variable identities and display labels |
| `classes` | `variable,class,label,colour` | Complete class dictionary; character class IDs, explicit hex colours |
| `profiles` | `variable,param,statistic,category,label,panel` | Indicator mapping; `statistic` is `mean` or `probability`; response category is required for probability |
| `matrices` | `from_variable,to_variable,condition,kind,label` | Explicit printed table identities and conditional meanings |

Supply `latent_order` in the original Mplus `CLASSES` declaration order. It is
independent of display order and particularly matters when G precedes the wave
classes. If the model includes its parsed declaration, the adapter checks the
order against it. Joint class tables must be complete. Repeated profiles across
other joint classes collapse only when every selected value is identical;
varying values raise an error instead of being averaged.

`ch7_profile_data(model,mapping)` selects conditional means from
`parameters$unstandardized` and response probabilities from
`parameters$probability.scale`. Numeric-looking probability fields coerced to
character by a parser's trailing test section are converted only after explicit
indicator/category selection; nonnumeric fields are rejected. Thresholds are
never substituted for probabilities.

`ch7_proportion_data(model,mapping,method)` requires one of `modelEstimated`,
`posteriorProb` or `mostLikely`. It preserves the measure, counts, proportions and
reported sums. It does not normalize printed probabilities.

`ch7_matrix_data(model,mapping)` requires a complete explicit class-pair table.
Supported printed meanings are `kind="marginal_transition",condition="overall"`
and `kind="conditional_initial",condition="given <origin variable>"`. A G-to-first
wave table is an initial conditional distribution; it is not a mover transition.
The adapter does not derive G-specific transitions from marginal printed tables.

The renderers are `ch7_profile_plot`, `ch7_fixed_response_plot`,
`ch7_proportion_plot` and `ch7_matrix_plot`. The fixed-response heatmap is a
separate display from the continuous/categorical measurement profile.
Matrix facets use `from_variable`, `to_variable`, `condition` and `kind` as
their identities in input order. The `label` supplied in the mapping is only
a display title: different matrices may share it without merging panels.
Pass the identity and class columns returned by `ch7_matrix_data()` to the
renderer; duplicate identity/class cells, colliding display cells or conflicting
titles within one matrix are rejected before plotting.

## Enumeration, flow and quadratic curves

`ch7_enumeration_data(models,mapping)` takes a named list of model objects and a
mapping with `model_id,K,source_id,dataset_id,indicator_set`. Dataset and indicator
identities are caller-declared, sample sizes must match, and K must be unique.
The function extracts LL/BIC/N and makes no model-selection decision.
`ch7_enumeration_plot` shows LL/BIC against the declared K values.

`ch7_model_flow_data(model,mapping,wave_map,class_map,tolerance)` delegates to
the existing `ch7_transition_flow_data()` after selecting the explicit overall
transition tables and posterior counts. Source `ch7_transition_flow.R` first.
The existing [flow contract](chapter7-transition-flow.md) controls conservation,
units and rendering. The adapter does not add a mover-conditional reconstruction.

`ch7_model_quadratic_curve(model,mapping)` delegates to the existing
`ch7_quadratic_curve_data()`. Source `ch7_quadratic_curves.R` first. Its mapping
contains a `terms` frame with `role,paramHeader,param,LatentClass,covariance_index`
for the linear and quadratic terms, `covariance_source` selecting `paramCov` or
`paramCov.savedata` from TECH3, and a `curve` list containing the existing curve
arguments. TECH3 indices must be bound to TECH1 by the caller. Missing covariance,
ambiguous parameter keys and invalid covariance matrices fail explicitly. Full
cross covariance, log scale, reference category and interval rules are preserved;
see the [curve contract](chapter7-quadratic-curves.md).

## Validation boundary

`test_ch7_figures_20261111.R` uses synthetic model objects to test renaming,
2–4 waves, variable K including multi-digit class IDs, joint class ordering,
missing/ambiguous mappings, numeric parser text, condition selection and actual
plot layers. These object tests do not claim native estimation.

Same-input historical checks remain private: bind each original OUT, approved
class mapping, source CSV and old figure SHA; compare new long-table values and
labels before rendering. Different figure styling is not byte or pixel identity.
Original estimation warnings and failed attempts remain unchanged. Figure
readback, fresh source swapping, native estimation and manuscript adoption are
separate acceptance layers.
