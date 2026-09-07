# ClaudeR 架构说明与 `clauder-rstudio-workbench` 使用指南

> 适用版本：`clauder-rstudio-workbench v0.6.1`、ClaudeR `0.14.1.9002`
>（公开配套标签 `v0.14.1.9002-lzhs.1`）、`clauder-mcp 0.14.5.post1`。
>
> 本文是当前权威指南。2026 年 5 月的 Windows 初创手册已保留为历史证据，
> 但其中的版本、路径和 `uvx` 建议不再代表当前推荐配置。

## 连接排障补充（2026-09-07）

`doctor PASS` 只表示配置与 discovery 检查通过，不代表当前 agent 已加载原生工具。
新增诊断命令逐层区分终端、配置、bridge、活跃 RStudio 和 agent 工具：

```text
clauder-workbench connection-diagnose --session-name <实际会话名> --probe-http
```

该命令只做标记执行和 PID 核对，不拟合模型、不改研究对象、不提交异步任务。
HTTP 必须命中明确的 discovery 会话、使用对应认证并收到成功执行标记；错误正文非空不能算成功。
独立 MCP 通道可用时返回 `MCP_STDIO_OK`，诊断总体仍为 `WARN/2`，
`native_gate=NOT_VERIFIED`；这不是原生发布门禁通过。

当前工具列表缺少 r-studio 不能推出 RStudio 停止。先核查工具暴露、有效配置与实际进程，
没有证据时不得断言配置写入者或“注册表冻结”。没有可用的热加载接口也不能虚构调用。
交互式 Codex 启动必须保留 stdin/stdout/stderr 的终端属性；`rtk proxy` 等输出捕获层
只用于非交互检查。脚本语法检查及 `mcp get` 成功不等于交互启动验证通过。

## 2026-09-07 治理状态补充

v0.6.1 把此前的定点诊断补丁纳入维护来源，并增加统一就绪检查、原子配置合并、公开配套来源和进程绑定原生证据。本轮 Codex 原生四步调用已在既有 RStudio 会话实测通过，包含异步完成前的阶段进度；这不证明此前配置丢失的未知写入者已找到，也不代表所有 GUI 客户端生命周期均已实测。发布状态以对应 GitHub Release 为准。

三仓依赖、fork 分支与本机版本差异、Windows—Mac 故障台账及剩余整改见同目录的《ClaudeR_教程审查与SKILL设计建议》。用户已因 Claude 欠费授权 Codex 独立接管，不再等待或调用 Claude；测试及发布门禁仍保留。不要为“恢复工具”重启现有研究会话。

新的统一入口（默认只读）：

```text
clauder-workbench ensure-ready --client codex --session-name <实际会话名> --task-key <任务名>
```

正式原生任务在真实四步 smoke 后追加 `--require-native --native-evidence <证据文件>`。
门禁核对当前客户端进程/session、配置哈希、目标 R PID 和四步归档原文哈希；同一 thread
在新进程中恢复也必须重新验证。`--client claude|copilot` 使用对应配置文件，项目级配置用
`--config-file` 显式选择；“读到了文件”不等于证明宿主采用了它。
`--repair safe` 只定点合并已有持久入口，不安装新版本、不启动 agent、不重启 RStudio，
不抹掉禁用状态、其它 MCP、自定义参数/env。未知锁和损坏 discovery 保留待核查。

安装与实际加载必须分开检查：`getNamespaceVersion("ClaudeR")` 是当前 R 进程版本，
`packageVersion("ClaudeR")` 是磁盘版本。已有健康研究进程可能继续持有旧 namespace；
不要为对齐版本号而终止它。MCP 的新磁盘入口也不证明已运行的 bridge 自动热换版。
`$clauder` 仅作薄别名；用安装器 `--sync-clauder-alias`（Windows `-SyncClaudeRAlias`）
备份并同步该兼容入口，连接规范只维护在核心 skill 中。

宽表遇到密度阻断时，先检查列数与比较项，再在独立 spec 副本中显式设置横向/字号；
不要删检验列以凑验收，也不要自动改论文原规格。一次 15 列面板表实测需要横向 9.5 磅，
版式调整后仍须复核展示值、原始统计值和三线边框。

