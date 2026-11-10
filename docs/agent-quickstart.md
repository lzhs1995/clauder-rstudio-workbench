# Use with an agent / 與 Agent 配合使用

The skill files are ordinary UTF-8 Markdown. An agent with repository file access
can read them directly. Automatic discovery and native MCP execution depend on
the client and its installed configuration; neither is guaranteed for every agent.

技能是 UTF-8 Markdown。具備檔案讀取能力的 Agent 可直接使用；自動發現技能及
原生 MCP 呼叫是否可用，取決於客戶端與實際設定，不能概稱全部已支援或驗證。

## Choose a task

Paste one of these instructions into your agent after opening this repository:

```text
Read AGENTS.md and skills/clauder-rstudio-workbench/SKILL.md. Connect to the
selected existing RStudio session, verify the current tool connection, and
preserve any running jobs. Report configuration, connection, and execution separately.
```

```text
請讀 AGENTS.md 與 skills/comparegroups-guide/SKILL.md，依我的資料及表格規格
產出描述性統計表。先核標籤、缺失值、分組與面板結構，保留計算及驗證記錄。
```

```text
Read AGENTS.md and skills/cmaverse-paired-mval/SKILL.md. Prepare paired M=0/M=1
CMAverse four-way decomposition for my stated model. Reuse the original job IDs,
keep full model objects, and verify scientific outputs before declaring completion.
```

## Install and verify

Follow the version-paired commands in the [English README](../README.md#quick-start)
or [繁體中文介紹](../README.zh-TW.md). Use a fresh destination; never overwrite a
dirty checkout or an active task's pinned runtime.

| Client | Repository support | What must still be checked |
| --- | --- | --- |
| Codex | Explicit installer configuration and skill directory | Current task actually lists and invokes the `r-studio` tools |
| Claude Code | Explicit installer configuration; project/global scope matters | The intended project loads the actual MCP entry |
| GitHub Copilot CLI | Explicit installer configuration | Native tool surface and current session execution |
| Gemini, Antigravity, other clients | Manual `SKILL.md` reading; client-specific MCP setup | The client's supported config schema and real tool calls; no universal installer claim |

Start with the read-only doctor for the configured client. A successful doctor
does not replace a real native-tool check. For formal work, follow the selected
skill's connection and evidence steps. If the agent has no native MCP tool
surface, report that limitation and use only an explicitly supported fallback.

Use the core skill's resource-aware fan-out workflow for independent R workers.
Run ordinary single descriptive tables directly; multiple agent conversations
alone do not create isolated R sessions or permit simultaneous writes to shared
objects. Keep output directories distinct and merge only verified results.

## Local credentials and paths

Keep real credentials and machine paths in local configuration. Public examples
use `$HOME`, `$env:USERPROFILE`, or explicit placeholders. The agent should read
the configured local entry instead of asking you to paste secrets into a public
issue, repository file, or log. A private repository is not a secret manager.

本機設定可保留完整可用的路徑與憑證；公開技能保留讀取方法及範例。這樣不需要
以過度脫敏破壞本機效率，也不需要把密鑰提交到 GitHub。
