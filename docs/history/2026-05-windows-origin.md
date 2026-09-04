# 2026 年 5 月 Windows 初创与迁移摘要

本文是公开、去隐私的历史摘要。原始 Windows 开发手册约四千余行，包含本机路径、
逐次排障记录和研究工作流上下文，因此只在维护者本地按原 SHA-256 保存，不直接
原样发布。

## 起点

2026 年 5 月，`clauder-rstudio-workbench` 最初用于解决 ClaudeR 在 Windows 上的
三个实际问题：

1. 长异步任务只能看到 `running`，看不到 bootstrap 阶段和业务进度。
2. 多 RStudio session 和多 agent 可能连接错会话或重复提交任务。
3. Windows discovery 清理若错误使用具有副作用的 PID 探针，可能伤害仍存活会话。

最初的 fork 因此加入异步 progress sidecar、并行任务元数据、Copilot 支持和
Windows 只读 PID 存活检查。workbench 则把这些能力写成可复用的运行纪律。

## 从文档规范到可执行门禁

| 版本 | 主要变化 |
|---|---|
| v0.1.0 | Windows-first 安装器、异步进度、多 session 安全和 MCP 边界 |
| v0.2.1 | doctor、preflight、async guard、resource/completion gate 和 evidence schema |
| v0.2.4 | UTF-8 no-BOM 配置写入，修复中文 Codex project 路径损坏 |
| v0.3.0 | skill collection、parallel fan-out、worker lint、动态并发和 CMAverse skill |
| v0.3.1–0.3.4 | Native smoke 原始证据、父证据链和 freshness 防伪 |

这一阶段形成的核心不变量延续至今：

- 一个逻辑 worker 只提交一次。
- `running` 只继续轮询原 job ID。
- 持久 state/manifest/validation 是事实源。
- HTTP 与 Rscript 不能冒充 MCP；MCP stdio 不能冒充 Native wrapper。
- 正式结论必须由可执行 completion gate 给出。

## macOS 迁移

2026 年 8 月迁移到 macOS 后，项目没有另起一套不可兼容实现，而是把 Windows
约束抽象成跨平台接口：

- `install.sh` 与 POSIX harness 复用相同 Python 核心。
- Windows 使用 `clauder-mcp.exe`，macOS 使用持久 `clauder-mcp`。
- macOS `psutil` 进程枚举异常被降级为非关键指标错误。
- detached tmux/caffeinate 只作为 POSIX 长任务的可选外层托管。
- fan-out、job identity、evidence schema 和退出码保持跨平台一致。

## CMAverse 对项目的推动

CMAverse paired-mval 项目要求同一 bootstrap 同时计算 M=0/M=1，并在多个 mediator
间并行。它推动了以下通用能力：

- N 个子 R worker 与原 job ID 轮询；
- `FANOUT_PROGRESS` 和原子 runtime status；
- CPU、内存、磁盘和上传积压 admission；
- 科学验证与归档验证分层；
- verbose async 输出文件化及旧 pipe rescue。

百度网盘 CDP 操作仍是任务专用适配器。其结果可以作为 workbench 的集成案例，
但在通用化前不属于核心产品接口。

## 当前维护原则

- 仓库 `docs/ClaudeR_架构说明与clauder-rstudio-workbench使用指南.md` 是当前权威指南。
- `SKILL.md` 保持可加载、可路由，不复制整本手册。
- `CHANGELOG.md` 记录实现变化；运行报告记录某次验收事实。
- 历史失败和 BLOCKED 结论永久保留，不因后续成功而追溯改判。
- Windows 与 macOS 共用行为合同，仅安装入口和外层进程托管方式不同。
