# Movers–Stayers LTA workflow

MS-LTA（Mover–Stayer LTA）在普通 LTA 之上区分转移结构不同的高阶组。常见解释是 stayer 与 mover，但 mover 组的自由转移矩阵允许落在对角线，因而 mover 不是“必然发生类别变化”的人。它用于描述转移异质性，不能因为队列标签写成 MS-LTA 就自动认定语法确实包含 movers/stayers。

## 1. 先按语法分类

以 Mplus 输入语法为准检查：

- 是否有 `G(2)` 或等价的高阶 mover/stayer 类别；
- 是否有 `G#1`、`G#2` 的 group-specific transition 结构；
- stayer 的转移矩阵是否被固定为对角线 1、非对角线 0；若使用有限的 `-10/+20` 等 logit 约束，则只是数值上逼近 0/1，必须在 receipt 中标为近似约束；
- mover 的转移概率是否自由估计；
- 是否有 `KNOWNCLASS`、multiple-group 或随机截距等其他结构。

队列 metadata 只是导航信息。实际语法优先于队列标签。

## 2. 估计与诊断

MS-LTA 常见问题是 mover 转移单元稀疏和多项 logit 的完全分离。每次运行要分别记录：

1. mover/stayer 类别基数；
2. 每个 group 的转移概率和行和；
3. 多项 logit 的估计、自动修复或固定参数；
4. warning、未定义参数、标准误和边界值；
5. Step-1 savedata 到 Step-3 输入的逐字段关系。

Mplus 自动修复参数必须作为诊断写入 receipt，不能悄悄当作普通成功。

## 3. 第七章对应实现

q1629 的实际语法含 `G(2)`、`G#1` movers 和 `G#2` stayers，且为两期（16a20）`c1(4) c3(4)`；这不是本次 replay 的全四波 MS-LTA，故按语法应归入 MS-LTA。不要把这三个潜变量的声明折算成一个平坦的“类别数”：readback summary 的聚合潜变量字段不能替代逐项语法分类。其 Step-3 归档输入在 N=7008 上完成新鲜复现，但四个 mover multinomial logits 被 Mplus 自动修复；这属于 `FRESH_EXACT_REPLAY_WITH_DIAGNOSTIC`，不是没有条件的 clean pass。

动静模式图表使用归档 `readModels()` 对象和独立 R 脚本生成；最终 DOCX 中的 F30/F31 必须同时核对节点标签、比例、颜色和流量方向。

## 4. 解释边界

- mover/stayer 是潜在高阶模式，不等于简单把 most-likely class 的相邻差异计数后硬编码；
- 如果改用硬分类计数进行描述，必须把它标作描述性近似，并与 MS-LTA 潜变量结果分开；
- MS-LTA 的回归扩展需要足够的 mover/stayer 和转移单元基数；稀疏时应优先报告描述性结果并记录未估计的路径。

## 5. 验收清单

- [ ] 输入语法和 family 标签一致；
- [ ] movers/stayers 的约束被明确审计，并区分精确 0/1 与有限 logit 近似；
- [ ] 区分四波 MS-LTA 与 q1629 的两期（16a20）MS-LTA；两期模型若单独使用，需把它作为额外约束或简化扩展论证，不能直接当作标准多期证据；
- [ ] 自动修复参数和 warning 已进入 receipt；
- [ ] 图表和正文的模式名称、样本比例、流向一致；
- [ ] q1629 的 panel lineage 与 archived replay 边界已明确；
- [ ] 不把普通 multiple-group LTA、RI-LTA 或错误语法计入 MS-LTA。

## 参考来源状态

初稿引用 `Vermunt2004`、`Muthen2022`、`Kaplan2008`、`Moore2025`、`Hagman2021` 和 `QiuHaoZheng2023`。Vermunt2004 的 Zotero key 为 `46A2NJNG`，目前只确认 key/URI 与外部 repository 证据，未声称读取 Zotero 附件。`Muthen2022` DOI 为 `10.1037/met0000370`。