## 1. 先看结论

`clauder-rstudio-workbench` 不是 ClaudeR 的替代品，也不是统计分析包。它是
ClaudeR/RStudio 控制链外面的可执行治理层，负责连接检查、异步任务身份、
多 worker fan-out、资源门禁、进度证据、监控和正式完成判定。

```text
Codex / Claude Code / Copilot
              │ native MCP wrapper 或 MCP stdio
              ▼
        clauder-mcp bridge
              │ 本机 HTTP + discovery
              ▼
       ClaudeR RStudio Addin
              │
       RStudio 主会话 / 子 R worker

clauder-rstudio-workbench：在控制链两侧执行 doctor、guard、fan-out、monitor、gate
```

最重要的操作原则只有四条：

1. 短任务用 `execute_r`，长任务只提交一次 `execute_r_async`。
2. 一直使用首次返回的同一个 `job_id` 轮询；`running` 不等于失败。
3. 正式长任务必须把进度和结果写入持久文件，不能只依赖 MCP 返回文本。
4. “R 计算结束”不等于“整个工作流通过”；科学验证、归档和完成门禁必须分别检查。

## 2. 组件职责与边界

| 组件 | 负责什么 | 不负责什么 |
|---|---|---|
| RStudio | 交互式 R 会话、项目和 Addin 宿主 | 不提供跨任务证据门禁 |
| ClaudeR R 包 | 会话发现、执行 R、异步 job、进度、研究工具 | 不替代外部 fan-out/归档治理 |
| `clauder-mcp` | 把 ClaudeR 能力暴露为 MCP 工具 | 不把 stdio 自动升级成 Native 证据 |
| workbench skill | 告诉 agent 如何安全选择和组合工具 | Markdown 本身不是完成证据 |
| workbench harness | doctor、async guard、fan-out、资源门禁、monitor、completion | 不判断具体统计模型是否科学正确 |
| `cmaverse-paired-mval` | paired bootstrap、Delta CDE、CMAverse 科学验收 | 不负责通用 MCP 连接或百度客户端 |
| `comparegroups-guide` | 描述统计、标签审计、面板双轨表、三线 DOCX 和数值核验 | 不替代纵向模型或 ClaudeR 执行层 |
| tmux/caffeinate | macOS/POSIX 长任务的可选后台托管壳 | 不是 ClaudeR、RStudio 或 MCP 的组成部分 |

百度网盘、S3 或其他归档器属于工作流消费者。只有接口、失败语义和验证逻辑经过
通用化后，才应进入 workbench 核心。

## 3. 当前兼容矩阵

| 层 | v0.6.1 推荐值 | 验证方式 |
|---|---|---|
| workbench | `0.6.1` | `clauder-workbench --version` |
| ClaudeR | `0.14.1.9002` / `v0.14.1.9002-lzhs.1` | 磁盘 packageVersion 与当前 getNamespaceVersion 分别核对 |
| upstream 基线 | ClaudeR `0.14.1` | 安装元数据与源码提交 |
| MCP bridge | `0.14.5.post1` | 精确标签、manifest、安装元数据及已加载进程分别核对 |
| MCP 工具面 | 5 个核心执行能力；其余按用途 | ensure-ready 报告必需缺失与可选缺失，保留完整工具清单 |
| evidence schema | `0.2.4` | packaged schema |
| macOS/Linux | `install.sh` | installer/doctor 测试 |
| Windows | `install.ps1` | PowerShell 和跨平台回归测试 |

不要使用裸 `uvx clauder-mcp` 或裸 `uv tool install clauder-mcp` 作为稳定入口。
它们可能解析到未固定的 PyPI/upstream 版本，丢失本地 fork 的兼容改动。

## 4. 安装与升级

### 4.1 macOS/Linux

