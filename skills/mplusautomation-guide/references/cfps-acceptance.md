# CFPS-style manuscript acceptance workflow

This reference captures a reusable acceptance pattern for a completed
multi-script PP-LGCM run. It is an anonymized workflow example; study paths,
participant data and manuscript files remain outside the skill.

## Stage boundary

When every producer has reached its terminal source statement and the queue has
no pending or running estimation task, stop creating Mplus jobs. Move to export
and manuscript acceptance. A queue count alone is not enough: producer state,
terminal validation and downstream render objects must all be checked.

## Artifact identity

For each saved table or plot retain:

- producer and invocation ID;
- render-object hash and output path;
- archive/canonical artifact hash;
- renderer and package versions;
- format-specific content validation;
- any shared-destination or supersession relationship.

If an old destination was overwritten by a later call, do not choose the latest
file silently. Preserve each invocation in an exclusive canonical directory and
classify the shared destination as `superseded_shared_destination`. An unmatched
destination hash is an unresolved publication conflict, not an automatic model
failure.

Compare destination identities using the target filesystem's path rules while
retaining the original spelling. On a normal case-insensitive Windows run
directory, slash direction and letter case can differ for the same destination.
Use its complete normalized path, then verify the current file and the candidate
archive hashes; a shared basename in another directory proves nothing. Record
which invocation owns the current bytes without discarding earlier archives.

## Table and parameter binding

Build manuscript registers before comparing values. For each table cell record
the document hash, table/row/column, source script and reader statement, output
alias, model input fingerprint, parameter section and expected display text.
Resolve `ON`, `WITH`, `XWITH`, `MEANS` and variance labels from source semantics;
do not use the closest numeric value or a basename as the producer identity.

Compare estimates, standard errors, fit values, symbols, labels and structural
blanks independently. Keep `MATCH_DISPLAYED_PAIR`,
`DIFFERENT_DISPLAYED_PAIR`, `ESTIMATION_FAILED`, `DEPENDENCY_BLOCKED`,
`NOT_PREPARED` and `PRODUCER_AMBIGUOUS` as separate outcomes. A valid export
only proves that an artifact can be opened; it does not prove that its values,
footnotes or scientific interpretation are acceptable.

## Long-path export recovery

If Windows rejects a destination because of `PATH_MAX`, load the existing saved
render object once, export to a short local path with the same extension, close
only a browser created by that export, and publish through a hash-checked staging
copy. Do not rerun Mplus. If a short export succeeds but publication fails,
retain both states and the original failure evidence.

## Final gate

The acceptance report may say estimation production is complete while keeping
`reference_comparison_complete=false`. Only set the latter after every requested
manuscript component has a source identity, numeric/display verdict and explicit
handling for failures, deferred dependencies, saved-data limitations and
statistically inadmissible estimates. Keep inherited labels or footnotes in a
separate editorial-review field rather than silently rewriting historical output.

## Batch reconciliation after estimation

Freeze the provenance inventories, manuscript hashes, queue snapshot and existing
comparison files in a separate acceptance directory. Report candidate-comparison
counts, unique document cells and model counts independently: two producer
candidates for one cell create two comparisons, not two manuscript cells.
Coefficient/SE pairs omit fit statistics, p-value symbols, structural blanks,
measurement definitions, descriptive statistics and derived summary tables.
Register those components explicitly before reporting complete coverage.

Group differing cells by their bound model. Compare embedded historical input
against current input, then all referenced data files. Preserve imputation list
order (which can be `1,10,2,...,9`) and hash each member. Compare columns by their
declared names, not physical position; reordered NAMES are not changed values.
Include DEFINE inputs, sample filters and cluster identifiers. Assert unique
participant keys and missing-value contracts before comparing numeric values.
Never repair duplicate keys by silently aligning row positions.

A historical output proves its embedded specification, but a currently adjacent
data file may have been overwritten. If that file cannot satisfy the embedded
NAMES/key contract, inspect the companion input and all imputation members.
Record a historical-data recovery limitation. Do not rewrite the specification
to make the sidecar fit or claim that today's bytes were used historically.

When an author authorizes a backup search, search only the named project roots
and record every candidate's path, size, timestamp and hash. A duplicate Mplus
MI manifest (`TYPE=IMPUTATION` list file) is not a recoverable historical
dataset: the complete contract requires the historical input and every
referenced member hash, in the declared imputation order. A same-basename file
with a different member hash, or a manifest whose members are absent, must be
classified as an incomplete backup and cannot authorize a replay. Copy exact
candidates into an isolated evidence directory only after the hash inventory;
never copy or rewrite source data and never treat a manifest-only match as a
reason to rerun 165 downstream comparisons automatically.

Persist model-level verdicts incrementally. Cache numeric comparisons by both
content hashes, schemas, selected columns, keys, missing tokens, tolerance and
comparison-code version. Revalidate those inputs when resuming. Keep paths in
the evidence even when identical content permits cache reuse. An observed input
difference does not establish a quantitative cause for every changed coefficient.

Trace blocked readers through producer statements to the upstream model and its
validation. A deliberately deferred factor-score producer is distinct from an
estimation failure and does not authorize a new run. Verify requested/completed
imputation counts; partial results from an unsuccessful attempt cannot populate
an accepted current-results table.

