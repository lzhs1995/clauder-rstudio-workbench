# Windows 外部 Mplus 进程分类

RStudio `Running on http://127.0.0.1:8787` 只证明 ClaudeR/RStudio 通道可用，不能证明目标 CFPS 或 CHARLS 队列正在估计。每次看到 `Mplus.exe`，先沿父进程链向上读取 `Mplus → cmd → Rterm → rsession → RStudio`，再读取工作目录和输入文件名。

## 分类规则

1. 用工作目录、`candidate.inp` 的绝对路径和任务注册表把进程归属到 PP-LGCM、CHARLS 或其他章节审计。只有目录和任务身份同时命中，才计入目标队列。
2. 外部章节审计即使由同一个 RStudio 会话启动，也保持 `EXTERNAL_AUDIT` 状态；不附着、不杀进程、不重提、不把它的完成数累加到 CFPS/CHARLS。
3. 终态必须同时检查 `.out` 的 `MODEL RESULTS`、`Beginning/Ending Time`、错误标记，以及 `parameters.csv`、`parsed.rds`、`results.dat` 和 `runModels.log` 的存在与哈希。没有这些证据只能报告运行中或未验收。
4. 逐模型保存隔离完成回执，记录 PID、父链、输入目录、终态和新提交数。RStudio 连接和 Mplus 进程扫描都必须是只读操作。

本项目的三个第四章模型示范了该边界：它们由 RStudio→Rterm→cmd→Mplus 启动并正常生成结果，但目录属于 `scientific_audit_20261002/.../missing9_run`，因此回执明确排除 CFPS/CHARLS 队列。该规则避免把外部审计的自动推进误报为目标论文模型已经完成。
