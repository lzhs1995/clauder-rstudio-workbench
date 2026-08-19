# ClaudeR Tool Map

| Task | Tool | Notes |
|---|---|---|
| List sessions | `list_sessions` | First connection check. |
| Bind session | `connect_session` | Use when multiple RStudio sessions exist. |
| Short R code | `execute_r` | Use for quick checks and object inspection. |
| Plotting | `execute_r_with_plot` | Use when plot inspection matters. |
| Long R code | `execute_r_async` | Returns a `job_id`; poll later. |
| Poll async job | `get_async_result` | `running` is not failure. |
| Cancel async job | `cancel_async_job` | Inspect durable output paths after cancellation. |
| Read file | `read_file` | Prefer for large scripts/logs instead of dumping through R. |
| Session history | `get_session_history` | Useful in shared sessions. |

## Route Boundaries

- Native `mcp__r_studio__` wrappers are the preferred Codex route when available.
- MCP stdio against the same `clauder-mcp` command is still MCP transport, but label it separately from native wrappers.
- HTTP fallback is diagnostic only for MCP-only tasks.
- `Rscript` (`Rscript.exe` on Windows) is useful for offline package tests but does not prove RStudio MCP readiness.
