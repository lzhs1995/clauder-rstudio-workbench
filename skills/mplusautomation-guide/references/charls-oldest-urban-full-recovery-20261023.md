# CHARLS oldest × urban full-family recovery (Windows, 2026-10-23)

This note records a real MplusAutomation/ClaudeR recovery. It is a reusable
execution contract, not evidence that the whole H4 program is complete.

## What was run

The isolated family used 20 conditional working MI members (A), one MI01
start-sensitivity member (B), `TYPE=COMPLEX MIXTURE RANDOM`, `XWITH`, 15-point
Gauss-Hermite integration, and one Mplus engine slot. Each A member had
N=2,397, 433 clusters, and 134 expected free parameters. The A family was
pooled only after all 20 members had a `USABLE` normalized readback. B was
reported as start sensitivity and never substituted for A or entered the
Rubin pool.

The independent verifier read every saved parameter vector and covariance
matrix again, checked input/output hashes and positive-definite geometry, and
recomputed 21 planned contrasts. The primary `SY:SXIZ` urban group-1 minus
group-0 contrast was 0.0306772557 (95% CI [-0.2619070489, 0.3232615603],
p=.8371808527). The receipt explicitly keeps
`full_H4_complete=false`: one completed family is not four complete
moderation families.

## Failure that matters for future runs

The first full-family worker passed its RStudio identity check and completed
MI01--MI03. At MI04, the adapter raised `FileNotFoundError` before starting
Mplus because the full root did not contain the pilot's already-passed
`results/GH07_STARTS.json`. The gate in `adapter.py` intentionally requires
that evidence before later members. The failure was therefore a preparation
contract error, not an Mplus estimation failure.

The recovery sequence was:

1. Keep the failed MI04 directory and `ADAPTER_EXCEPTION.json` as an audit
   artifact; do not overwrite it.
2. Copy the pilot's passed GH07 starts evidence into the isolated full root
   and record its source, SHA-256, and `no_mplus_call=true` provenance.
3. Add a resume path that reuses a member only when `receipt.json` says
   `USABLE`; archive and remove a nonterminal directory before recompiling it.
4. Resume from MI04. MI01--MI03 were reused without any new Mplus call.

This is the required distinction between *missing gate evidence* and a
failed model. Never label a pre-estimation exception as a statistical
non-convergence, and never rerun already verified members merely because the
RStudio job acknowledgement was lost.

## RStudio parent identity on Windows

`list_sessions` reports the live R session (`rsession-utf8.exe`); the
`rstudio.exe` desktop parent is a different process. `execute_r_async` starts
an Rterm child whose parent is the live R session. Therefore the run contract
must record `Sys.getpid()` and `ps::ps_create_time(ps::ps_handle())` from the
bound R session. A bootstrap launched by the async worker should verify:

```text
worker.ppid == contract.rstudio_owner.pid
create_time(worker.ppid) == contract.rstudio_owner.created
```

Writing the desktop `rstudio.exe` PID into this field causes a safe
preflight rejection before Mplus starts. Correct the isolated contract and
archive the failed job; do not bypass the identity assertion.

## Scheduling and recovery rules

- Use `async-guard pre-submit`, call the native `execute_r_async` exactly once,
  register the returned real job ID, and poll that same ID.
- Source long R code with `local=TRUE` so `clauder_progress` and durable
  `PROGRESS.jsonl` remain visible.
- Limit this high-dimensional family to one Mplus process on a 16-GiB Windows
  host. Admit a new engine only after checking available memory, commit
  headroom, CPU, parent-chain ownership, and existing engine leases.
- A dead worker may leave a reservation or lease. Remove it only when the
  owner PID/create-time is dead and no completed engine receipt exists; write a
  cleanup audit line. Never remove a live lease or kill an unrelated Mplus.
- Treat `NOT_RUN_RESOURCE_HOLD` as a durable state with zero engine calls.
  Preserve the receipt and resume when the resource gate opens.
- Keep `USABLE`, `MPLUS_EXIT_FAILURE`, `ADAPTER_EXCEPTION`,
  `NOT_RUN_RESOURCE_HOLD`, and `NONCONVERGED` as distinct states.

## Semantic migration checks

The same internal slot names do not imply the same observed moderator. For
oldest × urban, the observed class is `c4`, while the ordinary control is
`c3` (plus `c5-c11`):

```mplus
USEVARIABLES = ... c1 c2 c3 c5-c11;
KNOWNCLASS = cg(c4=0 c4=1);
```

When migrating a gender or education source, rewrite the model and normalized
slot map together. Count `ON c3*` and `ON c4*` statements and assert the
expected class marker before running Mplus. A blind `c3`/`c4` replacement can
silently make the moderator a covariate or produce an unknown-variable error.

## Public evidence boundary

The public ZIP may contain model syntax, estimates, covariance transforms,
readback receipts, manifests, and audit logs with local paths redacted. It
must exclude individual-level `.dat`, MI/RData objects, auxiliary input
tables, and other row-level records. Verify the ZIP size (<25 MB), SHA-256,
forbidden-file scan, and independent readback before publishing. State the
family scope and the still-open H4 boundary in the README.

