# Recover an accepted prefix after a Windows progress-write failure

A coordinator can exit while publishing progress even though its preceding
Mplus calls and exports completed successfully. A continued staged MI batch
hit Windows error 5 at `os.replace` after 19 accepted imputations (38 GH7/GH15
stages). This was an infrastructure failure, not a failed last estimate or a
completed MI family. These rules apply to both Windows-local agents and Mac
agents controlling the same Windows RStudio/ClaudeR/MplusAutomation workflow.

## Bounded atomic publication

`durable_mplus_worker.atomic_json` flushes one complete UTF-8 snapshot, then
retries replacement of that same snapshot for at most two seconds for Windows
access/sharing/lock errors 5, 32 or 33. The caller retains its original OS lock.
Other errors, including disk-full and non-Windows permission errors, propagate
immediately. Each attempt still rejects a symlink or protected new evidence.

If the deadline expires, the previous JSON and the pending temporary snapshot
remain available. Do not discard an accounting write and continue starting
engines. These checks do not make an uncooperative writer obey the lock and
are not a power-loss recovery guarantee.

A real Windows `CreateFileW` handle with read/write sharing but without
`FILE_SHARE_DELETE` reproduced the replacement error; releasing that handle
allowed the retry to succeed. Six tests passed on Windows. The Mac passed the
five portable cases and skipped the native Windows case. This proves a
reproducible mechanism, not which reader caused the original incident.
Short PowerShell observers should use
`FileShare.ReadWrite -bor FileShare.Delete` and close streams promptly.

The final retry implementation also passed all 35 Windows durable-worker
regressions, covering original caps, duplicate guardians, coordinator loss,
unknown exits, prior costs and output-only export. These use synthetic Python
processes and make zero Mplus calls. Keep their engineering acceptance separate
from the active scientific batch and its frozen worker version.

## Reconcile before continuing

1. Preserve the failed job, original code/plan, R/coordinator records, output
   manifests and all attempts. Verify exited processes by PID and birth time.
2. Check every registered member's actual work and guard paths, including
   members without exports. An erroneous extra `members/` path component can
   hide an already-started attempt. Unknown starts/exits keep costs open.
3. Verify exact saved file sets/hashes, MI and engine identities, actual
   inputs, covariance and scientific checks. Reconstruct each GH15 input from
   that same MI's GH7 solution and retain original quadrature tolerances.
4. Reuse only verified stages, preserving their actual old R owner and
   MplusAutomation calls. A copied result is not a new recovery-worker call
   and must not be relabelled as unrelated calibration.
5. Give only genuinely unstarted nodes a new recovery contract. Carry old
   calls/seconds forward and subtract them from the original allowances.
   Enforce the original absolute coordinator deadline as well as elapsed
   worker time; a delayed submission must not renew the deadline.
6. Submit once through the same Windows RStudio/ClaudeR entry, then follow
   that recovery job ID. Keep the failed original job unchanged. Pool only
   the full registered MI family after independent readback.

The observed prefix closed at 36 new calls and 4,096.234753 engine seconds,
plus two reused original calibration stages. Recovery allowed only MI20–40:
at most 42 calls, 14,623.765247 remaining seconds, the original 240-second
per-call cap and the original coordinator deadline. Windows verified all
38 reused stages; 30 reader tests on both platforms preserved R lineage,
model identity, old costs and full-MI pooling gates. The first recovered
estimates used the same RStudio and MplusAutomation library. These checks
do not establish completion of the unfinished scientific family.

## Keep status replies small

PowerShell `Get-Content -Raw` may return an extended `PSObject`. Serializing
its provider properties turned a short test/audit reply into about 92.8 MB.
The tests had already passed; rerunning them would not repair the wrapper.
Use `[IO.File]::ReadAllText` or an explicit `[string]` cast, and prefer small
status/count/path/size/SHA256 summaries. Keep full logs on Windows and recover
the original result there without sending an oversized reply to a low-space
Mac. Transport lessons belong in `cross-device-remote`; session observations
also belong in `clauder-rstudio-workbench`.
