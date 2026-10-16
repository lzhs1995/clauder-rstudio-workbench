# Windows resource coordination for Mplus

## Objective and authority

Optimize completed-model throughput while preserving the approved analysis and
the user's work. When the user explicitly prioritizes Mplus and authorizes host
optimization, act on reversible scheduling and confirmed dispensable workloads;
do not respond to every memory shortage by waiting. Existing authorization is
sufficient for those actions. Unknown processes are not automatically disposable.

Never terminate by executable name, delete R objects to make a dashboard greener,
disable security services, kill the active R/Mplus tree, or shut down WSL hosting
the agent. Unsaved documents and in-flight tasks require preservation. Different
stdio MCP clients normally have separate server processes: duplicate executable
names alone do not establish stale servers. Coordinate their owners or verify
inactivity and a reliable reconnect path before retiring them.

## Diagnose before choosing a remedy

Collect a durable 15–30 second baseline and keep collection overhead small:

| Question | Evidence | Response |
|---|---|---|
| Does Mplus have enough CPU service? | Process CPU-seconds divided by its actual sample interval; active threads | A busy single thread should approach one core, not 100% of the whole machine |
| Is the machine swapping? | Available RAM, commit headroom, Pages Input/sec, disk activity, process faults | Separate system paging from Mplus paging; total faults include soft faults |
| Where is memory held? | RSS/working set, private committed bytes, process identity and owner | Retiring idle committed memory is not the same as releasing physical RAM |
| Is a hybrid CPU scheduling badly? | GetLogicalProcessorInformationEx efficiency classes, per-core activity, Mplus affinity | Test the discovered performance-core set; never hardcode another machine's indices |
| Is power constraining speed? | AC/battery, power mode, actual frequency if available | Consider reversible AC performance settings; CPU time alone does not measure clock speed |
| Is another task competing? | Interval CPU/I/O deltas, process tree, job purpose | Lower authorized background priority or gracefully stop confirmed dispensable work |

Use per-process timestamps for CPU deltas when enumerating many processes.
An expensive full process sweep can take minutes; do not divide short per-process
CPU deltas by the entire sweep and report the result as utilization. Avoid repeated
remote `cwd()`/command-line retrieval and heavyweight CIM calls in the hot loop.
Use the frozen attempt directory and validated ancestor chain for model ownership.
Do not log credentials or full unfiltered process command lines.

## Active optimization sequence

1. Confirm the dispatcher PID **and creation time**, then resolve its living Mplus
   descendants. Save affinity and priority before any mutation.
2. For a confirmed CPU-bound single-thread model, trial Above Normal priority and
   the measured performance-core set. Keep Real Time off; avoid High by default.
   Affinity is a scheduling experiment, not a universal optimum. Compare repeated
   samples, and roll back if CPU service, responsiveness or throughput worsens.
3. Lower authorized competing background UI/browser priority without killing tabs,
   terminals or their child jobs. Preserve their PID/creation-time/prior-priority
   records. Restore at workload completion only if the current value is still the
   value set by the coordinator, so a later user change is not overwritten.
4. Gracefully close confirmed dispensable auxiliary UI via its owned top-level
   window. Check the process actually exits; a posted WM_CLOSE is not completion.
   Do not force past an unsaved-work dialog. An elevated process may reject close
   or priority changes; report the failed action instead of claiming it succeeded.
5. Reclaim memory based on ownership and evidence:
   - R: one PID-guarded `gc(full=TRUE)` preserves live objects. Measure private/RSS
     before and after. If it does not release memory, do not repeat it as a ritual.
   - WSL: inspect available memory and file cache. A one-time authorized
     `sync; echo 1 > /proc/sys/vm/drop_caches` can reclaim clean page cache without
     killing processes; measure the host effect separately. It can make later reads
     slower and is not a periodic cleanup policy. Do not shut down the agent distro.
     Reassess only when a new, measured pressure event occurs: cache regrowth and
     an actual admission delay can justify another targeted reclaim hours later.
     Record before/after cache and host RAM separately; cache reduction alone does
     not prove the same amount of memory was returned to Windows.
   - MCP: identify module, owner, activity and connection state. Close truly stale
     or unused servers with a documented restart path. Live independent stdio
     servers cannot simply be merged. Prefer lazy loading heavyweight embeddings
     in future setup over loading them for every non-literature task.
   - Apps: graceful exit of an idle application can release private commit; preserve
     documents, downloads, notebooks and active research sessions.
