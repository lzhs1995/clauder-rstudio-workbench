# Async Long Jobs

Use `execute_r_async` for long-running model fitting, bootstrap, simulation, large file processing, or batch figure/table generation.

## Polling Rules

- Save the returned `job_id`.
- Poll with `get_async_result(job_id)`.
- Treat `running` as normal.
- Do not resubmit the same code unless there is a real error or intentional change.
- Add `clauder_progress(stage, message)` at meaningful milestones.
- Before submitting formal long work, record an `async-guard submit` evidence entry with `--io-mode`.
- For large RData/model jobs, use `--io-mode durable_files`; do not marshal large model objects through async `outputs`.

Example R code inside an async job:

```r
clauder_progress("read_data", "Reading inputs")
data <- readRDS(input_path)

clauder_progress("fit_model", "Fitting model")
fit <- fit_model(data)

clauder_progress("export", "Saving outputs")
saveRDS(fit, output_path)
```

## Progress Reporting

Report stage, message, elapsed time, and unchanged `job_id`. Do not rely on percent values as the main user-facing progress signal.

## Main Session Parallelism

The main RStudio session can respond while the async job runs, but shared resources still need discipline:

- Safe by default: `ls()`, `Sys.time()`, `str()`, `head()`, `file.exists()`.
- Unsafe by default: writing the same output files, mutating async `outputs`, or starting another long synchronous task in the same session.
- Best multi-agent mode: one agent monitors the async job while another agent uses a different RStudio session for substantial work.

## Dynamic Concurrency Gate

Use `resource-gate advise` for manual guidance and `resource-gate enforce` for automated pipelines. Increase `max_parallel` by exactly 1 only when all are true:

- memory has stayed below the threshold, normally 85%;
- disk I/O is not visibly blocked;
- Rterm/RStudio and MCP polling remain responsive;
- durable output state or file mtimes are still advancing.

If any condition fails, hold the current parallelism. If memory is extreme or MCP becomes unstable, reduce or stop instead of adding work.

## Cancellation

Use `cancel_async_job(job_id)` only for wrong code, clearly hung jobs, or work that is no longer needed. Cancellation kills the background process and cleans marshaled temp files, but it does not roll back durable files already written by user code.
