# CFPS deferred recovery queue

Use this reference when a historical manuscript ledger contains cells with an
input, an attempted model, or a table value but no acceptable terminal output.
The queue is an explicit exclusion from the completed-estimate set. It is not
a request to rerun every missing or failed model.

## Freeze the boundary first

Read the isolated queue receipt:

`reports/cfps_deferred_recovery_queue_20261004/cfps_deferred_recovery_queue_v1.json`

The 2026-10-04 CFPS packet contains 669 deferred cells:

| category | cells | meaning |
| --- | ---: | --- |
| `UPSTREAM_DEPENDENCY_BLOCKED` | 381 | a consumer cannot be accepted before its producer/data dependency is accepted |
| `HISTORICAL_SIDECAR_NOT_RECOVERABLE` | 165 | the old sidecar does not support a unique producer; numeric similarity is insufficient |
| `HISTORICAL_ESTIMATION_FAILED` | 116 | the historical attempt did not provide an acceptable terminal estimate |
| `NOT_PREPARED` | 7 | the manuscript row exists, but a reproducible input/specification contract is not prepared |

Keep all four categories visible in the manuscript audit. Do not silently
turn them into success, failure, or a new estimate. A normal `.out` already
validated in another namespace is reusable; an unresolved author adoption
decision alone is not a reason to rerun it.

The accompanying Windows read-only lineage audit found all 51 unique `.out`
names under the recorded result root, and all 669 deferred rows had a lineage
script, source line, block ID, output name, deferred category and next action.
This closes a file-location/source-traceability question; it does not close
the dependency, sidecar, estimator or scientific-adoption gates.
The reproducible project-side entry point is
`work/cfps_deferred_lineage_reference_audit_20261004.py`.

## Reopening a deferred cell

Reopen a cell only when all of the following are recorded in a new isolated
namespace:

1. the exact data and input/specification hashes;
2. the dependency graph and producer identity;
3. the intended estimator, starts, integration, missing-data and pooling
   contract;
4. a Windows memory/time admission decision; and
5. a terminal-output contract containing the `.out`, ending time, Mplus version,
   MplusAutomation readback, and parent-process chain.

For dependency-blocked consumers, accept the producer before submitting the
consumer. For failed or unprepared history, record why the historical output
cannot be used before considering a new study estimate. If the objective is
only to reproduce the draft, retain the historical limitation and continue
with already validated outputs.

## Evidence boundary

The queue receipt is an audit artifact, not a scientific release. It records
`new_mplus_submissions=0`, `source_mutations=0`, and
`manuscript_mutations=0`. CFPS scientific release, downstream CHARLS formal
adoption, exact-final-PDF NLM review, and guide release remain separate gates.
