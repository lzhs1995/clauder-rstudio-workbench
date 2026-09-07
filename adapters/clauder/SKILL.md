---
name: clauder
description: Connect to RStudio through ClaudeR or route R script execution, async progress and connection recovery to the maintained clauder-rstudio-workbench skill.
---

# ClaudeR compatibility entry

This is a compatibility alias, not a second implementation of the workbench
protocol. For tasks beyond a bare connection, read the installed sibling
`../clauder-rstudio-workbench/SKILL.md` and the
project's AGENTS.md, HANDOFF.md and MEMORY.md before acting.

For a bare connection request, attempt native `list_sessions` first. Bind the
user's named session explicitly; if there is exactly one live candidate, bind
and verify its PID. If multiple healthy candidates remain and the user has not
selected a target, ask which one. Do not silently choose the first research
session or treat a missing native tool as a missing RStudio installation.

If the native tool is absent or a call fails, use the core skill's layered
`ensure-ready`/diagnostic workflow. Record the failure class. Follow the project's
bounded retry policy before asking for manual R code; never resubmit an async
job merely because a polling request timed out. Retain the original job ID.

Connection and installation policy belongs to the sibling core skill:
persistent pinned bridge, platform-correct discovery home/cache, explicit client,
current native evidence, and no automatic RStudio/agent restart. Do not restore
Windows-only paths, bare PyPI `uvx` commands, guessed ports or blanket restart
advice here. Independent stdio/HTTP success is not native-wrapper success.

Scientific work continues to use the appropriate domain skill. This alias
does not choose models, modify user datasets or add analyses beyond the task.
