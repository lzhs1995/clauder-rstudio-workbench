# RStudio渲染缓存的深层内存回收

2026-10-02在真实PP-LGCM会话中验证。浏览器退出、`gc()`成功、`.GlobalEnv`的`object.size()`很小，都不能证明渲染对象已释放。

## 根因与诊断

- `object.size(environment)`只显示环境本身的浅层大小；本次停用调度器浅层仅几十字节，但`lobstr::obj_size()`测到约252MiB可达对象。
- `chromote::has_default_chromote_object()`返回FALSE表示默认浏览器不可用，不保证namespace内部`globals$default_chromote`已变成NULL。本次默认对象已关闭且页面会话数为0，仍保留约671MiB。
- 对环境及闭包先检查`environment()`、父环境、绑定列表，再测深层大小。各对象可共享引用，不能把深层大小简单相加当成预计释放量。
- 检查namespace缓存时跳过活动绑定及尚未求值的promise，避免为“检查内存”加载更多数据。`rlang::env_binding_are_lazy()`或个别绑定可能报`bad binding access`，逐绑定记录并跳过，不能吞掉整个检查结果。

## 已验证的回收顺序

1. 验证本任务R PID与创建时间、调度器`active=FALSE`/`busy=FALSE`、浏览器PID归属及0个页面会话。不能对用户浏览器或另一任务的活动Chromote执行同样清理。
2. 调用已验证的正常关闭方法。本次PID30376通过PID、创建时间、父R进程及空会话列表四重核对后`close()`成功。
3. 将停用调度器保存为独立RDS，回读核对绑定和函数体，保存SHA；随后只移除该已停用对象的全局引用，检查其他全局名称保持。
4. 对已关闭默认Chromote缓存也先归档、回读、校验SHA；再次确认`is_alive=FALSE`、`is_active=FALSE`、0个页面会话，再清除缓存引用。本机版本公共setter拒绝NULL，因此只在上述条件成立且缓存绑定未锁定时清理内部`default_chromote`字段。不得替换包函数、解锁受保护绑定或照搬到未知版本。
5. 在前台执行`gc(full=TRUE)`，核对Vcells、R private、Windows Available/Commit及RStudio响应。归档是已关闭对象的证据，不承诺恢复其中的浏览器外部指针；需要重新渲染时重新创建浏览器。

大对象归档验证有短时峰值：本次660MiB文件回读期间可用内存曾降至约0.77GiB。应串行执行，停止新模型准入；不要把大对象marshal到新R进程再次复制。必须在主会话修改缓存时，可用一次性`later`回调执行并写持久stage/message/updated_at；这属于前台回调，不能伪称`execute_r_async`作业。根据当前R PID、文件增长和进度监测同一回调，超时不重复提交。

## 实际效果与限制

- 已停用调度器归档262,732,260字节，清理后Vcells约940.9→711.4MiB。
- 已关闭Chromote缓存归档691,022,456字节，SHA256 `b0ebc202787e20a098f2192902295d832051fd1d3ca8d650184b14bdb1ae9a1d`；清理后Vcells约711.4→70.6MiB。
- 合计约870MiB活向量对象被释放。Windows主机余量受到其他任务和共享页面影响，不能承诺同量物理内存增长。
- 随后仅对已回收、无估计子进程的R执行一次`EmptyWorkingSet`：RSS约969→7MiB，但当时Windows可用内存仅约增加81MiB，private不变。再次证明工作集数字不是释放量。此操作不是周期性策略，不能反复清理活跃R/Mplus；会产生后续页面重新载入。
- 本任务MI的3GiB合同门槛未改。资源回收成功不等于模型已启动或科学验收通过。

可审计实现位于本任务`work/pp_lgcm_reconciliation_20261001/`的`sandbox_retire_idle_render_state.R`、`sandbox_release_closed_chromote_cache.R`及`reclaim_cleaned_idle_r_workingset.py`，这些是绑定PID与对象身份的一次性脚本，不能原样当作跨项目通用清理命令。