```bash
git clone --branch v0.14.1.9002-lzhs.1 --single-branch https://github.com/lzhs1995/ClaudeR.git \
  "$HOME/projects/ClaudeR-v0.14.1.9002-lzhs.1"
git clone --branch v0.6.1 --single-branch https://github.com/lzhs1995/clauder-rstudio-workbench.git \
  "$HOME/projects/clauder-rstudio-workbench-v0.6.1"
cd "$HOME/projects/clauder-rstudio-workbench-v0.6.1"

./install.sh \
  --clauder-dir "$HOME/projects/ClaudeR-v0.14.1.9002-lzhs.1" \
  --configure-codex \
  --sync-agents-skill \
  --backup-retention 0

"$HOME/.local/bin/clauder-workbench" doctor \
  --expect-client codex --check-toml-parse
```

`--backup-retention 0` 表示保留全部 skill 备份。安装器只有在显式指定
`--configure-codex`、`--configure-claude` 等开关时才修改客户端配置。
clone 目标必须不存在；已有工作树不要覆盖，先核对其精确标签和未提交修改。
安装器在替换 R/bridge 前验证 runtime-compatibility.json；不要以任意 fork main 代替配套引用。

推荐 Codex 配置形态：

```toml
[mcp_servers.r-studio]
command = "/Users/<USER>/.local/bin/clauder-mcp"
startup_timeout_sec = 180.0

[mcp_servers.r-studio.env]
HOME = "/Users/<USER>"
PYTHONIOENCODING = "utf-8"
NO_PROXY = "127.0.0.1,localhost"
UV_CACHE_DIR = "/Users/<USER>/Library/Caches/uv"
```

### 4.2 Windows

```powershell
git clone https://github.com/lzhs1995/clauder-rstudio-workbench.git `
  "$env:USERPROFILE\projects\clauder-rstudio-workbench"
Set-Location "$env:USERPROFILE\projects\clauder-rstudio-workbench"

powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -ConfigureCodex -SyncAgentsSkill

& "$env:USERPROFILE\bin\clauder-workbench.cmd" doctor `
  --expect-client codex --check-toml-parse
```

Windows 使用持久的 `clauder-mcp.exe`、`USERPROFILE` 和 Windows uv cache。
不要把 macOS 路径照搬到 Windows。v0.2.4 以后配置写入统一使用 UTF-8 no-BOM，
能够保留包含中文的 Codex project 路径。

### 4.3 RStudio 侧

在需要控制的 RStudio 会话中启动：

```r
library(ClaudeR)
claudeAddin()
```

修改 ClaudeR 包、bridge 或 MCP 配置后，重启相应的 Addin/MCP 客户端。
正在运行的 agent 不一定能热加载新增 wrapper。

## 5. 连接与 Native smoke

有多个 RStudio 会话时必须显式选择目标：

```text
list_sessions
connect_session(session_name = "analysis-main")
execute_r(code = "cat(Sys.getpid(), '\\n')")
```

正式 Native 工作必须完成当前 agent 工具层的四步 smoke：

```text
list_sessions
  → execute_r（返回唯一 marker 和 PID）
  → execute_r_async（返回 job_id）
  → get_async_result（使用同一 job_id 返回完成 marker）
```

先创建 evidence 状态，再把四个真实 wrapper 原始返回逐项登记：

```bash
clauder-workbench native-smoke start \
  --task-key <TASK_KEY> --session-name <SESSION> \
  --agent codex --require-raw-file

# 调用真实 wrapper，把每步原始返回保存为 raw 文件，再执行 record。
clauder-workbench native-smoke complete --task-key <TASK_KEY>
```

只有 `native-smoke complete` 生成的 `NATIVE_MCP_OK` 才证明当前 Codex wrapper。
Python MCP stdio、HTTP 或 `Rscript` 均不能冒充它。

## 6. 同步、异步与可见进度

### 6.1 何时用异步

```text
预计 <25 秒且输出小  ──→ execute_r
预计 ≥25 秒或可能阻塞 ──→ execute_r_async
多个独立长任务        ──→ fan-out + durable files
需要 60–90 分钟鉴定   ──→ fan-out + soak-monitor + completion-check
```

异步任务的正确序列：

