# Changelog

## v0.4.6 - 2026-09-05

- Prevent verbose ClaudeR async jobs from stalling on full process stdout or
  stderr pipes by pairing with ClaudeR `0.14.1.9001` file-backed output.
- Add `async-io-rescue run/status` for jobs that were already started by an
  older ClaudeR package. It drains only original job IDs from durable fan-out
  status and cannot submit, cancel, or restart workers.
- Make soak-monitor checkpoint and JSONL evidence serialization cycle-safe so
  a malformed or self-referential MCP result cannot terminate monitoring.
- Treat explicit `Async job error`/cancelled/not-found responses as terminal
  fan-out failures while leaving transient MCP transport errors retryable.
- Publish the maintained cross-platform Chinese architecture and operations
  guide, including the four progress layers, Native/stdio evidence boundary,
  tmux hosting boundary, release history, and an evidence-honest CMAverse case
  study. Preserve the Windows-first development record as a sanitized history
  summary rather than exposing local research paths and logs.

## v0.4.5 - cross-platform candidate, 2026-09-02

- Add an explicit `--defer-native-smoke` compute-first mode to `fanout-plan`,
  `fanout-run`, `fanout-poll`, and `merge-gate`. It is OS-independent, keeps
  the real worker transport labelled `MCP_STDIO_OK`, records
  `NATIVE-SMOKE-DEFERRED`, and deliberately leaves formal `completion-check`
  blocked until a fresh native-wrapper smoke is supplied.
- Write `<output_root>/fanout_runtime_status.json` atomically on every fan-out
  polling iteration and emit flushed `FANOUT_PROGRESS` lines containing the
  unchanged job IDs, done/running/pending counts, and failures.
- Document that an already-running agent task cannot reliably hot-add a newly
  configured MCP wrapper on Windows or macOS. Persistent bridge diagnosis and
  MCP stdio computation can continue without falsely claiming
  `NATIVE_MCP_OK`.
- Refresh the compatibility target to upstream ClaudeR 0.14.1 and bridge
  0.14.5, including unified home resolution, preserved MCP environment,
  Windows-safe liveness checks, and console-output logging fixes.
- Require the complete 41-tool ClaudeR 0.14.1 surface, including the new
  `suggest_edit` tool, so a current bridge is not rejected as incompatible.

## v0.4.4 - local candidate, 2026-09-02

- Add CPU, disk-free, and upload-backlog admission signals to memory-aware
  fan-out scaling for the CMAverse archival workflow.
- Redact ClaudeR discovery tokens from doctor evidence while retaining session
  health and provenance fields needed for diagnosis.

## v0.4.3 - local candidate, 2026-08-22

- Pair the local workbench with the fork rebased on upstream ClaudeR 0.12.2
  and MCP bridge 0.14.2 while retaining the fork's read-only PID checks,
  async progress sidecars, multi-session metadata, and Copilot installer path.
- Require the complete 40-tool ClaudeR MCP surface, including Coordination v2,
  screening, cross-reference reconciliation, citations, notebooks, and
  codebooks, instead of accepting only the five legacy connection primitives.
- Refresh provenance, compatibility, installer smoke, and skill documentation
  for the new pinned local candidate without changing evidence schema 0.2.4.

## v0.4.2 - local candidate, 2026-08-20

- Raise formal completion's default resource-gate freshness window from 60 to
  120 minutes so a valid final admission decision remains usable after a
  70-minute soak.
- Record the selected resource-gate evidence id, age, effective threshold, and
  acceptance decision in completion evidence; distinguish stale evidence from
  missing evidence.
- Document detached tmux plus run-scoped caffeinate as the macOS hosting model
  for formal Native soak monitoring.

## v0.4.1 - local candidate, 2026-08-20

- Add macOS/Linux `--backup-retention`; it defaults to `0` so upgrades preserve
  every runtime skill backup unless the operator explicitly opts into pruning.
- Record workbench/ClaudeR dirty-tree state and explicit ClaudeR/MCP component
  versions in macOS/Linux `INSTALL_INFO.json` for auditable local upgrades.
- Add the recoverable `soak-monitor` harness with exact scheduled heartbeat
  accounting, atomic checkpoints, supervised recovery, and durable resource,
  progress, event, and raw heartbeat evidence.
