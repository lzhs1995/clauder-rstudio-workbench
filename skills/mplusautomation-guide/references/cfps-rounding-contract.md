# CFPS 历史表格舍入合同

对逐单元格 ledger 中标记为 `rounding_contract` 的 16 个 Table 4.2 fit 单元格，先绑定 R script、精确 source line、`.out` SHA 和正文单元格，再从既有 Table 4.2 读回报告取得原始 AIC/BIC 与初稿显示值。

本次 Windows 复核确认：ledger 使用零基列号，第 5 列是 AIC、第 6 列是 BIC；relative.R 与 absolutive.R 各贡献 8 个单元格。`.out` 原始值保留三位以上小数，初稿显示两位小数。逐格按观测到的 R `round()` 二进制浮点行为复现，包括 `.445/.855/.355` 显示为 `.44/.85/.35`，16/16 完全一致。

这关闭的是历史初稿的显示精度合同，不修改原 DOCX/R/Mplus，也不把当前输入版本自动升级为正式科学采用。证据在 `reports/cfps_rounding_contract_20261004/cfps_rounding_contract_v1.{json,md}`。
