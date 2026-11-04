# LPA/LCA workflow

本文档把 LCA（分类指标）和 LPA（连续指标）视为同一套潜在类别识别框架的两种测量版本。它说明如何从类别数枚举走到类别命名、类别概率回归和图表验收。

## 1. 识别目标

- LCA 用分类指标估计各类别的条件反应概率。
- LPA 用连续指标估计各类别的条件均值/方差；指标需要检查尺度、极端值和近似正态性。
- 两者的共同输出是潜类别、后验概率、most-likely class、类别比例和模型拟合指标。
- 不要把 LPA 的类别编号当作有序等级；类别编号只是软件内部标签，最终解释必须依赖条件均值/概率和理论含义。

第七章的历史目录虽命名为 LPA，实际 24 个单期模型使用混合指标：
`closz`、`esupz`、`isupz`、`opp5z` 四个连续指标，以及 `edwc`、`idwc`
两个 `CATEGORICAL` 指标，各带对应波次后缀。原 `DEFINE` 先将后二者置 0，
再分别按 `edw < esup*1`、`idw < isup*1` 赋值 1。复现时以实际
`USEVARIABLES`、`CATEGORICAL`、`DEFINE` 和数据字典为准，不能把该目录当成
六个全连续指标模型。更换变量须同时核原尺度、标准化、阈值方向和缺失处理；
详见[换源与换变量合同](chapter7-source-variable-contract-20261104.md)。

## 2. 类别数枚举

逐步估计 1 至 K 个类别，并记录：

1. loglikelihood、AIC、BIC、aBIC；
2. Entropy 和平均后验概率；
3. LMR/VLMR、BLRT（如果模型和软件支持）；
4. 最小类别比例、异常标准误、局部最大值和收敛状态；
5. 类别形状能否被清楚命名，以及新增类别是否只是拆分已有类别。

仅凭某一个信息准则选 K 不够。第七章实际采用“统计拟合 + 分类质量 + 类别规模 + 理论可解释性”的联合判据。历史 acceptance 记录保留了 time1 的六类选择、time2–time4 的四类选择；论文最终为跨期 LTA 的可比性采用四类测量结构。这是“历史单期选择”和“最终纵向规格”两个不同决策，不能把最终四类改写成“四个时间点只估计了四类”，也不能用枚举 1–6 的范围掩盖该分歧。

## 3. MplusAutomation 结构

先识别实际生成入口。第七章本轮核查的 24 个单期模型与核心纵向模型来自
作者 R 脚本中的 `mplusObject()` / `mplusModeler()`；`[[init]]` 是可用的
另一种生成方式，不能据此改写历史来源。保留原 R 区块、生成参数和实际
`.inp` 的对应关系；旧大脚本中的安装、删除、清空和写回动作不能整体执行。

新批量模板可用 `[[init]]`，再由 `createModels(templatefile)` 展开。此前
已核验的 MplusAutomation 1.2 本机 `formals(createModels)` 只有一个参数
`templatefile`；它读取模板文件、解析一个且仅一个 `[[init]]`/`[[/init]]`
区段，并把生成的 `.inp` 写到 `outputDirectory`。`createModels()` 返回
`NULL`，所以必须用文件清单和内容检查来验收生成结果。`replaceOutfile` 是
`runModels()` 的参数，不是 `createModels()` 的参数。

下面是可独立运行的最小模板（只生成输入文件，不调用 Mplus）：

```text
[[init]]
iterators = classes;
classes = 1:2;
filename = "c[[classes]].inp";
outputDirectory = "C:/path/to/isolated/generated";
[[/init]]
TITLE: minimal mixture class [[classes]];
DATA: FILE IS "C:/path/to/isolated/audit.dat";
VARIABLE:
  NAMES ARE x1 x2;
  USEVARIABLES ARE x1 x2;
  CLASSES = c([[classes]]);
ANALYSIS:
  TYPE = MIXTURE;
  STARTS = 20 5;
OUTPUT: TECH1 TECH8;
```

对应的 R 调用契约是：

