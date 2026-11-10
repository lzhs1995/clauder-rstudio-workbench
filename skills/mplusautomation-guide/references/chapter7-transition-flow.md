# Explicit transition-flow data and Sankey rendering

`scripts/ch7_transition_flow.R` separates two small operations:
`ch7_transition_flow_data()` returns nodes, links, measurement metadata and
quality checks using base R; `ch7_transition_sankey()` returns a networkD3
widget. Neither runs Mplus, opens a browser, exports a file or installs a package.

The source contract deliberately avoids an automatic `readModels()` adapter:
the caller must select and record the correct posterior/conditional tables,
align classes by their meaning, and supply the long tables below. Successful
rendering proves neither that selection nor estimation, class equivalence,
fresh source swapping, manuscript adoption, or closure of historical F30/F31.

## Inputs and meanings

All identifiers are explicit non-empty strings, including numeric-looking class
IDs. `wave_map` row order declares chronology; each wave's `class_map` row order
declares node order. Two or more waves and different class counts per wave are
supported. No year, four-class assumption, or class-ID suffix is inferred.

| Input | Required columns / meaning |
| --- | --- |
| `wave_map` | `wave`, `label`; unique wave IDs in chronological order |
| `class_map` | `wave`, `class`, `semantic`, `label`, `colour`; one row per node; same semantic ID retains the same label and explicit hex colour across waves |
| `distribution` | `wave`, `class`, plus `count` or `proportion` according to mode |
| `transitions` | `from_wave`, `from_class`, `to_wave`, `to_class`, `probability`; all adjacent-wave class pairs, including explicit zeroes |
| `source_id` | Logical provenance identifier, bound to the selected output/parser and table hashes in the private project manifest |

Choose the measure explicitly:

- `mode="posterior_count", condition="overall"`: link value is the source
  estimated posterior count multiplied by the transition probability. Node
  percentages divide those counts by their own wave's total. These are
  **posterior-weighted expected flows**, not observed individual transitions.
- `mode="mover_scaled", condition="G=declared_movers", scale=<explicit>`:
  node weight is `round(proportion * scale)`, using R's rounding rule; link value
  multiplies that weight by the mover-conditional transition probability.
  Percentages retain the input conditional proportions. The scale is arbitrary
  and must never be labelled actual people or a measured sample size. The
  condition must identify the selected mover group, not merely a class number.

No probability is rounded or normalized. Missing keys/edges, duplicate pairs,
unknown classes, reverse/non-adjacent transitions, nonfinite inputs and
probabilities outside `[0,1]` are rejected. A missing edge is not filled with 0.
Row sums, conditional distribution sums and incoming/outgoing flow differences
are reported with the explicitly recorded absolute `tolerance` (default `1e-8`).
Imbalance yields `LIMITED`, preserving all values; rendering warns but does not
repair data. Rounding alone can create small residuals. A caller comparing
printed probabilities should set and document a tolerance derived from the
original printing precision, not widen it to erase a numerical discrepancy.

Node heights are controlled by networkD3's incoming/outgoing link totals, not by
an independent node-count field; percentage labels show the declared
distribution. Consequently a limited graph can visibly disagree with those
labels. Keep the quality report beside any exported figure.

## Minimal synthetic example

```r
source("scripts/ch7_transition_flow.R") # path relative to the skill root
waves <- data.frame(wave=c("entry", "later"), label=c("Entry", "Follow-up"))
map <- data.frame(wave=rep(waves$wave, each=2), class=rep(c("k10", "k20"), 2),
  semantic=rep(c("near", "far"), 2), label=rep(c("Near", "Far"), 2),
  colour=rep(c("#2A9D8F", "#264653"), 2))
d <- map[c("wave", "class")]; d$count <- c(20, 30, 22, 28)
t <- data.frame(from_wave="entry", from_class=rep(c("k10", "k20"), each=2),
  to_wave="later", to_class=rep(c("k10", "k20"), 2),
  probability=c(.8, .2, .2, .8))
flow <- ch7_transition_flow_data(d, t, waves, map,
  mode="posterior_count", condition="overall", source_id="synthetic_two_wave")
flow$quality
widget <- ch7_transition_sankey(flow) # requires networkD3 and jsonlite
# Explicit optional export; choose a fresh project-owned path:
# htmlwidgets::saveWidget(widget, "transition_flow.html")
```

Colours follow the source semantic class; explicit zero-flow edges are
transparent. Default labels include the declared wave label; `show_wave=FALSE`
omits it. The renderer retains width 40, padding 20, font size 13, iterations 0
and `sinksRight=TRUE` from the archived rendering style. Export settings,
browser selection, fonts, crop and manuscript figure binding remain separate.

## Evidence boundary / 证据边界

历史来源摘要保存在私有项目证据中：普通图使用 posterior count × probability；
Movers 图使用显式缩放后取整的条件分布。历史单位误标没有成为新接口默认值。
公开代码和例子不带个人路径、原研究数值、原HTML或RDS。

共享CI仅一次注册 `test_ch7_transition_flow`，覆盖合成改名、波次数/类别数变化、
来源颜色、方向、两种量纲、缺映射、非有限数值和不守恒不补值。widget载荷检查
不等于浏览器/PNG验收；原稿F30/F31与新数据估计仍须独立证据。
