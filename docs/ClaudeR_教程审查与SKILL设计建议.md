# ClaudeR 教程审查与 SKILL 设计建议

审查日期：2026-09-07。本文是版本化审查与整改台账，不替代 Release 验收记录。
审查配对：workbench v0.6.1、ClaudeR 0.14.1.9002、bridge 0.14.5.post1。文中整改前基线和阶段证据均保留时间边界；部署状态须同时检查 Release、INSTALL_INFO 和当前原生证据。
协作状态：用户因 Claude 欠费明确授权 Codex 独立接管；不再调用 Claude，也不声称有本轮联合终审。

## 1. 三个仓库的关系与安装选择

| 仓库 | 职责 | 不能混淆的边界 |
|---|---|---|
| [IMNMV/ClaudeR](https://github.com/IMNMV/ClaudeR) | 上游 R 包、RStudio addin、Python MCP bridge | 是实际软件，不是单纯教程 |
| [lzhs1995/ClaudeR](https://github.com/lzhs1995/ClaudeR) | 上游 fork；分支承载兼容性补丁与扩展 | 不同分支不等价，不能只写“安装 fork” |
| [lzhs1995/clauder-rstudio-workbench](https://github.com/lzhs1995/clauder-rstudio-workbench) | 安装、诊断、执行/监控/验收程序，操作规范与科研 skill 集合 | 不是 ClaudeR 的 fork；也不只是 Markdown 手册 |

执行关系：agent → MCP bridge → ClaudeR addin → R/RStudio；workbench 为整条链提供约束和证据，领域 skill 提供科研流程。

三个 peer skills 分工：

- clauder-rstudio-workbench：连接、明确会话绑定、异步任务身份、进度、资源、监控和完成门禁。
- cmaverse-paired-mval：CMAverse 配套扩展与成对 M=0/M=1 分析/核验。
- comparegroups-guide：描述性统计、缺失/样本流失分析、标签、面板/重复横截面、三线表及输出合同。

### 1.1 “fork 只新增 Copilot”是否准确？

不准确。早期 Copilot 接入是其中一项，主要是 CLI 安装/配置适配，不是新增统计引擎。
本次远端核查中，feature/copilot-cli-support 相对 fork main 含五个提交，覆盖 Windows 安全 PID 检测、异步进度及 MCP 展示、回归测试和 Copilot 安装支持。

本机当前分支另有：

- 38f41de692d6801f003eb1f811a8bbcc7c4e5116：移植异步进度、codebook 与相关兼容修正。
- 50a14f05161a86750f45be66ae508635c4bce722：异步 stdout/stderr 背压修复，采用文件承接输出。

不能把多会话、PID 安全等所有能力永久归为 fork 独占；上游已陆续合并其中一些机制。每次升级应重新计算补丁差异。

### 1.2 当前应依赖哪个版本？

正式 workbench 工作流目前依赖已验收的配套 LZHS fork，而不是任意上游最新版，也不是 fork 默认 main。

| 对象 | 本次核查基线 |
|---|---|
| 上游 main | 8a3227179f0bd5b55fe7c8f080f2a719d37339e2；DESCRIPTION 0.15.0，含工具分组及绘图设置 |
| fork 默认 main | e736b458d25fbbe6f2352701b2d3bd2a207ebc2c；本次比上游落后 45 个提交 |
| 本机 ClaudeR | 0.14.1.9001；源码提交 50a14f05161a86750f45be66ae508635c4bce722 |
| 本机 MCP bridge | 0.14.5；配套 fork 构建 |
| workbench 已发布安装基线 | v0.6.0 / 60b358c67205db45cc9fb4a62e966e0298f3d04e，另有明确标记的本地诊断补丁 |
| workbench 候选基线 | 7d041e35adfd874c5a12e85dffc31760e6951bc9；工作树另有未提交整改 |

上表保留整改前基线，不代表新的安装推荐。原本仅本机维护的补丁线现已纳入
[fork PR #1](https://github.com/lzhs1995/ClaudeR/pull/1)。v0.6.1 的配套目标为
[v0.14.1.9002-lzhs.1](https://github.com/lzhs1995/ClaudeR/releases/tag/v0.14.1.9002-lzhs.1)，
精确提交 `73685a67f82ff42d4e257dc103e23d3ab6708fb4`，R 包 `0.14.1.9002`、bridge `0.14.5.post1`。
仓库 `runtime-compatibility.json` 锁定该组合；安装器在改变运行时之前验证关键源文件哈希，Git 来源另须匹配精确提交且保持 clean。ZIP 路线只声明关键文件验证，不冒充完整 Git 来源证明。

目标策略：优先兼容上游，保留最小必要补丁；用精确来源和能力矩阵选择运行时。上游通过全部必需能力测试之后，才将其列为可直接替代的安装选项。

## 2. 文档版本复盘

另一份使用指南已更新，不应再称其仍停留在 Windows 阶段。

- Windows 原始开发手册保留 4,236 行。
- 本轮修改前的当前使用指南为 602 行，主体对应 workbench v0.6.0。
- 与 GitHub main 的差异仅为开头新增 19 行“连接排障补充（2026-09-07）”。
- GitHub 指南变更包括 ed80c3ff4935cb60ffbccd4a0b717fb1a81a0c0a、e76b711c0b5cfeab14612cd478a8e4bc5d6b4a5c、6617e28804767f9a3942bd678cf112e20f9fe168。
- 本审查报告的旧版仍为 550 行，以五月源码为基线，含“建议创建 workbench skill”等已过时内容。旧版已先备份再更新。

维护原则：仓库 docs 维护通用文档，工作区原路径保存同步副本；私有运行证据留在本机。文件名保留历史日期不代表内容日期。正文必须同时给出审查日期、版本、提交和尚未完成项。

## 3. Windows 到 Mac：故障不是一个问题

“r-studio 加载失败”至少可能发生在配置、程序启动、协议、会话发现、会话身份、客户端注册六个环节。RStudio 活着不保证 agent 工具已注册；工具不在清单中也不能推出 RStudio 丢失。

| 编号 | 问题与证据 | 当前状态 | 整改/回归要求 |
|---|---|---|---|
| C01 | Windows 用 tools::pskill(pid, signal=0) 判断存活可误杀会话 | 当前上游和本机已有安全检测修正；旧构建仍危险 | Windows 开第二会话时第一会话必须存活；安装阻止危险源码 |
| C02 | HOME/USERPROFILE 指向 Documents，R 与 bridge 找不同 discovery 目录 | 历史已定位；当前 Mac 不能直接归因于此 | 跨平台路径解析、中文/空格目录、两端目录一致性 |
| C03 | 每次 uvx 解析/构建导致 MCP 冷启动超时 | 当前采用持久入口；历史根因有修复方案 | 正式入口不依赖开发目录临时构建；验证离线启动 |
| C04 | Windows 5 月 28 日：HTTP、独立 stdio 正常，Codex direct wrapper Transport closed | 历史已记录；与当前原生注册失败同类，尚不能证明同一根因 | 分离宿主注册、有效配置、传输和模型可见工具证据 |
| C05 | Mac 原生工具曾未暴露；配置曾缺失 r-studio 段 | 当前原生已验证；原始配置写入者和失效原因未查明 | 保留进程/配置/日志时间线，不能以本次恢复替代根因说明 |
| C06 | 交互式 resume 启动器经过输出捕获代理，stdout 不是 terminal | 本地前一轮定点修复及 6 项 PTY/stub 测试通过 | TUI 直接继承终端；不把 bash -n 当交互验收 |
| C07 | HTTP 错误正文非空即被认作成功、猜 8787、遗漏认证 | 本地诊断补丁已修复并测试；尚需正式发布 | discovery 精确选目标、认证、成功随机标记、禁止重定向 |
| C08 | discovery 直接写 JSON；解析异常立即删除 | 配套源码已修复，三平台 PID/双进程回归通过 | 原子发布记录；未知/损坏记录保留；不自动抢占未知锁 |
| C09 | 已绑定会话消失后自动选另一会话 | 配套 bridge 已改为身份失效报错，回归通过 | 明确重新绑定目标；不得向其他研究会话重试原代码 |
| C10 | 安装器重建 r-studio 配置块，未保留全部自定义项；缺并发保护 | 候选共用 config_store；8 项定向测试通过 | 禁用/参数/env/其它 MCP 保留；原子、锁、冲突检测、私有备份；不回滚覆盖外部新写入 |
| C11 | 固定 41 工具与上游可选工具组混用 | ensure-ready 采用核心能力集合；可选项另列 | 保留完整清单供审计，不把可选工具缺失当 RStudio 死亡 |
| C12 | native-smoke 用相对 raw_file，换 cwd 后无法 complete | 本轮实测复现，候选已修复，3 项定向测试通过 | 绝对定位归档副本、完成时复验哈希；不依赖源文件仍在原位 |
| C13 | 默认 main、实际安装、配套补丁和文档不同步 | fork 配套线已公开；工作台候选安装前强制配套检查 | 精确标签、来源/关键文件哈希、安装后验证；文档同步列入发布清单 |
| C14 | 本机 `$clauder` 兼容入口仍保留 Windows 路径、uvx 和无条件重启建议 | 已备份并改为薄适配，仓库提供同源模板和可选同步开关 | 核心协议只有一个维护来源；别名不能覆盖新版 workbench 的连接/证据策略 |
| C15 | 旧真实面板表 15 列，旧报告仅复验历史产物，未证明最终密度检查下可原样重新生成 | 本轮完整重跑复现：纵向 10 磅、横向 10 磅均被合理阻断；独立横向 9.5 磅副本通过 | 版式迁移必须显式记录，统计列/有效数值不变；不能用历史文件校验替代最终源码重跑 |

“Windows 阶段已经反复出错”的判断有依据。正确结论不是“所有旧 bug 都没修”，而是多类缺陷曾分别修过，但缺少覆盖真实客户端、升级迁移和版本来源的统一可靠性验收。

## 4. 本轮生产实际：恢复了什么，没有证明什么（按阶段保留）

2026-09-07 11:23–11:26 UTC，当前 Codex 实际暴露 41 个原生 r-studio 工具。

- list_sessions、connect_session、execute_r 成功。
- 绑定既有 basic-regression-independent-v1，R PID 61484；另一既有会话 PID 67906 仍存活。
- 单次提交异步 job 1e5188b3。24 秒时 get_async_result 返回 running，并有 Latest progress: stage=stage_5；之后原 job 完成 stage_7 / NATIVE_ASYNC_DONE。
- native-smoke PASS evidence_id：291181f5-8956-4940-a8ab-045f650ae062；包含四个原生步骤的原始结果与哈希链。
- 本轮没有重新启动 RStudio、取消研究任务或重复提交该异步任务。
- 当前 Codex PID 为 35361，启动于 15:52:29 IST；之前诊断的 PID 45422 已不在。本轮未实施这次进程切换。因此不能宣称“旧进程原位热加载已修复”。
- Codex 配置 SHA-256 仍为 cca37f6dcaf5a4d857fd1b97493153fe7a4943830d386952a09cad367c5d5382；本轮未修改。
- 候选修改前 Python 226/226；本轮候选完整回归 232/232，含新增 native 证据可移植性和安装默认值测试。Windows PowerShell 安装尚未实机验证。
- Claude 原会话已找到，但本轮请求持续重试，握手等待 600 秒后 HANDSHAKE_TIMEOUT；未派发执行任务，不计作共同复核。联合任务已解除活动标记，原会话保留。
- 本轮另将 macOS/Linux 的正式 harness 安装改为非 editable，Windows pip 安装也取消 -e；Linux 缓存使用 XDG/default .cache。Windows 缓存仍保留旧安装器契约，待成套迁移；没有升级现有安装。

以上是当前安装的现场恢复证据，不是未发布整改版本的安装验收，也不是 60 分钟稳定性或三平台真实客户端全部通过的证据。

### 4.1 独立接管后的新增验收

- 用户已撤销本任务的 Claude 协作要求；状态记录为 SOLO_TAKEOVER。上方握手失败是历史事实，不再是等待 Claude 的理由。
- 当前 workbench 完整 Python 测试 `259/259`；readiness 14 项、配置存储 9 项、配套来源 4 项，覆盖换进程恢复、错误 PID、配置改变、归档篡改、显式禁用、畸形参数及并发冲突。
- Windows 四个配置入口（Codex、Claude 用户文件、Copilot、workspace）已改为定点合并；新增 PowerShell 5.1/7 的实际函数执行测试，最终结论以 CI 为准。
- Windows 缓存已统一改为 LOCALAPPDATA/uv/cache；macOS/Linux/Windows 正式 harness 安装均不再默认 editable。
- fork `73685a6`：bridge 40/40、发现层 10/10、R CMD check、R 功能检查、Windows/macOS/Linux 双进程发现与异步背压回归均通过。首轮 Windows CI 的 `R` 命令被 PowerShell 解释成 Invoke-History，已改为显式 bash 执行 R CMD INSTALL；这不是 RStudio 失效。
- 独立 MCP 60 分钟持续连接测试已启动，明确标为协议新建/绑定/关闭/重连，不冒充新建或恢复真实 agent 会话。最终时长、样本数和原 PID 存活情况留在本机报告。
- 配置丢失时间附近，本 session 日志只显示只读工具调用；缺少进程级写文件审计，不能据此认定写入者。新日志只证明 workbench 自己的未来写入，不替未知历史行为补造因果链。
- 本机已安装新 R 包和持久 bridge。安装后的新 R 进程确实加载 0.14.1.9002；原研究 R PID 保留并继续运行已加载的 0.14.1.9001。INSTALL_INFO 明确只是来源声明及入口哈希，不能替代 namespace/已运行 bridge 版本证明。
- 新原生制表 job a6d3d73b 单次提交并完成，后台加载 0.14.1.9002，七阶段及面板三种输出通过。新四步证据 816b68ab-4dde-4f5c-b5a5-10b9a36ca8f5 被进程绑定 ensure-ready 接受；另一个独立进度测试 job 115186e9 在 10 秒时可见 stage_2，原 job 完成 stage_7。
- 五类真实数据以最终统计源码重新生成：显式采用横向 9.5 磅的面板规格副本后 50/50 通过，展示 CSV 和有效统计数值未变。原规格及两次密度阻断证据保留；不把版式修改说成完全原样复现。
- 通用修复已单独提交 [上游 PR #30](https://github.com/IMNMV/ClaudeR/pull/30)，基于 0.15.0 保留 plot_auto/tool_sets。移植版 bridge 37/37、发现层 11/11、R 功能与双进程回归通过，fork 分支三平台 CI 34125603582 通过；上游是否接受由维护者决定。
- config_store 的锁只协调采用同一协议的写入者，外部写入冲突检测是有限时间点检查，不是对任意不合作程序的系统级写入拦截。没有“未来任何程序都不可能删配置”的保证。

## 5. 旧教程的功能判断如何更新

| 主题 | 更新后的准确表述 |
|---|---|
| install_cli | 主要生成需要执行的 CLI 命令/配置；不能写成其必然自动完成一切配置；实际自动写入者要按函数和安装器区分 |
| 安装工具列表 | 按固定源码版本提取，不再把五月列表当“当前全部支持”；fork Copilot 与上游支持项分别说明 |
| execute_r 与图像 | 独立 execute_r_with_plot 仍存在；当前上游 execute_r 也会转交响应中的 plot 图片，是否捕获取决于 addin 设置/实际响应。不能继续写“必须调用前者才能看到图” |
| get_r_info | 返回 R 版本、有限对象摘要及包数量；不是完整包清单。检查具体依赖用 requireNamespace/packageVersion |
| 多会话 | 已有 list_sessions/connect_session；必须明确绑定，不能把默认单会话描述成能力上限 |
| 异步 inputs/outputs | 适合小型可序列化对象；大型模型和科研流水线优先 durable files，保留 job ID 和输出合同 |
| 任务仍 running | 正常状态；需阶段/消息/更新时间。超时先查原 job，不能自动重提或取消 |
| clean_error_log | 整理日志，不证明计算正确，也不等于撤销失败代码的副作用 |
| 代码过滤/编辑限制 | 不是强隔离安全沙箱；checkpoint 也不是所有文件和外部副作用的事务回滚 |
| Reviewer Zero / 文献核验 | 是审查协议和辅助工具，不替代证据、复算和研究者判断；具体 pass 数及后端列表需按当前 prompt 核查，旧版数字不自动继承 |
| “全绿” | 必须注明源码版本、执行层、客户端、OS 和未测项目；CLI Connected、doctor、HTTP、stdio、native 不能互换 |

## 6. 科研 skill 的设计方向

旧报告“是否应创建 workbench skill”的问题已变成“如何维护已有复合工作台及领域流程”。

compareGroups 负责统计计算，ClaudeR 负责在 RStudio 中执行和回传，comparegroups-guide 把用户习惯沉淀为 spec、参数、标签、样本选择、导出和验证流程。ClaudeR 并不因为能执行任意 R 代码就自带与 compareGroups 等价的制表统计规范。

后续模板继续扩展时：

1. 核心 skill 只维护连接/执行/资源/证据规范，领域统计规则留在独立 skill。
2. 先核对实际用户脚本和产出，再提炼默认行为；不为了自动化改变分析单位、参照组、缺失处理和统计检验。
3. 高频流程形成可读 spec 与场景预设；默认值、可变参数和统计含义应可审阅。
4. 输出统计值、展示表、元数据和校验相互对应；版式修改与统计重算分开验收。
5. 能力不支持时精确说明缺口，不静默换算法、换 R 会话或换执行层。

## 7. 优化升级的实施与验收

### 7.1 安装及接口

- 正式安装使用公开精确引用和非 editable 构建；INSTALL_INFO 区分版本、源码、实际加载、dirty/hotfix。
- 增加统一 ensure-ready 入口，明确 client/session、必需能力和 native 要求，默认只读。
- safe repair 只做有界、已授权的配置/入口修复；不自动安装任意版本、不杀会话、不伪造客户端刷新。
- 官方 App Server 有 config/mcpServer/reload 等接口，但必须证明连接到当前原会话所属服务。存在官方接口不等于当前环境可调用；另起服务也不等于修复原会话。
- “重启客户端”只能是已定位兼容性问题后的受控动作，不能作为首选诊断结论。

### 7.2 回归矩阵

| 层级 | 所需测试 | 当前不能省略的边界 |
|---|---|---|
| 源码/单元 | 配置保留与冲突、路径、discovery、绑定、stdout 协议、能力过滤、证据防篡改 | 新门禁需要负例和非空洞性验证 |
| 跨平台协议 | Windows/macOS/Linux，离线启动、多会话、坏记录和重连 | 自动化协议通过不等于 GUI 客户端通过 |
| 真实客户端 | 当前 Codex 原生链必需；Claude 因欠费获用户豁免；Copilot 单列 | 没有实测环境标 NOT_VERIFIED，不伪造联合审查 |
| 科研流程 | compareGroups/CMAverse 已有测试、统计值与输出合同回归 | 连接修复不能改变科研结果 |
| 长任务 | 单次 async、完成前可见阶段、原 job 完成、60 分钟持续观测 | 只有最终阶段不算中途进度 |
| 生命周期 | 支持组合中新建、恢复、重连各 20 次 | 不为测试销毁用户原研究/agent 会话 |
| 发布安装 | 最终提交 CI、独立审查、配套来源公开、哈希、精确版本安装后验收 | 旧版本 PASS 不能给新候选背书 |

### 7.3 发布顺序与分工

由 Codex 独立实施、复核和发布，Claude 不再参与本轮。此前 Claude 的三轮 comparegroups 审查只作为历史证据，不用于给本轮新增连接代码背书。用户只豁免了协作角色，没有豁免测试、原生通道或发布来源门禁。

先公开经审查的 ClaudeR 配套源码与引用，再由 workbench 消费。通用修复向 IMNMV/ClaudeR 单独 PR，fork 专有扩展保留清晰补丁清单。没有全部所需门禁，不合并发布或升级本机。构建仅在本机或 GitHub Actions，禁止在 VPS/生产服务器构建。

## 8. 原始来源与维护约定

- [上游固定源码](https://github.com/IMNMV/ClaudeR/tree/8a3227179f0bd5b55fe7c8f080f2a719d37339e2)
- [fork Copilot 分支](https://github.com/lzhs1995/ClaudeR/tree/feature/copilot-cli-support)
- [workbench v0.6.0](https://github.com/lzhs1995/clauder-rstudio-workbench/tree/v0.6.0)
- [workbench 候选 PR 15](https://github.com/lzhs1995/clauder-rstudio-workbench/pull/15)
- [官方 App Server 文档](https://learn.chatgpt.com/docs/app-server)

本机原件和运行证据索引由工作区 HANDOFF 维护；公开文档不包含研究数据、认证 token 或个人完整路径。
任何新“已解决”状态必须附修复提交及对应测试；任何恢复现象不得替代根因证明。
