# CFPS 残余登记与历史成功优先

先读取隔离的历史重现候选包，再决定是否重新估计。它把历史显示复原、当前输入敏感性、舍入、限制/延期和逐格科学审查分开；开放的作者裁决不是提交 Mplus 的指令。实现和当前证据见 `cfps-historical-reproduction-candidate.md`、`cfps-rounding-contract.md` 以及任务目录下的 Windows 审计脚本与报告。

这份参考文档记录 PP-LGCM/CFPS 复盘中已经验证的工作边界。它是开发副本中的草稿，只有在逐单元格科学验收、CHARLS 复盘和 PDF-only NLM 三审三校完成后，才进入最终发布审查。

## 先核实审计对象是否为当前稿（2026-10-04）

原始稿的缺陷、已修订候选稿的状态、修正数据的科学采用是三个不同状态。
每份审计必须绑定实际读取的DOCX路径和SHA，而不能仅引用“最新”或旧的
`OPEN_AUTHOR_SEMANTIC_DECISION`。本例的v5已修正X/W标签，v42保留了修正，
但后来一个审计又读取20260214原始稿，造成已经处理的标签问题重新阻塞进度。

对v42的实际复核覆盖两张异质性表全部25行、107个系数及条件效应单元格。
Windows Python与default@8787的MplusAutomation独立回读完全一致；原始稿全范围
13行的X/W语义差异在当前稿为0。旧17组67格的当前标签与历史来源已经闭合，
不再需要用户重复裁定，也不需要重跑这些历史模型。证据见任务目录
`reports/cfps_current_manuscript_reconciliation_20261004/reconciliation_decision.json`。
本核验不包含列7模型比较有效性，不关闭修正数据、边界推断或最终论文采用。

恢复工作时先检查旧问题是否已在较新的候选稿、变更凭证和源公式中解决；
把原始稿诊断保留为历史记录，并发布有文稿哈希的当前处置。相同变量角色仍可能
对应多个源块：本例type21_sex12的260/261块还需用实际XWITH及参数名区分。
解析MI参数表时保留额外的Rate of Missing列；`min_w=(0)`按数值0理解，
不能让括号或文件名形成虚假的方法阻塞。

## 先固定来源，再决定是否估计

对每个论文单元格保存 `source_script`、精确 R block、Mplus `.inp`/`.out`、数据文件和哈希。相同 `.out` basename 出现在不同脚本或不同输入命名空间时，不能按文件名复用；以表题、标准化语义、`modelout`/`dataout` 和 block 哈希共同绑定 producer。已经有成功 `.out` 且输入/数据/输出哈希通过的模型优先复用，缺少 `.out`、失败或依赖未闭合的模型单独登记，不因为“有模板”就排入估计队列。

## 把技术完成与科学放行分开

建议每个组件至少维护四个状态：

1. `technical_verdict_complete`：文件、哈希、行数、解析和输入合同闭合；
2. `author_scientific_decision`：作者选择历史值、当前重建值、敏感性结果或限制说明；
3. `source_unavailable_limitation`：历史数据或精确模型对无法恢复时的明确限制；
4. `editorial_release_open`：表格、图形、正文和附录可以进入修订稿。

技术合同通过不等于论文可以放行。对于 CFPS 10,936 行 crosswalk、156 个历史/当前差异单元格和 25 个 LRT 候选，先生成机器可读 residual register，再逐项关闭科学状态；不要以“有 PDF”“有 display sidecar”或 worker `exit 0` 替代证据。

对派生单元格，必须把“派生公式来源”和“候选输出状态”分开记录。PP-LGCM 的
`MODEL CONSTRAINT` 会从 `b1`、`b4`、`b5`、`b7` 以及调节变量的均值/标准差构造边际效应；这类行没有独立的
`model_id`，应绑定到包含 `mplusObject`/`mplusModeler` 的 block、精确公式行和上游参数 producer。候选 `.out` 若含
`contains_error`，只能说明该候选不能直接作为科学结果；先用已保存的上游估计按原始公式和显示舍入重建，只有在输入/公式无法闭合时才进入 `deferred`，不要因错误输出盲目重跑。

