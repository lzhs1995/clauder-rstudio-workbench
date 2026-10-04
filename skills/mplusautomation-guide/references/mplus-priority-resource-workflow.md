# Windows Mplus 优先：诊断、回收、调度与验证

最新实测与已发布首跑策略见[首批模型资源测量](measured-first-run-resources.md)，其运行事实取代下文历史“MI尚未启动”的状态；阈值仅适用于已验证批次。

用户授权优先运行Mplus后，应主动执行本流程，不以反复读取可用内存代替推进。优化目标是有效模型吞吐量和研究结果交付，不能把少占内存、进程数量减少或单次CPU升高自动视为加速。

## 每次启动的顺序

若RStudio渲染过大量图表，优先检查[已关闭浏览器与调度器的深层缓存](r-browser-cache-reclamation.md)。本次沿环境引用追踪并归档清理，实测释放约870MiB活向量对象；浅层`object.size()`和浏览器关闭状态均曾漏报这一占用。

1. 核对本任务RStudio PID及创建时间、Mplus输入/数据哈希、当前异步job和输出状态。列出其他会话正在运行的Mplus，防止重复提交和盲目增加并发。
2. 先用轻量监控采样CPU、物理可用内存、系统commit余量、分页读取和磁盘延迟。使用下方脚本，不为读取路径常量导入NumPy、Pandas、模型数据或论文审计模块。
3. 回收已确认不再使用的本任务worker、重复数据与无文档辅助程序；有活动连接或存活客户端的MCP不是废弃进程。父进程缺失也不能单独证明服务无用。对恢复方式明确的辅助程序优先正常关闭，权限失败留证，不循环尝试同一失败操作。
4. 有用户授权且确有CPU竞争时，可将指定任务的Mplus设为Above Normal并记录原值；已有更高优先级不降低。不要使用Realtime，不把提高优先级当作启用多线程。保留模型、RStudio、网络代理、未保存文档及其他活跃任务。
5. 重新检查资源合同与依赖，按研究优先级提交已准备好的模型。未知峰值先运行一个有研究用途的模型；记录其峰值RSS/private、整体commit增量和耗时，后续才据此修订并发预算。合同修改必须走项目原有发布流程。
6. 同一主机的各队列共享准入/占位机制，并把不经过调度器的Mplus也计入预算。条件允许再增加并发；不能把16个逻辑处理器直接当作16个模型名额。内存受限时串行准备、估计、解析，避免十份MI数据同时复制进多个R进程。
7. 运行中按同一job_id轮询，并观察CPU累计时间、输出增长和阶段。出现资源压力先暂停新提交、减少自己的辅助负载；已有有效估计不因一次高内存读数而被杀死。模型结束立即释放其临时数据和已结束worker，继续下一个已验收依赖。

## 可执行轻量监控

Windows Python调用 `scripts/mplus_priority_watch.py --owner-pid <已核实R_PID> --duration 60 --interval 10 --output <新文件.jsonl>`。

- 默认只监测。`--prioritize-owned-mplus`只调整指定R父进程的Mplus后代，PID和创建时间绑定，正常退出恢复原优先级。跨研究任务调整需要本次授权覆盖其资源调度。
- JSONL持续落盘，包含系统commit、可用物理内存、Mplus RSS/private、按单核100%表示的CPU用量、I/O累计量、分页与磁盘延迟；英文PDH计数器适用于中文Windows。
- 权限失败/计数器缺失不是零。日志必须是新路径。此脚本不提交模型、不替代异步job登记、不降低准入合同门槛。
- 监控意外被强杀时，Python finally不能保证恢复；按日志的PID+创建时间核对仍存活进程，再恢复记录的original优先级。不得按旧PID盲目操作。
- 准入前用 `scripts/windows_memory.py` 检查系统；`--apply`仅在当前回收授权下使用其限定清单，实际操作和失败都会保存。不要定时全局清working set或反复drop_caches，这可能增加换页和重新读盘。

## 判定真正的瓶颈

| 连续观测 | 下一步 |
|---|---|
| 未生成Mplus进程，准入拒绝 | 是启动调度阻塞，不能称作Mplus计算慢；回收并重新核验合同 |
| 一个核心接近满载、模型内存小、输出持续增长 | 检查算法/当前阶段的并行支持和PROCESSORS；总体CPU占比低不等于空闲 |
| 可用内存低，持续分页读取与磁盘延迟升高 | 减少并发和数据副本，记录工作集/commit峰值；先保住当前估计 |
| CPU低且无输出增长 | 检查等待I/O、外部进程/对话框、阶段和实际错误；不能仅据此判死锁 |
| 多核已满或模型内部并行充分 | 避免外层模型并发与内层线程相乘造成过度调度 |

固定样本、规格、starts/seed、积分设置和版本后，才能比较性能。不要减少迭代、随机起点或积分精度来冒充纯资源优化。PROCESSORS支持取决于模型和算法；没有普遍最佳线程数。

## 工具能力与实际调度路径

