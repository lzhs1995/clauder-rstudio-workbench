# Validation standard

A successful invocation must retain:

- the input SHA-256 and package/session versions;
- one display CSV and one unformatted numeric-long CSV;
- all per-block `compareGroups` and `createTable` objects in RDS;
- a DOCX that can be opened as OOXML;
- a validation CSV in which every check is `TRUE`;
- a manifest containing size and SHA-256 for every non-manifest output.

The DOCX must use a true three-line layout: top border, header-bottom border,
and final bottom border, with no vertical grid. Do not compare DOCX hashes
across reruns because Office metadata can change. Compare group sizes, raw
statistics, p values/test methods, ordering, labels, digits, and OOXML borders.
In the numeric-long CSV, `n` is the count for a categorical level, whereas
`n_available` is the non-missing sample size reported for the variable by
`createTable`. Keep these fields separate when reconciling exported values.

Panel dual mode must additionally prove that the primary output suppressed an
invalid pooled p value or split by wave, and that the compatibility output
contains an explicit independence warning.
