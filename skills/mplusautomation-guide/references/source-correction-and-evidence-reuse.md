# 来源纠正与既有证据复用

## 何时适用

用户纠正论文初稿、分析脚本或数据版本，尤其已有大规模重跑和完成报告时。
来源纠正不等于全部技术工作失效，也不等于替换路径后可以沿用旧结果。

## 两条独立证据链

- 技术能力：ClaudeR连接/异步进度、Windows资源协调、队列恢复、模板展开、解析、图表生成和独立验证。按环境、接口和已测边界复用，只重测受变更影响的部分。
- 研究来源：原稿哈希、代码块、数据、模板、估计规格、历史输出和原稿表图。逐项重新绑定，不能由技术测试通过代替。

将旧成果分为直接复用、适配后复用、仅作历史参考、撤回来源结论。保存旧日志和结果，明确适用范围；不要销毁曾经支持错误结论的证据。

## 只读核验顺序

1. 冻结指定原稿与脚本的绝对路径、原始字节SHA-256，核对历史会话中最初指定的来源。
2. 正向追踪原始数据、do中的宏/工作目录/merge支路、CSV、R变换、模板、DAT/INP/OUT/GH5；反向追踪原稿图表的生产者。
3. 区分文件存在、静态引用成立、内容匹配、历史执行有凭证四类证据。缺少运行凭证时不得宣称历史执行已证明。
4. Word媒体字节哈希、解码像素/规范化矢量一致、表格规范化单元格一致、仅语义相近分别记录。PNG/SVG备用媒体不能重复计为两幅论文图。
5. RData缺失先报告；只存在注释load不能证明全盘缺失。若用户禁止重建，不得生成替代历史缓存。
6. 数据计数区分个体、夫妻、夫妻—时间和亲子二元组。核验ID实际语义；注释、文件名和总行数吻合都不能替代逐ID检查。
7. 检查同一do中所有同名`save, replace`，不能只取首次保存。只读解析应处理`///`续行、块注释和宏；未解析的循环或工作目录明确保留未决状态。
8. 从论文解包的媒体及论文副本仅证明副本身份，不是图表生产者。PNG与SVG伴随文件字节不可直接比较；标为跨格式对应待核验，不应标为内容错误。

## 模板范围与重跑

`createModels`全部组合、`runModels(filefilter=...)`筛选集合、磁盘现存INP/OUT和初稿实际采用集合可能不同。
先分列清单；静态笛卡尔积只是候选数，不代表全部有效模型。重复文件名、条件块和空筛选必须核验。
如用户要求双层全量，分别验收初稿依赖层与全部有效模板组合层。
历史规格忠实复现与纠正收入、改变聚类推断等方法改进分批保存。

## 本次已核验证据与限制

- 旧会话原始任务记录直接指定了旧两R脚本；这能证明任务来源沿革，不能证明旧模型全部错误。
- 正确combine脚本第1693–1695行使用生命周期APIMoM `_mg_1n/_mg_2n/_mg_3n`，三个文件均存在；手工清单重复写三次`_mg_1n`是清单错误。
- 现存主DTA为9,748行，四期3,521/2,698/1,937/1,592行；按`pid_`核验为6,381个唯一值，与do中6,350注释冲突。ID科学含义和历史版本须继续核查，不能直接据此确定独立夫妻数。
- 指定combine脚本及初稿已冻结哈希；新来源全链条尚未闭环，新Mplus执行数为0。
- 旧finally与新combine在首次`newdir <-`之前，去除空行及整行注释后的代码逐行一致；这只支持该数据准备代码块复用，不能扩展到所有后处理。
- 旧612份历史OUT归档全部通过原台账SHA-256回查，312份与现存模型目录OUT一致。归档证据可以保留，但现存DAT存在9,028/9,121行混用，不能只凭OUT文件名认定它由当前DAT生成。
- 上游do第257、394行两次覆盖`pair_sample_base_2022.dta`；第二次保存对应3,228行。手工清单11,598属于较早阶段，不能用于现存文件的样本量。
- 现存half_finish DTA的9,121个完整案例ID与CSV一致，61个直接/重命名字段和36个派生编码已只读核验。dummy检查须排除缺失类别并保留缺失，不能把缺失当成第4类或零。

