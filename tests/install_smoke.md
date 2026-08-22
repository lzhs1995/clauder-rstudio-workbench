# Install Smoke Transcript

This file records sanitized smoke evidence for the public sharing package. Private user paths are replaced with `<USER_HOME>`, `<TEMP>`, or `<REPO>`.

## v0.4.3 macOS Candidate Source Smoke

Observed: 2026-08-22 Asia/Kolkata

Commands:

```bash
python -m unittest discover -s tests -v
uv --no-config build --wheel
clauder-workbench tool-surface
```

Local result:

- 175 Workbench tests passed, including the exact 40-tool ClaudeR 0.12.2
  compatibility surface and the existing soak-monitor fault-injection suite.
- The 0.4.3 wheel built locally and the installer dry-run selected the pinned
  ClaudeR 0.12.2 / bridge 0.14.2 worktree.
- The candidate bridge returned all 40 expected tools over MCP stdio. Installed
  doctor and native-wrapper validation are recorded outside this distributable
  transcript in the run-specific evidence directory.

## v0.4.0 macOS Candidate Smoke

Observed: 2026-08-19 Asia/Kolkata

Commands:

```bash
./install.sh --clauder-dir <USER_HOME>/projects/ClaudeR --configure-codex --sync-agents-skill --backup-retention 0
<USER_HOME>/.local/bin/clauder-workbench doctor --expect-client codex --check-toml-parse
python -m unittest discover -s tests -v
```

Local result:

- R package 0.8.1 and MCP bridge 0.10.0 installed from the local ClaudeR
  worktree; the persistent MCP command and Codex TOML parse check passed.
- Real MCP stdio preflight found the live RStudio session and exercised sync
  and async execution; this evidence is intentionally labeled `MCP_STDIO_OK`,
  not `NATIVE_MCP_OK`.
- Migrated IV, DID, RDD, balance/sensitivity, plotting, file, routing, and async
  workflows passed.
- Three async workers completed 150,000 IV bootstrap fits with stable job ids,
  visible intermediate progress, merge-gate PASS, and strict formal
  completion-check PASS.
- The original Windows package inventory was rechecked in isolated R processes:
  744 namespaces loaded, one R base component was valid, and the only missing
  packages remained Windows-only `R2wd` and R-4.6-incompatible `pryr`.

## v0.2.3 Proxy-Resilience Smoke

Observed: 2026-05-29 Asia/Shanghai

Commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <REPO>\install.ps1 -DevSync -SyncAgentsSkill -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File <REPO>\install.ps1 -DevSync -SyncAgentsSkill
& "<USER_HOME>\bin\clauder-workbench.cmd" doctor --expect-client codex
```

Expected:

- `install.ps1` exposes `-NoZipFallback` and `-InstallPython314`;
- ClaudeR git install failures can fall back to the release tag zip unless `-NoZipFallback` is set;
- `INSTALL_INFO.json` records `workbench_source_type`, `workbench_ref`, `claudeR_source_type`, `claudeR_source_url`, and `configured_clients`;
- `doctor --expect-client codex` does not warn about missing Claude Code or Copilot config;
- README documents both git clone and workbench release-asset zip bootstrap paths.

Local result:

- unit tests: `Ran 55 tests ... OK`;
- `install.ps1 -DevSync -SyncAgentsSkill -DryRun`: completed and printed zip fallback-capable installer options;
- `doctor --expect-client codex`: `PASS` or Codex-relevant `WARN` only;
- workbench zip bootstrap commands were checked against the v0.2.3 release path after publishing.

## v0.2.2 Wrapper and PATH Smoke

Observed: 2026-05-29 Asia/Shanghai

Commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <REPO>\install.ps1 -DevSync -SyncAgentsSkill -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File <REPO>\install.ps1 -DevSync -SyncAgentsSkill
& "<USER_HOME>\bin\clauder-workbench.cmd" doctor
python -m clauder_workbench doctor
```

Expected:

- installer writes `<USER_HOME>\bin\clauder-workbench.cmd`;
- `INSTALL_INFO.json` records `schema_version = 0.2.2`, the current git commit, `harness_wrapper`, `add_harness_to_path`, and `user_path_contains_wrapper_dir`;
- wrapper invocation and `python -m clauder_workbench doctor` both reach the same harness package;
- the installer does not modify the user PATH unless `-AddHarnessToPath` is explicitly passed.

Local result:

- unit tests: `Ran 50 tests ... OK`;
- `install.ps1 -DevSync -SyncAgentsSkill -DryRun`: completed without writes and printed wrapper/PATH actions;
- `install.ps1 -DevSync -SyncAgentsSkill`: synchronized both runtime skill copies and wrote wrapper metadata;
- `<USER_HOME>\bin\clauder-workbench.cmd doctor`: `PASS`;
- `python -m clauder_workbench doctor`: `PASS`.

## v0.2.1 Harness Smoke

Observed: 2026-05-29 Asia/Shanghai

Commands:

```powershell
$env:PYTHONPATH = "<REPO>\skills\clauder-rstudio-workbench"
python -m unittest discover -s <REPO>\tests -v
python -m clauder_workbench doctor
python -m clauder_workbench transport-classify --no-probe-mcp-stdio --probe-rscript
python -m clauder_workbench resource-gate advise --current-parallel 1 --memory-threshold 85
python -m clauder_workbench async-guard pre-submit --task-key smoke
python -m clauder_workbench async-guard register-job --task-key smoke --job-id <JOB_ID>
```

Expected:

- unit tests pass;
- `doctor` returns `PASS` or `WARN` with distributable `<USER_HOME>`/environment-driven paths, not hard-coded private paths;
- `transport-classify` labels Rscript-only evidence as `RSCRIPT_ONLY` and does not treat it as MCP/native success;
- `resource-gate` only recommends `increase_by_1` when memory/I/O/responsiveness/durable-output checks all pass.

Local result:

- unit tests: `Ran 48 tests ... OK`;
- `doctor`: `PASS`, discovery found session `<SESSION>` on port `<PORT>`;
- first cold `transport-classify --probe-mcp-stdio` may time out while `uvx` installs dependencies; immediate warm retry returned `MCP_STDIO_OK`;
- `tool-surface`: `PASS`, expected `list_sessions`, `connect_session`, `execute_r`, `execute_r_async`, and `get_async_result` were present;
- `completion-check`: `PASS` for a fresh validation CSV with `min_rows`, `max_age_h`, and `output_root` constraints;
- `install.ps1 -DryRun` prints harness editable install unless `-SkipHarness` is passed.
- `install.ps1 -DevSync -DryRun` skips ClaudeR reinstall and prints runtime skill/harness sync steps.

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