```bash
clauder-workbench async-guard pre-submit \
  --task-key <TASK_KEY> --session-name <SESSION> \
  --transport-scope native-wrapper --io-mode durable_files \
  --code-file /absolute/path/worker.R

# 仅调用一次真实 execute_r_async，取得 JOB_ID。

clauder-workbench async-guard register-job \
  --task-key <TASK_KEY> --job-id <JOB_ID>
```

随后只轮询 `<JOB_ID>`：

```text
get_async_result(job_id = "<JOB_ID>")
```

R worker 应主动发出阶段信息：

```r
for (i in seq_len(nboot)) {
  # bootstrap work
  if (i %% 100 == 0L) {
    clauder_progress(
      stage = "bootstrap",
      message = sprintf("rep=%d/%d", i, nboot)
    )
  }
}
```

`running`、一次连接重置或一次轮询超时都不是重提理由。先检查持久 state 是否继续更新；
只有 bridge 明确返回 job error/cancelled/not-found，才视为 terminal failure。

## 7. 四层进度到底来自哪里

| 层 | 数据源 | 能回答的问题 |
|---|---|---|
| ClaudeR job | `get_async_result`、`clauder_progress()` | 该 job 是否在跑、目前处于什么阶段 |
| workbench fan-out | `fanout_runtime_status.json`、`FANOUT_PROGRESS` | 哪些原 job 已完成/运行/等待/失败 |
| soak monitor | checkpoint、resource、heartbeat、state-progress | 资源和链路是否持续满足 SLA |
| Codex 自动 heartbeat | 定时读取上述持久状态并向用户报告 | 用户无需守着终端也能看见综合进展 |

因此，定时出现在 Codex 对话中的中文进度报告通常是外层自动化读取 workbench
产物后生成的；它不是 ClaudeR 内建消息。真正的任务阶段来自 worker 写入的 state
和 `clauder_progress()`，两者不能混为一谈。

## 8. Parallel async fan-out

每个 worker 至少产生：

```text
state_<id>.json       # 状态、阶段、进度、错误
manifest_<id>.csv     # 文件、哈希、大小、时间
validation_<id>.csv   # 语义/科学断言
```

合同示例：

```yaml
task_key: analysis_20260905
max_parallel: 2
requires_native_smoke: true
require_resource_gate: true
resource_gate_max_age_min: 120
require_soak_monitor: true
soak_monitor_max_age_min: 120

artifacts:
  output_root: /absolute/run/main
  max_age_h: 24

resource_gate:
  memory_scale_up_percent: 80
  memory_hold_percent: 85
  cpu_scale_up_percent: 75
  cpu_hold_percent: 90
  min_disk_free_gb_scale_up: 200
  min_disk_free_gb_hold: 150
  upload_backlog_hold: 2
  healthy_samples_for_scale_up: 5

workers:
  - id: w01
    code_file: /absolute/run/worker.R
    expected_state: state_w01.json
    expected_manifest: manifest_w01.csv
    expected_validation: validation_w01.csv
```

执行链：

```bash
clauder-workbench worker-lint --contract task.yaml
clauder-workbench fanout-plan --contract task.yaml \
  --parent-evidence <NATIVE_SMOKE_PASS.json>

clauder-workbench fanout-run --contract task.yaml \
  --transport mcp-stdio --max-parallel 2 --max-parallel-cap 3 \
  --auto-scale --memory-scale-up-percent 80 --memory-hold-percent 85 \
  --cpu-scale-up-percent 75 --cpu-hold-percent 90 \
  --healthy-samples-for-scale-up 5

clauder-workbench fanout-poll --contract task.yaml
clauder-workbench merge-gate --contract task.yaml
```

`fanout-run` 的实际传输是 MCP stdio，证据必须标记 `MCP_STDIO_OK`。Native fan-out
则由 agent 对每个 worker 执行真实 `execute_r_async`，登记 job ID 后使用
`fanout-poll`。workbench 不会把两种传输混写。

自动扩容只影响“是否提交下一个 worker”。达到 hold 阈值时，已经在跑的 worker
自然完成，不应为了降并发而杀死它们。

## 9. 长时间监控与 tmux

