# CFPS 科学边界审计

技术回读、历史复原和科学采用必须分层记录。Windows 复盘时，将 156 个历史/当前版本差异、25 个 LRT 候选、MI v3 和 rank/derived score sources 放到同一个只读边界报告中，但不能用一个层级的通过替代另一个层级。

## 版本差异

只有在历史显示值、运行时输出哈希和脚本/模型身份都一致时，才能把单元格标成历史显示技术闭合。当前数据差异要进入敏感性或限制。对于本任务明确的 20260214 初稿复现目标，156 个已匹配单元格可由 `cfps_historical_version_adoption_20261004` 冻结为历史显示版本；这关闭历史复现版本选择，不等于修正数据的 scientific release。Table 4.2 的 16 个 AIC/BIC 舍入格另按 `cfps-rounding-contract.md` 固定 R `round()` 的显示规则。

## LRT

LRT p 值发布前必须同时保存精确的 null/alternative 输出对、完整嵌套语句、相同估计和插补合同、输入/输出哈希以及正确的 pooled likelihood 计算。存在编号 `.out` 但缺少精确 pair、观察协变量分布改变或只完成部分 pooling 时，保持 `sensitivity_only`/`defer_source_followup`/`defer_nested_pooling_audit`，不要填入 p 值。

## MI 与派生得分

10 份插补文件的列数、行数和字节对齐只能证明数据读回。收入定义、负值/缺失语义、确定性二分类、最终停止规则和链混合证据仍要独立审查；不能截零、取绝对值或无依据重编码。rank/score source 还需封闭 tie、availability、个人/夫妻身份和输入哈希，之后才物化消费者。

本机 Windows 只读入口：

- `work/pp_lgcm_reconciliation_20261001/audit_cfps_scientific_boundaries_20261004.py`；
- `reports/cfps_scientific_boundary_audit_20261004/cfps_scientific_boundary_audit_v1.{json,md}`。

该审计的 `new_mplus_submissions=0` 是成功的复盘策略：已有历史证据优先，只有真正缺少证据且资源门通过时才建立隔离新估计。

本轮进一步把历史初稿复现与修正后科学采用分开：156 个版本差异、16 个舍入格和 331 个技术审查格均已形成隔离历史复现合同；这些合同不会修改 DOCX 或自动放行 MI/LRT/rank/图形结果。
