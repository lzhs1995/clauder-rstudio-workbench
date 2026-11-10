# Agent entry point / Agent 使用入口

This repository is a portable collection of skills and tools. Read the relevant
`SKILL.md` before executing its scripts; resolve its relative references against
the skill directory, not the caller's working directory.

本倉庫提供可移植的技能與工具。先讀對應的 `SKILL.md`，再執行程式；相對路徑
以該技能目錄為準。繁體中文總覽見 [README.zh-TW.md](README.zh-TW.md)。

| Task / 任務 | Entry / 入口 |
| --- | --- |
| Connect to RStudio, check MCP, submit/poll async R jobs / 連接與非同步執行 | [clauder-rstudio-workbench](skills/clauder-rstudio-workbench/SKILL.md) |
| Descriptive tables and compareGroups / 描述性統計表 | [comparegroups-guide](skills/comparegroups-guide/SKILL.md) |
| Paired M=0/M=1 CMAverse four-way decomposition / 成對中介值四項分解 | [cmaverse-paired-mval](skills/cmaverse-paired-mval/SKILL.md) |
| Mplus model workflows / Mplus 模型工作流程 | [mplusautomation-guide](skills/mplusautomation-guide/SKILL.md) |

## Execution contract

- Reuse the task's selected runtime, RStudio target, original job IDs, and
  evidence. Installing a skill or changing a config does not reload a live agent.
- Do not restart a healthy RStudio session or resubmit a running job because a
  polling call timed out. Inspect the original job's current state.
- Distinguish readable skill files, MCP configuration, HTTP/stdio connectivity,
  actual native tool calls, and verified scientific results. Never claim one
  proves the next. Client support is described in
  [the agent guide](docs/agent-quickstart.md).
- Prepare independent analyses concurrently where resource limits permit;
  assign one writer per result directory and shared session object. Do not
  mutate another agent's active session or overwrite another task's outputs.
- Use synthetic data for tests. Keep credentials, local configuration, private
  research data, participant identifiers, and raw session logs outside Git.
  Read [the public/private boundary](docs/public-private-boundary.md).
- Build only on a local development machine or GitHub Actions. Never build or
  compile source on a VPS or production server.

This file is a navigation layer, not a replacement for the skills' scientific
contracts. It does not authorize publication of private data or secret values.
