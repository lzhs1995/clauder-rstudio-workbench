# 长任务结果与恢复后的独立核验

远程任务返回 DONE/0 只证明执行包装器结束。把正常终止、来源绑定、结果字节、
数值复现和故障恢复分别核验；已完成估计不能因为缺少汇总回执就自动重跑。

## 两项实测误接受与修正

2026-11-01 在独立合成文件中复现过：

- 两份数值副文件与原件相同，model.out 仅有错误，旧 PASS_NUMERIC 仍通过。
  正常终止与无致命错误必须是所有成功分支的共同条件。
- RESULT.json 存在后改动 estimates.dat，旧恢复分支直接跳过，返回陈旧成功。
  恢复时重新核当前输入、已存输出 SHA、退出状态和数值，不信任文件存在。

复核数值文件时按完整 token 解析，拒绝空文件、NaN/Inf、溢出和夹杂文字。
用正则抽取数字会漏掉不合法字段，两个空数组也可能被误判为完全一致。
保留原回执；补件另外记录修正，不重写旧错误为成功。

## 只读工具与适用合同

[verify_saved_batch.py](../scripts/verify_saved_batch.py) 不导入执行 worker，
也不调用引擎。它接受以下目录/回执结构：

- 原始目录的 contracts/RUN_CONTRACT.json，其 primary_sequence 明确成员集合；
- 每成员 models/<成员>/job.json，hashes 列出 model.inp 及数据 SHA；
- 每成员原 engine_receipt.json、model.out、estimates.dat 和 tech3.dat；
- 返回目录的同名成员与 RESULT.json，其中记录 member、engine_exit_code、
  engine_state、inputs、removed_input_copies、wall_seconds 和 compare.<输出>.sha_new。

示例：

~~~sh
python3 verify_saved_batch.py --source /absolute/original-family \
  --returned /absolute/returned-batch --report /absolute/new-readback.json
~~~

若 job.hashes 同时列出不供 Mplus 读取的 JSON 起点映射，明确追加
--provenance-only-file normalized_slots.json。工具仍逐份核其原 SHA，并拒绝
把 INP 中引用的文件排除为元数据；不得忽略所有多余键或按返回结果反推输入合同。

源目录和返回目录必须不同；同 inode 的硬链接不能当独立返回文件。检查完整
成员集合、读取前后身份、原 job 输入哈希、当前输出与回执的哈希，以及非空有限
数值。只忽略 model.out 的日期、起止和耗时行；其他差异返回 REVIEW_REQUIRED，
供按研究合同审阅，不能凭两份数值副文件接近就自动采用。

默认数值绝对容差 1e-6 是该工具的工程复现合同，并非所有模型的科学容差。
它不会自动放宽原参数、SE、协方差或似然标准，也不替代完整 MI/Rubin 推断。
不符合以上目录/回执结构的其他运行需要明确适配，不能补造缺失字段。
Mac 已有十三个合成测试，含错误终止、陈旧结果、非有限数值、缺失/额外成员、
源数据变化、非时间输出变化、硬链接和来源元数据边界。相同脚本已通过 Windows
Python 3.14 对真实 20 成员保存结果的只读核验；Windows 负例套件未全跑。

上述“未全跑”是首次核验的历史范围。2026-11-02 的修订验证已在 Windows 完整
执行同一保存结果读取器的 13 项套件，全部通过；同版独立 guard 18 项也通过。
通用执行器的导出正例、失败诊断及排除回执篡改检查归入其 32 项套件，见
[批次执行器验证](durable-windows-worker.md)。

如果 worker 已按约定删除运行时数据副本，只能独立重读原数据并核其复制回执。
应明确写“运行时副本已不在，未独立重读该副本”，而不是把回执当成仍有原字节。
输出包仍需通过独立传输 SHA；本工具不证明网络传输或故障注入成功。

通用执行器的 `export` 采用另一种方式：输入副本仍留在 Windows，返回包另外携带
`RETURN_INPUT_EXCLUSIONS.json`。读取器核该文件与 BATCH_BINDING、原 RESULT 及
每个输入 SHA 的绑定，报告 `input_copy_bytes_excluded_from_return`；不把“未取回”
写成“已删除”。原 RESULT 保持原字节。原数据仅在 Windows 时，此读取器也在
Windows 对独立导出目录运行；Mac 可以核返回清单和已有获准来源，不能把缺少
原数据的本机核验冒称完整 source 重读。

