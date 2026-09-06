# Personal table conventions

## Row organization

Keep variables in the requested scientific order and separate them with visible
section rows. The standard labels are:

1. 被解释变量
2. 解释变量
3. 中介/调节变量
4. 个体特征
5. 父母特征
6. 家庭特征
7. 混杂因素

Do not alphabetize variables or silently move them between blocks.

## Statistics and display

| Variable type | Method | Display | Default digits |
|---|---|---|---:|
| continuous, approximately normal | `normal` | mean (SD) | 3 |
| continuous, skewed | `nonnormal` | median [Q1, Q3] | 3 |
| categorical | `categorical` | n (%) | count 0, percent 2 |

Rename `[ALL]` to `全样本` and `p.overall` to `p-value`. Show the total
column and available N by default. Multiple-comparison and trend p values are
opt-in. Always preserve the raw numeric values separately from formatted text.
`display.hide_no` affects the presentation layer only: the numeric-long audit
export retains raw category statistics, including levels hidden in the DOCX.
Use `display.hide_no` when the legacy table intentionally suppresses a
negative category such as `no`; do not infer that choice from the data.

## Coding style

- Build named lists/specifications instead of repeated `get()`/`assign()`.
- Never use `c` as a loop variable.
- Reuse one audited base specification to derive lifecycle, sex, year, and
  sample-selection variants. Use ordered 1.1 `analysis.variants` when the group
  is unchanged, and a batch manifest when the grouping variable changes.
- Prefer Stata variable labels. Require an explicit decision for value-label
  ordering and reference level.
- Use `officer` + `flextable` for complex Word output. `export2word()` remains
  a compatibility option, not the only export path.
