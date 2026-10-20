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

## Delivery gate

Hold publication when prose, labels, or diagnostics disagree with the executed input. Rebuild a new package namespace, include the semantic audit and calibration receipt, run the public replay without participant data, split large blobs below the observed proxy limit, and anonymously read back every part. Keep the held candidate and its error record; never overwrite it or treat a previous `LOCAL_DELIVERY_READY` file as sufficient after semantic findings.
