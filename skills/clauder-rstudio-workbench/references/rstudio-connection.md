# RStudio Connection

## Recommended Codex MCP Config

Use the patched ClaudeR bridge from a local clone:

```toml
[mcp_servers.r-studio]
command = "uvx"
args = ["--from", "<USER_HOME>\\projects\\ClaudeR\\clauder-mcp", "clauder-mcp"]

[mcp_servers.r-studio.env]
USERPROFILE = "<USER_HOME>"
PYTHONIOENCODING = "utf-8"
NO_PROXY = "127.0.0.1,localhost"
```

The same release can also run from Git:

```text
uvx --from git+https://github.com/lzhs1995/ClaudeR.git@v0.2.0-lzhs.1#subdirectory=clauder-mcp clauder-mcp
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
<USER_HOME>\.claude_r_sessions
```

If `list_sessions` is empty, check that `USERPROFILE` in the MCP environment points to the real user home where R writes discovery files.
