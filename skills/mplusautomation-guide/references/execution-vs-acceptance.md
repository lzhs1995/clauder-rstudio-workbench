# 执行完成与论文验收的分层

长耗时 Mplus 项目必须把至少三个状态分开记录：

1. **估计生产层**：R script 已完成、`.out` 已生成、任务没有 pending/running，并且输出有终止与哈希证据；
2. **历史复现层**：脚本、输入、输出和论文显示值已经逐格回绑，历史结果可被复现或明确标记为 limitation/deferred；
3. **科学采用/发布层**：数据版本、负方差、LRT、MI pooling、标签语义、图表和最终 PDF 已满足项目合同。

`CFPS_CLOSURE_GATE.ready=false` 只能表示第 3 层尚未关闭，不能倒推第 1 层没有运行。状态文件应同时保存 `estimation_production_complete`、`historical_reproduction_complete`、`manuscript_scientific_acceptance` 和 `new_mplus_submissions`。

本项目的典型证据是：11 个直接规格各有 10/10 插补估计，四个 producer 已 `script_finished`，但 5,117 条比较仍需差异/失败/依赖/未准备处置。因此不得因为论文 gate 未关闭而重复提交已经有哈希和终止证据的 Mplus；应继续做只读逐格验收，并把负方差、LRT 或数据版本问题保留为科学审查状态。

进度报告必须明确写出“估计生产完成、论文验收开放”，而不是笼统地写“CFPS 未完成”。