`soak-monitor` 独立采样 CPU、内存、磁盘、RStudio PID/端口、durable state 和 MCP
heartbeat。它按单调时钟安排槽位，记录 planned/observed/missed、延迟、gap、重启和
violation，并通过原子 checkpoint 恢复受监督的采样子进程。

macOS 正式长任务可使用：

```bash
tmux new-session -d -s "clauder_soak_<RUN_ID>" \
  "caffeinate -dimsu clauder-workbench soak-monitor run \
   --contract /absolute/run/task.json \
   --evidence-dir /absolute/run/monitor \
   --expected-pid <RSTUDIO_PID> --port 8788 \
   --stop-file /absolute/run/monitor/STOP"
```

这是防止 Codex 前台命令结束或电脑休眠带走 monitor 的托管方式：

- tmux 不是 ClaudeR 的依赖。
- Windows 可以使用计划任务、服务或保持终端运行，不要求安装 tmux。
- 短任务不需要 tmux。
- 正式运行中外层 monitor 在 STOP 前消失，应如实 BLOCK；不要用外部 `--resume`
  把不连续运行包装成连续运行。

worker 全部终态且持久产物完整后，才创建 STOP 并等待 monitor 自行生成 summary。

## 10. 四类传输证据

| 类别 | 能证明什么 | 不能证明什么 |
|---|---|---|
| `NATIVE_MCP_OK` | 当前 agent 注册的原生 wrapper 四步可用 | 不能由 Python 手写或补造 |
| `MCP_STDIO_OK` | 配置中的 `clauder-mcp` 可经 stdio 调用 | 不能证明当前 Codex wrapper 已注册 |
| HTTP fallback | RStudio Addin HTTP 服务仍存活 | 不能证明 MCP/native 可用 |
| `Rscript` | 离线 R 包、语法或算法可运行 | 不能证明 RStudio、Addin 或 MCP |

`--defer-native-smoke` 只允许 compute-first：它必须真实完成 MCP stdio probe，证据
标记 `NATIVE-SMOKE-DEFERRED`，而正式 `completion-check` 仍会因缺少 Native 证据阻塞。

## 11. 常见故障和恢复顺序

### 11.1 `Transport closed`

1. 运行 `doctor --expect-client codex --check-toml-parse`。
2. 核对 persistent `clauder-mcp` 路径、180 秒 timeout 和 uv cache。
3. 确认 RStudio Addin、discovery PID 和端口仍存活。
4. 重新执行当前工具层 Native smoke。
5. 已经提交的 worker 只检查原 job ID 和 durable state，不重提。

### 11.2 verbose async job 停在运行中

ClaudeR `0.14.1.9001` 把 async stdout/stderr 写入临时文件，避免未消费 pipe 填满。
旧 ClaudeR 已经启动的 job 可使用：

```bash
clauder-workbench async-io-rescue run \
  --runtime-status /absolute/run/fanout_runtime_status.json \
  --session-name <SESSION> --evidence-dir /absolute/run/evidence
```

rescue 只跟踪状态文件里已有的原 job ID，不提交、不取消、不恢复 job。

### 11.3 Windows 多会话

不要使用把 `tools::pskill(pid, signal = 0)` 当成 Windows 存活探针的旧 ClaudeR。
它可能伤害仍存活的 RStudio 会话。当前 fork 使用只读 PID 检查。

### 11.4 worker 文件存在但任务仍不能 PASS

依次核对：

1. state 是否为 `complete`；
2. manifest 的哈希是否与真实文件一致；
3. validation 是否全部 TRUE；
4. 原 job ID 是否 terminal；
5. merge-gate、monitor 和正式 completion-check 是否都 PASS。

## 12. 正式完成门禁

```bash
clauder-workbench completion-check \
  --mode formal --task-key <TASK_KEY> --contract task.yaml \
  --require-native-smoke --native-smoke-max-age-min 120 \
  --require-preflight \
  --require-resource-gate --resource-gate-max-age-min 120 \
  --require-soak-monitor --soak-monitor-max-age-min 120 \
  --require-transport-class NATIVE_MCP_OK \
  --transport-class NATIVE_MCP_OK \
  --state-file /absolute/run/merged_state.json \
  --parent-evidence <NATIVE.json> <PREFLIGHT.json> <RESOURCE.json> \
                    <FANOUT.json> <MERGE.json> <MONITOR.json>
```

