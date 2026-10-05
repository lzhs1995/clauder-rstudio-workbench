# Manuscript missingness contracts: `missingTable()` versus Mplus

When reconciling a descriptive table with a longitudinal Mplus model, do not
compare every number labelled “missing” as if it were the same estimand. In the
CFPS Table 4.1.1 audit, the historical R code used
`compareGroups(...); missingTable(...)` to report the number of missing values
for each variable in the 3,274-person analytic cohort. The historical export
therefore produced 935, 115, and 380 for three derived closeness variables.

The corresponding Mplus step-1 outputs used `MISSING=.` and a model-specific
`USEVARIABLES` set. Their warnings reported cases missing on **all** model
variables (929, 8, and 279), while `Number of observations` was respectively
2,345, 3,266, and 2,995. Each pair sums to the same 3,274-person input cohort.
Rows with partial missingness remain available under the model's MLR/FIML
missing-data contract, so an Mplus all-variable warning is not a replacement
for a variable-level missing count.

The manuscript flowchart may report a third quantity: branch-specific sample
exclusions such as `Exclude n=929`, `n=6`, or `n=279`. Preserve the labels and
keep all three contracts in the provenance record:

| Contract | Evidence | Meaning |
|---|---|---|
| Variable-level missingness | R `missingTable()` export | Missing values for one named variable in the analytic cohort |
| Mplus all-`USEVARIABLES` missingness | `.out` warning plus `Number of observations` | Rows excluded because every model variable is missing |
| Flowchart exclusion | Manuscript sample-flow text/figure | Branch-specific screening or construction loss |

For a reconciliation receipt, store the R line range, historical export hash,
Mplus output hash, baseline cohort size, both counts, and the arithmetic check
`observations + all_variable_missing = baseline_N`. Mark the component
`RESOLVED_DISTINCT_MISSINGNESS_CONTRACTS` only when all three contracts are
identified and the manuscript's displayed number matches its historical
producer. Do not silently replace the table value with an Mplus warning count,
rerun Mplus, or edit the manuscript during a provenance audit.
