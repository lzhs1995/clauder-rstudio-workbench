---
name: clauder-rstudio-workbench
description: Use when an agent needs to connect to a live RStudio session through ClaudeR, configure or verify the r-studio MCP bridge, run R code safely, poll long async jobs with progress, or avoid multi-session and multi-agent conflicts.
---

# ClaudeR RStudio Workbench

This skill is the operating protocol for using ClaudeR as a live RStudio workbench from Codex, Claude Code, GitHub Copilot CLI, or another MCP-capable agent. It is not a statistics reference; combine it with an R analysis skill for modeling decisions.

> **Headline capability:** async polling lets one RStudio session drive N child R worker processes at once and merge the results autonomously. See [parallel-async-fanout.md](references/parallel-async-fanout.md) and the Parallel Async Fan-out section below.

## First Reads

- Before formal long-running RStudio work, run the executable harness layer below. Markdown is advisory; harness evidence is the completion gate.
- For connection setup and MCP routing, read [rstudio-connection.md](references/rstudio-connection.md).
- For long jobs, read [async-long-jobs.md](references/async-long-jobs.md).
- For running many parallel R workers from one session, read [parallel-async-fanout.md](references/parallel-async-fanout.md).
- For tool selection, read [clauder-tool-map.md](references/clauder-tool-map.md).
- For completion checks, read [verification-and-recovery.md](references/verification-and-recovery.md).

## Executable Harness Layer

Use these commands from this skill directory or after `install.ps1` installs the editable Python package:

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

For async long jobs, use the two-step hook:

```powershell
.\harness\run.ps1 async-guard pre-submit --task-key <task> --io-mode durable_files
# agent performs the real execute_r_async call through its approved transport
.\harness\run.ps1 async-guard register-job --task-key <task> --job-id <real_job_id>
```

`async-guard submit --via-mcp-stdio --code-file <R>` is diagnostic MCP stdio mode only. Do not report it as native `mcp__r_studio__` wrapper execution.

### Parallel Async Fan-out

Run many independent R workers from one RStudio session and gate the autonomous merge. Each worker writes `state_<id>.json`, `manifest_<id>.csv`, and `validation_<id>.csv` into `output_root`; the harness polls those durable files. Full contract schema and rules are in [parallel-async-fanout.md](references/parallel-async-fanout.md).

```powershell
.\harness\run.ps1 fanout-plan --contract task.yaml                          # validate + parallelism advice
.\harness\run.ps1 fanout-run  --contract task.yaml --max-parallel 3 --first-artifact-timeout-min 10
.\harness\run.ps1 fanout-poll --contract task.yaml                          # for native-wrapper submissions
.\harness\run.ps1 merge-gate  --contract task.yaml                          # final all-workers-complete gate
```

`fanout-run` submits via an independent Python MCP stdio client and labels evidence `MCP_STDIO_OK`; it BLOCKs `--transport native-wrapper`. For native-wrapper fan-out, use `fanout-plan` to emit each worker's submit code, submit it via your own wrapper, record real job ids with `async-guard register-job`, then poll with `fanout-poll`/`merge-gate`. Stale prior-run outputs do not count unless you pass `--reuse-existing` (resume) or the worker output is within `artifacts.max_age_h`.

### Transport Evidence Boundary

- Native `mcp__r_studio__` wrapper: current agent tool-layer evidence only. A Python harness cannot directly call this wrapper; require parent evidence from a real wrapper smoke before claiming native-wrapper success.
- Python MCP stdio: independent MCP probe against the configured `clauder-mcp` server. Valid MCP evidence, but label it `MCP_STDIO_OK`, not native wrapper success.
- HTTP fallback: diagnostic only for MCP-only tasks. It can prove the Addin HTTP server is alive, not that MCP/native wrapper is healthy.
- `Rscript.exe`: offline R process only. It never proves RStudio/ClaudeR/MCP readiness.

`transport-classify` ignores agent-supplied `--native-ok`, `--mcp-stdio-ok`, `--http-ok`, and `--rscript-ok` hints unless `--allow-agent-hints` is explicitly passed for diagnostic/test use.

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
- A Codex native-wrapper long job is ready only after `list_sessions`, `execute_r`, and a short `execute_r_async -> get_async_result` smoke test pass in the current Codex tool layer.
- HTTP fallback can diagnose whether the Addin HTTP server is alive, but it is not MCP-only success evidence.
- If a Codex direct wrapper returns `Transport closed`, test the same configured server command through MCP stdio before blaming RStudio.
- After changing ClaudeR source, R package installation, or MCP config, restart the relevant agent/MCP process. Running agents may not hot-load changes.

## Compatible Release

This skill collection release `v0.3.0` is paired with
`lzhs1995/ClaudeR@v0.2.0-lzhs.1`. The collection includes this workbench skill
and the companion `cmaverse-paired-mval` skill.

Do not use `v0.2.3` for `install.ps1 -ConfigureCodex`: it can corrupt
`<USER_HOME>\.codex\config.toml` when existing Codex project entries contain
non-ASCII paths. `v0.2.4` is the minimum safe release because it writes UTF-8
without BOM and validates TOML after writing. Releases after `v0.2.4`, including
`v0.3.0`, inherit that config-writer fix.
