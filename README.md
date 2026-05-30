# clauder-rstudio-workbench

Portable skill **collection**, executable harness, and installer for using a patched ClaudeR build as an RStudio workbench through MCP.

This repository pairs with the ClaudeR fork release `lzhs1995/ClaudeR@v0.2.0-lzhs.1`.

**Platform status:** v0.2.x/v0.3.x is Windows-first. macOS/Linux installation scripts are not included yet.

## Skills in This Collection

`install.ps1` installs every `skills/<name>/` directory that contains a `SKILL.md`:

- **`clauder-rstudio-workbench`** — core skill: connect/preflight/async-guard/resource-gate/completion gates plus the parallel **fan-out** harness (one RStudio driving N async R workers with autonomous merge).
- **`cmaverse-paired-mval`** — domain skill: a worked, executable example of the fan-out workflow for paired M=0/M=1 CMAverse bootstrap (7 mediators in parallel), with a generator and a validation gate.

## What This Installs

- The patched ClaudeR R package from `https://github.com/lzhs1995/ClaudeR`.
- Every skill in this collection under `<CODEX_HOME>/skills` (and `<AGENTS_HOME>/skills` with `-SyncAgentsSkill`).
- The `clauder_workbench` Python harness package for doctor, transport classification, async guard, fan-out, resource gate, and completion gate checks.
- Optional MCP configuration for Codex, Claude Code, or GitHub Copilot CLI.

The installer is Windows-first. It does not modify MCP client configuration unless you pass an explicit `-Configure...` switch.

## Quick Start

Open PowerShell and run the install path you need. For Codex:

```powershell
git clone --branch v0.3.3 https://github.com/lzhs1995/clauder-rstudio-workbench.git "$env:USERPROFILE\projects\clauder-rstudio-workbench"
cd "$env:USERPROFILE\projects\clauder-rstudio-workbench"
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ConfigureCodex
& "$env:USERPROFILE\bin\clauder-workbench.cmd" doctor
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

If the wrapper path is not available, use the portable fallback:

```powershell
python -m clauder_workbench doctor
```

To make the short `clauder-workbench doctor` command available in future terminals, rerun the installer with `-AddHarnessToPath`.

If `git clone` is blocked by a proxy or reset connection, use the supported tag-zip bootstrap instead:

```powershell
$zip = "$env:TEMP\clauder-rstudio-workbench-v0.3.3.zip"
$tmp = "$env:TEMP\clauder-rstudio-workbench-v0.3.3"
$dest = "$env:USERPROFILE\projects\clauder-rstudio-workbench"
Invoke-WebRequest -Uri "https://github.com/lzhs1995/clauder-rstudio-workbench/releases/download/v0.3.3/clauder-rstudio-workbench-v0.3.3.zip" -OutFile $zip
Remove-Item -LiteralPath $tmp,$dest -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
Move-Item -LiteralPath (Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1).FullName -Destination $dest
cd $dest
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ConfigureCodex
```

## Running the CMAverse fan-out workflow

Once installed, the `cmaverse-paired-mval` skill auto-loads in any agent that reads
`skills/<name>/SKILL.md`. To trigger it, ask the agent to run the paired-mval
CMAverse 4-way decomposition (the SKILL `description` matches on "CMAverse",
"paired mval", "fan-out", "4-way decomposition"). The agent then drives this command
chain (one RStudio session, N async R workers, autonomous merge):

```powershell
# 1. generate + validate a fan-out contract from your paired worker .R
python skills\cmaverse-paired-mval\scripts\make_worker_contract.py `
  --worker-file <paired_worker.R> --output-root "<OUTPUT_ROOT>" --run-id <RUN_ID> `
  --mediators m1,m2,...,m7 --groups sy_female,sy_male --nboot 10 --seed 12345 --out task.yaml
clauder-workbench native-smoke start --task-key cmaverse_paired_mval_<RUN_ID> --session-name default --agent codex --require-raw-file
# Run the real Codex native MCP tools now:
#   list_sessions -> execute_r -> execute_r_async -> get_async_result
# Dump each native tool output to a raw text file and record it with --raw-file.
# Then finish with native-smoke complete.
clauder-workbench fanout-plan  --contract task.yaml --parent-evidence <native_smoke_PASS.json>

# 2. static-safety lint (BLOCKs any worker containing sink()), then run
clauder-workbench worker-lint  --contract task.yaml
clauder-workbench fanout-run   --contract task.yaml --max-parallel 3 --auto-scale --memory-threshold 85

# 3. scientific validation + merge gate before claiming success
python skills\cmaverse-paired-mval\scripts\cmaverse_validate.py --output-root "<RUN_DIR>" `
  --mediators m1,m2,...,m7 --groups sy_female,sy_male
clauder-workbench merge-gate   --contract task.yaml --parent-evidence <native_smoke_PASS.json>
```

