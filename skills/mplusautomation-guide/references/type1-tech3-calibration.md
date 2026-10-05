# Windows single-slot TECH3 calibration

Use a small, pre-specified set of existing successful non-MI models to calibrate
the Windows host before considering concurrency. Stage the `.inp` and its data
under a run directory, add only `TECH3`, and keep the original input/output
directories read-only. Call `runModels()` with the staged `.inp`, then call
`readModels()` on the staged `.out`; passing an `.inp` to `readModels()` is a
wrapper error and must be recorded rather than retried as a new estimate.

The CFPS calibration on 2026-10-05 completed three models in one controlled
slot:

| model | elapsed | parameter identity | result |
|---|---:|---|---|
| `type1::edu` | 619 s | 112 rows, max estimate/SE difference 0 | normal |
| `type1::pinc` | 1049 s | 114 rows, max estimate/SE difference 0 | normal |
| `type1::sex` | 688 s | 112 rows, max estimate/SE difference 0 | normal |
| `type1::urban` | 1240 s | 112 rows, max estimate/SE difference 0 | normal |

The `pinc` worker's sampled Mplus private peak was about 324 MiB; the `edu`
sample was about 204 MiB. The `sex` and `urban` runs completed normally but had
no reliable private-memory sample, so their peaks must remain unknown. These
are calibration observations, not universal Windows requirements and not
evidence for model selection.

Before each submission, take a fresh Windows profile and apply the composite
admission gate: physical-memory increment plus reserve, commit headroom, disk
free space, CPU pressure, and output paging combined with disk latency. Pages
Input/sec alone is telemetry. After completion, verify that the owned Mplus
parent chain is gone, save the receipt/readback/identity hashes, and refresh the
profile before admitting another worker. Keep MI, LMS, Bayes, and models without
a historical normal `.out` in a separate deferred lane until their resource and
scientific contracts are explicit.

ClaudeR's async wrapper can retain a stale `running` record after durable output
files are complete. Do not resubmit in that state: compare `progress.json`, the
receipt, `.out` normal-termination marker, readback RDS and the owned process
chain. Archive the original async record with its real job id only after those
files prove terminal completion.
