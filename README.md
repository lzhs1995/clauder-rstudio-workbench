# clauder-rstudio-workbench

Portable Codex skill, executable harness, and installer for using a patched ClaudeR build as an RStudio workbench through MCP.

This repository pairs with the ClaudeR fork release `lzhs1995/ClaudeR@v0.2.0-lzhs.1`.

**Platform status:** v0.2.x is Windows-first. macOS/Linux installation scripts are not included yet.

## What This Installs

- The patched ClaudeR R package from `https://github.com/lzhs1995/ClaudeR`.
- The `clauder-rstudio-workbench` Codex skill under `<CODEX_HOME>/skills`.
- The `clauder_workbench` Python harness package for doctor, transport classification, async guard, resource gate, and completion gate checks.
- Optional MCP configuration for Codex, Claude Code, or GitHub Copilot CLI.

The installer is Windows-first. It does not modify MCP client configuration unless you pass an explicit `-Configure...` switch.

## Quick Start

Open PowerShell:

```powershell
git clone --branch v0.2.0 https://github.com/lzhs1995/clauder-rstudio-workbench.git "$env:USERPROFILE\projects\clauder-rstudio-workbench"
cd "$env:USERPROFILE\projects\clauder-rstudio-workbench"
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ConfigureCodex
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
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -DryRun -ConfigureCodex
```

Use `-SkipHarness` only when you want to install the Markdown skill without the executable Python gate.

## Install Choices

Use one MCP configuration path at a time:

- **Recommended for colleagues:** run this repository's `install.ps1` and pass one explicit configuration switch such as `-ConfigureCodex`.
- **Alternative for ClaudeR developers:** run `library(ClaudeR); install_cli(..., mcp_from = "local")` from the ClaudeR package.

Do not run both paths blindly. If both are used, the last writer wins and may replace the previous `r-studio` MCP block.

Installer prerequisites:

- Git for Windows: `winget install --id Git.Git -e`
- uv/uvx: `winget install --id astral-sh.uv -e`
- R installed with `R.exe` available, or pass `-RExe "C:\Program Files\R\R-x.y.z\bin\R.exe"`.
- Claude Code CLI is required only when using `-ConfigureClaudeCode`.

## Compatibility

| Skill | ClaudeR fork | Notes |
|---|---|---|
| `v0.2.0` | `v0.2.0-lzhs.1` | Adds executable harnesses, evidence schema, transport classification, async guard, resource gate, completion gate, and distributable Python configuration. |
| `v0.1.2` | `v0.2.0-lzhs.1` | Adds safer skill replacement, Claude Code MCP verification, release dates, feature request template, and real smoke transcript. |
| `v0.1.1` | `v0.2.0-lzhs.1` | Adds installer preflight, troubleshooting, issue templates, and idempotent Codex config rewrite. |
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
6. For formal completion, run the harness gate, for example:

```powershell
.\skills\clauder-rstudio-workbench\harness\run.ps1 completion-check --mode formal --require-file "validation::C:\out\validation.csv,min_rows=1,max_age_h=24"
```

Harness evidence is written to `<USER_HOME>\.clauder_workbench\evidence`.

For the installer smoke transcript format, see `tests/install_smoke.md`.

Current validation status:

- Local Windows install, reinstall idempotence, and privacy scan have passed.
- A git-subdirectory MCP runtime smoke has passed when a live RStudio ClaudeR Addin session is available.
- A clean-VM or colleague-machine validation remains the final gate before broad rollout.

## Troubleshooting

### `uvx` is not found

Install uv and restart PowerShell:

```powershell
winget install --id astral-sh.uv -e
```

### PowerShell blocks `install.ps1`

Use process-scoped bypass instead of changing machine policy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ConfigureCodex
```

### MCP config does not appear after install

Restart the client. Codex, Claude Code, and Copilot CLI do not reliably hot-load MCP config changes.

### Codex shows `Transport closed`

Treat this as a transport-layer failure until proven otherwise. Check that RStudio is open, `library(ClaudeR); claudeAddin()` is running, and the discovery session appears. If HTTP/Addin is alive but the Codex native wrapper is stale, restart Codex before rerunning a long job.

### Windows opens a second RStudio session and the first one aborts

Do not use an unpatched ClaudeR build whose stale discovery cleanup uses `tools::pskill(pid, signal = 0)`. Install `lzhs1995/ClaudeR@v0.2.0-lzhs.1` or later, restart RStudio, then rerun a multi-session safety check before trusting concurrent sessions.

### `Latest progress:` does not appear

Confirm all three layers:

1. The R code includes `clauder_progress(stage, message)` markers.
2. RStudio has loaded the patched ClaudeR package after reinstall/restart.
3. The MCP command points to the patched local bridge, not plain `uvx clauder-mcp`.

## Upgrade

To upgrade the skill and reinstall the paired ClaudeR release:

```powershell
cd "$env:USERPROFILE\projects\clauder-rstudio-workbench"
git fetch --tags
git checkout v0.2.0
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ConfigureCodex
```

If you configured Claude Code or Copilot CLI, pass the corresponding `-Configure...` switch again.

## What Is Not Included

- No private dissertation scripts or logs.
- No machine-specific paths.
- No API keys.
- No full validation log. Only a short portable smoke transcript is included because the complete validation history contains local project context.
- No PyPI publication for the forked `clauder-mcp`.
- No upstream PR bundle; upstream contributions should be split later.

## Agent Metadata

The packaged skill includes `agents/openai.yaml` for Codex skill UI metadata. Claude Code and Copilot CLI use MCP configuration rather than Codex skill metadata in this release.
