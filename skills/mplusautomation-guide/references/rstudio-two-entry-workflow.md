# One Windows RStudio workflow, two agent entry points

The statistical runtime is Windows RStudio → ClaudeR-managed R execution →
MplusAutomation → licensed Windows Mplus. The agent may run on Windows or
remotely on a Mac. Changing the agent's location does not change the original
R scripts, data definitions, estimands, model specifications or inference rules.

| Layer | Maintained responsibility |
| --- | --- |
| `mplusautomation-guide` | R model drivers, input lineage, MplusAutomation calls, MI/budget contracts, diagnostics, tables and statistical acceptance |
| `clauder-rstudio-workbench` | Actual RStudio binding, ClaudeR protocol, synchronous/async execution, progress and session recovery |
| `cross-device-remote` | Windows connectivity, signed transport, file transfer, request deduplication and remote identity checks |

Keep the scientific R driver transport-independent. A Windows agent sources
the driver through its bound ClaudeR session. A Mac agent transfers the same
file, verifies its hash and asks Windows ClaudeR to source it with `local=TRUE`.
Keep configuration paths outside the driver, with an explicit Windows Mplus
command and the original package library. Do not create separate model logic
for native Windows and remote Mac use.

RStudio may launch asynchronous child R processes. This preserves the requested
route when the actual parent chain and ClaudeR job are recorded and the R code
calls MplusAutomation. Record current RStudio/R/worker identities, package
versions, exact R/input hashes, actual Mplus process receipts and output checks.
Loading MplusAutomation and then bypassing it with a direct engine launch does
not establish that route. Direct-engine engineering benchmarks keep their own
label and cannot stand in for requested RStudio workflow acceptance.

## Original scripts and completed results

Inventory original R scripts before executing them: hard-coded paths, package
installation, environment clearing, shared output names and failed branches
require an isolated driver. Preserve statistical expressions and document
path-only adaptations separately. Existing accepted outputs remain valid
evidence even if their original transport differs; do not re-estimate them
only to obtain a new transport label. Read them from RStudio with
MplusAutomation, retaining source hashes and original acceptance boundaries.

For PP-LGCM, original CFPS script lineage and subsequent CHARLS R drivers are
both part of the evidence chain. Historical `run_pilot.R` and `run_family.R`
call `MplusAutomation::runModels` with a bounded command adapter. A Python
supervisor under that call may own the engine timeout; this is different from
a Python coordinator skipping the R/MplusAutomation call. Keep supervision
independent enough to retain the cap when the client disconnects. A prior
timeout consumes its original budget; changing transport never resets it.

## Efficient execution and honest acceptance

Submit a bounded batch once. Windows handles scheduling, Mplus calls,
validation and checkpoints; the Mac reads stage/message/time and later returns
declared outputs. Avoid a full cross-machine round trip for every MI member.
Measure queue, R startup, estimation, polling and transfer separately. Task
Manager can miss short-lived fits; saved process receipts provide durable proof.

When the user permits xdev HTTP, label it `MAC_XDEV_WINDOWS_LOOPBACK_HTTP`.
It proves RStudio execution only after the actual Windows R identity and result
are verified. It does not prove the Mac native `mcp__r_studio__` wrapper. A
native-MCP-only task retains that separate gate. The two entry points use the
same numerical checks; old Windows success is not a new remote-adapter test.

Source pattern: original Windows PP-LGCM requirements and plan from September 8,
and the author's November 2 correction and two-entry clarification. Shared
examples contain no private participant data, personal paths or licenses.

## Bind the original package in each R worker

An asynchronous R worker can resolve a different package library from the main
RStudio session. In the PP-LGCM readback, the default Windows library contained
MplusAutomation 1.2 and the original project library contained 1.3. `runModels`
had the same function hash; `readModels` and `mplusModeler` differed. Readback of
one saved success and one original timeout produced identical parameter tables,
which does not establish equivalence of the whole packages or all outputs.