- Make macOS process enumeration defensive: `psutil` `cmdline()` permission and
  `SystemError` failures are recorded as non-critical metric errors instead of
  terminating a formal long run.
- Add contract monitor policy, `completion-check --require-soak-monitor`, and
  fault-injection coverage for recovery, missed slots, safety cancellation, and
  matching monitor provenance.

## v0.4.0 - local candidate, 2026-08-19

- Rebase the paired ClaudeR fork on upstream R package 0.8.1 and MCP bridge
  0.10.0 while retaining safe Windows PID checks, async progress, multi-session
  metadata, parallel job guidance, and GitHub Copilot setup.
- Add `install.sh` and `harness/run.sh`, platform-aware doctor/provenance checks,
  POSIX paths, macOS uv cache discovery, and native macOS memory sampling.
- Install the MCP bridge from the local ClaudeR worktree into the persistent
  `~/.local/bin/clauder-mcp` entry and atomically update Codex configuration and
  runtime skills with backups and TOML rollback validation.
- Preserve original job ids through fan-out polling and final collection, and
  surface intermediate async progress from worker sidecars.
- Validate the candidate locally on macOS with R CMD check, Python tests, a
  real RStudio/MCP workflow suite, multi-session cleanup, and a three-worker
  150,000-fit IV bootstrap fan-out. This entry does not represent a tag or
  published release.

## v0.3.4 - 2026-05-31

- Harden downstream native-smoke consumption: fan-out and completion gates now require a `native_smoke` parent evidence to carry four unique record `parent_evidence_ids`, so v0.3.2-era empty-chain PASS evidence no longer satisfies formal gates.
- Add installer backup retention for runtime skill directories. `-BackupRetention 5` is the default; `0` disables pruning, and `-DryRun` reports which old `*_bak_*` directories would be removed.
- Document the strict by-design policy: no mixed-agent native-smoke, no bypass for empty parent chains, and no automatic cleanup of raw formal evidence.

## v0.3.3 - 2026-05-31

- Close the high-assurance `native-smoke` evidence chain. Each successful `record` now writes its `evidence_id` back into the native-smoke state, and `complete` BLOCKs unless all four native steps contribute parent evidence ids.
- Preserve raw native MCP output proof in `--require-raw-file` mode: every raw file is SHA256 hashed, size/mtime stamped, and copied under the evidence tree so later audits do not depend on mutable working-directory files.
- Enforce agent/tool-layer consistency. `--agent codex|claude|copilot` derives the matching `<agent>-native` tool layer when omitted, and mismatched or mixed native tool layers BLOCK.
- Promote the CMAverse paired-mval workflow examples to the high-assurance default (`--agent codex --require-raw-file`) and document that old v0.3.2 native-smoke states must be rerun rather than completed.

## v0.3.2 - 2026-05-31

- Harden the `native-smoke` gate with a high-assurance `--require-raw-file` mode: every recorded step must supply `--raw-file` (a dump of the real native MCP tool output), and any `--marker` is verified to actually appear inside that file. A `record` without the raw file, or a marker absent from it, is BLOCKed. This raises the anti-fabrication bar beyond agent-self-reported strings.
- Add `--agent {codex,claude,copilot}` provenance to `native-smoke`. The agent identity is stamped on the `start`/`record`/`complete` evidence and, when omitted, inferred from the native tool layer — so multi-agent setups can trace which agent produced an `NATIVE_MCP_OK` proof.
- Document the addin-transient failure mode (first `execute_r_async` returns `RStudio addin is not running` -> retry on the **same** native layer, never restart) as both a failure mode in `cmaverse-paired-mval/references/failure-modes-and-pr.md` and a worked example in `references/native-mcp-gate.md`.
- Add a CMAverse fan-out runbook: native-smoke must PASS (parent `transport_class=NATIVE_MCP_OK`) before a fan-out, plus the `Transport closed` recovery order (doctor -> confirm persistent entry/provenance -> reinstall -> native-smoke retry -> only then restart) directly in the CMAverse failure-modes reference.

## v0.3.1 - 2026-05-30

