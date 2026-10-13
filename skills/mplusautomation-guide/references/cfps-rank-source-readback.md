# CFPS rank/score source technical readback（Windows）

## 目的

当 rank/score producer 已经存在时，先把 source identity、`.out` 哈希、R 的真实
`readModels` 绑定、代表性 consumer 输入和隔离 corrected-score candidate 读回，
再决定是否允许下游 consumer。技术 readback 与科学接受必须分开。

## 本轮证据

只读报告：
`reports/cfps_rank_source_readback_20261004/cfps_rank_source_readback_audit_v1.{json,md}`。

- 16 个 source 的 `.out` SHA 全部一致，16/16；384 个 consumer 均有 source binding，未绑定 0。
- 12 个 source 与当前输入兼容；4 个原始合同中的 rebuild-required source 已有隔离 corrected score candidate，证据文件 4/4 完整。
- 代表性 consumer 输入逐值一致 280 个；历史输入差异 8 个，保留为敏感性边界。
- `rank_dependent_refresh_readiness.json` 因 `MI_DIAGNOSTICS_NOT_ACCEPTED` 仍为 `ready=false`，不能物化下游 consumer。

## 处置规则

技术 readback 通过不等于正式采用。保留 consumer 提交开关为 false，不能因为已有
candidate CSV 或 `.out` 就写入正式 MI 数据。只有 MI 科学接受、pooling/LRT 合同、
estimand 和资源准入同时通过，才可在隔离命名空间执行下游 Mplus；旧成功 `.out` 继续
复用，不重复估计。每个实际执行必须保存 input/output/data 哈希、Mplus 正常终止、
MplusAutomation readback 和父链证据。
