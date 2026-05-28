# Install Smoke Transcript

This file records the portable smoke checks expected before sharing a release. It intentionally omits private project logs and machine-specific research paths.

## v0.1.1 Local Rehearsal

Environment:

- Windows PowerShell
- R installed and discoverable as `R.exe`
- Git and `uvx` available on `PATH`
- Test root: temporary directory outside the repository

Commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -DryRun -ConfigureCodex
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -ClaudeRDir <TEMP>\ClaudeR `
  -CodexHome <TEMP>\codex-home `
  -LogFile <TEMP>\clauder_install.log
uvx --from <TEMP>\ClaudeR\clauder-mcp clauder-mcp --help
```

Expected results:

- ClaudeR fork tag `v0.2.0-lzhs.1` is cloned or checked out.
- `R CMD INSTALL <TEMP>\ClaudeR` exits with code 0.
- Skill files are copied to `<TEMP>\codex-home\skills\clauder-rstudio-workbench`.
- `uvx --from <TEMP>\ClaudeR\clauder-mcp clauder-mcp --help` exits with code 0.
- Re-running the installer leaves exactly one `[mcp_servers.r-studio]` block and one `[mcp_servers.r-studio.env]` block.
- No real local user paths, unpublished project directories, or API keys are present in the published repository.

Observed on 2026-05-28:

- Two consecutive installer runs passed against an isolated temporary Codex home.
- Codex TOML idempotence check returned `mainCount=1 envCount=1`.
- Local `uvx --from <TEMP>\ClaudeR\clauder-mcp clauder-mcp --help` returned the `clauder-mcp` help text.

## MCP Runtime Smoke

After restarting the MCP client and RStudio:

```text
list_sessions
connect_session("<session>")
execute_r("cat('MCP_SYNC_OK\n')")
execute_r_async("<short R job with clauder_progress(stage, message)>")
get_async_result("<job_id>")
```

Expected results:

- `execute_r` returns from the live RStudio session.
- `get_async_result` reaches `complete`.
- Final output contains `Latest progress:` or final progress fields with `stage`, `message`, and `updated_at`.
- The async job output is loaded back into the RStudio session when outputs are requested.