```r
library(MplusAutomation)

template_file <- "C:/path/to/isolated/template.inp"
generated_dir <- "C:/path/to/isolated/generated"
dir.create(generated_dir, recursive = TRUE, showWarnings = FALSE)
stopifnot(file.exists(template_file), dir.exists(generated_dir))

# 只展开模板；返回值为 NULL，生成物在 outputDirectory。
createModels(template_file)
generated <- sort(list.files(generated_dir, pattern = "\\.inp$",
                             full.names = TRUE))
stopifnot(identical(length(generated), 2L))
stopifnot(all(file.exists(generated)))

# 只有经过人工/脚本验收、资源准入和 Mplus executable 检查后才估计。
# runModels(target = generated_dir, recursive = FALSE,
#           replaceOutfile = "never",
#           logFile = file.path(generated_dir, "Mplus Run Models.log"))

# 估计返回且输出存在后再解析；readModels() 成功解析不等于收敛或方法验收。
# fit <- readModels(generated_dir, recursive = FALSE, what = "all", quiet = TRUE)
```

调用前固定记录模板哈希、`[[init]]` 迭代值、数据哈希、输出目录和预期文件
清单。`runModels()` 的 `replaceOutfile = "never"` 只是一项防覆盖选择，不能
替代隔离目录、进程身份和估计 receipt。批量运行前必须为每个规格保存：模板
哈希、替换参数、输入数据哈希、Mplus 版本和输出 `.out` 哈希。`readModels()`
成功解析不等于估计有效；必须同时检查 warning、收敛、TECH 输出和 savedata
行数。此处的 `createModels()` 形参和返回行为已用本机 R 4.5.1、
MplusAutomation 1.2 的 `formals()`/实际展开测试核对，并与官方
MplusAutomation vignette 的 `[[init]]`、`filename`、`outputDirectory` 模板
契约交叉核对；官方接口说明见
<https://cran.r-project.org/web/packages/MplusAutomation/vignettes/vignette.html>。

## 4. 类别命名和二次分析

1. 从每期最优模型读取条件均值/概率；
2. 对齐不同模型中的类别编号（使用语义排序或显式映射）；
3. 用稳定的理论标签命名类别；
4. 读取 CPROB、posterior probability 和 most-likely class；
5. 类别概率回归和边际效应图必须绑定到同一个参考类别、同一套映射和同一个 `.out`。

第七章的 LPA 主要用于描述类别及其概率变化。后续转移机制的主要估计来自 LTA/MS-LTA 和 R-side logistic，而不是把单期 LPA 结果误当作转移结果。

`readModels()` 的 `class_counts` 中，`modelEstimated`、`posteriorProb`
与 `mostLikely` 是不同口径。导出长表时保留口径、潜变量、类别、计数/比例、
原 `.out` SHA256；不能把三组相加，也不能用一组替代另一组。先在同一
口径内检查比例和，再做显式类别映射。仅以类别数字对齐或仅比较 BIC 无法
证明跨运行类别含义一致。

归档表格还可能含派生显示值：第七章历史 aBIC 表存在从已打印舍入的 LL
重新计算的路径。应分别核 Mplus 原输出值、R 派生公式和最终显示精度，
不能把显示差异直接归因估计错误。比较合同见
[第七章复现映射](chapter7-replay-map.md)。

## 5. 验收清单

- [ ] 每个 K 的 `.inp`、`.out`、savedata 和 receipt 可追溯；
- [ ] 连续/分类指标和 `DEFINE` 与原规格一致，生成入口有证据；
- [ ] 类别编号已完成跨期语义对齐；
- [ ] 每个类别都有条件均值/概率和样本比例；
- [ ] 类别比例口径单独保存，原值、派生值和显示值分别验收；
- [ ] Entropy、后验概率和最小类别规模符合预设门槛；
- [ ] 明确说明 Entropy 是后验分类不确定性的摘要，不是逐人分类准确率，也不会自动校正 most-likely class 硬分类回归的测量误差；
- [ ] 图、表和正文引用同一类别映射；
- [ ] 任何硬分类回归都明确记录分类误差局限。

第七章归档中，部分六类模型和自由测量模型已有标准误/一阶导数矩阵诊断；
另有极端 logit 被固定的记录。`readModels()` 可能把这些信息放在 `errors`
字段，即使原输出含正常结束文字。复盘应保留原文字、位置与输出 SHA，不为
获得 clean pass 而改 starts、约束或样本。R 解析成功、新鲜引擎运行成功和
科学推断可用性分别报告。

## 参考来源状态

第七章初稿引用了 `Lubke2007c`、`Masyn2013`、`QiuHaoZheng2023`、`WenZhongLin2023` 和 Mplus 用户手册。Zotero key 已从 DOCX XML 核验；附件全文是否读取必须以 source audit manifest 为准，不能由 citation key 推断。
