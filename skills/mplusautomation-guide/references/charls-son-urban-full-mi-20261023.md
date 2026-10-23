# CHARLS son×urban：修复后的完整 20-MI 家族（2026-10-23）

本记录是一次真实的 Windows 原生 Mplus 复现经验。旧 son×urban 根虽然有 MI PASS，出处审计发现 20 份 DAT 实际复制了 education 家族；城乡乘积项只被追加到事后辅助表，未进入实际拟合矩阵。旧 GH15 输入还在当前 GH07 完成前生成，因而不能把旧 timeout 当作目标模型不可估计的证据。修复过程和旧结果保存在同一隔离项目中，旧文件没有覆盖或删除。

## 修复和准入

- 新 MI 根先把全部 25 个 urban×XZ 派生变量加入 mice 输入，再导出每份实际拟合 DAT；独立验证同时检查预测矩阵，而不是只检查辅助 CSV。
- C4 是城乡 known class，C3 是普通教育控制；`USEVARIABLES`、`KNOWNCLASS`、`ON` 和 mixed-community 诊断都按当前数据 schema 生成。
- 先运行 GH07 A/B，只有读取到当前终值并通过哈希比较后，才编译 GH15 A/B。adapter 只捕获普通异常，避免 `SystemExit` 成功返回被误记为失败。
- pilot 的 5 次调用全部 `USABLE`，随后 MI01 A/B 字节级复用；MI02–20 A 新开 19 次调用。每次 240 秒上限，单 Mplus 引擎，四个内部处理器；任何 A 成员不可采用就停止，不用部分池化替代完整家族。

## 完整执行结果

隔离根：`C:/Users/LZHS/pp_lgcm_review/charls_latent_h42_son_urban_full_20261023`。原生 RStudio async job `c0ae878a` 共记录 21 个成员（20 A + MI01 B）；A 全部 `USABLE`，B 起点敏感性通过。Mplus 新调用为 19 次，MI01 A/B 是已核验的 pilot 输出，不重复估计。

独立读取每份 `model.out`、`estimates.dat`、`tech3.dat`，重新构造参数变换、协方差和 Rubin 合并：2,814 个参数、21 个研究对比，N=2,263、社区=433，状态 `PASS_FULL_TRANSFORM_AND_RUBIN_SON_URBAN`。

主对比 `SY:SXIZ`（城乡组1 − 组0）为 0.17879163145，95% CI [−0.10073309697, 0.45831635987]，p=0.20997057250；规划的 12 项 Bonferroni 值为 1。该结果不得按显著性筛选或改写为假设支持。

## 可复用边界

这是一条条件工作 MI 路线，独立合并通过不等于证明 MAR 或精确潜变量相容性；C4 组差是该家族的估计对象。公开包只含输出、参数、协方差和核验记录，不含 `data.dat`、MI/RDS/MIDS、辅助输入或个人记录。公开验证器只能复核包完整性和保存的独立验收状态，含私有数据的全量重算仍需本机隔离环境。

它完成了 CHARLS 一个 H4.2 单元，不能替代其余资源/指标家族。**四项调节完整推断、完整 H4 仍未完成。**
