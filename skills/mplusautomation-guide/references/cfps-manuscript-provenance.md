# CFPS 初稿正文 provenance 综合合同

综合回执：
`reports/cfps_manuscript_provenance_20261004/cfps_manuscript_provenance_v1.{json,md}`。

它把表格、图形、源文件和运行态分成四个独立证据层：

- 10,936 个表格单元格中，10,267 个有历史 `.out`、model identity 和 R lineage，已冻结为初稿历史复现候选；669 个明确标为 limitation/deferred。它们进一步冻结在 `cfps_deferred_recovery_queue_20261004`：381 个上游依赖阻塞、165 个历史 sidecar 无法唯一恢复、116 个历史估计失败、7 个未准备。它们不因 scientific adoption 未关闭而触发重复估计。
- 正文 18 个 PNG/SVG 逻辑图形中，16 个按 SVG 文本标签精确回绑到既有 producer 和指定 R script 动态命名模板；2 个图 3.1 图形保留为六份 PP-LGCM script 之外的历史候选。
- 图 3.1 的第二层来源边界审计见 `reports/cfps_figure_provenance_20261004/cfps_figure31_source_boundary_v1.{json,md}`：六份 canonical script 的 sample-selection/path-diagram 生成证据均为 0/6；相邻 GMM/LTA 轨迹图不升级为图 3.1 producer。
- Rank/score 技术 readback 见 `reports/cfps_rank_source_readback_20261004/cfps_rank_source_readback_audit_v1.{json,md}`：16/16 source SHA 一致、384 个 consumer binding 完整、4 个隔离 corrected-score candidate 有证据；但 MI 诊断门仍关闭，consumer 不得提交。
- 八个受保护源文件（六份 R script、正文和 Appendix DOCX）字节、大小和哈希均未改变。
- 运行态只证明 RStudio 8787 在线和目标队列当前没有 Mplus；第四章外部审计进程必须按父链/工作目录单独归档，不能计入 CFPS/CHARLS。

正式发布仍需独立关闭 CFPS 的 669 个限制/延期、MI/LRT/rank 和图形剩余候选，再接续 CHARLS formal adoption。最终 PDF 冻结后才运行确切最终稿的 PDF-only NLM 三审三校，之后才将 guide 从 draft 改为 release candidate。
