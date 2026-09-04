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

## Repeated cross-sections

When each wave samples different people, specify `time` but omit `id`, or use an
ID whose audit proves no repetition. Year grouping and trend tests are then
allowed subject to ordinary assumptions.

## Attrition and missing-sample tables

Create the retained/deleted indicator before deleting observations. Select the
baseline wave and retain one row per ID for the formal comparison. Do not infer
attrition from a dataset that already discarded the missing follow-up cases.
