# Bounded research reopening after manuscript closeout

Use this when the author explicitly reopens unfinished hypotheses. Preserve the
accepted manuscript and its closeout state; create a separate research root and
execution contract. A new research request does not invalidate an earlier
scoped delivery, and a successful pilot does not complete the larger study.

## Reuse and scope

- Read prior model receipts and the exact input/data identities before running.
  An unchanged failed specification is evidence to reuse, not an automatic retry.
- Distinguish latent baseline factors, observed baseline measurements and factor
  scores. Keep the requested estimand; do not substitute zero residual variance,
  class membership or a different outcome merely to obtain a legal result.
- Register all planned branch/resource combinations. Separate direct-path
  heterogeneity from a three-way interaction, retain lower-order terms, and test
  group differences directly. Do not condition eligibility on a significant
  average interaction or compare subgroup stars.
- A register written after a pilot is prospective for later work, not a claim of
  preregistration before seeing that pilot. Document its timestamp and scope.
- Single-member feasibility, a complete MI family, pooled inference and manuscript
  adoption are separate milestones. Do not average p-values, discard failed MI
  members, or predict an unrun model from another model's small FMI.

## Budget and admission

Freeze total and per-category limits, per-attempt timeouts and a small recovery
reserve. Count failed attempts and syntax-only repairs. A conservative ledger may
charge the full Rscript plus Mplus subprocess wall clock; identify that accounting
instead of calling it precise Mplus CPU time.

Inspect Windows physical and commit headroom, CPU and existing engine ownership.
MCP data preparation can overlap one estimating engine. More engine workers need
measured headroom and a coordinator that actually reserves resources atomically;
do not add workers merely because a model runs slowly. Release only owned process
trees, verified by PID and creation time, at the agreed cap. Polling granularity
and shutdown cause a small recorded timeout overrun; include it in the ledger.

In the 2026-10-15 pilot, eight attempts cost about 19.2 minutes including runner
overhead. The two CFPS derivative trials still had negative SY residual variance;
H4.1 had one legal member, H4.2 hit its ten-minute cap. Three CHARLS linear models
were legal after one input syntax repair. This supports bounded triage, not a
claim that complete moderation or H4 inference was achieved. Available Windows
memory at engine admission was roughly 3 GiB; the failed statistical branch was
not demonstrated to be a RAM shortage. This was a single engine lane with
parallel R preparation, not a multi-engine speed benchmark.

## Input and progress failures

- Token checks must consume complete numeric start values, including scientific
  notation. An exponent `e` is not an undeclared variable. Keep a negative control
  with a genuinely unknown variable so a repair does not disable validation.
- Emit each separately labelled Mplus regression as its own semicolon-terminated
  statement: `sy ON ix (bis); sy ON sx (bss);`. Multiple parenthesized labels on
  a single statement can cause an input error before estimation.
- A runner exit code of zero does not prove estimation success. Read raw Mplus
  errors before interpreting missing saved parameters as a parser failure. Keep
  the failed directory and perform a syntax-only repair in a fresh directory.
- When using ClaudeR async, source with `local=TRUE`. Otherwise a real engine can
  advance while MCP still displays only `stage=started`, because the sourced code
  lost the injected progress callback. An engine heartbeat and MCP stage are
  distinct observations. Correct the next submission; do not rerun finished
  estimates merely to repair a progress display.

## External-study measurement gate

Contact frequency and emotional closeness are adjacent constructs, not identical
measures. An ordinal frequency score is not an annual count. Audit wave-specific
residence codes before assigning a co-resident child the highest frequency:
the same numeric code can mean adjacent housing in one wave and co-residence in
another. Ambiguous near-neighbor residence does not establish daily meetings.

For CESD, inspect actual item labels and codes. Items can move between modules
or change variable numbers. Record reversal and item-completeness rules. A legacy
score that agrees on complete responses can still use a different partial-item
rule; do not describe changed missingness as proof that all legacy totals were
wrong. Rebuild the cohort for the new age/wave contract rather than importing
old age-50, constant-child-count or class-analysis selections.

Keep the source boundary explicit when reusing already filtered child-long data.
Recomputing aggregates is not a complete reconstruction of every original roster.
Resolve birth-rank ties without arbitrary row order. Preserve household identity;
one participant per household does not establish complex survey weighting.

An independent pandas/Stata check must promote float32 columns to float64 before
group means and SDs when comparing against R doubles. In the pilot, apparent
differences of about 4e-7 disappeared at double precision; do not silently relax
a substantive data tolerance or alter data to accommodate reader precision.

## Delivery

Publish aggregate reports, exact model inputs/outputs, parameter covariance and
hash manifests through an explicit per-file selection. Keep DAT, RDS, individual
scores and identifiers local. Split archives at the agreed size limit. Separate
failed attempts, adopted pilots and unrun registered models in the report.
No new NLM rounds are required merely to release a diagnostic report; a new
manuscript candidate still follows the manuscript review workflow.
