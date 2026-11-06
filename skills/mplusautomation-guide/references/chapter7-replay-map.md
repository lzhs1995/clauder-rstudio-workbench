# Chapter 7 replay map

该映射把第七章的研究问题、模型家族、代码入口、输出和验收边界连接起来。路径使用逻辑名称；具体 Windows 路径和哈希保存在项目级 replay manifest，不写入可共享 skill。

## 总体链条

```text
Stata data cleaning
  → panel/predata inputs
  → R mplusObject/mplusModeler or a verified [[init]] template
  → MplusAutomation model generation
  → licensed Mplus estimation
  → readModels()/savedata/CPROB
  → R second-stage logistic and plotting
  → Word/DOCX and PDF
  → NLM source-specific A5 review
```

## 家族映射

| 家族 | 主要目的 | 典型输入 | 典型输出 | 第七章用途 |
|---|---|---|---|---|
| LPA/LCA | 单期类别识别 | 实际为四连续+两分类指标及 DEFINE | fit indices、条件均值/概率、CPROB | 类别命名与类别比例 |
| LTA | 跨期类别转移 | 多波次 LPA 测量结构 | transition matrix、Step-3 savedata | 核心转移描述 |
| MS-LTA | mover/stayer 异质性 | G(2)、G#1/G#2 语法 | mover/stayer probability、流量图 | 动静模式描述 |
| R-side logistic | 机制和调节效应 | most-likely class 与转移状态 | 390 个二元模型、OR/CI、边际效应 | 直接效应和调节效应 |

核心 24 个单期模型及下列纵向模型的历史生成入口是作者 R 的
`mplusObject()` / `mplusModeler()`。`[[init]]` 是其他探索分支和新批量
任务可用的入口；复现须绑定实际生成区块与 INP，不能仅凭技能示例判定来源。

## 31 模型的最小复盘集合

2026-11-04 按现存归档建立下列复盘清单。它是指定范围的待运行/核验图谱，
不是 31 次新鲜引擎估计的完成证明。各模型的绝对路径、SHA、starts、seed、
原生成行号和运行回执保存在项目级计划，不能只按同名文件匹配。

| 顺序与阶段 | 数量 | 样本/原 DAT 尺寸 | 保留的合同 |
|---|---:|---|---|
| time1–4 各 1–6 类 | 24 | 3586×1276 | 各波 USEVARIABLES；4连续+2分类；原 DEFINE、MLR、starts 与 LRTSTARTS |
| 四波测量不变/自由 | 2 | 3586×1276 | 四个四类潜变量；约束差异；不变模型 OPTSEED=89970；自由模型原诊断 |
| 四波 ref.cat.4 Step-1 | 1 | 3586×1276 | 参考类别及 OPTSEED=89970；分类误差、CPROB 和保存数据生产者 |
| 四波 LTA Step-3 | 1 | 3586×286 | c1–c4 各四类；STARTS=0；参考类别与固定分类误差参数 |
| 四波 MS-LTA Step-3 | 1 | 3586×286 | G(2) c1–c4；有限 logit stayer 约束；STARTS=0 |
| 两期 q1604/q1629 对应 Step-3 候选 | 2 | 7008×284 | c1(4) c3(4)，MS 另有 G(2)；须与原运行 SHA 绑定 |

上表顺序只规定复盘先后，不能把四波 Step-3 当成两期模型的数据生产者。
两期和四波各有独立的 Step-1/分类误差/Step-3 血缘；归档输入可直接重放。
血缘闭合要求生产脚本、参数、行键、数值投影和 SHA 绑定可验证，已保存的
历史生产链可通过只读核验闭合。若声明本次端到端新鲜复现，则须核验本次
Step-1→本次分类误差与 Step-3；两种证据分别标记。
枚举 time1 六类、time2–4 四类的历史选择与终稿纵向统一四类分别保留。

## 数值与图表比较

每行比较至少保存 model_id、INP/DAT/归档 OUT/新 OUT SHA、指标、原打印值、
新打印值、精度或容差、类别映射、诊断和结论。尚无新 OUT 时填
`NOT_RUN`，不能用同一归档输出的两次解析填充新鲜复现比较。

- LL、BIC、AIC 按对应 OUT 实际打印小数位比较；整位不同不能因宽容差
  消失。对从打印 LL 派生的 aBIC 等表值，另记录公式、输入精度和舍入步骤。
- 类别比例按 `modelEstimated`、`posteriorProb`、`mostLikely` 分口径；
  先用条件均值/分类概率建立类别置换，再按同一口径比较。原始类别号相同
  不证明类别含义相同。
