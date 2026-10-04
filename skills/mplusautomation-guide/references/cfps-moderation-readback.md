# CFPS PP-LGCM moderation readback

The Windows PP-LGCM workflow separates an existing-output readback from a new
Mplus estimate. When a moderation result is weak or non-significant, first
inventory the successful `.out` files with `MplusAutomation::readModels()` and
extract interaction rows, standard errors, reported p-values, and diagnostics.
Save a CSV, a file-level ledger, and plots in a timestamped directory outside
the original result tree. Record the input root, filename filter, R and
`MplusAutomation` versions, and `new_mplus=0`.

Filename variants are common (`mi_tics`, `nocontrolmean`, `plot`, `lrt`, `mg`,
`test`, and copied files). Counts of significant rows are therefore never a
model-selection rule. Group by substantive model identity and variant, retain
all attempted variants, and defer scientific adoption to the MI/LRT,
convergence, parameter-boundary, and manuscript-provenance contracts.

Allowed next steps are theory-led and pre-specified: verify the estimand and
scale (absolute versus mean-standardized), centering and interaction coding,
reliability and range restriction, sample loss and interaction power, and a
nonlinear/threshold form only when supported by the substantive theory. A
simple slope can be significant in one group while the interaction is not; the
group difference itself requires a Wald or equivalent joint test. Do not
average MI p-values, use an invalid LRT, choose the smallest p-value,
dichotomize after seeing the outcome, remove controls because they weaken
significance, or hide failed/convergence-warning models.

The isolated CFPS audit under
`reports/cfps_moderation_readback_20261004/` read 56 existing output files and
168 interaction rows. It is diagnostic evidence only; it does not release a
moderation claim or authorize new Mplus submissions while scientific or memory
gates are closed.

A raw-text scan of the same 56 files found no `TECH3` section and no explicit
parameter-estimate covariance matrix. Four files contain latent-variable
covariance tables, which are not a VCOV for the interaction regression
coefficients. The reproducible read-only entry point is
`work/cfps_moderation_raw_tech3_scan_20261004.py`, with receipt
`reports/cfps_moderation_evidence_v2_20261004/cfps_moderation_raw_tech3_scan_v1.{md,json}`.

The corresponding 56 historical `.inp` files all contain `MODEL CONSTRAINT`
and `XWITH`, but request `TECH3` in 0/56 inputs (TECH8 is requested in 52/56).
This confirms that missing interaction-parameter VCOV is an input-contract
limitation. The input-side scan is reproducible from
`work/cfps_moderation_input_output_contract_scan_20261004.py`; its receipt is
`reports/cfps_moderation_evidence_v2_20261004/cfps_moderation_input_output_contract_scan_v1.{md,json}`.

An isolated preparation script,
`work/prepare_cfps_moderation_tech3_repair_20261004.py`, creates 56 copies with
only `TECH3` added to the staged `OUTPUT:` block. Its manifest records original
and staged hashes and reports `PREPARED_NOT_SUBMITTED`, `mplus_submissions=0`.
The stage is a reusable input package, not a result and not permission to run
all 56 models; a family and resource/VCOV contract must be frozen first.

The staged files are grouped into a reproducible family schedule at
`work/cfps_moderation_tech3_repair_20261004/schedule_manifest_v1.json`:
24 process-by-moderator batches and 56 members. The schedule starts with one
worker, permits two only at a documented memory threshold and excludes any
unclassified external Mplus process. It records `PREPARED_NOT_SUBMITTED` until
the manuscript-table target and scientific contract are fixed.
