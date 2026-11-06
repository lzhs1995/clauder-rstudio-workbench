# APIM v2 Stata/CSV adapter

The schema-2 workflow accepts `data_mode = 'csv'` (the default), `'dta'`
(requires `haven`), or the existing hash-bound `'archived_dat'` route.
Use a prepared wide couple-wave file: the adapter does not merge spouses,
reshape panels, derive survey scales, impute missing values, or choose models.

`column_map` is an optional one-to-one named character vector whose names are
the canonical columns used throughout the config and whose values are source
columns. Unmapped columns keep their original names. Missing source names,
duplicate mappings, and collisions with unmapped names are errors. Filtering,
designs, control lists, `row_id`, and `cluster` use the resulting canonical
names. Variable order in the source is immaterial.

```r
# 先复制模板并逐项核对真实来源；占位名不会被自动猜测。
mapping <- read.csv('reviewed_variable_map_v2.csv', colClasses='character')
stopifnot(!any(grepl('^REPLACE_', mapping$source)))
cfg$column_map <- setNames(mapping$source, mapping$canonical)
cfg$data_mode <- 'dta'
# 只声明已从本次问卷/数据字典确认的缺失编码；不能把所有负值都当缺失。
cfg$missing_codes <- list(x1=c(-9, -8), x2=c(-9, -8))
plan_apim_workflow(cfg)
run_apim_workflow(cfg, stages=c('check', 'prepare', 'compile'))
```

Start with [the CFPS template](../assets/cfps_variable_map_v2.csv) or
[the CHARLS template](../assets/charls_variable_map_v2.csv). These deliberately
contain `REPLACE_` source names: neither survey has one universal wide-column
schema. Set member order from a verified spouse roster, document the wave,
units, score direction, and the missing codes, and select your intended
APIM/APIMeM designs. Successful transport between surveys is not evidence
that their measurements or target populations are equivalent.

Stata value labels are removed without converting codes to factor levels.
Stata ordinary/tagged missings become R `NA`; the receipt counts tagged
missings separately. Character IDs retain leading zeros and long digit
strings. Numeric IDs must be finite integers smaller than 2^53 in absolute
value; IDs already rounded in their source format cannot be recovered.
Numeric model columns retain double round-trip precision. Date/time columns
used as IDs or model variables require explicit upstream preprocessing.

`missing` retains the existing global CSV contract. Optional `missing_codes`
names canonical columns and replaces only the declared codes. Identity
columns cannot be recoded with this option. Codes declared as numbers are
compared numerically; character codes on CSV inputs are matched exactly.
Do not infer missingness from the sign of a value. The existing per-model
complete-case rule still decides which rows enter each model.

CSV and DTA runs record aggregate column-level recoding counts, reader version, source
SHA256, and adapter SHA256 in `audit/data_adapter.json`; archived DAT runs keep
their hash-bound identity checks and do not write this receipt. No respondent IDs or
values are included in that receipt. Source bytes remain in the existing
read-only snapshot; missingness and rename settings are part of the scientific
cache contract. Archived DAT rejects these options to retain its strict
identity boundary. Existing cached preparations from older code need a fresh
run directory; they are not silently reused with the new adapter.

For CSV, `source_missing` counts missing values immediately after `read.csv`,
including the existing global `missing` codes. `global_codes_replaced` is zero
because the adapter does not apply those codes again. For DTA it records the
additional global-code conversions after the haven reader. Both formats record
new per-column conversions in `column_codes_replaced`.

Run `test_apim_v2_data_adapter()` from
`scripts/test_apim_v2_data_adapter.R` in an isolated directory. It creates
small synthetic CSV/DTA fixtures and checks mapping, missingness, labels,
IDs, numerical preparation and APIM/APIMeM compilation without Mplus.
