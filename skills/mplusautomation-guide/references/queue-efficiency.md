# One family queue, one observer, unchanged scientific drivers

Both a Windows-local agent and a Mac agent can source
`scripts/run_rstudio_family_queue.R` inside the intended Windows
RStudio/ClaudeR session. The queue calls the existing
`run_rstudio_mplus_batch.R`; MplusAutomation remains the actual R caller.
Do not substitute a Python/executable launch to satisfy this route.

Keep one stable family root and a reviewed `QUEUE.json` with family ordering,
immutable candidate hashes, budgets, dependencies and READY/HOLD dispositions.
`rstudio_queue_admission.py` verifies candidate/driver identities, observes
Windows resources and reuses the established engine-attempt reader. It checks
attempts without exports too. Unknown exits or costs prevent new admission.
Each closed predecessor source is added once; the frozen input plan is kept,
and a small admitted plan/config is written beside the existing helpers.
No scientific scripts are copied for a new status update.

Completed attempts and scientific acceptance remain separate. A held family
may be explicitly excluded from dispatch while an independent ready family
continues, once the held family's costs are closed. A queue entry is not an
authorization to rerun a timed-out model, alter starts, or accept partial MI.
Full-family pooling and manuscript adoption still require their original gates.

The R queue uses a permanent run claim and append-only `EVENTS.jsonl` with one
writer. It forwards stage/message updates to ClaudeR. A second invocation of
the same queue state is refused; it does not reset or silently resume a prior
run. Reconcile original processes and receipts after a crash, then prepare only
the missing work in the same family root. Do not claim power-loss exactly-once.

Resource waiting before a new family can be bounded at 15–30 minutes without
consuming engine seconds. This setting does not automatically change the
already frozen member runner's resource timeout. A longer member wait needs a
reviewed scheduling change and checks against the original absolute coordinator
deadline; never renew deadlines by reconnecting. The per-engine cap, estimator,
integration, seeds and complete-MI acceptance remain unchanged. Do not
periodically flush WSL caches: shared jobs may pay additional disk I/O. Observe
the actual Windows headroom and use only owned or explicitly authorized remedies.

Use one background observer for the queue, normally every 180 seconds; sample
more closely only for a real diagnostic need. Preserve original request/job IDs
after timeout. Append a small event referencing xdev's existing raw evidence
instead of keeping repeated stdout/stderr copies in four new files per poll.
Read the same terminal receipt once and stop the observer at that boundary.

Append-only progress avoids frequent snapshot replacement but cannot eliminate
all Windows sharing errors, disk-full failures or truncated crash tails. Keep
submission claims, engine costs and terminal results durable and separate from
observational progress; failed accounting writes must still stop new engines.
Do not rewrite already frozen worker files merely to standardize their logs.

New xdev ClaudeR status replies are bounded to 64 KiB on Windows; oversized
originals stay there with a SHA/path/size/line-count reference and explicit
output omission. Keep success/failure and job status distinct. File collection
is a separate, explicitly bounded operation; transport does not filter inputs.

Keep the active HANDOFF within 30 lines and history in a separate file. Resume
from the current handoff, queue event and the exact missing evidence, not the
entire session. Run targeted tests for changes to dispatch, cost accounting and
Windows I/O; do not repeat passing suites or reinstall skills after every
documentation edit. Make one reviewed skill update after the working change.

Validation of this queue layer included five cost/admission tests on both Mac
and Windows, plus a real Windows RStudio control check that wrote three ordered
events and refused a duplicate queue claim with zero Mplus calls. The xdev wire
limit separately passed five native Windows cases, including UTF-8, failure,
unknown outcome and identical cached replies. These are control checks, not
proof that every queued scientific family completed.

## Start an approved batch promptly when its window opens

Prepare and approve the exact `PLAN`, scientific R driver, input hashes,
RStudio owner binding, closed prior costs and remaining budget before waiting
for a shared compute window. Freeze the submission script and its original
request/job IDs. The grant must bind those same identities and limits; a ready
script is not itself a window grant or proof of current resource headroom.

Use one lightweight local observer to check the task's grant file, for example
every two seconds, without a remote status request on every check or another
agent reasoning round trip. This short interval is for window admission; keep
the running-model observer at its existing bounded cadence. Verify the grant's
issuer, source hashes, matching budget, expiry and other active windows. Persist
an exclusive submission claim before invoking the existing submit entry once.
Recheck the grant and pinned sources immediately before submission. If a crash
leaves a claim without a queue receipt, retain UNKNOWN and reconcile it; do not
delete the claim or assign a new ID to try again.

