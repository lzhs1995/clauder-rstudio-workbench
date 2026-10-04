# CFPS moderation B1/B2 boundary report

This is a readback of existing artifacts. It submits no Mplus model and does not
change any source file.

## B1: MI D2/LRT

The existing LRT contract covers 25 candidates. Its current evidence counts are
6 sensitivity-only rows, 12 source-follow-up rows and 7 rows deferred for nesting
or pooling audit. `candidate_D2_rows=7`, but `candidate_D2_release=false` and
`scientific_release=false`. The contract explicitly says that sidecar hashes and
printed likelihood precision do not prove immutable paired-member execution
bytes. Therefore no formal LRT p value is released. Arithmetic averages of MI
p values are not a substitute.

## B2: group-slope Wald test

The 56 moderation outputs contain 168 interaction parameter rows. A representative
`MplusAutomation::readModels()` object contains the unstandardized parameter table,
but its `tech3` object is empty and no coefficient covariance matrix for the
conditional slopes is available in the parsed historical output. The existing
simple-slope rows therefore cannot be converted into a valid between-group Wald
test from this evidence alone. A significant simple slope in one group and a
non-significant slope in another remains insufficient evidence of a significant
interaction.

## Decision

B1 and B2 stay open as evidence boundaries. The next admissible action is to
locate a complete historical constraint/covariance artifact or pre-register an
isolated new model after MI, memory and estimand gates pass. No model is selected
because it has the smallest p value.
