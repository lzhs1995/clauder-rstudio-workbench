# CFPS rank/score source 处置

先按 source 文件而非下游模型计数。当前 16 个 rank/score source 共有 384 个 consumer 引用；12 个 source 与当前输入兼容，保留既有输出并等待 score readback；4 个 source 明确需要 rebuild，所有对应 consumer 暂不提交。

保留 source 输出哈希、PID 集合、个人/夫妻身份、tie/availability 规则和 consumer 清单。不要为了推进下游而静默补写排行、截断值或假定一人一家庭；source readback 通过也不等于 rank 规则和正式论文采用已闭合。

证据：`reports/cfps_rank_source_disposition_20261004/cfps_rank_source_disposition_v1.{json,md}`。
