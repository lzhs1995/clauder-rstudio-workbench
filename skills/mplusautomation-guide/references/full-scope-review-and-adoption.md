# Full-scope inference review and manuscript adoption

## Separate four completion claims

Keep execution/file delivery, numeric candidate coverage, inferential validity,
and manuscript adoption as separate states. Preserve the original reproduction
categories as a baseline; a later repair cannot retroactively turn a changed
specification into an exact reproduction. In Chapter 4 the original 612-model
classification was 320 report-precision agreements, 4 data-version differences,
216 parameter-structure differences and 72 sample differences. Agreement is not
evidence that identification, dependence or substantive assumptions are valid.

Apply inference gates to their actual contract. Historical direct/moderation
models in this audit have no bootstrap request, whereas mediation/conditional
models request bootstrap. Do not impose a new BC requirement on every item merely
because another family needs it. Record the bound models and original comparison
categories per item, then distinguish cluster covariance/convention review from
the additional whole-spouse BC/Monte Carlo gate where required. Existing point
agreement alone closes neither gate.

An alternative solver producing every parameter is not the same as every Mplus
fit passing engine calibration. Preserve engine precision exceptions and all
normal-termination/diagnostic evidence. A complete candidate CSV is not a
rendered or visually verified Word/SVG/PDF artifact.

## Complete families, aliases and correction

Freeze hypothesis membership before inspecting p-values. Join by model identity,
physical effect polynomial, sample/likelihood signature and declared family.
Distinct testing units need not be statistically independent. Do not call display
rows, model identities or all nonconstant effect rows independent tests.

For each family, verify every required canonical unit, finite p-values, uniqueness,
canonical source identity and agreement of alias p-values. Preserve aliases on
their own effect scales and retain genuine symbolic constants with no p/q values.
Use the entire frozen family for adjustment, including results absent from the
manuscript; never correct just the displayed or significant subset.

Independently recompute BH and BY with native R `p.adjust` and compare the full
vectors, not only significance counts. Hash the effect, membership and adjustment
files. Reconcile a stale `pending` state only after verifying its corresponding
completed evidence; preserve the earlier generation receipt.

Chapter 4's full kernel analysis contains 35,268 effects, 5,388 constants and
29,880 nonconstant rows. The frozen alias mapping yields 24,264 unique units in
12 complete families: direct 80, mediation 608, moderation 2,040 and conditional
mediation 5,360 for each of total/fy/sy. Native R recomputation gave maximum BH
and BY differences of about 1.77e-14 and 3.82e-14. These counts describe this
contract, not universal denominators for APIM studies.

BH needs the relevant dependence assumptions. BY's arbitrary-dependence result
still requires valid input p-values. Family-wise application does not establish
a single FDR bound for the entire dissertation. A corrected Wald/delta p-value
is not a corrected BC confidence interval; retain both 90% and 95% intervals
and their actual provenance. Failure to pass a threshold does not prove zero
effect, and passing does not release data, design or identification gates.

Evidence under `scientific_audit_20261002`: `ledger/unified_testing_units.csv`,
`full_kernel_family_adjustments.csv`, `full_kernel_family_coverage.csv`,
`full_kernel_effects_with_adjustment.csv`; native checks in
`validation/full_kernel_family_adjustments_native.csv` and
`full_kernel_family_adjustments_verified.json`.

## Independent manuscript binding

Generate all required item candidates, then use a separate implementation to
verify each display row against (1) the frozen item/effect binding, (2) the
unadjusted inference ledger, and (3) the complete-family adjustment ledger.
Check display order, named path/probe, N, clusters, point, SE, both intervals,
p/q, constant status, source hashes and unique row keys. Independently recompute
normal endpoints and p-values; do not only compare a candidate with its own
aggregate copy. A native R readback provides a separate arithmetic/schema check.

Normalize boolean fields explicitly at language boundaries. Python CSV writers
can emit `True`/`False`; R may import these as character columns. Require exactly
TRUE/FALSE after case normalization, reject missing/unknown tokens, and only then
use logical negation or release checks. Do not rely on `any()` coercion or silently
turn an unknown string into FALSE. The first native Chapter 4 readback failed on
this type mismatch; the strict conversion was added and the full check reran.

Reconcile companion identity and order against the frozen inventory. Preserve
the older historical/reproduction fields. Link each companion to its item, but
leave visual verification false until the actual artifact is rendered and
inspected. Count a repeated figure/table path as multiple display rows, not
multiple new hypotheses. Store per-item checks and input/candidate hashes.

The full Chapter 4 candidate target is 279 main items, 209 companions and 5,328
display rows. See `scripts/build_full_kernel_adoption_review.py`,
`validate_full_kernel_adoption_review.py` and
`validate_full_kernel_adoption_native.R`. Acceptance is determined by the actual
`validation/full_kernel_adoption_readback.json` and
`full_kernel_adoption_native.json` receipts, never by the generator's counts.

Even full numeric coverage leaves whole-spouse BC/Monte Carlo adequacy, source
and specification interpretation, sample selection and final manuscript review
open. If several repairs change together, report a joint specification
comparison; do not attribute a changed significance marker to just one repair.
An old BC estimate and a new cluster-delta estimate must retain separate labels.
Two conflicting frozen cells or unresolved bootstrap endpoints cannot be
silently fixed by copying a newer candidate.

## Frozen precision exports while the engine queue runs

The local Workbench 0.3.4 completion checker treats `validation`, `manifest` and
`csv_rows` artifact types as CSV regardless of filename. A JSON file can therefore
produce a misleading "csv has N data rows" receipt. Use `validation::` with
explicit `min_rows` for actual CSV, and `file::` for a JSON existence/size gate;
parse and verify JSON fields/hashes independently. A harness artifact PASS is
neither JSON-schema validation nor statistical acceptance. Keep a mistaken
contract's evidence and issue a corrected receipt rather than relabeling it.

Freeze completed output identities independently of the live queue. Reuse a
precision cache only when its OUT/RESULTS hashes match; keep old checkpoints
readable. Export only the remaining fixed list in small chunks, recording source
hashes before/after and writing a completion receipt after every row succeeds.
Do not change the frozen membership when additional engine models finish.

`RESOURCE_HOLD` from an admission probe is not an estimation error and does not
justify a duplicate job. An empty chunk directory or partial parameter CSV is
not a completed export. Continue lightweight independent review while the
resource coordinator protects Mplus; do not lower a memory threshold solely to
produce a success message. An active R worker executes its submitted source,
so editing a script on disk does not alter that worker's code.

Chapter 4's `snapshots/unified_20261004_02` froze 298 completed fits, reused 83
hash-matching caches and scheduled 215 precision exports. Those are snapshot
counts, not current live-queue progress. Read each `chunks/*/complete.json` for
actual export completion and poll the unchanged engine job for estimation.

The first completed 20-model export was read back with the 83 cached models:
103 precision bundles passed RESULTS values, printed rounding, covariance
symmetry/diagonal and source-identity checks. This did not mean 103 strict engine
calibration passes. At the unchanged parameter <1e-4 and printed-LL <0.0006
thresholds, 87 passed and 16 remained exceptions: the earlier 71/12 plus a new
16/4. The new four have not inherited the earlier 12 independent-optimizer
explanations. Retain their identities and diagnose them separately; numerical
parsing, source identity and scientific calibration are different claims.
Evidence: `scripts/validate_current_precision_snapshot.py` and the frozen
snapshot's `precision_readback.json`, `precision_readback.csv` and
`raw_diagnostic_lines.csv`. The initial export leaves 195/298 precision bundles
pending; subsequent exports need their own receipts before changing that count.
