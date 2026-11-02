# The same Windows RStudio session from either agent location

A Windows-local agent and a Mac agent can source the same scientific R driver
through Windows ClaudeR. The statistical skill owns model specifications,
MplusAutomation calls, inference and engine budgets. This workbench owns
RStudio/ClaudeR session semantics. The optional `cross-device-remote` skill
owns connectivity, signed transport and file transfer.

## Bind the destination, not the agent computer

For the xdev route, use its maintained `rstudio bind`, `execute`, `submit`,
`poll` and `result` commands. Discovery, loopback listener, R PID/birth and
RStudio ancestry must agree on Windows. The Mac's native `list_sessions`
enumerates its configured bridge; an empty local result does not prove that
Windows RStudio has stopped. Do not send a Windows task to an unrelated local
session or restart a healthy Windows session to repair the local registry.

When the task permits xdev HTTP, record
`MAC_XDEV_WINDOWS_LOOPBACK_HTTP`. Successful Windows execution requires the
actual Windows R identity and output. This class is distinct from
`MCP_STDIO_OK` and `NATIVE_MCP_OK`; it cannot satisfy a native-only task's
smoke gate. Config files, a live port, and a queued request are separate from
successful R execution.

## Keep long work in one R worker

Submit the batch once to ClaudeR's asynchronous execution. Keep the same job
ID, Windows session, R/input hashes and durable progress files across Mac
reconnections. Load MplusAutomation once in that R worker and make its real
`runModels` calls there; a Python command adapter may enforce each engine's
cap beneath that call. A coordinator that directly invokes Mplus bypasses this
route even if it has loaded the R package elsewhere.

Do not pay a cross-machine round trip or a new R/package startup for every
imputation. The Windows worker schedules and checks members locally, while
the agent polls stage/message/update time. Save R and engine process identities,
timing and output receipts; a short Mplus process may disappear before a person
opens Task Manager. Watching the RStudio window is useful feedback, but is not
a substitute for the execution log.

## Recovery boundaries observed with the older Windows fork

- An HTTP timeout can occur after R started the request. Preserve the request
  ID and inspect its original result or the scientific worker's durable files;
  never submit the same estimation again solely because its reply is missing.
- Some old ClaudeR versions remove an async job from memory after returning
  its terminal response. Persist that response before further polling.
  `not_found` alone does not mean the model never ran.
- GUI initialization can take longer than a short transport command's process
  lifetime. Separate a named detached GUI launch from readiness observation.
  Do not create successive RStudio sessions while an earlier launch is unknown.
- Programmatic startup must match the installed fork's function signatures and
  authentication. Historical function-body indices are not a cross-version API.
  A successful tokenless legacy fork probe does not validate a token-bearing
  release.
- A small identity request is preferable to a full process census inside a
  synchronous HTTP call. Use a separate Windows read-only probe when detailed
  process inspection is needed. Record a timeout honestly even if a subsequent
  smaller request succeeds.

These observations justify an adapter and a distinct transport label. They do
not establish reboot recovery, exactly-once execution, or statistical acceptance.
