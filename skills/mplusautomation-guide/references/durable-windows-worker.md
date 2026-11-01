# Windows 批次执行与原目录恢复

`scripts/durable_mplus_worker.py` 用于**已有完整基准输出的复现批次**。Mac 保存代码、
计划和验收结果，Windows 本地协调器逐成员执行；每次引擎另有独立监督进程。
协调器退出后，监督进程继续执行原超时上限并保存退出回执。

它目前读取 saved-batch 来源合同，需要原始 `model.out`、参数和 TECH3 基准。
新增模型规格、没有基准输出的探索分析以及统计显著性判断仍走相应科研流程。
不会自动接管旧探针目录，也不会在 Mac 运行真实 Mplus。

## 两层计划

外层用 [Mac 客户端](durable-remote-client.md) 的 `xdev-batch-plan/1` 保存任务名、
脚本 SHA、传输与取回路径。内层 `mplus-durable-plan/1` 给 Windows 执行器：

```json
{
  "schema": "mplus-durable-plan/1",
  "authorization": "具名的已批准复现范围和预算出处",
  "source": "C:\\study\\frozen-baseline",
  "engine": "C:\\Program Files\\Mplus\\Mplus.exe",
  "engine_sha256": "已核实的完整 SHA256",
  "members": ["MODEL_MI01_A", "MODEL_MI02_A"],
  "provenance_only": [],
  "poll_seconds": 1,
  "budget": {
    "max_engine_starts": 2,
    "max_total_engine_seconds": 480,
    "prior_engine_starts": 0,
    "prior_engine_seconds": 0
  }
}
```

这些地址与预算是合同示意，必须换成已经核收的本批实际值。恢复旧研究时要填入
真实已用次数与时间；没有记录时不能把它们写成零。执行器同时核原
`contracts/RUN_CONTRACT.json`，不允许放大其中的次数、总时间或每成员 cap。
来源成员目录的 `job.json` 必须列实际输入 SHA，且保留 `engine_receipt.json` 和
三个基准输出。具名 provenance 例外只允许未被 INP 引用的 JSON 元数据。

Windows 启动正文可写成：

```powershell
$ErrorActionPreference = 'Continue'
$BatchRoot = Expand '%LOCALAPPDATA%\xdev\work\my-approved-batch'
& 'C:\Users\LZHS\AppData\Local\Programs\Python\Python314\python.exe' -X utf8 -B `
  (Join-Path $BatchRoot 'tools\durable_mplus_worker.py') run `
  --plan (Join-Path $BatchRoot 'plan.json') --work (Join-Path $BatchRoot 'run')
exit $LASTEXITCODE
```

一起传入同版 `durable_mplus_worker.py`、`orphan_output_guard.py` 和
`verify_saved_batch.py`；Windows Python 需已有 `psutil`。来源和运行目录必须分开，
首次运行目录为空。代码与来源在 `BATCH_BINDING.json` 中固定，另存其摘要。
改变计划、来源、代码或引擎后不能沿旧目录继续执行。

## 中断时如何接续

- Mac 退出或等待到期：用外层客户端的原状态目录 `reconcile`、`wait`、`collect`。
  原 Windows 协调器仍在时无需再次运行 worker。
- Windows 协调器退出：先查原任务和 `STATUS.json`，确认旧协调器已结束，再以
  同版脚本 `run --work <原运行目录>` 接续。原目录里的 OS 文件锁拒绝并发协调器。
  xdev 已终态的包装任务名不能重复 detach；新的恢复包装名仍指向同一个原目录。
- 原监督进程仍在：核 PID、创建时间、exe 和工作参数，只观察原引擎。
- 监督进程已结束：先核原退出回执、当前来源和所有输出，完整通过才复用。
  原始输入或已验收输出变化时 HOLD，保留原路径，不归档后自动重算。
- 监督进程和退出回执都丢失，但引擎已经退出、输出完整：另写采用回执，保留
  未知退出码和未知剩余预算；不自动启动下一成员。若原引擎仍活着，保持观察，
  仅在它原有 cap 到期时按严格身份结束本批自己的引擎树。

