# Contract and compareGroups mapping

The runner accepts both `schemas/table-spec.schema.json` (`spec_version:
"1.0"`) and `schemas/table-spec-1.1.schema.json` (`spec_version: "1.1"`).
Version 1.0 behavior is retained. Version 1.1 adds optional normalization so a
large family of tables can share defaults without hiding scientific choices.

| Contract value | `compareGroups` method |
|---|---:|
| `normal` | 1 |
| `nonnormal` | 2 |
| `categorical` | 3 |

Useful optional variable fields are `levels`, `reference`, `label`, and
`include_missing`. Numeric categorical variables without Stata value labels
must supply `levels`, for example:

```json
{
  "name": "sex",
  "type": "categorical",
  "method": "categorical",
  "levels": [
    {"value": 0, "label": "Male"},
    {"value": 1, "label": "Female"}
  ],
  "reference": "Male"
}
```

In 1.1, every variable still declares `name`, `type`, and `method`. `digits`
and `include_missing` may inherit from:

```json
{
  "defaults": {
    "continuous_digits": 3,
    "categorical_digits": 2,
    "p_digits": 3,
    "include_missing": false
  }
}
```

Variable values override defaults. `display.p_digits` overrides
`defaults.p_digits`. Metadata records both resolved values and their source.

`analysis.group_levels` and `analysis.group_reference` apply the same explicit
code/label/reference discipline to the grouping variable. Unknown codes,
duplicate mappings, missing references, and fewer than two non-empty groups
block execution. Priority is: explicit spec mapping/label, Stata value or
variable label, then an already meaningful factor/character value. Numeric
unlabelled categorical variables and grouping variables require explicit
levels.

`display.show_all`, `show_n`, `show_p_overall`, `show_p_multiple`, and
`show_p_trend` map to `createTable()`. `display.hide_no` maps to `hide.no` and
accepts one string or a list of exact strings. The runner always retains each block's
original `compareGroups` and `createTable` objects so numeric extraction does
not depend on a lossy combined display object.

`analysis.subset` is an optional R expression evaluated only against columns in
the imported data. It is recorded verbatim in metadata; use a prepared input
file when the selection logic is complex.

Ordered 1.1 `analysis.variants` add named subset expressions under the same
group. A different group requires a separate spec in
`schemas/batch-manifest.schema.json`. Resolved IDs retain array order. They are
stored in the combined evidence rows and also become deterministic
`<stem>__<resolved-variant-id>` prefixes for independent DOCX, display CSV,
numeric-long CSV, RDS, and metadata files.

Automatic `analysis.attrition` uses the declared ID/time, baseline values, and
follow-up values before baseline selection. Every non-missing ID in the input
must have exactly one baseline row; follow-up-only IDs and duplicate baselines
are blocked. The runner never overwrites an existing status column.

`display.docx` controls font family, point size, orientation, repeated headers,
title, footnote, and optional per-column widths. These controls never change
the required top/header-bottom/final-bottom border structure or permit vertical
grid lines.

All three core formats are always emitted because they form one validation
contract. `outputs.formats` documents delivery preferences; it does not disable
the evidence artifacts needed for independent validation.
`display.compatibility_export2word: true` additionally emits the official
`export2word()` result for a single-variant run whose blocks each use one
missing-value policy; complex panel/combined tables intentionally use only the
stable `officer`/`flextable` route.
