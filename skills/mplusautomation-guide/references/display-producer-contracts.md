# 图表数值生产规则与成员路径核验

用于核对原稿图表、迁移已有循环脚本或排查“模型正确而展示选错”的问题。
只读重建绘图数据能证明数值对应，不能证明某份R文件当时确实运行过，也不解除模型诊断。

## 在出图前保存的最小合同

每个点或表格单元格保存：model_id、INP/OUT/GH5哈希、样本、暴露者—中介者—结果者、
参数精确名称、探查值、点来源、CI来源/置信水平、抽样数/切片/分位数算法、显示标签及显著性规则。
点、区间和显著性从同一具名效应取得。完整拟合结果可按哈希缓存；只核查少数效应时逐GH5列读取，
保留紧凑结果，避免将所有模型的bootstrap矩阵常驻内存。

## 选参陷阱

- 正则或包含匹配`HI...`也会命中`VHI...`。首个匹配行取决于文件顺序，不能代表研究定义。
  已知别名先按模型族显式规范化，再精确匹配；重复匹配必须报明歧义。
  第四章PA晚分支曾将VHI和HI归到相同indicator，GH5取VHI点而OUT保留HI区间。
- child模型的交互项INTF/INTM会在多个方程出现。键应包括方程和参数名；
  例如按结果成员F/M后缀再唯一选择，不能只搜参数名或固定行号。
- OP与OP5命名随模型块变化；sibg中等探查标签可能是TTP1/TTP2，不能类推成TTPP1/TTPP2。
  从实际INP/OUT与脚本映射确认，不用“第一个看起来相似的参数”。
- PA/AP/PP由每段成员是否相同判定：X→M相同为A、不同为P；M→Y同理。
  条件模型child别名与连续W别名须分别验证。性别前缀明确指暴露者或结果者，
  最稳妥的审阅展示是显式XF→MM→YF等三成员路径。

## CI与bootstrap的区别

- 先验证OUT表头。Mplus七列`Lower .5, Lower 2.5, Lower 5, Estimate, Upper 5, Upper 2.5, Upper .5`
  中，90%区间是零基2/4，95%是1/5。列解释错误是审计器错误，不应报告为论文错误。
- BC区间按实际脚本：z0=Φ⁻¹(mean(draw < point))，再取概率Φ(2z0+Φ⁻¹(q))的经验分位数。
  记录严格小于、完整抽样数、缺失策略和分位数算法。R默认type7对应NumPy linear；
  原生Mplus BC或其他分位数算法须作为不同合同，不能悄然替换。
- `V3:V1002`按列名可选全部1000抽样；`V3:ncol(merge_data)`到合并对象末列也可覆盖全部抽样；
  如果结束位置使用合并前对象的长度，前置元数据列会造成截尾。第四章PA汇总曾只用991/1000，
  AP/PP汇总和八幅中介图使用1000。必须按表达式和列布局推导，不能一律套用“B−9”。
- 历史忠实复盘保留历史切片；方法纠正另存新合同。两重复代码分支只在已核查的目标单元格上可称等价，
  PA符号表等价不能推广到HI/VHI图。

## 从数据核查到实际图元

根据真实ggplot比例尺计算期望坐标，包含点、CI、零线和expansion；
`facet_grid(scales="free_x")`按列训练范围，不一定每个分面独立。
同时检查样本顺序、L/M/H位置、点、CI主线、端帽、颜色、透明度与零线。
容差来自写出精度/栅格定位，不能由观察误差反推放宽。
打印舍入后零长度CI可产生两个重叠端帽，不能误判为重复参数。
PNG与伴随SVG跨格式证据和SVG与模型参数绑定分别记录。

有意义的反例包括：95%替换90%、HI/VHI选错、991替代1000抽样、交换AP/PP数据、
改点或端帽、改显著性透明度。metadata变更应通过。审计器失败先核验映射与解析，
保留修正记录后才归因到研究产物。

## 从核查进入隔离修订候选

来源审计期间若可只读提取历史模型，先保存可审阅的修订CSV，保留原始与候选的参数名、
点、CI、成员路径和逐行差值。候选的点/CI必须同名、路径符合所要检验的效应；
同时保留未受影响的对照行，检查没有额外数值变化。
纯标签修订应保留全部点和区间。选择不同具名效应造成的显著性标记变化不是重新估计结果，
也不解除历史推断诊断。候选数据通过、图已渲染、文稿已修订分别登记。
本案例87幅图的候选已准备，79条件图474行中291变化/183不变，8中介图432行值保留；
14图25行90%标记变化仍处于显示候选阶段，未用于正文或新估计。