本地证据包：`<LOCAL_AUDIT_ROOT>/`，
主要文件为`source_manifest.json`、`history_evidence.json`、`sample_counts.csv`和`main_dta_counts.json`。
这些本地记录是当前案例的审计凭证，不是其他研究迁移时必须存在的依赖。

## 逐项收口时的新增判据（2026-10-06）

- **夫妻身份必须固定方向。** 本案例9,748条夫妻—时间记录有6,381个有向键，但按两个配偶PID排序后只有4,386组；1,995组跨期交换方向。`totalcount_final`等于有向键频数，不能直接解释为夫妻追踪期数。无向键也不自动证明是同一持续婚姻关系。旧6,350注释仍无来源证明。
- **候选ID匹配不等于恢复历史原始ID。** 9,028行历史DAT在15位写出及配偶方向约束下全部找到唯一候选；与当前完整案例候选交集8,934，历史独有94，当前新增187，且72列变化。不得只用净增93解释数据版本，不把受约束候选关系当作历史数据消费凭证。
- **脚本静态解析要先排除注释，再读参数。** 本次把已注释的`filefilter`当作活动参数，曾误报540个候选和192个漏选。修正后780个候选覆盖旧612个依赖。加入注释过滤负例，保留字符串内`#`。模板2,328候选、活动筛选780、旧稿依赖612仍为不同集合，尚需原生生成语法验证。
- **图形结构可以排除同名输出分支。** 本案例8幅中介图有六类效应标签，可排除早期四类效应块；但这只定位代码候选，不证明该脚本历史上执行过。4张PA汇总表有重复生成分支，第三轮已证明对表内符号局部等价，不能按代码先后随意定来源。
- **Word矢量结构变化不等于数值变化。** `path M/L`与`polyline`可以表示相同CI线段。按分面clip归一化，比较标记次序、坐标、文字、颜色与透明度；容差来自坐标写出精度，不能由最大观察差倒推。负例应改变点、CI、透明度和文字并确认拒绝。第三轮247项已扩展到灰黑标记；仍不覆盖全幅像素或历史生产凭证。
- **表格按研究角色验收。** 本案例30表含12理论/定义/公式、2描述、16模型结果。理论表需要内容/公式审查，不能要求并不存在的Mplus结果生产者。
- **标签相同不能共用变量映射。** 本人年龄与父母年龄、两种机会结构、本人/父母户口要按表格分区与代码绑定。后设值标签也会错：本案例`coresi=1`为同住，`housewc=0`为区分工作日，下游描述表标签有反向定义；优先核查生成公式、原始问卷及逐值频数，不为通过检验交换标签。
- **p值差异先核对检验合同。** 本案例6处原稿p值符合Welch，而历史RTF符合等方差t检验；数值解释成立不证明已找到Welch生产者，更不证明独立样本推断适合夫妻与跨期相关数据。不要归类为舍入误差。
- **输入回显和数据消费分开证明。** 612份归档INP与OUT去空白/注释回显一致，证明语句对应；OUT通常不记录DAT哈希，不能据此证明同目录现存DAT被当时消费。

新增证据入口：`exact_couple_identity.json`、`data_version_resolution.json`、
`template_scope_resolution.json`、`static_filter_guard_validation.json`、
`mediation_branch_structure.json`、`archived_input_echo_status.json`、
`descriptive_cell_resolution.json`和`svg_geometry_guard_validation.json`。

## 第三轮：从GH5和实际模型合同补强证据

