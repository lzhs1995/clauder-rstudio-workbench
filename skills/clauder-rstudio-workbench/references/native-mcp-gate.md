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
clauder-workbench native-smoke start --task-key <task> --session-name default
```

Then the agent must use the real native MCP tools:

1. `list_sessions`
2. `execute_r` with a short marker such as `NATIVE_EXECUTE_OK`
3. `execute_r_async` with a short async marker job
4. `get_async_result` for the same `job_id`

Record each result:

```powershell
clauder-workbench native-smoke record --task-key <task> --step list_sessions --ok --session-name default
clauder-workbench native-smoke record --task-key <task> --step execute_r --ok --marker NATIVE_EXECUTE_OK --pid <R_PID>
clauder-workbench native-smoke record --task-key <task> --step execute_r_async --ok --job-id <JOB_ID>
clauder-workbench native-smoke record --task-key <task> --step get_async_result --ok --job-id <JOB_ID> --marker NATIVE_ASYNC_DONE
clauder-workbench native-smoke complete --task-key <task>
```

The final evidence must have:

- `harness_name = native_smoke`
- `decision = PASS`
- `transport_class = NATIVE_MCP_OK`
- the same `task_key` as the long job contract

## What does not count

- `fanout-run` Python MCP stdio evidence (`MCP_STDIO_OK`)
- HTTP fallback evidence
- `Rscript.exe` evidence
- a hand-written JSON file
- native-smoke records missing the real async `job_id`

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

