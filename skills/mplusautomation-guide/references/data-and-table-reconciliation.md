# Trace Data and Manuscript Differences

Use three separately identified evidence sets: the manuscript, historical
INP/DAT/OUT files that may have produced it, and newly generated files. A current
script successfully rerunning does not prove it is the manuscript's version.
Keep original hashes and report the scope of each comparison.

## Data Before Estimates

Compare the current source CSV/DTA with its newly generated DAT, then compare
historical and current DAT. Record explicit NAMES order, row count, unique case
key, missing-value encoding, added/removed columns and numeric differences.
Match on a stable key; equal row counts do not prove aligned cases. Duplicate,
missing or reordered keys require explicit alignment in an isolated copy.

The helper `scripts/compare_numeric_data.py` exposes `compare_numeric_data()`.
Omit a schema to read a CSV header; pass an explicit column-name sequence to
read whitespace numeric data. It does not parse Mplus ranges or general input
syntax. Pass missing tokens from the actual input contract on each side:

```python
result = compare_numeric_data(
    source_csv, generated_dat, key="case_id", right_names=names_from_manifest,
    left_missing=("", "9999", "9999.00"), right_missing=(".",), atol="0.00000001"
)
```

The tolerance above is an example, not a universal statistical criterion.
Choose it before inspecting the comparison and retain it in evidence. The
helper also reports maximum absolute differences and missingness changes.
Hashes are checked before and after reading. It reports aggregate column
differences without participant identifiers; it does not modify input files.
Use a domain-specific comparison for nonnumeric or fixed-width records.

A Windows PP-LGCM case had identical source CSV and generated DAT values at
the recorded tolerance, but historical DAT differed in several sibling-rank
variables and derived standardizations. The supplied R scripts loaded those
columns from CSV. That establishes an input-version difference; it does not
prove that the current R run generated a nondeterministic ordering. Trace the
upstream construction before attributing changes to tie-breaking, seeds, R,
Mplus or the OS. A proposed tie-breaking change creates a new analysis version.

For `TYPE=IMPUTATION`, hash and compare every resolved member of the list in
the order actually consumed. Identical list-file bytes can refer to different
member bytes in different directories. Record the used-column schema and
unique case alignment for each member; a missing, repeated or unaligned member
leaves the comparison incomplete. Revalidate cached input hashes before reuse.

Trace an imputation discrepancy through the actual reader binding to its
producer's `SAVEDATA INFORMATION` column order, then to the downstream model's
NAMES/USEVARIABLES. Separate variables named in `IMPUTE` from auxiliary growth
indicators carried through unchanged. Verify any re-standardization, joins and
recodes between these stages. A discrepancy confined to carried-through
indicators is not automatically imputation randomness. Equal MODEL/ANALYSIS
syntax plus changed used inputs establishes a data-version difference; it does
not quantify how much each change contributed to an estimated coefficient.

## Table Identity

Use a mapping with at least:

| Field | Meaning |
| --- | --- |
| manuscript hash and table/row/column | The exact displayed target |
| script hash, invocation ID, scale and trajectory | The generating specification |
| INP hash, data hashes, imputation index/member hashes | Actual estimation inputs |
| OUT hash and validation state | Estimate source and diagnostic limitations |
| parameter section, relationship, outcome, predictor | Exact extracted quantity |
| expected text, raw numeric value, tolerance, verdict | Comparison evidence |

Resolve cross-script readers explicitly. For example, a relative-scale table
may read a mean-process output produced only by an absolute-scale script. A
matching basename in the relative directory cannot establish the correct
producer. The same output can appear in multiple tables: count unique model
identities separately from table entries and comparison components.

## Interpret the Comparison

Record each numeric component independently (estimate, SE, fit, R-squared),
then review significance symbols, structural blanks, labels and notes. Extract
pooled multiple-imputation summaries from the correct section; an extra
missing-information column must not shift estimate/SE positions. An absent
fit statistic is unresolved, never zero and never a borrowed neighboring fit.

Mplus may print `*********` in a diagnostic column, including a z statistic
for a fixed parameter with zero SE. That row is still a parameter row; it must
not become the next section heading. In a PP-LGCM audit, an older parser's
mistake propagated an entire numeric row into later parameters' group labels.
Verify a cached mapping against the original output hash and exact source
line, then record a separate corrected mapping. Retain duplicate parameter
identities as ambiguous, and stop before standardized or technical sections.
Test the parser against real historical parameter rows as well as synthetic
multiple-imputation, fixed-parameter and repeated-name cases.

Compare only after manuscript table text still matches the mapped reference.
Resolve the script, invocation, parameter section and parameter name before
looking for numerical agreement. If several distinct input identities could
have produced a cell, report the ambiguity; do not choose the estimate that
happens to match. Keep numeric verdicts and saved-data/estimation diagnostics
in separate columns, including when a queue's `completed` record still carries
a warning or a failed saved-data contract.

Apply the same distinctions to table-readiness summaries. A basename is only
a candidate search key: distinct producers must remain ambiguous unless an
audited content identity establishes equivalence. Do not select whichever
same-name task succeeded. Keep deferred, blocked, failed, waiting, unknown and
not-prepared counts separate, and require both queue completion and validated
estimation before counting an estimate as available. Report saved-data limits
separately. Counts across tables are dependency references, not unique models.
If a live monitor still holds an older reporting function, write the corrected
schema to a versioned evidence file so its old loop cannot overwrite the new
semantics; changing a source file does not hot-reload an imported module.

For repeated rounded coefficient/SE pairs, build explicit cell identities from
the source script's reader bindings, table coordinates and parameter labels,
then validate the historical numbers. In the PP-LGCM core tables, 85 cells
verified this way resolved 24 numeric-match ambiguities. Pin manuscript,
script and historical output hashes; reject changed cells or identities absent
from the independently parsed historical candidates. Keep producer ambiguity
separate. An `S5 ON` equation may contain both the exposure intercept and `I5`
as a baseline outcome control, so an `I` prefix alone does not identify the
table's exposure path. Resolve the exposure factor from the generating model
and table construction before comparing its coefficient.

Audit the final formatting assignment as well as the extraction statement. In
one verified case, a script correctly created the fifth model's fit-text object
but inserted the fourth model's object into the fifth column. Three manuscript
fit values exactly matched that neighbor, while the fifth model's historical
and current outputs lacked those statistics. Preserve the faithful reproduction
and record this as a presentation defect; a separately corrected export must
use unavailable/NA, not substitute another model's fit. Equal-looking columns
are a prompt to inspect ownership, not proof of an error by themselves.

Retain warnings and failed-imputation counts even when rounded estimates
match. Equal AIC/BIC changes can be a diagnostic clue, but cannot prove that
data and model specifications are identical. Compare the inputs themselves.

Keep four verdicts distinct: numerically matched, numerically different,
unresolved extraction/mapping, and statistically inadmissible or under review.
A partial table audit must list omitted tables, symbols and validity checks.
The guide and reproduction stay draft until the requested inventory has an
explicit disposition for every model and manuscript component.
