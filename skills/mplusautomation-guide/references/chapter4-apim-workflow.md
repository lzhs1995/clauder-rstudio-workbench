# 第四章 Mplus—RStudio—MplusAutomation 逻辑复盘

## 来源纠正（2026-10-06）

用户已将指定初稿 `20260311 第4章 整合.docx` 的核查入口纠正为
`<CHAPTER4_ROOT>/证据链副本_20260909/scripts/original/analysis/20260514 Mod_APIMeM_combine.R`，
SHA-256 为 `cb77f912eb40ffb0c6a7db15f4336bb1c1bc6f8723aaf382eb7626ffa755885e`。
下文保留的是旧两脚本合同下的技术记录，不能作为新来源与初稿已闭环的证明。
模型数、样本数、图表来源和行号均须重新绑定；连接、调度、解析和隔离保护经验可按其验证范围复用。
详见 [来源纠正与证据复用](source-correction-and-evidence-reuse.md)。

## 旧任务指定的来源（历史记录）

本复盘以用户指定的两个脚本为主来源：

- `<CHAPTER4_ROOT>/20250720 Mod_APIMeM_finally.R`
- `<CHAPTER4_ROOT>/20260108 Mod_APIMeM_continuing.R`

当前文件分别与 `证据链副本_20260909/scripts/original/onedrive/` 下的同名副本一致，SHA-256 为 `f977d84257a4ae26d950c3eac04f186f2268bb0d7c3990e5eaffd40c1c4dba97` 和 `6f0260efaa8897d2cc8b7ff5d8c1be42e8a56aab91f6f199092e00df7aa5350b`。`original/analysis/` 下的同名副本是另一版本，不能混用。路径与哈希证据见 `evidence/user_declared_path_hashes_20261004.json`。

Mplus、历史 OUT/GH5 和二次分析文件所在的根目录确认为：

`<MPLUS_RESULTS_ROOT>`

该目录包含多代 LTA、APIM、APIMeM 和图形产物；递归清单为600个目录、151,920个文件。根目录存在不能单独证明文件属于同一批第四章结果，模型身份必须再由 INP、DAT、OUT、GH5 和脚本路径绑定。

## R 端先准备数据和分析尺度

脚本启动时清空工作空间，加载 `MplusAutomation`、`rhdf5`、`tidyverse`、`here`、`glue`、`gt`、`reshape2`、`cowplot`、`patchwork` 等包，设定无中文的 Mplus 工作目录并调用 `detectMplus()`（finally.R 第26—39行）。随后读取 `predata_apim_renew_16_22.csv`，将夫妻双方的 `f/m` 后缀变量整理成长表，用于计算共同量尺的均值和标准差（第44—84行）。

接着生成三类输入变量：

1. 以夫妻双方共同长表均值/标准差计算 `*_sd`，用于标准化 APIM 路径；
2. 以共同均值计算 `*_ct`，用于中心化和交互项；
3. 按 `lifetime` 拆出全样本、`fy` 和 `sy`，分别重新计算相应阶段的均值/标准差。

因此，`f` 和 `m` 是配偶角色，`fy`/`sy` 是阶段样本，不是自动生成的独立夫妻。`prepareMplusData(..., inpfile=TRUE)` 把 R 数据帧写成 Mplus DAT，并同时生成数据段，确保 NAMES、DAT 列顺序和输入文件一致。审计中进一步核对出当前完整病例基线为9,121条夫妻—年度记录、4,073个夫妻簇；历史9028口径与9121口径不能直接互换。

## `[[init]]` 模板如何展开模型

模板把固定 Mplus 语法和小范围占位符分开。`[[init]]` 中的 `iterators` 定义笛卡尔积，向量变量通过 `#` 索引映射到变量名，`filename` 和 `outputDirectory` 决定每个 INP/OUT 的身份。例如 Basic APIM 模板使用 `iv=1:5`、`dv=1:4`、`step=1:4`，将 `age/edu/siops/incc/hw` 与 `clo/eco/hg/op` 组合，并把 A1/A2、P1/P2 约束映射到四个嵌套步骤。APIMeM 模板使用 `iv=1:3`、`mv=1:2`、`dv=1:4`、`step=1:16`，显式区分 a、b、c' 路径和 Actor/Partner 角色。调节—中介模板再增加 `wv=1:4`（`ag/dw1/sib1/sib3`），把交互变量和调节值写进 `MODEL CONSTRAINT`。

当前已核验的代表模板及哈希为：

- `result_Basic_apim_test_renew_3sd_16_22/Basic_apim_test.txt`：`cce3ff0ecb891930de0176569d66528f55c5aa42fbd3cc68f5de9003e889fc70`；
- `result_Basic_apim_test_renew_3sd_16_22/Basic_apim_test_saturated.txt`：`1381b0c6b7ce7bcb761b8efd3d2034b0ad6691f181b8ff76cc84484064488b2e`；
- `result_apimem_test_renew_2sd_16_22/apimem_total_test_nocov_sat.txt`：`f6b1f609bd9accae53a934f5f833a74abc3d2c6849c66c900ee07f1cfecf28d4`；
- `result_Mod_apimem_plot2sd_renew_16_22_sat/Mod_apimem_total_combine_plot_1.txt`：`d720d673ac947c6eced4362d759ccfd26904c6bc5da8a5d5f65ae3cf2ae5b3cd`。