- Add executable `native-smoke` gate. The command uses an agent-driven contract (`start` -> real native `list_sessions`/`execute_r`/`execute_r_async`/`get_async_result` -> `record` -> `complete`) and writes `transport_class=NATIVE_MCP_OK` only after all four native-wrapper steps are present. Python MCP stdio, HTTP fallback, and hand-written JSON do not count.
- Add native-smoke parent-evidence checks to `fanout-plan`, `fanout-run`, `fanout-poll`, `merge-gate`, and `completion-check`. CMAverse-generated fan-out contracts now set `requires_native_smoke: true` by default; `--no-require-native-smoke` is available only for diagnostic MCP-stdio runs.
- Harden `install.ps1` for MCP cold-start stability: optional prewarm after installing the persistent `clauder-mcp.exe`, `-SkipPrewarm`, `-RequirePrewarm`, `-PrewarmTimeoutSec`, and richer `INSTALL_INFO.json` provenance (`clauder_mcp_install_from`, executable SHA256, ClaudeR git origin/head, and prewarm result).
- Add optional `-ConfigureWorkspaceMcp` / `-WorkspaceMcpPath` to migrate workspace `.mcp.json` off the cold `uvx --from ...` path and onto the persistent executable.
- Document the anti-restart runbook: `Transport closed` -> doctor/provenance -> reinstall or prewarm persistent entry -> native-smoke retry -> only then ask the user to restart the agent.

## v0.3.0 - 2026-05-29

- **Collection**: this repo is now a skill *collection*. `install.ps1` discovers and installs every `skills/<name>/` directory that contains a `SKILL.md`, not just the primary skill. `INSTALL_INFO.json` is still written into `clauder-rstudio-workbench`.
- **Version decoupling**: package/release version is now `0.3.0` (`pyproject.toml`, `__init__.py`, README clone/zip/upgrade). The evidence *file-format* version (`schema_version`) deliberately stays `0.2.4` because the evidence format did not change; evidence now carries an additional `producer_version` field so you can still tell which package wrote it.
- Add **fan-out harness** to `clauder-rstudio-workbench` (`clauder_workbench/fanout.py` + CLI): generate, submit, and merge-gate N parallel async R worker jobs driven from one RStudio session, with autonomous result merge. Adds `submit_async` and a minimal-YAML contract loader. `fanout-run --transport native-wrapper` BLOCKs and points to the native path (it only submits via mcp-stdio).
- The fan-out contract schema now ships with the skill at `skills/clauder-rstudio-workbench/schemas/fanout-contract.schema.json` (kept byte-identical to the `shared/schemas/` source).
- Add new domain skill **`cmaverse-paired-mval`**: a worked, executable example of the async fan-out workflow (one RStudio driving 7 R workers for paired M=0/M=1 CMAverse bootstrap).
  - `scripts/make_worker_contract.py` generates a fan-out `task.yaml` (one worker per mediator, env `NEW47_*`, absolute forward-slash paths).
  - `scripts/cmaverse_validate.py` is a Python gate over `validation_<mediator>.csv` enforcing full `cmest`, effect/column counts, `ref` mval 0/1, no duplicate/wrong-mediator rows, **boot-hash equality** (M=0 and M=1 share the same bootstrap indices — `m0_boot_hash == m1_boot_hash`, not just a self-reported boolean), and the **`delta_cde` deliverable** (`has_delta_cde` + `delta_cde_pe/se/ci_low/ci_high/pval/scale/contrast`). `--no-count-check` / `--no-pairing-check` / `--no-delta-cde-check` each flag the run as `weak_validation` (not for formal success claims).
  - Relaxed CMAverse gates now return `WEAK_PASS` with exit code `2`, not `PASS`/`0`, so agents cannot treat `--no-count-check`, `--no-pairing-check`, or `--no-delta-cde-check` output as a formal completion claim.
  - `assets/worker_template.R` is a credential-free worker skeleton emitting state/manifest/validation plus the bootstrap-pairing proof and delta_cde columns. It **stops with a failed state before saving** if any scientific invariant fails, so a "files complete but scientifically invalid" result is never recorded as complete.
