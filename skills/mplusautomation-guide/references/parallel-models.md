# Parallel model scheduling

Partition only genuinely independent model calls (for example, measurement
scales or moderator variants). Keep dependency edges explicit: a worker may
start only after every required upstream output has passed its SAVEDATA and
hash checks. Use a queue with immutable task IDs, one claim transaction, and a
per-worker state file. The coordinator may enqueue work while workers run, but
must never duplicate a claimed task.

Use a conservative resource gate. A second worker is admitted after five fresh
healthy samples; a third requires a new review of available memory and actual
Mplus RSS. A monitor reports stage, message, elapsed time, job ID, queue counts,
and resource values. Closing the monitor window must not stop workers.
