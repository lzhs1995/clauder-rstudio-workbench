# Data-structure decisions

## Cross-sectional data

Use one row per independent unit. Overall and between-group p values may be
reported when their assumptions are reasonable.
If `input.id` is declared, missing IDs or repeated IDs are not an independent
cross-sectional sample and must be resolved explicitly before running.

## Panel or longitudinal data

First audit `input.id` and `input.time`. Declared keys must be non-missing and
each person-wave pair must be unique; wave splitting cannot make duplicated
person-wave records independent. The runner must block these records, not
silently deduplicate or aggregate them. If IDs repeat across distinct waves,
`panel_mode: "dual"` means:

- **Primary:** if grouping is not time, generate one table per wave; if time is
  the grouping variable, show pooled time distributions but suppress pooled
  p/trend values because rows are repeated measures.
- **Compatibility pooled:** reproduce the legacy pooled `compareGroups` table,
  retain requested p values, and add a warning that ordinary t/chi-square tests
  assume independent rows and are descriptive/compatibility evidence only.

For formal longitudinal inference, use an appropriate repeated-measures or
cluster-aware model outside this skill.
An explicitly requested `pooled_compatibility` view must carry the same
independence warning; it is not a safe inferential primary analysis.

With 1.1 `analysis.variants`, each named subset inherits the same group and
block contract. Dual mode then emits IDs in deterministic order:
`<variant>__primary_wave_<time>` followed by
`<variant>__compatibility_pooled`. Without explicit variants the historical
`primary_wave_<time>` and `compatibility_pooled` IDs remain unchanged. Every
declared group must remain observed in every resolved variant; filtering out a
declared group is a hard failure even when two other groups remain.
This check applies equally to automatic wave variants without an explicit
`analysis.variants` array. Colliding resolved IDs are also a hard failure.

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

## Migration from v0.6.0

v0.6.1 keeps spec formats 1.0 and 1.1 but intentionally tightens validation.
Previously accepted data may now stop before statistics are calculated:

- For a genuinely cross-sectional question, explicitly select the scientifically
  intended wave/sample upstream and verify one non-missing ID per observation.
  Do not take an arbitrary first row or remove `id` to bypass the check.
- For repeated observations of the same people, declare panel `id` and `time`
  and use `panel_mode: "dual"` for wave-specific primary tables plus labelled
  pooled compatibility output. Ordinary pooled p values are not longitudinal
  inference. An explicit `pooled_compatibility` request is now labelled as such.
- Missing IDs/times and duplicated person-wave pairs must be investigated in
  source data. This runner does not impute keys, deduplicate, or aggregate them.
- Every declared group must occur in every resolved subset/wave. Adjust the
  scientific grouping or specify a separate justified table contract when a
  subgroup has different populations; do not silently drop levels.

Regenerate affected artifacts in a new output directory and retain the old
evidence. Display formatting may be unchanged even when numeric-long exports
correctly lose auxiliary `Fact OR/HR` rows previously misreported as sample N.
