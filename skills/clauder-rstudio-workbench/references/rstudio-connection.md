# RStudio Connection

## Recommended Codex MCP Config

Use the persistent patched ClaudeR bridge installed from the local clone:

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

On Windows the command is
`<USER_HOME>\\.local\\bin\\clauder-mcp.exe`, the home variable is
`USERPROFILE`, and the uv cache uses a Windows path.

For development diagnostics only, the bridge can run from the local source:

```text
uvx --from <USER_HOME>/projects/ClaudeR/clauder-mcp clauder-mcp
```

## Startup

In RStudio:

```r
library(ClaudeR)
claudeAddin()
```

Then in the agent:

1. `list_sessions`
2. `connect_session("<target>")` when needed
3. `execute_r("cat(Sys.getpid(), '\\n')")`

## Discovery Root

ClaudeR writes session discovery files to:

```text
<USER_HOME>/.claude_r_sessions
```

If `list_sessions` is empty, check that `HOME` on macOS/Linux or `USERPROFILE`
on Windows points to the real user home where R writes discovery files.
