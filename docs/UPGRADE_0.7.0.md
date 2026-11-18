# Workbench 0.7.0 candidate upgrade

> **Status in this checkout:** this guide describes the 0.7.0 candidate. This
> checkout still pins workbench 0.6.7 / ClaudeR 0.14.1.9002 / bridge
> 0.14.5.post1 in `runtime-compatibility.json`, and does not yet contain
> `clauder_workbench.paired_release`, the bridge's `wait_s` parameter or the
> Python 3.14 CI jobs. Do not run these commands against this checkout.

[繁體中文](UPGRADE_0.7.0.zh-TW.md) · [Project overview](../README.md)

The candidate pairs workbench **0.7.0**, ClaudeR R **0.16.5.9001** and bridge
**0.16.4.post1**. Read [runtime-compatibility.json](../runtime-compatibility.json)
for the exact ClaudeR commit and critical-file hashes. The source incorporates
the complete upstream 0.16.5 line and the maintained discovery, ownership,
async-output and progress protections. Do not substitute an old reduced bridge
or an unpinned PyPI package merely because its command still starts.

All four skills remain available: [workbench](../skills/clauder-rstudio-workbench/SKILL.md),
[compareGroups](../skills/comparegroups-guide/SKILL.md),
[paired CMAverse](../skills/cmaverse-paired-mval/SKILL.md), and
[MplusAutomation](../skills/mplusautomation-guide/SKILL.md). Their scientific
contracts and retained jobs do not change with this installer update.

Full macOS/Windows candidate qualification is **PENDING**. CI retains the six
Linux/macOS/Windows Python 3.10/3.12 jobs and adds macOS/Windows Python 3.14.
Windows PowerShell 5.1 and 7 cover config writers and failed-candidate refusal.
Configured jobs, local injected tests and historical releases are not native
cross-platform success receipts.

Keep the UTF-8 BOM on non-ASCII `.ps1` entry files when deploying to Windows
PowerShell 5.1. On a CP936 host, UTF-8 without BOM can silently merge a following
statement into a comment. Test the actual file with `Parser.ParseFile` and a
native execution receipt; decoding it as UTF-8 before `ParseInput` does not test
the executable file's encoding. This rule concerns PowerShell source files;
client JSON/TOML configuration writers continue to produce UTF-8 without BOM.

## Isolated stage and verify

Use reviewed source checkouts whose versions and source identity match the
manifest. The commands below do not assume that a candidate tag is published.
Run from the workbench checkout. Replace the three example paths before use.
Python 3.14, R/Rscript, the existing R dependencies and network access for pip
dependencies must be available; stage does not install missing R dependencies.

```bash
export PYTHONPATH="$PWD/skills/clauder-rstudio-workbench"
python3.14 -m clauder_workbench.paired_release stage \
  --release-root /absolute/path/isolated-releases --release-id pair-0.7.0 \
  --workbench-source "$PWD" --clauder-source /absolute/path/fixed-ClaudeR \
  --manifest "$PWD/runtime-compatibility.json" \
  --python /absolute/path/python3.14 --r /absolute/path/R --rscript /absolute/path/Rscript
```

This is a plan. After reviewing it, repeat with `--apply`. On Windows use the
same module and arguments, PowerShell's `$env:PYTHONPATH`, and absolute
`python.exe`, `R.exe` and `Rscript.exe` paths. For example:

```powershell
$env:PYTHONPATH = Join-Path $PWD 'skills/clauder-rstudio-workbench'
& 'C:\path\Python314\python.exe' -m clauder_workbench.paired_release stage `
  --release-root 'C:\path\isolated-releases' --release-id pair-0.7.0 `
  --workbench-source "$PWD" --clauder-source 'C:\path\fixed-ClaudeR' `
  --manifest (Join-Path $PWD 'runtime-compatibility.json') `
  --python 'C:\path\Python314\python.exe' --r 'C:\path\R.exe' --rscript 'C:\path\Rscript.exe'
```

Stage creates a new venv and R library under that release only. It keeps source
and installed-package fingerprints, runs bounded fresh-process probes, and
records their actual loaded versions and locations. A failed stage stays on
disk for diagnosis; it cannot be selected or overwritten by another attempt.
Existing shared uv tools, user configurations and active RStudio processes are
not replaced.

```bash
python3.14 -m clauder_workbench.paired_release verify \
  --release-dir /absolute/path/isolated-releases/pair-0.7.0
```

`verify` runs new probe processes; it does not establish what an already-open
agent or RStudio has loaded. Its output supplies the exact client command and
R library. Windows uses the release's native `Scripts/clauder-mcp.exe`; POSIX
uses `bin/clauder-mcp`. No batch content is written to an `.exe` file.

## Select the pair, then switch the chosen client explicitly

```bash
python3.14 -m clauder_workbench.paired_release activate \
  --release-dir /absolute/path/isolated-releases/pair-0.7.0 \
  --expected-active-sha ABSENT
```

Use `ABSENT` only if there is no `active.json`; otherwise provide that file's
actual SHA-256. The default is a plan. `--apply` changes only the selected-pair
record and returns `SELECTED_PAIR_ONLY`. It does not edit MCP configuration,
install skill copies, change an RStudio library, or reload any client.

The coordinator then merges the chosen client's `r-studio` entry through the
existing scoped config writer, preserving unrelated settings and backups.
Use the exact verified release command. Select the candidate R library only in
the intended new/dedicated R session; preserve healthy existing sessions and
their jobs. Verify the client's real tool chain and loaded namespace separately.
Installed files, HTTP connectivity, independent MCP stdio and native agent calls
remain distinct evidence layers.

## Roll back the selected pair

```bash
python3.14 -m clauder_workbench.paired_release rollback \
  --release-root /absolute/path/isolated-releases \
  --activation-id ACTUAL_EVENT_ID --expected-active-sha ACTUAL_CURRENT_SHA
```

After reviewing the plan, add `--apply`. Rollback validates the original
activation event, re-verifies the prior complete runtime pair and restores its
record only if the current record still matches. It preserves unknown external
changes. Client configurations and skill copies require their own recorded,
conflict-checked restoration; pair rollback does not pretend to restore them.

## Async polling and legacy installation

The new bridge supports `get_async_result` with the original `job_id` and
`wait_s=0` for a quick status check. Without that parameter the bridge may wait
up to 300 seconds by default. A running job or transport timeout is not a reason
to submit the work again. Keep bounded polling, progress messages and original
job evidence; use longer waits only when the caller's timeout permits them.

`install.sh` and `install.ps1` remain explicit legacy installation paths, not
the isolated paired transaction. A failed bridge installation must fail rather
than report an existing old executable as success. Actual fresh-process probes
still do not prove that existing clients reloaded. Do not mix the two routes
without recording which entry point each client uses.