- 转移矩阵保留起止波次、行/列类别映射及条件集合；总体边际矩阵、给定
  G 的矩阵和 G 条件初始分布分别命名。打印到 d 位的 K 项行和可以用
  K×0.5×10^(-d) 加浮点余量作舍入边界；这不替代逐单元比较。
- 图表绑定原 OUT SHA、解析器版本、类别映射和长表 SHA；比例和与矩阵
  行和通过只说明内部一致。热图不能替代需另外验收的 alluvial 图，派生
  图也不自动证明原 DOCX 图的节点、颜色或流向已一致。
- 保留 SE/导数矩阵问题、极端 logit 固定和自动修复。正常结束文字或
  `readModels()` 可解析不等于科学推断全部可用；原缺陷的复现与修复分开。

## 影响因素路线选择

初稿比较了三条路线：

1. Mplus 中对潜在转移概率直接建模（VAM/三步法和交互项）；
2. 合并为少量五分类转移结果后做多元 logistic；
3. 按转移方向拆成多个二元 logistic。

最终采用路线 3，理由必须同时写出：样本稀疏、Mplus 频繁不收敛、VAM 交互项编码复杂、路线 2 过度折损转移方向信息。该选择并不等于硬分类没有误差；正文必须保留 Entropy 较高但分类误差和标准误风险仍存在的限制说明。

## 证据边界

- q1604：LTA Step-3 归档输入新鲜复现通过；
- q1629：MS-LTA Step-3 归档输入新鲜复现并保留自动修复诊断；
- R-side logistic：390/390 fresh convergence，23,904/23,904 coefficient keys，最大差约 `4.9738e-14`；
- q1604/q1629 当前 panel→Step-1→Step-3 lineage：仍是 `PARTIAL_LINEAGE_CONFIRMED_NOT_CLOSED`，原因包括旧/新列宽、SIBO、PIDN/FID 和 AGEC/SIOPC 数值投影。

2026-11-04 新增的本地验收只覆盖 31 个归档输出的 R 读取与重绘：31 条拟合
记录、520 条分类比例、288 个概率单元、18 个 PDF/PNG 图文件；31 项 LL/BIC/N
独立文本核对、142 组类别和、72 组概率行和通过。该批状态是
`PASS_ARCHIVED_READBACK_AND_REDRAW_ONLY`，新鲜 Mplus 估计数为 0，跨模型
类别语义对齐仍待完成。原 64 组 warning 与解析器归入 errors 的 9 组诊断
均保留；这不撤销原 q1604/q1629 回执，也不把历史新鲜复现算成本次运行。

## 代码入口

- `scripts/ch7_mixture_syntax.R`：`ch7_mixture_object()` 按显式规格生成 LPA/LCA、LTA、MS-LTA 及 Step-3 的 `mplusObject`。
- `scripts/ch7_mixture_tools.R`：`ch7_classify_inp()` 从 INP 判定家族；`ch7_enumeration_table()` 汇总类别枚举；
  `ch7_step3_binding()` 核 Step-1 存盘到 Step-3 输入的绑定。
- 合成合同：`scripts/test_ch7_mixture_family_20261105.R`、`scripts/test_ch7_mixture_tools_20261105.R`。

## 可复现目录合同

每批复盘目录必须有：

- `inputs_manifest.json`：输入路径、大小、SHA256；
- `spec_manifest.json`：模型 family、实际生成入口、连续/分类变量、DEFINE、波次、约束、参数和 seed；
- `run_receipt.json`：Mplus 状态、warning、输出解析；
- `derived_manifest.json`：R 读取、表格和图形；
- `manuscript_binding.csv`：表/图/正文位置；
- `acceptance.md`：通过、诊断或未闭合边界。

另保存逐模型比较表、类别映射和图表来源表；使用 CSV/JSON 等其他文件名也
可，但必须记录完整字段及索引。输入迁移字节一致、归档读取/重绘、新鲜
估计比较、完整生产链、论文采纳分别标状态，不能用一个 PASS 覆盖所有层。

## 未来扩展规则

更换研究数据或指标时，先依照
[换源与换变量合同](chapter7-source-variable-contract-20261104.md)
固定源数据、变量字典、波次、指标类型、派生规则、样本、类别命名和模型
规格；不要复制旧 `.out` 或直接复用旧 CPROB。任何 new model 都必须先
通过 synthetic smoke，再进入真实数据批次。该合同是生成前的审阅规范，
不是已实现任意映射自动编译器的声明。
