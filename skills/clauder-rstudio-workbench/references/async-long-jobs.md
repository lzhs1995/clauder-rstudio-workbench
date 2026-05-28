# Async Long Jobs

Use `execute_r_async` for long-running model fitting, bootstrap, simulation, large file processing, or batch figure/table generation.

## Polling Rules

- Save the returned `job_id`.
- Poll with `get_async_result(job_id)`.
- Treat `running` as normal.
- Do not resubmit the same code unless there is a real error or intentional change.
- Add `clauder_progress(stage, message)` at meaningful milestones.

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

## Cancellation

Use `cancel_async_job(job_id)` only for wrong code, clearly hung jobs, or work that is no longer needed. Cancellation kills the background process and cleans marshaled temp files, but it does not roll back durable files already written by user code.
