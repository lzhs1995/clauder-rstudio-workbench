# Contract and compareGroups mapping

The public schema is `schemas/table-spec.schema.json` (`spec_version: "1.0"`).

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

`display.show_all`, `show_n`, `show_p_overall`, `show_p_multiple`, and
`show_p_trend` map to `createTable()`. The runner always retains each block's
original `compareGroups` and `createTable` objects so numeric extraction does
not depend on a lossy combined display object.

`analysis.subset` is an optional R expression evaluated only against columns in
the imported data. It is recorded verbatim in metadata; use a prepared input
file when the selection logic is complex.

All three core formats are always emitted because they form one validation
contract. `outputs.formats` documents the caller's requested deliverables.
`display.compatibility_export2word: true` additionally emits the official
`export2word()` result for a single-variant run whose blocks each use one
missing-value policy; complex panel/combined tables intentionally use only the
stable `officer`/`flextable` route.
