# Windows RStudio/ClaudeR 前台响应异常：诊断与恢复

长任务期间，RStudio addin 无回执不等于 R 或 Mplus 已停止。必须先检查同一会话的 durable 文件、原 job id、RStudio PID 和 Mplus 进程，再恢复观察。

## 已实测故障链

一次同步递归 list.files 扫描发送到 8787 后，addin 暂无 HTTP/native 回执；另一次无界 ps::ps() 进程枚举后，8789 短暂无回执。两次都没有重启 R、没有终止 worker、没有新增 Mplus。等待后重新绑定同一会话，短 native ping 恢复。这是观测到的先后关系；现有证据没有唯一证明内存耗尽、R 崩溃或 ClaudeR 缺陷，也没有区分等待与重绑各自的恢复贡献。

## 恢复顺序

1. 停止新的提交和重试；保留原 job id。
2. 读取精确路径的 BOOT_PID、PROGRESS、engine_receipt、model.out、结果文件和 reservation。
3. 用有界 tasklist 过滤（例如只查 Mplus.exe）确认目标进程，不做全盘递归扫描或无界进程枚举。
4. 先 list_sessions，再 connect_session 到原会话；用短 execute_r 标记验证 native 通道。
5. 只有 durable 证据证明 worker 已终态且没有目标进程，才关闭或恢复 guard；不能因 API 返回空白就重提。
6. 若 native 仍不通，HTTP 仅作为 Addin 存活诊断，不能冒充 native MCP 成功；恢复后继续轮询原 job。

## 工程约束

长任务使用 execute_r_async 和 local=TRUE，阶段信息写入 clauder_progress 与 PROGRESS.jsonl。任何前台诊断都应有时间上限和输出上限。恢复回执必须记录会话、PID、marker、是否重启 R、是否终止 Mplus、是否重提；没有这些证据时不得报告“接口修复”或“模型继续运行”。

## 本次接续确认与跨平台边界

- 2026-10-22 的新原生 list_sessions 和 execute_r 再次确认原 8787 会话可用；这证明当前短调用健康，不能回填成前一批 HTTP 发起子进程的原生异步证据。
- Windows Python 接受 `C:/...` 路径，WSL 文件工具接受 `/mnt/c/...`；不要把后一种路径传给 Windows Python。执行 R 脚本前用实际 runtime 的 `file.exists` 核对完整路径。
- 将多行 R/Python 代码写入文件再执行。避免嵌套 shell 引号吞掉 R 的 `$`、将 `\\n` 当成字面量，或把 `JSON.stringify()` 当 shell 转义。
- WSL `gh` 未登录不证明 Windows 没有凭据。先分别查看原生 `gh auth status`，再用已授权的原生凭据帮助器执行 Git 操作；不要把令牌打印出来、复制到配置或要求用户重复登录。
- `.libPaths()` 改变后，记录实际已加载 namespace 的版本与路径。配置指向新库不等于当前 namespace 已升级；加载中的包不能被静默替换。当前 1.3 是本机已验证版本，不是其他环境的普遍最低门槛。