模板展开后必须逐个检查：文件名、输出目录、DAT 相对路径、NAMES 顺序、USEVARIABLES、角色后缀、调节值和 `MODEL CONSTRAINT` 标签。不能对整段模板做不受限的字符串替换，也不能只凭 OUT 文件名猜模型规格。

## 基础 APIM 回归

Basic APIM 模板为每个结局同时估计男性/女性结果，男性结果由男性预测变量得到 Actor 路径、由女性预测变量得到 Partner 路径；女性结果反向写入 A2/P2 标签。模型还写入结果协方差、配偶预测变量协方差以及控制变量。四个 `step` 通过标签相等约束比较 Actor/Partner 的可区分性。R 端在 continuing.R 第1—93行中分别生成全样本和 `fy/sy` 模型，再按 `step1`、`saturated` 文件筛选调用 `runModels()`。

## APIMeM 中介

APIMeM 在同一输入中同时写入：

- `a_A1/a_P1/a_A2/a_P2`：预测变量到两位成员中介的 Actor/Partner 路径；
- `b_A1/b_P1/b_A2/b_P2`：中介到两位成员结果的 Actor/Partner 路径；
- `c_dashA1/c_dashP1/c_dashA2/c_dashP2`：直接效应；
- `MODEL INDIRECT`：四种配偶角色下的间接路径。

模板还写入中介之间的 PWITH 和结果/预测变量的 WITH。输出使用 `CINTERVAL(bcbootstrap)`，并在部分模板中设置 `bootstrap=1000`。这意味着 OUT 中的间接效应、GH5/RESULTS 保存值和 R 端表格必须明确区分：直接路径的正态/Wald结果、中介乘积的 BC 区间、以及后来由 R 二次计算的近似区间不能混称。

## 调节与条件中介

调节—中介模板在 `DEFINE` 中生成四个交互项：男性中介×男性调节、男性中介×女性调节、女性中介×女性调节、女性中介×男性调节。`MODEL` 同时估计 b 路径、调节变量主效应和交互项，并为男女结果写入各自的控制项。`MODEL CONSTRAINT` 为每个调节变量写入均值、标准差、±1SD/±2SD 或三分类点，计算简单斜率、条件间接效应和 `TIE=HI-LO`。这一步是条件中介的核心：每一个条件效应必须与同一模型的路径标签、调节取值、协方差和区间来源绑定。

R 端通过 `readModels()` 循环读取 `parameters`、`indirect`、`gh5`，再整理为长表，添加显著性符号、90%/95%区间，使用 `officer`/`flextable` 输出 Word 表，用 `ggplot2`、`cowplot`、`patchwork` 输出图形。脚本中有大量按 `iv/mv/wv/dv` 和 `fy/sy/total` 循环的路径标签转换；其中 `siops` 因 Mplus 变量名长度限制曾映射为 `siop`，不能靠友好名称字典盲目还原。

实际写出位置并非一个单一“results”文件夹，而是模板对应的多个子目录。`finally.R` 的生成与读取块明确指向 `result_Basic_apim_test_renew_2sd_16_22`、`result_Basic_apim_test_mg_renew_2sd_16_22`、`result_apimem_test_renew_2sd_16_22_sat`、`result_apimem_test_mg_renew_2sd_16_22_sat`、`result_Mod_apimem_plot2sd_renew_16_22_sat` 和 `result_Mod_apimem_plot2sd_mg_renew_16_22_sat`（约第1450—1886、2461—4074、5191—5301行）。`continuing.R` 又使用了 3sd/扩展版目录（第6—181、202—345行）。表格通过 `gtsave(...docx)`，图形通过 `ggsave()`，因此同一模型的 OUT、GH5、CSV、DOCX、PNG/SVG 可能分散在模型子目录和工作目录；审计时必须以 `file.path`、模型身份和哈希共同定位。

## 原流程的关键风险与本次审计修复

原脚本多处使用 `replaceOutfile="always"`、`processors=10`、1000次 bootstrap 和较宽的递归目录筛选；直接重跑可能覆盖历史 OUT，并把不同数据版本混在一起。本次审计改用时间戳沙盒、冻结输入哈希、显式 `expected_N/expected_clusters` 和可恢复队列；MplusAutomation 的 `runModels()` 队列设为 `killOnFail=FALSE`，避免一个失败模型终止其他 Mplus 进程。

历史首轮统一候选队列由612个模型身份压缩为363个代表拟合，后补9个代表，最终范围以快照04的372个代表为准。历史作业号、端口和PID不能作为当前运行依据；恢复时读取项目专属交接并重新核验进程身份。已完成记录通过 OUT 哈希、结束标记、N、夫妻簇、`parsed.rds` 和 `parameters.csv` 独立核验；这些是执行/解析证据，不是科学放行。精度导出和效应重建保留隔离快照，候选效应保持独立采用标志。

