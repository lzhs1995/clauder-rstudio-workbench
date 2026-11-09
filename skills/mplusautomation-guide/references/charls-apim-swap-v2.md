# CHARLS 夫妻数据换源：APIM 与 APIMeM 技术验证

本流程先用已核实的 CHARLS 同波配偶关联构造两人宽表，再通过现有 APIM v2 工作流串行运行一个 APIM 和一个 APIMeM，产出解析结果、效应表和图，并保留数值校验记录。它不建立新的统计队列，不复用其它研究的个体 DAT 冒充夫妻数据，不将横截面间接关联解释为因果中介。

默认合同处于阻断状态：配偶 ID 字段、其关系语义/文档和逐字段缺失码尚未验证。准备代码、通过合成测试或获得引擎窗口，都不能替代这些数据条件。

## 组件与接口

| 文件 | 用途 |
|---|---|
| `scripts/charls_apim_swap.R` | 检查来源合同、保留字符身份、构造互指配偶对、整理同波变量和审计表 |
| `assets/charls_apim_swap_config_v2.R` | 默认阻断合同与精确两模型的 APIM v2 配置 |
| `scripts/charls_apim_swap_driver.R` | `--request PATH`；准备/编译后申请一次拟合许可，再拟合、解析、渲染与校验 |
| `scripts/charls_swap_windows_runner.py` | 正式 grant 与资源核验、只读源复制、原子单次启动、进程身份与完成证据 |
| `scripts/test_charls_apim_swap.R` | 无引擎合成数据检查 |
| `scripts/test_charls_swap_windows_runner.py` | 授权、路径、预算、进程身份和重复运行的合成回归 |

底层仍调用 `run_apim_workflow()` 的 v2 入口、既有队列和资源监控。`max_parallel=1`，精确请求集合为：

| id | family |
|---|---|
| `apim_sample1_x1_y1_m1_w1_step1` | `APIM` |
| `apimem_sample1_x1_y1_m1_w1_step1` | `APIMeM` |

当前技术示例的构念合同是双方年龄、ADL 困难数与 CESD10 总分。完整病例按各模型实际字段分别定义；不自动施加既有纵向研究中的双方 60 岁样本规则。社区 ID 映射到模型的 `CLUSTER=cid`；历史 API 名 `spouse_cluster_MLR_delta` 不意味着实际采用夫妻聚类，结果展示与收据须明确社区聚类。

APIM 与 APIMeM 使用各自完整病例，N 可能不同。不能把两模型路径的变化当作同一样本中加入中介后的比较；任何这种比较都需要另行明确且获准的共同样本设计。

## 官方基期身份映射与成对资格

旧合同默认仍使用已规范化的 12 位身份、只接受原生/空字符串配偶缺失，`pair_eligibility="strict"`；缺 health、角色缺失、域外或同码都会阻断。缺省 `pair_eligibility` 的既有合同按 strict 处理，不因升级自动扩大样本处理范围。

当已核实的 Harmonized 版本用 `s1id` 保存 2011 原始身份时，显式设置以下合同字段：

```r
contract$identity_policy <- "official_id_w1_crosswalk_zero_spouse_missing_only"
contract$key_modes$demographic <- "official_id_w1_crosswalk"
contract$key_modes$health <- "official_id_w1_crosswalk"
contract$spouse_link$source <- "harmonized"
contract$spouse_link$person_id_column <- "ID"
contract$spouse_link$person_id_mode <- "as_is"
contract$spouse_link$spouse_id_column <- "s1id"
contract$spouse_link$spouse_id_mode <- "official_id_w1_crosswalk"
contract$spouse_link$spouse_missing_values <- "0"
contract$spouse_link$crosswalk <- list(
  source = "harmonized", from_column = "ID_w1", to_column = "ID",
  sha256 = reviewed_harmonized_file_sha256
)
```

