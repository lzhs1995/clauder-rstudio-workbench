# 可接续的 Mac 批次客户端

`scripts/remote_batch_client.py` 把本地计划、固定输入、提交意图、原任务名和每阶段
计时保存在一个独立目录。它只调用现有 `cross-device-remote/scripts/xdev`；
Windows 继续执行原批次，Mac 退出或等待到期后先查原任务。

客户端不决定模型规格、运行预算或 Windows worker 的恢复策略。研究家族、种子、
积分、起点、原 cap 和实际调用次数仍由具名研究合同与 Windows 执行器约束。
特别是旧探针 worker 的“缺 RESULT 就重算”路径不能因换了 Mac 客户端而自动启用。
worker 中断先按 [保存输出与恢复核验](remote-output-acceptance.md) 处理。

## 一次计划，提交后用原状态目录

计划文件是 `xdev-batch-plan/1` JSON：

~~~json
{
  "schema": "xdev-batch-plan/1",
  "name": "my-study-batch-20261101-v1",
  "launcher": "./launch.ps1",
  "return_dir": "%LOCALAPPDATA%\\xdev\\work\\my-study-batch-20261101-v1\\results",
  "output_dir": "./returned",
  "payload": [
    {
      "local": "./batch.R",
      "remote": "%LOCALAPPDATA%\\xdev\\work\\my-study-batch-20261101-v1\\batch.R"
    }
  ]
}
~~~

`launch.ps1` 是已经审阅的、无 BOM UTF-8 的完整启动正文；它使用 Windows 已确认
的 Rscript/Mplus 路径、在具名工作目录运行整个批次，并写出所需返回目录。
`payload` 只列本次确需传输的脚本或小型输入；原研究数据可以继续放在 Windows。
路径相对于计划文件解析；Windows 路径要求绝对地址或明确的 `%变量%` 根。
`return_dir` 应为 worker 完成后不会继续写入的结果目录，不能把整个用户目录取回。

~~~sh
B="$HOME/.agents/skills/mplusautomation-guide/scripts/remote_batch_client.py"
python3 "$B" --state ./batch-state submit --plan ./plan.json
python3 "$B" --state ./batch-state wait --max 60
python3 "$B" --state ./batch-state collect
python3 "$B" --state ./batch-state timings
~~~

`submit` 要求新的本地状态目录；会先保存固定副本，再经 xdev 推送，启动正文还会
在 Windows 核 payload SHA。重复 submit 拒绝，Windows 同名任务也拒绝。
Windows 的 `DONE/0` 和传输完成只表示执行/文件流程结束，统计结果另行验收。
失败作业同样可以 collect 诊断文件，客户端保留实际非零退出码。

## Mac 中断或提交回执丢失

~~~sh
python3 "$B" --state ./batch-state status
python3 "$B" --state ./batch-state reconcile
python3 "$B" --state ./batch-state wait --max 60
python3 "$B" --state ./batch-state collect
~~~

`reconcile` 不调用 detach。它经 xdev 只读检查 Windows 的原 `jobs/<name>/body.ps1`：
必须包含本次随机绑定标记及完整固定启动正文，才能把未知提交转为已确认。
不同正文、同名旧任务、路径变化或读取失败都保留未知/拒绝状态，不自动另提模型。
若 Mac 在保存查询脚本后、登记查询阶段前退出，下次恢复保留该残留脚本，
另用唯一文件名查询同一个原任务；不会因为本地同名文件而阻塞，也不重新提交。
实际队列 ID、原 stdout/stderr 和逐阶段意图都在本地状态目录；有迟到队列回执时
也可用原 `xdev result <id>` 查明，不能把一次查询超时解释为从未提交。

`--client-timeout` 默认 90 秒，仅限制本地 xdev 子进程的等待。`wait --max` 也是
Mac 等待预算，不是 Mplus cap。客户端到期只结束自己的等待进程；Windows 任务
可能已启动或仍在队列中。继续使用原状态目录，按其未知状态先 reconcile。

启动正文和 payload 的固定副本、原名称与绑定字段不可修改。开发源码可以在另一路径
继续编辑；后续新计算用新计划和新命名。若只有健康检查失败，尚未尝试任何 push/detach，
通道恢复后可用 `retry-preflight` 接着提交同一固定计划。任何推送或提交已有未知结果时，
该命令拒绝；保留现场核原次，不自动恢复推送或猜测已执行状态。

## 文件、计时与证据

- `TASK.json`：原计划、固定 SHA、状态、阶段索引和原 Windows 任务名；原子写入。
- `phase-*/INTENT.json`、`RESULT.json`、`stdout.txt`、`stderr.txt`：每次真实调用及单调时钟耗时；
  未结束的阶段没有伪造耗时，目录残留不会触发第二次提交。
- `COLLECTION.json`：xdev 核过传输 ZIP 后，本客户端再次核返回文件集、大小及 SHA。
  `verify-collection` 可在后续使用前复核本地文件是否改变。
- `timings`：分别汇总 health、push、detach、reconcile、wait、pull 调用。每项仍包含相应
  排队、执行与轮询；Windows 引擎时间和单独的队列时间未测时为 `null`。

`status` 与 `timings` 在另一个客户端持锁等待时仍可只读。实际 submit、reconcile、
wait、collect 则由同一本地状态目录锁串行，防止两个 agent 同时改变其状态。
取回要求新目录或空目录；原失败目录不清空。恢复下载可明确指定新的 `collect --output`。
collect 后发现文件被改动就停止采用原验收，不通过重新下载覆盖变化。

## 已验证范围

2026-11-01 的 21 项本机模拟覆盖重复提交、提交回执丢失、进程退出、等待超时、任务名冲突、
固定副本篡改、错误返回 SHA、负退出码、失败诊断取回以及锁内并发观察。
恢复查询正文落盘后的退出已用真实本地进程故障注入复现并修复，原任务仍只提交一次。
另有真实 Windows 25 秒无模型测试：Mac 在远端已提交、本地确认状态写入前退出，
随后按固定正文接回，实际启动一次，4 个返回文件 SHA 通过。

那一次的本地调用耗时为 push 2.15 秒、detach 2.15 秒、reconcile 2.18 秒、
wait 查询 1.68 秒、pull 5.26 秒。它们不是纯网络延迟，也不能与早先冷启动/多文件
往返的总耗时直接比较。这次没有新 Mplus 估计、服务中断、Windows 休眠或重启。
真实 Mplus 批次依据仍是 [20 成员长任务证据](remote-longtask-evidence.md)。
