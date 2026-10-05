---
name: mplusautomation-guide
description: Use when running reproducible Mplus 9 models from R through MplusAutomation and ClaudeR, including isolated Windows/macOS paths, asynchronous fan-out, resource gates, recovery, and manuscript-level validation.
---

# MplusAutomation Guide (draft until manuscript reconciliation)

Use this skill to run Mplus 9 from R with durable inputs, outputs, checkpoints,
and validation evidence. It complements `clauder-rstudio-workbench`; it does
not replace the statistical model specification or the manuscript source of
truth.

## Required workflow

1. Read the workbench connection and async-job guidance first.
2. Create a new, isolated run root. Copy scripts and required data into it;
   never overwrite source scripts, historical outputs, or the manuscript.
3. Record platform-neutral paths in a manifest. Resolve Windows paths with
   `normalizePath()` and macOS paths with `path.expand()`; do not hard-code
   another machine's home directory in a reusable skill.
4. Check R, MplusAutomation, Mplus 9, and the Mplus executable before model
   generation. Save `sessionInfo()`, package versions, executable metadata,
   input hashes, and a manifest.
5. Generate one `.inp` per model and run it with an explicit command:

   ```r
   MplusAutomation::runModels(
     target = model_dir,
     Mplus_command = mplus_exe,
     killOnFail = FALSE,
     recursive = FALSE,
     showOutput = FALSE
   )
   ```

6. For independent models, submit separate ClaudeR async jobs and poll the
   original job IDs. Each worker must write a state file, log, output hash,
   and validation record. Do not resubmit a job because it is still `running`.
7. Set concurrency from live memory, CPU, disk, and observed Mplus RSS. Start
   with one worker; activate another only after five consecutive healthy
   samples. Stop scaling when memory or disk gates fail.
8. On interruption, snapshot the queue and evidence, identify live PIDs, move
   only confirmed-dead `running` tasks back to `pending`, and verify input
   hashes before resuming. Keep old queue and evidence files as immutable
   recovery artifacts.
9. Validate every output independently: estimation completion, warnings,
   SAVEDATA files, expected parameters, input/output hashes, and dependency
   fingerprints. A completed queue row alone is insufficient.
10. Reconcile model-level results to each manuscript table and Appendix row.
    Record expected rows, available estimates, discrepancies, and unresolved
    failures. Only after this reconciliation may this guide be marked final.

## Evidence contract

Keep a durable run directory containing `manifest.csv`, `session_info.txt`,
`queue.sqlite`, worker logs, checkpoints, `output_audit.json`, and a table
reconciliation file. Use atomic JSON replacement and append-only error logs.
Treat `PASS`, `REVIEW`, and `FAIL` as separate states; warnings requiring
scientific review must not be silently converted to success.

## Platform boundary

The R/MplusAutomation code is portable. Platform-specific adapters are limited
to executable discovery, path separators/quoting, process inspection, file
locking behavior, and launching the ClaudeR addin. Keep those adapters behind
one configuration layer and test both Windows and macOS path identities.

## Current project note

This file is a draft scaffold. Do not mark it final or publish result mappings
until the active reproduction's four scripts, all Mplus outputs, and manuscript
tables have passed the reconciliation gate.

See [parallel-models.md](references/parallel-models.md),
[recovery.md](references/recovery.md), and
[validation.md](references/validation.md),
[cfps-full-docx-provenance.md](references/cfps-full-docx-provenance.md),
[manuscript-missingness-contracts.md](references/manuscript-missingness-contracts.md),
[cfps-table455-row12-semantic-labels.md](references/cfps-table455-row12-semantic-labels.md),
[charls-reuse-first-gate.md](references/charls-reuse-first-gate.md),
[execution-vs-acceptance.md](references/execution-vs-acceptance.md),
[deferred-output-triage.md](references/deferred-output-triage.md).
