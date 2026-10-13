# CFPS MI v3 修复前置合同（Windows）

MI v3 当前只能读回，不能物化下游 producer/consumer。新估计必须放在独立本地目录，不能写回 `interge_rela`、OneDrive 或原始 R script 目录。

## 准入条件

- FreePhys 达到项目资源门槛，且没有未分类的外部 Mplus 争用；初始 worker 采用单槽位。
- 固定 10 个 MI 成员的顺序、PID/样本/聚类和变量列顺序；为每个成员保存输入 DAT/INP 哈希。
- 明确 `pinc12`（1–5）、`pinc212`（0–18.864 万元）和 `finc12`（0.0005–112 万元）的尺度与缺失/零点定义。
- 为非负收入变量使用有依据的有界/尺度相容插补规格；禁止截零、绝对值转换、事后重编码或挑选单个成员。
- 在运行前冻结增长形状、中心化、控制变量、聚类、估计器、积分/迭代和终止合同；不得根据试跑 p 值改规格。

## 终止与验收

每个 MI 成员必须有正常终止标记、完整参数/SE、最终 TECH8/链诊断和收入派生一致性；任何非正定 Fisher、负方差、SE/VCOV 缺失、超时或不完整成员都会使 MI v3 保持 hold。只有 10/10 成员通过后，才允许按依赖顺序重新物化 CFPS producer，再核对 downstream consumer。

验收报告至少保存：source/input/DAT/OUT SHA-256、成员映射表、范围违规计数、PSR/最终停止规则、MplusAutomation `readModels()` 回读、失败/超时清单和 `new_mplus` 计数。结果目录必须与原始目录隔离，并能从单一 manifest 重放。

当前证据：`reports/cfps_mi_v3_hold_20261004/cfps_mi_v3_hold_contract_v1.{md,json}`、`reports/cfps_mi_v3_hold_20261004/cfps_income_scale_readback_v1.md`。在这些合同关闭前，所有 51 个 MI producer 与 384 个 rank/score consumer 的提交开关保持关闭。

源码合同也已独立复核：`absolutive.R:7086-7108` 和
`absolutive.R:7236-7258` 的 `VALUES` 行明确约束 `cdar12`、`pinc12`、
`sat12`、`adl12`，但没有为 `finc12` 或 `pinc212` 写支持范围。复核入口为
`work/cfps_mi_v3_source_contract_audit_20261004.py`，回执为
`reports/cfps_mi_v3_hold_20261004/cfps_mi_v3_source_contract_audit_v1.{md,json}`。
这解释了为什么负插补值必须进入插补尺度/支持范围修复，而不能用截零或取绝对值代替。
候选修复路径（原始尺度有界、变换/反变换、零值两部分）及各自放行条件见
`reports/cfps_mi_v3_hold_20261004/cfps_mi_v3_repair_options_v1.md`；在方法裁决和
资源门同时满足前，不物化任何下游模型。