`--auto-scale` makes the harness sample memory each poll cycle and raise concurrency
by one (up to the worker count, or `--max-parallel-cap`) while memory stays under the
threshold, throttling back when it crosses it (never killing a running job). Drop
`--auto-scale` for a fixed `--max-parallel` ceiling. For the agent's **native** MCP
transport (instead of `fanout-run`'s Python MCP stdio), use the native path documented
in the skill: `fanout-plan` → native submit → `async-guard register-job` →
`fanout-poll` → `merge-gate`. See `skills/cmaverse-paired-mval/SKILL.md` for the full
workflow and the worker contract.

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
- Python 3.14 for the harness: `winget install --id Python.Python.3.14 --source winget -e` or pass `-InstallPython314`.
- R installed with `R.exe` available, or pass `-RExe "C:\Program Files\R\R-x.y.z\bin\R.exe"`.
- R fallback install hint: `winget install --id RProject.R -e`
- RStudio install hint: `winget install --id Posit.RStudio -e`
- Claude Code CLI is required only when using `-ConfigureClaudeCode`.

## Compatibility

| Skill | ClaudeR fork | Notes |
|---|---|---|
| `v0.3.3` | `v0.2.0-lzhs.1` | Closes the high-assurance `native-smoke` chain: each record evidence id is saved into state and `complete` requires all four parent evidence ids; raw native output files are hashed, size/mtime stamped, and copied into the evidence tree; agent and native tool-layer must match. CMAverse examples now default to `--agent codex --require-raw-file`. |
| `v0.3.2` | `v0.2.0-lzhs.1` | Hardens the `native-smoke` gate: high-assurance `--require-raw-file` mode (markers must appear in the dumped native tool output) and `--agent` provenance on the evidence. Adds CMAverse fan-out runbooks: native-smoke-before-fan-out gate, `Transport closed` recovery order, and the addin-transient (retry-same-layer) failure mode. |
| `v0.3.1` | `v0.2.0-lzhs.1` | Hardens native MCP stability gates: adds executable `native-smoke` evidence flow, installer MCP prewarm/provenance fields, workspace MCP config support, and fan-out/cmaverse parent-evidence checks so long jobs cannot start from an unproven native wrapper. |
| `v0.3.0` | `v0.2.0-lzhs.1` | Becomes a skill collection (installer auto-discovers all `skills/<name>/`); adds the parallel async fan-out harness, the `worker-lint` `sink()` BLOCK gate, `fanout-run --auto-scale` dynamic concurrency, and the `cmaverse-paired-mval` domain skill. |
| `v0.2.4` | `v0.2.0-lzhs.1` | UTF-8 no-BOM writer for Codex/Copilot configs, fixes Chinese-path corruption in `[projects.''...'']` entries, adds `doctor --check-toml-parse` self-check with auto-rollback after `install.ps1 -ConfigureCodex`. |
| `v0.2.3` | `v0.2.0-lzhs.1` | Adds ClaudeR zip fallback, source metadata in `INSTALL_INFO.json`, client-scoped `doctor`, Python 3.14 opt-in install, and workbench zip bootstrap docs. |
| `v0.2.2` | `v0.2.0-lzhs.1` | Adds a user-level `clauder-workbench.cmd` wrapper, optional PATH update, clearer colleague Quick Start, and updated smoke transcript. |
| `v0.2.1` | `v0.2.0-lzhs.1` | Adds executable harnesses, real MCP stdio preflight, async two-step hook, resource gate, completion gate, DevSync, and runtime install metadata. |
| `v0.1.2` | `v0.2.0-lzhs.1` | Adds safer skill replacement, Claude Code MCP verification, release dates, feature request template, and real smoke transcript. |
| `v0.1.1` | `v0.2.0-lzhs.1` | Adds installer preflight, troubleshooting, issue templates, and idempotent Codex config rewrite. |
| `v0.1.0` | `v0.2.0-lzhs.1` | Async progress, async metadata, Copilot CLI setup, Windows multi-session safety. |

## MCP Command

The preferred Codex configuration uses a persistent `clauder-mcp.exe` entry
installed from the local `lzhs1995/ClaudeR` fork clone. This avoids the repeated
`uvx --from ...` cold-start path that can exceed a client startup timeout on a
new machine or after cache eviction.

```toml
[mcp_servers.r-studio]
command = "<USER_HOME>\\.local\\bin\\clauder-mcp.exe"
startup_timeout_sec = 180.0

[mcp_servers.r-studio.env]
USERPROFILE = "<USER_HOME>"
PYTHONIOENCODING = "utf-8"
NO_PROXY = "127.0.0.1,localhost"
UV_CACHE_DIR = "C:\\tmp\\uv-cache"
```

`install.ps1 -ConfigureCodex` creates this entry by running:

```text
uv tool install --force --from <USER_HOME>\projects\ClaudeR\clauder-mcp clauder-mcp
```

The source is still the patched fork, not upstream ClaudeR and not PyPI. Never
use a bare `uvx clauder-mcp` or `uv tool install clauder-mcp`; those can resolve
to the upstream package and lose the LZHS async progress, multiple-session, and
Copilot changes. `uvx --from <USER_HOME>\projects\ClaudeR\clauder-mcp
clauder-mcp` remains valid only as a development diagnostic path, not the
stable colleague install path.

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

Treat this as a transport-layer failure until proven otherwise. First run:

```powershell
clauder-workbench doctor --expect-client codex --check-toml-parse
```

The Codex `r-studio` MCP entry must use the persistent
`<USER_HOME>\.local\bin\clauder-mcp.exe`, `startup_timeout_sec = 180.0`, and
`UV_CACHE_DIR = C:\tmp\uv-cache`. If it still uses `uvx --from`, rerun
`install.ps1 -ConfigureCodex` to install the hot entry from the local LZHS fork.
Only after the config/provenance check passes should a native wrapper smoke be
accepted. In v0.3.3 and later, record that smoke with the high-assurance executable gate:

```powershell
clauder-workbench native-smoke start --task-key <task> --session-name default --agent codex --require-raw-file
# Use the real agent-native MCP tools, not Python stdio:
# list_sessions, execute_r, execute_r_async, get_async_result
clauder-workbench native-smoke record --task-key <task> --step list_sessions --ok --session-name default --raw-file <list_sessions_raw.txt>
clauder-workbench native-smoke record --task-key <task> --step execute_r --ok --marker NATIVE_EXECUTE_OK --pid <R_PID> --raw-file <execute_r_raw.txt>
clauder-workbench native-smoke record --task-key <task> --step execute_r_async --ok --job-id <JOB_ID> --raw-file <execute_r_async_raw.txt>
clauder-workbench native-smoke record --task-key <task> --step get_async_result --ok --job-id <JOB_ID> --marker NATIVE_ASYNC_DONE --raw-file <get_async_result_raw.txt>
clauder-workbench native-smoke complete --task-key <task>
```

The gate verifies each marker appears in the dumped native tool output, stamps
agent identity on the `NATIVE_MCP_OK` evidence, chains all four record evidence
ids into the final PASS, and preserves raw output hashes/copies for later audit.

Do not start long fan-out work after a single `Transport closed`.

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
git checkout v0.3.3
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ConfigureCodex
```

If you configured Claude Code or Copilot CLI, pass the corresponding `-Configure...` switch again.

## Working on This Skill

Use the repository under `<USER_HOME>\projects\clauder-rstudio-workbench` as the only development source. Runtime skill directories are installer outputs and may be overwritten.

| Location | Role | Commit? | Writer/reader |
|---|---|---:|---|
| `<USER_HOME>\projects\clauder-rstudio-workbench` | Development source of truth | Yes | Edit, test, commit, push |
| `<USER_HOME>\.codex\skills\clauder-rstudio-workbench` | Codex runtime copy | No | Written by `install.ps1` |
| `<USER_HOME>\.agents\skills\clauder-rstudio-workbench` | Shared agents runtime copy, when `-SyncAgentsSkill` is used | No | Written by `install.ps1` |
| `<USER_HOME>\.clauder_workbench` | evidence / inflight state | No | Written by harness |
| GitHub `lzhs1995/clauder-rstudio-workbench` | Published source | Yes | Colleagues clone tags/releases |
| editable Python install | `python -m clauder_workbench` across directories | n/a | Points to the development source |

Development sync:

```powershell
cd "$env:USERPROFILE\projects\clauder-rstudio-workbench"
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -DevSync
```

Use `-SyncAgentsSkill` when the shared `.agents` runtime copy also needs updating.
Use `-AddHarnessToPath` only when you want the installer to add `<USER_HOME>\bin` to the user PATH. Without that switch, the installer still writes `<USER_HOME>\bin\clauder-workbench.cmd`, and `python -m clauder_workbench ...` remains the portable fallback.

## What Is Not Included

- No private dissertation scripts or logs.
- No machine-specific paths.
- No API keys.
- No full validation log. Only a short portable smoke transcript is included because the complete validation history contains local project context.
- No PyPI publication for the forked `clauder-mcp`.
- No upstream PR bundle; upstream contributions should be split later.

## Agent Metadata

The packaged skill includes `agents/openai.yaml` for Codex skill UI metadata. Claude Code and Copilot CLI use MCP configuration rather than Codex skill metadata in this release.
