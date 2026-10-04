# Cross-tool handoff contract

This guide coordinates several skills without treating any one tool as proof
of the whole analysis. Every handoff keeps the same `run_id`, `study`,
`model_id` or `table_id`, input hashes, output paths and transport evidence.
Private participant data, licenses, credentials and machine-specific secrets
stay outside the skill repository.

## Routing matrix

| Need | Route | Required evidence |
|---|---|---|
| R/MplusAutomation or Mplus | `clauder-rstudio-workbench` + this guide | session identity, transport, Mplus command/version, input/output hashes, validation and log |
| Descriptive or baseline table | `comparegroups-guide` | data audit, labelled-code mapping, numeric CSV/RDS, DOCX hash and validation |
| Stata data construction or cross-check | `stata-workbench-shared-session` and `stata_local` | visible session/port, do-file, log, saved data hash and output freshness |
| Word structure or table rendering | `officecli`/`docx` | source DOCX hash, generated DOCX hash, table/figure register and reopen check |
| References and DOI metadata | Zotero MCP | item keys, metadata query and unresolved-reference list; do not infer full text from metadata |
| PDF/source verification | PDF/NLM source workflow | source file hash, page/section locator and extraction method |
| Thesis review | `论文精炼助手`/`thesis-refiner` | NLM round IDs, prompts, source set, findings and disposition log |

`cmaverse-paired-mval` is invoked only for CMAverse paired-mval analyses. It
does not become a substitute for the PP-LGCM Mplus queue merely because both
workflows use RStudio fan-out.

## Windows compatibility rules

1. Use Windows-native R and Mplus for licensed estimation. WSL is the
   controller only; convert `/mnt/c/...` to `C:/...` at the R boundary.
2. Use the configured Python 3.14 path, explicit `USERPROFILE`, UTF-8 output,
   and the persistent local ClaudeR bridge. Do not use the Windows Store
   `python3.exe` redirector.
3. Use forward-slash paths inside R, short local staging paths for Office/PDF
   export, and exclusive per-invocation directories for Mplus output.
4. Keep the visible Stata Workbench session as the default. Do not run a hidden
   Stata MCP beside it unless the task explicitly requires isolation.
5. Treat Word COM/LibreOffice, Zotero local API, browser/NLM login and Mplus
   licensing as separate capability gates. A successful R call does not prove
   any of them. NLM authentication is proven by `nlm notebook list --json`,
   and the NotebookLM Clash rule is checked on the host that will call NLM;
   a Mac profile does not gate Windows R/Mplus work.
6. After changing ClaudeR, the MCP bridge, R package installation or client
   configuration, run the multi-session safety and native smoke checks before
   submitting a long job.

## Evidence handoff

The producer writes a manifest row before invoking a consumer. A consumer may
read only rows whose input hashes and terminal statuses are present. The
minimum row contains:

```text
run_id, study, model_id, table_id, producer, consumer,
input_hashes, output_paths, output_hashes, transport_class,
estimation_status, savedata_status, table_status, reviewer_status
```

`historical_only`, `deferred`, `blocked`, `review_pending` and `failed` remain
distinct from `completed`. A document can be structurally valid while its
numeric or scientific status remains unresolved.

## Recommended order

1. Lock data and model provenance.
2. Run or reuse Mplus estimates and validate them.
3. Generate descriptive or cross-check tables with compareGroups/Stata.
4. Bind estimates to manuscript cells by syntax and source identity.
5. Render Word/PDF outputs and reopen them for structural checks.
6. Verify references in Zotero and source documents.
7. Run the three NLM review passes.
8. Publish only after all unresolved cells have an explicit disposition.