## 本地实证边界

2026-10-06第五轮：263幅图3360个绘图数据行与正确combine规则及历史输出对应；
16张表1332个所核单元格中1330匹配，PA/AP各保留一个符号冲突。
条件图105行点/CI混用、114行路径类别错误、237行极端探查值选择有重叠，合计影响79图；
另八幅中介图144个位置的AP/PP标签错误。不得相加成不重叠的错误点总数。
这些是数值和展示层证据；9028历史上游缺口、SE诊断、聚类/抽样推断与正文采用仍单列。
生产依赖范围与实际显示范围也分开：612个依赖中只有588个模型有参数直接进入冻结稿显示，
另外24个保留在复现合同，不为其补造显著性，也不因没有显示行静默缩小已授权范围。
本地凭证：`ch4_source_correction_20261006/ROUND5_FINDINGS.md`及对应producer CSV；迁移技能无需该路径存在。
# Printed claims need member-path verification

Matching an estimate and p-value to a cited figure does not validate the prose.
Bind predictor, mediator, outcome, stage and figure column, then independently
read the raw OUT specific-indirect triple (printed outcome, mediator, exposure).
Do not infer the recipient from a wife/husband facet prefix or an AP/PP label.
In the corrected Chapter 4 manuscript, all 19 explicit BC-p quotes match their
selected estimate/p at printed precision, yet 14 assign the wrong member path.
These concern six paragraphs and four cited figures, not 14 independent figures.
Preserve source hashes and native triple line numbers. Revisit the mechanism
interpretation as well as the label; the indirect product alone does not identify
the separate signs of its a and b paths. A negative search for p>1 among explicit
BC-p tokens does not clear unlabelled p-values or all manuscript text.

To check mechanism wording, bind the native a and b regression rows separately,
and verify their product against the high-precision GH5 indirect estimate. GH5
regression labels may be `Parameter N, Y ON X (equality/label)` rather than plain
`Y ON X`; parse the actual format, reject duplicate mappings and retain the full
source label. Do not equate component Wald tests with a BC product test, require
both components to be individually significant as a mechanical mediation gate,
or transfer product significance to both components. Repeated citations can share
the same b coefficient, so citation counts are not independent test counts.

## Trace corrected paths into manuscript conclusions

Keep a separate prose ledger keyed by native DOCX paragraph index and source
hash. Verify cached paragraph text against the document before drafting isolated
candidates. Record whether each finding is a confirmed member mismatch, a
downstream dependency on that mismatch, an inference overreach, or an unverified
numeric claim. An explicit `bc_p` scan does not cover ordinary `p` quotations.
Do not promote a locally correct quotation to a valid paragraph when the
paragraph synthesizes another, mislabelled path.

Significant-path counts alone do not compare effect magnitudes or establish a
dominant mechanism. Actor-Partner denotes the member structure X→M→Y; it does
not itself measure caring for a spouse's parents. A product estimate does not
measure unobserved time competition, gender beliefs or household negotiation.
Write these as hypotheses unless the research design and measures support them.
In an additive linear decomposition, opposite indirect effects can cancel in
the total indirect effect; do not say that they cancel the direct coefficient.
Bootstrap inference does not itself establish causal identification or correct
cross-wave dependence. Preserve numeric results and confidence conventions while
reviewing interpretation; keep pending numeric checks explicitly pending.

For ordinary `p=` quotations, compare each candidate against both the native
Wald column and the script-derived bootstrap statistic. Retain the unrounded
value: a printed 0.050 may be greater than .05, while a finite-sample type7 BC
interval excludes zero. Record this as a rule-specific discrepancy rather than
silently forcing agreement or substituting a native interval. The Chapter 4
care paragraph supplies seven such ordinary-p bindings, all matching custom BC
at printed precision and all carrying a reversed member interpretation. This
extends the explicit-BC audit; it does not validate every unlabelled p or the
a/b regressions for those newly bound effects.

