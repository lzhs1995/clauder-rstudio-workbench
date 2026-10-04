# Diagnose slow runs before changing estimation

Capture a timestamped report with the Python runtime on the machine that owns
R and Mplus (Windows Python when controlling Windows from WSL):

```text
python queue_diagnostics.py --root <isolated-run> --namespace <current-prefix> --output <new-evidence.json>
```

The helper opens SQLite read-only, checks registered worker PID plus creation
time, enumerates their Mplus children, separates dependency and resource holds,
and summarizes terminal attempt durations. It never claims, requeues or kills
a job. Capture CPU counters again later to assess activity. Inspect queue and
worker evidence before calling anything stalled; `.out` may remain buffered
while a Bayesian model continues consuming CPU.

When the host is busy despite a small local queue, add `--host-processes`.
This inventories all Mplus processes, grouping them by verified worker identity
(PID plus creation time), reporting private memory and missing parent processes.
Inspect recorded working directories before assigning ownership. A process
outside the registered tree may still belong to an interrupted worker from the
same run. A missing parent alone is not permission to terminate it. Do not use
an image-wide kill command on a shared machine.

Process ownership requires the exact executable, PID, creation time, parent
chain and working-directory/input path. Exclude the diagnostic command itself
from matches: searching a command line for `monitor_parallel.py` can make the
probe report its own process as a duplicate monitor. `Rscript.exe` and
`Rterm.exe` are different worker identities on Windows; do not infer that a
worker is missing from an `Rterm.exe`-only search.

## Sleep and host-wide pressure

Record wall time and cumulative CPU time separately. Laptop standby/hibernation
can leave the same process IDs alive while elapsed wall time increases by hours.
Check OS sleep/resume events before attributing that interval to estimation.
CPU deltas establish activity; only model diagnostics establish convergence.
A buffered `.out` does not establish either success or a stall.

Audit other runs and Mplus child processes when local RSS is small but system
commit is high. In one Windows recovery snapshot, the active model used about
117 MiB private memory while 18 Mplus children outside its worker tree retained
about 14.5 GiB after their parent processes exited. Sleep/hibernate events were
also recorded. Raising this run's worker count would not resolve those causes.
These figures describe a snapshot, not a universal memory requirement or a
performance benchmark.

Keep cancelled, idle worker registrations distinct from live workers. Verify
PID and creation time and check task ownership under the same queue transaction
before retiring a registration; preserve cancellation evidence. Reading a live
Windows SQLite/WAL database with WSL's Linux sqlite library may fail with an
I/O/locking error: use native Windows Python or a native SQLite backup instead.
Do not delete the WAL to work around a diagnostic read error.

## Distinguish four costs

