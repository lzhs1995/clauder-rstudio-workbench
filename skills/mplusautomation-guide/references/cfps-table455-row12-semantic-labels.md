# CFPS Table 4.5.5 第 12 行：显示值与语义标签

当论文表格中的数值可以由历史 `.out` 精确产生，但正文标签与该 `.out` 的 `XWITH` 结构不一致时，先区分“显示值 producer”和“语义候选”，不要直接重跑模型、改写 DOCX 或按显著性选择结果。

本项目的只读核验链如下：

1. `relative2.R:132128–132134` 读取四个 type-41 输出；`i_mod_s` 对应 `type41_s2i1`，`s_mod_i` 对应 `type41_i2s1`。
2. `relative2.R:132696–132737` 组装并导出 `EDU12_MEAN` 的 moderation 表。
3. `i_mod_s` 的输入使用 `s4 XWITH i1`，其 `S5 ON XWZ_INT` 精确产生初稿显示值 `0.163 (0.083), p=.049`。
4. 初稿正文标签写作 `I4_4 × S1 × Edu → S5`；严格按该标签对应的 `s_mod_i` 输入，历史值为 `0.000 (0.006), p=.939`。

因此状态应记录为 `DISPLAY_VALUE_PRODUCER_RESOLVED_LABEL_MAPPING_PROPOSAL_OPEN`：

- 保留 `i_mod_s` 作为初稿显示值的历史 producer；
- 提出标签映射修正 `S4 × I1 × Edu → S5`，但不自动替作者接受；
- 将 `s_mod_i` 作为严格标签语义的敏感性候选；
- 把作者裁决、显示值、语义候选和输入哈希写入 decision packet/gate；
- 在裁决前不修改原始 R、Mplus `.inp/.out`、DOCX，也不提交新的 Mplus。

2026-10-05 的复核进一步确认：正文表 4.5.5 的 producer 是
`relative2.R:78096–121333`，表 4.5.6 的 producer 是
`relative3.R:2925–73557`；两表共 25 行、107 个当前候选稿系数单元格，
当前 v42 的 X/W/Z/Y 语义不匹配为 0，且 Python 与原生
`MplusAutomation` 回读一致。详细只读回执见
`reports/cfps_table455_456_acceptance_20261005/REPORT.md`。这关闭了两表的
出处追踪，但不自动关闭原始 20260214 初稿的历史标签裁决、LRT 或科学释放。

这条规则防止“producer 已找到”被误报成“论文科学合同已闭合”，也防止通过换模型或换标签追逐显著性。
