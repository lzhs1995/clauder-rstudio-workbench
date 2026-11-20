# CFPS MI v3 科学暂缓

MI 文件的原生列/行回读成功，不等于可以物化下游模型。准入仍须核对收入派生的支持范围、固定阈值二分类一致性以及 TECH8 链诊断；实际违规计数和诊断值保留在私有回执中。

Windows 复盘应固定 `scientific_acceptance=false` 和 `downstream_submission_allowed=false`，不截零、不取绝对值、不无依据重编码，也不因等待而重提 MI consumers。完成收入定义、支持范围和更充分链诊断后，才按依赖顺序物化 51 个 producer 和 384 个 consumer。

证据：`reports/cfps_mi_v3_hold_20261004/cfps_mi_v3_hold_contract_v1.{json,md}`。

原生 ClaudeR/RStudio 的源 `.dta` 回读用于核对相对收入等级、个人绝对收入与家庭收入的尺度、支持范围及缺失定义；实际观测范围保留在私有回执中。若插补值违背经确认的支持范围，应修复插补规格，不能事后截零或取绝对值。回执：
`reports/cfps_mi_v3_hold_20261004/cfps_income_scale_readback_v1.md`。

复盘原始 R 规格时还要检查 `DATA IMPUTATION` 的 `VALUES` 约束是否覆盖所有有界
收入变量；仅约束 `pinc12` 而未约束 `finc12`，不能被误报为已完成的支持范围合同。