- 历史CSV缺失时，先检查GH5的`individual_data/raw_data`和`var_names`。本案例600份GH5可与归档DAT逐模型核对实际变量、DEFINE乘积、筛选后的行序和float32存储值。该证据比同目录推断强，但不能恢复精确超长ID、未使用字段或所有原始CSV字节；12份直接效应模型没有GH5，不能借其他模型自动补齐。
- 官方MplusPlotsUI.zip中的`mplus.R`明确将GH5数据中的999转为NA。应按原输入重建缺失传播，在HDF5比较层转换缺失哨兵；不能把未满足任何IF的效应编码设成0。60份排行APIMoM删除缺失协变量记录，72份条件中介保留记录及缺失编码，分别验证，不能只要求总N相同。
- 重复代码分支可以做**结果相关等价性**裁定，不必猜历史运行顺序。本案例两PA分支的BC计算体、显著性函数及420格所需GH5参数选择均一致；419格匹配原稿，1格历史冲突保留。分支对其他HI/VHI参数的选择不同，不能把局部等价推广到所有图表。
- `[[[malemv#mv]]]`是合法的Mplus截距括号`[]`包围模板`[[malemv#mv]]`。标签解析必须禁止把额外左括号吞入标签名；加入`[[[...]]] → [inccm_sd]`负例。初版审计误报504差异（含288依赖模型），修正后2328模板体全部与现存INP一致；该计数是静态等价，不是2328模型均已估计。
- `runModels`经`convert_to_filelist`对完整路径作PCRE匹配。给目录时可能命中历史“副本”和手工额外输入。本案例780合同候选外还命中9个额外INP；生产队列应使用冻结的精确文件列表，不直接复制宽泛目录筛选。
- 比较完整黑色CI时必须读SVG全局CSS。svglite常在`.svglite ...`规则中声明黑色stroke，Word将相同属性写在单个图元。仅看元素属性会漏掉不显著结果。已知CSS规则下247图全部分面点/线比较通过，黑点、黑CI、红点、文字扰动均被拒绝；不得对任意SVG硬设默认描边。
- 描述表316值和92数值p值均可独立回查；这是数值/方法对应，不是历史producer或夫妻/跨期独立性的科学认可。

第三轮证据：`gh5_embedded_data_bindings.csv`、`pa_branch_cell_adjudication.csv`、
`template_body_comparison.csv`、`template_and_filter_guard.json`、
`svg_all_panel_marks_status.json`和`svg_all_panel_guard.json`。

## 第四轮：缺失GH5、栅格伴随图与历史科学合同

- 无GH5时，可独立计算归档DAT按输入筛选后的均值、协方差、相关系数，与OUT打印精度比较，并核对N与实际CLUSTER变量的组数。本案例12模型21,000个样本矩全部匹配。该证据支持数据合同，不能唯一辨识逐人身份；不能用匹配矩阵冒充历史CSV字节恢复。
- PNG先合成白底再检查。透明背景在黑底查看器中会隐藏黑色点和CI。跨格式比较应独立识别面板边界，将点、CI端帽中心和零线转为面板归一化坐标；用栅格化及边界定位精度设置容差。16图960组点/CI/颜色和320零线通过3px合同，最大差2.67px；没有据此证明历史PNG导出命令或文字OCR。
- `.svglite`可能位于根节点，也可能位于内层`g`。只对已识别CSS选择器作用域应用默认stroke，并允许元素显式样式覆盖。内层组负例必须覆盖黑点、黑CI、颜色和零线；metadata变化应通过。不要在任意SVG上强加默认黑色。
- 历史与重跑诊断必须分别从哈希绑定的OUT提取。本案例612历史输入与正确combine模板体全部一致；历史360个bootstrap全部1000/1000，999次属于后续重跑。历史60项missing-X与72项SE诊断，不等于后续重跑132项missing-X或更多参数化诊断。原稿关联不能从`current_codes`列推断。
- CLUSTER名称是估计合同的一部分。历史252模型按FID聚类，360个bootstrap模型没有COMPLEX聚类合同；不能把这些FID组数改称修正候选中的无向夫妻簇。历史60个排行APIMoM是删缺失X子样本，72个排行条件中介保留历史阶段样本，旧132项完整案例范围裁定不可整批回灌原稿。
- 中介路径用`pred/intervening/outcome`的成员身份判定，每段成员相同为A、不同为P，不凭标签字面或注释猜。正确combine也可能保留错误显示标签：本案例`aP1bP2`为XF→MM→YF（PP）却显示AP；`aA1bP2`为XM→MM→YF（AP）却显示PP。性别前缀必须声明指暴露者还是结果者。图像与归档一致并不解除这些语义问题。
- 双层合同分别保存稿件依赖和模板全集的精确输入、模板、替换参数、DAT/OUT哈希及待执行状态。612是2328候选的子集，不应报为2940个不同模型。当前目录有OUT不等于本轮已估计，静态有效也不等于原生Mplus语法与统计有效；不同数据/引擎合同不可偷换复用。

