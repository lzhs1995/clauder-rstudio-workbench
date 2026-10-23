# CHARLS son×urban pilot: bootstrap recovery and bounded timeout (2026-10-23)

This case records a Windows/RStudio pilot that used a changed MI input, so it
is a recovery and contract lesson rather than a completed H4 result.

## Keep the moderator semantics explicit

For the son×urban family, `C4` is the known-class grouping variable and `C3`
is an ordinary baseline control. A generated input inherited the education
family's `USEVARIABLES`, `KNOWNCLASS`, and `ON c4` lines. Before any engine
submission, patch the isolated root together and refresh every `job.json` and
contract hash:

```text
USEVARIABLES=... c1 c2 c3 c5-c11;
KNOWNCLASS=cg(c4=0 c4=1);
sz/ix/sx/iy/sy/iz ON c3*...;
```

Preserve a preimage hash and write an independent semantic audit. A pilot
that runs with the wrong C3/C4 role is not evidence for the requested family.

## R bootstrap ordering on Windows

`execute_r_async()` runs the script in a fresh R process. Functions used before
`library()` must be namespace-qualified. In this case the first two submissions
failed before Mplus because the script called `write_json()` before loading
jsonlite, then `ps_create_time(ps_handle())` before loading ps. The robust
pattern is:

```r
jsonlite::write_json(...)
ps::ps_create_time(ps::ps_handle())
```

Parse the script and run these namespace smoke checks through the live RStudio
session before resubmitting. Archive the failed guard record and use a new
task key; do not overwrite or resubmit an in-flight record.

## Bounded pilot interpretation

The final native job used one Mplus slot and a 240-second per-model limit.
Parent and GH07 A/B were usable and the GH07 start comparison passed. GH15 A
timed out, so GH15 B was correctly withheld. This is a pilot feasibility
failure, not a failed substantive hypothesis and not a completed MI family.
Keep `engine_receipt.json`, stdout/stderr, `receipt.json`, the terminal file,
and the released awake-guard evidence. Never pool the usable prefix or extend
the same GH15 structure merely to obtain a full family.

## Reusable Windows checks

1. Run a static C3/C4 semantic audit and refresh hashes before `runModels()`.
2. `py_compile` the adapter; preparation scripts can introduce indentation
   errors while copying recovery code.
3. Use a durable `PROGRESS.jsonl` and the same async job ID for polling.
4. Treat bootstrap failures, Mplus timeouts, readback failures, and usable
   estimates as different terminal classes.
5. A timeout under a declared bound closes that pilot. A new attempt requires
   a new contract and explicit change in estimation object or resource plan.

The isolated son×urban root contains the complete evidence without private
MI/RDS release files. The corresponding scientific boundary remains:
**四项调节完整推断、完整 H4 仍未完成。**