- Add unit tests (fan-out contract round-trip + CMAverse generator/validator pass/fail/missing/weak/hash/delta paths + native-wrapper BLOCK + schema-packaged checks).
- **Worker-lint gate (`sink()` ban)**: add `clauder_workbench/worker_lint.py` and a `worker-lint` CLI command. Any fan-out worker whose `code_file` contains `sink(` is a hard BLOCK — a `sink()`-wrapped worker keeps the detached Rterm alive after the computation finishes, so the job never exits and the fan-out slot is never released (recorded failure mode; recovery needs a manual `cancel`). The lint also runs automatically inside `fanout-plan` and `fanout-run` (BLOCKed before any submit). Documented as a hard rule in `cmaverse-paired-mval` (`SKILL.md`, `assets/worker_template.R`, `references/worker-contract.md`, `references/failure-modes-and-pr.md`).
- **Dynamic concurrency (`--auto-scale`)**: `fanout-run` now implements best-practice §6 auto-scaling. With `--auto-scale`, the harness samples system memory each poll cycle and raises concurrency by one (up to the worker count, or `--max-parallel-cap`) while memory stays under `--memory-threshold` (default 85%); when memory crosses the threshold it stops launching new workers and lets in-flight ones drain (never killing a running job). Every change is recorded in the run's `scale_log`. Without `--auto-scale`, `--max-parallel` remains a fixed ceiling.
- Add 15 unit tests for worker-lint (clean/sink/commented-sink/missing-file, plan/run BLOCK paths), auto-scale (scale-up under low memory, throttle under high memory, hold on unknown memory, `--max-parallel-cap` ceiling), and documentation consistency so stale "no auto-scale" guidance cannot return unnoticed.
- **MCP launch stability hot path**: `install.ps1 -ConfigureCodex` now installs a persistent `clauder-mcp.exe` with `uv tool install --force --from <USER_HOME>\projects\ClaudeR\clauder-mcp clauder-mcp`, writes Codex `r-studio` to that executable, sets `startup_timeout_sec = 180.0`, and shares `UV_CACHE_DIR = C:\tmp\uv-cache`. This keeps the source on `lzhs1995/ClaudeR@v0.2.0-lzhs.1` while avoiding repeated `uvx --from ...` startup latency.
- Add `doctor` provenance checks that BLOCK bare `uvx clauder-mcp` / bare `uv tool install clauder-mcp` risk, because those can resolve to upstream/PyPI and lose LZHS async progress, multiple-session, and Copilot changes.
- The Python MCP stdio harness now reads the configured Codex `r-studio` server command first, so diagnostics exercise the same persistent executable path as Codex instead of silently falling back to `uvx --from`.
- Native release gate passed after a Codex restart: `mcp__r_studio.list_sessions`, `execute_r`, and `execute_r_async -> get_async_result` succeeded on session `default` with async job `f8f39586`.

## v0.2.4 - 2026-05-29

- **HOTFIX (P0)**: Fix `install.ps1 -ConfigureCodex` corrupting `~/.codex/config.toml` on Windows installs that contain Chinese paths (e.g. `[projects.'C:\Users\...\开题报告']`). PowerShell 5.1 `Set-Content -Encoding UTF8` adds a BOM and `Get-Content -Raw` reads with ANSI/CP936, causing the Chinese path bytes to be misdecoded and the trailing `'` to be lost. Codex then fails to start with `unclosed table, expected ]`.
- Introduce UTF-8 helpers `Read-Utf8File`, `Write-Utf8NoBom`, `Test-TomlParseable`, and `Restore-FromLatestBackup` in `install.ps1`. All `.codex/config.toml`, `INSTALL_INFO.json`, and `.copilot/mcp-config.json` writes now go through the no-BOM writer.
- Add post-write TOML parse self-check in `Write-CodexConfig`. On parse failure, automatically restore from the most recent `config.toml.bak_*` and abort with a pointer to guide section 27.11.
- Add `doctor --check-toml-parse` so colleagues can verify their Codex config independently without rerunning the installer.
- Add 8 regression tests covering: UTF-8 BOM input, invalid UTF-8 bytes, Chinese paths in `[projects.'...']` entries, unclosed-table corruption, missing config, helper presence, doctor flag wiring, and installer no-BOM contract.
- Bump evidence schema to `0.2.4`.
- Document the incident, root cause, manual recovery, and long-term fix in guide section 27.11.

