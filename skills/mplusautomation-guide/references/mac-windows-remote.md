# Mac 编写与核验，Windows 执行 Mplus

后续 20 成员真实批次、服务中断和 worker 恢复的独立证据见
[真实长任务与效率](remote-longtask-evidence.md)。下文保留较早合成试验的原测量边界。

适用情形：Mplus 许可证、原始输入和既有运行环境位于 Windows，而 agent 在 Mac。
使用已安装的 `cross-device-remote` skill；唯一入口为
`~/.agents/skills/cross-device-remote/scripts/xdev`。不要启动另一套常驻队列。
需要跨 Mac 会话保存任务状态时，使用 [可接续客户端](durable-remote-client.md)；
它仍调用原 xdev。Mac 的 21 项客户端测试、两端各 18 项独立孤儿检查测试及原任务
查询恢复已有独立回执。原探针 v3 的有限兼容已通过两端各 26 项合成测试与原目录
20/20 只读复用判定，见[恢复验收](remote-output-acceptance.md)；它保留原 21 次
启动和一次未知耗时，没有重新执行真实模型。
已有完整保存输出的复现批次另有 [Windows 执行器](durable-windows-worker.md)，
把每次引擎的超时监督放在独立进程中，避免 Mac 或批次协调器退出时丢失原预算。
它使用新的具名工作目录；旧探针的版本、输出与实际 21 次启动仍保持原记录。

## 接续顺序

1. 读原接续 Prompt、最新专题交接、家族覆盖表及终态回执。已完成估计先复用。
   迁移时的暂停由用户后来的具体恢复指令更新；传输成功本身不授权估计。
2. `xdev health` 返回 OK 后，记录 Windows R、包、Mplus 路径、可用内存和现有
   Mplus 进程。一次先提交一个模型；Windows 内存和其他任务共同决定并发。
3. 在 Mac 的新工作目录编写完整脚本。用户要求 RStudio／ClaudeR 时，先按
   [两种入口共用流程](rstudio-two-entry-workflow.md) 绑定真实 Windows 会话，
   再用 `xdev rstudio submit` 让 ClaudeR source 同一 R 批次脚本；该脚本在
   Windows 本机 agent 下也可直接经 ClaudeR 执行。只有用户选择后台 Rscript
   或直接引擎路线时，才使用相应 `xdev rscript` / `detach` 入口。
   原始数据留在已有 Windows 目录；只复制本批确需的输入到隔离工作目录。
4. 明确设置 `MPLUS_COMMAND` 为 Windows 完整 exe 路径。helper 的默认 `command`
   读取这个环境变量；显式 `command=` 可覆盖。旧 helper 的 `command=""` 会
   绕过环境默认值而重新探测路径，不能仅凭设置环境变量声称已固定引擎。
5. 记录输入/数据哈希、种子、积分、起点、PROCESSORS、引擎版本和唯一任务名。
   有效结果要求正常终止、诊断检查与数值核验，不能只看进程退出码。
   取回后用[独立输出核验](remote-output-acceptance.md)检查当前字节与完整成员集合；
   RESULT 存在或包装器 DONE/0 不等于统计结果已通过。
6. Windows 完成后生成只含所需输出的目录及文件清单，一次取回并复核 SHA256。
   用新目录保存图表、报告和新结果；不覆盖迁移原件或现役 CC Switch 技能目录。

## 等待和预算

`xdev run --timeout` 是 Windows 短命令的运行上限；`--wait` 是客户端等回执的
上限。迟到回执用 `xdev result <job_id>` 取回。不要因客户端超时再派原命令。

`xdev wait <name> --max` 及 `rscript --max` 控制等待，**不会终止模型**。
等待到期后继续 `xdev wait <原名>`，再 `pull-dir` 原工作目录。
研究模型的预算必须在 Windows worker 内执行，例如对本次新建的 processx
子进程设置 timeout 并 cleanup_tree；只监督自己的进程树。保留原失败和已用预算。

