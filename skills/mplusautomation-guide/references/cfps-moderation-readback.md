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
