# Changelog

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
