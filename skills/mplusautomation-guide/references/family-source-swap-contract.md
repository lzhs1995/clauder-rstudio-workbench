# 换数据源与换变量合同（全家族通用）

本文说明把已有模型家族迁到另一份数据或另一组变量时，哪些事必须显式声明、按什么顺序做、哪些证据可以进公开仓库。
每个家族当前能走哪条路线、证据到哪一层，见 [家族注册表](family-registry.md)（由 `families.json` 生成）。

## 1. 适配层的边界
适配层只做：读入 CSV / Stata `.dta` / 已钉哈希的归档 DAT，按表换名，按列认缺失码，保留底层编码与精确 ID，按内容 SHA-256 钉数据身份，写 DAT 与有序 NAMES，写不含个体值的回执。
不做：合并夫妻、长宽转换、派生量表、插补、选择模型。这些留在研究自己的上游 Stata/R 链。换源跑通只说明 I/O 与编译可用，不说明两套调查的测量等价或总体可比。

APIM 系使用 [APIM v2 data adapter](apim-v2-data-adapter.md)（`data_mode`、`column_map`、`missing_codes`）。通用 [source_spec](source-spec.md) 的 `prepare_mplus_source()` 已提供 CSV/DTA 到有序 DAT 与 DATA/VARIABLE 片段的准备入口；它不接归档 DAT、不编译模型、不推导或认证长整数 ID，也不代替家族适配和真实换源验收。归档 DAT 仍按原项目的 SHA、列序与缺失码合同处理。所有路线均须满足下面第 2 节的声明。

OTHER_GROWTH 与 MOD 只接收内存数据框：文件读取和缺失码处理由调用方在上游完成，同样要满足第 2 节。OTHER_GROWTH 的 DAT 由 `run_mplus_model()` 从映射后的数据框写出；MOD 在 R 中拟合，不写 DAT。

## 2. 必须显式声明的六件事
1. **成员与波次**：一行映射对应一个模型列，写明 member 与 wave。不从列名后缀推断：同一研究的不同数据层可能用 `_f/_m`、`f/m`、`actor_/partner_` 前缀加 `_`/`_c_` 后缀、`_t1.._t4` 等不同约定，派生列的词干也可能不规则。
2. **成员朝向**：用性别或配偶 ID 列核实「member 1 是谁」，把核对方法写进映射表的 `verification` 列。同名的本人/配偶列在不同版本或不同年份可能互换。
3. **缺失码按列**：只声明问卷手册或数据字典确认过的码值。同一列里可能同时有缺失码形状的值和合法负值，不能按正负号推断缺失。
4. **标准化基准**：写明矩来自哪个样本（筛选前全样本、本模型分析行、分组内），并把实际均值来源样本的 n 落盘。同名的 `_sd`、`_ct` 列在不同文件里可能用不同基准。
5. **样本切分机制**：行筛选后写 DAT、保留全行交 Mplus 的 `USEOBSERVATIONS`、`GROUPING` 多组、`CLASSES` 加 `KNOWNCLASS` 已知类别，四者不等价，按研究原设计选一种并写明。
6. **数据身份与列序**：所有格式都按内容 SHA-256 钉，不按文件名或行数判断「同一份数据」；输出 DAT 写有序列名向量，读回时逐位核对。

## 3. 变量映射表
列：`canonical, source, member, role, verification`（APIM v2 模板已有），可选追加 `dataset, wave, construct, type, missing_codes, derivation, scale_note`。
- `type` 取 `continuous`、`binary`、`categorical`、`count`、`id`。
- `missing_codes` 用 `|` 分隔。
- DEFINE 派生变量的依赖列也登记成行，`role=derivation_input`，`derivation` 写表达式说明。
- 仓库只放占位模板（`REPLACE_` 源名）。填好的映射表留在本机证据目录。

## 4. 最短步骤
### 4.1 APIM 系（配置路线）
1. 上游链产出宽格式夫妻-波次文件（CSV 或 DTA）。
2. 复制 `assets/cfps_variable_map_v2.csv` 或 `assets/charls_variable_map_v2.csv`，逐行填 `source` 并核朝向。
3. 复制 `assets/example_config_v2.R`，只改数据、映射、缺失码、ID、样本、变换、设计、推断与输出目录；不改模型编译代码。
4. `plan_apim_workflow(cfg)` 只读检查。
5. 无 Mplus 的机器上先跑 `stages=c('check','prepare','compile')`。
6. 在获准的 Windows 窗口跑 `stages=c('fit','parse','effects','render','validate')`，同一输出根按已完成阶段复用。
7. `python scripts/validate_apim_v2_native.py <run root>` 独立核对。
8. 出效应表、作图数据、图和 Word/HTML 表；写第 5 节的回执。