6. Recheck RAM, commit, paging and Mplus CPU service. Retain admission reserves;
   lowering the resource threshold is not an optimization.

## Sustained admission waits

Treat a long wait as an observable coordination state, not as permission to
blindly relaunch the model. Keep the original dispatcher, worker creation time,
manifest and progress CSV unchanged while sampling the same admission record.
When one model remains in `resource_wait` across several polling intervals:

1. Recheck the live worker and its Mplus descendants by PID and creation time.
2. Record available RAM, commit headroom, disk headroom and the exact required
   budget in a new receipt; do not infer the threshold from a standalone probe.
3. Inventory large processes and classify them by owner, input directory and
   parent chain. A different chapter's Mplus, an active R session, a sync client
   or an interactive monitor remains protected unless its owner has explicitly
   authorized retirement.
4. Apply at most one evidence-backed, reversible cleanup for a new pressure
   event. If it does not improve admission or paging, record the null result
   and stop repeating the same cleanup.
5. Continue polling the unchanged job. Lowering the reserve, editing a live
   budget file, or launching a second Mplus is a new experiment and requires an
   isolated contract, not an implicit response to waiting.

The receipt should state whether a candidate Mplus child was present, whether
the wait was caused by RAM/commit/disk, which processes were protected, and
whether termination or restart occurred. This makes “active optimization”
auditable without turning a safe wait into an untracked model change.

A later candidate queue briefly lowered its RAM reserve from 0.75 to 0.45 GiB.
Subsequent models advanced, but there was no matched throughput or paging
comparison, and host memory changed concurrently. The reserve was restored to
0.75 GiB through the per-admission probe without restarting the running queue.
Keep that as a reverted admission experiment, not a validated speedup or a
portable default. Repeated working-set trimming in that attempt likewise did
not establish a lasting gain. An HTTP-responsive RStudio is not proof of an idle
process family; check live descendants and PID creation times before intervention.

Do not use repeated EmptyWorkingSet/standby-list flushing as proof of improvement:
it can merely evict useful pages and increase page faults. Do not use RSS alone to
rank committed-memory pressure. Do not claim all memory was reclaimed by an action
if other applications changed during the same interval.

For a scoped, one-time working-set intervention, first sample the exact process
identity and its descendants for activity. Skip active families and record skipped
actions as skipped, not reclaimed RAM. Preserve R objects and the session. Judge
an actual intervention by subsequent workload progress and paging, not RSS alone.
In the Chapter 4 follow-up, all three RStudio families failed the idle check, so
none was trimmed (`evidence/idle_r_workingset_trim_20261002.json`).

A later foreground-only observation found the exact Chapter 4 R session nearly
CPU-idle while its separate worker waited for admission. A single EmptyWorkingSet
call reduced that foreground RSS from 0.294 to 0.007 GiB; private commit stayed
0.695 GiB. Host available RAM rose only from 1.330 to 1.376 GiB in the immediate
window, and a later poll still showed admission waiting. Record this as a scoped
residency reduction, not proven throughput improvement or 0.287 GiB of net host
recovery. The process remained alive; no object deletion, process termination or
persistent working-set limit was issued. Do not use a short foreground-only idle
sample as proof that the whole process family is inactive, and do not repeat
trimming as an admission workaround. Evidence:
scientific_audit_20261002/validation/ch4_foreground_working_set_reclaim.json.

Retire auxiliary jobs whose complete work has been independently verified and
whose role is no longer needed. Archive their last native response and cancellation
receipt, verify their process exited, and preserve the main dispatcher identity.
Label this as intentional retirement, never successful natural completion. Remove
retired job IDs from polling; do not restart them because an old state file says
`watching`. In this run the incremental observer was retired only after all 612
comparisons matched the final table; the main post-processing job remained alive.

## Portable coordinator entry

`scripts/windows_coordinator.py` extracts the reusable scheduling parts of the
historical machine-specific coordinator. It has no default dispatcher PID or
hardcoded CPU set. Run it with native Windows Python and `psutil`; pass the
actual worker PID and creation time, and a fresh evidence directory for every run.

