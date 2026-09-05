# ClaudeR integration

## Preflight

Use a dedicated RStudio session when possible. Ask ClaudeR to check R and the
packages `compareGroups`, `haven`, `labelled`, `officer`, `flextable`,
`jsonlite`, and `digest`, then audit the real input and its labels.

## Sync versus async

- One small table expected to finish within about 25 seconds: `execute_r`.
- Multiple tables, large `.dta` input, or DOCX batches: one
  `execute_r_async`, followed by `get_async_result` using the same job ID.

The runner locates ClaudeR's injected `clauder_progress()` in the async work
environment and emits the same stages to stdout for Rscript use:

`preflight -> import -> labels -> compute -> render -> validate -> complete`

The batch runner adds `batch_preflight`, one `batch_job` message per declared
job, and `batch_complete`. Submit the whole batch in one `execute_r_async`
call; do not submit each manifest row as a separate job.

Transient polling failure is not task failure. Inspect durable outputs and poll
the original job again. Never submit a second copy while the first can still be
running.

## Verification loop

After completion, use ClaudeR to read the DOCX, inspect the numeric CSV, and
reconcile manuscript claims. `generate_codebook` is useful for the project
inventory, but the skill's `haven` audit is authoritative for `.dta` labels and
missing values. `generate_notebook` may then preserve the final workflow.
