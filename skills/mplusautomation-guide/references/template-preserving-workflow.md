# Preserve complete study templates

Use this route when a study already has reviewed `[[init]]` templates whose full
equations, covariance structure, member-specific controls and constraint steps
must survive reproduction. The simplified four-family configuration runner does
not automatically represent all such models. Do not replace the original
specification just to fit its narrower schema.

## Read-only execution specifications

`scripts/template_contracts.py` reads a frozen CSV manifest and each registered
INP/template SHA-256. It writes structured literal specifications and feature
summaries, without creating runnable input files or invoking an estimator:

```text
python template_contracts.py execution_manifest.csv --output FRESH_CONTRACT_DIR
```

Required CSV fields are `model_id`, `registered_inp`, `registered_inp_sha256`,
`template`, `template_sha256`, `substitutions` (a JSON iterator-value object) and
`sandbox_relative_path`. Optional `manuscript_dependency` separates required
models from the larger candidate set. Windows output paths are compared without
case after normalizing slash styles and single-dot components; absolute paths,
parent traversal and collisions are rejected.

The inventory preserves ordered commands, ON/WITH/PWITH statements, parameter
labels, MODEL INDIRECT, MODEL CONSTRAINT, sample filters and inference options.
It strips both line comments and `!* ... *!` block comments while retaining
quoted text. Repeated commands and command tails without a semicolon are recorded;
they are not silently repaired or automatically declared invalid. These writing
patterns can occur in historical outputs that Mplus accepted.

This is a literal inventory, not a universal Mplus grammar validator. Duplicate
options or unsupported statement layouts can require manual review. Read the
original INP and preserve its hash; a parsed contract is not a substitute for
native syntax acceptance, data lineage, identification or scientific review.
`receipt.json` is written only after the full inventory completes. Retain an
incomplete directory as a failed attempt and use a fresh output directory after
fixing a parser defect; do not mistake a partial JSONL for a complete manifest.

## Native expansion without replacing model logic

Load `scripts/compile_template_bundle.R` and call:

```r
source(file.path(skill_root, "scripts/compile_template_bundle.R"), local = TRUE)
compile_mplus_template_bundle(
  template_path = frozen_template,
  template_sha256 = expected_sha256,
  expected_files = all_expected_basenames_for_this_template,
  output_dir = fresh_isolated_directory
)
```

The function checks the original hash, parses the iterator values, predicts all
output filenames, rejects unsafe paths/collisions/scope mismatches, and then
rewrites only the single literal `outputDirectory` declaration in `[[init]]`.
The template body, filename pattern, iterator values and conditional branches
are retained. MplusAutomation `createModels()` performs the actual expansion.
The receipt binds the original and relocated template, generated INP hashes,
package version and initialization-parser function hash. Logs stay in the isolated
directory. The function never invokes Mplus or prepares study data.

Filename prediction uses MplusAutomation's internal `processInit` function as
observed in version 1.2. Its source hash is part of the receipt. An upgrade needs
the same compilation checks; do not presume an internal API remains compatible.
Filename tags support direct iterator values, scalar values and indexed lists.
The outputDirectory declaration must be a single quoted literal. Keep unsupported
template dialects out of this entry until they have an explicit implementation
and test, rather than weakening confinement checks.

Pass the complete expected filename grid for a template, even if only a subset
will be estimated in the first batch. Native expansion and estimation selection
are distinct operations. A smaller expected list fails before file generation;
it does not silently drop constraint steps or modify iterator-indexed label lists.
Before estimation, reconcile each generated INP with its frozen source contract,
stage and hash the verified data, check output-write paths, and select the exact
approved model list. Do not use a loose filename filter to approximate that list.
When a study's source prerequisite remains open, this function must not be used
to bypass that prerequisite; development tests can use independent synthetic
templates instead.

## Chapter 4 coverage and pending native acceptance

The full 18-template inventory contains 2,328 candidates, including the 612-model
manuscript subset. Its extra models include 180 APIM and 1,080 APIMeM instances
with repeated parameter labels. None of those 1,260 equality-constrained instances
belongs to the manuscript subset. Thus an unconstrained `step1` demonstration
does not cover the full candidate requirement. Across the full grid, 672 inputs
declare COMPLEX/MLR and 1,656 declare ML/native BC; these counts describe syntax,
not valid completed estimates.

The study's execution review also keeps 120 USEVARIABLES patch proposals, 24
historical input errors within that set, and 13 other INP/OUT-echo differences
separate. Absence of a listed issue is not native acceptance. Preserve original
syntax reproduction separately from reviewed revisions, and retain the historical
OUT and data bindings rather than attaching them to changed inputs.

Current implementation checks: 22 synthetic static-contract tests; 16 native
`createModels()` tests of a synthetic paired-mediation template with free versus
equal labels and a conditional MODEL TEST block. The 2,328 literal study contracts
were independently reconstructed and compared with all active source tokens;
1,392 constraint-step patterns were checked against iterator positions. Research
templates have not been compiled under this new entry. On 2026-10-15, two separate
synthetic paired-mediation models were also fitted with Mplus, preserving different
member controls and free versus equal b paths; parameter-count, likelihood ordering
and path-product checks passed. These synthetic native fits do not establish
Chapter 4 historical-source reproduction.

Repeat the bounded checks with `scripts/test_template_contracts.py` and
`scripts/test_compile_template_bundle.R`. Do not promote the test receipts to a
full-study execution or scientific-release claim.
