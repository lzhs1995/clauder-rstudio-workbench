# CFPS deferred-output audit

Use this reference after the frozen CFPS deferred queue has been built and
before reopening any model. It describes an output-level readback, not a new
Mplus run. The audit must be performed against a copied ledger and must never
write into the canonical R, data, input or result directories.

## What the audit records

For every unique output basename, record:

- queue-cell count and deferred category;
- existence, size, modification time and SHA-256;
- `MODEL RESULTS`, beginning/ending time and normal/non-normal termination
  markers;
- input `ERROR`/`WARNING` counts;
- incomplete-imputation replication messages;
- ill-conditioned or non-positive Fisher information, saddle-point messages,
  and unavailable standard errors; and
- a short, line-numbered excerpt of each substantive diagnostic.

Join this file-level record back to the cell-level queue. A single `.out` can
serve several rows and can contain both normally completed and failed
imputation replications; do not multiply a file-level success into a complete
MI result.

## Decision labels

The 2026-10-04 CFPS read-only audit produced 51 existing files for 669 deferred
cells:

| output evidence | audit label | permitted use |
| --- | --- | --- |
| 31 files with ordinary Mplus warnings and no explicit non-normal termination | `COMPLETED_WITH_WARNINGS` | historical table-cell comparison after warning review; not a new scientific claim |
| 19 files with an input-level `SAVEDATA`/auxiliary error but `MODEL RESULTS` and an ending timestamp | `INPUT_INSTRUCTION_ERROR_MODEL_RESULTS_PRESENT` | technical or historical numerical corroboration only; do not use missing factor scores/VCOV for downstream inference |
| a file with an incomplete replication, ill-conditioned/non-positive Fisher information, or unavailable SE | `ESTIMATION_NONNORMAL` | retain as a technical limitation; do not select the successful imputation members |
| missing output or no terminal evidence | `MISSING_OUTPUT` or `INCOMPLETE_OR_UNCLASSIFIED` | deferred until a new contract exists |

These labels do not close the frozen queue automatically. In particular,
`MODEL RESULTS` plus an ending timestamp does not repair an ignored `SAVEDATA`
request, and one normally terminating imputation member does not repair an
incomplete MI analysis.

## Moderation boundary

The same rule applies to interaction readback. A count of nominal `p < .05`
rows is an audit statistic, not a selection rule. If parameter covariance is
not available, do not report interaction, group-difference, simple-slope,
Johnson–Neyman, or three-way moderation significance. A simple slope that is
significant within one subgroup does not establish a significant difference
between subgroups.

The safe readback order is:

1. verify model identity, scale, centering/coding, controls, clustering and
   imputation membership;
2. check complete replication and standard-error status;
3. require a usable covariance matrix for a joint Wald or delta-method
   conditional-slope calculation;
4. inspect estimates, confidence intervals, missingness, reliability and
   power; and
5. write the null or limitation explicitly when a gate is not passed.

Do not average imputation-member p-values, drop controls, change cut points,
choose a favorable imputation member, or search model variants for the lowest
p-value. Any new sensitivity estimate must be specified before execution,
isolated, hash-logged, resource-admitted and retained whether it succeeds or
fails.

## Evidence and guide linkage

The source audit receipt is:

`reports/cfps_deferred_recovery_queue_20261004/cfps_deferred_output_error_audit_v1.{csv,json,md}`

The native ClaudeR/MplusAutomation spot-check receipt is
`reports/cfps_deferred_recovery_queue_20261004/cfps_deferred_mplusautomation_readback_v1.md`.
It demonstrates that `readModels()` can parse a non-normal file (134 parameter
rows and 17 warning blocks) while preserving the separate MI completion and
standard-error validity gate.

It records `new_mplus_submission=0` and `source_mutation=false`. The report is
an evidence boundary for historical reconciliation; it is not a scientific
release and does not authorize downstream CHARLS adoption or final PDF review.