Queue acceptance may precede R execution. In the Windows R worker, check the
grant's latest-start time again before evaluating the byte-hashed original
submission script. Expiry blocks a late start; it does not extend or replace
the original engine cap or absolute deadline. The scientific driver still
checks live ancestry, resources, attempt identity and budget. This time check
does not guarantee detection of a revocation issued after enqueueing; retain
the original task's explicit stop and confirmed-exit procedure.

For a missing or delayed submit response, reconcile only the original request
and job. Match the returned request, payload and RStudio identity, then require
the original job ID and `success=true`; an HTTP/CLI return code alone is not
acceptance. A successful submit body need not contain a separate `status` key.
Stop the admission observer after confirmed acceptance and hand the same job
to the existing terminal observer. Submission, engine startup and scientific
acceptance remain separate evidence. A Windows-local agent and a Mac agent
controlling Windows use the [same scientific R driver and acceptance rules](rstudio-two-entry-workflow.md).

One actual batch on 2026-11-08 recorded one submission intent: grant to durable
claim was 0.599 seconds, grant to original HTTP acceptance 4.933 seconds, and
grant to Mplus process birth 39.791 seconds. These are cumulative intervals
from the same grant, not three additive phase durations. The evidence includes
the frozen grant, claim, original HTTP receipt and live engine process record.
This single-batch observation is not a controlled benchmark, a general latency
guarantee or evidence of model convergence; scientific acceptance was pending
when the startup receipt was recorded.

## Separate batch throughput from calibration time

The 2026-11-04 M1 continuation completed 19 new imputations in one Windows
RStudio/ClaudeR async R worker, reusing accepted MI01. The observed Taipei
16:50:48–17:14:11 batch window was 1,403 seconds; confirmed Mplus elapsed time
was 1,273.1365357 seconds, or 90.74%. Its preceding five-call pilot used
204.6378507 engine seconds between the first claim at 16:00:43 and the final
numerical comparison at 16:47:20.912: 2,797.912 seconds, or 7.31%. Neither
ratio is CPU utilization, a Mac-versus-Windows speedup or whole-day efficiency.

The pilot intervals include retrieval, independent readback, start/input
preparation and staged calibration admission; the evidence does not isolate
pure network delay. Batch completion to the final pooling audit took another
916.979 seconds. Report these windows separately. Prepare reusable inputs and
readback work while an earlier point runs, retain the required numerical gates,
then dispatch an admitted full-MI batch once rather than making each MI a
cross-device round trip. The associated scientific checks are documented in
[latent-product-full-mi.md](latent-product-full-mi.md).

## Recover a resource-held prefix

For the PP-LGCM income GH7/GH15 adapter,
[recover_rstudio_mi_prefix.py](../scripts/recover_rstudio_mi_prefix.py) checks a
`HOLD_NO_EXPORT` result whose next stage was never started. It verifies the
complete saved file sets, original R producer, parameter identities, covariance,
quadrature agreement and all engine claims before preparing a new attempt under
the existing family root. A prefix may end at GH7: retain that fit and continue
with its own GH15 stage. A timed-out engine is not an unstarted stage.

Unchanged code is linked within the same Windows volume; inputs and originals
remain in their existing paths. Only the changed coordinator, plan, config and
audit are new. Source helpers are immutable: replace a changed file rather than
editing a shared hard link. This is a study-specific recovery adapter that
requires the study's independently validated reader, not a general MI compiler.

The resource-held oldest prefix passed nine stage checks and retained seven
calls / 837.1107531 seconds. Its remaining 71-call allowance and original absolute
deadline were preserved. The scheduling change permits at most 1,800 seconds of
member resource waiting; the coordinator rechecks its original deadline and
reserves a full per-engine cap before admission. Five targeted checks passed on
Windows. Mac ran the four scheduling checks; the reader contract check was
deferred to the existing Windows scientific environment. Preparation and queue
receipt do not establish that the remaining estimations ran.

Observed engine RSS maxima were about 70.6 MiB for gender and 74.1 MiB for the
saved oldest prefix. They exclude R, Python, operating-system and WSL pressure;
do not use engine RSS alone to derive a host admission floor. The queue checks
Windows result-volume space before admitting a family (currently 1 GiB),
independently of the Mac result-return floor. Pagefile allocation, pagefile use
and volume free space are separate observations; a shrinking volume without an
allocation change cannot be attributed to pagefile growth from those two samples.