```text
python windows_coordinator.py observe --output OBSERVATION_DIR --owner-pid PID --owner-created CREATED --interval 15 --duration 15
python windows_coordinator.py watch --output COORDINATOR_DIR --owner-pid PID --owner-created CREATED
python windows_coordinator.py stop --output COORDINATOR_DIR
python windows_coordinator.py restore --output COORDINATOR_DIR
```

`observe` performs no scheduling mutations. `watch` applies Above Normal priority
only to Mplus descendants of the identified owner; optional `--affinity` accepts
an explicitly reviewed list of CPU indices. It does not discover performance
cores or choose an affinity by itself. Prefer the default unpinned setting until
a topology/throughput comparison justifies pinning. Do not use a live RStudio PID
as the owner when a narrower dispatcher/worker identity is available.

The Windows byte lock prevents a second coordinator or restore from sharing the
same evidence directory while the watcher is active. A stop request is a signal,
not evidence of exit: verify `completion.json`, its `stop_reason`, and the final
restore actions. The watcher stops when its owner disappears or its identity
changes. A caught interrupt invokes restoration; a crash can be recovered using
`restore` after the Windows lock is released. State is saved before mutations.
Restoration checks each original process identity and restores only a setting
still equal to the value this coordinator requested. Later user changes are
preserved; subsequent polling does not repeatedly reapply a changed setting.

Observations contain native physical RAM and commit headroom from
GetPerformanceInfo plus owned Mplus CPU-time deltas, thread count, RSS, private
bytes and total page faults. Per-process sample timestamps define the CPU rate.
Total faults include soft faults; these records alone do not diagnose disk paging
or establish an elapsed-time improvement. There is no periodic cache trimming,
process termination, R object deletion, Mplus submission, or change to model syntax.

This tool supplies scoped scheduling and durable measurements. **It does not
automatically decide which other applications are dispensable or replace the
active memory-reclamation steps above.** Use ownership, activity and recovery
evidence before those actions. The workflow's RAM/commit/disk admission still
applies; the coordinator does not lower its thresholds or add execution slots.

The development checks include 13 fake-process tests for ownership, PID reuse,
persist-before-mutation, idempotence, crash recovery and conditional restore.
A native Windows lifecycle test also covers lock exclusion, stop/exit and
post-exit restore on a controlled Python tree without Mplus. Neither certifies
throughput: validate actual Mplus coordination and benchmark gains when a model
is authorized and running. Use `scripts/test_windows_coordinator.py` to repeat
the mutation-free contract tests.

## Persist coordination across model boundaries

The coordinator must have a unique lock, its own identity record and durable log.
Bind it to the original dispatcher identity. Poll at a modest interval, e.g. 30 s,
discover new Mplus children, and apply validated settings only when different.
Keep it alive across model changes, but never submit or restart an analysis model.
Stop if the original dispatcher disappears or its identity changes. Provide an
explicit stop/restore procedure, and restore surviving processes at completion.
Do not restore while a still-running coordinator immediately reapplies the change.

Prefer a single model slot until throughput and memory measurements justify a
change. Parallel models may compete for power, cache and RAM. If concurrency is
authorized, compare completed-model throughput, not just aggregate CPU use; use
distinct attempts and preserve the bootstrap/random-seed policy. Do not silently
change PROCESSORS, bootstrap count, estimator, convergence or statistical syntax.

## Evidence from the Chapter 4 Windows run (2026-10-02)

This is a measured example, not portable default settings:

- 16 logical CPUs: indices 0–7 were performance-core threads (efficiency class 1),
  8–15 were efficiency cores (class 0). The latter were saturated while the former
  were substantially less busy during the diagnostic sample.
- The observed Mplus process had one thread, about 109 MiB private memory and very
  few process page faults. System RAM pressure existed, but Mplus self-paging was
  not established as the main explanation for its slow execution.
- After affinity to the measured performance-core set and Above Normal priority,
  several successive normal monitor intervals showed about 30 CPU-seconds per
  31 wall-seconds. A coordinator then applied those settings to the next model,
  which also achieved about 30/31. Earlier normal intervals were commonly 20–26/31
  and contention intervals were lower. These are CPU-service observations, not a
  controlled claim about equal-model elapsed speedup or numerical equivalence.
