# CFPS LRT/D2 数据身份与 MI 语义交叉核验

LRT/D2 的第一层是确认每个 null/alternative 输出指向的真实 `.dat` 文件存在、字节数和 SHA-256 与既有合同一致；第二层是确认它确实对应主模型的同一 MI 成员。第一层通过不代表第二层通过。

当前只读证据：

- `reports/cfps_lrt_data_identity_audit_20261004/cfps_lrt_data_identity_audit_v1.{md,json}`：13 个完整 10 对家族的 260 个 LRT `.dat` 记录真实文件哈希全部通过。
- `reports/cfps_lrt_semantic_review_20261004/cfps_lrt_semantic_review_v1.{md,json}`：7 个 D2 候选与主模型 MI 成员逐个交叉核验，只有 7/70 通过，63/70 失败；差异集中于 `adl12`、`cdar12`、`finc12`、`pinc12`、`pinc212`、`sat12`，部分家族还有 `pinc412`。

因此 D2 候选的打印数值不能直接释放为正式 LRT p 值。正式比较必须同时满足：同一插补成员、同一数据版本、同一观测样本/聚类、同一变量声明、完整嵌套关系、合法的 MLR/D2 合并。发现跨成员数据绑定错误时，保留既有输出和审计结果，修复输入合同后才允许在隔离目录重估；不能通过挑选“更显著”的候选成员来修复。

MplusAutomation 的 `readModels()` 或输出解析成功只说明文本可读，不能替代这两层数据身份和语义检查。