crosswalk 是已声明的 Harmonized DTA 中的 `ID_w1→ID` 两列，配置绑定该文件的 SHA256，读取前后均核源文件哈希，回执记录相同 SHA 和两个模块成功映射的人数。所有身份保持字符与前导零；非空 `ID_w1` 和目标 `ID` 必须各自唯一。原生/空的 `ID_w1` 行不参与映射，用于保留跨波文件中无基期身份的记录。demographic 和 health 的原始人员 ID 也必须通过同一张官方映射转换；未知模块身份硬拒绝，禁止混用旧插零规则导致连接静默丢行。配偶先将且仅将 `s1id="0"` 转为缺失，再精确匹配 `ID_w1` 取对应 `ID`；不使用本人的 householdID 拼接配偶，也不按性别猜配偶。未知码、未匹配身份、格式不符和映射冲突均阻断。

只有预先决定并明确写入合同的 `pair_eligibility="exclude_ineligible_pairs"` 才允许整对排除：缺 health 模块，任一角色缺失，任一角色超出声明的两值域，或双方有效角色同码。此项不会消除身份冲突、自配、不互指、多配或社区冲突；这些检查在排除之前对所有已观测互指关系执行。没有任何合格夫妻或模型完整病例不足时仍阻断。角色缺失和域外可能发生在同一夫妻的不同成员，计数不强行互斥；有效角色同码单列。

`preparation_receipt.json` 的 `pair_eligibility` 记录原互指对数、各项原因、角色原因并集、缺 health 与角色原因交集、角色缺失与域外交集、排除并集及剩余对数。`reciprocal_persons` 保留排除前关系计数，`couples` 是资格筛选后宽表对数，`complete_apim/complete_apimem` 分别记录各模型实际完整病例。排除规则必须在估计前固定，不依据估计结果调整。

## 私有运行配置

配置保存在公共仓库之外；公共代码不包含个人主机路径、真实数据或结果值。外层 JSON 必须包含以下字段，未知信息应保留为 `null` 并令 `ready=false`：

| 字段 | 合同 |
|---|---|
| `schema` | `CHARLS_SWAP_RUN_V1` |
| `ready`, `worker`, `request_id` | 布尔准备状态、`W1`、`W1_charls_swap_20261104` |
| `purpose`, `root`, `models` | 与真实 grant 完全匹配的用途、独立绝对运行根、上表有序两模型集合 |
| `request` | 原请求 JSON 的绝对 `path` 与当前 `sha256`；请求须位于运行根外，与配置、grant 分属不同文件 |
| `grant_authority` | `granted_by` 为已核实的调度者 pane 与会话声明；必须与正式 grant 精确一致 |
| `sources` | `harmonized`、`demographic`、`health`，必要时加 `spouse_roster`；每项为原始 `.dta` 的绝对 `path` 和当前 `sha256` |
| `protected_roots` | 非空来源/其它研究只读目录；每个源都须处于受保护目录中 |
| `files` | `rscript`、`python`、`driver`、`engine` 的绝对路径及当前 SHA256 |
| `code_files` | 同一运行包 scripts 中全部非 test 的 `.R/.py` 文件，加 CHARLS 配置 asset；精确集合逐件核 SHA |
| `scientific_contract` | 从 `charls_apim_swap_contract()` 导出并用真实文档/标签确认的合同；Python 只验证它是对象，语义门由 R helper 执行 |
| `budget` | 下述上限、预留与有文字依据的运行新增量上界 |

`budget` 必填：`max_total_bytes<=1000000000`，`max_single_file_bytes<=999999999`，`min_c_free_bytes>=10737418240`，`min_ram_available_bytes>=3221225472`，`reserve_bytes>=268435456`，正整数 `run_growth_upper_bound_bytes`，非空 `growth_bound_basis`。源复制总量、完整运行新增量上界和预留之和不得超过累计上限。Stata 的单独 3 GB 例外不适用于此 CHARLS 包。

外层 `PREFLIGHT_PASS_NOT_STARTED` 仅表示运行授权、文件与宿主资源检查通过，不代表配偶/缺失码合同科学有效。R helper 会在读取副本后再次拒绝未验证或不互指的配偶关系。

