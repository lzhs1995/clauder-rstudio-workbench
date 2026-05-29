# Changelog

## v0.2.0 - 2026-05-29

- Add the `clauder_workbench` executable harness package under the skill, with `doctor`, `transport-classify`, `tool-surface`, `preflight`, `connect`, `async-guard`, `resource-gate`, and `completion-check`.
- Add evidence schema `0.2.0` with `evidence_id`, `parent_evidence_ids`, `task_key`, `transport_class`, `io_mode`, artifact paths, policy violations, and stable exit codes.
- Add independent MCP stdio, HTTP, and Rscript transport classification. Agent-supplied transport flags are ignored unless explicitly allowed for diagnostic use.
- Add an in-flight async registry and dynamic concurrency gate. Increasing concurrency requires memory below threshold, no I/O block, responsive Rterm/MCP, and advancing durable output.
- Add completion policy checks for transport class, large async outputs, incomplete state files, duplicate in-flight tasks, missing resource-gate evidence, and missing/weak durable artifacts.
- Make harness configuration distributable with `<USER_HOME>`/environment-variable based paths instead of machine-specific absolute paths.
- Preserve v0.1.2 installer governance files and add harness editable install to `install.ps1`.

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
