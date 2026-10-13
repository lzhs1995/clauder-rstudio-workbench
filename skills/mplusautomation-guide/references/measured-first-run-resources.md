# 从固定内存门槛到真实模型测量

2026-10-02，PP-LGCM本机首次修正MI通过受监控首跑完成：Mplus9耗时36秒，采样峰值RSS约0.396GiB/private约0.648GiB。随后八个5波CESD单过程模型串行完成。不能将这些数值泛化为所有MI、bootstrap、LMS或混合模型的需求，也不能声称新版提速。

- 先区分“进程未启动”与“估计慢”。原固定3GiB门造成未启动；经测试/版本化发布，试运行要求2.25GiB Available、2.5GiB commit余量、3样本平均CPU<90%、最多两个外部Mplus和新鲜监督心跳。只对该试运行与限定八个模型生效，不是通用阈值。
- 保留至少1GiB系统余量，连续3次不足才进行本任务保护性处理；核实PID创建时间、研究父进程及精确输入。未知峰值不能用任意0.7GiB私有内存上限杀死有效模型。未来根据实际峰值及R工作进程总开销校准预算。
- 把arm→fresh admission→native async提交放在紧邻的顺序步骤，避免耗时分析消耗180秒监控有效期。一次旧监控过期导致提交前拒绝，确认真实终态后归档再提；绝不因观测超时盲目重提。
- 每个原生job提交后登记真实ID，轮询原ID，确认终态后归档。控制器可串行驱动多项原生工具，保留各项ID及输入/输出哈希，不能伪称同时多核运行。
- MplusAutomation1.3在Mplus9的MI输出中，对SUMMARY与Specifications for Data Imputation重复的dependent/independent计数会捕获异常并返回空summaries，readModels未抛出顶层错误不等于解析完整。检查必要字段。
- 本次局部解析适配只允许两条数值/文本相同、仅空白布局不同的计数行，折叠重复后调用原extractValue；不同数值仍拒绝。保持原输出、原模型RDS和包namespace不变；保存新的修复RDS、摘要CSV与适配收据。既有引擎也有解析问题，不能把所有问题归因于升级。
- 十份保存数据逐PID/列序/原观测/缺失一致性通过仍不足以科学放行。新MI出现14/40个人负收入、184/900家庭负收入和1/40派生不一致，已保留科学门；最后打印PSR不是完整的链诊断。八增长模型中四项PSI非正定，全部运行结束不是全部验收。

真实证据：<WINDOWS_USERPROFILE>/pp_lgcm_runs/20260908_parallel/recovery/20261001_pp_lgcm_reconciliation/10_resume_verified_20261001/scientific_followup/measurement_audit/first_corrected_estimations_checkpoint.json 。代码及备份位于work/pp_lgcm_reconciliation_20261001。

## 2026-10-05 TECH3-only calibration (one CFPS base model)

The isolated `type1::edu` base model used the historical successful input plus a
TECH3 output request. It ran through the native ClaudeR/RStudio async chain and
MplusAutomation 1.3 in about 619 seconds. The observed Mplus private-memory
sample peak was about 204 MiB and the process used about one CPU core. The
staged output terminated normally and its 112 unstandardized parameter rows
matched the historical output exactly (maximum estimate and SE differences
zero). These numbers are a local calibration for this model only; they do not
authorize MI, LMS, Bayes, bootstrap, or concurrent workers.

The first wrapper error also supplies a reusable contract: `runModels()` takes
the exact `.inp` target, while `readModels()` must receive the resulting `.out`
path. A successful Mplus process followed by a wrong readback target is an
integration failure, not a model failure, and must be recovered with a separate
readback job while retaining the original error in the receipt.
