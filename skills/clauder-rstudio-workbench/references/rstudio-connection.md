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

## Diagnostic boundaries

Use `ensure-ready --client codex|claude|copilot --session-name <target>
--task-key <task>` for the maintained client-specific entrypoint. Default is
read-only. It checks core execution capabilities instead of requiring every
optional manuscript/annotation tool; the full inventory is still reported.
`--require-native --native-evidence <file>` additionally requires a fresh
actual native smoke for the current client process/session, config hash and
target R PID. A known-good independent stdio route cannot satisfy that flag.

Safe configuration repair is explicit (`--repair safe`). Installers preserve
other servers, custom args/env, comments in Codex TOML, and disabled flags. On
Windows the cache defaults to `%LOCALAPPDATA%/uv/cache`; macOS uses
`~/Library/Caches/uv`, Linux uses `$XDG_CACHE_HOME/uv` or `~/.cache/uv`.

The discovery lock is per record. Corrupt files and unknown-owner locks need
inspection, not automatic deletion. Reopening an already-running addin refreshes
its record without rotating its identity. Duplicate live names and a vanished
bound identity fail closed; select a unique intended session name explicitly.

`clauder-workbench doctor` is a configuration check, not proof of live R or
native agent tool registration. Use:

```text
clauder-workbench connection-diagnose --session-name <target> --probe-http
```

This performs read-only marker execution through the configured MCP bridge and,
when requested, authenticated HTTP against the explicit discovery target. It
does not submit an async job or modify research objects. Missing or ambiguous
discovery targets fail closed; HTTP errors and unrelated nonempty responses
cannot pass. Its WARN/2 with `MCP_STDIO_OK` is a diagnostic result, not native
smoke or release approval. A supplied tool-name inventory remains an observation.
