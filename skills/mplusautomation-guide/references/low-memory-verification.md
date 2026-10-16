# Low-memory verification without repeated estimation

Freeze the model list and input/output hashes before incremental precision export.
Use small disjoint chunks in the existing RStudio session; avoid spawning a new R
process or copying its global environment merely to read completed outputs.
Every chunk needs its exact start/end identities, input hash and completion receipt.
Merge only completed, non-overlapping chunks and independently read the files back.
Native export count and independently verified count are separate states.

Changing a chunk size changes index arithmetic. In the Chapter 4 frozen 298-fit
snapshot, completed ranges 1–20, 21–40 and 131–135 coexist. Calling chunk 7 at size
20 would overlap 131–135; the guard must reject it. Select the next actual gap
from the frozen manifest (`export_next_current_precision_chunk(5L)` in that
experiment), rather than assuming an index based on the old chunk size. Do not
change the pending identities to make the coverage appear complete.

## Cache model contracts by content

A single-model check need not parse every nested contract. Build one JSON per
model, bind the manifest to the original full-contract hash, compare every cached
structure with the original, and check the selected model hash before loading.
Invalidate on source changes. Chapter 4 verified all 612 cached structures and
used the cache in native checks. This removes redundant parsing; a controlled
speedup or peak-memory reduction still requires measurements and must not be
claimed from the implementation alone.

## Measure transient memory in the actual phase

Estimate additional allocations separately from existing committed memory and
pages that may become resident again. Record a host reserve and the exact budget
used by the live queue. File-size multipliers are admission estimates, not observed
peaks. The Chapter 4 read-only exporter used a 750 MiB reserve plus an incremental
file-volume estimate and up to 256 MiB for page reactivation; those are local
choices, not universal defaults or permission to lower another worker's gate.

Start the observer first and require an explicit `MEMORY_OBSERVER_READY` signal.
Then launch the calculation in the same orchestration step, without an intervening
agent planning delay. Bind PID plus creation time and sample timestamps to the
calculation's start/finish receipt. A monitor that finds an existing receipt,
expires before fitting, or samples only idle time has no workload peak evidence.
Polling at finite intervals gives an observed peak, not a mathematical upper bound.

The valid paired Chapter 4 observation of `apimom_total_siops-sibg-hg` recorded
RSS growth 220,504,064 bytes and private-commit growth 175,849,472 bytes. The
original incremental-only estimate undercovered private growth; the separately
reserved residency allowance must not hide that diagnostic fact. Use measured
growth with headroom when refining budgets; one small model does not bound all
larger models. Preserve the earlier failed/idle-only observations as failed scope.

Independent optimizer agreement does not erase a strict Mplus calibration
exception. Keep the predeclared parameter/LL tolerances, retain each exception
and add the independent outcome as a separate field. The first three new checks
agreed within about 2.15e-6, 4.02e-6 and 4.04e-6; the fourth remained pending at
the initial memory-constrained checkpoint. Consult current receipts, not these
historical counts, before deciding what to execute next.

Evidence/scripts under `scientific_audit_20261002/`:
`scripts/cache_recursive_contracts.py`, `experiments/recursive_contract_cache/`,
`scripts/export_current_precision_chunk.R`,
`scripts/calibrate_current_precision_model.R`,
`scripts/monitor_calibration_memory.py`,
`snapshots/unified_20261004_02/independent_calibration/`.

Windows Python invoked through WSL may retain its Windows console encoding even
when the shell sets `PYTHONIOENCODING`. Use the approved Windows interpreter with
`-X utf8` for Chinese diagnostic output. Distinguish a post-computation encoding
failure from absence of a saved analysis receipt before retrying the calculation.