## 传输字节与跨语言再序列化

传输验真与 R/Python 再序列化对照是两项检查。取回包、清单和文件集仍须按原始
字节逐项核 SHA256；不能把换行、引号或浮点文本差异当成允许传输改变的理由。
如果同一来源 CSV 经 R `write.csv` 重写，先固定源 CSV 的 SHA，再依其明确的列、
行顺序及字段语义逐字段核对派生文件，同时保存派生文件自己的 SHA。字节不同
须说明是已验证的序列化差异，不能反推新来源哈希或泛化成所有 CSV 均可近似比较。

2026-11-04 的六格终态核验中，仅历史 JSON 耗时 `seconds` 经 R/Python 往返时允许
绝对误差不超过 `1e-9` 秒；其余来源字段精确比较。该舍入容差不适用于参数、SE、
TECH3、积分比较或科学采用门槛。两份原失败审计均保留，新核验另写回执；不为
修复序列化审计重复估计。具体证据是 `CFPS_H42_FINAL_FIRST_ATTEMPT_DISPOSITION_20261104.json`
引用的独立 `MAC_ACCEPTANCE.json`，其状态明确为终态证据通过而非完整 MI 通过。

TIMEOUT 也是实际引擎调用，原调用次数、实际耗时、cap 与确认退出记录必须保留，
不能因没有可采用结果把成本归零。输出停在 `INPUT READING TERMINATED NORMALLY`
只说明输入读取已结束，不能证明后续估计从未运行；估计是否结束以原引擎回执及
完整输出核验为准。失败回执及其来源可以验收 PASS，同时仍为
`scientific_usable=false`；超时和负 SY 方差都不因此成为科学可采用结果。

## Worker 中断后的边界

区分“Mac 等待到期”“服务短时离线”和“Windows worker 退出”。前两者不代表
引擎退出；继续原任务名查结果。worker 退出后按 PID、创建时间和工作目录确认
原引擎。它可能在控制器重启前自行完成，故没有 RESULT 不等于没有有效输出。

先校验原输入、输出正常终止、必要副文件及其来源，再决定导入完成输出、
等待原引擎，或按已授权预算处理确实未完成的尝试。保留孤儿输出与恢复日志。
若发生额外一次估计，报告实际调用次数和耗时，不能称为严格恰好执行一次。
新 xdev 包装器任务名和不变的模型工作目录也应分别记录。

同一 MI 家族的首个不可采用成员应停止该家族的后续估计。保留已有 PASS 与失败
输出，不替换失败 MI、不自动延长 cap，也不因恢复过程顺手扩大研究家族。
这不等于冻结计划中已分别登记、各有既定预算的独立目标必须一并停掉：只有前一格
原引擎已确认退出、调用与耗时记账完整、下一格仍满足原计划和剩余预算，才可继续
该独立目标；退出或成本未知则 HOLD。不能用此规则重启同规格失败格或追加 MI。
工程探针若与原 cap、准入等待或资源门槛不同，逐项记录其差异与实际影响。

## 独立孤儿检查与采用回执

`scripts/orphan_output_guard.py` 是独立的检查器，所有分支都不启动或结束引擎。
默认只写具名检查报告；`--record-adoption` 才在运行目录的 `recovery_adoptions/`
另写采用回执。它不覆盖 RESULT、输入、输出或旧失败，也不改现役 worker。

~~~sh
python orphan_output_guard.py --source C:\work\original-family \
  --work C:\work\isolated-run --member MI01_A \
  --engine C:\tools\Mplus.exe --report C:\work\checks\MI01_A-check.json
~~~

在 Windows 本机调用，以便实际核原 PID、创建时间、程序、工作目录与 model.inp
参数。不能在 Mac 检查一个 Windows PID 后把“本机无此 PID”当成远端引擎已退出。
CLI 拒绝在非 Windows 主机上运行；Windows 调用方仍须确保 marker 属于本机，
不能把另一台 Windows 的 PID 当成本机进程。库函数的 Mac 测试只使用本机合成进程。
Mac 可以复核取回的输出和回执，但不能代替这个活跃进程观察。

