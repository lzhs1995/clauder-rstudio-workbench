---
name: native-mcp-gate
description: Executable native MCP smoke gate and Transport closed recovery order.
---

# Native MCP Gate

Use this gate before formal long-running RStudio work that claims the agent's
native `mcp__r_studio__` wrapper path. The Python harness cannot call the native
wrapper directly. It can only record and validate evidence produced by the
agent tool layer.

## Required sequence

```powershell
clauder-workbench doctor --expect-client codex --check-toml-parse
clauder-workbench native-smoke start --task-key <task> --session-name default --agent codex --require-raw-file
```

Then the agent must use the real native MCP tools:

1. `list_sessions`
2. `execute_r` with a short marker such as `NATIVE_EXECUTE_OK`
3. `execute_r_async` with a short async marker job
4. `get_async_result` for the same `job_id`

Record each result:

```powershell
clauder-workbench native-smoke record --task-key <task> --step list_sessions --ok --session-name default --raw-file <list_sessions_raw.txt>
clauder-workbench native-smoke record --task-key <task> --step execute_r --ok --marker NATIVE_EXECUTE_OK --pid <R_PID> --raw-file <execute_r_raw.txt>
clauder-workbench native-smoke record --task-key <task> --step execute_r_async --ok --job-id <JOB_ID> --raw-file <execute_r_async_raw.txt>
clauder-workbench native-smoke record --task-key <task> --step get_async_result --ok --job-id <JOB_ID> --marker NATIVE_ASYNC_DONE --raw-file <get_async_result_raw.txt>
clauder-workbench native-smoke complete --task-key <task>
```

The final evidence must have:

- `harness_name = native_smoke`
- `decision = PASS`
- `transport_class = NATIVE_MCP_OK`
- the same `task_key` as the long job contract
- four non-empty `parent_evidence_ids` from the four record steps
- raw output hashes and evidence copies for all recorded `--raw-file` values

## What does not count

- `fanout-run` Python MCP stdio evidence (`MCP_STDIO_OK`)
- HTTP fallback evidence
- `Rscript.exe` evidence
- a hand-written JSON file
- native-smoke records missing the real async `job_id`

## Worked example: addin-transient on first async submit

A real native-smoke run produced this sequence: `list_sessions` ok →
`execute_r` ok (`NATIVE_EXECUTE_OK`) → first `execute_r_async` returned
`RStudio addin is not running`. That error is a **native layer transient**, not a
`Transport closed`, and not a reason to restart the agent. The correct handling
is to **retry `execute_r_async` on the same native layer**; the retry returned a
real `job_id` and `get_async_result` later carried `NATIVE_ASYNC_RETRY_DONE`.
Record only the successful retry:

```powershell
clauder-workbench native-smoke record --task-key <task> --step execute_r_async --ok --job-id <REAL_JOB_ID>
clauder-workbench native-smoke record --task-key <task> --step get_async_result --ok --job-id <REAL_JOB_ID> --marker NATIVE_ASYNC_RETRY_DONE
```

This is exactly the failure the gate is meant to catch before a long fan-out:
surface the transient on a 2-second async job, not on a multi-GB worker.

For maximum assurance, and for formal CMAverse fan-out work, use
`--require-raw-file` on `native-smoke start` and pass `--raw-file <dump.txt>` on
every `record`; the harness then verifies each marker actually appears inside
the dumped native tool output, so a step cannot be fabricated from a
self-reported string alone.

## High-assurance mode (--require-raw-file)

```powershell
clauder-workbench native-smoke start --task-key <task> --session-name default --agent codex --require-raw-file
clauder-workbench native-smoke record --task-key <task> --step execute_r --ok --marker NATIVE_EXECUTE_OK --pid <R_PID> --raw-file <execute_r_output.txt>
```

In this mode any `record` without `--raw-file` is BLOCKed, and a `--marker` that
is absent from the raw file is BLOCKed. Use `--agent codex|claude|copilot` so the
final `NATIVE_MCP_OK` evidence records which agent produced it (multi-agent
provenance); if omitted, the agent is inferred from the native tool layer.
v0.3.3 and later also copy each raw file into the evidence tree and store
`sha256`, `size_bytes`, and `mtime_utc`. A final `complete` without one parent
record evidence id per native step is BLOCKed; rerun old v0.3.2 smoke states
rather than trying to complete them after upgrading.

## Transport closed recovery order

Do not ask the user to restart Codex first. Use this order:

1. Run `clauder-workbench doctor --expect-client codex --check-toml-parse`.
2. Confirm Codex config uses `<USER_HOME>\.local\bin\clauder-mcp.exe`,
   `startup_timeout_sec = 180.0`, `UV_CACHE_DIR`, and LZHS fork provenance.
3. Re-run installer with `install.ps1 -ConfigureCodex` if the config still uses
   `uvx` or bare `clauder-mcp`.
4. Run the native-smoke sequence above.
5. Only if the configured persistent entry is correct and repeated native-smoke
   attempts still fail should the user restart the agent.

