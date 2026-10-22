# Windows RStudio/ClaudeR 前台响应异常：诊断与恢复

长任务期间，RStudio addin 无回执不等于 R 或 Mplus 已停止。必须先检查同一会话的 durable 文件、原 job id、RStudio PID 和 Mplus 进程，再恢复观察。

## 已实测故障链

一次同步递归 list.files 扫描发送到 8787，使 addin 暂无 HTTP/native 回执；另一次无界 ps::ps() 进程枚举使 8789 短暂无回执。两次都没有重启 R、没有终止 worker、没有新增 Mplus。等待后重新绑定同一会话，短 native ping 恢复。

## 恢复顺序

1. 停止新的提交和重试；保留原 job id。
2. 读取精确路径的 BOOT_PID、PROGRESS、engine_receipt、model.out、结果文件和 reservation。
3. 用有界 tasklist 过滤（例如只查 Mplus.exe）确认目标进程，不做全盘递归扫描或无界进程枚举。
4. 先 list_sessions，再 connect_session 到原会话；用短 execute_r 标记验证 native 通道。
5. 只有 durable 证据证明 worker 已终态且没有目标进程，才关闭或恢复 guard；不能因 API 返回空白就重提。
6. 若 native 仍不通，HTTP 仅作为 Addin 存活诊断，不能冒充 native MCP 成功；恢复后继续轮询原 job。

## 工程约束

长任务使用 execute_r_async 和 local=TRUE，阶段信息写入 clauder_progress 与 PROGRESS.jsonl。任何前台诊断都应有时间上限和输出上限。恢复回执必须记录会话、PID、marker、是否重启 R、是否终止 Mplus、是否重提；没有这些证据时不得报告“接口修复”或“模型继续运行”。
