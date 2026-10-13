# CFPS 派生表的正文标签—R `XWITH`—Mplus 参数核验

三重交互表不能用“哪个历史 `.out` 的三位数字与 Word 相等”来决定
producer。数字相等只能形成候选；`X/W/Z/Y` 的正文语义和实际 R block 才能
确定模型。这个边界在 20260214 初稿的 Table 4.5.5/4.5.6 中实际发生过：
12 个 producer 组、52 个单元格的正文显示值与反向 basename 的历史输出相等，
但 R block 的 `XWITH` 与正文标签对应的是另一份历史输出。

## 逐组合同

对每个 Word 行保存以下字段：

1. 原始 DOCX 路径、SHA-256、表号、python-docx 行索引和 X/W/Z/Y 文本；
2. R 脚本 SHA-256、包含 `mplusObject`/`mplusModeler` 的精确 block 起止行，
   以及 `xw_int`、`xz_int`、`xwz_int` 的原文；
3. 语义 producer 的 `.inp/.out` 路径、哈希、`MODEL RESULTS`/`New/Additional
   Parameters` 参数行和终态诊断；
4. 与正文数字匹配的历史输出作为 `manuscript_value_candidate` 单独保留，
   不能覆盖语义 producer；
5. 每个单元格的参数名、estimate、SE、p、显著性符号、正文显示值和差值。

将 Word 标签规范化后，要求：

```text
xw  = {X, W}
xz  = {X, Z}
xwz = xw_int XWITH Z
```

`I4_4` 是 Word 标签别名，脚本中应核对为 `i4`。对于 `MODEL CONSTRAINT`
中的简单斜率，参数前缀由潜变量类型决定：
`W` + X 的 `i/s` + W 的 `i/s` + Y 的 `i/s`，例如
`S1 × I3 → S5` 使用 `WSIS0/WSIS1`。不能从 `i_mod_s` 文件名猜参数。

## Windows 只读实现

当前实现位于：

```text
work/pp_lgcm_reconciliation_20261001/
  verify_docx_derived_rows_20261004.py
  reconcile_derived_semantics_by_word_labels_20261004.py
```

Windows Python 3.14 执行后生成：

```text
reports/cfps_derived_semantic_reconciliation_20261004/
  docx_row_evidence_v1.json
  semantic_reconciliation_v2.json
  semantic_reconciliation_v2.md
  semantic_table_correction_candidate_v1.csv
```

表格组装层也必须单独追踪。`readModels()` 的对象别名和 `gt()` 的
`tab_spanner()` 不是 Mplus 的模型语义：在本次初稿中，连续分支明确把
`s_mod_i` 读入 `type13_i2s1`、把 `i_mod_s` 读入 `type13_s2i1`，随后固定标为
`I2S1`、`S2I1`；分类分支同样存在该类别名约定。于是正文行按 X/W 标签整理时，
可能显示反向 alias 的数值，形成“正文有数值、却找不到 producer”的假象。应同时
保存以下三层证据：

1. R 的 `readModels` 行、`model.result` 重命名和 `tab_spanner` 行；
2. 语义 producer 的精确 `XWITH` block 与历史 `.out` 参数；
3. 正文显示值对应的反向 `.out`，以及可找到时的历史 sidecar DOCX。

本次追踪脚本和报告为：

```text
work/pp_lgcm_reconciliation_20261001/trace_r_table_assembly_20261004.py
reports/cfps_derived_semantic_reconciliation_20261004/
  r_table_assembly_trace_v1.json
  r_table_assembly_trace_v1.md
```

历史初稿复现若需要保留正文已经打印的数值，可使用隔离的
`historical_display_adoption_candidate_v1.{json,md}`。该候选把历史显示 `.out` 与语义
producer 并列保存，记录 R 组装警告，不修改 DOCX，也不把语义纠正自动发布。

报告覆盖 Table 4.5.5/4.5.6 的 12 组、52 格，R 组装证据全部闭合；sidecar DOCX
只作为补充，部分行因后续人工合并而没有独立 sidecar。历史 `.out` 才是完整的
展示值证据。该发现只能关闭“producer 无法恢复”的技术判断，不能自动决定论文
应采用语义值还是历史显示值；在作者选择、LRT/估计合同和逐格验收完成前，仍保持
`formal_scientific_release=false`。

该实现先直接读取原始 DOCX，再读取 R block 和历史输出；不提交 Mplus、不改
R script、`.inp/.out` 或 DOCX。原始 DOCX 直接复核通过后，才允许建立隔离的
校正候选。校正候选仍不等于作者采用：必须保留
`formal_scientific_release=false`，直到每格的 producer、数值、LRT/估计合同和
论文版本选择单独关闭。

## 常见误判

- 把数值命中的反向 `i_mod_s`/`s_mod_i` 输出当作源；
- 把 `.out` 文件名当作模型语义，而不读取 R 的 `XWITH`；
- 将 python-docx 行号减一。历史 packet 使用的是表头为 0 的实际行索引；
- 用 Word 显示值反推精确 Mplus 结果；显示值只能作为历史展示证据；
- 因历史 `.out` 存在 `SAVEDATA` 错误而丢弃其中可读的 `MODEL RESULTS`，或反过来
  把可读结果称为干净正式重估。两种状态必须分开记录。
