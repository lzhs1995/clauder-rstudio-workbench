# Mplus 升级与 MplusAutomation 兼容性

先判断更新是否作用于当前模型与算法，再决定是否值得测试；不要把新版本自动视为速度提升。官方更新记录：https://www.statmodel.com/verhistory.shtml 。

- 只读核查安装包实际 ProductVersion、签名与哈希，文件夹名称不作版本证据。同一 UpgradeCode 不能证明版本可以并存；默认安装不能当隔离测试。
- 区分三层：命令行启动接口、输出解析、统计结果。MplusAutomation 的 Mplus_command 可明确选择引擎；包发布时间较早不等于新版不能启动。版本头可解析也不等于 readModels 全部字段正确。
- 在独立目录固定输入/数据/统计设置，逐个验证正常结束、参数/SE/拟合指标/警告、MI与savedata；原生输出与R解析交叉检查。新增ESEM等输出布局需专项验证。
- 多队列使用 killOnFail=FALSE，避免某些版本 runModels 的 taskkill /f /im mplus.exe 误杀其他研究；失败清理必须绑定PID、创建时间和输入归属。
- 记录引擎哈希/输出版本头、R包版本、单模型与整批耗时、峰值RSS/private、系统commit和主机负载；在相近负载下重复基准后才报告加速。不能削减迭代/starts/积分精度冒充版本收益。
- 2026-10-02核查：9.1主要增加EFA/ESEM/DSEM相关功能，9.1.1修复9.1中特定DSEM TWOLEVEL + observed LAGGED + PROCESSORS>CHAINS结果失真。普通PP-LGCM/TYPE=BASIC MI不因该公告而必须升级；候选测试优先9.1.1，不能套用DSEM改进推断普通增长模型提速。
- 不把升级设成已经可以运行的生产任务的无谓前置步骤；保留可恢复旧环境，不在活跃估计中覆盖引擎/PATH。升级若改变算法结果，单独做科学核查，避免混合版本结果而不标注。