## Derived tables and tests

For manually summarized interactions, bind X, W, Z, outcome and variable
definition to the actual MODEL/DEFINE syntax. Filename suffixes or swapped
intercept/slope labels are not a substitute for reading XWITH. If a descriptor
conflicts with its variable label or the bound output differs from the displayed
number, retain the conflict and prepare an explicit correction decision.

Audit likelihood-ratio tests separately from coefficient tables. Capture the
actual MplusAutomation return object, both output hashes, model/data contracts,
degrees of freedom, correction factor and statistic. A computed `p=1` can coexist
with a negative difference statistic; it does not establish a valid nested-model
test. Verify nesting and likelihood comparability. A test on one imputed dataset
does not establish a pooled test for the multiply imputed coefficient table.

At decimal half-unit boundaries, preserve the uncertainty introduced by printed
output precision and verify the exporter. Do not force a discrepancy or equality
through a blanket tolerance. Treat fixed-parameter p-value sentinels separately
from inferential significance symbols.

The portable [acceptance_contracts.py](../scripts/acceptance_contracts.py) helper
checks comparison identities, rounding boundaries and minimum LRT evidence.
It classifies supplied evidence; it cannot establish provenance or nesting.
Keep `audit_closed`, `numerical_equivalence` and `manuscript_release` separate;
an archived discrepancy is not a numerical match or an NLM release approval.

## Component closure and Word read-back on Windows

Before closing a manuscript gate, build a component register that includes
tables, figures, measurement definitions, descriptive/MI tables and derived
summary tables. Use four independent closure buckets:

1. `technical_verdict_complete`: the registered cells have machine-readable
   source identities and numeric/display verdicts. This is an evidence status,
   not permission to release the manuscript.
2. `author_scientific_decision`: the displayed definition, variable binding,
   interaction label or LRT interpretation still requires a research-design
   decision. Do not resolve it by selecting the nearest numeric candidate.
3. `source_unavailable_limitation`: the historical or current export needed to
   verify a cell is absent. Preserve the cell coordinates and state the exact
   limitation rather than filling it from the embedded Word value.
4. `editorial_release_open`: figures or technically compared components still
   need footnote, label, rendering or visual review.

On Windows, Word COM is not required for a read-only audit. A stable fallback
is to read `word/document.xml` from a copy of the DOCX ZIP, extract table rows,
and record the document SHA-256, table index, dimensions and cell text. This
read-back is useful for confirming the table contract (for example, MI
denominators and column labels), but the Word value is never promoted to a
current model result. Check the read-back against the static R-script evidence
and the table register; keep the original DOCX untouched.

For a table with missing current exports, distinguish “the manuscript contains
a value” from “the value is reproducible from the present project.” The former
is historical evidence; the latter requires the export, producer/input
identity, and (for MI) the complete imputation contract. A closed acceptance
batch should report both counts and keep `CFPS_CLOSURE_GATE.ready=false` until
the source-unavailable and author-decision buckets have an explicit disposition.

## Static script candidates versus verified producers

When reconstructing a historical R-to-Mplus pipeline, scan every script for
`mplusModeler`, `mplusObject`, `readModels`, model-output declarations, result
roots and estimator branches. Store that static inventory separately from the
frozen execution inventory. A script can contain many input/output names and
still have no verified producer identity if no immutable invocation record binds
it to the accepted output.

Use `static_script_candidate_unbound` for that state. Do not infer provenance
from a matching filename, directory or existing `.out`; do not count the model
as reproduced and do not enqueue a replay solely because its input exists.
Record the static declaration count, historical input/output presence, verified
producer count and any Bayes/LMS branch explicitly. Bayes/LMS inputs that are
deferred, failed or missing an accepted terminal receipt stay outside the
publication queue until a separate, resource-bounded contract is authorized.

If two producer namespaces yield equivalent-looking inputs or the same
`modelout` basename, classify the manuscript component as
`SOURCE_IDENTITY_NOT_UNIQUE` until the table definition, input fingerprint and
producer invocation select one. An `equivalent_input_candidates` label is
evidence that comparison was possible; it is not evidence that the historical
producer has been uniquely recovered.

## Runtime receipts and external-process boundaries

Keep dated, append-only runtime receipts beside the acceptance batch. Each
receipt should record the RStudio session names/ports and liveness, the observed
`Rscript.exe`/`Mplus.exe` parent information, the command line when Windows
exposes it, and explicit counts for `new_cfps_submissions` and
`external_processes_touched`. The closure finalizer should discover all
`runtime_health_*.json` receipts rather than naming only one snapshot; this
prevents a later Mplus PID rotation from being mistaken for a new CFPS replay.

Classify a process by its input command and parent chain, not by the executable
name alone. An Mplus process for another chapter is an external process and is
read-only evidence for CFPS; do not terminate, attach to, or count it as a
CFPS model. A healthy RStudio session likewise proves transport availability,
not that an analysis has been submitted. A strict CFPS gate remains closed
when no new CFPS submission occurred and source/contract blockers remain.
