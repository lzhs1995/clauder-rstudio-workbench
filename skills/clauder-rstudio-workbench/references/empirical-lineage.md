# Empirical lineage during manuscript refinement

Use this reference when a manuscript claim, table or figure must be traced back
to existing R results. It does not authorize extra models or require automatic
re-estimation of every model. Trace the entire original inventory, then rerun only
missing, contradictory, affected or explicitly requested stages.

For each claim retain data and script hashes, variable definitions, analysis unit,
sample membership, missingness/exclusions, model specification, result object,
table/figure anchor and the eventual retain/rewrite/move/delete disposition.
Resolve an apparent missing input as a real file, in-memory alias, write-only
snapshot, derived copy or missing historical source before choosing recovery.
Derived data can support a documented downstream check without restoring lost
historical provenance.

`clauder-workbench completion-check --empirical-contract /absolute/trace.json`
adds the portable empirical trace gate to existing execution gates. Its failure
cannot be bypassed with `--policy skip`. Run the checker without reconnecting or
restarting RStudio. The contract records:

- Hashed script, all relevant inputs/outputs and explicit CSV sample keys.
  Equal N does not prove the same people, couples or waves; compare memberships.
- Runtime source revision, installed version, loaded version, session, original
  job ID and transport separately. An installed patch does not update a loaded
  R namespace or current agent-native tool registration.
- Full-precision comparisons with explicit absolute/relative tolerance, storage
  precision, display rounding, CI method and requested/saved draws. Binary32
  explains a representation difference; it never silently expands tolerance.
- Normal termination, usable SE, saved draws and replicate convergence as
  separate model-health axes. A normal-ending model can still support only a
  limited claim. Propagate limitations to every dependent claim.
- Table row/column sets, denominators, labels and missing counts. Keep numeric
  source results distinct from display text and DOCX formatting.

The CLI consumes JSON schema version 1; see the maintained
[thesis-refiner contracts](https://github.com/lzhs1995/thesis-refiner/tree/main/schemas).
The bundled `clauder_workbench/empirical_trace.py` is a versioned copy so checking
does not depend on another skill installation. It performs no statistical execution.

Report evidence closure and full reproduction separately. Full reproduction needs
an actual end-to-end execution receipt bound to script, all input/output hashes,
session and job; a saved log, compatible numbers or a found output is insufficient.
Documented scientific partials must remain visible even when a manuscript is ready.
If NLM finds a serious discrepancy, return to the affected local evidence chain;
do not let an external review opinion directly change a coefficient or study design.

## Result assembly and relocated caches

Checker 1.1 supports tables with `row_keys`, for example `["model_id", "term"]`,
and an explicit `expected_rows` list of key arrays. Declare the current full key
set, optional `expected_n`, and `expected_cell_rows` (`key` array plus `values`
object). Legacy `row_key` contracts remain valid. Do not join compound keys with
an ambiguous separator or use a historical chapter's row count as a default.

A full p-value vector assigned to a one-row `data.frame` can silently recycle
scalar columns and multiply rows. Bind each scalar to its model/term, check
lengths before construction, then validate complete unique keys and cell values.
Correcting assembly in a new output directory does not require re-estimation
when saved objects already contain the correct values. Retain the failed table
and demonstrate the failure with a synthetic negative case.

A readable archive symlink does not prove a canonical-root gate or an ancestor
dependency works. Preserve required roots, or declare a new portable entry with
provenance mapping. Execute each promised entry and compare actual outputs;
label cached postprocessing separately from model re-estimation. Native R and
Rscript reading the same cache are not independent scientific replications.
Skill installation must not restart a live R process or replace its fixed code.
