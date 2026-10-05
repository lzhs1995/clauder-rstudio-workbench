# CFPS full DOCX table/figure provenance

The PP-LGCM manuscript has two independent Word sources: the正文 DOCX and
`Appendix.docx`. A reproducibility run is incomplete until every Word table and
every embedded media object is represented in a manifest.

## Required inventory

Parse `word/document.xml` and `word/media/*` from both DOCX files. Preserve the
Word table index, row/column dimensions, caption context, embedded-media
SHA-256, and paragraph index. In the CFPS draft the inventory is 15正文 tables
plus 100附录 tables and 36正文 plus 12附录 media objects. Do not infer the
count from captions alone: repeated “Table 1” fields and unlabeled Appendix
media are common.

Join the inventory to the existing cell contract and R/Mplus crosswalk. Each
table record should retain:

- the producer R script and exact code-line range;
- historical `.docx`/`.out` source paths and hashes;
- isolated `.inp`/`.out` paths and hashes when a verified rerun exists;
- expected Word dimensions, contract-record count, pair-agreement count, and
  disposition counts;
- a status that separates technical evidence from scientific acceptance.

For tables with identical output basenames in multiple scripts, use the
manuscript's standardization contract and the R assembly block to select the
producer. In this project,正文 Table 4.2.1/4.2.2 are `relative.R` blocks
3055–3561 and 6478–6985. The `absolutive.R` candidate with the same basename
is retained as an alternative historical asset, not silently promoted to the
producer.

Derived tables need the `mplusObject`/`mplusModeler` lines and XWITH/constraint
contract. A numerical match alone does not settle a swapped `i_mod_s` versus
`s_mod_i` label. Keep the semantic/LRT review state visible in the manifest.

## Figure rule

Byte equality between a DOCX embedded image and a historical PNG/SVG is not
required: Word commonly repackages or converts the media. Use the embedded
SHA-256 as the immutable manuscript identity, then match the SVG/PNG axis
labels, the R plotting constructor, and the external export path separately.
Record `external_artifact_unavailable` when the DOCX is the only surviving
copy. Figure 3.1 is a special case: the surviving source is an external
SVG/PPT assembly, while `relative.R` supplies the sample-selection and
PP-LGCM model semantics (`7400–7458, 7506–7544` and `10763–10799,
11522–11529`). Verify the source SVG against the embedded SVG text sequence
and record
`SOURCE_FILE_CONFIRMED_SEMANTIC_SOURCE_CONFIRMED_GRAPHIC_GENERATOR_RECEIPT_NOT_REQUIRED_FOR_PROVENANCE`.
The absence of a one-click SVG export receipt remains visible as a limitation,
but it does not reopen the provenance gate once the source SVG, embedded media,
and R semantic lines agree. A neighboring GMM or LTA script is not evidence
for a producer.

## Acceptance and validation

Technical source mapping and scientific adoption are different gates. A table
can have a complete R/Mplus/Word lineage while still requiring MI, LRT,
rounding, version, or author semantic review. Validate the totals, allowed
producer scripts, embedded hashes, referenced asset existence, and unchanged
source-script/DOCX hashes before reporting completion. The isolated CFPS
implementation is:

```text
work/build_cfps_full_docx_provenance_20261005.py
work/validate_cfps_full_docx_provenance_20261005.py
reports/cfps_full_docx_provenance_20261005/manifest.json
```

The validator must report `new_mplus_submissions=0` when it is only reading
historical and already verified outputs. This prevents a provenance audit from
re-running expensive models or contaminating the source result directory.