### Mplus `.out` 状态的窄判定

不能用 `grepl("error", out)` 作为失败判定。Mplus 输入注释经常包含
`residual error terms`，这会把有完整结果的文件误标为 `contains_error`。Windows 复盘中，17 个
relative2/relative3 派生组的 35 个历史/隔离候选均没有 `*** ERROR`、`*** FATAL` 或
`THE MODEL ESTIMATION DID NOT TERMINATE NORMALLY`，并且同时有 `MODEL RESULTS` 与
`Ending Time`；它们应记为 `COMPLETED_OUTPUT_NO_TERMINATION_BANNER`，而不是失败。由于这些旧
`.out` 没有显式的 `THE MODEL ESTIMATION TERMINATED NORMALLY` 横幅，不能把它们升级成带横幅的
正常终止；仍必须按 `MODEL CONSTRAINT`/`NEW/ADDITIONAL PARAMETERS` 和 Word 单元格合同做科学验收。

建议把原始索引状态和复核状态分开保存：`artifact_index_statuses` 保留历史索引，
`artifact_terminal_decisions` 保存窄判定，`true_error_lines` 保存可审计的错误行。这样可以修复
解析器误报而不篡改历史索引，也不会把“输出完整”误报成“论文已复现”。

### 派生值必须同时通过数值和潜变量语义

对三维调节表，按 Word 的估计值、标准误和显著性标记回搜 `.out` 只能得到数值候选；
它可能把反向的 `i_mod_s`/`s_mod_i` producer 或另一个模型中恰好相同的数值选出来。每个候选
还要从 R block 和 `.inp` 读取 `xw_int`、`xz_int`、`xwz_int` 的实际表达式，并与 Word 的
X/W/Z 列逐一比较；若 Word 在 type14_4 分支写作 `I4_4`，必须记录为 Word 标签别名，
并与 `.inp` 中实际的 `i4` 对照，不能把标签别名误报为新 latent factor。针对原始初稿的PP-LGCM复盘中，67个派生单元格有12个旧队列组的basename反向归组，
数值候选覆盖17/17组，但原始稿只有5/17组同时满足角色语义；其余必须保留
`VALUE_MATCH_SEMANTIC_MISMATCH`作为原始稿诊断，不能仅凭数值关闭验收或重跑模型。当前v42的处置见本文开头，不能沿用原始稿阻塞。旧mapping、纠正后的
mapping、chosen block 行号、`.inp` 哈希和 Word 单元格位置应并存，便于判断是文稿标签问题、
历史脚本选择问题还是当前 crosswalk 问题。

Word 对照也要按表格的实际显示合同执行。PP-LGCM 的正文/附录 Table 4.2.1 fit 行已逐行与历史 `.out` 对照，附录 AIC/BIC 使用两位小数；Table 4.2.2 参数行从未标准化 `Means`、`Variances` 和 `WITH` 段解析，`p < .10` 的 `+` 必须作为显著性标记单独保存。技术显示核验通过后，仍保留作者的历史/当前版本选择状态。

## MI 生产者的接受门

修复测量输入后，先验收所有 390 列、PID 顺序、观测值不变、缺失模式、10 份插补文件和 SAVEDATA 列名。随后独立记录：

- Mplus 原始输出哈希和最终诊断区域；
- TECH8 全部公开迭代和最高 PSR；
- 每个插补成员的收入范围、零点/负值和确定性二分类派生一致性；
- `income_derivation_review` 的状态、理由和 audit 哈希。

即使 10 个 `.dat` 文件原生回读通过，收入定义冲突或收敛证据不足也只能标为 `DATA_READBACK_PASS_SCIENTIFIC_HOLD`。禁止为了清除负值而截零、取绝对值或静默重编码；如需改变模型支持范围，建立新的隔离版本并保留原结果。

## 资源门控与可观察性

