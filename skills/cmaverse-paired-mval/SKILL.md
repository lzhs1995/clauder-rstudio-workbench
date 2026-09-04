---
name: cmaverse-paired-mval
description: Use when running CMAverse 4-way decomposition with paired mval (M=0 and M=1 in one bootstrap), saving full cmest objects, and fanning the per-mediator workers out across one RStudio session. Pairs with clauder-rstudio-workbench for the parallel async fan-out machinery.
---

# CMAverse Paired-mval Bootstrap

This skill captures a verified workflow for running CMAverse 4-way decomposition
where, within a single bootstrap process, each replicate computes both
`mval=list(0)` and `mval=list(1)` on the **same** bootstrap indices, and the
full `cmest` object (not a compact summary) is saved per mediator per group.

It is a domain companion to **clauder-rstudio-workbench**: the orchestration
(one RStudio session -> N child R workers -> poll -> merge gate) is provided by
the fan-out harness there. This skill supplies the CMAverse-specific contract:
what a worker must do, what counts as a valid result, and how to map a
monolithic `g_formula` script into independent per-mediator workers.

For ordinary descriptive statistics and publication-ready three-line Table 1
outputs, route to the sibling `$comparegroups-guide` skill instead.

> First case study: `g_formula_new4.7` (original script region `552:3561`). The
> skill is written to generalize to `new4.8.*`; always re-do the region
> inventory for a new script version before trusting the old region map.

## Why paired mval

Running M=0 and M=1 as two separate `cmest(..., inference="bootstrap")` calls
draws independent bootstrap samples, so the M=0 vs M=1 contrast is contaminated
by resampling noise. Paired mval fixes one set of indices per replicate:

```text
replicate b:
  indices_b   <- bootstrap sample
  effect_m0_b <- statistic(data, indices_b, mval = list(0))
  effect_m1_b <- statistic(data, indices_b, mval = list(1))
```

The implementation wraps `cmest()`/`boot()` so the original `mval=list(0)`
region also produces M=1 inside the same bootstrap. **Do not** run the original
M=0 and M=1 regions separately and then claim "same bootstrap".

## First reads

- Map a monolithic script into workers: [region-mapping.md](references/region-mapping.md)
- Worker responsibilities and the three-file contract: [worker-contract.md](references/worker-contract.md)
- What a valid cmest result must satisfy: [validation-standard.md](references/validation-standard.md)
- Choosing and proving concurrency: [concurrency-and-resources.md](references/concurrency-and-resources.md)
- Post-processing the saved objects into tables/plots: [postprocessing.md](references/postprocessing.md)
- Failure modes, prohibitions, native-PR direction: [failure-modes-and-pr.md](references/failure-modes-and-pr.md)

## Workflow

