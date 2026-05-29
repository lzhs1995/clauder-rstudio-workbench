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
   clauder-workbench fanout-plan --contract task.yaml
   ```

3. **Smoke first** (`nboot=10`), then run:

   ```powershell
   clauder-workbench fanout-run --contract task.yaml --max-parallel 7 --first-artifact-timeout-min 15
   ```

   > `fanout-run` submits and polls the workers itself **through the Python MCP
   > stdio client** (its evidence is stamped `MCP_STDIO_OK`). It does **not** drive
   > the agent's native `mcp__r_studio__` wrapper. If a task must be proven over the
   > agent's native MCP transport, use the **native path** instead of `fanout-run`:
   > `fanout-plan` (emit per-worker submit codes) → submit each via the native
   > wrapper → `async-guard register-job` (record each real `job_id`) → `fanout-poll`
   > → `merge-gate`. `fanout-run --transport native-wrapper` deliberately BLOCKs and
   > points here, so it can never silently masquerade as a native submission.
   >
   > `--max-parallel` is a **fixed, manually chosen** ceiling for this run. The
   > harness does not auto-scale concurrency up or down mid-run; pick it from a
   > resource probe (step 5) and re-run with a different value if needed.

4. **Validate** every mediator x group result before claiming success:

   ```powershell
   python scripts\cmaverse_validate.py --output-root "<RUN_DIR>" `
     --mediators msat_c12_2,msat_c12_3,msat_c1_2,msat_c21_2,msat_c21_3,msat_c2_2,msateco_c2_2 `
     --groups sy_female,sy_male
   clauder-workbench merge-gate --contract task.yaml
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