Windows上将资源准入放在Mplus提交之前，并按本任务实际测得的新增内存、commit余量、CPU和受监督上限决定并发。旧审计采用的3GiB是保守政策值，不能写成所有模型实测需求，也不能覆盖后续已验证的分支预算。准入记录必须包含预算出处、可用内存、CPU采样、外部模型数、监督器PID/创建时间、输入/数据哈希和提交计数。资源不足时先按已授权范围回收闲置资源并重新测量，同时继续未完成的来源/后处理工作；不得反复以任意固定门槛永久等待，也不绕过实际有效的监督合同。

RStudio `8787` 在线只证明传输层可用；必须另外记录本轮 `new_Mplus_submissions`、Mplus PID/父链、输出路径和终态。来自其他章节的 Mplus 进程只做外部资源证据，不能附着、杀进程或计入 CFPS/CHARLS 队列。

CHARLS 的一次 Windows `MplusAutomation` pilot 进一步验证了超时边界：`Gender / model_0930 / MI01`
在 1,800 秒受控上限以 return code 124 和 `TIMEOUT_INCOMPLETE` 收尾。即使目录中有
`model.out`，也不能把它写入正式估计；应保存 execution receipt、bounded progress、输入/输出哈希、
父链和资源峰值，并将 `scientific_acceptance=false` 固定下来。超时后先停在隔离目录，只有新的
时间/资源/模型合同经审查后才允许另开一次 pilot，不能因为 agent 轮询超时而盲目重提。

同一 CHARLS 分支随后已有一个隔离 `finite_seed` 试验正常结束：Mplus return code 0，`.out` 明确包含 `THE MODEL ESTIMATION TERMINATED NORMALLY`，`MplusAutomation::readModels()` 读回 180 个参数且 `errors`/`warnings` 为空。这个结果仍登记为 `COMPLETED_OUTPUT_SCIENTIFIC_HOLD`，因为“引擎正常终止 + readback 成功”只证明计算和传输链健康，并不自动完成跨插补、识别、标签、模型稳定性或论文采用验收。Windows 工作流应同时保存 input/output/results.dat/receipt/readback log 的 SHA，并将 `scientific_acceptance` 与 `returncode` 分开记录。

先按 DOCX SHA 和版本指针区分初稿与当前稿。20260214 初稿的 12 组语义冲突应保留为历史诊断；本次当前 v42 两张异质性表已在隔离目录完成 25 行/107 格的 Python + 原生 R 回读，current X/W/Z/Y mismatch=0，不能把初稿诊断重新打开为当前稿阻塞。

64 个 fit producer 组也必须把历史 `.out` 与隔离 `.out` 分开记账。即使两边都正常终止、且输出来自同一类模型，也不能因文件名相同或隔离目录较新就自动覆盖论文；先固定 R block、输入/输出 SHA、显示精度和诊断，再由作者选择历史、修正或敏感性版本。

派生表不能只做数值回搜。原始初稿的17个producer组中，5组同时通过数值与XWITH语义，另12组的52个单元格有标签与数值来源不一致。旧block、数值命中block、R行号和input原文均应保留；但本例标签已经在v5修正，并在当前v42的原生回读中闭合。不得继续为这12组创建重复作者决策包。是否采用历史估计、修正数据的方法是否有效和最终发布状态仍须独立判断。

这12组的技术来源闭合回执为
`reports/cfps_derived_alias_resolution_20261004/cfps_derived_alias_resolution_v1.{json,md}`：
R `XWITH` block、semantic/display producer 和 alias/spanner 组装行均已绑定，正文历史显示值已保留。该回执只关闭“来源不可追踪”问题，不替代作者对历史显示值与 semantic producer 的科学采用裁决，也不触发新的 Mplus。

## 交付前检查

最终发布前按以下顺序执行：

1. 读 residual register，逐行关闭或明确限制；
2. 回读论文正文/附录的每个表格单元格；
3. 对修订版 PDF 做本地文本、页面渲染、DOCX XML 和历史 `.out` 交叉核验；
4. 在稳定 PDF 上执行 PDF-only NLM 三审三校，保留 source IDs、原始 JSON/stderr 和 A5 判定；
5. 通过 Windows smoke、Mac smoke 和 skill eval 后，再合并三份 guide 副本并发布。
