# PP-LGCM worked example: from model families to manuscript cells

This worked example records the execution design used for the four isolated
R branches `absolutive`, `relative`, `relative2` and `relative3`. It is a
project-specific example inside the general MplusAutomation guide. It does
not claim that the manuscript has been fully reproduced.

## Model graph from the manuscript

The manuscript tables define independent model families. A table row is not a
single Mplus run, and a script name is not a sufficient scheduling unit.

| manuscript family | independent dimensions used for planning |
| --- | --- |
| Table 4.2.1, LGCM model fit summary | Process-1 mean, Process-2 SD, Process-3 sex difference, Process-4 sibling difference, Process-4 sibling4 difference, Process-2 SD/Mean, Process-3 sex difference/Mean, Process-4 sibling difference/Mean, Process-4 sibling4 difference/Mean, Process-5 CESD-8; each may use linear, quadratic, piecewise or shape-factor growth |
| Table 4.3.1, direct effects | closeness trajectory scale (mean, SD/mean, gender difference/mean, sibling difference/mean, sibling4 difference/mean), with the specified trajectory form and outcome model |
| Table 4.4.2.1, SD-difference moderation | closeness mean trajectory, depressive trajectory and SD-difference moderation terms; each actual input is a separate dependency graph |

The planner therefore records `script`, `source_call_id`, model input
fingerprint, table tags, trajectory form, measurement scale, dependencies,
processor demand, memory reservation and historical output candidate. Claims
are made at the input/output level; a basename match alone is not an identity
match.

For the 20260214 PP-LGCM draft, the four Table 4.2.1/4.2.2 components have a
stronger source contract already verified on Windows: `relative.R` lines
3055–3322 generate the unstandardized fit table, 3324–3561 generate the
unstandardized parameter table, 6478–6745 generate the baseline-standardized
fit table, and 6747–6985 generate the baseline-standardized parameter table.
The corresponding crosswalk row counts are 280, 50, 280 and 50, with 40, 10,
40 and 10 output names respectively. The raw script SHA-256 is recorded in
`pp_lgcm_table42_provenance_v1.json`. Once these checks pass, do not re-estimate
these four historical producers merely because a later acceptance packet lost
their block identity; continue with cell-level adoption and limitations.

The Windows cell audit then reads the Word tables independently and parses the
historical `.out` files named by the script. In this example all 80 fit rows
(40 unstandardized and 40 baseline-standardized) matched at the manuscript's
display precision, and all 20 parameter rows (five estimate/SE/significance
cells in each of the two parameter tables) matched the unstandardized
`Means`, `Variances` and `WITH` sections. The appendix displays AIC/BIC to two
decimal places, so its comparison contract must use that precision. A plus
sign at `p < .10` is a significance marker, not part of the numeric estimate;
the parser must preserve it separately. Keep this audit as a hash-pinned
sidecar with counts and output statuses. It closes historical source/display
verification, but it does not silently choose a current corrected-data version.

## Execution order

1. Hash the original R scripts, input data, manuscript documents and
   historical `.inp`/`.out` inventory.
2. Generate or preserve each model in a private local namespace. Do not run
   the cloud-synchronised source directory as a working directory.
3. Validate a small Mplus 9 smoke model through the actual ClaudeR/RStudio
   native wrapper, then use a durable-file worker for formal estimates.
4. Admit historical-success candidates first. A hash-pinned candidate
   manifest is a scheduling filter only: a fresh estimate still needs its own
   input/data hashes and terminal validation. No-history Bayes/LMS, failed,
   nonconverged or overlong branches go to the explicit `deferred` lane after
   identity-verified archiving.
5. Submit only independent ready nodes. Keep one worker until private-memory,
   CPU, disk and monitor responsiveness have several healthy samples; raising
   the worker count simply because the table has many rows is unsafe.
6. Read each output with MplusAutomation diagnostics. Store the `.out`,
   execution log, `validation.json`, `model_status.json`, input manifest and
   saved-data checks together.
7. After producers and model attempts finish, compare estimates, standard
   errors, fit measures, imputation scope and displayed path labels against
   the corresponding manuscript cells. Only then render or finalize a table.

## What the Windows run established

- Native ClaudeR/RStudio async jobs can keep a coordinator and one durable
  worker alive while the supervisor remains event-driven.
- Mplus child ownership must be proven by worker PID and creation time,
  executable, working directory, input filename and parent chain. A queue
  `running` row is not evidence that Mplus is alive.
- `completed` means `estimation_ok` under this queue. `savedata_ok` is reported
  separately because Mplus can finish estimation while rejecting a requested
  TYPE=IMPUTATION SAVEDATA filename. `deferred` is neither success nor an
  estimation failure and blocks consumers that require the artifact.
- The resource gate uses processor, memory, CPU, disk and Bayes class limits.
  Observed private-memory credit is applied only after exact process identity
  checks. A disk hold can wake the same worker when space is restored; it does
  not justify a duplicate worker.
- A user logoff can terminate RStudio, Mplus, workers and a session monitor
  without a reboot. The recovery sequence is native SQLite backup, process
  identity review, orphan archive and hash check, checkpoint validation, a
  native smoke, then one new coordinator/worker. Old async IDs belong to the
  old RStudio session.

## Acceptance boundary

The project-specific queue and guide fixtures validate execution mechanics,
but they do not certify manuscript equivalence. The guide remains `draft`
until the four script branches, all requested table cells, failed/deferred
models and numerical comparisons are reconciled. Do not report a table as
replicated merely because an `.out` exists or an Mplus process terminated.

When an artifact inventory reports `contains_error`, inspect the actual output
before scheduling a rerun. A comment such as `residual error terms` is not an
Mplus failure. Preserve both the inventory status and a narrow terminal audit;
complete `MODEL RESULTS` plus `Ending Time` without `*** ERROR`/`*** FATAL` is
evidence for an output-complete candidate, while the missing explicit Mplus
termination banner must remain visible as a limitation until the manuscript
cell itself is reconciled.

For three-way moderation tables, value matching is only the first pass. Read
the Word X/W/Z labels and compare them with the exact `xw_int`, `xz_int` and
`xwz_int` expressions in the chosen R block. In the CFPS worked audit, 67
derived cells produced value consensuses for 16 of 17 producer groups after
correcting opposite `i_mod_s`/`s_mod_i` basename assignments, but only five
groups also passed the latent-factor semantic check. Keep a semantic mismatch open as a
provenance problem; do not resolve it by choosing whichever `.out` has the
same rounded number.