审计还确认：2022家庭收入处理存在缺陷；夫妻跨年度记录使普通逐行 bootstrap 不能自动代表夫妻/家庭依赖；MLR/delta 区间不等于 BC 或整簇 bootstrap；部分 AP/PP/PA 标签、HI/VHI 条件点和图注存在错配；完整检验族 BH/BY、数据/控制/聚类敏感性、279个正文项目和209个配套项目仍需逐项裁定。

## 可复现的交付链

建议后续按以下顺序重跑：冻结主 R 脚本、DAT、模板及版本哈希；先用一个 Basic APIM、一个 APIMeM、一个调节—中介模板做 INP/OUT/GH5 小样本验收；再按 `[[init]]` 扩展模型清单；使用 `runModels()` 写入独立日志；完成后才使用 `readModels()`/GH5 读取；最后在 R 中生成独立的参数表、效应表、绘图数据和图形。每个展示单元都要保存“项目→模型→数据→估计→区间→检验族→采用理由”的映射，原始脚本、数据、INP/OUT/GH5 和论文均保持只读。

本文件只描述已经从脚本、模板、输出和审计证据确认的逻辑；`scientific_closed=false`，不把技术复现状态写成论文结论。

## 2026-10-04 完整代表覆盖

首轮统一队列完成363个代表后，按模型身份—代表拟合映射重新盘点出9个未覆盖代表（对应19个身份）。它们在独立沙盒中逐一执行并通过Ending Time、解析、样本量和夫妻簇核验，再合并到快照04；因此最终不是把旧历史OUT当成已重跑结果，而是得到372个实际代表拟合、612个模型身份的完整执行范围。精度读取仍按OUT哈希分块缓存，避免一次性把全部 `readModels(what="all")` 对象留在内存中。

最终快照04的合同效应为35,268行，testing units为24,264个，按12个检验族生成的BH/BY敏感性值覆盖29,880个非恒定效应。RStudio二次分析输出表格、绘图数据和PNG，并保存 `sessionInfo`、读取烟雾测试和独立一致性清单。该证据证明执行、解析和数值绑定链条闭合；`scientific_closed=false` 仍表示诊断、整簇推断、敏感性与正文/原图采用尚未被自动裁定。

## 技术完成与科学放行的矩阵

完整复现后应生成独立闸门矩阵，而不是用一个“成功/失败”字段覆盖所有判断。快照04的执行解析、精度与效应范围、BH/BY敏感性、RStudio表图和原始文件保护已有完成证据；数据/规格、诊断的科学影响、夫妻/家庭依赖与Bootstrap、正文数值采用和最终视觉验收分别审查。2026-10-05已纠正历史Type3/7与PA切片审查被错误重新列为待办的问题：从已完成的重放和两格拒绝采用裁定续接，不重复重放。矩阵生成器必须绑定最新的专项验证回执，不能仅复制旧review文字。


## 2026-10-04 完整队列复现与资源优化证据

中间快照 `scientific_audit_20261002/snapshots/unified_20261004_03` 冻结了首轮363个代表拟合。统一队列 `9292fe2c` 正常终态，363/363 个 `.out` 均通过 Ending Time、N、夫妻簇、源哈希、`parsed.rds` 和 `parameters.csv` 核验；这批中82个输出含原始诊断标记，故执行完成不等于科学放行。RStudio `default1@8789` 通过 `MplusAutomation` 分块读取161个缺失精度缓存，连同202个旧哈希复用缓存覆盖首轮363个模型；`readModels(what="all")` 烟雾核验、R表格、PNG图和 `sessionInfo` 均保存于该中间快照。最终范围以快照04为准。

随后中间快照用稀疏解析梯度重建593个模型身份的34,033个效应；这些中间计数不代表最终覆盖。最终快照04重建612个身份的35,268个效应，覆盖24,264个testing units，BH/BY敏感性覆盖29,880个非恒定行。所有这些输出都标记 `scientific_closed=false`，因为 MLR/delta 近似不替代整簇 BC bootstrap、数据/聚类敏感性和正文/原图采用裁定。

资源方面，Windows 可用内存曾低于队列实测准入要求约 1.558 GiB，形成门控等待；在保留 8787/8786/8789 三个 RStudio 会话的前提下，仅执行一次有 PID 守卫的工作集回收、一次 `gc(full=TRUE)` 和一次 WSL cache receipt，并记录前后 RSS/private/available。它们释放了部分 RSS/guest cache，但没有稳定降低 private commit，因此不能重复当作加速手段。活动 Mplus 子进程通常只有约 0.07–0.47 GiB private bytes；中位模型耗时约 100 秒，说明吞吐主要由外部 Mplus 启动/估计/解析和资源门控共同决定。保持单槽位、显式 `killOnFail=FALSE`、不降低准入储备，才是当前可复现的安全策略。
