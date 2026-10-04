# CFPS 图形 producer 追溯（Windows，只读核验）

## 适用范围

本合同针对初稿正文
`20260214 代际亲近度对老年心理健康的影响——基于家内差异的视角.docx`。
Word 会把原始 SVG 重新写入 `word/media`，因此媒体文件的 SHA-256 不能直接用来
证明源文件相同。可靠顺序是：先按正文 caption 和媒体配对，再读取嵌入 SVG 的
坐标轴、图例、斜率标注，最后与 `interge_rela` 中的既有 SVG 文本标签集合匹配，
并回绑六份 R script 的动态输出命名行。PNG/SVG 同编号是同一逻辑图形的两个
Word 媒体表示。

只读回执：
`reports/cfps_figure_provenance_20261004/cfps_embedded_svg_match_v1.json`（正文）和
`cfps_embedded_svg_match_appendix_v1.json`（Appendix）。正文扫描了 18 个 SVG（对应
18 个 PNG/SVG 逻辑图形媒体），其中 16 个精确匹配、2 个保留为六份脚本之外的历史
候选；Appendix 扫描了 6 个 SVG（12 个媒体），6 个均精确匹配 `relative3.R` 的
`ThreeWay_Combined_EDU_` producer。两份报告共扫描 39 个既有 SVG，没有修改 DOCX、
R script、Mplus 输入/输出或数据，也没有提交新的 Mplus。

## 已闭合的 16 个正文图形

| 正文图 | 既有 producer | R script 动态生成位置 |
|---|---|---|
| Figure 4.4.2.1 SD_diff | `result_pp_lgca_continu.panel_best_clo_ces8sd_covar_time12_22/TwoWay_type12_s1i2_S1I2_INT_S5.svg` | `20251003 closeness&depression_relative.R` 的 `TwoWay_` 模板，约 59480 行 |
| Figure 4.4.2.2 Gender_diff | `.../TwoWay_type13_s1i3_S1I3_INT_S5.svg` | `relative.R` 的 Gender_diff `TwoWay_` 模板，约 61756 行 |
| Figure 4.4.2.3 Sib_diff | `.../TwoWay_type14_s1i4_S1I4_INT_S5.svg` | `relative.R` 的 Sib_diff `TwoWay_` 模板，约 64033 行 |
| Figure 4.4.2.4 Sib_diff4 | `.../TwoWay_type14_s1i4_S1I4_INT_S5_4.svg` | `relative.R` 的 Sib_diff4 `TwoWay_` 模板，约 66307 行 |
| Figure 4.5.2 (3 panels) | `SimpleSlope_EDU_type1_I1SX_INT_on_I5.svg`; `SimpleSlope_EDU_type1_S1SX_INT_on_S5.svg`; `SimpleSlope_EDU_type2_I2SX_INT_on_I5.svg` | `relative.R` 的 EDU `SimpleSlope_` 模板，约 24891/24917 行 |
| Figure 4.5.3 (2 panels) | `SimpleSlope_URBAN_type3_I3SX_INT_on_S5.svg`; `SimpleSlope_URBAN_type5_S4SX_INT_on_S5.svg` | `relative.R` 的 URBAN `SimpleSlope_` 模板，约 25757/25783 行 |
| Figure 4.5.4 (2 panels) | `SimpleSlope_PINC_type1_I1SX_INT_on_I5.svg`; `SimpleSlope_PINC_type1_S1SX_INT_on_S5.svg` | `relative.R` 的 PINC `SimpleSlope_` 模板，约 26624/26650 行 |
| Figure 4.5.6 (5 panels) | `ThreeWay_Facet_EDU_type12_i2i1_S5.svg`; `...i2s1_S5.svg`; `...s2s1_S5.svg`; `ThreeWay_Facet_URBAN_type31_s1s3_S5.svg`; `ThreeWay_Facet_EDU_type4_41_s1s4_S5.svg` | `20251003 closeness&depression_relative3.R` 的 `ThreeWay_Facet_` 模板，约 10590/60793/79946 行 |

这里的“闭合”表示 Word 嵌入 SVG 的全部关键文本标签（斜率数值、坐标轴、图例
条件）与既有 SVG 完全匹配，且源命名模板存在于指定 R script。它不等于重新估计；
这些图形应优先复用历史 producer。