原请求须含 `worker/request_id/purpose/root/models`（与配置一致）、正数 `est_minutes/est_ram_gb`、非空 `xdev_command` 和 `hard_cap`。后者的精确六键为 `max_total_bytes/max_single_file_bytes/min_c_free_bytes/min_ram_available_bytes/reserve_bytes/run_growth_upper_bound_bytes`，数值须与配置预算一致；命令字段只作审查信息，验证器不执行它。

正式 grant 除 `approved=true` 和相同身份/目的/root/模型外，还须有 `request_name`（原请求文件 stem）、`request_sha256`、`config_sha256`、完整 `hard_cap`、`granted_by` 和有效带 `+08:00` 偏移且不晚于校验时间的 `granted_taipei`。grant 与原请求文件同名、目录不同，且都在运行根外。签发者匹配证明声明一致；真实来源仍依调度者交付与外部固定 SHA，不等于数字签名认证。

当前版本仅执行与冻结配置完全相等的授权预算。放宽拒绝；收紧也明确拒绝，直到新的请求、配置和正式 grant 一致，不会接受更紧 grant 却继续使用较宽配置。增长上界是容量估算，不能通过调低它少预留。没有新增授权有效期假设。

## 授权与单次执行

1. 先完成真实文件 header、标签与文档核验，确定同波明确配偶关联及缺失码。不能用同户、性别、婚姻状态或猜测 `s1*` 字段代替关系证据。
2. 在独立包目录部署已冻结代码并逐件核 SHA；包目录、原始数据、配置、grant 和实际输出根互相隔离。输出根必须不存在或完全为空；任何旧产物/意图存在时只观察原 attempt，不自动重新拟合。
3. 先冻结请求，再冻结记录请求 SHA 的配置，最后由调度者签发绑定这两份 SHA 的 grant。调用方另传 grant 和配置的预期 SHA。请求不得反向包含最终配置/授权 SHA，配置不得包含 grant SHA。包含 grant SHA 的独立启动脚本最后冻结，其 SHA 写入独立审查回执，不能回写请求形成哈希循环。占位文件不代替真实授权。
4. 使用 Windows 宿主 Python 进行只读预检；要求没有 Mplus 或 Stata 进程、可用 RAM ≥ 3 GiB、C 盘可用量 ≥ 10 GiB，并留足复制/运行上界及预留空间。Python 的 `psutil` 是项目既有依赖，缺失时拒绝，不自动安装。
5. 由操作者通过其既有持久任务机制调用一次 `launch`，不要使用有超时后自动重提行为的包装。启动器不会运行 xdev，也不会修改共享队列或他人进程。

参数化命令形式如下；所有变量必须来自已核验的私有配置和正式 grant：

```powershell
& $python $runner preflight --config $config --config-sha256 $configSha --grant $grant --grant-sha256 $grantSha
& $python $runner launch --config $config --config-sha256 $configSha --grant $grant --grant-sha256 $grantSha
```

启动器以 `O_CREAT|O_EXCL` 创建 `STARTED.json` 后才复制源和启动 R。请求、配置与grant都对同一次读取的JSON字节核SHA并解析，拒绝重复键和非有限数值。源以只读句柄核 SHA，复制到本方 `source_snapshot`，核原件及副本一致后将副本设只读；R driver 仅接受这些副本路径。`PROCESS.json` 保存 R PID、出生时间、exe、driver/request/config/grant 哈希。失败保留 STARTED 和原 attempt；不删除意图、不杀进程、不自动重试。

R driver 首先构造宽表并准备/编译两模型。拟合前调用 `gate-fit --run-root ... --attempt-id ...`：再次核正式 grant、完整代码/源 SHA、宿主资源、同一 R 与 Python 监督进程身份、请求文件哈希，并沿每条父子边校验 gate 是该 R 的后代（允许 Windows `system2` 的 shell 中介，拒绝仅同名 exe）。原子生成 `FIT_ADMITTED.json` 后才进入既有 v2 拟合队列；同一批次无法重复领取许可。

