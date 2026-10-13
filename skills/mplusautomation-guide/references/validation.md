# Completion Evidence

The October 2026 Windows closeout ran the repository unittest suite through
native Python: 282 cases, zero failures/errors, 15 explicit skips. Eleven
additional resource-admission/queue regression functions passed, and 71
links from the guide entrypoint resolved. These are software/documentation
checks, not additional Mplus estimates or licensed macOS validation. Test
invocations must use the repository working directory and its declared
dependencies; a missing `tomlkit` import is an environment error, not a model
failure. Raw results and scope boundaries belong in the project release.

Check the levels independently:

1. Transport: actual session identity and native sync/async/poll records.
2. Execution: new inputs/outputs, actual executable/version, logs and explicit
   terminal states for every requested invocation.
3. Estimation: termination, errors, finite coefficients/standard errors,
   identification warnings, variance problems and imputation counts.
4. Reproduction: specification/data identity followed by numeric comparison.
5. Presentation: tables/plots reopen and show reconciled values and path labels.

The helper's output validator is a conservative first gate, not a proof of
scientific assumptions or per-imputation convergence. `REVIEW` requires reading
warnings. Inspect estimator-specific Bayes, mixture and integration diagnostics
separately. Imputation-only producers require the separate saved-data checks
described in `replication.md`.

The queue's `completed` state currently follows `estimation_ok`; it does not
require `savedata_ok`. Report both fields and the full validation status. A
PP-LGCM run exposed many complete pooled estimates whose requested save files
were absent: the actual Mplus outputs said that a TYPE=IMPUTATION filename
without `*` was ignored, and some also rejected class-probability saving for
the specified model type. Preserve those diagnostics. Audit consumers requiring
the missing files before retrying an otherwise complete estimate. An audit of
already-generated dependencies cannot rule out a future source-script reader.

`deferred` is a separate queue result for an intentionally archived attempt.
It must publish `estimation_ok=false` and `savedata_ok=false`, retain the
partial-output evidence and reason, and block consumers that require the
estimate. A deferred record is never included in the completed-estimate
denominator when reconciling a manuscript table. The final report should show
completed, failed, deferred and reused counts separately.

Preserve those states through the manuscript-cell mapper as well as the queue
summary. A catch-all such as `state != completed -> estimation failed` silently
mislabels intentionally deferred models and consumers blocked by dependencies.
Record the queue state and reason beside the numeric verdict; only a completed
record with positive estimation validation may enter numeric comparison. Test
the mapper against deferred, blocked, pending/running with stale success files,
failed, validated completed and unknown states before the final audit runs.

Keep a post-estimation audit separate from the execution completion marker.
Trigger it only after all producers have finished and no task is pending or
running. Store model hash checks, numeric comparisons and unresolved mappings
in durable files; a successful audit process may still report numerical
differences and missing artifacts. Never use its exit code alone to finalize
the manuscript or the skill.

Text-fixture tests require R, jsonlite and digest. Licensed integration adds
MplusAutomation and Mplus. For a ClaudeR request, execute the synthetic template
with the actual async tool and retain the job ID. Do not infer Mac integration
from a mocked platform test or a Windows run.
