# Runtime provenance in doctor and session-bootstrap

Skill source metadata, a configured bridge, installed package files and a running
client are separate evidence layers. `INSTALL_INFO.json` remains descriptive;
source-only installation does not erase or manufacture runtime provenance.

`doctor` and `session-bootstrap` read the selected client's actual configuration,
resolve a supported persistent launcher, and verify local distribution metadata,
installed Python sources against RECORD and their local source, and an adjacent
paired-release receipt when present. A source pairing manifest additionally
checks the expected bridge version and critical server bytes. No bridge, R or
network operation is executed by these checks. PASS does not prove that an
already-running client or RStudio session loaded the checked files.

Examples work through either the installed command or the matching skill's
`harness/run.sh` / `harness/run.ps1` entry:

```text
clauder-workbench doctor
clauder-workbench doctor --expect-client codex
clauder-workbench doctor --expect-client claude --config-file /path/project/.mcp.json
clauder-workbench doctor --expect-client copilot --config-file /path/mcp-config.json
clauder-workbench session-bootstrap --client claude --config-file /path/project/.mcp.json
```

For `auto`, a declared current client takes priority, followed by configured
clients in install metadata, then configurations containing an r-studio entry.
Malformed existing configuration is retained as a failure. `all` includes all
three supported clients and therefore reports missing configurations.

Codex reads its TOML r-studio entry; Copilot reads its JSON mcpServers entry.
Claude checks `.mcp.json` from the current directory up through its ancestors,
then user-level JSON. `--config-file` selects exactly one explicit file. These
are file-level checks; they do not resolve a running client's plugin configuration,
project-local JSON scopes, trust decisions, or environment expansion. Use an
explicit file for an installation whose effective source is outside these paths.

Supported launchers are the exact stable POSIX wrapper with its configured Python
override, a Python console entrypoint, and a Windows native entrypoint with an
adjacent Python interpreter. Console and native entrypoint paths and bytes must
also match the installed distribution RECORD; a neighboring interpreter alone
does not prove the dispatch target. Editable installs and unknown wrappers fail
closed. Every registered Python package source must still exist. Explicit
discovery home and an absolute UV_CACHE_DIR are required. Windows path/layout
fixtures do not replace native Windows qualification. Changing client versions
or selecting a different runtime requires its own authorized installation and
current native-tool verification. The checks never update configurations,
restart sessions, install packages or modify hooks.