稳定退出码：

| code | 含义 |
|---:|---|
| 0 | PASS |
| 2 | WARN |
| 3 | BLOCK |
| 4 | TRANSPORT_UNSTABLE |
| 5 | CONTRACT_FAILED |

资源、monitor 或归档失败时，已经完成的科学结果仍应保留，但不能追溯性改判为全绿。

## 13. ClaudeR 41-tool surface

### 执行与会话（12）

`list_sessions`、`connect_session`、`get_r_info`、`execute_r`、
`execute_r_async`、`get_async_result`、`cancel_async_job`、
`execute_r_with_plot`、`get_active_document`、`read_file`、`get_viewer_content`、
`get_session_history`。

### 研究工作流（13）

`annotate`、`cancel_annotation_job`、`get_annotation_job_status`、
`load_annotation_data`、`run_annotation_job`、`check_cross_references`、
`reconcile_values`、`verify_references`、`search_citations`、`get_bibtex`、
`generate_codebook`、`generate_notebook`、`screening_report`。

> 注：工具面以 `clauder-workbench tool-surface` 的实时结果为准。完整调用参数由 MCP
> schema 提供；本文按工作流分组，不复制可能随 ClaudeR 更新的全部 JSON schema。

### 多 agent 协调（7）

`set_agent_name`、`send_message`、`check_messages`、`wait_for_message`、
`coordination_roster`、`create_task_list`、`update_task_status`。

`set_agent_name` 固定连接身份；`as_agent` 是在支持它的单次协调调用中选择 persona，
不会重新命名整个连接。`wait_for_message` 用于 agent 消息，不用于等待 R async job。

### 编辑、诊断与恢复（9）

`checkpoint_session`、`list_checkpoints`、`restore_session`、
`clean_error_log`、`probe_scripts`、
`search_project_code`、`modify_code_section`、`insert_text`、`suggest_edit`。

ClaudeR 还提供 Coordination/consensus、系统综述/PRISMA、Grant Panel、Response to
Reviewers、DOCX 注释、引用和 notebook 等高级工作流。使用前应先查看当前 ClaudeR
版本的 prompt/schema；不得把外部 citation 服务超时写成本地功能 PASS。

## 14. CMAverse paired-mval 案例

该案例验证了一台 RStudio 会话可以驱动多个独立 R worker，并持续产出可合并的
统计和归档状态：

- `cmaverse-paired-mval` 规定一次 bootstrap 同时计算 M=0/M=1，并验证共享
  bootstrap hash、完整 `cmest` child 和 Delta CDE。
- workbench 负责 job 身份、fan-out、CPU/内存/磁盘 admission、轮询、monitor 和
  evidence gate。
- 百度客户端适配器负责上传、回下载和哈希复验；它不是 workbench 核心。

2026-09-02 的 `nboot=100` 全量检验结果：

| 项目 | 结果 |
|---|---|
| mediator × group | 7 × 25 = 175 |
| 科学验证 | 175/175 PASS |
| worker | 7 个唯一原 job ID，均无重复提交 |
| 百度远端往返并安全删除 | 114/175 |
| 未删除本地分片 | 61/175 |
| 归档阻塞原因 | 百度客户端出现两个 main renderer，CDP 适配器无法唯一选择 |
| monitor | BLOCKED：存在 missed slot、state gap 和一次 restart |
| 可声明结论 | 计算与科学验证 PASS；完整归档链不是 `FORMAL_ALL_PASS` |

这次事件同时证明了 compute-first 解耦是必要的：归档消费者失败不应停止仍在运行的
bootstrap；但上传未通过独立回下载哈希验证时，也绝不能删除本地 RDS。

### 14.1 compareGroups Guide：描述统计三线表

`comparegroups-guide` 是第三个并列 skill。它把自然语言制表需求沉淀为
`table-spec.json`，由官方 `compareGroups` 负责统计计算，由 ClaudeR 负责读取旧脚本、
检查标签、生成合同、执行/异步轮询、读取 DOCX 和复核论文数值。

