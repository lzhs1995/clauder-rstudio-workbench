---
name: clauder-rstudio-workbench
description: Use when an agent needs to connect to a live RStudio session through ClaudeR, configure or verify the r-studio MCP bridge, run R code safely, poll long async jobs with progress, or avoid multi-session and multi-agent conflicts.
---

# ClaudeR RStudio Workbench

This skill is the operating protocol for using ClaudeR as a live RStudio workbench from Codex, Claude Code, GitHub Copilot CLI, or another MCP-capable agent. It is not a statistics reference; combine it with an R analysis skill for modeling decisions.

## First Reads

- For connection setup and MCP routing, read [rstudio-connection.md](references/rstudio-connection.md).
- For long jobs, read [async-long-jobs.md](references/async-long-jobs.md).
- For tool selection, read [clauder-tool-map.md](references/clauder-tool-map.md).
- For completion checks, read [verification-and-recovery.md](references/verification-and-recovery.md).

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

This skill release `v0.1.1` is paired with `lzhs1995/ClaudeR@v0.2.0-lzhs.1`.
