# Failure modes, prohibitions, and the native-PR direction

## Common failure modes

### Tiny RData saved
A few-MB RData usually means a compact result was saved instead of the full
`cmest` object. With `sy_female,sy_male`, `nboot=10`, a correct nested file can
reach several GB. Check size before trusting it.

### Async objects not in the foreground .GlobalEnv
An async Rterm worker does not auto-return objects to the RStudio foreground
`.GlobalEnv`. Treat the local RData + manifest + validation CSV as the only
completion evidence. To inspect in the foreground, read the RData back
explicitly.

### MCP poll interruption != Rterm failure
A dropped MCP poll does not mean the model failed. Before reacting, check
`state_*.json`, `manifest_*.csv`, `validation_*.csv`, the Rterm process, and
whether the output RData is still growing or already complete. **Do not resubmit
the same mediator because of one poll interruption.**

### Optional upload: file not visible
If an upload target is not visible in a web/client view, trust the API
verification (returned `fs_id` + matching size) over the unrefreshed web view.
Account identifiers are **never** stored in this skill — they come from the
environment or an untracked config only.

### sink()-wrapped worker hangs (Rterm will not exit)
Wrapping a worker body in `sink()` (to capture its console output to a file) is a
recorded trap: the detached Rterm finishes the model and writes its durable
`state/manifest/validation`, but the open `sink()` connection keeps the **process
alive**, so the fan-out slot is never released and `get_async_result` keeps
reporting `running`. Recovery: confirm the RData + validation CSV are complete,
then `cancel` the job to clean up the stuck Rterm. Prevention (enforced):
`clauder-workbench worker-lint --contract task.yaml` — also run automatically
inside `fanout-plan`/`fanout-run` — **BLOCKs** any worker containing `sink(`.
Workers must log only via `cat()` + `flush.console()` and `write_state()`.

### Native MCP addin-transient on first async submit (retry in the same layer)
Observed during a real fan-out smoke: the **first** `execute_r_async` call
returned `RStudio addin is not running` even though `list_sessions` and
`execute_r` had just succeeded on the same native MCP layer. This is a **native
layer transient**, not a `Transport closed` and not a reason to restart the
agent. Diagnosis: a one-off error on the async submit while the session is
otherwise live. Handling: **retry the same `execute_r_async` on the same native
layer** — the retry produced the real `job_id` and the `NATIVE_ASYNC_RETRY_DONE`
marker. Never restart Codex/RStudio for this; that throws away the live session.
The native-smoke gate exists precisely to surface this transient *before* a
multi-GB fan-out, not during it.

## Native-smoke gate before fan-out (required)

Before launching any CMAverse fan-out that claims the agent's native MCP path,
the parent task must pass `clauder-workbench native-smoke` so its evidence has
`transport_class = NATIVE_MCP_OK` under the same `task_key`. `fanout-plan` /
`completion-check` consume that parent evidence; a fan-out without a passing
native-smoke is BLOCKed (not WARNed). See
`clauder-rstudio-workbench/references/native-mcp-gate.md` for the exact sequence.
For formal runs, start native-smoke with `--agent codex --require-raw-file` (or
the matching agent name) and pass `--raw-file` for all four record steps.
v0.3.3 and later require all record evidence ids to be chained into the final
PASS and preserve raw output hashes/copies; old v0.3.2 native-smoke state files
without record evidence ids must be rerun.
v0.3.4 and later also enforce that chain in every downstream fan-out and
completion gate. A `native_smoke` PASS with missing or duplicate
`parent_evidence_ids` is treated as absent, even when it says
`transport_class = NATIVE_MCP_OK`.

This strictness is by design for CMAverse long runs: do not mix agents inside
one native smoke, do not bypass `--require-raw-file` for formal results, and do
not delete raw native evidence as part of ordinary installer cleanup. Runtime
skill backups have retention; scientific/native evidence does not.

### Transport closed recovery order (do not restart the agent first)

When the native MCP path reports `Transport closed` mid-task, follow this order
and only escalate to a restart at the end:

1. `clauder-workbench doctor --expect-client codex --check-toml-parse`.
2. Confirm the persistent entry: `<USER_HOME>\.local\bin\clauder-mcp.exe`,
   `startup_timeout_sec = 180.0`, a shared `UV_CACHE_DIR`, and LZHS fork
   provenance (never bare `clauder-mcp`, which would pull the upstream package
   from PyPI and drop the async/multi-session/copilot changes).
3. Re-run `install.ps1 -ConfigureCodex` if the config still points at `uvx` or a
   bare `clauder-mcp`.
4. Re-run the `native-smoke` sequence (a cold persistent exe may need one warm
   retry; treat a single transient as retryable in the same layer).
5. Only if the configured persistent entry is correct **and** repeated
   native-smoke attempts still fail should the user restart the agent.

## Prohibitions

- Do not edit the original R script and overwrite it.
- Do not run the original M=0 and M=1 regions as two independent bootstraps and
  then claim "same bootstrap".
- Do not save a table or compact list in place of the full `cmest`.
- Do not delete a local RData before validation passes.
- Do not delete a local RData before an upload is verified (when upload is on).
- Do not write any authorization credential into markdown, assets, schemas, or
  contracts.
- Do not resubmit a long job because of a transient MCP poll failure.
- Do not extrapolate the `nboot=10` concurrency optimum to `nboot=1000`.

## Delete-local-RData conditions

Delete a local RData only when **all** hold: the RData wrote completely;
validation passed; (if uploading) the upload API returned success, the remote
`fs_id` is readable, and remote size == local size; the manifest records
`upload_status=success` and `size_match=TRUE`. Otherwise keep the file, mark the
failure reason in the manifest, keep the upload log, and stop silent cleanup.
When not uploading, you may delete by a disk policy, but only after validation
and after saving a deletion manifest.

## Verifying the paired contrast against native CMAverse

To prove the wrapper did not distort results, re-run the same specification with
a native multi-`mval` path and compare effect tables within tolerance. This is
the regression that justifies the wrapper approach.

## Toward a native CMAverse PR

The wrapper around `cmest()`/`boot()` is a user-side workaround. The cleaner
design is native multi-`mval` support:

```r
cmest(..., mval_grid = list(list(0), list(1)))
# or
cmest(..., mval = list(list(0), list(1)), paired_mval = TRUE)
```

A PR's core is not concurrency scheduling but:

1. supporting multiple `mval` in one `boot()` call;
2. every replicate sharing the same bootstrap indices;
3. each `mval` returning a complete `cmest` structure;
4. keeping the single-`mval` legacy interface compatible;
5. a sensible `summary()` for multi-mval results.
