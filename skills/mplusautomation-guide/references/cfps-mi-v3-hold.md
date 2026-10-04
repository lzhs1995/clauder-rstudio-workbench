# CFPS MI v3 科学暂缓

10 份 MI v3 文件的原生列/行回读成功，不等于可以物化下游模型。当前收入派生仍有 14/40 个个人收入插补负值、184/900 个家庭收入插补负值和 1/40 个固定阈值二分类不一致；TECH8 公开到 600 次时 PSR=1.111，收敛证据仍不足。

Windows 复盘应固定 `scientific_acceptance=false` 和 `downstream_submission_allowed=false`，不截零、不取绝对值、不无依据重编码，也不因等待而重提 MI consumers。完成收入定义、支持范围和更充分链诊断后，才按依赖顺序物化 51 个 producer 和 384 个 consumer。

证据：`reports/cfps_mi_v3_hold_20261004/cfps_mi_v3_hold_contract_v1.{json,md}`。

本轮通过原生 ClaudeR/RStudio 读取源 `.dta` 后确认：`pinc212`（绝对收入）观测范围
为 0–18.864 万元，`finc12`（家庭收入）观测范围为 0.0005–112 万元，观测值均无
负数；`pinc12` 为 1–5 的相对收入等级。该读回支持把 MI 中的负 `finc12`/`pinc212`
视为支持范围问题，但不允许事后截零或取绝对值。回执：
`reports/cfps_mi_v3_hold_20261004/cfps_income_scale_readback_v1.md`。

复盘原始 R 规格时还要检查 `DATA IMPUTATION` 的 `VALUES` 约束是否覆盖所有有界
收入变量；仅约束 `pinc12` 而未约束 `finc12`，不能被误报为已完成的支持范围合同。
