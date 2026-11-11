# Chapter 7 automatic Step-1 → Step-3 binding

`scripts/ch7_step_chain_20261111.R` reads a completed Step-1 Mplus output and
its declared savedata, extracts each wave's printed classification logits,
and passes them to `ch7_mixture_object()`. It never starts Mplus. Load
`ch7_mixture_tools.R`, `ch7_mixture_syntax.R`, then the chain script.

```r
# Paths below are relative to the private run directory.
chain <- ch7_step3_from_step1(
  step1_out = "step1/model.out", step1_savedata = "step1/posterior.dat",
  id = "sid", nominal_map = c(n1 = "MLCC1", n2 = "MLCC2"),
  latent = c("c1", "c2"), classes = 3L, family = "lta"
)
# chain$object is an mplusObject; chain$data is the private Step-3 input.
# Compile with mplusModeler(run=0) in a fresh run-owned directory, then:
receipt <- ch7_step3_chain_receipt(chain, "step3/model.inp")
```

`family="mslta"` uses the existing mover/stayer generator and retains its finite
logit approximation. `keep` optionally names additional savedata columns to
project. `...` passes declared estimation options to the generator. The source
Step-1 must declare an `IDVARIABLE`; integer IDs must be unique, nonmissing and
exactly representable. The Step-3 object also preserves `IDVARIABLE`.

The ordered `latent` vector defines waves. `nominal_map` names the new nominal
variables and maps them to the corresponding `MLCCn` column by the Step-1
`CLASSES` declaration order. `MLCJOINT` and joint `CPROB` columns cannot silently
substitute for wave-specific classifications. Missing classifications, unknown
waves, duplicate cells, changed class counts and mismatched file paths fail.

The chosen table is **Logits for the Classification Probabilities for the Most
Likely Latent Class Membership (Column), by Latent Class (Row)**. Rows are true
latent classes, columns are assigned classes, and class K is the reference.
The average-posterior table has the reverse conditioning and is not used.
The direct logits remain unchanged; printed zero probabilities are not smoothed.
The companion forward-probability table is checked with a bound derived from
both tables' printed precision. This is a printing-consistency check, not a
validation of the underlying mixture model.

`ch7_classification_error()` exposes the extracted logits and probability
matrices for private scientific use. `chain$lineage` records output/savedata
SHA256, table line positions, selected text hashes, direction, reference class,
mapping and dimensions; it contains no IDs or raw estimates. Local absolute
paths are kept separately in `chain$private_paths`. `chain$data`,
`chain$error_source` and the complete object remain private for real studies.

The compiled receipt independently checks the source hashes, Step-3 DATA path,
column projection by ID, nominal/ID/class declarations and fixed logits in their
correct latent namespaces. Its status is `PASS_COMPILED_LINEAGE`, with
`engine_estimated=FALSE`. A new native Step-1→Step-3 claim additionally requires
the authorized RStudio/ClaudeR→MplusAutomation→Mplus execution receipts for both
stages, their output hashes, convergence and warnings. An archived output used
to exercise this adapter does not become a new estimation.

The synthetic contract is
`test_ch7_step_chain_20261111(output_dir, skill_root)`. It covers two/four waves,
K=2/3/4, variable names, column-split tables, both SAVEDATA layouts, fixed-width
negative values, explicit native-call interception and mutation failures. It
uses synthetic text/data only and separately records native execution as
`NOT_RUN`.
