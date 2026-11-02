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

## Windows HTTP text fidelity

PowerShell 5.1 can decode `Invoke-WebRequest.Content` incorrectly when a JSON
response declares `application/json` without a charset. In the observed case,
the R-written JSON file contained correct Chinese while the HTTP-derived text
was mojibake. On the same subsequent live response, strict UTF-8 decoding of
`RawContentStream` preserved Chinese, U+0085, U+2028 and U+2029, while `.Content`
differed. The maintained fix belongs to the xdev transport adapter; it requires
no RStudio or ClaudeR runtime restart. Preserve the old response and compare
against R's durable output rather than silently repairing historical text.

Line-oriented JSON consumers must split on LF, not Python `str.splitlines()`:
the latter also splits these valid Unicode characters inside a JSON string.
Save complete raw replies before structural parsing. If an outer logger fails
after a terminal result was cached, recover that exact job's cache; this does
not justify a second R or Mplus submission.

An async worker's package library is also independent of transport. Record the
loaded MplusAutomation path/version and let the statistical driver bind its
original library; in the observed project, default 1.2 and project 1.3 had
different parser functions. Do not unload the user's active namespace to fix
the selection, and do not change the model while changing the agent location.

These observations justify an adapter and a distinct transport label. They do
not establish reboot recovery, exactly-once execution, or statistical acceptance.

## Preserve an accepted prefix after a coordinator I/O failure

A progress publication can fail after Mplus finished. Preserve the original
job, R owner, code/input hashes, exports and all attempt receipts. Verify that
the original workers exited, then reconcile every registered work/guard path;
absence of an export alone does not prove that an engine never started.

The statistical skill owns validated-prefix reuse and the remaining engine
budget. A recovery worker may use the same RStudio/ClaudeR session, but copied
outputs keep their original R producer and MplusAutomation calls. Record a
new recovery job only for genuinely unstarted nodes and preserve the failed
original job. The observed recovery reused 19 complete imputations and began
at MI20 through the same Windows RStudio and original MplusAutomation library.
This does not establish complete-family inference or reboot recovery.

Windows read handles without delete sharing can obstruct atomic progress
replacement. Use short shared read/delete handles for observers; bounded
writer retries belong to the statistical worker. Do not drop failed cost
writes and continue estimation. Keep the original absolute deadline when
starting a recovery worker so that reconnecting cannot renew time.

Return compact status and SHA summaries. Passing `Get-Content -Raw` directly
to `ConvertTo-Json` serialized extended PowerShell provider properties and
expanded one short test reply to about 92.8 MB. `[IO.File]::ReadAllText` or an
explicit string cast avoids that wrapper problem. Read the original durable
result without rerunning completed tests or transferring the oversized reply.

## Carry the same session through complete-family verification

The observed recovery later finished all 40 primary imputations and 80 stages.
The statistical reader verified output sets, hashes, budgets, full covariance
and the old and new R producers. A separate read-only job in the same Windows
RStudio compared pooled results with the original R functions and mitml,
passing 354 checks without another Mplus call. Keep estimation completion,
statistical acceptance and result transfer as separate states.

The original observer recorded a terminal response and exited after 49 polls.
Reuse that receipt rather than creating another observer or polling a legacy
ClaudeR job after its terminal record has been removed. Once the batch has
ended, the absence of Mplus in Task Manager is expected; the preserved R and
engine identities establish where it ran. Result files remained on Windows
while the Mac retained compact receipts under its capacity constraint. This
does not establish native Mac MCP operation or completion of the wider study.