Audit component signs even when member identities match: a positive indirect
product can arise from two positive or two negative components. In the care
example, correctly attributed husband-age→wife-housework→husband-care quotations
described wife housework decreasing, while both native a coefficients were
positive. Keep this component-direction issue separate from member-label errors.
When expanding an audit from 7 to 23 quotations, record the overlap and count
only 16 additions; shared b paths and repeated prose citations are not independent
tests. Do not infer completeness of unnumbered or universal significance claims
from successful verification of selected numeric quotations.

For prose without numeric quotations, enumerate its named effects across all
displayed samples and retain omitted effects as coverage controls. Distinguish
an explicit all-stage claim from a statement with an unspecified sample: a
stage counterexample may require qualifying the scope rather than declaring
the whole statement false. Tabulate confidence levels separately, including
non-significant rows. Differences in numbers of significant paths do not test
differences in effect size, lifecycle change, or mechanism dominance. Record
the unit of review (quoted number, effect-stage pair, model, or paragraph) so
counts from these audits are not added as though they measured the same thing.

Once per model, cache native regression rows and GH5 point labels rather than
reopening bootstrap matrices for every prose quote. Verify display coverage
against an independently specified Cartesian product of outcomes, predictors,
mediators, samples and effect codes; row count alone is not coverage. Reconcile
previous quote records by model, native label, path, point and source hash.
Keep displayed-effect and all-parameter contracts distinct: the Chapter 4
eight-plot contract contains 432 effects, whereas 72 models contain 576 specific
indirect effects including 144 undisplayed AA effects. Full plot coverage does
not prove all-parameter or all-prose verification.

Audit comparative clauses as well as the primary path claim. A sentence can
correctly describe one spouse's coefficient while incorrectly assigning the
opposite sign to the other spouse. Bind each comparison to its own equation
and sample. A negative point contradicts a claimed positive point direction,
but does not establish a significant negative effect. Gender beliefs,
compensatory motives, time availability and strict zero-sum constraints require
evidence beyond age, occupation, wage or housework coefficient signs.

For universal null statements, enumerate every referenced effect and sample,
including overlapping citations, and distinguish the displayed column from an
incorrect prose label. Check both the declared interval rule and custom p rule;
a 90% lower bound barely above zero can coexist with a custom p slightly above
.10. Bind the interval to the actual plotting record before calling it a prose
counterexample. Preserve the disagreement rather than promoting it to a robust
discovery. No rejection is not proof of no effect or of another dominant pathway.

For a paragraph enumerating significant effects, compare its complete named
set with the full referenced column/sample universe, not just the quoted rows.
Record both missing and extra effects under each declared threshold. Preserve
positive verification: the enumeration can be correct even when spouse labels
or mechanism explanations are wrong. A 90% match must not be promoted to 95%
evidence, and a check of numerically quoted columns does not cover other columns
mentioned in the same paragraph. Report these as separate adoption dimensions.

Cross-path agreement can arise from shared parameters: two conditional indirect
effects with distinct a paths may share the same moderated b segment. Verify
their native formulas before describing independent corroboration. A significant
high-minus-low contrast does not imply both endpoints exclude zero. If GH5
component products fail a predeclared tolerance, retain every residual as an
unresolved check; do not relax the tolerance or replace stored estimates to force
agreement. Separate structural formula evidence from numerical agreement.

For GH5 product inconsistencies, inspect storage dtype and propagate a declared
ULP bound through the actual arithmetic. Compare original point records and
bootstrap draws separately: draws can satisfy the identity while original-point
records do not. This does not by itself identify a solver or engine defect.
To assess local BC impact without adopting a substitute point, hold the draws
fixed and compare the count below each candidate center. Unchanged counts imply
unchanged z0 and quantile probabilities under the same strict-inequality/type7
contract; they do not resolve point identity or validate another CI algorithm.

When available, cross-check GH5 point vectors against native SAVEDATA RESULTS.
Confirm the OUT save-file declaration, continuous parameter numbering, vector
length and per-token decimal quantization before using the saved ordering.
Match the complete point vector, not only four convenient coefficients. Agreement
localizes an inconsistency to recorded native values rather than a GH5-only
decoding issue; it does not identify solver internals. Keep saved estimates, SEs
and trailing fit-statistics coverage distinct. Do not call a historical engine
artifact a defect in a newer installed version without native evidence.

