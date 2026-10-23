# CHARLS son×urban pilot: bootstrap recovery and bounded timeout (2026-10-23)

This case records a Windows/RStudio pilot with verified input-provenance and
refinement-generation defects. Its initial MI PASS and feasibility conclusion
were superseded by a targeted review. It is not a completed H4 result.

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

The first completed native job used one Mplus slot and a 240-second per-model
limit. Parent and GH07 A/B returned usable numerical results; GH15 A timed out,
and GH15 B was withheld. A subsequent provenance check found two reasons not
to interpret this as failure of the intended scientific model:

- All 20 DAT files were copied from the education MI family. Urban×XZ columns
  existed only in an auxiliary CSV added after imputation, while the actual
  predictor matrix retained education×XZ. The old verifier did not require
  the target columns in the actual fit. A declaration or derived column is
  not proof of execution.
- GH15 inputs had been generated before the current GH07 calls finished.
  Existing directories caused the runner to skip compilation. All 134 labels
  differed from the required current GH07 final values. A `refinement: true`
  metadata flag cannot establish that those starts were used.

The repair uses a new isolated MI root, requires all 25 target interaction
columns in the actual predictor matrix, exports auxiliary values directly
from the fitted inputs, and compiles GH15 only after current GH07 success.
Store source-final-value hashes and compare every inserted label. Keep all old
outputs and mark them diagnostic-only; do not pool them into the repaired
family. This is a correction of a demonstrated implementation defect, not an
unbounded extension after a valid timeout.

## Reusable Windows checks

1. Run a static C3/C4 semantic audit and refresh hashes before `runModels()`.
2. `py_compile` the adapter; preparation scripts can introduce indentation
   errors while copying recovery code.
3. Use a durable `PROGRESS.jsonl` and the same async job ID for polling.
4. Treat bootstrap failures, Mplus timeouts, readback failures, and usable
   estimates as different terminal classes.
5. Before classifying a timeout scientifically, verify actual input and
   prerequisite provenance. A confirmed implementation defect warrants a
   corrected isolated attempt with an explicit cost bound. A correctly
   executed timeout is retained without automatic repeated extensions.
6. Derive C4's data column from the declared schema. C3's column was also
   mistakenly used for the old mixed-community diagnostic; do not transfer
   that diagnostic to urban models or infer it from an education template.

The isolated son×urban root contains the complete evidence without private
MI/RDS release files. The corresponding scientific boundary remains:
**四项调节完整推断、完整 H4 仍未完成。**
