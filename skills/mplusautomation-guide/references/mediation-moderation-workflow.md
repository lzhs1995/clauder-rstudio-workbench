# 第五章中介、静态调节与有调节中介：配置与验收合同

本文是第五章三个家族（MED、MOD、MODMED）的配置字段与验收层次。路径用逻辑名称；
具体路径、哈希与比对数值保存在项目级证据目录，不写入可共享 skill。
通用方法不在此重写，按需链接：[路径分类与 a·b(W)](apim-paths.md)、
[效应提取与检验族](effect-extraction-and-testing-families.md)、
[GH5 精度与 BC 区间](source-data-and-bootstrap-precision.md)、
[整簇与逐行重抽样](finite-cluster-and-bootstrap-contracts.md)、
[出图前最小合同](display-producer-contracts.md)、
[调节分析禁止项](cfps-moderation-readback.md)、[合成验收](synthetic-acceptance.md)。

## 1. 先认清模型族

第五章是**单层**观测变量模型：一行一个夫妻—年度记录，交互项在 `DEFINE` 里由观测变量
相乘得到，不是 `XWITH` 潜变量交互，也不是 APIM 双人成对结构。因此
`apim_v2_model()` 的 2×2 成员循环不适用；生成走 MplusAutomation `[[init]]` 模板路线，
静态调节在 R 中拟合。

| 家族 | 实现 | 推断 | 第五章用途 |
|---|---|---|---|
| MOD 静态调节 | R `glm`（线性或 logit）+ `sandwich::vcovCL(cluster=家庭, type="HC0")` + `lmtest::coeftest` | 聚类稳健 Wald；p<0.1 起标记 | 交互项系数表 |
| MED 普通中介（连续） | Mplus `MODEL INDIRECT ... IND`，ML，`BOOTSTRAP=1000` | `CINTERVAL(BCBOOTSTRAP)`；保存抽样重算 BC | 线性乘积间接效应 |
| MED 普通中介（二值 M、Y） | Mplus 反事实分解：`MODEL CONSTRAINT` 由阈值与斜率写 TNIE/PNDE/TNDE/PNIE/TE | 同上 | 风险差尺度的 TNIE |
| MODMED 第二阶段 | M×W 进结果方程（不含 X×M×W）；条件间接效应与 IMM 写在 `MODEL CONSTRAINT` | 连续：BC；二值：保存抽样百分位 | 高低条件差值判据 |
| MODMED 多组 | `GROUPING` 两组，组内标签；`dimm`/`dint` = 两组 IMM / 交互系数之差 | BC | 生命周期组间差值 |

既有 Mplus 模型未声明 `CLUSTER`：其 bootstrap 是逐行重抽样，不能称为夫妻聚类稳健区间。
R 侧静态调节用聚类稳健协方差。两侧推断口径不同，表注必须分开写。

模板骨架（合成变量名，`NAMES` 与 `scripts/ch5_synthetic_data.R` 的列序一致）：

| 模板 | 结构 | 分组 |
|---|---|---|
| `assets/ch5/linear_mediation_template.txt` | 连续 X→M→Y，`IND` + `ind = a1*b1` | 全样本与两组各自 `USEOBSERVATIONS` |
| `assets/ch5/counterfactual_mediation_template.txt` | 二值 M、Y 的反事实分解 | 两组各自 `USEOBSERVATIONS` |
| `assets/ch5/moderated_mediation_mg_template.txt` | 连续 W 调节 b 路径，mean±SD 取值点 | `GROUPING` 多组，`dimm`/`dint` |
| `assets/ch5/moderated_mediation_cat_template.txt` | 三分类 W 效应编码（1,0）/（0,1）/（−1,−1），按子样本量加权平均 | 每个样本文件各自的子样本量常量 |

静态调节的 R 路线在 `scripts/ch5_moderation_route.R`：`ch5_moderation_spec()` 校验配置（未知键、缺列、
角色重叠、连续 W 必须给显式且有限的取值点、三分类 W 必须给完整类别顺序；输入列名不得与内部 modw_effect1 等效应编码列冲突），`ch5_fit_moderation_spec()` 拟合，
`ch5_simple_slopes(m, level = 0.95)` 用含协方差项的 delta 法算简单斜率（logit 另给 OR）；`level` 必须显式给出，没有默认值，输出表带 `level` 列。`ch5_plot_simple_slopes()` 出图，y 轴标签写明置信水平（如 `95% CI`），并返回绘制数据。
合成合同核对：连续 W 的简单斜率等于把 W 平移到取值点后重拟合的主效应，三分类 W 的等于以该类为参照的处理编码重拟合，
SE 逐位一致；去掉协方差项的 SE 会被判错。

## 2. 显式配置字段

下列是项目配置应具备的字段要求，不是可直接传给现有函数的 API。

