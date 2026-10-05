# CHARLS reuse-first 科学采用门

CHARLS 的 registry 中可能记录历史运行曾经产生的估计，但这不等于当前轮次提交了新的 Mplus，也不等于结果已经获得科学采用。报告时必须分别记录：

- `existing_paths`：既有 `.inp/.out`、解析结果和表格路径是否存在；
- `new_mplus_submissions_this_turn`：本轮是否真正调用 `runModels()` 或启动 Mplus；
- `formal_adoption` / `scientific_acceptance`：是否通过边界、MI、class label、estimand 和方法审查。

本项目当前的 reuse-first 状态是：两个 registry 的 90/90 引用路径存在，`new_mplus_submissions_this_turn=0`，formal adoption 和 scientific acceptance 均为 false。开放事项包括 1 个 timeout/incomplete、3 个自动修正或零标准误审查项、SD likelihood mismatch、剩余插补成员、class label/reference category 对齐、comparison/ranking 合同。

边界读回还记录了 72 个 `APPLIED_OR_ALREADY_HIGHER` 状态；它们只是可复用的技术候选。registry 中的历史估计计数（本项目为 24）不能计入当前轮次的新提交，也不能代替 MI pooling、estimand 和标签合同。

在这些合同关闭前：

1. 只读回读既有产物、记录哈希和边界证据；
2. 不把 registry 中的历史 `new_Mplus_estimates` 计入当前轮次的新提交；
3. 不把超时、自动修正、零标准误或未完成 MI 结果写入论文正式表格；
4. 不因 CFPS 尚未关闭而盲目并发启动 CHARLS；
5. 合同关闭后才在隔离 run root 中按资源门逐步提交 CHARLS Mplus。

这一区分是长耗时项目的进度监控核心：`90/90 paths inventoried` 表示资产盘点完成，不表示 CHARLS 已正式完成。
