# Changelog

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