### 4.2 模板路线（LPA/LCA、LTA、MS-LTA、单人中介/调节、PP-LGCM）
1. 上游链产出分析数据，按第 3 节填映射表（含波次与派生依赖）。
2. CSV/DTA 可用 `prepare_mplus_source(spec, output_dir)` 生成 DAT 与有序 NAMES；按 [source_spec](source-spec.md) 核列序、列数、缺失码和源 SHA。该准备回执不能代替第 5 节的真实换源验收。
3. 准备已审 `[[init]]` 模板，写明其 SHA-256 与完整预期 `.inp` 清单；第七章家族另按 [第七章换源合同](chapter7-source-variable-contract-20261104.md) 固定指标类型、DEFINE、starts/seed 与 Step-1→Step-3 生产者。
4. `python scripts/template_contracts.py <manifest> --output <output-directory>` 盘点模板语句（在该目录写 `receipt.json` 等文件）。
5. `compile_mplus_template_bundle()` 生成全部 INP，不估计。
6. 在获准窗口经共用执行层一次性提交，按原 job 接回，不因等待超时重复提交。
7. `readModels()` 读出，按家族验收文档比对。
8. 出图出表；写第 5 节的回执。

### 4.3 内存数据框路线（OTHER_GROWTH）
`mplus_from_mapping()` 只接收内存数据框，不读文件，也不认缺失码。
1. 上游链读入 CSV 或 DTA，按第 2 节逐列声明缺失码并转成 `NA`，按内容 SHA-256 钉住源文件；分类变量先显式编码成数值。
2. 按实际观测时间用 `growth_time_basis()` / `growth_model_syntax()` 写增长语句，分段节点由研究者给出；它只写单一过程，并行过程和协变量仍要手写 MODEL。
3. 写 `Mplus 别名 = 源列名` 的命名向量（别名以字母开头、最多 8 个字符、忽略大小写唯一），连同数据框和显式 ANALYSIS 传给 `mplus_from_mapping()`。它只换名，保留行序、取值与 `NA`。
4. 先用小合成数据做换名、换序检查：INP 与 DAT 应逐字节相同，改值只改变 DAT。`scripts/test_other_growth_compile_20261105.R` 在 CI 里跑同样的检查。
5. 在获准窗口经 `run_mplus_model()` 提交。数据或规格一变就换新的模型 ID 与运行目录，见[模型复用说明](reusable-models.md)。
6. 读回后按家族验收文档比对，出图出表；写第 5 节的回执。

MOD（`r_glm_moderation`）同样只接收数据框，文件读取和缺失码处理在上游完成，之后的步骤见[第五章合同](mediation-moderation-workflow.md)第 5 节。

## 5. 公开回执（白名单）
真实数据只在本机运行，仓库只收汇总回执：`assets/real_data_receipts/<family>__<dataset>__<日期>.json`。
- 允许的键：`schema_version, family, dataset, route, generated_taipei, platform{os,r,mplus}, data_sha256, code_sha256, output_sha256, rows, columns, column_names, missing_by_column, comparisons{verdict,items,max_abs_diff}, verdict, evidence_logical_name`。
- 不允许：估计值（系数、SE、CI、LL、BIC、AIC、类别比例、转移概率）、个体值与 ID、本机路径、样本量以外的描述统计。白名单之外的键会被校验器拒绝。
- 每个字段的类型也锁定，允许的字段里放对象或数组同样被拒绝：`family`、`dataset`、`route` 是已登记的 id，且 `route` 属于该家族；`generated_taipei` 是 `YYYY-MM-DDTHH:MM:SS+08:00`；`evidence_logical_name` 与 `platform` 各值是单行短文本；`column_names` 是不重复的变量名数组，个数等于 `columns`；`missing_by_column` 非空时必须同时给 `column_names`，其键都在 `column_names` 里，值是不超过 `rows` 的非负整数；`comparisons` 必须有 `verdict`，`max_abs_diff` 是有限非负数。重复键的 JSON 不收。
- `verdict=PASS` 不得与 `comparisons.verdict=FAIL` 共存。FAIL 回执可以保留，但不计入覆盖。
- 骨架：`python scripts/family_registry.py receipt-template <family> <dataset> <route>`，`code_sha256` 按当前文件自动计算。
- 只有结构、身份都有效、`verdict=PASS` 且代码哈希与当前文件一致的回执，才能作为某家族 `real_data_swap: pass` 的来源并计入覆盖。CI 中 PASS 回执过期（代码在回执之后改过）只发警告；发布前用 `python scripts/family_registry.py check --strict` 把过期与缺失当作错误。
- 估计值、填好的映射表和逻辑名到本机路径的索引都留在本机证据目录。
