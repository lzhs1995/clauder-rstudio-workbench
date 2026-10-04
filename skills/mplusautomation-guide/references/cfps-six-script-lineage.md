# CFPS 六份 Rscript lineage 与逐行回读

这份参考把 PP-LGCM 初稿的六份原始 Rscript 与既有 Mplus `.inp/.out`、表格/图形 producer 的回读顺序固定下来。它只描述可复核的 source lineage，不授权重新估计，也不把“某行出现 `mplusObject`”自动等同于某个正文表格。

## 固定脚本角色

| 原始脚本 | 初稿用途 |
|---|---|
| `20251003 closeness&depression_relative.R` | 相对指标主分析、直接效应、调节效应和主要表图；正文 Table 4.2.1/4.2.2 的历史模型规格集中在该脚本的主分析区段（逐行审计覆盖 `134:6986`）。 |
| `20251003 closeness&depression_relative2.R` | 连续三重交互及异质性。 |
| `20251003 closeness&depression_relative3.R` | 二分三重交互及异质性；Appendix 的三重交互图形 producer 也在此脚本的 `ThreeWay_Combined_EDU_` 区段。 |
| `20251003 closeness&depression_absolutive.R` | 共同插补、均值模型和绝对指标补充检验；含插补 `DATA IMPUTATION` 与主表导出。 |
| `20251003 closeness&depression_absolutive2.R` | 绝对指标三重交互分支。 |
| `20251003 closeness&depression_absolutive3.R` | 绝对指标三重交互分支；当前初稿未发现其独有结果表。 |

## 必须保存的逐行证据

对每份脚本保存字节 SHA-256、总行数以及下列关键语句的精确行号和原文：`mplusObject`、`mplusModeler`、`DATA IMPUTATION`、`VALUES`、`XWITH`、`MODEL CONSTRAINT`、`SAVEDATA`、`ggsave`、`newdir`。当前只读回执为：

`reports/cfps_source_line_audit_20261004/cfps_source_line_audit_v2.{md,json}`。

审计使用 Windows 原始路径 `C:\Users\LZHS\Desktop\interge_rela`，不执行 Rscript，不调用 Mplus，不修改原始脚本、原始数据、原始 `.inp/.out` 或 DOCX。导出路径和 `newdir` 必须再与实际结果文件的 canonical root、`.inp/.out` SHA、`MplusAutomation::readModels()` 身份一起核对。

## 关键语义边界

- `relative.R` 的初稿注释明确区分“未基期标准化/基期标准化”“未均值标准化/均值标准化”“绝对/相对指标”，同时在模型字符串中保留真实增长因子与控制变量。表格 producer 绑定应以这一语义和实际 `MODEL`/`OUTPUT` 为准，不能只用文件名或表格标签反向猜测。
- 同一脚本既包含模型定义、`mplusModeler(..., run=TRUE)` 和结果表/图导出；“脚本中有调用”不代表该次调用是初稿最终 producer。必须优先匹配已有成功 `.out`、输入指纹、导出文件和 DOCX 嵌入媒体。
- `DATA IMPUTATION` 中的 `VALUES` 是 Mplus 对插补值的支持范围约束。观测数据回读显示 `pinc12` 为 1–5、`pinc212` 为 0–18.864 万元、`finc12` 为 0.0005–112 万元，观测值无负数；因此 `finc12`/`pinc212` 的负插补值属于支持范围合同问题。不能用截零、取绝对值或挑选某个 MI 成员来制造显著性。
- `XWITH`/`MODEL CONSTRAINT` 只证明候选交互的语义来源；调节显著性必须有参数、标准误、协方差/Wald 或条件斜率区间。没有可用 VCOV 时，名义 `p<.05` 行只能做历史审计计数，不能释放为正式调节结论。
- 图形必须按 DOCX 目标文件去重，再用 SVG 文本标签、原始 `ggsave` 目标和脚本区段绑定。当前 Figure 3.1 已确认两个原始 SVG 和 DOCX 媒体文本一致，并绑定到 `relative.R` 的 `7400:7458`、`7506:7544`、`10763:10799`、`11522:11529` 语义区段；不存在精确 generator receipt 的图形继续保留来源边界。

## 门控

1. 先回读既有 `.out` 与 producer；已有有效输出不得因为作者科学门开放而重复估计。
2. 若发现输入错误、非正常终止、非正定 Fisher、SE 缺失或 MI 不完整，保留原文件并进入 deferred/limitation；只有新的、明确的输入/规格/资源合同才能在隔离目录重开。
3. 调节效应优化只能执行预先指定的尺度/中心化、可靠性、缺失处理、联合 Wald、条件斜率、FDR/FWER 和边际效应图检查；禁止按最小 p 值挑规格、事后二分、删除控制、平均 MI p 值或隐藏不收敛结果。
4. 表格逐格核对、CFPS scientific gate、CHARLS reuse-first gate 和最终 PDF-only NLM 三审三校均关闭后，才把 guide 从 draft 升级为 release。