| 决定 | 含义与下一步 |
|---|---|
| WAIT_FOR_ORIGINAL_ENGINE | 原进程身份一致且活跃；继续观察原任务，不终止或重派 |
| REUSE_VERIFIED_RESULT | RESULT 经过完整输入/当前输出/数值复核，可复用 |
| ADOPTABLE_SAVED_OUTPUTS | 原进程已退出、完整保存输出满足采用条件；默认还没写采用回执 |
| OUTPUTS_ADOPTED | 已新建独立采用回执；退出码仍为 null，未造 RESULT/0 |
| HOLD | 输入、来源、回执、进程或输出存在缺口；保留现场，不自动重估 |
| NO_WORK_DIRECTORY | 没有可采用的运行目录；这不是新增估计授权 |

孤儿采用要求 ENGINE_STARTED.inputs 与原 job 的运行时输入哈希完全相同，并且输入副本
仍可逐字节核验；启动器须在运行前固定输入清单，进程出生记录沿用这份清单。
当前文件相同不能证明历史引擎实际使用过它；旧的仅 PID/时间记录、已经删除的数据副本
或没有来源绑定的输出保持 HOLD。不能为了让检查通过补造旧启动哈希或恢复一份数据后
声称它就是历史运行时副本。

正常终止、非时间行、有限数值、输出时间及独立文件身份均会检查。采用回执保留
`engine_exit_code=null` 与 `budget_remaining=null`，原预算台账另行核收；不把正常
输出推断成已经观察到退出码 0 或尚有完整重试额度。再次采用先重验当前字节，匹配时
复用原采用回执，不改其时间或内容。原始资料目录与模型目录不能用作新增报告位置。

采用写入使用 OS 文件锁。真正的 worker 若要自动消费这个决定，也必须协调同一恢复锁
并保存自身的累计预算和单实例约束；本工具自身不修改原探针的调度/杀进程逻辑。
Windows worker 尚未接入该检查器时，不能宣称已修复原 worker 的完整自动恢复。

2026-11-02，Mac 和 Windows 的同一套 18 项合成测试均全部通过，Windows 无跳过项。
覆盖活跃 Python 子进程、PID 复用、错误程序身份、未知进程、错误/空/非有限输出、
陈旧回执、输入缺失、旧薄启动记录、硬链接和单写者锁；Windows 实际运行了 msvcrt
锁与进程检查，Python 为 3.14.3。该次套件耗时 37.76 秒，两个回件取回并核 SHA 用时
4.18 秒，没有读取研究数据或调用 Mplus。

先前 Windows 尝试有一项失败：合成子进程的固定短 sleep 先于检查结束。保留原失败，
将夹具改为显式 ready/release 握手后另建具名测试；guard 实现与检查断言均未放宽。
这证明独立检查器在 Windows 上通过，不证明原 worker 已消费采用回执，也不证明
Windows 休眠、断电或整夜恢复。原 worker 接入、累计预算与单实例恢复仍须单独验收。

## 原探针 v3 的有限接入验收

2026-11-02，原作者的 v3 `f7d9a414` 已完成独立核收：Mac 与 Windows 各 26 项
合成测试通过，Mac 14 个故障变体均被指定测试检出。另在隔离副本复核未知耗时
（有、无总预算）、采用后输入变化和原批次预算绑定四组情形，均保留原输出且不启动
引擎。Windows 当前 190 个探针文件与作者已取回的 Mac 副本逐文件 SHA 相同。

原真实目录的 Windows `--decide-only` 返回 20/20 `REUSE_VERIFIED_RESULT`，
实际历史启动仍为 21 次，其中 MI19 第一次的耗时未知。未知耗时不使用输出 mtime
估算，不因省略总时间预算而放行下一次启动；既有成功结果仍可复核和复用。
批次成员、引擎、来源、原 cap 与总预算在首次绑定后不能由恢复参数改写。

这是原探针的兼容修复。v2、旧失败和实际调用记录保持原样，v3 没有执行新的真实
Mplus；活孤儿观察使用合成或替代进程检查。新增复现批次统一使用
[Windows 批次执行器](durable-windows-worker.md)，不维护第二套通用调度入口。
前述独立检查器的 18 项测试、v3 的 26 项测试与通用执行器测试是不同证据集，
不能相加后冒充真实模型数量或整夜可靠性证明。
