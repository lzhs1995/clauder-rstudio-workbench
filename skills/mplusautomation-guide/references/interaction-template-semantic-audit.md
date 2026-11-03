# Semantic audit after migrating an interaction family

A model can use the intended grouping variable and still have an incorrect delivery packet. A Windows CHARLS known-class family exposed four reusable boundaries.

## Parse the executed input, not the generator

When a family is migrated by replacing a control or group variable, inspect every actual `.inp` file. Expand `VARIABLE: NAMES` into an ordered vector, derive the group column by name, and check `USEVARIABLES`, `KNOWNCLASS`, the `%cg#%` blocks, and the TECH1 parameter specification. Do not infer semantics from copied labels (`p042`) or from the historical Python/R generator. A full parameter/VCOV check can pass while a copied label sidecar still names the wrong control.

Keep a separate map from actual matrix/row/column identities to printed labels. Recompute the map from the executed input and TECH1, then prove that the linear transformation and saved estimates are byte-identical before changing only the derived report. Preserve before/after hashes for every input and output.

## Treat a zero diagnostic as data

A cluster containing both levels of a grouping variable is not guaranteed. If the grouping variable is constant within every cluster, the correct mixed-cluster count is zero. Do not hard-code a requirement that `mixed > 0`, and do not reuse a count from the old grouping variable. Report the robust-cluster structure and its implication for interpretation; do not silently change the model to manufacture mixed clusters.

## Recover an unclear async submission without duplicate estimation

A missing job id or transient add-in response is an observation failure, not proof that the worker stopped. Check the durable stage files, owner PID/create time, MIDS/MI hashes, engine receipts, and parent chain before submitting again. If a second submission is attempted, an existing MIDS guard may reject it. Record the distinction precisely: **no duplicate computation** is different from **no duplicate submission**. Never manufacture a native guard receipt after the fact.

Formal long work requires a real native smoke, `async-guard pre-submit`, the actual wrapper job id, immediate `register-job`, and polling of that same id. A public or local verifier does not establish those transport facts.

## Calibrate a migrated family without rerunning the family

If the full MI family has already finished but same-sample parent/quadrature evidence is missing, create a new isolated, bounded contract. A useful minimal contract is ordinary parent → known-class parent → low-point A/B checks against the saved high-point endpoints. Freeze the LL, parameter, SE, VCOV, engine-time and first-failure gates before starting. Reuse existing full-family outputs; do not rerun all members, add p-value-driven retries, or claim that an education calibration proves an urban calibration.

The final acceptance must have separate states for: actual syntax/parameter mapping, numerical calibration, full-family Rubin inference, and manuscript adoption. A passing calibration does not complete H4 or the original CFPS moderation families.

## Gender × urban recovery, 2026-10-22

The new urban family used `C4` as its known class and retained education `C3`
as a control. A case-sensitive migration initially left lowercase
`KNOWNCLASS=cg(c3=0 c3=1)` unchanged. The pre-engine assertion caught it:
zero engine calls, preserved failed attempt, then corrected syntax. Check the
actual NAMES order, USEVARIABLES, KNOWNCLASS and normalized slot map together.

The corrected parent then terminated normally, but an education-specific
`mixed > 0` reader assertion failed: urban residence was constant within all
432 communities. Preserve the original error receipt, verify the unchanged
input/output hashes, fix the group-column lookup and reader assertion, and
read back the existing parent output. The parent was not re-estimated.
Four dependent pilot calls then completed the bounded five-call pilot.

Do not rename an education MI directory and admit it as urban MI. Quarantine
the inherited receipts, keep the original source read-only, and generate the
urban-compatible working MI in a fresh directory. This case retained 25 X×Z
and 25 urban×X×Z observed auxiliary products, imputed only the 14 missing ADL
values, and preserved all original observed values and structural masks.
Twenty draws produced 19 distinct DAT hashes; discrete identical draws do
not permit dropping an MI member or treating B starts as replacement draws.
These checks do not prove MAR or exact latent-model congeniality.

Earlier `local-1` SMOKE/GUARD JSON files were hand-written task summaries,
not executable harness evidence. Preserve and label that limitation; do not
retroactively claim a formal PASS. The recovery used the real native smoke,
raw wrapper outputs, `pre-submit`, actual job registration and terminal
archival. For example the native smoke evidence was
`c26a78d3-a776-40d5-a2e4-728524764cd5`; the resumed pilot's original job was
`61bdcf8b`. Those identifiers describe this case, not reusable admission for
another session. Formal delivery must use an actual `completion-check`.

Source entry scripts with `local=TRUE`. The resumed pilot, new working MI and
full-family job exposed native progress with the same original job IDs; no
RStudio restart or duplicate parent estimation was needed. Windows foreground
RStudio can be named `rsession-utf8.exe`, while async children can be
`Rterm.exe`; bind PID **and creation time** to the native session instead of
assuming a single executable basename.

## Delivery gate

Hold publication when prose, labels, or diagnostics disagree with the executed input. Rebuild a new package namespace, include the semantic audit and calibration receipt, run the public replay without participant data, split large blobs below the observed proxy limit, and anonymously read back every part. Keep the held candidate and its error record; never overwrite it or treat a previous `LOCAL_DELIVERY_READY` file as sufficient after semantic findings.