第四轮证据：`direct_sample_data_bindings.csv`、`png_svg_geometry_status.json`、
`png_svg_guard.json`、`combine_bound_historical_diagnostics.csv`、
`historical_rank_scope_correction.csv`、`combine_mediation_path_labels.csv`和
`two_layer_execution_contract_status.json`。历史转换命令、未恢复的9028上游版本、
科学采用分别记录，不因缺文件自动重估，也不把有限检索结果称为全盘不存在。

## 第五轮：实证展示数值对应与科学采用分开

全部279个实证对象已接回正确combine的实际选参及历史模型数据：263图3360行、16表1332格。
表内两格历史符号冲突保留；新增确认79幅条件图的点/区间混用、路径或极端探查选择问题，
以及8幅中介图144位置的类别标签问题。第五轮替代此前“逐点/区间绑定待完成”和“105行仅旧警报”的状态。
相关可迁移方法集中在 [display-producer-contracts.md](display-producer-contracts.md)，
避免重复维护选参、CI表头、bootstrap切片和图元验收规则。
原9028上游版本、精确历史ID、推断合同仍未因展示对应而通过；本轮未执行新的R/Mplus。

## 数据版本的样本进出与变量变化

历史 DAT 只有舍入后的超长 ID 时，保留受约束候选映射的限定条件。
比较版本至少分开共同记录、历史独有候选、当前新增候选；按年份分层，
再检查同一候选的原值、编码、缺失状态及标准化值。共同样本不变也可能有
原值变化，标准化列全面变化也不意味着每个人的原值都变了。

当前排除原因应静态展开 do 的活动宏/续行，逐行复核保存的 missing-count。
按缺失变量计数可以重叠，另外给出互斥的缺失组合才能与排除总数对账。
这解释的是当前筛选；不能倒推当前新增个案在旧版本中为什么被排除。
第七轮案例的 65 字段在 9748 行完全复核，94 个历史独有候选如今均被缺失
筛选排除，187 个当前新增候选为 2016 年 163 个、2018 年 24 个。
共同候选的 24 个原值/编码列也有变化，不能用净增 93 行概括版本差异。

已定位的 RData 对象可只读解析一个局部序列化区段：按列流式处理普通原子
向量，核对每列长度、相邻名称向量、属性值、前置符号和结束边界。
未知 ALTREP、引用或其他编码要明确保留或拒绝；未解析全局符号引用表时
不可冒充完整工作空间目录。第七轮定位的 `data.modmed` 候选有 9121 行、
234 列，证明该局部对象不是所缺的 9028 数据；不能排除文件内其他对象。
读取器应拒绝截断和不支持的编码，保留 NA 与真实负数的区别。

