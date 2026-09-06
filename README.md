# clauder-rstudio-workbench

Portable skill **collection**, executable harness, and installer for using a patched ClaudeR build as an RStudio workbench through MCP.

The `v0.6.1` release line is cross-platform and targets the local ClaudeR
`0.14.1.9001` fork based on upstream ClaudeR `0.14.1` / `clauder-mcp 0.14.5`, while
retaining strict native provenance and durable async progress.

**Platform status:** `install.sh` supports macOS/Linux and `install.ps1`
supports Windows. Both configure a persistent platform-native `clauder-mcp`
entry and share the same fan-out, progress, resource, and completion gates.

The maintained Chinese architecture and operations manual is
[ClaudeR 架构说明与 clauder-rstudio-workbench 使用指南](docs/ClaudeR_架构说明与clauder-rstudio-workbench使用指南.md).
It supersedes the Windows-first development diary while preserving a
[sanitized origin summary](docs/history/2026-05-windows-origin.md).

## Skills in This Collection

Both installers discover every `skills/<name>/` directory that contains a `SKILL.md`:

- **`clauder-rstudio-workbench`** — core skill: connect/preflight/async-guard/resource-gate/completion gates plus the parallel **fan-out** harness (one RStudio driving N async R workers with autonomous merge).
- **`cmaverse-paired-mval`** — domain skill: a worked, executable example of the fan-out workflow for paired M=0/M=1 CMAverse bootstrap (7 mediators in parallel), with a generator and a validation gate.
- **`comparegroups-guide`** — descriptive-statistics skill: contract-driven
  `compareGroups` computation, labelled-data audit, panel-safe dual output,
  true three-line DOCX rendering, numeric reconciliation, validation, and hashes.

## What This Installs

- The patched ClaudeR R package from the local `lzhs1995/ClaudeR` worktree.
- Every skill in this collection under `<CODEX_HOME>/skills` (and `<AGENTS_HOME>/skills` with `-SyncAgentsSkill`).
- The `clauder_workbench` Python harness package for doctor, transport classification, async guard, fan-out, recoverable soak monitoring, resource gate, and completion gate checks.
- Optional MCP configuration for Codex, Claude Code, or GitHub Copilot CLI.

Neither installer modifies MCP client configuration unless an explicit configure switch is passed.

Formal completion keeps resource-gate admission evidence fresh for 120 minutes
by default. Long-soak contracts can override this with
`resource_gate_max_age_min`; an explicit contract value takes precedence over
the CLI default.

## Quick Start

On macOS/Linux:

```bash
cd "$HOME/projects/clauder-rstudio-workbench"
./install.sh --clauder-dir "$HOME/projects/ClaudeR" --configure-codex --sync-agents-skill --backup-retention 0
"$HOME/.local/bin/clauder-workbench" doctor --expect-client codex --check-toml-parse
```

Use a clean checkout of the exact `v0.6.1` tag with these commands. Do not
overwrite a worktree that contains local changes.

On Windows PowerShell:

```powershell
git clone https://github.com/lzhs1995/clauder-rstudio-workbench.git "$env:USERPROFILE\projects\clauder-rstudio-workbench"
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

If the wrapper path is not available on Windows, use the portable fallback:

```powershell
python -m clauder_workbench doctor
```

To make the short `clauder-workbench doctor` command available in future terminals, rerun the installer with `-AddHarnessToPath`.

If the Windows `git clone` is blocked by a proxy or reset connection, use the
`v0.6.1` tag-zip bootstrap after that release is published:

```powershell
$zip = "$env:TEMP\clauder-rstudio-workbench-v0.6.1.zip"
$tmp = "$env:TEMP\clauder-rstudio-workbench-v0.6.1"
$dest = "$env:USERPROFILE\projects\clauder-rstudio-workbench"
Invoke-WebRequest -Uri "https://github.com/lzhs1995/clauder-rstudio-workbench/releases/download/v0.6.1/clauder-rstudio-workbench-v0.6.1.zip" -OutFile $zip
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

