# Chapter 7 replay map

该映射把第七章的研究问题、模型家族、代码入口、输出和验收边界连接起来。路径使用逻辑名称；具体 Windows 路径和哈希保存在项目级 replay manifest，不写入可共享 skill。

## 总体链条

```text
Stata data cleaning
  → panel/predata inputs
  → R [[init]] template
  → MplusAutomation model generation
  → licensed Mplus estimation
  → readModels()/savedata/CPROB
  → R second-stage logistic and plotting
  → Word/DOCX and PDF
  → NLM source-specific A5 review
```

## 家族映射

| 家族 | 主要目的 | 典型输入 | 典型输出 | 第七章用途 |
|---|---|---|---|---|
| LPA/LCA | 单期类别识别 | 六个代际关系指标 | fit indices、条件均值/概率、CPROB | 类别命名与类别比例 |
| LTA | 跨期类别转移 | 多波次 LPA 测量结构 | transition matrix、Step-3 savedata | 核心转移描述 |
| MS-LTA | mover/stayer 异质性 | G(2)、G#1/G#2 语法 | mover/stayer probability、流量图 | 动静模式描述 |
| R-side logistic | 机制和调节效应 | most-likely class 与转移状态 | 390 个二元模型、OR/CI、边际效应 | 直接效应和调节效应 |

## 影响因素路线选择

初稿比较了三条路线：

1. Mplus 中对潜在转移概率直接建模（VAM/三步法和交互项）；
2. 合并为少量五分类转移结果后做多元 logistic；
3. 按转移方向拆成多个二元 logistic。

最终采用路线 3，理由必须同时写出：样本稀疏、Mplus 频繁不收敛、VAM 交互项编码复杂、路线 2 过度折损转移方向信息。该选择并不等于硬分类没有误差；正文必须保留 Entropy 较高但分类误差和标准误风险仍存在的限制说明。

## 证据边界

- q1604：LTA Step-3 归档输入新鲜复现通过；
- q1629：MS-LTA Step-3 归档输入新鲜复现并保留自动修复诊断；
- R-side logistic：390/390 fresh convergence，23,904/23,904 coefficient keys，最大差约 `4.9738e-14`；
- q1604/q1629 当前 panel→Step-1→Step-3 lineage：仍是 `PARTIAL_LINEAGE_CONFIRMED_NOT_CLOSED`，原因包括旧/新列宽、SIBO、PIDN/FID 和 AGEC/SIOPC 数值投影。

## 可复现目录合同

每批复盘目录必须有：

- `inputs_manifest.json`：输入路径、大小、SHA256；
- `spec_manifest.json`：模型 family、模板、参数和 seed；
- `run_receipt.json`：Mplus 状态、warning、输出解析；
- `derived_manifest.json`：R 读取、表格和图形；
- `manuscript_binding.csv`：表/图/正文位置；
- `acceptance.md`：通过、诊断或未闭合边界。

## 未来扩展规则

更换研究数据或指标时，先复制该映射并替换变量字典、时间点和类别命名；不要复制旧 `.out` 或直接复用旧 CPROB。任何 new model 都必须先通过 synthetic smoke，再进入真实数据批次。
