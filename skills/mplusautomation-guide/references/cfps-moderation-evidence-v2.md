# CFPS 调节效应证据审计 v2

本记录对应 2026-10-04 的 Windows/RStudio/ClaudeR 只读审计。入口脚本为
`work/cfps_moderation_evidence_v2_20261004.R`，输入是已有 CFPS 调节 `.out/.inp`，
输出目录是 `reports/cfps_moderation_evidence_v2_20261004/`。它不调用 Mplus，
不覆盖原始 R、数据、输出或 DOCX。

## 固定结果

- 56/56 个 `.out` 可由 `MplusAutomation::readModels()` 读回，168 行交互参数。
- 原始报告 p<.05 为 12 行、p<.10 为 21 行；BH 和 Bonferroni 仅作审计列，各有
  5 行 p<.05。它们不是规格筛选或确认性推断依据。
- 56 个文件没有可用的 `readModels()` 参数协方差对象，因此条件斜率差的正式 B2
  Wald 检验保持开放；不能以“一个组显著、另一个组不显著”替代组间检验。
- 输入合同的 `XWITH`、`TYPE=COMPLEX`、`CLUSTER`、`MODEL CONSTRAINT` 已逐文件记录。

NotebookLM 的 follow-up 进一步把顺序固定为：先完成参数/协方差读回、联合 Wald、
条件斜率/Johnson–Neyman 和带区间的边际效应图；只有资源恢复且指定模型需要时，
才在隔离目录补 D2/D3 MI-LRT、LMS 收敛/边界诊断或多组不变性。没有完整协方差时，
不能把单个简单斜率的显著性当作调节结论。

## 安全的解释和优化顺序

先冻结尺度、编码、中心化、控制变量、聚类、估计量和 MI 合并合同；然后在已有输出
上完成协方差/条件效应可用性核验。内存和输入诊断满足准入后，才可在隔离目录运行
理论预先指定的原始尺度 vs 均值标准化、多组/Wald 交叉核验和 `S5@0` 边界敏感性。
所有尝试和失败都进入 manifest；不得按 p 值切换规格、切点、插补成员或控制变量，
不得平均 MI p 值或只画/只报告显著简单斜率。

完整审计图和结论见任务目录同名 `reports/cfps_moderation_evidence_v2_20261004/`。