For a complete endpoint/contrast review, group actual displayed L/H records by
item, panel and model; bind the contrast to its native subtraction formula.
Export basenames may use aliases such as AAM1 for native A1M, so filenames alone
are not parameter identities. Retain the original plotted point/CI labels beside
the HI/LO operands: a plot can show LO/VHI while its summary tests HI minus LO.
Keep the full-draw type7 diagnostic distinct from rounded native intervals and
from a 991-draw historical summary. Count diagnostic combinations separately
from prose errors. A significant difference need not have two significant
endpoints; two predictors mentioned together can have opposite endpoint signs.
Preserve correctly supported sample-specific patterns when drafting corrections,
and do not infer signs or significance from a rounded zero interval boundary.

Maintain two identities when a figure has the wrong path: the actual displayed
parameter and the manuscript/table's intended parameter. A ledger derived from
the displayed LO label follows the former, even if its native subtraction formula
is valid. Rebind intended endpoint claims using the table's native contrast and
validated repair candidates; never transfer significance from the wrong path.
Verify broad stage claims against every displayed table cell, including total
and late-stage findings, while distinguishing selected discussion types from
statistically significant cells. Preserve valid local claims: an accurate total
sample statement may coexist with omitted early-stage evidence. A negative
indirect product does not identify the sign of its mediator equation or establish
behavioral motives without separate component evidence.

For a universal moderation-null claim, enumerate the full declared predictor,
mediator and sample product, including combinations absent from the selected
summary table. A nonzero conditional endpoint does not contradict a null
high-minus-low contrast. For an assertion that all selected contrasts are
significant but neither endpoint is, inspect both the full universe and the
narrow selected subset. Bind counterexamples to actual plotted parameter names
and printed intervals when possible. When later component checks support a
previously unverified mechanism direction, update that dimension positively;
retain causal limits and do not interpret printed p=.000 as an exact zero or
infer the significance of b(W) from its point or from the product interval.

For cross-path robustness prose, build a path-by-sample grid with separate
contrast and endpoint decisions before combining conclusions. One path can have
two nonzero endpoints but a null difference in the total sample, while its
difference is nonzero only in an earlier stage; other paths can show differences
in the total and later samples. Do not splice these results into one common-stage
pattern. Preserve endpoint signs as well as significance: a positive imprecise
low endpoint is not evidence that both endpoints are negative. Correctly supported
null claims in the other member direction should remain alongside the corrections.

Check caption-to-prose member direction separately from figure-internal labels:
two adjacent figure groups may have reversed husband/wife captions even when
their native point/interval parameters are internally consistent. Bind predictor
sets too; a paragraph naming education/occupation may reference age/education
figures. Quantifiers such as most low endpoints are null require an explicit
denominator. A larger absolute point at low support in one stage must not be
extended to another stage where only the high-support endpoint excludes zero.

A sentence can assert no moderation and then acknowledge significant contrasts
in parentheses. Audit the literal contrast claim and the parenthetical endpoint
claim separately. Bind apparent exceptions to the existing table: if the table
already reports the contrast, correct prose rather than manufacturing a missing
table result. Repeated paragraphs referencing the same parameter family count as
claim references, not additional independent effects. For efficiency, build a
complete named-contrast ledger once and reconcile previously audited subsets;
complete numerical coverage does not imply every prose claim has been reviewed.

Before calling endpoint prose wrong, compare its historical display contract
with the unrounded diagnostic contract. Native rounded intervals ending at zero
can yield a non-significant plot alpha while a full-draw type7 interval excludes
zero. Record both and do not attribute all differences to rounding without
checking quantile algorithms. A table-bound contrast contradiction is stronger
evidence than a diagnostic-only endpoint discrepancy. Distinguish an explicit
universal claim from a selected example; a wider contextual screen does not
automatically prove the author intended to enumerate every significant endpoint.

To adjudicate printing effects, read the native CI token and its decimal step,
bind its OUT line/hash to the historical display, and test the diagnostic against
the half-step rounding bin. Compatibility does not recover an unprinted native
endpoint or prove identical quantile algorithms. Record out-of-bin exceptions
even when their significance decisions agree. Deduplicate shared model/parameter
exceptions across figures while retaining display-reference counts; do not turn
two references into two independent numerical problems.

When a newly established interval-contract issue affects earlier draft revisions,
reconcile those drafts against the complete displayed-CI inventory and add a
clear adoption limitation. Do not silently leave earlier diagnostic-only findings
phrased as confirmed historical prose errors. An unmatched named endpoint may
be unplotted, replaced by a different probe, or associated with a wrong path;
it is not automatically a missing artifact. Keep interval-source correctness
separate from the correctness of pairing that interval with its plotted point.