1. **Inventory** the target script's mediator regions (see region-mapping.md).
2. **Generate a fan-out contract** with the helper, then validate it:

   ```powershell
   python scripts\make_worker_contract.py `
     --worker-file <paired_worker.R> `
     --output-root "<OUTPUT_ROOT>" --run-id <RUN_ID> --max-parallel 7 `
     --mediators msat_c12_2,msat_c12_3,msat_c1_2,msat_c21_2,msat_c21_3,msat_c2_2,msateco_c2_2 `
     --groups sy_female,sy_male --nboot 10 --seed 12345 `
     --out task.yaml
   clauder-workbench native-smoke start --task-key cmaverse_paired_mval_<RUN_ID> --session-name default --agent codex --require-raw-file
   # Run real Codex native MCP tools and save each visible tool result to a raw text file:
   #   list_sessions -> smoke_list_sessions.txt
   #   execute_r("cat('NATIVE_EXECUTE_OK pid=', Sys.getpid(), '\n')") -> smoke_execute_r.txt
   #   execute_r_async("cat('NATIVE_ASYNC_DONE pid=', Sys.getpid(), '\n')") -> smoke_execute_r_async.txt
   #   get_async_result(<JOB_ID>) -> smoke_get_async_result.txt
   clauder-workbench native-smoke record --task-key cmaverse_paired_mval_<RUN_ID> --step list_sessions --ok --session-name default --raw-file smoke_list_sessions.txt
   clauder-workbench native-smoke record --task-key cmaverse_paired_mval_<RUN_ID> --step execute_r --ok --marker NATIVE_EXECUTE_OK --pid <R_PID> --raw-file smoke_execute_r.txt
   clauder-workbench native-smoke record --task-key cmaverse_paired_mval_<RUN_ID> --step execute_r_async --ok --job-id <JOB_ID> --raw-file smoke_execute_r_async.txt
   clauder-workbench native-smoke record --task-key cmaverse_paired_mval_<RUN_ID> --step get_async_result --ok --job-id <JOB_ID> --marker NATIVE_ASYNC_DONE --raw-file smoke_get_async_result.txt
   clauder-workbench native-smoke complete --task-key cmaverse_paired_mval_<RUN_ID>
   clauder-workbench fanout-plan --contract task.yaml --parent-evidence <native_smoke_PASS.json>
   ```

3. **Lint the worker, then smoke first** (`nboot=10`), then run:

   ```powershell
   clauder-workbench worker-lint --contract task.yaml
   clauder-workbench fanout-run --contract task.yaml --parent-evidence <native_smoke_PASS.json> --max-parallel 7 --first-artifact-timeout-min 15
   ```

   > `worker-lint` (also run automatically inside `fanout-plan`/`fanout-run`)
   > BLOCKs any worker whose `code_file` contains `sink(`. A `sink()`-wrapped
   > worker keeps the detached Rterm alive after the model finishes, so the job
   > never exits and the slot is never released. Log via `cat()` +
   > `flush.console()` and `write_state()` only.
   >
   > `fanout-run` submits and polls the workers itself **through the Python MCP
   > stdio client** (its evidence is stamped `MCP_STDIO_OK`). It does **not** drive
   > the agent's native `mcp__r_studio__` wrapper. If a task must be proven over the
   > agent's native MCP transport, use the **native path** instead of `fanout-run`:
   > `fanout-plan` (emit per-worker submit codes) → submit each via the native
   > wrapper → `async-guard register-job` (record each real `job_id`) → `fanout-poll`
   > → `merge-gate`. `fanout-run --transport native-wrapper` deliberately BLOCKs and
   > points here, so it can never silently masquerade as a native submission.
   >
   > **Concurrency.** `--max-parallel` is the **starting** ceiling. By default it is
   > also fixed for the whole run. Add `--auto-scale` to implement the
   > best-practice §6 behavior: each poll cycle the harness samples system memory
   > and, while memory stays under `--memory-threshold` (default 85%) and workers
   > remain pending, raises concurrency by one up to the worker count (or
   > `--max-parallel-cap`); when memory crosses the threshold it stops launching
   > new workers and lets the in-flight ones drain (it never kills a running job).
   > Every adjustment is recorded in the run's `scale_log`.
   >
   > ```powershell
   > clauder-workbench fanout-run --contract task.yaml --max-parallel 3 `
   >   --auto-scale --memory-threshold 85 --first-artifact-timeout-min 15
   > ```

4. **Validate** every mediator x group result before claiming success:

   ```powershell
   python scripts\cmaverse_validate.py --output-root "<RUN_DIR>" `
     --mediators msat_c12_2,msat_c12_3,msat_c1_2,msat_c21_2,msat_c21_3,msat_c2_2,msateco_c2_2 `
     --groups sy_female,sy_male
   clauder-workbench merge-gate --contract task.yaml --parent-evidence <native_smoke_PASS.json>
   ```

5. **Scale to formal run** only after a resource probe (concurrency-and-resources.md).
   Do not extrapolate `nboot=10` optimal concurrency to `nboot=1000`.

## Hard rules

- Save the **full `cmest` object**, never a compact result table or effect vector.
- Never overwrite the original R script; workers reuse the original M=0 region.
- Never delete a local RData before validation passes.
- Never put credentials (cloud-drive accounts, UK/UID, tokens) in any markdown,
  asset, schema, or contract. The optional durable-archive/upload step takes
  credentials only from the environment or an untracked config.
- Never resubmit a long worker just because one MCP poll dropped: check the
  durable files and the Rterm process first.
- Never start a CMAverse fan-out run without fresh `native-smoke` PASS evidence
  from the current agent native MCP tool layer. The generated contract sets
  `requires_native_smoke: true` by default; use `--no-require-native-smoke` only
  for diagnostic MCP-stdio experiments, not for formal completion claims. Formal
  runs must use `--require-raw-file`; v0.3.3 and later require all four record
  evidence ids to be chained into the final PASS and preserve raw output hashes.
  v0.3.4 and later also reject any downstream `native_smoke` parent evidence
  unless those four chained record ids are present and unique.
- **Never wrap the worker in `sink()`.** A `sink()`-wrapped worker keeps the
  detached Rterm alive after the computation finishes, so the job never exits and
  the fan-out slot is never released — recovery then needs a manual `cancel` after
  confirming the durable output. Log via `cat()` + `flush.console()` and the
  `write_state()` helper. This rule is enforced: `clauder-workbench worker-lint`
  (run automatically by `fanout-plan`/`fanout-run`) BLOCKs any worker containing
  `sink(`.
