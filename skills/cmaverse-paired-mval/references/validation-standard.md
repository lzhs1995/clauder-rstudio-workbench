# Validation standard: what a valid paired-mval result must satisfy

Completion is not "the worker exited without error". Each mediator must produce a
`validation_<mediator>.csv` with **one row per group**, and every check must pass
before the result is trusted or the local RData is deleted.

## Per-group checks

The worker **asserts these before saving** (a failure is a hard `stop()`):

- group key exists in the nested object;
- `[["0"]]` and `[["1"]]` both exist;
- `inherits(..., "cmest")` for both;
- `$reg.output` exists;
- `$call` and `$ref` are structurally compatible with a native CMAverse object.

The worker also **records these into `validation_<mediator>.csv`**, and
`scripts/cmaverse_validate.py` **re-checks them as the gate**:

- `m0_is_full_cmest`, `m1_is_full_cmest` (both TRUE);
- `m0_effect_n`, `m1_effect_n` == 17;
- `m0_data_ncol`, `m1_data_ncol` == 159;
- `m0_ref_mval` == 0, `m1_ref_mval` == 1;
- **boot-hash equality** — the core invariant: `m0_boot_hash` and `m1_boot_hash`
  must both be present, non-empty, and **equal** for every row. This proves M=0
  and M=1 used the **same** bootstrap indices rather than two independent
  resamples. The self-reported `paired_same_bootstrap` boolean is treated only as
  an auxiliary signal; the gate decides on the hashes themselves, so a worker
  cannot pass by asserting `paired_same_bootstrap=TRUE` without matching hashes.
- **delta_cde deliverable** — the skill's whole point is the paired controlled
  direct effect *difference*. Every row must carry `has_delta_cde` (TRUE) and a
  full inference set: `delta_cde_pe`, `delta_cde_se`, `delta_cde_ci_low`,
  `delta_cde_ci_high`, `delta_cde_pval` (all numeric) plus non-empty
  `delta_cde_scale` / `delta_cde_contrast`. Missing or non-numeric delta inference
  fails the gate. `--no-delta-cde-check` relaxes this but marks the run
  `weak_validation` (not for formal success claims).

The 17-effect and 159-column figures are case-study specific (new4.7 data). When
porting to another dataset/version, recompute the expected effect count and
column count from one known-good native `cmest` object and pass them via
`--expected-effects` / `--expected-ncol`. Prefer that over `--no-count-check`,
which relaxes the gate and marks the result `weak_validation` (not for formal
success claims). `--no-pairing-check` and `--no-delta-cde-check` likewise
downgrade the run to `weak_validation`.

## Row-count expectations

```text
validation rows = (#mediators) x (#groups)
```

| scope                 | mediators | groups | expected rows |
|-----------------------|----------:|-------:|--------------:|
| smoke (`sy_female,sy_male`) | 7   | 2      | 14            |
| formal (full data_list)     | 7   | 25     | 175           |

`scripts/cmaverse_validate.py` enforces this: it loads every
`validation_<mediator>.csv`, checks the row count equals mediators x groups, and
checks every row's pass column is TRUE. A missing CSV, a short CSV, or any FALSE
row fails the gate.

## A concurrency level is "usable" only if

- all mediators completed;
- `failed` is empty;
- manifest row counts are complete;
- every validation row passed;
- no Rterm abnormal exit;
- no RData write failure;
- C-drive free space covered the concurrent write peak;
- if upload is on, upload kept pace and local RData did not pile up.

Absence of a runtime error is **not** sufficient. No durable validation row, no
completion claim.