`attempts/<member>/INTENT.json` 在启动前永久保留一次调用和时间预算；
`CLAIM.json` 保证同一意图最多启动一次，即使两个迟到监督器同时出现。
它不是可以删除的“过期锁”。每个成员的 `ENGINE_EXIT.json` 保存实际退出与耗时，
`RESULT.json` 另绑定完整输出与退出回执 SHA。重复恢复不会清零已用预算。
只有真实已结束且核验通过的 `BATCH_VERIFIED` 才算本批完成。

每个成员启动前先预留其完整原 cap；剩余总预算不够时停止准入，不临时放大预算。
监督器使用单调时钟，下一次等待不会跨过剩余期限。到期后才观察到退出码 0 时，
仍保留真实退出码 0，并将状态记为 `TIMEOUT`，不能把轮询期间的迟到退出当作成功。
采用退出回执时还要独立确认实测耗时没有超过原 cap；保存输出和退出码正常并不足够。
这个口径约束的是执行器观察到的完成时间，不伪称掌握系统没有记录的精确退出时刻。

Mac 等待上限与引擎 cap 分开；在运行目录写 `STOP` 只针对本批新引擎。
程序不会按 `Mplus.exe` 名字批量杀进程。系统保持唤醒请求是尽力措施，不能代替
实际电源、登录和联网条件，也没有保证 Windows 注销或断电后自动继续。

## 平台差异与验收

Windows `psutil.boot_time()` 是每个进程各自取得的估计值。实测相差约
0.000256 秒，直接比较相等会把活监督器误判成已退出，提前采用尚未写完的回执。
把它当观察值；原进程身份应由主机、PID、精确创建时间、程序和工作参数确定。

Mac 已退出但未回收的进程读取 `cmdline` 可能返回 AccessDenied。先查内核终态，
查询期间退出则再核原身份；真正仍活着但不可读的进程保持 HOLD。Windows 对
仍有句柄的已退出进程用零超时等待查询真实退出状态，不把可查询等同于仍在执行。

测试使用真实 Python 子进程和全合成结果，覆盖控制进程终止、原 cap 延续、
双协调器/双监督器、永久预算、输入/输出/回执变化、孤儿采用与真实 Windows API。
测试日志、代码 SHA 和每项合成现场分别保存；unittest 的跳过项只写测试 ID 和原因，
不能把 TestCase 对象直接写入 JSON。通过这些测试不代表已验证 Mplus 全夜运行、
休眠、重启，或已经补齐原研究的延期家族。

2026-11-02 首轮候选验收：同一执行器源码在 Mac 为 18 项通过、1 项 Windows API 跳过；
Windows 共覆盖 19 项，来自完整套件的 18 项通过和 1 项定向补测。原完整套件的
外层等待超时保留，没有改写成一次全部通过。两个合成引擎都在原 12 秒 cap 内正常
退出；测试把外层等待从 20 秒改为 60 秒后，包含恢复和完整核验的单项共用 31.18 秒。
模型 cap、次数和执行器字节没有改变，其余 18 项不重复运行。

独立回下载核验共 954 文件；恢复批次的两个成员再次通过原 saved-batch 数值检查，
总共只有两次合成引擎启动。本轮真实 Mplus 调用为零。真实 Mplus 20 成员的测量仍见
[原长任务证据](remote-longtask-evidence.md)，不能把它移算成新执行器的真实 Mplus 实测。

随后补齐单模型 cap 的两个边界：退出回执超过原 cap 时不得发布 RESULT，以及
同为退出码 0、在期限前后观察到退出时分别记 EXITED/TIMEOUT。修订源码
`48a13c44` 的 21 项完整套件在 Mac 为 20 通过、1 平台跳过，Windows 单次
21/21 通过且无跳过；999 个回件 SHA 和恢复后两成员的数值检查通过。
两处检查移除后两个负例都失败，等价改写仍通过，实验副本已恢复原 SHA。
本次测试全为合成，Windows 套件用时 375.92 秒，取回核验用时 19.16 秒；
这不是 Mplus 性能比较，也没有重跑原研究。前述首轮失败与验收原件继续保留。
