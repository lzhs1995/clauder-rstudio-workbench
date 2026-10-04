# Active resource recovery on Windows

When memory pressure prevents authorized estimates, diagnose and recover capacity
in the same work cycle. Do not repeatedly report a resource hold without taking
an available action. Resource management belongs to the estimation workflow.

Measure available physical RAM, committed/private allocation, process RSS and CPU
deltas separately. Large private allocation with tiny RSS often means paging;
ending that process does not free the same amount of physical RAM. Capture
timestamped before/after evidence, and quantify measured changes without claiming
causation from a noisy whole-host snapshot.

First release this task's no-longer-referenced R allocations with `gc()`. Remove
named objects only after verifying ownership and durable replacements; never
clear the shared `.GlobalEnv`. Prefer local scopes and per-model file caches.
Retire completed owned workers only after checking outputs and downstream needs.
Do not kill a coordinator that still owns pending renders.

Inspect unnecessary infrastructure next: duplicate idle connectors, monitor
scans, terminal repainting, and retained browser instances. Honor existing user
authorization to reclaim unnecessary processes; do not ask again for the same
action. A connector is a service, not the user's document application. Before
ending a specifically authorized restartable connector, verify exact executable
and script arguments, PID, creation time, parent chain, no task dependencies and
repeated CPU/I/O inactivity. A persistent connection alone is neither proof of
an active request nor proof of idleness. Skip changing or ambiguous identities.
Record any client reconnection consequence. Windows `terminate()` is forceful;
do not label it a graceful application exit.

Prefer cooperative stop signals for owned monitors. Preserve their singleton
lock and supervisor; change one collector to bounded, headless logging with a
lower sampling frequency when estimates are idle. Verify the new PID and a fresh
report after restart. Preserve the RStudio session and model processes.

Never use image-wide termination, indiscriminate working-set trimming, standby
cache clearing, or stopping WSL/Windows Terminal that hosts the current agent.
Working-set trimming can increase paging while leaving committed allocations
unchanged. Do not disable security services, change the pagefile, or close an
unsaved research application as an automatic memory optimization.

After recovery, sample admission again and start ready models immediately when
eligible. `scripts/resource_admission.py` writes an atomic, timestamped gate for
a **measured existing-RStudio incremental model budget**, with three CPU samples.
It is not permission to start a new worker or to apply a continuous-model budget
to GMM, integration or MI. The runner must reject stale gates and recheck free
memory before each estimate. `scripts/resource_gate.R` raises the typed
`mplus_resource_wait` condition if capacity drops between admission and launch.
The dispatcher must catch that condition and retain its retry callback. Ordinary
model, contract or data-integrity errors remain fatal and visible; do not blanket
retry every error. Rebind the verified foreground PID and isolated package library
after an RStudio restart; in-memory callbacks do not survive a session exit.
Do not loosen a threshold simply to get a pass.

If estimates still cannot start, continue input generation, provenance checks,
cached-output diagnostics and manuscript reconciliation. For autonomous retry,
use a single owned, bounded callback/dispatcher with durable stage and model ID,
explicit cancellation, failure evidence and no duplicate submissions. Report
`resource_wait` honestly; preparing input does not count as an estimated model.

Validation must include actual reclaimed identities, protected-session survival,
monitor heartbeat and an estimate or explicit current hold. Record acceptance
separately for resource recovery, model execution and manuscript conclusions.

On Windows hosts coordinated from WSL, pass
`--windows-profile <fresh-profile.json>` to `resource_admission.py` and set the
same path as `windows_memory_profile` for `mplus_queue.py`. The profile must be
regenerated before a claim and is rejected after five minutes by default. If it
cannot be read, the result is an explicit `host_memory_unverified` hold; falling
back to WSL's optimistic available-memory number would make the scheduler unsafe.
