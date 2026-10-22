# CHARLS 因子得分近似路线：边界与恢复

本记录来自 2026-10-21 的隔离试验。它记录工程边界和失败处置，不是完整 H4 结果。

## 估计对象

潜在 SX XWITH IZ 收入路线在三次有界校准中没有形成可用估计。为避免原样重跑失败规格，可另立隔离目录，复用已验证收入父模型并输出增长因子得分，供未来第二阶段观测交互模型使用。

这条路线只能标为两阶段近似，不能替代潜变量 XWITH、完整 MI 家族或四项调节推断。单个 MI01 得分不能作为正式推断。

## 正确语法与合同

Mplus SAVEDATA 应写成：

    SAVEDATA: FILE IS fscores.dat;
              SAVE = FSCORES;
              RESULTS = estimates.dat;
              TECH3 = tech3.dat;

FSCORES=fscores.dat 不是标准 SAVEDATA 写法。输入、数据、job 合同、launch 脚本和输出必须放在新的隔离目录，不覆盖原始 MI 或已交付结果。

单 Mplus、单处理器运行前执行资源门控；可用物理内存低于 1.5 GiB 或提交空间低于 2 GiB 时只写 deferred 证据，不启动引擎。每个异步提交都必须有 durable BOOT_PID、PROGRESS、engine_receipt、model.out 和 fscores.dat 检查。

Windows 的可用物理内存和 commit 可用量不是同一个指标。若探针没有通过 GlobalMemoryStatusEx 或 host profile 独立读取 commit，就只能把该字段标成 RAM proxy，不能声称完成 commit 门控；宁可保守等待，也不要把代理值写进正式资源结论。

RStudio 前台原先未加载或使用 MplusAutomation 1.2 时，先切换到已经验收的隔离库 MplusAutomation 1.3，再提交任何新模型；记录 .libPaths、包版本和 Mplus 可执行文件哈希。仅切换库不等于重新估计，也不应触发旧模型重跑。

## 实测恢复与终态

第一次 async 回执异常，持久化检查确认没有 reservation、Mplus、model.out 或 fscores.dat；第二次 job ab5c3860 在另一健康 RStudio 会话进入运行，但资源门控 600 秒到期，实际 Mplus 调用为 0。

资源恢复后另立 r2 合同只提交一次 MI01。Mplus PID 14072 在 300.3 秒达到合同上限；输入读取正常但未正常终止，fscores.dat 为 0 字节，最终状态 TIMEOUT_NO_FSCORES。不能因文件存在就视为可用，也不能再延长或重提同一父模型。

一次无界进程扫描使 RStudio 前台短暂无回执。恢复方式是等待、重新绑定同一会话、执行短 native ping；没有重启 R、终止 worker 或重复提交。以后只使用有界的 Mplus 进程过滤、精确目录和持久化 JSON。

## 采用边界

只有在 fscores.dat 非空且通过列名、行数、缺失和得分确定性检查后，才可为全部 MI 成员定义第二阶段模型、家庭聚类、插补合并和测量误差处理。当前试验没有形成任何 H4 统计结论。
