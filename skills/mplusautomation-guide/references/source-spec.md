# 通用 source_spec：CSV / DTA 到有序 Mplus DAT

`scripts/source_spec.R` 的 `prepare_mplus_source(spec, output_dir)` 复用 APIM v2 的 `apim_v2_read_source()` 与 `column_map`（`canonical = source`）约定。它只准备数据和 `DATA/VARIABLE` 片段，不生成模型、不启动 Mplus、不筛行、不排序、不插补、不推导量表或夫妻身份。所有输入行按原顺序保留；只输出 `columns` 显式列出的列。

目前仅支持 `csv` 与 `dta`。注册表的 `source_spec` 仍由 W4 登记；本入口不宣称实现 `archived_dat`。

```r
source('skills/mplusautomation-guide/scripts/source_spec.R')
spec <- list(
  schema_version = 1L,
  data = normalizePath('private-input/source.csv'),
  data_mode = 'csv',
  data_expected_sha256 = digest::digest('private-input/source.csv', algo='sha256', file=TRUE),
  columns = c('y', 'x'),
  column_map = c(x='source_x', y='source_y'),
  missing = 'NA',
  missing_codes = list(x=c('', '-9'), y=character()),
  missing_value = -999
)
receipt <- prepare_mplus_source(spec, normalizePath('private-output', mustWork=TRUE) |> file.path('new-source-run'))
```

示例中的 SHA 计算仅展示接口；正式使用应先独立冻结输入 SHA，再把核准值传入。输出目录必须是绝对路径、全新且与来源目录分离。已有目录（即使为空）或文件均拒绝，不覆盖、不清理失败产物。输入前、读取后和写完回执前核源 SHA；变化即失败，不能自行重算期望 SHA 后续跑。

`columns` 是最终 DAT 与 Mplus `NAMES` 的唯一列序。名称必须以字母起头、后续为字母/数字/下划线，最多八个字符，大小写不敏感唯一；源字段可较长，通过 `column_map` 显式换名。映射必须一对一，不能与未映射字段撞名。未选取的字符串列不会输出；选取列必须是数值或可转换为有限数值的字符串，日期/时间及非数值编码须在研究上游显式处理。数值列使用 IEEE double；本入口不把字符 ID 编号为数值，也不认证超出 double 精度的长整数身份。

CSV每个逻辑记录必须与表头字段数一致，拒绝多余字段导致的隐式行名、短行自动填空和空白记录；引号内的逗号及换行按CSV规则读取。已加载适配源码在写入前和回执前均重新核SHA，回执绑定实际加载版本。

`missing_codes` 必须逐一声明全部输出列；`character()` 或 `numeric()` 明确表示该列没有额外缺失码。可选 `missing` 是沿用 APIM 规则的全局码，默认空向量；CSV 的空字段或字面 `NA` 应按源合同显式声明，不能因负号推断缺失。DTA 普通与 tagged NA 统一缺失，值标签移除但底层编码保留。缺失重码之后仍存在与 `missing_value` 相同的观测值时拒绝，避免把合法值写成缺失。

产物均在调用者指定的私有目录：

- `data.dat`：无表头、无行名、空格分隔，有限数值用17位有效数字输出，缺失写显式 sentinel；写后读回逐列核对数值、缺失和形状。
- `column_order.txt`：每行一个列名，UTF-8 无 BOM、LF、末尾换行；文件原始字节的 SHA256 就是列序 SHA，不依赖 R 序列化。
- `data_block.inp`：只有相对 `DATA: FILE = data.dat`、有序 `NAMES` 与 `MISSING` 声明。它可与已审模板接合；本函数不编辑模板、不核模型的变量语义。
- `source_receipt.json`：源/DAT/列序/数据片段/代码 SHA、行列数、列名、逐列缺失计数与未建模边界。无输入绝对路径、逐行值或个体 ID。它是准备回执，不是家族真实换源验收回执，不能直接放进 `assets/real_data_receipts`。

新合成测试 `test_source_spec(skill_root, out_dir)` 位于已登记的 `scripts/test_apim_v2_data_adapter.R`。同一合成数据换列名、换源列序后分别写 CSV 与 DTA，要求 DAT 和列序 SHA 一致；同时覆盖映射碰撞、非数值、sentinel 碰撞、非法列名、错 SHA、来源变化与已有输出拒绝。家族 CI 以独立步骤运行，输出 `source-spec-ci`。测试不调用统计引擎，不能代表真实数据或 Mplus 运行成功。