已读取2026-10-02在线来源：[ClaudeR README](https://github.com/IMNMV/ClaudeR)、[Workbench skill](https://github.com/lzhs1995/clauder-rstudio-workbench/blob/main/skills/clauder-rstudio-workbench/SKILL.md)、[MplusAutomation vignette](https://cran.r-project.org/web/packages/MplusAutomation/vignettes/vignette.html)。源码快照保存在本任务 `work/pp_lgcm_reconciliation_20261001/resource_sources_20261002/`。

- ClaudeR的`execute_r_async`通过独立callr进程保持前台响应；正式模型使用durable_files模式，后台只读取必要输入，不复制整个`.GlobalEnv`或把完整十份MI回传前台。一个长作业只提交一次，轮询同一job；完成即释放该worker。异步不代表Mplus数值计算本身加速。
- Workbench已有`fanout-plan`、`fanout-poll`、`merge-gate`和资源门槛，先复用这些能力。原生工具路径由agent提交并登记真实job；`fanout-run --auto-scale`属于独立MCP stdio模式，不能伪称原生调用。串行依赖的MI→得分→消费者不能一起fan-out。
- 开发版guide已有SQLite事务队列`mplus_queue.py`及`mplus_queue_worker.R`，包含用途/依赖优先级、CPU/内存/处理器预算、并发上限和暂停恢复。让参与同一批次的worker使用同一个队列root，避免每个会话各自判断“还有空闲”。未注册的外部Mplus仍须由主机监控计入；当前PP-LGCM的独立发布合同没有自动迁入该队列，不可宣称已统一接管所有会话。
- MplusAutomation文档明确数值估计由Mplus完成；`createModels`负责输入生成，`runModels`负责执行，`readModels`负责读回。精确目标、`recursive=FALSE`、独立输出目录和日志可防止误跑整树；`replaceOutfile='never'`只能防覆盖，不能代替输入哈希及结果有效性验证。批量模板和缓存读回提高流程效率，不自动把一个模型并行化。
- 保存完整输入/数据、随机起点/种子/积分设置后，才可在隔离性能副本比较PROCESSORS配置；资源设置不能擅自改变统计规格。已有计算阶段单核满载时，优先核对算法支持，再决定内部并行或独立模型并行，不能机械增加线程。
- 在线上游ClaudeR与本地LZHS fork版本不同。以本机实际暴露的工具和原生smoke为准，不为获取README中的新能力盲目升级/重启活跃RStudio。

## 2026-10-02本机实测与执行边界（不是Mplus加速基准）

- PP-LGCM的修正MI尚未启动，3 GiB为项目保守准入值，不是实测MI峰值。保留合同。
- 另一会话APIMeM模型PID18968在实测窗口RSS约36.5MiB、private约114.8MiB、约一个核心忙碌，原优先级已是Above Normal。不能用这份模型的低内存需求推断390列MI的需求。
- 后续PID34760模型输入明确写有`processor=10; estimator=ML; bootstrap=1000;`。独立20秒采样为96.0–97.7%单核CPU、RSS约33.7MiB、private114.85MiB、磁盘平均传输延迟约0.33–0.56ms，输出持续增长。随后OS检查仅1线程，亲和性为逻辑核0–7。说明配置数字不能代表当前实际并行度；需逐阶段实测，不能直接断定整个算法不支持并行，也不能用全机CPU低占比断定Mplus卡住。保持现有统计设置及其他任务的CPU亲和性。
- 资源检查原先为导入路径常量间接加载NumPy，私有内存536.68MiB、19线程；同一导入在仅限该Python进程的OPENBLAS_NUM_THREADS=1、MKL_NUM_THREADS=1、NUMEXPR_NUM_THREADS=1下为54.58MiB、4线程。RSS分别35.88与34.92MiB：主要节省commit，不是释放482MiB物理RAM。
- 去掉这项不必要依赖后，进程归属诊断自身private为11.16MiB；轻量性能监控约21.5MiB。不要改全局环境，也不要把资源检查的BLAS线程设置擅自套给R/Mplus数值估计。
- Task Manager终止返回AccessDenied；系统缓存回收返回NO_PRIVILEGE/1300。未宣称回收成功。当前证据没有证明所有Windows后台程序均已优化或Mplus整体变快。
- WSL一度无法启动Windows程序，错误`UtilAcceptVsock ... 110`；实际WSL_INTEROP指向已消失的socket。检查`/run/WSL`后，仅对子命令指定仍存在的`/run/WSL/2_interop`，Windows Python重新启动成功，最终5秒监控完成。未重启WSL/RStudio、未改持久环境。原生R拒绝system2的安全规则保留，不通过动态调用绕过。

本任务证据位于 `<WINDOWS_USERPROFILE>/pp_lgcm_runs/20260908_parallel/recovery/20261001_pp_lgcm_reconciliation/10_resume_verified_20261001/scientific_followup/measurement_audit/`：`mplus_priority_watch_20261002.jsonl`、`mplus_priority_apply_20261002.jsonl`、`resource_import_benchmark_1790918899970416400.json`、`windows_memory_priority_20261002.json`。长期指南不能用这些日期化数值代替当前机器的实测。
