# Windows 性能准入与 Mplus 调度

本机实测表明，Mplus 变慢不能仅凭“可用内存低”或 `Pages Input/sec` 下结论。Windows profile 至少要同时保存：物理可用内存、commit 余量、磁盘剩余空间与延迟、CPU 三次样本、`Pages Output/sec`、Mplus 的父链和输入身份。`Pages Input/sec` 可能包含 mapped-file 读取；只有它与 page output、磁盘延迟、CPU 饱和和 Mplus 进度共同出现时，才进入换页诊断。

## 执行顺序

1. 先复用已正常结束的 `.out`，不要因速度问题重复估计。
2. 用 `windows_host_profile.py` 做三次原生 Windows 采样。WSL 的 `psutil.virtual_memory()` 不能代替 Windows 物理内存准入。
3. 用父 PID、创建时间、命令行和工作目录核对所有 Mplus。外部 RStudio/ Mplus 任务必须保留，不能按名称误杀。
4. 先运行一个已有成功模型的隔离代表性试跑；记录 R worker、Mplus 子树峰值 private/RSS、CPU 秒、磁盘延迟、模型阶段和输出哈希。
5. 只有单槽位的峰值和稳定余量都通过后，才增加第二个 worker。并行度按测得的增量预算决定，不按 R 脚本数量或“Windows 支持多开”决定。

## 当前 Windows 经验

- 三个长期 RStudio 会话和 `vmmemWSL` 会占用提交空间；一次 `gc()`、清 tmux scrollback 或 uv cache 只能作为低风险辅助，不能假称释放了可用物理内存。
- `uv cache prune`、一次性 WSL cache 清理和已核实的 WSL 终端降优先级可以记录，但不应在每个模型前重复执行。
- Windows Job Object、硬超时和异步轮询必须只约束本次拥有的 R/Mplus 子树；取消时按 PID+创建时间和父链确认，不能终止未知 worker。
- `MplusAutomation::runModels(target=<exact input>, recursive=FALSE, replaceOutfile="never", killOnFail=FALSE, Mplus_command=<licensed Mplus 9>)` 是估计入口；输入、数据和输出均放在隔离目录，完成后单次 `readModels()` 并保存 RDS/哈希。
- ClaudeR 的 `execute_r_async` 解决 RStudio 前台阻塞和监控轮询问题，不会降低 Mplus 数值估计本身的时间；异步任务仍需 durable progress、原始 job id 和完成合同。

## 失败处理

资源不足时记录 `HOLD` 及具体原因（外部 Mplus、物理余量、commit、CPU、磁盘或 stale profile），不要把 HOLD 写成 Mplus 失败。模型超时、非正定 Fisher、无 VCOV 或输出不完整必须进入 deferred/limitation 队列，不能为追求显著性放宽规格或增加无合同并发。
