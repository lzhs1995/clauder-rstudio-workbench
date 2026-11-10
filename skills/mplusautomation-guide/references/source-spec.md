# 通用 source_spec：CSV / DTA 到有序 Mplus DAT

`scripts/source_spec.R` 的 `prepare_mplus_source(spec, output_dir)` 复用 APIM v2 的 `apim_v2_read_source()` 与 `column_map`（`canonical = source`）约定。它只准备数据和 `DATA/VARIABLE` 片段，不生成模型、不启动 Mplus、不筛行、不排序、不插补、不推导量表或夫妻身份。所有输入行按原顺序保留；只输出 `columns` 显式列出的列。

目前仅支持 `csv` 与 `dta`，已在 `families.json` 的 `source_spec` 适配层登记；本入口不宣称实现 `archived_dat`。独立 `test_source_spec()` 登记为共享数据准备测试，不计作任一家族的真实换源或原生引擎验收。

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

`columns` 是最终 DAT 与 Mplus `NAMES` 的唯一列序。名称必须以字母起头、后续为字母/数字/下划线，最多八个字符，大小写不敏感唯一；源字段可较长，通过 `column_map` 显式换名。映射必须一对一，不能与未映射字段撞名。未选取的字符串列不会输出；选取列的非缺失值必须是有限数值或十进制数值字符串，支持首尾空白、正负号、小数点和 `e/E` 科学计数法。十六进制（如 `0x1A`）、`Inf/NaN` 和非数值字符串不能作为观测值输出；日期/时间须在研究上游显式处理。数值列使用 IEEE double；本入口不把字符 ID 编号为数值，也不认证超出 double 精度的长整数身份。

CSV每个逻辑记录必须与表头字段数一致，拒绝多余字段导致的隐式行名、短行自动填空和空白记录；引号内的逗号及换行按CSV规则读取。已加载适配源码在写入前和回执前均重新核SHA，回执绑定实际加载版本。

Mplus DATA 规定单条记录最长为 10,000 字符。本入口的 DAT 只包含 ASCII 数字、符号和空格，按每行不含末尾换行的字节数检查；超过 10,000 字节时在创建输出目录之前拒绝，不截断或拆分记录。回执记录 `max_record_bytes` 和固定的 `record_length_limit_bytes=10000`。[Mplus 用户手册，第 15 章 DATA](https://www.statmodel.com/HTML_UG/chapter15v8.htm)

`missing_codes` 必须逐一声明全部输出列；`character()` 或 `numeric()` 明确表示该列没有额外缺失码。可选 `missing` 是全局码，默认空向量。此入口复用 APIM 的读取和换名接口，缺失重码在入口内独立处理，不改变 APIM 原函数的行为：字符码先按原文匹配，可解析为有限十进制数的声明码再按精确 double 数值比较。例如声明字符码 `'-9'` 会将 `-9.0`、` -9`、`-09` 和 `-9e0` 一并记为缺失，不使用近似容差；相邻可区分的 double 不合并。数值码保留原精度，不先转显示字符串。

CSV 的空字段、空白字符串或字面 `NA` 应按源合同显式声明，不能因负号推断缺失。非十进制文本码仅能精确匹配字符来源：显式声明 `'0x1A'` 可将同名文本记为缺失，但不能把数值 `26` 记为缺失；声明数值 `26` 也不能将未声明的十六进制文本吞掉。DTA 普通与 tagged NA 统一缺失，值标签移除但底层编码保留。先保留原生缺失计数，再按全局码优先、逐列码其次重码；两类重码不重复计数，tagged 是原生缺失的子集。CSV 显式文本码的替换也记入对应重码计数。缺失重码之后仍存在与 `missing_value` 相同的观测值时拒绝，避免把合法值写成缺失。

产物均在调用者指定的私有目录：

- `data.dat`：无表头、无行名、空格分隔，有限数值用17位有效数字输出，缺失写显式 sentinel；写后读回逐列核对数值、缺失和形状。
- `column_order.txt`：每行一个列名，UTF-8 无 BOM、LF、末尾换行；文件原始字节的 SHA256 就是列序 SHA，不依赖 R 序列化。
- `data_block.inp`：只有相对 `DATA: FILE = data.dat`、有序 `NAMES` 与 `MISSING` 声明。它可与已审模板接合；本函数不编辑模板、不核模型的变量语义。
- `source_receipt.json`：源/DAT/列序/数据片段/代码 SHA、行列数、列名、逐列缺失计数与未建模边界。无输入绝对路径、逐行值或个体 ID。它是准备回执，不是家族真实换源验收回执，不能直接放进 `assets/real_data_receipts`。

新合成测试 `test_source_spec(skill_root, out_dir)` 位于已登记的 `scripts/test_apim_v2_data_adapter.R`。同一合成数据换列名、换源列序后分别写 CSV 与 DTA，要求 DAT 和列序 SHA 一致；两源各自核 `NAMES`、列序文件和声明列序完全相同，以及落盘回执的三个输出 SHA 分别对应正确文件。负例还覆盖错列名的空缺失码声明、加载后改动隔离源码副本、十进制等价缺失码、十六进制绕过、映射碰撞、非数值、sentinel 碰撞、非法列名、错 SHA、来源变化与已有输出拒绝。家族 CI 由 `run_family_ci_tests.R` 按注册项 `source_spec_preparation` 执行一次，输出位于 `family-ci/source_spec_preparation/`，回执为该目录的 `SOURCE_SPEC_TEST_RECEIPT.json`；随 `family-ci` 产物统一上传。测试不调用统计引擎，不能代表真实数据或 Mplus 运行成功。
