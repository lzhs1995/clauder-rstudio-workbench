# Deferred 输出的只读分层

`deferred` 不等于“没有 `.out`”，也不等于“可以直接进入论文”。先对已有输出做只读分层：

- 若有 `MODEL RESULTS`、Beginning/Ending Time、标准误，且没有 incomplete replication、非正常终止、非正定 Fisher、零标准误或 SAVEDATA filename error，标记为 `EXISTING_OUTPUT_READBACK_COMPLETE_WARNING_REVIEW_OPEN`；
- 若存在 MI 不完整、输入指令错误、零标准误或非正常终止，保持 `RETAIN_DEFERRED`；
- 任何分层都不修改队列状态、不重跑 Mplus、不自动选择论文数字。

本项目的 669 个 deferred queue rows 中，31 个已有输出覆盖 471 行满足第一类条件；20 个输出覆盖 198 行继续延期。第一类仍需逐格连接论文单元格，决定历史采用、敏感性或限制；它只是技术读回完成，不是科学接受。

这种分层能避免把“输出存在但有 warning”与“真正未完成/不收敛”混为一谈，也能避免因为论文 gate 未关闭而重复估计已有结果。