## Running a compareGroups descriptive table

`comparegroups-guide` turns a JSON table contract into a verified display CSV,
unformatted numeric-long CSV, retained `compareGroups`/`createTable` objects,
metadata, a true three-line DOCX, validation, and SHA-256 manifest. Start from a
sanitized template under `skills/comparegroups-guide/assets/`:

```bash
Rscript skills/comparegroups-guide/scripts/check_dependencies.R
Rscript skills/comparegroups-guide/scripts/audit_input.R \
  --spec /absolute/path/table-spec.json \
  --output /absolute/path/input-audit.json
Rscript skills/comparegroups-guide/scripts/run_comparegroups.R \
  --spec /absolute/path/table-spec.json \
  --output-root /absolute/path/new-results
Rscript skills/comparegroups-guide/scripts/validate_comparegroups.R \
  --output-root /absolute/path/new-results --stem Table_1
```

Spec 1.1 adds reusable defaults, ordered subset variants, automatic attrition,
explicit group recoding/reference, `hide_no`, and DOCX controls. Each resolved
variant is emitted both in the combined evidence set and as an independent
`<stem>__<variant-id>` DOCX/CSV/RDS/metadata set. For several independent
specifications, run and validate one ordered batch:

```bash
Rscript skills/comparegroups-guide/scripts/run_comparegroups_batch.R \
  --manifest /absolute/path/batch-manifest.json \
  --output-root /absolute/path/new-batch-results
Rscript skills/comparegroups-guide/scripts/validate_comparegroups_batch.R \
  --output-root /absolute/path/new-batch-results
```

The runner maps readable methods (`normal`, `nonnormal`, `categorical`) to the
official `compareGroups` engine, requires explicit handling of unlabelled
categorical codes, and preserves Stata labels through `haven`. In panel
`dual` mode it creates a safe primary view plus a clearly warned pooled
compatibility view. Large batches should be submitted once with ClaudeR
`execute_r_async` and polled using the original job ID; ordinary single tables
do not need fan-out. See [the skill](skills/comparegroups-guide/SKILL.md).

Every `fanout-run` polling cycle atomically refreshes
`<output_root>/fanout_runtime_status.json` and emits a flushed
`FANOUT_PROGRESS` line with the original job IDs and
done/running/pending/failed counts. Use `--progress-file <absolute.json>` to
override the status path.

An explicit bridge response such as `Async job error`, cancelled, or not-found
is a terminal worker failure and is recorded with the original job ID. A
connection reset or other transport-only polling error remains retryable and
never causes the worker to be resubmitted.

If the current agent task was created before its native MCP wrapper was
registered, its tool registry cannot reliably hot-add that wrapper on either
Windows or macOS. After an independent `MCP_STDIO_OK` probe, an explicitly
authorized compute-first run may use `--defer-native-smoke`. This does not
weaken provenance: evidence is marked `NATIVE-SMOKE-DEFERRED`, never
`NATIVE_MCP_OK`, and formal `completion-check` remains blocked until a fresh
four-step native smoke is attached.

For a formal long soak, start the recoverable monitor before submitting native
workers and require its evidence at completion:

```bash
clauder-workbench soak-monitor run --contract task.json \
  --evidence-dir /absolute/run/evidence/native --expected-pid 39875 \
  --port 8788 --stop-file /absolute/run/evidence/native/stop.monitor
clauder-workbench completion-check --mode formal --task-key <task> \
  --require-soak-monitor --parent-evidence <soak_monitor_PASS.json>
```

The monitor isolates macOS process-enumeration errors, preserves one logical
run across supervised recovery, counts every scheduled heartbeat slot, and
never turns its independent stdio heartbeat into native-wrapper proof.

## Dry Run

Preview changes without writing files or installing packages:

```bash
./install.sh --clauder-dir "$HOME/projects/ClaudeR" --configure-codex --sync-agents-skill --backup-retention 0 --dry-run
```

On Windows, use `install.ps1 -DryRun -ConfigureCodex`.

Use `--skip-harness` on macOS/Linux or `-SkipHarness` on Windows only when you
want to install the Markdown skill without the executable Python gate.

On macOS/Linux, `--backup-retention 0` is the default and keeps every existing
runtime skill backup. Pass a positive count only when you explicitly want the
installer to prune older per-skill backups after a successful replacement.

## Install Choices

Use one MCP configuration path at a time:

- **Recommended for macOS/Linux:** run `install.sh` and pass one explicit configuration switch such as `--configure-codex`.
- **Recommended for Windows:** run `install.ps1` and pass one explicit configuration switch such as `-ConfigureCodex`.
- **Alternative for ClaudeR developers:** run `library(ClaudeR); install_cli(..., mcp_from = "local")` from the ClaudeR package.

Do not run both paths blindly. If both are used, the last writer wins and may replace the previous `r-studio` MCP block.

Installer prerequisites:

- macOS/Linux: Git, R, RStudio, Python 3.10+, and `uv` on `PATH`.
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
| `v0.6.1` | local `0.14.1.9001` / bridge `0.14.5` | Corrects available-N/variable mapping, validates all resolved variants and independent analysis-unit keys, and cross-checks CSV semantics against retained RDS objects plus a complete validation checklist. |
| `v0.6.0` | local `0.14.1.9001` / bridge `0.14.5` | Adds backward-compatible spec 1.1 defaults, ordered variants, automatic attrition, batch manifests, structured validation diagnostics, configurable true-three-line DOCX output, and explicit compareGroups 4.10.2/4.10.3 gates. |
| `v0.5.0` | local `0.14.1.9001` / bridge `0.14.5` | Adds the `comparegroups-guide` sibling skill, versioned Table 1 contract, labelled-data and panel audit, true three-line DOCX output, numeric reconciliation artifacts, validation, and cross-platform tests. |
| `v0.4.6` | local `0.14.1.9001` / bridge `0.14.5` | Adds file-backed async output compatibility, a non-mutating legacy pipe rescue loop, and cycle-safe soak-monitor evidence serialization. |
| `v0.4.5` | upstream `0.14.1` / bridge `0.14.5` compatible | Requires the complete 41-tool surface (including `suggest_edit`), adds OS-independent compute-first native deferral with an unchanged strict completion gate, and writes atomic live fan-out status containing the original async job IDs. |
| `v0.4.3` | local fork based on upstream `0.12.2` | Updates the strict MCP tool surface to all 40 ClaudeR tools, including Coordination v2, screening, cross-reference reconciliation, citation, notebook, and codebook workflows, while retaining the fork's safe PID and async-progress compatibility. |
| `v0.4.4` | local CMAverse Mac candidate | Adds CPU/disk/upload-backlog aware fan-out admission while preserving the `MCP_STDIO_OK` transport boundary and the v0.4.3 ClaudeR 0.12.2 compatibility surface. |
| `v0.4.2` | local fork based on upstream `0.8.1` | Extends resource-gate freshness to 120 minutes for long soaks and records the selected gate age while retaining the recoverable monitor introduced in v0.4.1. |
| `v0.4.1` | local fork based on upstream `0.8.1` | Adds recoverable long-soak monitoring, exact scheduled heartbeat accounting, supervised checkpoint recovery, macOS-safe process enumeration, and a monitor-aware formal completion gate. |
| `v0.4.0` | local fork based on upstream `0.8.1` | Adds macOS/Linux installers and harness entrypoints, platform-aware doctor/provenance checks, POSIX resource sampling, and retains async progress, parallel metadata, Copilot support, and safe Windows PID discovery. |
| `v0.3.4` | `v0.2.0-lzhs.1` | Closes the downstream gate: fan-out, merge, and completion checks now reject stale `native-smoke` PASS evidence unless it carries four unique record `parent_evidence_ids`. Adds installer `-BackupRetention 5` and documents strict single-agent/raw-proof behavior as by design. |
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

