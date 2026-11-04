# Chapter 5 replay map

该映射把第五章的论文图表、模型家族、代码入口、输出和验收边界连接起来。路径使用逻辑名称；具体 Windows/Mac 路径、哈希与比对数值保存在项目级 replay manifest，不写入可共享 skill。

## 总体链条

```text
Stata data cleaning → locked CSV
  → R: centering, effect coding, sub-samples
  ├─ R glm + vcovCL(cluster, HC0)            → static moderation tables
  └─ R prepareMplusData + [[init]] templates
       → MplusAutomation createModels/runModels (filefilter subsets)
       → licensed Mplus (ML, BOOTSTRAP=1000, PLOT3 → .gh5)
       → readModels() + rhdf5 saved draws → BC / percentile intervals
       → R/Python tables and matplotlib figures → Word/DOCX
```

## 家族映射

| 家族 | 主要目的 | 典型输入 | 典型输出 | 第五章用途 |
|---|---|---|---|---|
| Stata 直接效应 | 资源→结果直接关联 | 锁定 CSV、do-file | `.ster`、RTF | 正文表5-6~5-9、附录表A5.4（不在本映射复现范围） |
| MOD 静态调节 | 资源 × 情境交互 | 锁定 CSV | `coeftest` 表、交互项汇总 | 附录表A5.6（22 张联合规格 + 10 张逐一规格） |
| MED 普通中介 | X→M→Y 间接效应 | 模板展开的 `.inp`/DAT | `.out`、`.gh5` | 图5-2~5-5、附录表A5.5 |
| MODMED 第二阶段 | 高低条件间接效应差 | 同上，M×W | `TNIE_DIF` 等差值参数 | 附录表A5.7 |
| MODMED 多组 | 两生命周期组间差 | `GROUPING` 模板 | `DIMM*`/`DINT*` | 附录表A5.8 |
| 归档样本条件中介 | 补充结果 | 另一版本样本的既有输出 | `TNIE_WL/WH/DIF` | 附录表A5.10 |

## 路线选择

二值中介与结果的间接效应用 Mplus 反事实分解（风险差尺度的 TNIE），连续结果用线性乘积；
CMAverse 不进入第五章（正文与附录均无该路线），属另一篇独立稿件。静态调节留在 R，
理由须同时写出：需要家庭聚类稳健协方差、需要逐方程不同的控制集合、模型数量大且无需 bootstrap。
联合规格（多个交互项同入一个方程）与逐一规格（每次一个交互项、控制集合不同）是两套模型，
不能互相替代；逐一规格对某一结果按结果剔除一组控制，这条规则须写进配置。

## 证据边界

- MOD 联合规格：R 重新拟合，1,710/1,710 格系数/SE/符号按 3 位一致；
- MOD 逐一规格：锁定脚本缺生成段，按历史输出重建；对历史交互项汇总 2,520/2,520 行，最大绝对差约 `4.8e-14`；对附表 810/810 格一致；
- Mplus 现用 1,922 个模型：`ARCHIVED_READBACK_ONLY`，`.out` SHA 1,922/1,922；附表普通中介 432、条件差值 1,728、生命周期差值 676 行全部一致，保存抽样重算区间容差 `1e-9`；
- 论文附录印刷格：A5.5 1,296/1,296、A5.6 7,848/7,848、A5.7 1,728/1,728、A5.7-9 140/140、A5.8 152/152、A5.10 60/60；负对照（错位、扰动）均能判出不等；
- 图5-1~5-5：原出图脚本重出，去掉随机 id 与日期后 5/5 字节一致；
- Mplus 新鲜估计数为 0：分层重估待计算窗口；完成 0 次 bootstrap 的 2 个历史模型保留原诊断，不修复。

## 可复现目录合同

每批复盘目录必须有：

- `inputs_manifest.json`：输入路径、大小、SHA256；
- `spec_manifest.json`：家族、模板 SHA、迭代器、控制集合、手填常量、分组路线、bootstrap 设置；
- `run_receipt.json`：Mplus 或 R 运行状态、warning、解析结果；
- `derived_manifest.json`：读回、重算区间、表格与图形；
- `manuscript_binding.csv`：表/图/单元格位置与参数键；
- `acceptance.md`：通过、诊断或未闭合边界。

逐格比较表须保存：论文位置、印刷字符串、复现值、印刷精度容差、参数键（模型、样本、参数名、`.gh5` 语句下标）、结论。

## 未来扩展规则

更换数据或变量时，先按 [第五章配置与验收合同](mediation-moderation-workflow.md) 固定角色、样本、中心化、效应编码、控制集合与手填常量，并通过合成合同 `scripts/test_ch5_mediation_moderation_20261105.R`；不要复制旧 `.out`，不要沿用旧样本的 W 取值点。该合同是生成前的审阅规范，不是已实现任意映射自动编译器的声明。
