# Mplus版本升级与当前任务效率
先读官方版本日志，将每项优化映射到当前INP的估计器、TYPE、算法和输出需求；新版本不自动意味着当前模型加速。检查本地MSI ProductVersion与引擎身份，目录名不能代替版本证据。
分开验证命令行启动、版本标题解析、真实输出表/GH5解析、数值正确性和耗时。MplusAutomation以显式Mplus_command调用引擎，并不要求每次Mplus小版本发布就升级R包；但新格式可破坏解析。
2026-10-02第四章实测：MplusAutomation1.2能读取合成的9、9.1、9.1.1版本标题及原参数表；这是标题兼容性测试，不能报告为新版引擎验收。官网9.1主要针对EFA/ESEM/DSEM，9.1.1修复特定DSEM多处理器错误；本批ML＋1000次bootstrap未获已证实提速依据，因此继续固定9。
升级候选应优先已修复的9.1.1，不将9.1作为默认目的版本。用隔离路径、相同INP/DAT与设置、交替重复的计时验证CPU/墙钟、RAM/缺页，并验证N、参数、SE/CI、拟合、诊断、GH5及下游输出。不能把不同模型/机器压力时段当版本基准。
批次中途切换仅在预期剩余节省超过验证迁移成本且正确性通过时考虑；记录每项引擎hash，避免悄悄混用版本。公开日志没有提速声明不证明没有提速，只表示收益尚未建立。
来源：https://www.statmodel.com/verhistory.shtml
本次完整证据：mplusautomation_reproduction_20260915/recovery_20260930_auto/reports/MPLUS_UPGRADE_ASSESSMENT_20261002.md。

