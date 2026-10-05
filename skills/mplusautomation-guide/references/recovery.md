# Recovery after interruption

Before resuming, archive the queue, job registry, coordinator heartbeat, and
all checkpoint files. Confirm that no coordinator, worker, Mplus, or R child
process from the interrupted batch is alive. Reconcile only the exact stale
`running` IDs; preserve every other status. For each resumed task, verify the
input manifest hash and inspect any partial `.out`/SAVEDATA files. A partial
output is never reused without a validation record.

Write recovery metadata with the interruption reason, timestamp, old/new queue
counts, archived paths, and the native transport used for resubmission. Use
bounded retries for atomic publication on Windows because antivirus, indexing,
or Mplus file handles may temporarily lock a file. Never use a broad process
kill or stale-session cleanup that can terminate a live RStudio session.

Registry readers must tolerate older recovery records that omit optional
identity fields such as process creation time. Use `dict.get()` with a
PID-only warning until the registry is repaired; a malformed status file must
not stop the monitor or alter the queue.
