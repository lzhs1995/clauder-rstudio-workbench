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
