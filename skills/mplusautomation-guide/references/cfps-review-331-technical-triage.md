# CFPS 331-cell technical triage

`REVIEW_CELL` is a scientific adoption state, not a missing-source state. Before submitting a new estimator, combine the existing fit and derived evidence:

- the 264 fit cells are backed by 64 producer groups; the two shape-factor groups previously flagged for diagnostics are now resolved by the exact `ces8sd_covar_time12_22` filepath used in both R scripts;
- the 67 derived cells are backed by 17 producer groups; all inputs and chosen outputs are present, five groups are semantically closed and twelve have now been technically source-reconciled through the exact R alias/spanner assembly. Their scientific adoption remains open because the historical display producer and semantic producer are distinct;
- the entire queue is 331 cells in 81 review groups, and the report must keep scientific release false.

The Windows read-only implementation is
`work/pp_lgcm_reconciliation_20261001/build_cfps_review_331_technical_triage_20261004.py`, with evidence in
`reports/cfps_review_331_technical_triage_20261004/cfps_review_331_technical_triage_v1.{json,md}`.

Use the report to route work: decide historical display versus current sensitivity for fit changes and adjudicate the twelve derived alias groups. Do not describe the queue as “331 models missing,” and do not re-estimate a group merely because its scientific decision is still open.

The 12-group technical closure is recorded in
`reports/cfps_derived_alias_resolution_20261004/cfps_derived_alias_resolution_v1.{json,md}`.
It preserves the printed historical values and records both producer paths; it does
not modify the manuscript or authorize a new Mplus run.

For the initial-draft reproduction target, all 331 technically sourced cells are
also frozen in
`reports/cfps_historical_review_adoption_20261004/cfps_historical_review_adoption_v1.{json,csv,md}`:
264 fit cells retain current candidates as sensitivity, while 67 derived cells retain
the historical display and carry the semantic producer as a sidecar. This is a
historical-reproduction disposition, not a scientific release of the corrected study.