Freeze a section-bounded prose inventory before declaring review completion.
Track evidence available, documented review only, and no indexed evidence
separately. Extracting paragraph text is not reviewing its claims; one bound
claim does not clear every clause in a long paragraph. Keep caption classification
provisional and report sections excluded from coverage. Use the remaining-paragraph
list to drive finite work rather than repeatedly checking the same highlighted cases.

Qualify stronger effects as signed or absolute magnitudes: different predictors
can share an absolute-magnitude pattern while their indirect effects have opposite
signs. A gender difference in which endpoint is individually significant is not
a formal difference between member effects. Preserve correct stage enumerations
while separating them from untested motives or cross-stage robustness claims.

Absence of a significant proxy-variable comparison does not identify a confounder.
Report the tested proxy effects and their sample scope separately from any claim
that age confounding explains a result. A low-probe endpoint containing zero does
not mean the low-probe group has no moderation; moderation is the contrast or
interaction, not the individual endpoint test.

Path-count claims require an explicit unit: basic predictor/mediator/member path,
path-by-moderator combination, or effect-by-stage record. Freeze denominators and
compare contrast-only, contrast-plus-unrounded-endpoint and historical printed
endpoint selection separately. A coincidentally matching count does not identify
the manuscript producer or validate its enumeration. Counts cannot establish a
dominant mechanism, a between-outcome difference, or construct equivalence.

Audit grouped captions against every contained model, not only a representative
basename. Verify moderator coding and interaction operands in native input before
calling a title wrong. A group may contain both rank and age-gap models and need
an inclusive title; that does not establish the age-gap variable as a valid rank
proxy. Preserve wrong-parameter repair choices instead of relabeling an erroneous
plot to make its caption appear consistent.
# Turning reviewed evidence into manuscript candidates

Keep an adoption record separate from the proposed prose. Record the supported
content, narrowed claim and unresolved obligation for each reviewed passage;
removing an endpoint or mechanism sentence does not resolve its statistical
question. Link numeric paragraphs to model diagnostics and data identities.
An empty numeric scope for a method or synthesis paragraph means not enumerated,
not no dependencies. A normal-termination or empty-warning field alone cannot
release inference or manuscript use.

When converting a reviewed passage into an adoption decision, bind each original
sentence and record the fate of its numerical, endpoint and explanatory clauses.
Sentence partition coverage is an indexing check, not evidence that every atomic
claim is valid. A mixed sentence can retain a stage-specific contrast, leave its
endpoint unresolved, and withdraw an unsupported mechanism at the same time.
Distinguish a defensible limitation ("confounding cannot be ruled out") from a
claim of identification ("the pattern is caused by confounding"); do not withdraw
the former as if it made the latter claim. Preserve historical correction evidence
separately from diagnostic-only disagreements. An original table counterexample
can refute a universal null even while endpoint display rules remain unsettled.

For claims such as "most low-probe effects are nonsignificant", enumerate the
declared resources and stages under the actual historical display rule before
editing. A majority can reverse between rounded native intervals and full-draw
diagnostics; preserve a historically supported description with its explicit
contract. If both contracts reject a specifically claimed significant endpoint,
record that local correction without declaring the corresponding HI−LO contrast
nonsignificant. Rebind reference-image and embedded-media hashes when reusing
geometry evidence. A VHI point paired with an HI interval remains a display repair
obligation even if both diagnostic and displayed point orderings agree.

Validate prose path names against a source-hash-bound symbolic path contract,
not only the same actor/partner lookup used to generate the prose. Map outcome
aliases to actual native variable names (for example an analysis key may differ
from the measured variable suffix). A failed alias lookup is a validator issue
until checked; preserve the first receipt and rerun after the justified mapping
fix. Report parsing coverage: plain-arrow validation excludes grouped resources
and narrative sentences without arrows.

When evidence covers only one clause of a mixed paragraph, retain an exact
target-clause replacement and leave the other clauses explicitly unadjudicated.
Assert a unique match in the source paragraph before proposing substitution.
Count distinct model/parameter identities separately from repeated prose references;
two paragraphs repeating the same null result do not provide independent evidence.

