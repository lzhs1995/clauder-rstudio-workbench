# Recoverable Soak Monitor

Use `soak-monitor` for formal multi-worker runs that need scheduled resource,
durable-progress, and independent MCP heartbeat evidence. It is a separate
transport observer: heartbeat evidence is `MCP_STDIO_OK`; the monitored native
fan-out still requires its own fresh `NATIVE_MCP_OK` smoke chain.

## Run and inspect

```bash
clauder-workbench soak-monitor run \
  --contract /absolute/path/native_contract.json \
  --evidence-dir /absolute/path/evidence/native \
  --expected-pid 39875 --port 8788 \
  --stop-file /absolute/path/evidence/native/stop.monitor \
  --monitored-transport NATIVE_MCP_OK

clauder-workbench soak-monitor status \
  --contract /absolute/path/native_contract.json \
  --evidence-dir /absolute/path/evidence/native \
  --expected-pid 39875 --port 8788 \
  --stop-file /absolute/path/evidence/native/stop.monitor
```

The first invocation owns the logical monitor run. If that command is stopped
outside its internal supervisor, restart it only with `--resume`; an existing
checkpoint is never overwritten implicitly.

## macOS formal hosting

For a formal Codex soak, do not leave the outer monitor process attached to the
agent's foreground command session. Run it in a named detached tmux session and
wrap it in a run-scoped `caffeinate` process:

```bash
tmux new-session -d -s clauder-soak-<run_id> \
  "/usr/bin/caffeinate -dimsu /Users/<USER>/.local/bin/clauder-workbench soak-monitor run <arguments> >monitor.stdout.log 2>monitor.stderr.log"
```

Before worker submission, verify the tmux session, checkpoint logical run id,
two resource rows, and one successful heartbeat from a separate shell. During a
full-green qualification, disappearance of the outer tmux/monitor process
before the stop file is a BLOCK; do not use external `--resume` to make that
run appear continuous. The monitor's own supervised sampling-child recovery
remains valid when it stays within policy and does not break the SLA.

## Recovery and accounting

- Process attributes are read one at a time. macOS `psutil` failures from
  `cmdline()` are non-critical metric errors and never terminate sampling.
- Resource and heartbeat slots use absolute schedules. Missed slots remain in
  the denominator and are not hidden by catch-up calls.
- CSV writes are flushed and synced. `monitor_checkpoint.json` is atomically
  replaced, and a supervised restart reconciles any committed CSV row written
  immediately before a checkpoint failure.
- The internal supervisor preserves one logical run id and enforces the
  contract's restart budget.

## Safety policy

The optional contract `monitor` map controls cadence and thresholds. Defaults
are 30-second resource samples, 60-second heartbeats, 99% minimum scheduled
success, 120-second maximum heartbeat/state gap, 85% memory admission hold,
90% memory hard abort for three samples, 75GB minimum disk, and a 10-minute
combined MCP-plus-durable-state stall before cancellation.

R worker count is diagnostic. Memory, disk, expected PID, and port are safety
critical. A hard abort cancels only registered original job ids; it never
resubmits work.

For formal completion, pass the resulting `soak_monitor` evidence as a parent
and require it explicitly:

```bash
clauder-workbench completion-check --mode formal \
  --task-key <task> --require-soak-monitor \
  --soak-monitor-max-age-min 120 \
  --parent-evidence <soak_monitor_PASS.json> <other_parent_evidence.json>
```

The gate accepts only a matching, fresh `PASS` whose heartbeat route is
`MCP_STDIO_OK`, whose monitored transport is `NATIVE_MCP_OK`, and whose summary
checks are all true.