- WSL page cache was reclaimed initially. At a later measured pressure event,
  the observer waited with Windows available RAM around 1.15 GiB and WSL cache
  regrown to 1629 MiB. A targeted sync/page-cache reclaim reduced cache to 833 MiB;
  the next monitor showed 2.09 GiB host RAM and resumed comparison. Concurrent
  workloads prevent attributing the entire host RAM increase to this action.
  Evidence: `evidence/cache_reclaim_20261002T1142.json`; no periodic flush was set.
  Zotero desktop exited gracefully, with about
  0.87 GiB private commit and 114 MiB working set before exit. Seven live Zotero MCP
  processes were classified separately, not mislabeled as orphaned processes.
- PID-guarded GC in three R sessions succeeded but did not materially reduce their
  private memory at that measurement. Do not report it as a successful RAM saving.
- Task Manager rejected WM_CLOSE and priority changes; it was not closed. Edge and
  Windows Terminal priorities were successfully reduced with rollback records.

The project implementation is in the recovery sandbox:
`scripts/optimize_owned_mplus.py`, with `resource_coordinator_identity.json`,
`mplus_resource_optimization_state.json` and action JSONL under `evidence/`.
That script is specific to the validated machine and dispatcher. Adapt topology
and ownership before reuse elsewhere; do not copy its process IDs into a new run.

## Verified tool capabilities and sources

Consulted on 2026-10-02; snapshots are retained in this project's
`evidence/reference_sources_20261002/`:

- [ClaudeR upstream README](https://github.com/IMNMV/ClaudeR): `execute_r_async`
  runs self-contained code through a separate `callr` process; poll the same job
  with `get_async_result`. Main-session objects are not automatically shared.
- [Workbench skill](https://github.com/lzhs1995/clauder-rstudio-workbench/blob/main/skills/clauder-rstudio-workbench/SKILL.md)
  and [parallel contract](https://github.com/lzhs1995/clauder-rstudio-workbench/blob/main/skills/clauder-rstudio-workbench/references/parallel-async-fanout.md):
  one RStudio can drive independent concurrent workers. Each worker needs its own
  state, manifest and validation artifacts; the merge gate checks all workers.
  Dynamic `fanout-run` admission samples resources, raises concurrency gradually,
  and drains existing work when thresholds are crossed. Native-wrapper submissions
  remain explicit and cannot be relabeled from Python MCP stdio evidence.
- [MplusAutomation CRAN vignette](https://cran.r-project.org/web/packages/MplusAutomation/vignettes/vignette.html):
  Mplus is the estimation engine; MplusAutomation generates/runs/reads models.
  `runModels` supports directories, recursion, logging, output display and skipping
  existing outputs. These features alone do not promise local concurrent model
  execution or automatically turn a single-thread Mplus fit into a multi-thread fit.
  The vignette's mixture example containing `PROCESSORS=4` is not evidence that
  adding it to a frozen bootstrap model preserves the requested reproduction.

Do not upgrade a live computation merely because upstream documentation advertises
new tools. The retrieved Workbench skill described v0.6.7 paired with ClaudeR
0.14.1.9002; the locally installed shared skill described an older compatible line.
Validate actual loaded tools and code. In this task the native tool inventory did
not expose the newer `coordination_roster`/message tools described upstream.

For an existing serial dispatcher, a second launcher against the same mutable
manifest is unsafe. Prepare and test a single-owner multi-slot scheduler first:
atomic model claims, isolated worker state/event logs, coordinator-only audit
writes, summed RAM/commit budgets, cap 2 initially, checkpoint draining, orphan
child recovery, and final all-workers merge. Only migrate at a verified checkpoint
after the current Mplus exits. Preserve outputs and attempts, record old/new job
identities, rebind the observer and resource coordinator, and never resubmit models
that already have successful current-hash evidence. A batch scheduler redesign is
separate from changing statistical model specifications.

After a later 5,000-replicate foreground computation ended, a fresh native
measurement found about 741 MiB foreground working set. A single PID/creation
and idle-CPU guarded EmptyWorkingSet reduced it to about 47 MiB, but private
commit stayed unchanged and immediate host available RAM gained only about
4 MiB. Native session/previous-object-name checks passed. Do not repeat this
action to chase admission or report the 694 MiB working-set drop as recovered
host capacity. Evidence: recursive_gaussian_kernel_v1/independent5000/
post_batch_working_set.json and post_batch_native_health.txt in the audit.

A read-only process scanner can itself inherit `below_normal` priority and
take a long time under competing load. Verify the exact scanner command,
PID and creation time before restoring only that owned diagnostic process to
`normal`; record the prior value and rollback. This is distinct from increasing
Mplus concurrency or altering another chapter's process. The observed resource
the recorded scanner PID is historical evidence only, never a reusable process target;
see resource_audit_priority_restore.json in the same independent5000 folder.

When `sudo -n` requires a password inside WSL, it does not establish that all
authorized Windows-side WSL administration is unavailable. In this session,
`wsl.exe --distribution Ubuntu --user root --exec id` verified the existing
root entry. After checking actual cache pressure and preserving other jobs,
a one-time script ran `sync` followed by `drop_caches=1`; it did not shut down
WSL, kill processes, drop user objects or change persistent memory limits.
Use the verified current distribution and an explicit one-time receipt, never
assume a root entry or repeat the action periodically. This is within an
existing authorized host-resource optimization scope, not a reason to acquire
new credentials or bypass a tool approval boundary.

The measured Cached field went from 1,136,572 to 538,656 KiB; subsequent Windows
available RAM was about 1.425 GiB and the model still waited for approximately
1.5 GiB admission. Guest free/cache figures and host physical RAM are different
quantities; concurrent load prevents attributing the whole host change to cache
reclaim. Evidence: wsl_meminfo_before/after.txt, wsl_cache_reclaim_done.txt and
windows_memory_before/after_cache_reclaim.json in independent5000.

The paired saved host observations were actually about 1.499 GiB before and
1.425 GiB after, a decrease of roughly 76 MiB. Do not choose an earlier 1.2 GiB
low point as the before value to claim success. This intervention proved guest
cache reduction only; it did not prove increased host availability or throughput.
# Release completed diagnostic allocations before admitting the next model

When diagnosing an admission wait, pass the live worker's measured budget file
to the probe. A standalone probe's default minimum budget can produce a lower
threshold than the actual queue. In one check, the default implied about 1.19
GiB, but the queue's saved peak budget required about 1.50 GiB. Read the actual
admission record before calling a wait stale or reducing a safety margin.

After a known batch of local matrix checks has finished, one `gc(full=TRUE)` in
the owning R session can release unreachable diagnostic allocations. Preserve
global objects and measure RSS, private bytes and host available RAM separately.
This differs from periodic working-set trimming: here the Chapter 4 session's
private allocation fell about 0.42 GiB, with observed host available RAM rising
from 0.832 to 1.038 GiB across snapshots. Do not attribute all host change solely
to GC, sum shared RSS as reclaimable memory, or claim queue recovery until the
unchanged job reports actual estimation. Evidence: audit validation files
`memory_before_effect_gc.json`, `memory_after_effect_gc.json`, and
`effect_gc_native_health.txt`. Do not delete live user objects to repeat this.

A subsequent post-review GC had no measurable private-memory release: private
bytes remained 1,043,755,008 and RSS was effectively unchanged. Host available
RAM fell from about 1.873 to 1.751 GiB during that observation. A precision chunk
then passed admission, but that is not evidence that GC freed its budget. Retain
the before/after data, stop repeating ineffective GC, and attribute progress only
to the observed admission/worker receipts. Evidence:
`validation/post_full_review_foreground_gc.json` in the same Chapter 4 audit.

## Page reactivation and background UI memory priority

A later GC reduced private commit by about 39.5 MiB but increased RSS by about
119.9 MiB while host available RAM fell from 1.149 to 0.967 GiB. GC touches heap
pages that Windows may have paged out; private release does not guarantee an
immediate physical-memory gain. One coordinated GC in each of the two other
research sessions preserved their global names but showed no sustained host RAM
improvement. Stop repeating ineffective GC. See `validation/post_contract_cache_gc.json`
and `validation/coordinated_default8787_gc_20261004.json` /
`validation/coordinated_default38786_gc_20261004.json` in the audit.

A later one-time WSL clean-cache reclaim reduced guest cache from about 1.92 to
0.55 GiB, while paired Windows available RAM fell from about 1.526 to 1.170 GiB.
A separate idle foreground trim reduced RSS from 1,008,881,664 to 4,571,136 bytes,
left private commit unchanged and immediately gained only about 43.7 MiB of host
RAM. Neither observation establishes a throughput improvement. Preserve completed
action sentinels; do not rerun the scripts to chase the admission number.

Windows process memory priority controls page-replacement preference, not CPU
priority or a guaranteed memory release. Within authorized host optimization, a
confirmed background WebView renderer can be assigned lower memory priority
while its network backend remains protected. Check owner, renderer role, foreground
window, PID and creation time; record the old value and verify the new value.
An active renderer is not an idle one merely because its window is in the background.

In Chapter 4, an idle-only attempt skipped the renderers. A later explicitly
background-allowed action changed the Clash Verge and CC Switch renderers from
priority 5 to 1. It terminated no process and modified no network backend. Evidence:
`evidence/background_ui_memory_priority.json`; restoration entry:
`scripts/coordinate_idle_ui_memory.py --background-allowed --restore`.
Restore only when identity still matches and current priority remains the value
set by this action, preserving later user changes. Historical PIDs are not new
targets. Do not reapply the intervention while its receipt remains active.

The mere presence of Linux `memory.reclaim`, `swappiness` or balloon-driver
interfaces does not authorize indiscriminate anonymous-memory eviction. Distinguish
inspection from execution and evaluate effects on the live agent, terminals and
other research work before making any further scoped resource change.

## Chapter 4 queue optimization evidence (2026-10-04)

The live unified queue used a measured peak worker/Mplus budget of about 0.982
GiB. Its admission probe therefore required about 1.558 GiB of Windows available
memory, while the three preserved RStudio sessions, the R worker and WSL/MCP host
left roughly 0.75–1.38 GiB available. This was a host-resource bottleneck, not
evidence that the Mplus syntax or estimator had failed.

The following scoped actions were executed without closing sessions or changing
models: `gc(full=TRUE)` in the three R sessions, PID-guarded `EmptyWorkingSet` for
the current 8789 session/R worker and the preserved 8787/8786 sessions, and one
`sync; echo 1 > /proc/sys/vm/drop_caches` in the existing WSL distribution. The
working-set calls reduced RSS but left private commit essentially unchanged; the
cache reclaim reduced guest `Cached` memory but did not produce a stable Windows
availability gain. Do not repeat either action as a ritual or report RSS/cache
reduction as Mplus throughput improvement. Evidence is kept under
`scientific_audit_20261002/evidence/working_set_optimization_*.json`,
`wsl_meminfo_before_20261004_0346.txt`, `wsl_meminfo_after_20261004_0346.txt`,
and paired Windows memory snapshots.

A later sustained-pressure event justified one final root-scoped cache check via
`wsl.exe -u root`; `Cached` fell from about 1.00 to 0.52 GiB while Windows
available RAM did not improve (receipt
`experiments/income_candidate_full_20261004/resources/wsl_cache_reclaim_003.json`).
After this negative result, stop cache reclamation and investigate anonymous
owners or user-approved session retirement instead.

For a CPU-bound single-slot queue, record the active Windows power plan before
the run. The Chapter 4 queue was moved reversibly from `Balanced` to the built-in
`High performance` plan and the original GUID was saved in
`resources/power_plan_high_performance_20261004.json`; restore the recorded plan
after the run if the machine should return to its prior power policy. A power
plan change does not justify increasing Mplus concurrency or changing syntax.

When more than one `Mplus.exe` is visible, classify every process before
intervening. Follow the parent chain and read the working-directory/input path:
the Chapter 4 queue child was an owned Mplus PID under its recorded Rterm parent and its
`income_candidate_full_20261004` path; a separate Mplus PID belonged to a separate CFPS
TECH3 repair task. Preserve the latter and record the inventory in
`resources/external_mplus_inventory_20261004.json`; never kill or reprioritize
an unowned Mplus merely because it competes for CPU or RAM.

The reproducible helper is
`scientific_audit_20261002/scripts/optimize_windows_working_sets.py`. It accepts
only explicit, owned PIDs, records before/after RSS/private bytes, never kills or
pauses a process, and reports a nonzero result when Windows denies the action.
The queue remains single-slot because measured RAM/commit reserves do not justify
parallel Mplus models. Future throughput changes should first benchmark isolated
slots with atomic claims and summed resource budgets; never lower the admission
reserve or silently alter `PROCESSORS`, bootstrap count, estimator, or syntax.

During a later pressure event, a process inventory showed that the remaining
reclaimable non-analysis UI was Task Manager itself. A PID-guarded termination of
that auxiliary process released about 0.8 GiB of immediately available memory;
the Mplus child, queue worker, RStudio sessions and MCP stayed alive. This is an
exception for a clearly identified disposable UI, not permission to terminate
arbitrary Windows processes. The receipt was
`experiments/income_candidate_full_20261004/resources/taskmgr_graceful_close_002.json`.
Running `gc()` once in each preserved RStudio port was also recorded
(`resources/rstudio_gc_20261004.json`); private bytes did not fall, so further GC
or working-set eviction would be ritual rather than an optimization.


## Queue throughput evidence (2026-10-04 04:12 PDT)

At 344 completed live rows, the same serial queue had a median model elapsed time of 100.1 s (mean 115.8 s). Direct and mediation models were faster (medians 62.9 s and 59.8 s), while moderation and conditional models were slower (102.5 s and 109.6 s). A live Mplus child observed during estimation used about 0.07–0.15 GiB working set and 0.16–0.47 GiB private bytes; the R worker was about 0.17 GiB working set and 0.23 GiB private bytes. This supports an execution-cost bottleneck from repeated external Mplus launch/estimation/parse work plus admission waits, rather than a single Mplus child exhausting memory.

Keep one Mplus slot under the current budget. A future throughput experiment must use a disposable copy, atomic manifest claims, per-slot peak-memory receipts, and a summed admission budget; only then can two slots be considered. Preserve `runModels()` specifications and `readModels()` audit parsing in the scientific queue. Evidence: `scientific_audit_20261002/evidence/mplus_queue_performance_20261004.json`.

The live candidate queue supplied a stronger tail example: one representative
was recorded at about 3,658 seconds wall-clock while its eventual Mplus child
used only about 0.11 GiB private and one CPU core. The elapsed field therefore
must be decomposed into admission wait, Mplus estimation, and parsing before
calling a model “slow”; otherwise memory-gate delay is misdiagnosed as an
estimator or syntax problem.

## Complete-coverage resource lesson (2026-10-04)

After the 363-row queue terminated, nine missing representatives were run one at a time in an isolated copy and merged into snapshot04. Their Mplus private memory remained roughly 0.15–0.34 GiB while elapsed times ranged from about 185–543 seconds. This confirms the observed ceiling was repeated external estimation/parse CPU time plus host admission pressure, rather than a single child exhausting RAM. The safe operating point stayed one Mplus slot with explicit ownership, measured admission and `killOnFail=FALSE`; preserving 8787/8786/8789 was compatible with completion. The final execution manifest records 372 representatives and `all_pass=true` for technical consistency, while `scientific_closed=false` remains a separate scientific gate.
# Restart-safe coordinator ownership

A successful queue restart does not prove its resource coordinator restarted.
Chapter 4's coordinator rejected a valid new R worker because it asserted an old
RStudio PID literally. The fitting queue continued while priority/CPU/peak-memory
coordination had already exited. Inspect coordinator stderr, identity and fresh
samples separately from the analysis job status.

Resolve the explicitly targeted worker's live RStudio ancestor, require a unique
session ancestor, and optionally assert the currently selected session PID. Save
both worker and owner creation times. A read-only identity mode should pass before
starting the coordinator. Never make a historic PID the permanent ownership rule.
Preserve the failed stderr and source version. Restart only the missing owned
coordinator; a live Mplus fit does not need to be cancelled to repair supervision.

Native R analysis and OS process supervision are distinct operations. When a
native R tool prohibits `system2`, use the authorized Windows process tool for
the OS coordinator, retaining its exact target and logs; do not move statistical
analysis into an offline R process or claim that shell execution was native R.

The repaired coordinator observed approximately one CPU core of service and
0.21 GiB private memory for one live model. This proves active service in that
window, not a matched performance improvement. Maintain per-stage timings and
owned-process receipts before attributing faster execution to priority changes.
