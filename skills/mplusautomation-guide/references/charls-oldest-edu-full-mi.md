# CHARLS oldest × education full MI: path recovery and bounded H4.2 execution

This reference records the 2026-10-22 Windows run of a second CHARLS H4.2 branch: the unique oldest-child-minus-remaining contact contrast (`oldest`) moderated by baseline education (`C3`) in the latent `SX XWITH IZ` model.

## Contract and result

- Isolated root: `C:/Users/LZHS/pp_lgcm_review/charls_latent_h42_oldest_edu_full_20261022`.
- N=2397, communities=433, 20 A working-MI members plus one MI01 B start sensitivity.
- One Mplus process at a time; 21 real Mplus calls; all 20 A members had usable normal termination and complete readback.
- Independent verification reconstructed 2,814 parameters, 21 contrasts, the full robust covariance transform, and Rubin pooling.
- Primary `SY:SXIZ` education group difference: −0.107926, 95% CI [−0.378970, 0.163118], p=.435137; planned 12-test Bonferroni value=1.
- Scientific receipt must keep `original_CFPS_four_complete=false` and `full_H4_complete=false`. A complete CHARLS family is not complete four-family moderation or complete H4.

## Recovery sequence that matters

The first full-family submission stopped before the engine because a Windows contract contained WSL `/mnt/c/...` paths. Windows Python interpreted the path as `\\mnt\\c\\...`, so the bootstrap could not open the MI verification file and Mplus calls remained zero. Preserve that stderr and guard cancellation as a failed startup attempt. Convert every contract/source/MI path to native `C:/Users/...`, verify source and MI hashes, and submit a new task key; do not edit the old attempt into success.

Before retrying, perform a static scan for `/mnt/c`, stale N/community values, and the wrong indicator label. Then use the same native RStudio session and the same sequence:

1. `async-guard pre-submit` with a new retry key.
2. Native `execute_r_async(source(..., local=TRUE))` and immediate registration of the returned job id.
3. Read `runtime/PROGRESS.jsonl` for durable stages; MCP's generic `started` message may lag behind the durable file, so it is not evidence that the model is idle.
4. Poll the original job id. Never submit a second job because a progress response is stale.
5. Close the guard only after terminal status, independent verification, and wake-guard release are present.

This run also demonstrated the resource rule: serialized Mplus was fast and stable (about 1–2 minutes per member, 1,740.89 engine seconds total) with no concurrent Mplus processes. Do not open multiple engines merely because two RStudio sessions are available; use measured RAM/commit headroom and a separate contract.

## Readback and publication boundary

Mplus termination, readback, and scientific adoption are separate states. Require the exact input/data/output hashes, complete estimates and TECH3, positive covariance geometry, parameter-key uniqueness, Rubin matrices and all planned contrasts before pooling. Public packages should include outputs and evidence but exclude `data.dat`, MI_INPUTS/RDS/MIDS, AUXILIARY_INPUTS and individual records; a package that cannot rerun Mplus can still support transparent readback.
