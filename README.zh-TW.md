# clauder-rstudio-workbench

![ClaudeR RStudio Workbench — connect, describe, decompose, verify](docs/assets/workbench-logo.svg)

[English](README.md) · 繁體中文

讓 AI agent 透過 ClaudeR 與 MCP 操作 RStudio 的技能集合、安裝器與可執行工作流程。核心工具負責連線檢查、會話識別、非同步任務、平行 worker、進度與結果驗收；領域技能提供描述性統計、CMAverse 成對 bootstrap 和 MplusAutomation 的操作規範。

ClaudeR 提供 RStudio addin 與 MCP bridge；本專案整理安裝、執行、診斷和證據保存。統計計算仍由對應的 R 套件或 Mplus 執行，成功產生檔案不等於研究假設或因果識別已獲驗證。

## 選擇技能

| 技能與實際入口 | 適用工作 | 主要界線 |
|---|---|---|
| [clauder-rstudio-workbench](skills/clauder-rstudio-workbench/SKILL.md) | 綁定 RStudio、檢查工具、追蹤非同步任務與平行 worker、核對輸出 | 安裝成功、HTTP 可用、獨立 MCP stdio 與 agent 原生呼叫須分別驗證 |
| [comparegroups-guide](skills/comparegroups-guide/SKILL.md) | 使用 compareGroups 建立描述性統計、樣本流失分析與三線表，保留數值、RDS 和驗證紀錄 | 先確認標籤、缺失值、分析單位與重複觀測；DOCX 是展示，原始數值另存 |
| [cmaverse-paired-mval](skills/cmaverse-paired-mval/SKILL.md) | 成對 M=0/M=1 bootstrap、四分解、worker 合約與結果核驗 | 成對重抽樣的實作一致性不代表因果識別成立；新資料與規格須另行確認 |
| [mplusautomation-guide](skills/mplusautomation-guide/SKILL.md) | 透過 MplusAutomation 驅動 Mplus 模型、批次執行、診斷與表格整理 | 須有相容且合法授權的 Mplus；模型家族的實作與驗證範圍以技能登錄表為準 |

此表反映目前 `main` 原始碼。固定版 `v0.6.7` 包含前三個技能；`mplusautomation-guide` 是之後加入 `main` 的內容。需要第四個技能時，使用包含該目錄的已審查提交，不把舊版安裝視為已安裝全部新技能。

## 安裝與版本

Windows 使用 `install.ps1`；macOS 和 Linux 使用 `install.sh`。準備 Git、R、RStudio、Python 與 uv；實際最低版本及選項見[英文安裝說明](README.md#quick-start)。Linux 的 RStudio／addin 仍須能在目標使用者的工作階段運行。

配套版本由 [runtime-compatibility.json](runtime-compatibility.json) 指定。以下沿用固定版 `v0.6.7` 與 ClaudeR `v0.14.1.9002-lzhs.1`，不把任意上游最新版當成已驗證替代品。所有目的目錄必須尚不存在；保留已有研究會話和未提交工作樹。

### macOS／Linux：固定版快速安裝

```bash
git clone --branch v0.14.1.9002-lzhs.1 --single-branch https://github.com/lzhs1995/ClaudeR.git "$HOME/projects/ClaudeR-v0.14.1.9002-lzhs.1"
git clone --branch v0.6.7 --single-branch https://github.com/lzhs1995/clauder-rstudio-workbench.git "$HOME/projects/clauder-rstudio-workbench-v0.6.7"
cd "$HOME/projects/clauder-rstudio-workbench-v0.6.7"
./install.sh --clauder-dir "$HOME/projects/ClaudeR-v0.14.1.9002-lzhs.1" --configure-codex --sync-agents-skill
"$HOME/.local/bin/clauder-workbench" doctor --expect-client codex --check-toml-parse
```

可先在安裝命令末尾加上 `--dry-run` 檢查計畫。Claude Code 或 Copilot 的設定選項分別為 `--configure-claude`、`--configure-copilot`；只選需要設定的客戶端。

### Windows PowerShell：固定版快速安裝

```powershell
git clone --branch v0.6.7 --single-branch https://github.com/lzhs1995/clauder-rstudio-workbench.git "$env:USERPROFILE\projects\clauder-rstudio-workbench-v0.6.7"
cd "$env:USERPROFILE\projects\clauder-rstudio-workbench-v0.6.7"
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ConfigureCodex -SyncAgentsSkill
& "$env:USERPROFILE\bin\clauder-workbench.cmd" doctor
```

可先加 `-DryRun`。其他客戶端選項為 `-ConfigureClaudeCode`、`-ConfigureCopilot`；目前沒有對所有 agent 通用的自動設定承諾。安裝器只有在指定 configure 選項時才修改對應 MCP 設定。

## 讓 agent 使用

每個 `SKILL.md` 都可直接閱讀，相關檔案以相對路徑連結。具備檔案讀取與所需命令／MCP 能力的 agent 可以依照操作，但自動發現技能、`$技能名稱` 語法與原生工具名稱取決於客戶端。

- Codex：可使用安裝器管理的技能目錄與 MCP 設定；例如 `$clauder-rstudio-workbench 連接 RStudio`。
- Claude Code／GitHub Copilot CLI：安裝器提供對應 MCP 設定；若未自動發現技能，請明確指定要讀取的 `SKILL.md`。
- 其他 agent：從原始碼或共用技能目錄讀取完整技能及相對檔案，依該客戶端支援的機制設定 MCP，並實測呼叫。共用目錄不保證所有客戶端都會掃描。

可直接交給 agent 的指令：

```text
讀取此 checkout 的 skills/clauder-rstudio-workbench/SKILL.md，選定實際 RStudio 會話，依技能執行連線與證據檢查。保留既有研究物件；非同步工作沿原 job ID 查詢，不因暫時連線失敗重送。
```

只有新建且尚未啟動 addin 的 RStudio 會話才需要執行：

```r
library(ClaudeR)
claudeAddin()
```

`doctor` 通過不是當前 agent 原生工具驗收。正式原生工作須依核心技能取得真實 `list_sessions → execute_r → execute_r_async → get_async_result` 證據；設定檔、HTTP、獨立 stdio 與原生工具的結果不可互相冒充。不要為更新磁碟上的版本而中斷健康的研究會話。

## 研究資料與公開程式

公開技能與程式使用可移植路徑、合成範例和合約模板。本機帳號憑據、認證 token、個體研究資料與私人執行紀錄應留在受控的本機設定或證據目錄。設定路徑可由環境或安裝參數提供；公開文件不需要內嵌秘密才能讓 agent 使用。

三線表仍需視覺檢查；長工作須保留進度和原 job ID；正式結果須能追溯至輸出與驗證紀錄。工具驗證不取代研究設計、模型假設或投稿規範的實質判斷。

## 延伸閱讀

- [英文完整 README：安裝、操作、驗證與故障排除](README.md)
- [ClaudeR 架構與操作指南（簡體中文）](docs/ClaudeR_架构说明与clauder-rstudio-workbench使用指南.md)
- [教程審查與技能設計紀錄（簡體中文）](docs/ClaudeR_教程审查与SKILL设计建议.md)
- [版本紀錄](CHANGELOG.md) · [配套執行環境](runtime-compatibility.json) · [MIT 授權](LICENSE)