A shared control queue must remain responsive. A 300-second recursive disk
scan occupied it until timeout and delayed a ready recovery receipt by about
280 seconds. Use bounded status reads in synchronous commands and detach any
long scan. A delayed control receipt does not imply that the already detached
Windows work stopped, and never justifies submitting that work again.

## Continue independent families without a coordinator round trip

After a closed predecessor, a single ClaudeR async R worker can prepare and
run successive approved families locally, sourcing the same scientific R
driver each time. Persist a run claim, family order, pinned preparation code,
per-family input/config hashes, append-only events and the original absolute
deadline. Preparation itself makes no Mplus calls. A blocked dependent stage
is not ready merely because another family is independent.

If an independent family returns HOLD, a successor may continue only after
the actual preceding attempt costs and exits are closed. Its preparation
inherits the latest cumulative ledger and keeps its own remaining allowance;
unknown costs stop admission. Preserve every failed stage, never repeat an
already submitted family merely to advance the queue, and never pool partial
MI. Poll one queue job at a modest interval, caching its terminal response.

The observed post-sleep continuation added a 5 GiB Windows result-volume
floor checked before every new member. This is a host-specific contract, not
a universal Mplus requirement. It is separate from the Mac return-capacity
floor. Available memory, commit headroom, disk and the original deadline
still apply even when a single Mplus process has small RSS.

## A successful member followed by a preparation failure

Give every effective execution contract a distinct member-and-attempt path.
Two templates in one directory must not both resolve to the same
`EFFECTIVE_EXECUTION_CONTRACT.json`. An exclusive-write rejection protects
the first member's evidence; removing that protection or replacing the file
is not a recovery. Check destination uniqueness before dispatching a pair.

In the SD MI39 check, A finished in 208.4248702 seconds, then B was blocked by
this path collision before it started. Its original R call, exact export
manifest, input identity and scientific checks were verified in place. Only
B received the remaining one-call, 240-second allowance, under the original
calibration deadline and through the same RStudio/MplusAutomation 1.3 route.
B finished in 196.1790694 seconds. Both starts agreed on all 140 parameters
and the full covariance matrix; the first fit was not estimated again.

Keep the two original R owners and their separately pinned receipts when
comparing or importing these results. Carry intervening closed family costs
into the successor ledger exactly once. A pair agreement can release its
declared remaining stages, but is not complete-MI pooling or proof that a
different imputation will finish within the cap. These rules are identical
for an agent on Windows and one controlling Windows from a Mac.

The SD successor reused 77 stages and ran only the three originally unstarted
stages, consuming 410.1106045 engine seconds. Its 40 primary imputations and
80 stages then passed complete-file/source verification and 354 independent
R/mitml checks. The calibration import audit retained the earlier producers;
that acceptance did not cover the separate son or CFPS calibrations.

## Completed income queue: 2026-11-03

The son continuation subsequently retained 21 verified stages and completed
the remaining 59 through the same Windows RStudio/ClaudeR/MplusAutomation 1.3
driver. All four income families (gender, oldest, SD and son) now have 40
primary imputations, 80 stages and independent R pooling acceptance. Each
full-family check covered 354 assertions. The 12-family CHARLS H4.2 resource
summary separately passed 148 checks; original CFPS moderation and full H4
are not established by that summary.

The final son segment used 6,703.5815702 engine seconds over 7,263.353105
seconds between its first and last stage boundaries: 92.29% engine wall-time
share. This includes local dispatch/readback overhead within those boundaries.
It excludes earlier tool development, calibration and failed attempts; it is
neither CPU utilization nor a controlled Mac-versus-Windows-local comparison.
Report those other costs separately instead of extrapolating this one segment
to the whole project. Results stayed on Windows while the Mac return-capacity
condition was unmet.

The CFPS MI01 calibration was later accepted independently; its bounded
quadrature/optimizer lesson is in
[native-worker-and-quadrature-recovery.md](native-worker-and-quadrature-recovery.md).
It does not authorize a new imputation family or erase prior failed costs.

The separately registered CFPS continuation later completed ten original
imputations and passed 189 independent R checks. Its ten additional Mplus calls
took 200.954147 seconds; the prior MI02 timeout and every earlier calibration
remain in the 39-call/4,010.247962-second ledger. Imputation-specific numerical
initialization is described in the same reference. Do not charge only engine
time when assessing total workflow efficiency, or interpret a successful
strong-constraint sensitivity as completion of the original unrestricted study.
