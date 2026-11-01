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

如果 worker 已按约定删除运行时数据副本，只能独立重读原数据并核其复制回执。
应明确写“运行时副本已不在，未独立重读该副本”，而不是把回执当成仍有原字节。
输出包仍需通过独立传输 SHA；本工具不证明网络传输或故障注入成功。

## Worker 中断后的边界

区分“Mac 等待到期”“服务短时离线”和“Windows worker 退出”。前两者不代表
引擎退出；继续原任务名查结果。worker 退出后按 PID、创建时间和工作目录确认
原引擎。它可能在控制器重启前自行完成，故没有 RESULT 不等于没有有效输出。

先校验原输入、输出正常终止、必要副文件及其来源，再决定导入完成输出、
等待原引擎，或按已授权预算处理确实未完成的尝试。保留孤儿输出与恢复日志。
若发生额外一次估计，报告实际调用次数和耗时，不能称为严格恰好执行一次。
新 xdev 包装器任务名和不变的模型工作目录也应分别记录。

首个不可采用成员应终止该批次的进一步估计。保留已有 PASS 与失败输出，
不替换失败 MI，不自动延长 cap，也不因恢复过程顺手扩大研究家族。
工程探针若与原 cap、准入等待或资源门槛不同，逐项记录其差异与实际影响。