The preferred Codex configuration uses a persistent `clauder-mcp` entry
installed from the local `lzhs1995/ClaudeR` fork clone. This avoids the repeated
`uvx --from ...` cold-start path that can exceed a client startup timeout on a
new machine or after cache eviction.

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

`install.sh --configure-codex` creates this entry on macOS. Windows uses the
same structure with `clauder-mcp.exe`, `USERPROFILE`, and `C:\\tmp\\uv-cache`.
The local macOS installer runs:

```text
uv tool install --force --from <USER_HOME>/projects/ClaudeR/clauder-mcp clauder-mcp
```

The source is the local fork based on current upstream, not an unpinned PyPI build. Never
use a bare `uvx clauder-mcp` or `uv tool install clauder-mcp`; those can resolve
to the upstream package and lose the LZHS async progress, multiple-session, and
Copilot changes. `uvx --from <USER_HOME>\projects\ClaudeR\clauder-mcp
clauder-mcp` remains valid only as a development diagnostic path, not the
stable colleague install path.

## Validation

After installation:

1. Restart Codex only when MCP configuration or bridge source changed; an
   existing task cannot reliably hot-add a new native tool registry.
2. Start the ClaudeR Addin in RStudio.
3. Ask Codex to connect with `$clauder 连接Rstudio`.
4. Verify `list_sessions`, `execute_r`, and a short `execute_r_async -> get_async_result` smoke test.
5. For long tasks, require visible `Latest progress:` or final progress before claiming MCP async readiness.
6. For formal completion, run the harness gate, for example:

```bash
./skills/clauder-rstudio-workbench/harness/run.sh completion-check --mode formal \
  --require-file "validation::$HOME/out/validation.csv,min_rows=1,max_age_h=24"
```

On Windows, use the equivalent `harness\run.ps1` command. Harness evidence is
written to `<USER_HOME>/.clauder_workbench/evidence`.

For the installer smoke transcript format, see `tests/install_smoke.md`.

Historical qualification evidence (through v0.6.0; not v0.6.1 test results):

- Local Windows install, reinstall idempotence, and privacy scan have passed.
- The macOS release candidate passed the 206-test Python harness suite, skill
  validation, MCP stdio/tool-surface checks, real RStudio workflows,
  multi-session cleanup, and asynchronous fan-out regression tests.
- An earlier full-green qualification ran eight workers for 4,200 seconds each
  and matched all canonical RDS hashes between Native and MCP stdio transports.
- A git-subdirectory MCP runtime smoke has passed when a live RStudio ClaudeR Addin session is available.
- Native Codex wrapper evidence always requires a fresh current-task four-step
  smoke after MCP configuration changes; MCP stdio evidence must not be
  relabeled `NATIVE_MCP_OK`. Explicit `--defer-native-smoke` can keep
  computation moving, but cannot make formal completion pass.
- A clean-VM or colleague-machine validation remains the final gate before broad rollout.
- The compareGroups release gate additionally requires synthetic cross-platform
  regression, five private real-data cases on the local Mac, three-skill
  validation, a fresh native ClaudeR sync/async smoke, and privacy scanning.

The v0.6.1 correctness audit found gaps despite earlier green tests. This
patch requires new regressions for auxiliary available-N columns, duplicate
labels, automatic panel group loss, duplicated analysis-unit keys, and CSV
corruption with recomputed manifests. The independent validator must compare
exported content with retained statistical objects and require the full
validation checklist. Consult the release's own evidence for execution status;
historical test totals do not certify the patch.

These checks do not independently prove a scientific design, visually inspect
Chinese typography or page layout, or protect against coordinated alteration
of every retained artifact. Review the analysis unit, methods and rendered
DOCX before using the table in a manuscript.

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

