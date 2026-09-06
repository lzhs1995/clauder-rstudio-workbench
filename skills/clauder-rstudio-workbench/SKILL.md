---
name: clauder-rstudio-workbench
description: Use when an agent needs to connect to a live RStudio session through ClaudeR, configure or verify the r-studio MCP bridge, run R code safely, poll long async jobs with progress, or avoid multi-session and multi-agent conflicts.
---

# ClaudeR RStudio Workbench

This skill is the operating protocol for using ClaudeR as a live RStudio workbench from Codex, Claude Code, GitHub Copilot CLI, or another MCP-capable agent. It is not a statistics reference; combine it with an R analysis skill for modeling decisions.

> **Headline capability:** async polling lets one RStudio session drive N child R worker processes at once and merge the results autonomously. See [parallel-async-fanout.md](references/parallel-async-fanout.md) and the Parallel Async Fan-out section below.

## First Reads

- For the complete cross-platform architecture, installation, operations, and
  evidence guide, read the maintained
  [Chinese usage manual](https://github.com/lzhs1995/clauder-rstudio-workbench/blob/main/docs/ClaudeR_%E6%9E%B6%E6%9E%84%E8%AF%B4%E6%98%8E%E4%B8%8Eclauder-rstudio-workbench%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97.md).
- Before formal long-running RStudio work, run the executable harness layer below. Markdown is advisory; harness evidence is the completion gate.
- For connection setup and MCP routing, read [rstudio-connection.md](references/rstudio-connection.md).
- For long jobs, read [async-long-jobs.md](references/async-long-jobs.md).
- For recoverable long-soak monitoring, read [soak-monitor.md](references/soak-monitor.md).
- For running many parallel R workers from one session, read [parallel-async-fanout.md](references/parallel-async-fanout.md).
- For native wrapper smoke and `Transport closed` recovery, read [native-mcp-gate.md](references/native-mcp-gate.md).
- For tool selection, read [clauder-tool-map.md](references/clauder-tool-map.md).
- For completion checks, read [verification-and-recovery.md](references/verification-and-recovery.md).

## Domain skill routing

- Use `$comparegroups-guide` for descriptive statistics, Table 1, labelled
  Stata inputs, panel/repeated-cross-section presentation, attrition tables,
  and validated three-line DOCX exports.
- Use `$cmaverse-paired-mval` for paired M=0/M=1 CMAverse bootstrap and Delta
  CDE validation.
- This core skill supplies the RStudio/MCP execution, async identity, resource,
  fan-out, monitoring, and completion discipline used by both domain skills.

## Executable Harness Layer

Use the matching entrypoint from this skill directory, or use the installed
`clauder-workbench` command after either installer installs the Python package:

```bash
./harness/run.sh doctor
./harness/run.sh doctor --expect-client codex --check-toml-parse
./harness/run.sh transport-classify
./harness/run.sh tool-surface
./harness/run.sh resource-gate advise --current-parallel 1 --memory-threshold 85
./harness/run.sh soak-monitor status --contract /path/task.json --evidence-dir /path/evidence --expected-pid 1234 --stop-file /path/stop.monitor
./harness/run.sh async-io-rescue status --runtime-status /path/output/fanout_runtime_status.json --session-name default --evidence-dir /path/evidence
./harness/run.sh completion-check --mode formal --require-file validation::/path/validation.csv,min_rows=1,max_age_h=24
```

On Windows PowerShell:

```powershell
.\harness\run.ps1 doctor
.\harness\run.ps1 doctor --expect-client codex
.\harness\run.ps1 transport-classify
.\harness\run.ps1 tool-surface
.\harness\run.ps1 resource-gate advise --current-parallel 1 --memory-threshold 85
.\harness\run.ps1 completion-check --mode formal --require-file validation::C:\path\validation.csv,min_rows=1,max_age_h=24
```

The harness writes JSON evidence under `<USER_HOME>\.clauder_workbench\evidence`, following [evidence.schema.json](schemas/evidence.schema.json), and returns stable exit codes: `0 PASS`, `2 WARN`, `3 BLOCK`, `4 TRANSPORT_UNSTABLE`, `5 CONTRACT_FAILED`.

Formal completion must pass `completion-check`. Completion evidence can be supplied through `--contract task.yaml` or CLI flags such as `--require-file`, `--require-transport-class`, `--require-preflight`, `--state-file`, and `--require-resource-gate`.

Formal soak completion should also require a fresh matching `soak_monitor` PASS
with `--require-soak-monitor`. The monitor uses an independent MCP stdio
heartbeat and records `extra.monitored_transport=NATIVE_MCP_OK`; it never
substitutes for the agent-native smoke chain.

For async long jobs, use the two-step hook:

```powershell
.\harness\run.ps1 async-guard pre-submit --task-key <task> --io-mode durable_files
# agent performs the real execute_r_async call through its approved transport
.\harness\run.ps1 async-guard register-job --task-key <task> --job-id <real_job_id>
```

`async-guard submit --via-mcp-stdio --code-file <R>` is diagnostic MCP stdio mode only. Do not report it as native `mcp__r_studio__` wrapper execution.

For native-wrapper long jobs, prove the current agent tool layer first with the
two-step `native-smoke` gate. The harness does **not** call the native wrapper
itself; the agent must run the real `mcp__r_studio__` tools and register their
outputs:

```powershell
.\harness\run.ps1 native-smoke start --task-key <task> --session-name default --agent codex --require-raw-file
# agent-native calls: list_sessions, execute_r, execute_r_async, get_async_result
.\harness\run.ps1 native-smoke record --task-key <task> --step list_sessions --ok --session-name default --raw-file <list_sessions_raw.txt>
.\harness\run.ps1 native-smoke record --task-key <task> --step execute_r --ok --marker NATIVE_EXECUTE_OK --pid <R_PID> --raw-file <execute_r_raw.txt>
.\harness\run.ps1 native-smoke record --task-key <task> --step execute_r_async --ok --job-id <JOB_ID> --raw-file <execute_r_async_raw.txt>
.\harness\run.ps1 native-smoke record --task-key <task> --step get_async_result --ok --job-id <JOB_ID> --marker NATIVE_ASYNC_DONE --raw-file <get_async_result_raw.txt>
.\harness\run.ps1 native-smoke complete --task-key <task>
```

`native-smoke complete` writes `transport_class=NATIVE_MCP_OK`. Python MCP
stdio evidence, HTTP fallback, or hand-written JSON must not be used as this
native parent evidence. In high-assurance mode, every record evidence id is
chained into the final parent evidence list, and each raw output file is hashed
and copied under `<USER_HOME>\.clauder_workbench\evidence\raw`.

### Parallel Async Fan-out

Run many independent R workers from one RStudio session and gate the autonomous merge. Each worker writes `state_<id>.json`, `manifest_<id>.csv`, and `validation_<id>.csv` into `output_root`; the harness polls those durable files. Full contract schema and rules are in [parallel-async-fanout.md](references/parallel-async-fanout.md).

```powershell
.\harness\run.ps1 fanout-plan --contract task.yaml                          # validate + parallelism advice
.\harness\run.ps1 fanout-run  --contract task.yaml --max-parallel 3 --first-artifact-timeout-min 10
.\harness\run.ps1 fanout-poll --contract task.yaml                          # for native-wrapper submissions
.\harness\run.ps1 merge-gate  --contract task.yaml                          # final all-workers-complete gate
```

`fanout-run` submits via an independent Python MCP stdio client and labels evidence `MCP_STDIO_OK`; it BLOCKs `--transport native-wrapper`. For native-wrapper fan-out, use `fanout-plan` to emit each worker's submit code, submit it via your own wrapper, record real job ids with `async-guard register-job`, then poll with `fanout-poll`/`merge-gate`. Stale prior-run outputs do not count unless you pass `--reuse-existing` (resume) or the worker output is within `artifacts.max_age_h`.

Every `fanout-run` polling cycle atomically refreshes
`<output_root>/fanout_runtime_status.json` and prints a flushed
`FANOUT_PROGRESS` line containing the original job ids and the
done/running/pending/failed counts. An agent task whose native wrapper was not
registered when the task started may explicitly use `--defer-native-smoke`
after a real MCP stdio probe. This compute-first escape hatch is identical on
Windows and macOS: evidence is marked `NATIVE-SMOKE-DEFERRED`, never
`NATIVE_MCP_OK`, and strict completion still requires a fresh four-step native
smoke. Do not use this flag to hide a failed wrapper or to claim final success.

ClaudeR `0.14.1.9001` and later route async stdout/stderr to temporary files,
so verbose jobs cannot block on undrained process pipes. For jobs already
started by an older package, `async-io-rescue run` drains only the original job
IDs present in `fanout_runtime_status.json`. It keeps one MCP stdio connection
open, follows newly admitted original IDs, and records append-only logs plus a
durable checkpoint. It never submits, cancels, or resumes a job:

```bash
clauder-workbench async-io-rescue run \
  --runtime-status /path/output/fanout_runtime_status.json \
  --session-name default \
  --evidence-dir /path/evidence
```

### Transport Evidence Boundary

- Native `mcp__r_studio__` wrapper: current agent tool-layer evidence only. A Python harness cannot directly call this wrapper; require parent evidence from a real wrapper smoke before claiming native-wrapper success.
- Python MCP stdio: independent MCP probe against the configured `clauder-mcp` server. Valid MCP evidence, but label it `MCP_STDIO_OK`, not native wrapper success.
- HTTP fallback: diagnostic only for MCP-only tasks. It can prove the Addin HTTP server is alive, not that MCP/native wrapper is healthy.
- `Rscript`/`Rscript.exe`: offline R process only. It never proves RStudio/ClaudeR/MCP readiness.

`transport-classify` ignores agent-supplied `--native-ok`, `--mcp-stdio-ok`, `--http-ok`, and `--rscript-ok` hints unless `--allow-agent-hints` is explicitly passed for diagnostic/test use.

### MCP Launch Stability

Stable installs must launch Codex `r-studio` through a persistent executable installed from the local LZHS ClaudeR fork:

```toml
[mcp_servers.r-studio]
command = "/Users/<USER>/.local/bin/clauder-mcp"
startup_timeout_sec = 180.0

[mcp_servers.r-studio.env]
HOME = "/Users/<USER>"
PYTHONIOENCODING = "utf-8"
NO_PROXY = "127.0.0.1,localhost"
UV_CACHE_DIR = "/Users/<USER>/Library/Caches/uv"
```

On macOS, `install.sh --configure-codex` installs that executable with
`uv tool install --force --from <USER_HOME>/projects/ClaudeR/clauder-mcp
clauder-mcp`. Windows uses `install.ps1 -ConfigureCodex`,
`clauder-mcp.exe`, `USERPROFILE`, and a Windows uv cache path. The local Mac
candidate is the user-maintained fork branch based on upstream ClaudeR `0.14.1`
and MCP bridge `0.14.5`. Never use bare `uvx clauder-mcp` or bare
`uv tool install clauder-mcp`; those can resolve to PyPI/upstream and drop the
fork compatibility changes.

The macOS/Linux installer keeps all runtime skill backups by default. Use
`--backup-retention 0` to make that policy explicit; pass a positive number only
when older backup pruning is intended.

Cold start means every MCP launch asks `uvx --from ...` to resolve/build before serving JSON-RPC. Warm start means the uv cache helps but the launch still goes through `uvx`. Hot/persistent start means Codex launches `clauder-mcp` (`clauder-mcp.exe` on Windows) directly. Long async/fan-out tasks require the hot path plus a native smoke in the current tool layer.

## Core Workflow

1. **Connect**
   - Confirm the active RStudio session with `list_sessions`.
   - Bind explicitly with `connect_session("<session>")` when multiple sessions exist.
   - Verify the target with a short `execute_r("cat(Sys.getpid(), '\\n')")`.

2. **Run**
   - Use `execute_r` for short work.
   - Use `execute_r_async` for work likely to exceed 25 seconds.
   - Poll the same `job_id` with `get_async_result`; do not resubmit a job just because it is still `running`.
   - For multi-minute work, put `clauder_progress(stage, message)` markers inside the R code.

3. **Parallel discipline**
   - Async jobs keep the main session available, but default parallel work should be lightweight and read-only.
   - Do not mutate objects named in async `outputs` while the job is running.
   - Do not write the same files or directories from another task while the async job is running.
   - Prefer a second RStudio session for substantial work by another agent.

4. **Verify**
   - A finished command is not automatically a correct result.
   - Check returned objects, output files, logs, and expected dimensions/counts before reporting completion.
   - For formal deliverables, report durable evidence paths, not only console output.

## Required Safety Rules

- **Windows multi-session warning**: do not trust a ClaudeR build whose stale discovery cleanup uses `tools::pskill(pid, signal = 0)` as a liveness probe. Use a patched build with a read-only PID check.
- Before native-wrapper work, run `clauder-workbench doctor --expect-client codex --check-toml-parse`; BLOCK if the Codex MCP entry is not the persistent absolute executable, is missing `startup_timeout_sec` or `UV_CACHE_DIR`, or lacks local fork provenance.
- A Codex native-wrapper long job is ready only after `native-smoke complete` records `list_sessions`, `execute_r`, and a short `execute_r_async -> get_async_result` smoke test from the current Codex tool layer.
- A formal soak is complete only when its recoverable `soak-monitor` evidence also passes the schedule, latency, resource, state-gap, and restart-budget checks.
- HTTP fallback can diagnose whether the Addin HTTP server is alive, but it is not MCP-only success evidence.
- If a Codex direct wrapper returns `Transport closed`, treat it as a failed native gate: run the doctor/provenance check, prewarm or reinstall the persistent entry, and retry the native smoke. Do not ask the user to repeatedly restart Codex as the primary recovery path.
- After changing ClaudeR source, R package installation, or MCP config, restart the relevant agent/MCP process. Running agents may not hot-load changes.

## Compatible Release

This skill collection release `v0.6.1` is paired with the
`lzhs1995/ClaudeR` local fork branch `0.14.1.9001`, based on upstream ClaudeR `0.14.1`, and MCP
bridge `0.14.5`. The collection includes this workbench skill and the companion
`cmaverse-paired-mval` and `comparegroups-guide` skills.

Do not use `v0.2.3` for `install.ps1 -ConfigureCodex`: it can corrupt
`<USER_HOME>\.codex\config.toml` when existing Codex project entries contain
non-ASCII paths. `v0.2.4` is the minimum safe release because it writes UTF-8
without BOM and validates TOML after writing. Releases after `v0.2.4`, including
`v0.3.4`, `v0.4.1`, `v0.4.2`, `v0.4.3`, `v0.4.4`, `v0.4.5`, `v0.4.6`, `v0.5.0`, `v0.6.0`, and `v0.6.1`
inherit that
config-writer fix.