旧数据清理缺陷要重绑到新指定来源。先核对源 DTA/脚本哈希，再核对归档
INP 的实际 ON 方程，不能仅凭 USEVARIABLES 认定某变量作了回归控制。
第七轮重新绑定了当前源 2022 家庭收入遗漏平减、缺失值进入上端缩尾的
既有机制；612 个归档模型都实际使用 fincc 回归项，4 个历史 DAT 组的
2022 fincc 均为常量。历史同症状仍不是遗失旧 CSV 的生产证明，也不能
自动选择既有修正候选或把旧修正结果写入本次正文。

证据：`ch4_source_correction_20261006/ROUND7_FINDINGS.md`、
`historical_sample_turnover_status.json`、`rdata_local_frame_status.json`、
`historical_family_income_rebinding.json`（同一审计目录）。
# Consolidated chain delivery

Track negative provenance searches with exact roots, filename rules, enumerated
counts, read failures and already-screened candidates. Do not repeat the same
search or turn "no named candidate found" into "no historical version exists".
For long Stata do-files, inspect data-switch and export branches throughout the
script; the first use command is not its only possible input. A nearest preceding
use is a locator, not an execution-state proof across merges, preserve/restore,
macros and conditional branches. Deduplicate copies by content hash when counting
distinct producer versions.

Keep a single readable chain index alongside round-by-round audit logs. Link raw
file inventory, resolved intermediate paths, the actual designated script, template
paths, model-specific DAT/INP/OUT identities, RData availability and manuscript
artifact mappings. Arrows show dependency structure unless each transformation
has independently verified values; source existence and static references are
not execution provenance. State missing historical CSV/ID/version links explicitly.

For figures, keep byte identity, supported SVG geometry/text agreement, numeric
producer logic and scientific adoption as separate fields. In this Chapter 4
audit 16 selected reference images equal embedded media bytes, while 247 SVGs
have differing hashes and supported point/segment/text agreement. Rebind both
hashes when reusing that geometric evidence; do not relabel it full rendering
identity. RDS caches or a locally parsed frame in another RData are not a recovered
original workspace. Preserve a missing requested RData as missing until found.
# Archive snapshots are a separate provenance layer

After a bounded loose-file search, inspect justified research ZIP central
directories before repeating the same filename search. Stream selected members
without extracting into research directories; record both archive and member
SHA-256, local counterpart hash and exact search limitations. An archive DAT
matching the local DAT confirms another snapshot, not the missing upstream CSV,
historical IDs or execution history. File timestamps are not authenticated dates.
Do not treat every `.dat` as analysis input: SAVEDATA results can share that
extension. Resolve its producer and consuming DATA statement.

For archive/current INP differences, compare effective syntax and classify
output-only additions separately from estimation changes. In this Chapter 4
case, 384 current inputs retain the archived effective prefix and append
SAVEDATA RESULTS plus PLOT TYPE=plot3. This is a static statement about syntax;
it is not a new native equivalence test or permission to reuse mismatched outputs.
Keep template differences, input differences and run-log changes distinct.

When comparing archived OUT files, preserve whole-file hashes and separately
compare a documented statistical-report region. Runtime timestamps, input echo,
SAVEDATA/PLOT and DIAGRAM metadata can differ without changing printed estimates.
Do not discard warnings or parameter lines to obtain agreement. If the comparison
boundary changes after inspecting a metadata difference, document that change and
rerun the entire affected comparison. An input-echo-only archived OUT is an
incomplete snapshot, not evidence of completed estimation or a currently live job.
ZIP members are case-sensitive even when their Windows counterparts are not;
case-folded matching must reject ambiguity instead of silently picking a member.

If named CSV searches fail, a bounded header-based search can detect renamed
copies: declare roots/exclusions, read CSV records with a parser, and record
header overlap, row count, file hash and unread cases. Similar headers or a
matching row count only nominate candidates; they do not establish historical
identity. Count exported index columns separately from substantive variables.
An absence result applies only to the declared formats and search scope. Long
searches should emit periodic stage/file-count progress and retain a single live
job handle; observation delays are not authorization to resubmit the search.