## Appendix 图形

Appendix 的 6 个 SVG（`image2.svg`、`image4.svg`、`image6.svg`、`image8.svg`、
`image10.svg`、`image12.svg`）均按空格归一后的文本标签精确匹配到：

- `ThreeWay_Combined_EDU_type12_i2i1_S5.svg`
- `ThreeWay_Combined_EDU_type12_i2s1_S5.svg`
- `ThreeWay_Combined_EDU_type12_s2s1_S5.svg`

每个 PNG/SVG 配对是同一逻辑图形的两个 Word 媒体表示；Appendix 仍未触发新估计。

## 两个图形的边界

`图3.1 Details of sample selection` 和 `图3.1 平行过程潜在增长曲线模型的结构
路径图` 的 SVG 在 `interge_rela` 中存在相似的 `GMM_trajectory_*` 文件，但其命名
和生成语句没有出现在本次指定的六份 `closeness&depression_*` script 中。因此本次
报告将它们标为 `LABEL_MATCH_CANDIDATE`，不把相似文件名升级为六份脚本的正式
producer。若要关闭这两项，应继续读取历史附件/早期 GMM 脚本的生成记录；不需要
重跑 CFPS Mplus。

这项边界已在
`reports/cfps_figure_provenance_20261004/cfps_figure31_source_boundary_v1.{json,md}`
做了第二层只读审计。六份指定的 `closeness&depression_*` script 中，
sample-selection 生成证据为 0/6、结构路径图生成证据为 0/6，也没有发现
`semPlot`、`qgraph`、`DiagrammeR` 等路径图调用。相邻的六份 GMM/LTA script 全部包含
`GMM_trajectory_*_combine.svg/png` 轨迹图输出，但这只说明相邻历史轨迹图的 producer，
不能把它们升级为图3.1。六份脚本里出现的 `process1 = Means` 等普通区段标签已单独
记录，不能作为路径图证据。

因此两个图3.1逻辑媒体继续保持 `SOURCE_BOUNDARY_OPEN`。这是可复现性边界，不是对
原作者生产软件的推断；只有找到图形原始源文件、真实生产脚本或带生成路径的历史
receipt，才可关闭该门。

### 2026-10-04 v2 纠偏：语义 producer 与图形 receipt 分开

逐行复核 `relative.R` 后，两个 Figure 3.1 图形的模型/样本语义 producer 已经定位，
不能再表述为“没有 R 来源”：

- 样本流程图的输入、失访/分析/插补合并、计数、标签和描述性表在
  `relative.R:7400-7458`、`:7506-7544`；
- 结构路径图中的 `i1/s1`、`i5/s5` 和 `i5 on i4 i1`、`s5 on i4 s4 i5 i1 s1`
  在 `relative.R:10763-10799`，调节扩展的 `XWITH` 路径在 `:11522-11529`。

因此应使用两层状态：

`SEMANTIC_SOURCE_CONFIRMED; GRAPHIC_GENERATOR_RECEIPT_OPEN`。

脚本没有发现将这两个图形排版为当前 SVG 布局的 `ggsave`、`DiagrammeR`、
`semPlot` 或 `grid::arrow` receipt；这只限制逐字节重生成，不否定 R→Mplus 对图形
所表达样本流程和结构语义的来源。只读证据见
`reports/cfps_figure_provenance_20261004/cfps_figure31_source_boundary_v2.md`。

## 可复用规则

1. 先按 `target_file` 区分正文与 Appendix；`figure_links.json` 同时记录多个 DOCX，
   不能只按 `word/media/imageN.*` 全局取最后一条记录。
2. 先合并 PNG/SVG 逻辑对，再按 SVG 文本标签核验；Word 媒体 hash 不匹配可能只是
   尺寸、命名空间或压缩重写。
3. `SimpleSlope_`、`TwoWay_`、`ThreeWay_Facet_` 多数由 `paste0()` 动态生成，不能
   只搜索完整文件名；必须同时保存脚本行号、变量命名规则和实际既有文件。
4. producer 已存在时，图形追溯不触发 Mplus/R 重跑；只有输入指纹、producer 身份
   或图形标签无法恢复时，才进入科学边界审查。