A bibliography match or publisher overview establishes a method reference's
identity and scope, not its endorsement of a particular confidence level, probe
selection or display filter. Retain page-level support for attributed rules.
Check fetched content signatures and final URLs: a nominal PDF link may return
an abstract HTML page. Label it accordingly rather than treating it as full text.

Method-section corrections must distinguish intended reporting rules from
historically executed behavior. Do not describe an unimplemented unified probe
or CI rule in the past tense. If a synthesis claim lacks a defined denominator,
enumeration or formal comparison, retain its specific path evidence and remove
the unsupported ranking; do not invent replacement counts. Verify cited method
attributions separately from the computational rule they are claimed to justify.

An R-produced table may use re-computed bootstrap intervals while an accompanying
plot uses printed OUT intervals. Bind each candidate claim to its actual producer:
agreement with table symbols can coexist with printed-zero interval ambiguity.
For tidyselect ranges mixing a named start with a numeric end, resolve positions
after joins; a pre-join column count can silently truncate the selected draws.
Never label omitted draws as failed replications without separate evidence.

Check contrast intervals as well as plotted endpoints before carrying significance
claims into replacement prose. A matching endpoint display does not validate a
HI−LO contrast decision. When a candidate uses diagnostic bootstrap intervals,
state that contract inside the proposed text or its inseparable table note;
an external packet preamble can be lost during copying. Native printed-zero
boundaries require the same rounding caution for contrasts as for endpoints.

When two figure groups have swapped member labels, compare their complete
resource inventories before proposing a move. A two-panel group and a three-panel
group are not interchangeable by merely swapping captions. Record each media hash,
actual X→M→Y path, destination caption and paragraph; flag any relocated resource
not covered by the prose. Retaining historical media preserves its numerical
content, not its scientific acceptance. Layout and cross-reference validation
remain necessary when applying the candidate in an isolated document.

Bind replacement prose to the original DOCX hash and exact paragraph text, then
export the original, proposed wording, decision and supporting model/parameter
keys together. Reconcile local evidence with the complete effect ledger and show
the full sample-stage matrix, including nonsignificant stages. A proposed
paragraph must not silently inherit unverified endpoint, mechanism or member
comparison claims from its original. Mark omitted, unresolved clauses explicitly.
Keep the interval contract alongside the candidate: a diagnostic type7 decision
does not become a native historical decision merely because it appears in prose.
Candidate preparation, manuscript insertion and scientific adoption are separate.

## Closing endpoint obligations without transferring the wrong evidence

Use three distinct evidence states for each intended path and sample: a matching
historical figure, a historical figure containing another path, and no figure in
the frozen inventory. Do not drop the latter two when counting review coverage.
Hash both the reference image and the embedded Word media, including rejected
wrong-path figures. A correctly parsed figure of AA cannot substantiate an AP
sentence; a PA figure cannot substantiate PP merely because its signs look similar.

For a wrong-path or unplotted case, read the intended named HI/LO parameters from
the existing OUT, retaining its hash, exact CI tokens and line numbers. Compare
these values with an existing repair candidate if one exists. Label the result as
intended-parameter evidence, never as evidence that the original figure was correct.
This can settle the numerical clause before rendering while leaving the figure
repair and scientific inference gates open. No new fit or bootstrap calculation
is required to make this distinction.

Validate statements about all endpoints against the declared universe and the
contrast-selected subset separately. Unplotted wage endpoints can exclude zero
even when their HI-minus-LO contrasts do not; they are not additional moderation
discoveries. Conversely, every printed endpoint in a figure family may include
zero while some differences exclude zero. Preserve a historically supported
endpoint description without allowing its reporting filter to erase differences.

Keep named point signs separate from points rounded to zero in the historical
display. Also compare magnitude order within each sample: a low-end advantage
in the total sample can reverse at the stage where the contrast is significant.
Do not combine the total-sample endpoint result and the stage-specific contrast
into a single stronger-effects claim. A VHI/VHI figure has a different probe
contract from HI-minus-LO even though its own point and interval match; a VHI/HI
figure has an additional point/interval mismatch.

When updating the adoption entry, preserve the earlier sentence obligations and
the source file for each decision. Endpoint-only replacement clauses are not full
paragraph replacements. Use an independent readback to check the exported labels
and intervals against raw OUT and verify that earlier decisions, model links and
source hashes did not change. Report scoped adjudication complete separately from
remaining rendering, exact-interval, provenance and inference obligations.