`gate-fit`重新读取原调度请求；其 SHA 必须与 `RUN_BINDING/STARTED/PROCESS`一致，不能以driver请求代替调度请求。`FIT_ADMITTED`记录原请求SHA及实际使用上限。持久任务若另开PowerShell进程，启动脚本必须自含冻结路径/SHA，无交互输入，并用`exit $LASTEXITCODE`传递Python退出码；不要依赖父会话变量或超时自动重提。

## 验收与比对清单

| 层级 | 应比对的证据 | 不得据此宣称 |
|---|---|---|
| 来源 | 当前源 SHA、只读复制 SHA、完成时原件 SHA；真实 header 与文档对应 | 相同文件名就代表同一版本 |
| 配偶 | 双方字符 ID、同波互指、不同个体、无多人配对、无重复夫妻、成员角色记录 | 同户或有伴侣就证明配偶是谁 |
| 变量 | 原列/标签到双方年龄、ADL、CESD10 的映射；缺失码依据；CESD 全题与反向项规则；两人值的非退化检查 | 同名列自动代表相同构念 |
| 行集合 | 每步保留/剔除数、宽表唯一夫妻波次键、每模型 selected/excluded rows、社区数 | APIM 与 APIMeM 必须强制同 N |
| 模型 | 精确两条 ID/family、串行配置、实际 INP、社区 `CLUSTER`、每模型输入/输出哈希绑定 | 启动成功就是估计成功 |
| 数值 | 正常结束标记、解析模型 N/社区数、完整效应与区间、既有 workflow validation、警告与失败原样保留 | 内部 validation 就是科学采纳或因果证明 |
| 展示 | 社区聚类标签、源构念和成员标签；独立渲染收据；表图与解析效应一致 | 沿用夫妻聚类标题或其它数据标签 |
| 运行 | 正式 grant/config SHA、STARTED/PROCESS/FIT_ADMITTED/DRIVER_COMPLETE/DONE、日志、资源峰值、源未改变 | 有文件夹或 DONE 文件就代表 PASS |

`DONE.json` 只有退出码 0、完整 driver 收据匹配本次 attempt 和两模型、源 SHA 未变、没有持久停止标记时才写 `INTERNAL_WORKFLOW_PASS_NOT_SCIENTIFIC_RELEASE`。该标签仍保留独立科学审查边界。

## 运行边界

外层监控约每 5 秒记录本方 R 内存、隔离目录占用、最大文件与 C free；Mplus 子进程峰值由现有 APIM v2 的 `resource_measurement.json` 提供。`STOP_NEW_FIT.json` 是持久的**批次拟合前门**，不宣称每个模型重新核 grant。一个两模型批次已经获得许可后，该标记不会中断运行中的模型，也不能单独阻止队列中的第二模型；既有队列仍执行自己的资源准入。外层不增加 kill 或替代统计调度器。

目录占用与峰值是采样测量，不是文件系统硬配额，也不是历史累计写流量。需要可信的复制及运行新增量保守上界；上界未知、超过 1 GB 或可能越 C/RAM 底线时保持阻断并请求调度决定。不得把最终未超预算反推为运行期间必未瞬时超限。

## 无引擎验证

```sh
python -m unittest discover -s skills/mplusautomation-guide/scripts -p test_charls_swap_windows_runner.py -v
Rscript --vanilla -e 'source("skills/mplusautomation-guide/scripts/test_charls_apim_swap.R"); test_charls_apim_swap(normalizePath("skills/mplusautomation-guide"), tempfile("charls_synthetic_"), normalizePath(Sys.which("Rscript")), normalizePath(Sys.which("python3")))'
```

这些检查使用合成资料并验证代码行为，不证明真实 CHARLS 配偶来源已闭合，也不证明 Windows Mplus 运行成功。真实配偶字段、缺失码文档、宿主资源和正式 grant 缺一项，就不能报告换源实跑通过。
