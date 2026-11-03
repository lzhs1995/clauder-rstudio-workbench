# Count engine attempts even when export fails

An engine can start and finish without a usable export. For example, the
supervisor can reject a changed input, fail to confirm exit, or lose the R
wrapper response. Counting only exported members understates the cost of a
later plan. A successful estimate, an exported result and an engine call are
separate facts.

Use [engine_attempt_accounting.py](../scripts/engine_attempt_accounting.py) to
inspect the original member work directory, its RStudio adapter `guard` and
`guard_export` directories, and its result export. Preserve the small original
claim/start/receipt files with their hashes. Copies of one receipt count once.
Check every planned member before admitting another engine, including members
later in the plan when an earlier output fails validation.

Confirmed, consistent exit receipts provide exact recorded calls and elapsed
time even when no output was exported. A known start with unknown exit keeps
the call but reports elapsed time as unknown. A claim alone does not prove a
start; reserve one call and the original cap while retaining that uncertainty.
The reservation is **not an elapsed-time upper bound**: an unsupervised process
may have outlived its cap. Never relabel it as measured time.

`totals()` exposes exact values only when known, plus confirmed costs, observed
elapsed time and reservations. `followup_budget_eligible=false` prevents using
an unresolved record to finance another batch. A follow-up planner calls
`require_closed_budget()` before adding previous totals. This function checks
numeric completeness; it cannot retrospectively prove that a legacy result
counted every call. Bind legacy totals to their independently inspected
receipts.

The collector neither starts nor stops an engine, adopts an orphan output,
changes a cap, or accepts statistical results. Recovery still reconciles the
original process, inputs and output set. Do not run a claimed member again.

For a two-stage GH7 → GH15 member, reserve both remaining calls and both caps
before starting GH7. Check STOP before generating a new refinement input and
while waiting for resources. Use explicit exceptions for runtime gates:
Python removes `assert` statements under `-O` or `PYTHONOPTIMIZE`. Per-member
validation failures must produce a durable HOLD result with the cost ledger.

Parameter-identity regression tests should include a three-cycle permutation
of estimates, standard errors and both covariance axes. A two-element swap is
its own inverse and cannot detect a reversed permutation direction. Include
an off-diagonal covariance-only change as a rejection case.

These rules apply to both Windows-local and Mac-remote agents using the same
RStudio/MplusAutomation workflow. They do not change the scientific model or
justify pooling an incomplete set of imputations.

## Use the latest closed predecessor as the cumulative baseline

When several family checks and recoveries have run, a previously saved
calibration total can be stale even though that file is valid. For a new
successor, verify the latest predecessor's plan and raw attempt receipts,
then use `predecessor.prior_cost + predecessor.actual_new_cost`. Do not add
only its new cost to an older calibration snapshot: that can omit an
intervening recovery. Conversely, do not add costs already included in the
predecessor's prior total a second time. Record the source plan/result hashes
and the shared history scope, which may be narrower than the whole project.

The successor's new-call and engine-time allowances still come from its own
original family allowance minus that family's consumed attempts. Historical
costs, remaining allowances and the original absolute deadline are distinct.
System-sleep wall time remains in the original receipt; it is not an automatic
credit. A successful same-input resource check proves only that checked stage,
not that all later imputations will fit within the cap.