```bash
clauder-workbench doctor --expect-client codex --check-toml-parse
```

The Codex `r-studio` MCP entry must use the persistent
`<USER_HOME>/.local/bin/clauder-mcp` (`.exe` on Windows),
`startup_timeout_sec = 180.0`, and a platform-native `UV_CACHE_DIR`. If it
still uses `uvx --from`, rerun `install.sh --configure-codex` on macOS/Linux or
`install.ps1 -ConfigureCodex` on Windows to install the persistent entry from
the local LZHS fork.
Only after the config/provenance check passes should a native wrapper smoke be
accepted. In v0.3.4 and later, record that smoke with the high-assurance executable gate:

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

Do not use an unpatched ClaudeR build whose stale discovery cleanup uses
`tools::pskill(pid, signal = 0)`. Install the maintained fork branch based on
ClaudeR 0.14.1 (or the older Windows `v0.2.0-lzhs.1` release), restart RStudio,
then rerun a multi-session safety check before trusting concurrent sessions.

### `Latest progress:` does not appear

Confirm all three layers:

1. The R code includes `clauder_progress(stage, message)` markers.
2. RStudio has loaded the patched ClaudeR package after reinstall/restart.
3. The MCP command points to the patched local bridge, not plain `uvx clauder-mcp`.

## Upgrade

To upgrade macOS/Linux and reinstall the paired ClaudeR worktree:

```bash
cd "$HOME/projects/clauder-rstudio-workbench"
git fetch origin
./install.sh --clauder-dir "$HOME/projects/ClaudeR" --configure-codex --sync-agents-skill --backup-retention 0
```

For the published Windows release:

```powershell
cd "$env:USERPROFILE\projects\clauder-rstudio-workbench"
git fetch --tags
git checkout v0.6.1
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ConfigureCodex
```

If you configured Claude Code or Copilot CLI, pass the corresponding `-Configure...` switch again.

## Working on This Skill

Use the repository under `<USER_HOME>/projects/clauder-rstudio-workbench` as the
only development source. Runtime skill directories are installer outputs and
may be overwritten.

| Location | Role | Commit? | Writer/reader |
|---|---|---:|---|
| `<USER_HOME>/projects/clauder-rstudio-workbench` | Development source of truth | Yes | Edit, test, commit, push |
| `<USER_HOME>/.codex/skills/clauder-rstudio-workbench` | Codex runtime copy | No | Written by an installer |
| `<USER_HOME>/.agents/skills/clauder-rstudio-workbench` | Shared agents runtime copy | No | Written by an installer |
| `<USER_HOME>/.clauder_workbench` | evidence / inflight state | No | Written by harness |
| GitHub `lzhs1995/clauder-rstudio-workbench` | Published source | Yes | Colleagues clone tags/releases |
| editable Python install | `python -m clauder_workbench` across directories | n/a | Points to the development source |

Development sync:

```bash
cd "$HOME/projects/clauder-rstudio-workbench"
./install.sh --clauder-dir "$HOME/projects/ClaudeR" --skip-r-package --skip-mcp --sync-agents-skill --backup-retention 0
```

Windows developers can use the existing `install.ps1 -DevSync` flow. On
Windows, `-AddHarnessToPath` controls whether `<USER_HOME>\bin` is added to
PATH; macOS installs the wrapper directly under `<USER_HOME>/.local/bin`.

## What Is Not Included

- No private dissertation scripts or logs.
- No machine-specific paths.
- No API keys.
- No full validation log. Only a short portable smoke transcript is included because the complete validation history contains local project context.
- No PyPI publication for the forked `clauder-mcp`.
- No upstream PR bundle; upstream contributions should be split later.

## Agent Metadata

The packaged skill includes `agents/openai.yaml` for Codex skill UI metadata. Claude Code and Copilot CLI use MCP configuration rather than Codex skill metadata in this release.
