# Warm-session reuse

Use this path when the current agent task already exposes the native
`mcp__r_studio__*` tools and `list_sessions` returns an active RStudio session.
An active discovery record is sufficient to reuse the existing ClaudeR Addin;
do not ask the user to start `claudeAddin()` again, open another RStudio, or
rotate the session identity.

## Successful native sequence

The following is a real high-assurance smoke from this workstation. It reused
an already-running session without manual Addin interaction:

```text
list_sessions
  -> chapter4-mac / port 8788 / pid 19087
execute_r
  -> NATIVE_EXECUTE_OK pid=19087
execute_r_async
  -> job_id=b422a3bc
get_async_result("b422a3bc")
  -> NATIVE_ASYNC_DONE
```

The parent evidence was recorded as `NATIVE_MCP_OK` with four chained raw
tool outputs and SHA-256 hashes. The evidence is an example of the protocol,
not a reusable identity: every task must discover the current session again.

## Agent procedure

1. Confirm that the current task actually exposes the native RStudio tools.
2. Call `list_sessions` before asking for any user action.
3. If exactly one session is active, reuse it directly. If more than one is
   active, call `connect_session` with the exact name returned by the listing.
4. Run a short `execute_r` PID marker and verify that it matches the selected
   session.
5. Run a short `execute_r_async` marker. Save the real `job_id` and poll that
   same job with `get_async_result`; a `running` response is not a failure.
6. Register all four native outputs with `native-smoke --require-raw-file`.
7. Submit the formal R job only after the native-smoke and completion gates
   pass.

If the first short async submission reports that the Addin is not running,
retry that short smoke once on the same native tool layer. Do not restart the
agent or RStudio. Record only the successful retry and continue polling its
real job ID.

## Copyable agent prompt

```text
先检查当前任务是否有 mcp__r_studio__ 原生工具。
如果有，立即调用 list_sessions。
若返回唯一活动会话，直接复用，不要求用户点击 ClaudeR Addin。
只有多个活动会话时才调用 connect_session。
随后执行短 execute_r PID 检查，再执行一个短 execute_r_async，保存真实
job_id，并用 get_async_result 轮询同一 job_id。
全部成功后再提交正式 R 任务。
```

This prompt is an operating template, not a replacement for the native tool
calls or their raw evidence files.

The diagnostic CLI may still require an explicit `--session-name` so that a
read-only probe cannot guess a target. That CLI safeguard is separate from
the native-agent warm path: the agent first reads `list_sessions`, then uses
the unique active session directly when the native tool contract permits it.

## Three states, not one generic connection result

- **Warm reuse:** an active session is discovered and the current task has
  native tools. No manual Addin action is needed.
- **Addin startup required:** discovery is empty, stale, duplicated, or the
  selected port/PID is no longer live. Ask for one startup action only after
  recording the exact diagnostic reason.
- **Task tool registration missing:** RStudio may be healthy, but the current
  Codex task has no native tool surface. Report
  `CODEX_NATIVE_TOOLS_NOT_REGISTERED`, do not use HTTP or MCP stdio as a
  substitute, and create a fresh task context.

## Prohibited shortcuts

- Never guess `default`, `chapter4-mac`, or a historical PID/port.
- Never call `claudeAddin()` again when a unique active session is already
  listed.
- Never submit a second async job because the first one is still `running`.
- Never treat HTTP, Python MCP stdio, Rscript, a tool-name inventory, or a
  hand-written evidence JSON as native-smoke proof.
- Never send an unsupported SIGHUP or automatically kill/restart RStudio.

## Evidence fields

Formal work should retain the current task key, exact session name, R PID,
native-smoke evidence ID, four raw-output paths and hashes, formal job ID, and
completion-check evidence. A previous successful session is useful for
debugging and training, but cannot satisfy a new task's native gate.
