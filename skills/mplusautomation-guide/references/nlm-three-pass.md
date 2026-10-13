# NLM three-pass manuscript gate

The NLM workflow is a review layer after model and table provenance are
stable. It must not be used to invent estimates, silently rewrite historical
results or replace a source check.

## Pass 1: structure and numerical binding

- Supply the manuscript, appendix, table/figure registers and the acceptance
  report as the source set.
- Check chapter/section order, table and figure numbering, cross-references,
  displayed values, sample sizes, signs, decimal places and footnotes.
- Every finding becomes a review item with a document locator and a linked
  `model_id`/`table_id` or an explicit editorial-only label.

## Pass 2: method, interpretation and references

- Supply the methods text, model syntax summaries, validation reports and
  Zotero reference export.
- Check estimator names, time basis, measurement scale, missing-data rules,
  convergence language, causal wording and the distinction between association,
  transition and causality.
- Verify citations and DOI metadata through Zotero or the documented source;
  unresolved references remain open items.

## Pass 3: final format and hallucination audit

- Supply the rendered DOCX/PDF, final registers and the disposition log.
- Check headings, captions, tables, figures, appendix links, symbols, page
  references and consistency between manuscript and results.
- Search for unsupported claims, invented numbers, unlinked table cells,
  accidental replacement of historical-only results and stale filenames.
- Require a human-readable disposition for every NLM finding: accept, revise,
  reject as unsupported, or defer.

## Release rule

The final manuscript package is releasable only when all three pass reports,
source hashes, document hashes and unresolved-item dispositions are stored next
to the acceptance report. NLM completion does not change a model's statistical
status; it only confirms that the written presentation is traceable and
internally consistent.

## Windows evidence rule

Keep each PDF pair and its exact source IDs in an isolated run directory. A
valid `nlm 0.13+` response must have `returncode=0`, non-empty
`sources_used` matching both PDF IDs, and a saved raw response. The Windows
audit for the PP-LGCM revision is recorded in
`reports/nlm_pdf_three_pass_audit_20261004/nlm_pdf_three_pass_audit_v1.{json,md}`.
The audit shows why an A5 scan result for `revision_v4` cannot be promoted to
the final manuscript after a later table or wording change: freeze the final
PDF pair first, then repeat the three passes against those hashes.
