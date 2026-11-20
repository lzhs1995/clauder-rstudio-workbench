# Workbench 0.7.0 候選版升級

[English](UPGRADE_0.7.0.md) · [專案總覽](../README.zh-TW.md)

本候選版配對為 workbench **0.7.0**、ClaudeR R **0.16.6.9001**、MCP bridge
**0.16.6.post1**。實際來源提交與關鍵檔案 SHA 位於
[runtime-compatibility.json](../runtime-compatibility.json)。來源納入上游開發提交 `3b56327`，並保留本地會話探索、程序歸屬、非同步輸出與進度保護；不能因舊
bridge 還能啟動，就把它當成本次升級成功，也不能以未固定的 PyPI 套件替代。

macOS 與 Windows 的隔離安裝均已驗證兩個啟動器，並實際列出 42 個 MCP 工具，包含 `wake_on_message` 與 `get_async_result(wait_s=0)`。科學復現依各次紀錄的版本驗收。

四項技能都保留：[workbench](../skills/clauder-rstudio-workbench/SKILL.md)、
[compareGroups](../skills/comparegroups-guide/SKILL.md)、
[paired CMAverse](../skills/cmaverse-paired-mval/SKILL.md)、
[MplusAutomation](../skills/mplusautomation-guide/SKILL.md)。升級不改原模型、
統計驗收規則或已提交工作的身分。

完整 macOS／Windows 候選驗收目前為 **PENDING**。CI 保留三個作業系統各自的
Python 3.10／3.12 六組，另加 macOS／Windows Python 3.14；Windows PowerShell
5.1／7 分別測配置寫入與候選安裝失敗拒絕。已寫工作流、注入式本地測試、歷史
版本通過，都不等於本版雙平台原生驗收通過。

部署至 Windows PowerShell 5.1 時，含非 ASCII 文字的 `.ps1` 入口須保留 UTF-8
BOM。CP936 主機可能把無 BOM UTF-8 的下一條陳述式併入註解，而且不報語法錯誤。
須以 `Parser.ParseFile` 及實際執行回執核驗；先明確解碼 UTF-8 再 `ParseInput`
不等於測過可執行檔案的編碼。此規則只針對 PowerShell 原始碼，JSON／TOML
客戶端配置仍由寫入器使用 UTF-8 無 BOM。

## 隔離安裝與實際核驗

使用已審查、版本與 manifest 相符的固定原始碼目錄；下列命令不假設候選 tag
已經發布。從 workbench 根目錄執行，先替換示例絕對路徑。需要 Python 3.14、
R／Rscript、既有 R 相依套件及取得 pip 相依套件的網路；stage 不自動補裝 R 相依套件。

```bash
export PYTHONPATH="$PWD/skills/clauder-rstudio-workbench"
python3.14 -m clauder_workbench.paired_release stage \
  --release-root /absolute/path/isolated-releases --release-id pair-0.7.0 \
  --workbench-source "$PWD" --clauder-source /absolute/path/fixed-ClaudeR \
  --manifest "$PWD/runtime-compatibility.json" \
  --python /absolute/path/python3.14 --r /absolute/path/R --rscript /absolute/path/Rscript
```

預設只產生計畫。核對後加 `--apply` 才建立新版本目錄內的獨立 venv 與 R library。
Windows 使用相同模組／參數，先設 `$env:PYTHONPATH`，並指定實際 `python.exe`、
`R.exe`、`Rscript.exe`；完整 PowerShell 示範見[英文指南](UPGRADE_0.7.0.md)。

stage 保存來源與已安裝套件指紋，實際啟動有時間上限的新程序讀取版本、載入位置
與 hash。失敗目錄保留，不能當成成功版本選取或原樣覆寫。現役 uv 工具、客戶端
配置及健康的 RStudio 程序不會被 stage 替換。

```bash
python3.14 -m clauder_workbench.paired_release verify \
  --release-dir /absolute/path/isolated-releases/pair-0.7.0
```

verify 的新程序核驗不證明已開啟的 agent／RStudio 載入了新版。回件會列出精確
client command 與 R library。Windows 使用該版本內真正的
`Scripts/clauder-mcp.exe`，POSIX 使用 `bin/clauder-mcp`；不把 batch 文字寫入 `.exe`。

## 選取配對不等於切換客戶端

```bash
python3.14 -m clauder_workbench.paired_release activate \
  --release-dir /absolute/path/isolated-releases/pair-0.7.0 \
  --expected-active-sha ABSENT
```

只有尚無 `active.json` 時使用 `ABSENT`；已有記錄時必須提供它的實際 SHA-256。
預設只預覽，加 `--apply` 僅更新選取記錄，狀態為 `SELECTED_PAIR_ONLY`。這不寫
MCP 配置、不安裝技能副本、不修改 RStudio library，也不重新載入任何客戶端。

主管隨後才透過既有 scoped config writer，明確合併選定客戶端的 `r-studio`
入口、保留其他配置和備份。候選 R library 只供指定的新建或專用 R session 使用，
健康研究會話及其原 job ID 保持原狀。最後另核該客戶端真實工具呼叫與載入 namespace；
安裝、HTTP、獨立 MCP stdio、agent 原生工具不能互相冒充。

## 回滾完整配對

```bash
python3.14 -m clauder_workbench.paired_release rollback \
  --release-root /absolute/path/isolated-releases \
  --activation-id ACTUAL_EVENT_ID --expected-active-sha ACTUAL_CURRENT_SHA
```

核對計畫後加 `--apply`。回滾先校驗原 activation 回件、重新核驗舊完整配對，再以
compare-and-swap 檢查恢復記錄；外部已改動時拒絕覆蓋。客戶端配置和技能副本的
恢復是另外的具名操作，須依其備份與衝突檢查處理，不能把 pair rollback 當成已完成。

## 非同步輪詢與舊安裝入口

新版 `get_async_result` 使用原 `job_id` 和 `wait_s=0` 可快速讀取狀態；省略此參數
預設可能等待 300 秒。工作仍在執行或輪詢傳輸逾時，不代表應重新提交工作。
保留原 job ID、進度及證據，依呼叫端時間上限安排後續輪詢。

`install.sh`／`install.ps1` 保留為明確的舊式安裝入口，不宣稱具備隔離配對交易的
完整回滾。bridge 安裝失敗必須報錯，不能改說重用舊執行檔成功。任何新程序 probe
都不等於現役客戶端已重新載入；切換前記清每個客戶端真正使用的入口。
