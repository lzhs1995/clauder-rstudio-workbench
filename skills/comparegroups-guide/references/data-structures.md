# Data-structure decisions

## Cross-sectional data

Use one row per independent unit. Overall and between-group p values may be
reported when their assumptions are reasonable.

## Panel or longitudinal data

First audit `input.id` and `input.time`. If IDs repeat, `panel_mode: "dual"`
means:

- **Primary:** if grouping is not time, generate one table per wave; if time is
  the grouping variable, show pooled time distributions but suppress pooled
  p/trend values because rows are repeated measures.
- **Compatibility pooled:** reproduce the legacy pooled `compareGroups` table,
  retain requested p values, and add a warning that ordinary t/chi-square tests
  assume independent rows and are descriptive/compatibility evidence only.

For formal longitudinal inference, use an appropriate repeated-measures or
cluster-aware model outside this skill.

With 1.1 `analysis.variants`, each named subset inherits the same group and
block contract. Dual mode then emits IDs in deterministic order:
`<variant>__primary_wave_<time>` followed by
`<variant>__compatibility_pooled`. Without explicit variants the historical
`primary_wave_<time>` and `compatibility_pooled` IDs remain unchanged. Every
declared group must remain observed in every resolved variant; filtering out a
declared group is a hard failure even when two other groups remain.

## Repeated cross-sections

When each wave samples different people, specify `time` but omit `id`, or use an
ID whose audit proves no repetition. Year grouping and trend tests are then
allowed subject to ordinary assumptions.

## Attrition and missing-sample tables

Create the retained/deleted indicator before deleting observations. In spec
1.1, `analysis.attrition` does this from `input.id`, `input.time`, declared
`baseline_values`, and declared `followup_values`; it then retains exactly one
baseline row per ID. Missing IDs, duplicate baseline rows, overlapping wave
sets, overwritten status columns, empty groups, and subset-induced group
collapse are hard failures. Do not infer attrition from a dataset that already
discarded the missing follow-up cases.

## Batch manifests

Use ordered `jobs` when sex, lifecycle, year, or sample-selection tables need
different grouping variables or independent specs. Each job has its own safe
relative output directory. The batch stops after the first failure, preserves
completed evidence, and never resubmits an async ClaudeR job.
