# 安装与更新

从 `lzhs1995/clauder-rstudio-workbench` 的 `skills/mplusautomation-guide`
安装完整目录，不能只复制 `SKILL.md`。入口同时保留通用 Mplus 工作流和
[第四章 APIM 工作流](APIM.md)，运行脚本、配置示例和引用资料均为依赖。

已经由 CC Switch 托管的环境，请在 CC Switch 中从该 GitHub 仓库安装或
更新此技能，并启用需要的客户端；不要再用另一套同步器覆盖托管目录。
安装后核对文件哈希，并检查客户端原生技能发现结果。当前会话已加载的
指令不会因文件替换自动更新；下一轮或重新启动后检查技能发现。

未托管的环境可以使用仓库安装器或客户端的技能安装工具。仅更新技能时
无需重装 ClaudeR、修改 MCP 配置或关闭 RStudio。Mplus 引擎须另行合法安装。

`RELEASE_MANIFEST_20261004.json` 是保留的历史快照，不是当前版本的清单。
本次 APIM 数值验收摘要在 `assets/native_acceptance_20261015.json`；其代码
哈希只覆盖列出的实现文件，不代表其他模型家族也接受过相同测试。
