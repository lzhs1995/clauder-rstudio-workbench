# Windows worker loading and supervisor recovery

Use this reference when an authorized batch is held before Mplus starts, or a
long-lived R session accumulates supervisor handles. Keep the original job and
statistical inputs bound throughout recovery. These are runtime procedures;
they do not establish numerical agreement or scientific adoption.

## Distinguish loading admission from model admission

A controller's pre-submit check, the newly started R worker's loading check,
and the model launch gate are separate consumers of memory. Record the effective
threshold at each stage, including thresholds embedded in launchers. An
unchanged model configuration hash does not prove that all resource policy is
unchanged. A documented configuration field may not be read by the launcher.

If a worker repeatedly fails or waits at loading, a longer timeout does not
repair the budget. Preserve each real terminal response, confirm whether any
model was dispatched, and close only that reconciled attempt. Measure the
same workload's R peak working set, worker-plus-child private allocation,
Windows available memory and commit headroom. Distinguish sampled maxima from
OS lifetime peaks, and do not add overlapping RSS figures as independent demand.

Build a revised loading budget from the system reserve, measured incremental
worker cost, model allocation and an explicit margin. Cross-check the whole
process tree and competing jobs. Document and version the changed outer policy
through the project's existing process; preserve the model gate when its
evidence still applies. Do not lower a gate simply until an attempt starts.
Load one additional worker at a time, verify its actual identity and fitting
stage, then assess the next worker from current host capacity. Emit progress
before package loading and subprocess checks so startup is observable.

In one archived APIM replay, two same-workload R lifetime peak working sets
were below 0.35 GiB, and sampled whole-tree private maxima were about 0.69 and
0.68 GiB. Two earlier attempts failed before model dispatch under a 2.15 GiB
loading gate; the second had already waited 30 minutes. The replacement used
a 1.85 GiB controller gate and a 1.75 GiB worker gate, with 3 GiB commit
headroom. Its physical budget combined a 1 GiB reserve, 0.35 GiB worker bound,
0.15 GiB model increment and 0.25 GiB margin. The first resumed lane actually
entered Mplus under the unchanged model driver and input hashes.

These figures explain that particular decision; they are not defaults for
other machines or models. A startup success does not prove that the reserve
will hold throughout a batch, or establish a speedup. Continue observing the
same job and retain the original whole-host model admission gate.

## Recycle an owned supervisor only after a version-specific test

Handle growth is distinct from large R objects, private commit and resident
memory. In a tested processx 3.8.6 installation, an owned supervisor accumulated
over one million handles. Replacing it reduced the new supervisor's observed
count to a few thousand while the same R session and active jobs survived.
This released accumulated handles; the installed binary was unchanged, so it
was not a permanent leak fix or a demonstrated Mplus speed improvement.

Inspect the installed supervisor implementation before considering recovery.
The tested `supervisor_reset()` sent kill commands to supervised children;
calling it on the live instance would defeat preservation of active models.
An internal “running” flag was not an OS liveness check, and an already-true
process supervision flag did not prove registration with a replacement.

First test the exact package and binary in an isolated R process: verify that
terminating only its test supervisor leaves the test child alive, then start
a new supervisor, register both the surviving and a new test child, and verify
normal supervision. Preserve binary hashes, process identities and cleanup
results. A test of another installation does not authorize the live procedure.

For an already-authorized live recovery, freeze the owning R identity, job IDs
and every owned direct child. Stop only the proven supervisor; verify its OS
exit before closing old pipe connections or clearing its runtime state. Start
the original supervisor implementation, explicitly register the preserved
children, and verify their identities, active jobs and the other R sessions.
Keep the installed package untouched. This is a project-specific recovery,
not a generic cleanup command to run on startup or on another session.

## Bound only the read-only identity retry

A short bridge health probe can report the addin unavailable before dispatching
a read-only identity command. A bounded retry may target that exact command
and recognized transient response. Save each response, require the expected
session PID, and return other errors immediately. Test that async submission,
other R code and genuine R errors are never retried, and that the retry limit
is enforced. This keeps a recovered identity check distinct from a new job.

An ambiguous async response still requires registry and durable-artifact
reconciliation before any resubmission. If an earlier client failed, keep its
logs and prove the stage it reached rather than equating client exit with no
dispatch. Save the original terminal response immediately; large responses
belong in files, since passing them as Windows command-line arguments can
exceed the command-line limit.
