# CHARLS 夫妻数据换源：APIMoM 与 APIMeMoM 技术验证

本流程在 PR #79（`references/charls-apim-swap-v2.md`，与本文件独立合并）产出的 CHARLS 2011 夫妻宽表上追加一个共享调节变量，再经现有 APIM v2 工作流串行运行一个 APIMoM 和三个 APIMeMoM。它是方法演示，用来验证调节 APIM 能换到另一个数据源上运行，不是研究结论，不建立新队列，也不把横截面的条件间接关联解释为因果中介。

默认合同处于阻断状态。配偶关系由 #79 的合同核验，调节变量的编码方向和缺失码由本合同核验，两者都还没有对照真实文档。准备代码、合成测试或得到引擎窗口，都不能代替这些数据条件。

## 组件与接口

| 文件 | 用途 |
|---|---|
| `scripts/charls_apim_moderated_swap.R` | 校验调节合同；只读一列调节变量；把它追加到 #79 的夫妻宽表并写准备回执 |
| `assets/charls_apim_moderated_swap_config_v1.R` | 默认阻断的调节合同、四模型 APIM v2 配置、固定的预期模型表 |
| `scripts/charls_apim_moderated_swap_driver.R` | `--request PATH`；准备/编译后，在原生 Windows 上核到同名 grant 才拟合 |
| `scripts/test_charls_apim_moderated_swap_20261105.R` | 无引擎合成检查（CI：mplus-guide-family-tests.yml） |

输入边界是 #79 `charls_prepare_apim_swap()` 的三件产物：`charls_couples_2011_v2.dta`、`preparation_receipt.json` 和同目录的 `source_contract.rds`。本流程只接受 `status=PASS_PREPARE_ONLY`、`wave=2011`、`cluster=community` 且 `data_sha256` 等于宽表当前 SHA256 的回执；回执的 `contract_sha256` 必须是 64 位十六进制，并等于 `source_contract.rds` 的 digest；这份合同里配偶互指（`spouse_link.verified`、`reciprocity_required`）、缺失码、身份码三项都必须已核验，三份文档 SHA256 都是 64 位十六进制。核过的合同 digest 与文件 SHA256 记入本流程的回执。哈希只核格式与一致性，挡不住有意伪造，但能挡住拿未核实或合成合同产出的回执去跑。本流程不重做配偶互指、成员角色和社区一致的检查，只另拒 `member1_id == member2_id`。

## 调节变量的选择

| 项 | 取值 |
|---|---|
| 来源列 | harmonized 文件 `h1rural`，按 `ID`（与 #79 相同的 12 位字符人员 ID）读取 |
| 层级与范围 | 住户层，夫妻共用；APIM v2 中为 `scope='shared'`、`type='binary'` |
| 编码 | `0=urban`（参照）、`1=rural`；来自既有 CHARLS 协变量生成代码，尚未绑定官方编码本 |
| 宽表新列 | `couple_rural`，在模型中映射为 `wr` |

选择理由：年龄与抑郁症状、功能受限与抑郁症状的关联可能随城乡居住环境不同，这是一个说得通的调节问题。城乡是住户层变量，夫妻按定义共用同一个值，用 shared 调节变量正好检验 APIM v2 的共享 W 路径，不必另造成对的调节列。教育也可以用，但它是个人层变量，要成对声明两列，还要另定分档规则，这次不做。上述理由只说明为什么拿它做技术演示，不代表任何实质结论。

## 四个模型

| id | family | moderated_paths | 乘积项所在方程 |
|---|---|---|---|
| `apimom_sample1_x1_y1_m1_w1_step1` | APIMoM | — | Y |
| `apimemom_a_sample1_x1_y1_m1_w1_step1` | APIMeMoM | a | M |
| `apimemom_b_sample1_x1_y1_m1_w1_step1` | APIMeMoM | b | Y |
| `apimemom_ab_sample1_x1_y1_m1_w1_step1` | APIMeMoM | ab | M 与 Y |

X 为双方年龄，Y 为双方 CESD10 总分，M 为双方 ADL 困难数，W 为共享城乡。每个模型只有一个无约束步骤，`max_parallel=1`，社区聚类 MLR（`CLUSTER=cid`），原始尺度不中心化。探测点为 `urban`（W=0）与 `rural`（W=1），对比为 `rural_minus_urban`。APIMoM 只用 X、Y、W 的完整病例，APIMeMoM 另需 M，因此 APIMoM 与 APIMeMoM 的 N 可以不同，三个 APIMeMoM 的 N 相同。不同 N 下的路径变化不能当同一样本的比较。

## 阻断规则

