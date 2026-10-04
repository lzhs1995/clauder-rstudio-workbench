# PP-LGCM source and Word reconciliation lessons

Verified during the 2026-10-01 continuation. The guide remains draft; these
lessons do not imply manuscript release or complete numerical reproduction.

## Source identity before comparison

Bind each manuscript result to its output-specific producer block. A nearby
export statement is not necessarily the producer. Preserve the reader script
separately: a relative-scale script can read an absolute-scale producer.
Resolve duplicate output basenames with frozen invocation IDs and actual
VARIABLE/MODEL/data contracts, not the nearest filename match.

A matching receipt hash establishes file identity. It does not establish input
semantics or data equality. Compare embedded input, runtime input, reused input
and declared used values by participant key. Compare historical tables
separately. Currently adjacent historical data sidecars can document observed
differences but cannot prove the exact historical execution bytes or explain
the resulting estimate differences causally.

## Word objects and print-time behavior

`python-docx` paragraph/run text can omit cached results inside `w:fldSimple`.
An apparent `Table :` can actually be a valid `Table 1:` caption. Inspect raw
XML before deleting it. Count `fldSimple` separately from `fldChar`; preserving
only the latter does not establish field preservation.

Replace verified spans across `w:t` nodes rather than separately within runs.
Assert target occurrence counts and the complete resulting paragraph text.
Preserve styles, drawings, bookmarks, cells, fields, section properties and ZIP
parts outside the intentional edit. Footnotes live in `word/footnotes.xml`;
body-only searches do not cover them.

When isolated review copies need fixed caption numbering, explicitly lock the
relevant SEQ fields and disable print-time field/link updates for the owned
Word instance. Preserve the original documents. Export one file at a time with
an independent receipt: resolved DOCX path, before/after hash, owned Word PID,
PDF hash, nonempty parsed text and page count. Close only that owned instance.
Visually inspect representative dense tables and field captions; extracted PDF
text and NLM OCR artifacts are not proof of visible missing characters.

Lock both simple fields and complex `fldChar` begin/separate/end fields.
`UpdateFieldsAtPrint=False` alone did not prevent two complex SEQ fields with
blank cached results from reappearing as extra numbers after manually assigned
appendix captions. Track each complex field's instruction and lock its begin
node; do not indiscriminately lock unrelated citation/reference fields.

## Descriptive tables and MI interpretation

A manuscript may combine `compareGroups` descriptive and missingness exports.
Bind each column to the corresponding export and each row to the explicit R
formula/label order. Existing-export equality must not be called a fresh export.
Verify transcription errors using both source tables and raw-data counts where
available. Record exact cell coordinates and preserve original values.

Ten stacked imputations of 3,274 people contain 32,740 rows, not that many
independent participants. Stacked descriptive statistics, Rubin-pooled
inference and tests comparing an observed group with its own imputed versions
are different objects. An arithmetic mean of imputation-specific LRT p-values
is not a valid pooled LRT. A p-value of 1, especially from an invalid negative
difference statistic, does not prove adding an interaction worsens fit or that
an effect is absent. Qualify manuscript conclusions while the statistical
contract remains unresolved; do not silently substitute a different estimate.

## NLM evidence

Source-bound output can still be truncated. A zero CLI exit code and valid
citations do not rescue a missing A5 trailer. Preserve the raw response as
diagnostic, request concise location/issue records in a new fingerprint, and
do not manufacture a no-new count. Changed PDFs require fresh uploads and a
new valid review sequence. Old A5 evidence validates only its recorded hashes.

A reviewer may repeat a prior issue even while its current-source citation
shows the correction. Compare `answer` with each `references[].cited_text` and
the local rendered PDF; record the contradiction as reviewer carryover. A5
closes an advisory scanning loop, not statistical acceptance. Never alter a
correct current caption or coefficient to satisfy a repeated false report.