## v0.2.3 - 2026-05-29

- Add ClaudeR tag-zip fallback in `install.ps1` for proxy/reset environments where GitHub smart HTTP clone fails.
- Add `-NoZipFallback` and explicit `-InstallPython314` installer switches.
- Extend `INSTALL_INFO.json` with workbench source metadata, ClaudeR source metadata, and configured client metadata.
- Add `doctor --expect-client codex|claude|copilot|all`, with `auto` defaulting from `INSTALL_INFO.json`, so Codex-only installs do not warn about missing Copilot config.
- Add README release-asset zip bootstrap commands for obtaining `clauder-rstudio-workbench` itself when `git clone` is blocked.
- Add clearer winget hints for Git, uv, Python 3.14, R, and RStudio prerequisites.

## v0.2.2 - 2026-05-29

- Add a user-level `clauder-workbench.cmd` wrapper under `<USER_HOME>\bin` so colleagues can run short harness commands without remembering the full Python module path.
- Add installer switches `-WorkbenchBinDir` and `-AddHarnessToPath`; the installer writes the wrapper by default but only updates the user PATH when explicitly requested.
- Extend runtime `INSTALL_INFO.json` with wrapper path and PATH-update metadata for easier support.
- Tighten README Quick Start around the v0.2.2 clone/install/smoke path for colleague onboarding.
- Expand the sanitized install smoke transcript with the v0.2.1 harness chain and v0.2.2 wrapper/PATH validation notes.

## v0.2.1 - 2026-05-29

- Add the `clauder_workbench` executable harness package under the skill, with `doctor`, `transport-classify`, `tool-surface`, `preflight`, `connect`, `async-guard`, `resource-gate`, and `completion-check`.
- Add evidence schema `0.2.1` with `evidence_id`, `parent_evidence_ids`, `task_key`, `transport_class`, `io_mode`, artifact paths, policy violations, and stable exit codes.
- Add independent MCP stdio, HTTP, and Rscript transport classification. Agent-supplied transport flags are ignored unless explicitly allowed for diagnostic use.
- Add an in-flight async registry and two-step `async-guard pre-submit` / `register-job` hook so agents cannot silently skip task identity and duplicate-job checks.
- Add real MCP stdio preflight smoke checks for tool surface, `list_sessions`, optional `connect_session`, synchronous `execute_r`, and async submit/poll.
- Add cold-start retry for MCP stdio probes to handle first-run `uvx` dependency installation.
- Add completion policy checks for transport class, large async outputs, incomplete state/job evidence, duplicate in-flight tasks, fresh matching resource-gate evidence, and missing/weak durable artifacts.
- Make harness configuration distributable with `<USER_HOME>`/environment-variable based paths instead of machine-specific absolute paths.
- Preserve v0.1.2 installer governance files, add harness editable install, `-DevSync`, and runtime `INSTALL_INFO.json` to `install.ps1`.

## v0.1.2 - 2026-05-29

- Replace the skill installer backup flow with staged copy, copied backup, and automatic restore on failure.
- Verify Claude Code MCP configuration with `claude mcp list` after `claude mcp add`.
- Add release dates to the changelog.
- Add feature request template and a dedicated bug-report field for `install.ps1 -DryRun` output.
- Upgrade `tests/install_smoke.md` to include sanitized real transcript excerpts and git-subdirectory MCP runtime smoke evidence.

## v0.1.1 - 2026-05-28

- Add public troubleshooting guidance for `uvx`, PowerShell execution policy, MCP hot-load behavior, `Transport closed`, Windows multi-session aborts, and missing async progress.
- Add installer prerequisite checks with actionable Windows install hints.
- Make Codex TOML rewrite idempotent by removing all existing `r-studio` and `r-studio.env` blocks before writing the replacement.
- Add optional installer transcript logging through `-LogFile`.
- Add issue/PR templates and a portable install smoke transcript.

## v0.1.0 - 2026-05-28

- Initial public portable skill release.
- Pairs with `lzhs1995/ClaudeR@v0.2.0-lzhs.1`.
- Adds Windows-first installer with optional Codex, Claude Code, and Copilot MCP configuration.
- Documents async progress, async metadata, multi-session safety, and MCP transport boundaries.
