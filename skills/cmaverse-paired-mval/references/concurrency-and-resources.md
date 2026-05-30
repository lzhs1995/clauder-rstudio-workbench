# Concurrency and resources

`max_parallel` must not be hard-coded. The optimal concurrency depends on
`nboot`, the number of groups, each `cmest` object's size, how many RData files
write at once, machine memory, free disk on the output drive, and (if enabled)
whether the upload keeps pace with model output.

## Native smoke first

Before launching a CMAverse fan-out run, prove the current agent-native MCP
wrapper path with `clauder-workbench native-smoke complete`. The generated
contract sets `requires_native_smoke: true`, so `fanout-plan`, `fanout-run`,
`fanout-poll`, and `merge-gate` require the resulting parent evidence. Python
MCP stdio prewarm and HTTP fallback are diagnostics; they do not satisfy this
native gate.

If the native tool returns `Transport closed`, do not ask the user to restart
Codex first. Run doctor/provenance checks, reinstall or prewarm the persistent
`clauder-mcp.exe` entry if needed, and retry native-smoke. Restarting the agent
is the last step after the persistent entry and provenance are already correct.

## Smoke / structure validation (`nboot=10`)

In the case-study smoke (`groups=sy_female,sy_male`, `nboot=10`, no upload),
`max_parallel = 1..7` all passed 14/14 validation; `max_parallel=7` was fastest:

| max_parallel | wall (min) | max memory | min disk free |
|-------------:|-----------:|-----------:|--------------:|
| 1            | 78.90      | 91.2%      | 78.32 GB      |
| 2            | 11.18      | 94.0%      | 58.89 GB      |
| 3            | 7.23       | 87.2%      | 31.35 GB      |
| 4            | 5.30       | 88.5%      | 61.42 GB      |
| 5            | 6.38       | 86.0%      | 61.41 GB      |
| 6            | 5.87       | 88.3%      | 61.40 GB      |
| 7            | 3.13       | 89.5%      | 61.41 GB      |

So for **structure validation only**, start at `max_parallel = 7`.

## Formal run (`nboot=1000`) — do not extrapolate

`nboot=1000` objects are far larger and write more RData. The `nboot=10` optimum
does not carry over. Use a dynamic strategy:

1. Probe formal parameters on 1-2 mediators first.
2. Watch memory peak, RData write speed, upload speed, and minimum free disk.
3. If resources are stable, raise concurrency.
4. If memory nears the system limit, writes back up, upload lags, or validation
   goes missing, lower concurrency.

A conservative formal start is `max_parallel = 3` or `4` — a starting point, not
a fixed optimum.

## Resource log

During concurrency tests or formal runs, record: CPU %, memory %, free disk on
the output drive, Rterm/Rscript process count, each worker's stage, each
worker's last-update time, each worker's saved file size, and each worker's
elapsed time. This log is the input to the raise/lower concurrency decision.

The clauder-rstudio-workbench `resource-gate` harness encodes the rule: only
when memory stays clear of the threshold, I/O is not stalled, Rterm/MCP stays
responsive, and durable output keeps advancing may concurrency step up by one.
