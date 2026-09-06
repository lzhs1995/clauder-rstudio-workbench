# Validation standard

A successful invocation must retain:

- the input SHA-256 and package/session versions;
- one display CSV and one unformatted numeric-long CSV;
- all per-block `compareGroups` and `createTable` objects in RDS;
- a DOCX that can be opened as OOXML;
- a validation CSV containing the complete required check set, each exactly
  once and `TRUE`, with compatible `check`,
  `passed`, and `details` plus structured `expected`, `actual`, and `detail`;
- a manifest containing size and SHA-256 for every non-manifest output;
- `SHA256SUMS.txt`, including the manifest itself.

The independent validator rejects unsafe or incomplete manifest/SHA entry
sets, verifies each manifest byte count against the actual file size, reopens
the RDS and DOCX, and reconciles spec/skill versions, variant IDs, row counts,
and group counts between metadata, RDS, display CSV, and numeric-long CSV.
It also reconstructs display and numeric rows from the retained per-block RDS
objects and compares their full content, including stable variable identities,
statistic/group keys, and raw values. An edited CSV must fail even if its row
count is unchanged and its manifest/SHA hashes have been recomputed. Removing
required validation rows must fail even when all remaining rows say `TRUE`.

Each DOCX table must use a true three-line layout: top border, header-bottom
border, and final bottom border, with no vertical or extra internal rules. Do
not compare DOCX hashes across reruns because Office metadata can change.
Compare group sizes, raw statistics, p values/test methods, ordering, labels,
digits, and OOXML borders.
In the numeric-long CSV, `n` is the count for a categorical level, whereas
`n_available` is the non-missing sample size reported for the variable by
`createTable`. Keep these fields separate when reconciling exported values.
Only actual total/group columns may produce `n_available`; auxiliary columns
such as `Fact OR/HR`, `method`, or `select` are never group sample counts.

Panel dual mode must additionally prove that the primary output suppressed an
invalid pooled p value or split by wave, and that the compatibility output
contains an explicit independence warning.
All resolved variants must also preserve declared groups and unique IDs, and
declared analysis-unit keys must pass missing/duplicate checks before fitting.

Batch validation additionally proves declared order, unique output ownership,
all child decisions, recursive manifest membership and byte sizes, and
top-level SHA-256. A failed child leaves `batch_summary.csv` and completed child
evidence intact.

## Evidence boundaries

Semantic reconciliation detects export inconsistency; it does not constitute
an independent statistical engine, validate the research design, or provide
cryptographic protection against coordinated alteration of the RDS and all
other evidence. Package/version and source provenance still matter. A true
three-line OOXML structure also does not certify Chinese font rendering,
column widths, pagination or publication readiness: inspect the rendered DOCX.
