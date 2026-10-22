# CHARLS gender × education full MI: native recovery and adoption boundary

This reference records the 2026-10-22 Windows run of one CHARLS H4.2 branch: sons-minus-daughters contact (`gender`) moderated by baseline education (`C3`) in a three-process latent growth model with `SX XWITH IZ`. It is a reproducibility record, not evidence that the four CFPS moderation families or the complete H4 are finished.

## Frozen estimand and evidence

The run used an isolated directory and the original latent `gender` parent syntax. The pilot had already passed five native Mplus calls (parent equivalence, two quadrature levels, two start refinements). The full batch then used the pilot-passed 15-point A start for all 20 working-MI members and one MI01 B start sensitivity. It did not rerun the failed CFPS specifications.

The working MI was admitted only after all 20 members had N=2085, 14 ADL imputations, the original observed X/Y/Z values and missingness masks unchanged, all 50 required product and product-missingness auxiliaries retained, and a full-rank conditional design. This is a conditional working MI with observed product auxiliaries; it is not a proof of MAR or exact latent congeniality. Pool only when every A member has a normal Mplus termination, complete TECH/estimates readback, positive robust covariance geometry, and a usable receipt. A B start is a sensitivity check for the same MI member and never substitutes for a missing A member.

The completed batch used one Mplus process at a time because the Windows admission contract reserved physical RAM and commit headroom. It produced 20 pooled A members plus one B sensitivity (21 real Mplus calls). Independent Python readback reconstructed 2,814 parameters, all 21 research contrasts, full robust covariance transforms, and Rubin pooling. The primary group difference `SY:SXIZ` was -0.0148 (95% interval about -0.238 to 0.208; p about .897), so the run provides a valid non-significant result rather than a reason to change the model or search for a significant specification.

## RStudio/ClaudeR recovery sequence

1. Bind the native RStudio session by PID and creation time. In this run the default session was the RStudio process at port 8787; the actual async worker was a child of that session. Preserve the original job ID and use the same `get_async_result` handle.
2. Run `async-guard pre-submit`, submit exactly once with native `execute_r_async`, immediately register the returned job ID, and save the terminal response. A stale or missing response is not permission to resubmit.
3. Keep Windows paths inside code and contracts in native form (`C:/Users/...`). WSL `/mnt/c/...` paths can be read by WSL tools but are interpreted as `\mnt\c\...` by Windows Python. In this run that mistake stopped the worker before Mplus; no engine call was claimed. Preserve the boot stderr, cancel/archive that attempt, convert the contract paths, and submit a new, explicitly named retry.
4. Separate engine execution from readback. The first real MI01 A Mplus call exited normally and wrote `model.out`, `estimates.dat`, and `tech3.dat`, but the new readback compiler omitted the required `parent` field in `job.json`. The resulting `KeyError('parent')` was a readback failure, not a model failure. Add the metadata, archive the failed receipts and partial readback artifacts, rerun only the readback, and verify that the input/data hashes and output hash are unchanged.
5. A resume runner should detect an existing `engine_receipt.json` with a verified `USABLE` receipt and reuse it. It should compile and run only members without a valid engine receipt; it must never overwrite a historical or completed output merely because a supervisor died. The resumed batch above reused MI01 A and estimated MI02--MI20 A plus MI01 B.
6. Close the guard only after the terminal JSON, independent verification, and wake-guard release are present. Record the failed startup/readback attempts as diagnostics; do not collapse them into a false “all calls succeeded” history.

## Practical implementation rules

- Use the pinned Windows interpreter `C:/Users/<user>/AppData/Local/Programs/Python/Python314/python.exe` for Windows-side helpers. Use WSL Python only for file preparation and reporting; never place WSL paths into a Windows process contract.
- Keep `replaceOutfile='never'`, a per-model directory, immutable input/data hashes, and a separate `execution/` stdout/stderr receipt. A normal Mplus exit is necessary but not sufficient: inspect the output for error summaries, non-positive-definite structures, missing standard errors, and complete TECH files.
- Treat `READBACK_FAILED`, `INADMISSIBLE`, `NOT_RUN_RESOURCE_HOLD`, and `USABLE` as different states. Do not pool a member because `model.out` exists.
- Run independent transform/Rubin verification after the R script writes pooled tables. Verify parameter keys, the 134-by-134 transform, robust covariance, positive geometry, cluster degrees of freedom, every research contrast, and the B-start diagnostic.
- Keep the scientific status explicit in every receipt: `original_CFPS_four_complete=false` and `full_H4_complete=false` for this branch.

## What this run does not establish

A complete working MI family for one CHARLS indicator/resource pair does not complete the four CFPS moderation families, does not establish exact latent MI congeniality, and does not turn a non-significant interaction into support for H4. Report the interval and the analysis contract; do not tune starts, scales, cut points, or covariates to seek significance.