1. **Estimation cost.** Inspect the actual uncommented ANALYSIS block. Fixed
   iterations, random effects, integration, imputations and chains determine
   work. `FBITERATIONS` specifies fixed iterations per MCMC chain; it is not
   the convergence-based maximum/minimum `BITERATIONS` setting. Do not silently
   reduce it or split a pooled imputation analysis to obtain a faster result.
   See the [Mplus ANALYSIS reference](https://www.statmodel.com/HTML_UG/chapter16V8.htm).
2. **Scheduling cost.** A ready task is different from an admissible one.
   With a processor budget of 12, two running tasks declaring 3 each exclude
   a task declaring 10 even if RAM is available. A configured concurrency cap
   does not start workers; verify real registered live workers. Keep a slot
   available for ready work that advances the next preparation/table step.
3. **Preparation cost.** Record bytes and time for checkpoint load/save. On a
   dependency wait, persist the exact expected validation path in small state
   JSON. Poll that file without loading the R environment; wake on success OR
   failure. Save large checkpoints after actual statement/model progress,
   never merely because an unchanged wait was polled. Keep package attachment,
   RNG state, source position and stable model IDs in the durable checkpoint.
4. **Interruption cost.** R checkpoints do not normally contain Mplus's active
   estimation state. Archive partial outputs before retrying; do not describe
   restarting a 12-hour model as continuing from its final iteration. Report
   observed lost attempt time separately from completed-model timing.

## Scheduling controls

An optional `dispatch_priority` overrides a task's original `priority` without
changing its `.inp`. Optional `execution_class` plus
`resource_policy.max_running_by_class` can reserve capacity, for example one
Bayes model at a time. Lower priority values run first; dependency, CPU, memory,
disk and ownership gates remain mandatory. These are workload choices, not
universal operating-system requirements. For a finite reproduction batch,
run ready prerequisite/short models first and retain all expensive models in
the manifest; do not turn prioritization into silent exclusion.

After recovery, resolve each coordinator checkpoint's exact `waiting_for`
validation path to its queued producer. Elevate ready producers that unblock
script preparation before unrelated estimates of the same class. Record old
and new dispatch priorities in a transaction and retain the input hashes.
Do not preempt active estimates merely to apply the ordering. Reassess this
list when the preparation frontier changes; one initial priority list is not
a complete dependency-aware scheduler.

The queue can refresh that ordering on every claim. Configure
`producer_state_files` in the run's `config.json` as a list of paths relative
to the run root (for example `runs/analysis_a/state.json`). A producer publishes
`stage=dependency_wait` or `stage=compound_model_wait` and an absolute
`waiting_for` path to the expected validation file. Its directory must contain
the matching `request.json`. The queue checks the task ID, fingerprint and
output directory, then prioritizes that pending task and its pending upstream
dependencies or reuse source. Completed records, malformed state and paths
outside the run root cannot acquire priority. Resource and ownership gates
still apply, and the task payload and statistical inputs remain unchanged.
Native queue CLI workers load this configuration on their next claim; a
long-lived in-process Queue instance needs an explicit reload or restart.

In a later Windows snapshot, a compound statement waited about twelve hours
for a ready integration model while unrelated models completed. The outer
coordinator heartbeat stayed stale because its script loop could not advance,
although its inner progress timestamp kept refreshing. Thus a fresh progress
timestamp proves activity, not forward movement. Compare the waiting task ID
and statement position over time, and include compound waits when promoting
dependencies. Do not unwind and replay an arbitrary compound R statement:
partially executed loops can mutate objects, RNG state and model call counters.
Resume its existing dependency when possible; a coroutine/checkpoint redesign
requires separate replay-equivalence tests.

Measure committed/private memory as well as RSS on Windows. A small RSS can
coexist with substantial private allocation. Calibrate `memory_gib` using
observed peaks plus R-worker overhead. The current queue reserves running-task
budgets again when admitting candidates, so its conservative rule can hold
work even when apparent free memory looks adequate. Do not defeat that rule
without a measured replacement.

## Success-first triage for legacy replications

Before admitting a large or unfamiliar model, join its input fingerprint to the
historical `.out` inventory. A historical estimation success is the preferred
reproduction target and should be imported or reused before generating a new
attempt. A task with no historical successful `.out` remains visible in the
manifest, but it belongs in a deferred lane when the mainline is under pressure.

Treat Bayes, LMS and other long-running classes conservatively. Do not lower
`FBITERATIONS`, split imputations, or silently change the estimator to make a
run finish. If a no-history attempt exceeds the documented runtime budget,
capture the exact worker/Mplus identity, archive every file with SHA-256 hashes,
stop only that verified process chain, and publish queue status `deferred` with
`estimation_ok=false`. This preserves the input and partial `.out` for later
scientific review without consuming the mainline's resources.

`deferred` is distinct from `failed`: it records an intentional scheduling
decision, blocks downstream consumers, and is counted separately in monitoring.
It must never be treated as a successful estimate or silently omitted from the
final table audit. A small evidence JSON should record the reason, elapsed wall
time, CPU/private memory observed, historical-match result, archive path and
whether Mplus and its worker were confirmed dead after the stop.

Enforce a success-first scope on future claims, not only on the tasks visible
at triage time. The optional queue configuration `historical_success_policy`
contains a manifest path and its SHA-256. Its `allowed_output_names` list is
built from hash-verified, successfully estimated historical outputs. Unknown
names become `deferred` before resource admission, including work generated
later by a coordinator. Missing or changed manifest evidence fails closed.
An exact-input reuse task whose source was deferred must also become deferred;
otherwise it can wait forever for a source that will never finish.

This basename filter is only a coarse eligibility screen for fresh execution.
It does not authorize importing a historical output, certify matching source
data, or establish numerical equivalence. Reuse still requires the complete
input/data content identity, and manuscript acceptance requires a separate
comparison. Keep the manifest, source inventory hash, task reason and event
record together. Enable this policy only when the user has selected this scope.

Calibrate a single pending model before generalizing a smaller budget. In one
observed recovery, 25 completed integration comparators with at least ten
monitor samples each had sampled Mplus private-memory peaks no higher than
324.1 MiB. A blocked related model's incremental budget was changed from
1 GiB to 0.65 GiB (more than twice that sampled peak); existing idle R workers
were already included in the host's used memory. The system reserve and hold
thresholds remained intact. The original worker then claimed that model and
an owned Mplus child became CPU-active. Record the queue backup, comparators,
input hashes, old/new budget and actual process evidence. Sampled peaks are
not exhaustive peak guarantees, and this one admission does not validate a
class-wide budget reduction or prove convergence. Keep observing host pressure
and block additional admissions when headroom falls.

A later four-variant, ten-imputation family supplied a narrower calibration:
three completed variants shared the same imputation hashes and active ANALYSIS
settings, with 22 retained monitor samples and process-reported private-memory
peaks up to 239.5 MiB. Only the fourth pending variant was changed from 1 GiB
to 0.5 GiB, more than twice that observed maximum. The same worker then claimed
it without restarting RStudio or relaxing the 10 GiB disk reserve, CPU limit or
memory hold threshold. Check the process peak field rather than only one late
RSS/private sample, preserve a native SQLite backup and queue event, and verify
the unchanged input hash and actual owned child after admission. This family
comparison supports that one scheduling budget; it does not establish a safe
default for other integration models or authorize extra workers without ready
independent work and memory headroom.

When a running task already owns an Mplus child, subtracting its full planned
budget again can hold an independent task even after the allocation is visible
to the operating system. A safe memory credit requires the registered worker
PID and creation time to match, the child to be the configured Mplus executable,
and its working directory and input filename to match the task. Credit only
the observed private bytes, capped at the task budget; keep the unobserved
remainder reserved. If any identity check fails, use the full reservation. In
this Windows run, this released about 1.17 GiB of a 1.8 GiB Bayes reservation,
allowing a separately calibrated 0.65 GiB regular model to start while Bayes
continued. CPU and memory hold thresholds remained active, and one Bayes class
limit continued to apply. Record the queue backup, identity evidence, measured
private bytes and admission event. This is an admission optimization; it does
not prove convergence or justify changing Mplus settings.

Source order and accumulated prior `readModels()` calls are not a precise data
dependency graph. Track provenance separately from validated direct inputs;
never delete an apparent extra dependency merely because it delays a task.

## Evidence from a Windows PP-LGCM recovery

Preparation needs its own measured budget. A fixed check of “available minus
0.5 GiB must remain below 90% used and above 1.5 GiB” repeatedly blocked a
producer while its model worker kept running. The coordinator's observed peak
private allocation was 1.47 GiB and its idle allocation was 0.57 GiB. A scoped
1.65 GiB peak budget admitted the next preparation by reserving only the
increment above its current private allocation. The new check retained at least
5% of physical RAM (and never less than 0.5 GiB), plus 1 GiB of Windows commit
headroom after the incremental reservation. It raises its projected peak when
new observed peaks times a 1.10 margin exceed the calibrated ceiling.

This is a local calibration, not a portable default. Record the process peak,
PID/creation time, available memory, commit headroom, decision and policy per
admission. Test low physical memory, low commit headroom, unknown probe values,
boundary cases and rising peaks. Load policy changes at a durable checkpoint;
keep estimates running on their existing worker. A passing admission test is
only infrastructure evidence: observe actual source advancement, new model
inputs and owned Mplus CPU progress before claiming the delay was resolved.

Available physical RAM and available Windows commit are different constraints.
If a bounded preparation process fits the verified commit budget, normal OS
paging can be preferable to indefinite waiting for idle physical RAM. Make that
an explicit, local mode: the PP-LGCM preparation fallback requires at least
0.75 GiB physical RAM before admission, at least 3 GiB commit remaining after
the incremental budget, and a projected process peak no larger than 2 GiB.
It checkpoints after at most 25 source statements per admission. Normal mode
retains the physical reserve above. Record `paging_admit` separately, retain
critical-low-memory and low-commit rejection, and measure real progress and
process peaks. This does not change the estimator, remove queue admission
checks, or establish a universal memory setting.

Do not make a background job's startup depend on the interactive agent writing
its returned async ID within a short timeout. Use the process identity and
atomic singleton lock for execution ownership; register the real async ID in
the same orchestration call immediately after submission. Late registration
must not kill a valid worker or substitute a fabricated job ID.

A real run exposed 12 dependency-ready pending records behind two long Bayes
attempts. Six pending records declared 10 processors, while the two running
ones occupied 6 of a 12-processor budget. The third worker had not been
submitted. Large preparation checkpoints totaled about 1.60 GB and were
reloaded/rewritten on unchanged waits. After restoring live workers and changing
dispatch order, three waiting models completed within roughly 30 seconds.
This demonstrates avoidable queue delay; it is not a serial-versus-parallel
speedup benchmark or a whole-project ETA.

The same queue mixed historical and current namespaces: 388 completed records
corresponded to only 213 completed records in the current namespace, with many
results reused. Report namespace counts, reused results, valid estimates,
warnings, saved-data failures and reconciled manuscript cells independently.
A median based only on terminal attempts excludes running and interrupted
long jobs and must not be used to promise a finish time.

## Monitor and acceptance

- Store the collector heartbeat independently of the display window. Show
  freshness, coordinator PID/creation time, actual Mplus children and CPU
  deltas. An old `running` record is not current process evidence.
- Keep collector history compact: IDs, states, resources and process identities;
  input manifests already live in the queue and need not be repeated per sample.
- A monitor can report failure without repairing it. State explicitly whether
  recovery is manual, agent-driven or an installed supervisor's responsibility.
- Test mixed processor demands, class limits, simultaneous claims, unchanged
  waits and wake-on-failure. Validate real output hashes and model diagnostics
  after recovery. Keep the guide draft until manuscript reconciliation is done.

## Headless monitor recovery and supervisor token budget

Treat the monitor as a local evidence collector, not as the Mplus execution
engine or as a reason for an agent to poll RStudio continuously. Keep its
heartbeat, queue counts, process identities and resource samples in durable
files so the executor can inspect them and the supervisor can remain dormant
between events. A visible PowerShell/RStudio panel is optional; closing it must
not stop an owned Mplus process.

If the heartbeat stops, first compare the monitor PID with the last durable
timestamp and inspect its stderr/exit record. In the Windows PP-LGCM recovery,
`monitor_parallel.py` exited with `OSError(28) No space left on device`; the
Mplus workers continued and the queue advanced. After freeing space, restart
exactly one monitor instance, wait for two fresh writes, and verify that its
PID, queue counts and Mplus child identities are current. Do not start a new
coordinator merely because the monitor is stale, and do not infer a model
failure from an old `PROGRESS.md`.

Use a callback/event boundary for agent supervision: the executor handles
long-running workers and local monitoring, while the supervisor samples only
at startup, model completion/failure, resource alerts or heartbeat expiry.
Record API/transport failures separately from RStudio, worker and Mplus state.
If the executor provider is unavailable, preserve the same run and queue
identity and perform a single-writer supervisor takeover; never resubmit a
live task or create a second coordinator.
