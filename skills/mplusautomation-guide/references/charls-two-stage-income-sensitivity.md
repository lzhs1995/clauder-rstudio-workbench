# Factor-score batch: reuse and inference boundaries

This is a failure-analysis record, not an endorsed replacement for latent
interaction inference. The CHARLS low-dimensional score batch produced results
quickly, but its initial `USABLE_FSCORES` receipts were too weak. Independent
readback placed the batch on `HOLD_DIAGNOSTIC_ONLY`.

## Check the effective model inputs before expanding MI

Across 40 imputations in each of four indicators, the first-stage model used
only X/Y/Z; imputation changed covariates excluded from that stage. Hashing the
ordered X/Y/Z values and missing masks found four distinct first-stage inputs,
not 160. All 40 score files within each indicator were byte-identical. There
were 156 redundant first-stage member slots. The MI-specific second-stage
covariates still require separate analyses.

Reuse is valid only when the complete effective inputs match: row identity,
used columns and masks, model/estimator, grouping, weights, cluster settings,
starts, transformations, and executable. A filename or equal sample size is
insufficient. Preserve a per-member mapping to the shared producer; do not count
reuse as a new engine call or as 40 independent measurement-model fits.

## Separate engine completion from acceptable inference

The batch had normal-termination text and nonempty scores, yet 66 outputs also
contained `1 ERROR(S) FOUND IN THE INPUT INSTRUCTIONS`. There was no accompanying
detailed error explaining the count. The cause is unresolved: retain the full
outputs and hold adoption rather than suppress the marker or infer a cause.

The SD MI01 input was rewritten after its pilot output was created. A
`replaceOutfile='never'` skip then paired that old output with the current input
hash. An output's embedded input and its original receipt govern provenance;
never certify a skipped fit with a new input hash. Keep the recovered historical
input in a sidecar, without editing the output or pretending the new input ran.

Validate score order against the saved observed columns and missing masks as
well as the cluster column, at the saved precision. A repeated community code
is not a unique participant ID. In this batch those row checks passed, but
`cluster` represented communities, not households. Validate the substantive
variable dictionary too: `oldest` was the unique oldest child versus other
children; `son` was the unique oldest son versus other children.

## Faster changed models do not complete the requested model

The approximation fixed all three trajectories to linear loadings, removed
the known-class measurement/structural model and same-wave residual structure,
and omitted several original structural adjustments. Its second-stage outcome
was itself an estimated score. These are scientific changes, not a speedup of
an equivalent `SX XWITH IZ` fit. Keep them out of the original hypothesis
completion count.

Community-robust second-stage SEs and Rubin pooling describe the conditional
score analysis; they do not propagate first-stage estimation uncertainty or
correct score measurement-error bias. The [Mplus factor-score note](https://www.statmodel.com/download/Factor%20scores.pdf)
also distinguishes regression scores used as predictors from scores used as
outcomes. Do not generalize its simple regression result to latent products.

A verified gate should stop downstream adoption on contradictory diagnostics,
input/output mismatch or an unapproved estimand substitution. Store a separate
disposition that supersedes weak legacy receipts. Preserve old results for
audit; do not rerun the entire batch to make the receipt green.