2026-11-01 的恢复试验只提交一个 25 秒无模型任务：首次等待返回 124，
原名续等返回 DONE/0，Windows 回执 starts=1。它证明等待到期恢复，未模拟断网、
休眠、重启或整夜任务。Rscript 链不等于原生 RStudio/ClaudeR 链。

## 测量与选择

2026-11-03 已有真实 RStudio 长批次证据：son 最后59阶段保留同一个Windows
RStudio/ClaudeR/MplusAutomation 1.3链路，新增引擎6703.5815702秒、阶段边界墙钟
7263.353105秒，引擎占92.29%。这不是CPU利用率，也未计此前工具开发、失败和校准
时间；没有Windows本机agent对照，不能声称远程比本机快。其余细节见
[队列效率与最终核收](queue-efficiency.md#completed-income-queue-2026-11-03)。

2026-11-04 的 CFPS H4.2 六个独立首尝试，经 xdev 提交回执 `3063` 进入同一
Windows RStudio/ClaudeR 异步 R 链。原 `R_OWNER.json` 记录 RStudio PID 42264、
rsession PID 33684、R worker PID 28872；`R_MPLUSAUTOMATION_CALL.json` 固定
`MplusAutomation::runModels` 1.3。PID 仅标识这次证据，不是后续会话的连接参数。
`QUEUE_CLAIM.json` 的 2026-11-03 23:47:44 UTC 至 `QUEUE_RESULT.json` 的
2026-11-04 00:05:15 UTC 为 1051 秒，六次引擎记录合计 979.7800463 秒，占这段
队列墙钟的 93.2236%。该比例包含失败尝试的引擎耗时，不是 CPU 利用率，不含
此前开发与后续取回审计时间，也没有 Windows 本机 agent 对照，不能外推为整个
项目效率或远程加速比。

六格终态为 3 次 TIMEOUT、3 次负 SY 方差，科学可采用数为 0；完整 MI 家族没有
完成。同一队列依原冻结计划、逐格确认退出并完整记账后完成六个独立首尝试，
没有追加同规格重跑或后续 MI。终态证据独立核验通过只证明调用、成本、来源与
失败分类可追溯，见 `CFPS_H42_FINAL_FIRST_ATTEMPT_DISPOSITION_20261104.json`
及其引用的 `MAC_ACCEPTANCE.json`；不能把这次运行效率读成科研成功率。

下面三组小模型保留原先完整往返的测量口径，不与该长批次直接作加速比。

2026-11-01 在同一 Windows Mplus 9 / R 4.5.2 / MplusAutomation 1.2 上，
完成三组配对：每组 helper 合成回归，然后以完全相同 INP/DAT 直接运行 Mplus。
六个估计均正常终止，每对三行参数的估计与标准误差为零。

| 组 | Windows 整段 R 脚本 | 直接引擎 | Mac 完整往返 |
|---|---:|---:|---:|
| 1 | 24.61 s | 0.43 s | 69.253 s |
| 2 | 17.04 s | 0.57 s | 68.359 s |
| 3 | 16.67 s | 0.41 s | 69.243 s |

Mac 往返含两次输入推送、后台提交、轮询、打包及输出下载。二者的差值还含
R 脚本计时以外的启动，不是纯网络延迟。固定顺序、同一台 Windows 和小样本
限制了比较；没有测量人在 Windows 本地开发的效率，也未测复杂 MI/LMS 长任务。

三组脚本外开销为 44.643–52.573 秒。若把“额外开销不超过批内计算时间的
10%”作为规划目标，计算批次至少约为 446–526 秒，即 7.44–8.76 分钟。
这是按已测固定开销推算的批次规模，不是长模型已经通过的性能门槛。当前记录
没有分别测量排队、上传、下载与轮询；不能把剩余时间进一步拆成未经计量的阶段。
最终 helper 回归中，子 Rscript 启动与正文之外约为 9.90−1.39=8.51 秒，
只能代表该次观测。长任务、断连和进程终止恢复需另有原任务的实测证据。

推荐 Mac 负责编辑、版本比较、输出复核；Windows 集中执行有用途的模型批次。
不要把每个短命令、每个 MI 成员拆成一次完整往返。长期任务靠 Windows 本地
日志和阶段文件推进，Mac 适度轮询；把等待间隔降到很小也会增加共用队列开销。
大型初次迁移仍用既有百度网盘流程，日常 xdev 传脚本和结果增量。
频繁 GUI/许可证操作、Windows 无法保持在线或持续网络故障时，保留 Windows
原会话作为回退。远程控制改善开发位置，不会使同一 Mplus 算法自动变快。

## 技能版本与文件验真

Windows 现役目录可能由 CC Switch 管理。先按文件导出并核 SHA，再与仓库比较；
“Windows 比主分支新”不足以决定整目录覆盖。此次双方各有三份独有参考文件，
Mac 候选按并集保存，并保留较新的恢复说明；模型 helper 的变化另做真实回归。
Mac 技能可与 Windows 的已验证隔离候选配合，安装、仓库合并和现役切换分别记账。

共享技能入口宜指向固定的本机验收副本，与可继续修改的开发分支分开；记录源
commit、逐文件 SHA 和原链接，先验新副本再原子切换。固定本机副本不等于
上游合并或公开发布。Windows CC Switch 原目录和正在运行的任务保留原版本；
只有文档变化、引擎 helper 字节不变时，不为安装重复消耗已完成的模型试验。

PowerShell 5.1 使用 ZipArchiveMode 前须加载 `System.IO.Compression` 和
`System.IO.Compression.FileSystem`。读取 JSON 数组直接赋值给变量；把
`ConvertFrom-Json` 包进额外 `@(...)` 可能形成嵌套数组。R、Python 和 shell
代码写成文件再调用，避免 Windows 原生命令参数重新解析引号。

结果包清单不得登记自身哈希。`artifact_manifest.py build <新候选目录>` 会拒绝
覆盖已有清单；`verify ... --expected-sha256 <包外摘要>` 同时检查完整文件集、
大小和 SHA。原有错误清单保留在原件中。清单通过不证明统计结果；PP-LGCM 的
完整数值复核在隔离副本执行原独立验证器，公开包仍缺少个体输入，不能重估模型。

## PP-LGCM 科学边界

2026-10-23 终态为 CHARLS H4.1 12/12，H4.2 核心 4/4，H4.2 资源 8/12；
四个收入分组资源家族延期。此处收入是观测基期收入分组下的 `SX XWITH IZ`，
不能称为收入本身的潜轨迹。`SX XWITH Z0` 是另一种敏感性估计对象，收入通常
40 份 MI，教育/城乡通常 20 份。未启动依赖与真实 Mplus 超时分别报告。

修复的 son×urban 20 A + MI01 B 家族采用正确 C4 城乡语义、进入实际拟合矩阵
的辅助乘积项，以及 GH07 终值核验后的 GH15 起点。既有输出的复核不会新增
家族覆盖。CFPS 原四项调节完整推断与完整 H4 仍未完成；超时不等于零效应，
基础设施修复不授权重跑原样失败规格或延长研究预算。

2026-11-03 接续结果：四个收入分组家族均已完成40MI/80阶段及独立R合并，
H4.2资源汇总从8/12补齐至12/12并通过148项汇总检查。CFPS观测Z0、固定SY的
MI01两起点数值校准也已通过，见[积分规则与优化器核验](native-worker-and-quadrature-recovery.md#read-the-integration-rule-not-a-filename)。
这两项都不等于CFPS原四项调节完整推断或完整H4；保留原估计对象和条件工作MI边界。
