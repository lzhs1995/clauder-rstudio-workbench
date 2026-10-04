# CFPS 历史重现候选包

在历史论文复现中，先把已完成的逐单元格审计结果编成候选包，再决定是否需要估计。使用
`build_cfps_historical_reproduction_candidate_20261004.py` 读取既有
`cfps_historical_decision_draft_v1.csv`，为每行增加候选通道、复原动作和科学门状态。

候选通道必须至少区分：

- `HISTORICAL_REPRODUCTION_CANDIDATE`：历史 producer、输出和论文显示值已有技术证据；
- `HISTORICAL_REPRODUCTION_WITH_CURRENT_SENSITIVITY`：历史显示值可复原，但当前输入差异只能作为敏感性/限制；
- `HISTORICAL_REPRODUCTION_PENDING_ROUNDING`：值已绑定，但需先冻结显示舍入合同；
- `HISTORICAL_LIMITATION_OR_DEFERRED`：历史上游或 sidecar 不足，保留限制或延期，不自动重提；
- `SCIENTIFIC_REVIEW_REQUIRED`：技术链已接通但需要逐单元格研究设计/作者裁决。

候选包的硬性边界：

1. 原始 R、Mplus、数据和 DOCX 只读；所有 CSV/JSON/Markdown 放在新的报告目录。
2. 候选包不修改 manuscript，不改变 CFPS gate，不因开放单元格自动提交 Mplus。
3. 每一行必须保留 `model_id`、`.out`、脚本 lineage、原始 disposition 和 `author_final_decision`；不得用同名输出替代身份。
4. 历史复原候选不等于修正数据的科学有效性。MI、LRT、舍入、图表和最终 PDF/NLM 仍须分别验收。

本次 Windows 实测入口与证据：

- 脚本：`work/pp_lgcm_reconciliation_20261001/build_cfps_historical_reproduction_candidate_20261004.py`；
- 机器合同：`reports/cfps_historical_reproduction_candidate_20261004/cfps_historical_reproduction_candidate_v1.json`；
- 人工审阅：同目录的 `.md`；
- 本次 10,936 行只读整理的 Mplus 新提交数为 0。

对历史初稿目标明确的 156 个历史/当前版本差异，可在技术核验通过后单独冻结
历史显示版本，把当前输入保留为敏感性说明。当前合同为
`reports/cfps_historical_version_adoption_20261004/cfps_historical_version_adoption_v1.{json,csv,md}`；
它只关闭 20260214 初稿的复现版本选择，不代表修正后论文的 scientific release。
Table 4.2 的 16 个 AIC/BIC 舍入单元格另有
`cfps-rounding-contract.md` 和 `reports/cfps_rounding_contract_20261004/`，避免
把显示精度问题误当成缺少 Mplus 输出。

该流程适合在磁盘恢复、断电或异步队列失效后先恢复“已有成功结果”，避免把长时间估计误当成复现进度。
