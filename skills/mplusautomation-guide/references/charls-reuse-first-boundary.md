# CHARLS reuse-first 与科学采用边界（Windows）

CHARLS 的 registry、FCS 成员、Mplus `.out` 和 pooled CSV/RDS 必须先作为历史产物验收，
再决定是否新增 Mplus。`RStudio 8787` 在线、Mplus 正常终止或 `readModels()` 能读回，
都只证明传输/计算链健康，不能自动关闭科学采用门。

当前 Windows 清点脚本：

```text
work/pp_lgcm_reconciliation_20261001/audit_charls_reuse_first_20261004.py
reports/charls_reuse_inventory_20261004/charls_reuse_inventory_v1.{json,md}
```

脚本只读取 `PRIMARY_ADJUSTED_CURRENT.json` 与 `CLASS_SENSITIVITY_CURRENT.json`，逐一检查
其引用文件的存在性和 SHA-256，不启动 RStudio/Mplus。当前 90/90 个引用文件存在，
但 SD/Gender 的自动固定参数、边界规格、MI 相容性和 estimand 仍未通过正式采用。

每个候选至少要分开记录：

1. `new_Mplus_estimates`、Mplus return code、最终输出诊断和 `readModels()` 读回；
2. FCS 成员/链诊断、类别标签与成员 crosswalk、边界或自动修正；
3. pooled 结果、Monte Carlo 误差和论文 estimand；
4. `scientific_acceptance` 与 `formal_adoption`。

边界未闭合时复用和对账已有产物，记录为 `SCIENTIFIC_HOLD`，不要为了刷新 registry
而重跑同一模型，也不要把仅存在输入模板的模型排入长队列。