固定流程：

```bash
Rscript skills/comparegroups-guide/scripts/check_dependencies.R
Rscript skills/comparegroups-guide/scripts/audit_input.R \
  --spec /absolute/path/table-spec.json \
  --output /absolute/path/input-audit.json
Rscript skills/comparegroups-guide/scripts/run_comparegroups.R \
  --spec /absolute/path/table-spec.json \
  --output-root /absolute/path/new-results
Rscript skills/comparegroups-guide/scripts/validate_comparegroups.R \
  --output-root /absolute/path/new-results --stem Table_1
```

v0.6.0 的 `spec_version=1.1` 在不破坏 1.0 的前提下增加默认精度、显式分组
标签/参照、`hide_no`、有序 subset variants、自动 attrition 和 DOCX 样式。不同
group 的独立合同使用一个 batch manifest 一次提交：

```bash
Rscript skills/comparegroups-guide/scripts/run_comparegroups_batch.R \
  --manifest /absolute/path/batch-manifest.json \
  --output-root /absolute/path/new-batch-results
Rscript skills/comparegroups-guide/scripts/validate_comparegroups_batch.R \
  --output-root /absolute/path/new-batch-results
```

输出同时包含三线 DOCX、展示 CSV、未格式化数值长表、原始
`compareGroups/createTable` RDS、输入/标签/方法/版本元数据、结构化 validation、
manifest 和 `SHA256SUMS.txt`。论文叙述必须以数值长表为准，DOCX 只负责展示。

v0.6.1 加强正确性门禁：`n_available` 只来自真实全样本/分组列，不能把
`Fact OR/HR` 等辅助字段当成样本量；数值行按原变量身份映射，允许显示标签重复。
独立复验从保留的 RDS 对象重建数值和展示内容进行核对，并要求完整的 validation
检查集合；“CSV 行数相同、所有剩余检查为 TRUE、重算哈希一致”不能代替内容核对。

个人做表规范已经固化：连续正态变量为“均值（标准差）”并保留 3 位小数，偏态变量
为“中位数 [Q1, Q3]”并保留 3 位小数，分类变量为“n（%）”且比例保留 2 位；
`[ALL]` 显示为“全样本”，`p.overall` 显示为“p-value”；变量按被解释变量、解释
变量、中介/调节变量、个体、父母、家庭、混杂因素等区块排列。

对于 Stata 数据，优先保留变量标签和值标签；数值型无标签分类变量必须在合同中显式
给出编码、显示标签和参照水平。声明的 ID/time 不得缺失，同一 person-wave 不得重复；
不能将重复 ID 行声明为独立横截面，也不能自动去重来通过门禁。真正跨波次重复观测时，`panel_mode: dual`
会生成安全主表和兼容 pooled 表：正式主表按波次输出，或隐藏不成立的 pooled p 值；
兼容表保留旧结果，但必须携带“普通 t/卡方检验假设独立行”的限制说明。删除/保留样本
比较必须在删除记录前构造状态，并以基期一人一行为正式分析单位。
所有自动波次表与显式 subset variants 使用相同的非空/声明分组完整性检查；显式
`pooled_compatibility` 也必须保留非独立性警告，不能冒充正式推断主表。

这仍不替代研究设计审查、原始数据核对和最终 DOCX 视觉验收。OOXML 真三线通过不等于
中文字体、列宽、分页均合格；RDS 内容核对也不是对所有产物协同篡改的安全防护。
合同中的 subset 是受信任的 R 表达式，不是安全沙箱，执行前必须审阅。

单张小表用 ClaudeR `execute_r`；大型 `.dta` 或多表 DOCX 批处理只提交一次
`execute_r_async`，再使用同一个 job ID 轮询
`preflight → import → labels → compute → render → validate → complete`。只有多个真正
独立的表格合同时才使用 workbench fan-out。

## 15. 已完成的关键验收

### v0.4.2 Native 70 分钟全绿浸泡

