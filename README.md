# clauder-rstudio-workbench

Portable Codex skill and installer for using a patched ClaudeR build as an RStudio workbench through MCP.

This repository pairs with the ClaudeR fork release `lzhs1995/ClaudeR@v0.2.0-lzhs.1`.

## What This Installs

- The patched ClaudeR R package from `https://github.com/lzhs1995/ClaudeR`.
- The `clauder-rstudio-workbench` Codex skill under `<CODEX_HOME>/skills`.
- Optional MCP configuration for Codex, Claude Code, or GitHub Copilot CLI.

The installer is Windows-first. It does not modify MCP client configuration unless you pass an explicit `-Configure...` switch.

## Quick Start

Open PowerShell:

```powershell
git clone --branch v0.1.0 https://github.com/lzhs1995/clauder-rstudio-workbench.git "$env:USERPROFILE\projects\clauder-rstudio-workbench"
cd "$env:USERPROFILE\projects\clauder-rstudio-workbench"
.\install.ps1 -ConfigureCodex
```

Then restart Codex and start ClaudeR inside RStudio:

```r
library(ClaudeR)
claudeAddin()
```

In Codex:

```text
$clauder 连接Rstudio
```

## Dry Run

Preview changes without writing files or installing packages:

```powershell
.\install.ps1 -DryRun -ConfigureCodex
```

## Compatibility

| Skill | ClaudeR fork | Notes |
|---|---|---|
| `v0.1.0` | `v0.2.0-lzhs.1` | Async progress, async metadata, Copilot CLI setup, Windows multi-session safety. |

## MCP Command

The preferred Codex configuration points to the local cloned ClaudeR source:

```toml
[mcp_servers.r-studio]
command = "uvx"
args = ["--from", "<USER_HOME>\\projects\\ClaudeR\\clauder-mcp", "clauder-mcp"]

[mcp_servers.r-studio.env]
USERPROFILE = "<USER_HOME>"
PYTHONIOENCODING = "utf-8"
NO_PROXY = "127.0.0.1,localhost"
```

The ClaudeR release also supports Git-subdirectory execution:

```text
uvx --from git+https://github.com/lzhs1995/ClaudeR.git@v0.2.0-lzhs.1#subdirectory=clauder-mcp clauder-mcp
```

Local clone is the default installer path because it is easier to inspect, patch, and debug.

## Validation

After installation:

1. Restart Codex.
2. Start the ClaudeR Addin in RStudio.
3. Ask Codex to connect with `$clauder 连接Rstudio`.
4. Verify `list_sessions`, `execute_r`, and a short `execute_r_async -> get_async_result` smoke test.
5. For long tasks, require visible `Latest progress:` or final progress before claiming MCP async readiness.

## What Is Not Included

- No private dissertation scripts or logs.
- No machine-specific paths.
- No API keys.
- No PyPI publication for the forked `clauder-mcp`.
- No upstream PR bundle; upstream contributions should be split later.