- 合同：`codes_verified=TRUE`、编码本 SHA256 与定位都要填；空的缺失码列表不算核验证据。缺失码不得与有效码重叠。
- 读取：人员 ID 必须是 12 位字符串且唯一；有效码与已声明缺失码以外的值直接阻断，不静默改成缺失。原生缺失与 Stata 标记缺失计数分别保留。
- 夫妻宽表：回执没有绑定已核验的配偶合同（`BLOCKED_UNBOUND_COUPLE_CONTRACT` / `BLOCKED_UNVERIFIED_COUPLE_CONTRACT`），或同一人自配成对（`BLOCKED_SELF_PAIRED_COUPLE`），阻断。
- 追加：夫妻任一方不在调节来源里，说明来源版本不一致，阻断。住户层变量只有一方有值或两人取值不同，也阻断，不挑一个人的值顶替。
- 完整病例中 W 必须两档都有、社区多于一个；含 W 主效应与乘积项的 Y 方程、M 方程预测矩阵必须满秩。
- 输出目录已存在就停，保留原 attempt。准备回执只记计数与哈希，取值分布留在本机证据。

## 授权与单次执行

驱动读取私有请求 JSON：`request_name`、`root`、`attempt_id`、`couples_data`/`couples_receipt`/`couples_contract`/`moderator_source`（各含绝对 `path` 与当前 `sha256`）、`moderated_contract`、`engine`、`python`、`protected_roots`、`expected_models`、`grant` 与 `window_request`（各含 `path` 与 `sha256`）。请求文件含本机路径，只留本地，不进仓库。

1. #79 已合并，`charls_prepare_apim_swap()` 在 `scripts/charls_apim_swap.R`。先按 [#79 的流程](charls-apim-swap-v2.md) 在 Windows 上核实配偶关联与缺失码，并运行到 `charls_prepare_apim_swap()` 产出 `PASS_PREPARE_ONLY` 回执；不需要先拟合 #79 的两个模型。这三件产物出来之前，本流程在 main 上不能端到端执行。
2. 只读核对 harmonized 文件中 `h1rural` 的标签与编码本，把编码本 SHA256 与定位写进合同；未核实就保持 `codes_verified=FALSE`。
3. 在 `mplus_window/requests/` 提交请求，等调度者写出同名 grant。把 grant 文件的 SHA256 写进私有请求 JSON。
4. 运行一次驱动：先准备、编译四个输入，再在原生 Windows 上由 `charls_apim_moderated_admit_grant()` 核 grant。grant 格式见 PROGRAM 计算窗口规则：文件为 `grants/<request_name>.json`，SHA256 一致且不在运行根之内；内容 `approved=true`，`request_name`、`request_sha256`（窗口请求文件的 SHA256）、`worker`、`request_id`、`purpose`、`models` 与窗口请求一致，`root` 等于本次运行根，有 `granted_by`、`granted_taipei`；`hard_cap` 照抄或收紧请求，`max_engine_starts` 不少于模型数。任何一项不符都报 `FIT_GRANT_NOT_ADMITTED`。准入后按 `hard_cap` 重建配置：`processors_per_model` 进处理器预算，`max_wall_seconds` 收紧调度等待上限（到时停调度、保留进程，不强杀）。用独占创建写 `FIT_STARTED.json` 后串行拟合、解析、计算效应并做内部校验，最后独占创建 `DRIVER_COMPLETE.json`。失败保留现场，不重提、不杀进程。
5. 展示副本用 #79 的 `charls_render_apim_swap()`（同在 `scripts/charls_apim_swap.R`）改写聚类文字（v2 历史入口名会写成夫妻聚类，实际是社区聚类）；只改标签，数值缓存不变。

本驱动的拟合闸门比 #79 的 `charls_swap_windows_runner.py` 简单：它不做源文件只读快照、进程身份和宿主资源检查。那个 runner 把 worker 和两模型集合写死，要用它跑这四个模型，需要先让它从配置读取 worker、请求名与模型表，这一步不在本 PR 范围内。

## 验收与比对清单

| 层级 | 应比对的证据 | 不得据此宣称 |
|---|---|---|
| 输入 | #79 准备回执的状态、`data_sha256` 与宽表一致；本回执记下的 `couples_contract_sha256` | 有宽表就代表配偶关系已核实 |
| 调节变量 | 编码本 SHA256 与定位；有效码、声明缺失码、原生与标记缺失计数；夫妻不一致与单方缺失为 0 | 同名列在不同版本含义相同 |
| 行集合 | 夫妻数、APIMoM 与 APIMeMoM 各自完整病例数、W 缺失的夫妻数、社区数 | APIMoM 与 APIMeMoM 必须同 N |
| 模型 | 恰好四个 id/family/moderated_paths；实际 INP 中乘积项与 W 主效应所在方程；`CLUSTER=cid` | 编译成功就是估计成功 |
| 数值 | 正常结束、解析 N 与社区数、条件效应与对比的完整区间、既有 workflow validation、警告原样保留 | 内部 validation 就是科学采纳或因果证明 |
| 运行 | grant SHA256、`FIT_STARTED`/`DRIVER_COMPLETE`、日志、输入 SHA256 在运行前后不变 | 有 `DRIVER_COMPLETE` 就代表科学结论可用 |

## 运行边界

- 合成测试的检查只说明代码路径与阻断规则成立，不说明 Mplus 接受或收敛。
- 只用 2011 一波。不继承既有纵向研究的年龄筛选、标准化或多重插补。
- 公开仓库只放代码、合成夹具与变量名；真实个体值、ID、估计值和本机路径都留在本机证据。
