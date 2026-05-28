# Install Smoke Transcript

This file records sanitized smoke evidence for the public sharing package. Private user paths are replaced with `<USER_HOME>`, `<TEMP>`, or `<REPO>`.

## v0.1.2 Local Rehearsal

Observed: 2026-05-29 Asia/Shanghai

Environment:

- Windows PowerShell
- R available as `R.exe`
- Git and `uvx` available on `PATH`
- Test root: `<TEMP>\clauder_share_v012_test`

### Dry Run

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <REPO>\install.ps1 -DryRun -ConfigureCodex
```

Key output:

```text
==> Checking prerequisites
R.exe: <R_HOME>\bin\x64\R.exe
git: <GIT_HOME>\cmd\git.exe
uvx: <USER_HOME>\.local\bin\uvx.exe

==> Installing Codex skill
Would copy backup <USER_HOME>\.codex\skills\clauder-rstudio-workbench -> <USER_HOME>\.codex\skills\clauder-rstudio-workbench_bak_<timestamp>
Would stage new skill <REPO>\skills\clauder-rstudio-workbench -> <USER_HOME>\.codex\skills\clauder-rstudio-workbench_staging_<timestamp>
Would replace <USER_HOME>\.codex\skills\clauder-rstudio-workbench with staged skill and keep backup
```

### Isolated Install and Reinstall

Commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <REPO>\install.ps1 `
  -ClaudeRDir <TEMP>\ClaudeR `
  -CodexHome <TEMP>\codex-home `
  -ConfigureCodex `
  -LogFile <TEMP>\clauder_install_first.log

powershell -NoProfile -ExecutionPolicy Bypass -File <REPO>\install.ps1 `
  -ClaudeRDir <TEMP>\ClaudeR `
  -CodexHome <TEMP>\codex-home `
  -ConfigureCodex `
  -LogFile <TEMP>\clauder_install_second.log
```

Key output:

```text
+ git clone --branch v0.2.0-lzhs.1 https://github.com/lzhs1995/ClaudeR.git <TEMP>\ClaudeR
+ <R_HOME>\bin\x64\R.exe CMD INSTALL <TEMP>\ClaudeR
* DONE (ClaudeR)

==> Installing Codex skill
Staging new skill <REPO>\skills\clauder-rstudio-workbench -> <TEMP>\codex-home\skills\clauder-rstudio-workbench_staging_<timestamp>
Installed skill to <TEMP>\codex-home\skills\clauder-rstudio-workbench

==> Installing Codex skill
Staging new skill <REPO>\skills\clauder-rstudio-workbench -> <TEMP>\codex-home\skills\clauder-rstudio-workbench_staging_<timestamp>
Copying backup <TEMP>\codex-home\skills\clauder-rstudio-workbench -> <TEMP>\codex-home\skills\clauder-rstudio-workbench_bak_<timestamp>
Installed skill to <TEMP>\codex-home\skills\clauder-rstudio-workbench

mainCount=1 envCount=1 firstBytes=239,187 backupCount=1
```

Notes:

- `mainCount=1 envCount=1` confirms repeated installer runs do not accumulate duplicate Codex MCP blocks.
- `firstBytes=239,187` is the UTF-8 BOM written by PowerShell, not a leading blank line.
- `backupCount=1` confirms the existing skill directory was copied to backup before replacement.

### Local `uvx --from` Check

Command:

```powershell
uvx --from <TEMP>\ClaudeR\clauder-mcp clauder-mcp --help
```

Key output:

```text
usage: clauder-mcp [-h] [--agent-id AGENT_ID]

R Studio MCP Server

options:
  -h, --help           show this help message and exit
  --agent-id AGENT_ID  Unique identifier for this agent instance
```

## Git-Subdirectory MCP Runtime Smoke

Observed: 2026-05-29 Asia/Shanghai

Command under test:

```text
uvx --from git+https://github.com/lzhs1995/ClaudeR.git@v0.2.0-lzhs.1#subdirectory=clauder-mcp clauder-mcp
```

MCP client protocol:

- newline-delimited JSON-RPC, not `Content-Length` framing
- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call` with `name = "list_sessions"`

Key output:

```text
initialize_ok= True
tools= execute_r,execute_r_with_plot,get_r_info,get_active_document,modify_code_section,insert_text,create_task_list,update_task_status,clean_error_log,execute_r_async,get_async_result,cancel_async_job,list_sessions,connect_session,read_file,search_project_code,probe_scripts,verify_references,get_viewer_content,get_session_history,run_annotation_job,get_annotation_job_status,cancel_annotation_job,load_annotation_data,annotate
list_sessions_response= Active R sessions (1):
  <SESSION> -- port 8787, pid <PID>, started <timestamp> (connected)
```

Result:

- `git+...#subdirectory=clauder-mcp` starts the MCP server.
- `tools/list` exposes `list_sessions`.
- `list_sessions` returns live RStudio session metadata including port and PID.

## Remaining External Gate

This transcript is local-machine evidence. A clean-VM or colleague-machine install remains required before broad public rollout.
