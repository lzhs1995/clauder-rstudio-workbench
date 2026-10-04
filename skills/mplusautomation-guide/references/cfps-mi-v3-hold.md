# CFPS MI v3 科学暂缓

10 份 MI v3 文件的原生列/行回读成功，不等于可以物化下游模型。当前收入派生仍有 14/40 个个人收入插补负值、184/900 个家庭收入插补负值和 1/40 个固定阈值二分类不一致；TECH8 公开到 600 次时 PSR=1.111，收敛证据仍不足。

Windows 复盘应固定 `scientific_acceptance=false` 和 `downstream_submission_allowed=false`，不截零、不取绝对值、不无依据重编码，也不因等待而重提 MI consumers。完成收入定义、支持范围和更充分链诊断后，才按依赖顺序物化 51 个 producer 和 384 个 consumer。

证据：`reports/cfps_mi_v3_hold_20261004/cfps_mi_v3_hold_contract_v1.{json,md}`。
