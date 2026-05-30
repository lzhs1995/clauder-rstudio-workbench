# Worker contract: one mediator, paired mval, three durable files

Each worker handles exactly one mediator across all requested groups. It is
driven entirely by environment variables (so the fan-out harness can launch many
copies), and it must emit three durable files the orchestrator polls.

## Inputs (environment variables)

The reference worker reads these (`NEW47_*` is the case-study prefix; rename per
project but keep the shape):

| env var               | meaning                                  | example                         |
|-----------------------|------------------------------------------|---------------------------------|
| `NEW47_MEDIATOR`      | required mediator id                     | `msat_c12_3`                    |
| `NEW47_NBOOT`         | bootstrap replicates                     | `10` (smoke) / `1000` (formal)  |
| `NEW47_SEED`          | RNG seed                                 | `12345`                         |
| `NEW47_GROUPS`        | comma list of groups                     | `sy_female,sy_male`             |
| `NEW47_RUN_ID`        | run identifier (folder name)             | `20260526_212922_maxp7`         |
| `NEW47_MAX_PARALLEL`  | concurrency level (recorded in manifest) | `7`                             |
| `NEW47_OUTPUT_ROOT`   | base output dir                          | a project path                  |
| `NEW47_UPLOAD_ENABLED`| optional durable-archive toggle          | `false`                         |

Output layout (must match what the fan-out contract expects):

```text
<OUTPUT_ROOT>/<RUN_ID>/max_parallel_<N>/<mediator>/
  state_<mediator>.json        # progress + status
  manifest_<mediator>.csv      # one row, completion bookkeeping
  validation_<mediator>.csv    # one row per group, pass/fail checks
  run_log_<mediator>.txt
  <nested cmest RData/RDS>
```

## The paired-mval mechanism

The worker temporarily shadows `CMAverse::cmest` and `base::saveRDS` so the
original `mval=list(0)` call also produces the M=1 result on the **same**
bootstrap indices, then assembles a nested object:

```r
res_cma_<mediator>_aincc_2_1_list[[group]][["0"]]   # full cmest, mval = 0
res_cma_<mediator>_aincc_2_1_list[[group]][["1"]]   # full cmest, mval = 1
```

Both `[["0"]]` and `[["1"]]` must be complete `cmest` objects. The shadows are
installed in `.GlobalEnv` and removed `on.exit`, so the original script body is
reused unchanged inside the wrapper.

## Required object shape (do / don't)

```r
# CORRECT
res_cma_<mediator>_aincc_2_1_list[[group]][["0"]]
res_cma_<mediator>_aincc_2_1_list[[group]][["1"]]

# WRONG: split objects, missing the paired "1"
res_cma_<mediator>_aincc_2_list[[group]]
res_cma_<mediator>_aincc_2_1_list[[group]]   # group holds a bare cmest, no "0"/"1"
```

Save the full `cmest` (effects, `$data`, `$reg.output`, `$ref`, `$call`,
bootstrap fields). Never save a compact result table or effect vector instead.

**Logging rule (enforced): never wrap the worker in `sink()`.** In a detached
Rterm an open `sink()` connection keeps the process alive after the model
finishes, so the job never exits and the fan-out slot is never released. Log only
via `cat()` + `flush.console()` and `write_state()`. `clauder-workbench
worker-lint` (invoked automatically by `fanout-plan`/`fanout-run`) BLOCKs any
worker whose `code_file` contains `sink(`.

## manifest fields (one row per mediator)

`run_id`, `mediator`, `groups`, `nboot`, `seed`, `max_parallel`,
`local_rds_path`, `local_size`, `save_elapsed_sec`, `validation_csv`,
`upload_status`, `remote_path`, `remote_size`, `size_match`, `fs_id`,
`upload_log_path`, `completed_at`, `worker_version`.

These let the orchestrator decide whether the model finished, the file saved,
the optional upload succeeded, and whether a local delete is compliant.

## state file

`state_<mediator>.json` carries at least `stage`, `status`, and `updated_at`.
`status == "complete"` plus the two CSVs present is the orchestrator's
done-signal (see clauder-rstudio-workbench fan-out merge gate). Emit progress at
each stage and `flush.console()` so long runs are observable.

## Async / .GlobalEnv caveat

An async Rterm worker does **not** put its objects back into the foreground
RStudio `.GlobalEnv`. The durable RData + manifest + validation CSV are the only
evidence of completion. If a foreground check is needed, read the saved RData
back into the session explicitly.