- 8 个 worker，各持续约 4200 秒，8 个唯一 job ID。
- detached tmux monitor 连续运行约 4503 秒，无外部 resume。
- resource 151/151、heartbeat 76/76，成功率 100%。
- heartbeat p95 约 1.08 秒、最大 gap 约 60.37 秒、restart 0。
- 8/8 canonical RDS 原始 SHA-256 及固定统计量与 stdio 基线完全一致。

这证明 workbench 核心长任务链可以取得全绿，但不意味着所有外部消费者都天然可靠。

### ClaudeR 0.12.2 新功能复验

- 本地核心功能、Native smoke、跨重启历史、60 秒异步、Codebook 修复和 strict
  completion 均 PASS，结论为 `CORE_PASS`。
- Citation 外部网络服务仍为 `BLOCKED_EXTERNAL`，因此未写成 `ALL_PASS`。
- 后续 v0.4.5/v0.4.6 已把兼容目标升级到 ClaudeR 0.14.1/bridge 0.14.5。

### v0.5.0 compareGroups skill collection 扩展

- 新增第三个并列 skill `comparegroups-guide`，不把统计计算误写成 ClaudeR 内建能力。
- 引入独立 `spec_version=1.0` 的表格合同；workbench evidence schema 仍为 `0.2.4`。
- 用真实三线 DOCX、数值长表、RDS、元数据、validation、manifest 和哈希组成可核验交付。
- 公共仓库只包含合成数据和去标识模板；私人 `.dta`、变量清单和实证结果只在本机验收。

### v0.6.0 compareGroups 工作流升级

- 1.0 合同继续可运行；1.1 将默认值解析来源、分组映射和规范化合同写入 metadata。
- 自动 attrition 先识别随访是否出现，再严格选取每人唯一基期行；重复基期和空组硬阻断。
- 有序 variants 与 batch manifest 减少生命周期、性别、年份和样本选择表的重复配置。
- validation 增加 expected/actual/detail，DOCX 增加样式控制但继续强制真三线和无竖线。
- 本机固定 compareGroups 4.10.2，CI 同时门禁 4.10.2 与 4.10.3。

## 16. 一页式速查表

| 目的 | 命令/工具 |
|---|---|
| 检查安装 | `clauder-workbench --version` |
| 配置与 provenance | `doctor --expect-client codex --check-toml-parse` |
| 检查工具面 | `tool-surface` |
| 当前会话 | `list_sessions`、`connect_session` |
| 短 R 代码 | `execute_r` |
| 长 R 任务 | `async-guard` + `execute_r_async` + 同 job ID 轮询 |
| 多 worker 计划 | `worker-lint`、`fanout-plan` |
| MCP stdio fan-out | `fanout-run --transport mcp-stdio` |
| Native fan-out | Native submit + `register-job` + `fanout-poll` |
| 实时汇总 | `fanout_runtime_status.json`、`FANOUT_PROGRESS` |
| 资源准入 | `resource-gate advise/enforce` |
| 长时间监控 | `soak-monitor run/status` |
| 旧 async pipe 救援 | `async-io-rescue run/status` |
| 合并前门禁 | `merge-gate` |
| 正式完成 | `completion-check --mode formal` |
| 描述统计输入审计 | `$comparegroups-guide` + `audit_input.R` |
| 三线表生成 | `run_comparegroups.R --spec ... --output-root ...` |
| 三线表独立复验 | `validate_comparegroups.R --output-root ... --stem ...` |

## 17. 版本管理与贡献

1. 在独立干净分支开发，不在含用户未提交修改的工作副本上覆盖文件。
2. 先运行单元测试、skill validation、doctor、tool surface 和真实 Native smoke。
3. PR 中区分本地测试、Native、MCP stdio、外部服务和历史证据。
4. 合并后再打 annotated tag；Release asset 由 `git archive` 生成并发布 SHA-256。
5. 禁止把 token、discovery secret、用户路径、研究数据或大型 RDS 提交到 Git。
6. 永久禁止在 VPS/生产服务器 build；只允许本机或 GitHub Actions 构建不可变产物。

版本历史详见 [Windows 初创与迁移摘要](history/2026-05-windows-origin.md) 和仓库
`CHANGELOG.md`。
