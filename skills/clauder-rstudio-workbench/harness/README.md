# clauder-rstudio-workbench Harness

This harness layer turns the skill's Markdown rules into executable checks.

## Entrypoints

```powershell
<SKILL_ROOT>\harness\run.ps1 doctor
```

or, after editable install:

```powershell
python -m clauder_workbench doctor
clauder-workbench doctor
```

## Core Commands

- `doctor`: local config/path/version/discovery checks.
- `tool-surface`: current agent-visible tool set check.
- `transport-classify`: native MCP / MCP stdio / HTTP / Rscript boundary.
- `preflight`: records three-layer preflight evidence.
- `connect`: records connection route classification.
- `async-guard`: pre-submit/register-job/list/complete/cancel guard with in-flight registry.
- `resource-gate`: advise/enforce dynamic concurrency.
- `completion-check`: validates artifacts, evidence, and policy rules.

By default, `transport-classify` and `tool-surface` use independent MCP stdio
probes where possible. Agent-supplied flags are diagnostic hints only unless
`--allow-agent-hints` is explicit.

## Exit Codes

- `0`: PASS
- `2`: WARN
- `3`: BLOCK
- `4`: TRANSPORT_UNSTABLE
- `5`: CONTRACT_FAILED

## Dynamic Concurrency Rule

`resource-gate enforce` permits increasing concurrency only when memory is below
85%, disk I/O is not blocked, Rterm/RStudio/MCP are responsive, and durable
output is still advancing.

## Async Guard Hook

```powershell
.\run.ps1 async-guard pre-submit --task-key <task> --io-mode durable_files
# Submit the actual job through the approved agent transport.
.\run.ps1 async-guard register-job --task-key <task> --job-id <real_job_id>
```

`submit --via-mcp-stdio --code-file <R>` is available only for diagnostic MCP
stdio workflows. It must not be labeled as native wrapper execution.

## Completion Contract Examples

```powershell
.\run.ps1 completion-check --mode formal `
  --require-file "validation::C:\out\validation.csv,min_rows=1,max_age_h=24,output_root=C:\out" `
  --require-file "rdata::C:\out\model.RData,min_bytes=1048576" `
  --require-transport-class NATIVE_MCP_OK `
  --require-preflight `
  --state-file C:\out\worker_state.json
```