| 配置部分 | 必填内容 | 生成前验收 |
|---|---|---|
| source | 数据文件、SHA256、编码、缺失码、行粒度、聚类键 | 文件身份；聚类键无缺失 |
| samples | 全样本与两个子样本的筛选规则；多组用 `GROUPING` 还是 `USEOBSERVATIONS` | 两种分组路线不混用；子样本行数与筛选规则一致 |
| roles | X、M、Y、W 的源列→模型名；连续或二值；资源基准方向（谁的资源、谁的结果） | 方向逐项写明，不靠文件名后缀推断 |
| centering | 连续变量中心化基准；份额变量的平移常数；中心化在拆样本前还是后 | 用当前样本重算并记录 |
| moderators | 连续 W 的取值点；三分类 W 的效应编码类别顺序与省略类 | 效应编码行向量逐类核对；取值点不是自动 ±SD 时写明来源 |
| controls | 每个方程的控制变量集合；按结果剔除的规则（例：某结果不进某组控制） | 剔除规则显式列出；联合规格与逐一规格的控制集合分别登记 |
| template | 模板文件 SHA、`[[init]]` 迭代器与范围、`name*`/`var*` 两套列表、`filename`、`outputDirectory` | 展开数 = 迭代器乘积；无未替换标签；每行 ≤ 90 字节 |
| constants | `MODEL CONSTRAINT` 中手填的 W 均值/标准差、子样本量等 | 由当前样本重算；与旧值并列记录 |
| run | `runModels` 的 `filefilter`、`PROCESSORS`、估计器、bootstrap 次数、是否有 SEED | 只跑登记的子集；`PROCESSORS` 视为规格，不为提速改动 |
| output | 隔离输出根、预期 `.out`/`.gh5` 清单、表图口径 | 不覆盖历史输出（`replaceOutfile` 不用 `"always"` 指向原目录） |

## 3. 模板与手填常量的陷阱

1. `name*` 进文件名，`var*` 进模型语句，同一下标同时索引两者。`readModels()` 按文件名
   拼路径读取时依赖 `name*`，改变量时两套列表都要改。
2. 同名模板在不同结果目录里字节可以不同：`[[init]]` 与常量段按家族、样本被手工改过。
   复现以每个结果目录内实际存在的模板为准，不按文件名合并。
3. 模板文件名里的 `1n`/`2n` 不可靠地表示调节变量类型；判断看 `namewv#wv` 的内容与有无
   `varwv1`/`varwv3` 两列。反事实模板没有 plot `type` 迭代器。
4. `MODEL CONSTRAINT` 里的 W 取值点、三分类子样本量是从 R 的描述统计手抄进模板的。
   换源或换样本时必须重算；`ch5_fill_template()` 会拒绝缺任何一个常量标签的填充，
   合成测试另核填入值等于当前样本的均值/标准差。
5. `outputDirectory` 与 R 侧工作目录必须一致；只改一侧会把 `.inp` 写到不存在的位置。
   `prepareMplusData()` 决定 DAT 列序，模板 `NAMES` 必须逐列一致。
6. Mplus 阈值在概率式中带负号：`P(Y=1)=1/(1+EXP(τ−βx))`。反事实分解照此写；
   `ch5_counterfactual_effects()` 与模板 `MODEL CONSTRAINT` 逐式求值一致，并对大样本模拟核对。

## 4. 区间与判据

- 普通中介与连续条件中介：用 `.gh5` 保存抽样按 BC 定义重算
  （`z0 = Φ⁻¹(#{θ* < θ̂}/B)`，分位 `Φ(2z0 + z_p)`，R `quantile(type=7)`）。抽样全在点估计
  同侧时 z0 无界，区间记 NA，不补值。
- 二值条件中介差值：保存抽样百分位区间。
- 差值判据三档：95% 区间排除零 / 仅 90% 排除零 / 90% 含零（论文显示为 ✓ ◐ ✗）。
  判据按未舍入区间判，不按印刷值判。
- 静态调节：`+`（附录显示为 †）p<0.1，`*`/`**`/`***` 为 0.05/0.01/0.001。
- 抽样数要逐模型读回：请求 1000 不等于完成 1000。完成数少于请求数记为降级；完成 0 次
  且报 SE 不可算的模型原样记录，不改成成功结果。
- `.out` 打印值为 3 位，论文附录的中介点估计与区间是保存抽样复核值（5 位，更小的非零数
  用科学计数）。比对按各自印刷精度的末位半单位判定，并以同一规则重新格式化核字符串；
  `−0.000` 这类负零格回到全精度核符号。

## 5. 换源 / 换变量步骤

1. 固定新源快照、角色映射、样本规则、中心化与效应编码，写配置文件并保存 SHA。
2. 按配置重算全部手填常量；生成一个最小代表 `.inp`，核 `NAMES`、`USEVARIABLES`、
   `CATEGORICAL`、`DEFINE`、分组语句与 `MODEL CONSTRAINT`。
3. 跑合成合同（`scripts/test_ch5_mediation_moderation_20261105.R`、`test_ch5_templates_extended_20261105.R`、`test_ch5_moderation_route_20261105.R`）；新规格先过合成，再在获准窗口用 `test_ch5_native_synthetic_20261105.R --run` 过原生合成，再进真实数据。
4. 在获准的计算窗口提交一次，隔离输出根；保留进程、版本、起止时间与输入输出 SHA。
5. `readModels()` 读回，区分正常终止、估计诊断与解析成功；由 `.gh5` 重算区间与判据。
6. 重出表图并绑定来源（模型、参数名、`.gh5` 语句下标、SHA）。

不要复制旧 `.out` 当新结果，不要因削弱显著性删控制变量，不要事后改 W 取值点。

## 6. 验收层次

- `TRANSFER_VERIFIED`：明确文件集合逐件字节一致。
- `ARCHIVED_READBACK_ONLY`：读回既有 `.out`/`.gh5` 并重算区间、重出表图，没有新引擎估计。
- `R_REESTIMATED`：R 侧模型在新环境重新拟合并逐格比对。
- `FRESH_REPLAY_COMPARED`：Mplus 新估计回执与对应数值比对完成；bootstrap 无 SEED 时只比点估计
  与打印精度区间的容差带，另列诊断。
- `MANUSCRIPT_ACCEPTED`：经项目明确采纳。

各层分别记录，不线性自动升级。第五章当前各层状态见 [第五章复现映射](chapter5-replay-map.md)。
本文件只描述已经从脚本、模板、输出和审计证据确认的逻辑；`scientific_closed=false`，
不把技术复现状态写成论文结论。