The optional batch driver's `mplusautomation` configuration binds `library`,
`version`, `file_sha256` for `DESCRIPTION`, `R/MplusAutomation.rdb` and
`R/MplusAutomation.rdx`, and `function_sha256` for `runModels`, `readModels` and
`mplusModeler`. Derive these values from the intended installed library before
submission; package version alone is insufficient. Function hashes use SHA256
over `paste(deparse(function_object), collapse="\n")`, without R serialization.

`bind_mplusautomation_library()` checks the files, loads that library, and checks
the actual namespace and functions before creating the coordinator. It refuses
a worker that already loaded another library, preserving that namespace; start
a fresh ClaudeR async worker for the corrected configuration. Do not unload the
user's active namespace or reinstall packages merely to fix path selection.
Worker receipts retain the actual package path and hashes. Dependency packages
are outside this limited parity check.

Six Windows checks exercised the original library and rejected an already-loaded
alternate, an incorrect version, a changed file hash, a changed function hash and
a missing contract. They made no Mplus calls. The adapter also publishes local
JSON requests only after a complete write, using an exclusive same-directory
hard link on APFS/NTFS; an interrupted `.part` stays available for reconciliation.
This atomic publication is not a claim of full power-loss recovery.

## Optional adapter for an existing bounded batch

[run_rstudio_mplus_batch.R](../scripts/run_rstudio_mplus_batch.R) keeps one
ClaudeR R worker alive and makes each real `MplusAutomation::runModels` call
inside it. Its project-supplied Python coordinator uses
[rstudio_mplus_dispatch.py](../scripts/rstudio_mplus_dispatch.py)
`execute_stage(channel, contract, work, output, helpers)` to request the next
single-model call. Requests travel through local Windows files, not across the
network. An RStudio/R PID-and-birth check binds both sides. The original
[scoped supervisor](../scripts/run_scoped_pilot.py) runs beneath the
MplusAutomation command adapter and retains its own engine cap.

The adapter consumes the `pp-scientific-single-pilot/1` contract: one immutable
`model.inp` and `data.dat`, their hashes, an explicit engine/hash, helper and
runner hashes, one-call maximum, prior elapsed cost, cap, resource limits and
scientific authorization. It neither generates a new model nor selects an
imputation. The family coordinator still owns ordering, valid-result gates,
quadrature checks, cumulative budgets and complete-MI inference.

Source the R file and call `run_rstudio_mplus_batch(config_file)` in the
bound ClaudeR session. The `rstudio-mplus-batch-driver/1` configuration supplies
the Windows Python path, coordinator/hash/arguments, a new channel directory,
progress/result paths and the outer observation deadline. The engine budget
remains in its original contract. Configuration and source files should be
frozen and hashed before submission. A project that declares this route must
reject the direct-engine entry point.

On completion, each member's export preserves the original supervisor
manifest and adds the R call, package version, RStudio ancestry, wrapper return
and MplusAutomation log under a new complete manifest. Input data stay in the
Windows work directory. A missing R response, vanished R process or existing
request remains a recovery case; this adapter deliberately does not restart
the R worker or automatically adopt an unknown engine. Mac reconnection can
continue polling the same live ClaudeR job. RStudio/Windows restart recovery
requires separate reconciliation.

The initial implementation passed 12 dispatch checks and, with its project
integration, 28 scheduling/route checks. A real Windows RStudio/MplusAutomation
run also exercised a successful Python fixture and an owned timeout, rejecting
duplicate requests. Those two fixtures made zero real Mplus calls. An earlier
single synthetic Mplus regression proves the base RStudio/MplusAutomation
chain; it is not a licensed integration test of this new dispatcher or a
completed 40-imputation family.

The two-fixture batch body took 23.18 seconds. Submission to body start took
about 73 seconds, including asynchronous initialization, package loading and
identity checks that were not separately timed. This is a reason to amortize
startup across a batch, not evidence of pure network latency or of a speedup
in Mplus estimation. No controlled comparison of human development time on
Mac and Windows was performed.
