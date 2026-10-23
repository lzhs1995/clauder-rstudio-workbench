---
name: mplusautomation-guide
description: Use when running or reproducing Mplus models from R with MplusAutomation, including APIM, mediation, moderation, conditional mediation, [[init]] templates, ClaudeR/RStudio execution, multiple imputation, batch recovery, diagnostics, and manuscript tables.
---

# MplusAutomation Guide

Status: v1 operational guide. Windows execution, recovery, resource admission
and manuscript reconciliation are documented from the PP-LGCM workflow.
Project acceptance still requires explicit dispositions for every requested
model family and manuscript cell. A guide release does not establish that all
original hypotheses were tested or that licensed macOS Mplus was validated.

Use MplusAutomation as the R interface and licensed Mplus as the estimation
engine. For a requested ClaudeR workflow, first use the sibling
`clauder-rstudio-workbench` skill to bind RStudio and prove the actual agent
tools. An offline Rscript run does not establish that chain.

## APIM, mediation and moderation

For distinguishable-dyad APIM, APIMeM, APIMoM and b-path conditional mediation,
start with [the APIM operating guide](APIM.md). It routes new data through
`workflow.R` and complete existing `[[init]]` templates through the template
preserving compiler. Keep each route's inference and supported-scope contract.

The [native synthetic acceptance](references/synthetic-acceptance.md) covers
18 functional Mplus fits and four scheduling comparisons, with independent
effect, plot-data, Word-table, migration and recovery checks. A missing
historical thesis source does not block these independent skill operations;
manuscript adoption and historical reproduction retain their own requirements.
The [APIM reference map](references/reference-map.md) indexes Chapter 4 lessons.
Use the general workflows below for the other supported model families.

## Windows Mplus优先资源执行

启动模型或处理内存/速度问题时，先读 [Mplus优先资源流程](references/mplus-priority-resource-workflow.md)。使用轻量监控、已授权回收、按进程限制诊断BLAS线程和证据约束的并发调度；区分启动阻塞、CPU瓶颈与换页，保留模型规格和原有准入合同。Windows paging 计数只作诊断，不能用单项计数新增任意硬门槛；用实测增量、commit 和 Windows 可用内存决定并发。

## Workflow

When the author has chosen to stop estimation and narrow the manuscript, use
[scoped-manuscript-closeout.md](references/scoped-manuscript-closeout.md).
Resume existing candidate artifacts at the first missing acceptance gate;
do not execute the estimation steps below merely to close an editorial issue.

1. Inventory scripts, data, generated inputs, output readers and manuscript
   tables. Hash the originals. Distinguish current R specifications from
   historical `.inp` specifications before calling either a replication.
2. Create a new local run directory outside cloud synchronization. Give each
   script, model invocation and variant its own namespace. Repoint copies of
   hard-coded paths and `here()` roots explicitly; changing `getwd()` alone
   does not isolate an old analysis script.
3. In the target R session, record `R.home()`, `.libPaths()`, package versions,
   the resolved Mplus executable and the actual output version. Consult
   [platforms.md](references/platforms.md) for Windows, macOS and WSL details.
4. Run a synthetic model through the requested execution chain. Submit the
   reviewed worker once and poll its original job ID. When sourcing inside
   ClaudeR's async environment, use `local=TRUE` to retain its progress function.
5. Plan the model graph before executing a long script. Treat table rows,
   measurement scales and trajectory shapes as separate estimates when their
   actual inputs are independent. Use [parallel-models.md](references/parallel-models.md)
   for durable queue workers, resource admission, and manuscript merge gates.
   When a run takes unexpectedly long, use
   [performance-diagnosis.md](references/performance-diagnosis.md) and the
   read-only [queue_diagnostics.py](scripts/queue_diagnostics.py) before raising
   concurrency or restarting estimates.
   When resource pressure holds work, follow
   [resource-reclamation.md](references/resource-reclamation.md) to reclaim
   authorized idle infrastructure, measure the effect, and resume ready models
   while continuing lightweight work. A resource check is not a stopping point.
   For historical reconstruction, before admitting an expensive branch, match its input fingerprint against
   the historical `.out` inventory. Reuse or import successful estimates first;
   place no-history Bayes/LMS or overlong attempts in the explicit deferred
   lane after archiving and identity-verified stopping when that matches the
   agreed replication scope. Authorized new-study models are not deferred merely
   because they have no historical output.
6. Execute dependencies before consumers. Keep `.out` with the exact saved
   imputations and factor scores it describes. Resolve readers to that model
   directory; a shared basename is not a sufficient identity.
7. Validate each requested model and imputation. Record estimation errors,
   failed dependencies and exclusions separately. A completed attempt and a
   valid estimate are different states.
8. Reconcile raw estimates, standard errors, sample scopes and fit statistics
   before reviewing rounding or Word formatting. Trace displayed path labels
   to actual `ON`, `WITH` or `XWITH` syntax. When a historical table differs,
   use [data-and-table-reconciliation.md](references/data-and-table-reconciliation.md)
   to separate changed source data from estimation and presentation differences.
   After a reboot, disk-full event or stale worker registration, follow
   [recovery-runbook.md](references/recovery-runbook.md) before restarting any
   coordinator or estimator.
9. Route adjacent work through the appropriate verified skill and retain its
   evidence in the same run manifest. Use [cross-tool-handoff.md](references/cross-tool-handoff.md)
   for compareGroups, Stata, Word, Zotero, PDF and NLM boundaries; do not
   replace a model or table audit with a generic document review.
10. Before a manuscript deliverable is released, apply the three-pass NLM
    gate in [nlm-three-pass.md](references/nlm-three-pass.md). NLM feedback is
    advisory until every claim is linked to a source result or a documented
    editorial decision.

## Resources

- [native-worker-and-quadrature-recovery.md](references/native-worker-and-quadrature-recovery.md): bind native Rterm/Rscript jobs by identity, separate startup and estimation failures, preserve free-format outputs, and calibrate quadrature before complete-MI inference.


- [binary-observed-interaction-computation.md](references/binary-observed-interaction-computation.md):
  avoid unnecessary integration for an observed binary moderator when the
  conditional Gaussian model has an equivalent known-class representation;
  calibrate all parameters and robust covariance before using it, and keep
  faster computation separate from admissibility and complete MI inference.

- [charls-roster-missingness.md](references/charls-roster-missingness.md):
  verify child/household crosswalks before within-family contrasts, distinguish
  structural absence from missing responses, and prepare scoped moderation inputs
  without treating additive MI or a complete-case pilot as full inference.

- [bounded-research-reopening.md](references/bounded-research-reopening.md):
  resume author-approved mechanism research after scoped closeout, reuse prior
  failed attempts, bound pilot cost, distinguish H4 feasibility from complete MI,
  and rebuild adjacent-construct external-study inputs before fitting.

- [cfps-review-scale-and-sensitivity.md](references/cfps-review-scale-and-sensitivity.md):
  follow-up manuscript review after completed reproduction, actual CESD scale
  identity, common-sample sensitivity, Mplus line/label repairs, wrapped
  diagnostics and the boundary before adding more interactions.

- [figure-and-lrt-scientific-audit.md](references/figure-and-lrt-scientific-audit.md):
  SVG rendering limits, conditional curve equations, syntax-based axes,
  imputation permutations and comparable-likelihood repairs.

- [pp-lgcm-document-reconciliation.md](references/pp-lgcm-document-reconciliation.md):
  output-specific producer binding, historical-sidecar limits, Word simple fields,
  stacked-imputation descriptions and truncated NLM response handling.
- [cross-dataset-migration.md](references/cross-dataset-migration.md): move a
  research framework between panel studies, audit measurement and historical
  provenance, and validate each model family. Includes irregular-time loadings.
- [reusable-models.md](references/reusable-models.md): substitute data and source
  column names through `model_mapping.R`, preserving explicit growth-model
  syntax; validate renamed-column reuse before applying it to a new study.
- [mplus_workflow.R](scripts/mplus_workflow.R): exclusive-directory runner for
  a self-contained `mplusObject`, output diagnostics and hash manifests.
- [synthetic-smoke.R](assets/synthetic-smoke.R): licensed integration template.
- [replication.md](references/replication.md): old scripts, imputations and
  exploratory branches.
- [validation.md](references/validation.md): acceptance and evidence boundaries.
- [windows-result-export.md](references/windows-result-export.md): recover
  long-path table/plot export failures from saved objects, verify artifact
  hashes, and release only owned idle headless browsers.
- [compare_numeric_data.py](scripts/compare_numeric_data.py): streaming, keyed
  comparison of numeric CSV/free-format data with explicit schema, missing
  values and tolerance; aggregate differences only, without row identifiers.
- [power-loss-recovery.md](references/power-loss-recovery.md): recover local
  queues after power loss or reboot while preserving completed estimates.
- [pp-lgcm-worked-example.md](references/pp-lgcm-worked-example.md): project
  worked example mapping Tables 4.2.1, 4.3.1 and 4.4.2.1 to independent
  model families, success-first scheduling and manuscript acceptance gates.
- [cfps-acceptance.md](references/cfps-acceptance.md): completed-producer
  boundary, canonical render artifacts, semantic table binding and explicit
  manuscript acceptance states; incremental input audits, overwritten historical
  sidecars, derived interaction labels and LRT evidence checks.
- [cfps-residual-register.md](references/cfps-residual-register.md): PP-LGCM
  residual-register workflow, MI data-readback versus scientific acceptance,
  income-derivation diagnostics, and resource-gated submission boundaries.
- [cfps-historical-reproduction-candidate.md](references/cfps-historical-reproduction-candidate.md):
  turn the full audited cell ledger into an isolated historical-reproduction
  candidate packet before deciding whether any new estimation is justified.
- [cfps-historical-release-ledger.md](references/cfps-historical-release-ledger.md):
  combine the closed historical version, rounding and review contracts while
  keeping 669 limitation/deferred cells and scientific release gates explicit.
- [cfps-deferred-recovery-queue.md](references/cfps-deferred-recovery-queue.md):
  classify the 669 deferred cells into dependency-blocked, failed, unprepared
  and historical-sidecar limits; reopen them only with a new evidence contract.
- [cfps-deferred-output-audit.md](references/cfps-deferred-output-audit.md):
  read existing `.out` files without rerunning Mplus, separate ordinary
  warnings and ignored auxiliary exports from incomplete MI replications, and
  preserve the moderation/VCOV inference boundary.
- [cfps-scientific-boundary-audit.md](references/cfps-scientific-boundary-audit.md):
  keep version choice, LRT evidence, MI acceptance, and derived-score source
  rules separate while reusing historical outputs.
- [cfps-lrt-disposition.md](references/cfps-lrt-disposition.md):
  preserve historical LRT displays while withholding formal p-value release
  until exact pair, nesting and pooling contracts are complete.
- [cfps-lrt-data-identity.md](references/cfps-lrt-data-identity.md):
  verify real `.dat` hashes and the second-layer primary-MI crosswalk before
  releasing D2 or pooled LRT results.
- [cfps-mi-v3-hold.md](references/cfps-mi-v3-hold.md):
  separate successful MI data readback from income-definition and convergence
  acceptance before submitting downstream consumers.
- [cfps-mi-v3-preflight.md](references/cfps-mi-v3-preflight.md):
  isolated Windows repair admission, bounded income support, final MI diagnostics,
  and downstream producer/consumer release gates.
- [cfps-rank-source-disposition.md](references/cfps-rank-source-disposition.md):
  bind score sources before consumers and keep four rebuild-required sources
  outside the estimation queue.
- [charls-scientific-gate.md](references/charls-scientific-gate.md):
  reuse existing CHARLS artifacts while keeping timeout, boundary and formal
  adoption states separate.
- [charls-oldest-urban-full-recovery-20261023.md](references/charls-oldest-urban-full-recovery-20261023.md):
  Windows parent-identity contracts, pilot-to-full start evidence, semantic
  moderator migration, and receipt-preserving recovery of a 20-MI XWITH
  family.
- [charls-son-urban-pilot-timeout-20261023.md](references/charls-son-urban-pilot-timeout-20261023.md):
  C3/C4 semantic migration, namespace-qualified R bootstrap checks, adapter
  syntax validation, and the bounded son-by-urban pilot timeout rule.
- [charls-boundary-readback.md](references/charls-boundary-readback.md):
  independently read existing CHARLS registries and distinguish summary rows,
  process closures, timeout cases and method-review rows.
- [windows-skill-compatibility.md](references/windows-skill-compatibility.md):
  Windows-specific atomic-write and symlink-capability lessons from the full
  repository test run.
- [cfps-rounding-contract.md](references/cfps-rounding-contract.md):
  reproduce the historical AIC/BIC display precision from existing outputs and
  the observed R rounding behavior without rerunning models.
- [windows_host_profile.py](scripts/windows_host_profile.py): lightweight Windows-native
  admission profile with physical/commit/disk headroom, native CPU samples and
  paging telemetry; the full process census is optional.
- [windows-performance-admission.md](references/windows-performance-admission.md):
  measured Windows resource admission, parent-chain ownership, MplusAutomation
  run contract, and the rule that paging counters require joint interpretation.
- [type1-tech3-calibration.md](references/type1-tech3-calibration.md):
  measured single-slot TECH3 calibration, parameter-identity checks, and stale
  ClaudeR async-record recovery after durable completion.
- [windows-memory-census.md](references/windows-memory-census.md):
  RSS/private-byte interpretation, MCP/RStudio process attribution, and safe
  reclamation boundaries on a 16 GiB Windows host.
- [external-mplus-classification.md](references/external-mplus-classification.md):
  classify Windows Mplus processes by parent chain and working directory so
  external chapter audits do not get counted as CFPS/CHARLS estimates.
- [cfps-review-331-technical-triage.md](references/cfps-review-331-technical-triage.md):
  distinguish a scientific review queue from missing Mplus producers and route
  the formerly diagnostic fit groups and the twelve technically reconciled derived
  alias groups.
- [charls-reuse-first-boundary.md](references/charls-reuse-first-boundary.md): Windows
  CHARLS registry/artifact reuse-first inventory, FCS/MI/boundary checks, and the separation
  between engine success and scientific adoption.
- [type1-joint-structure-calibration.md](references/type1-joint-structure-calibration.md):
  modeled indicators that also act as predictors, historical `SAVEDATA` errors,
  and the boundary between a restricted Gaussian check and exact `TYPE=RANDOM`
  plus `XWITH` likelihood calibration.
- [cfps-derived-word-label-audit.md](references/cfps-derived-word-label-audit.md):
  Windows read-only verification of DOCX X/W/Z/Y labels against exact R
  `XWITH` blocks and historical Mplus parameters; prevents numeric reverse-
  basename matching from silently selecting the wrong producer. It also records
  the R `readModels`/`rename`/`tab_spanner` assembly layer, where aliases can
  reverse the displayed table labels.
- [cfps-figure-provenance.md](references/cfps-figure-provenance.md):
  target-aware DOCX media pairing, SVG label matching, dynamic `SimpleSlope_`,
  `TwoWay_`, and `ThreeWay_Facet_` producer binding, and explicit boundaries for
  figures whose historical generator is outside the six PP-LGCM scripts.
- [cfps-rank-source-readback.md](references/cfps-rank-source-readback.md):
  read back all 16 rank/score sources and 384 consumer bindings from existing
  evidence, preserve four isolated corrected-score candidates, and keep MI-gated
  consumer submission closed until scientific acceptance.
- [cfps-moderation-readback.md](references/cfps-moderation-readback.md):
  read-only inventory of existing moderation `.out` files, interpretation
  boundaries, and pre-specified paths for future checks.
- [cfps-moderation-optimization.md](references/cfps-moderation-optimization.md):
  theory-led ways to improve information and power while prohibiting
  post-hoc significance selection, including the dual within-output/global
  multiplicity readback and NLM review boundary.
- [cfps-b1-b2-boundary.md](references/cfps-b1-b2-boundary.md):
  evidence limits for MI D2/LRT release and conditional-slope Wald testing.
- [cfps-moderation-conclusion.md](references/cfps-moderation-conclusion.md):
  evidence-constrained reporting language for moderation results.
- [cfps-moderation-evidence-v2.md](references/cfps-moderation-evidence-v2.md):
  ClaudeR/RStudio read-only audit of 56 historical moderation outputs, audit-only
  multiplicity columns, covariance availability, and safe interpretation bounds.
- [cfps-manuscript-provenance.md](references/cfps-manuscript-provenance.md):
  combined table/figure/source/runtime checkpoint that keeps historical draft
  reproduction separate from scientific release and downstream CHARLS/NLM gates.
- [cfps-six-script-lineage.md](references/cfps-six-script-lineage.md):
  six-script role map, exact line/hash audit, MI support-range boundary, and
  source-to-table/figure gating rules for the PP-LGCM draft.
- [acceptance_contracts.py](scripts/acceptance_contracts.py): portable comparison
  counting, printed-number rounding boundaries and minimum LRT evidence gates.
- [cross-tool-handoff.md](references/cross-tool-handoff.md): Windows routing
  and evidence contracts for RStudio, Stata, compareGroups, Word, Zotero, PDF
  and NLM workflows.
- [nlm-three-pass.md](references/nlm-three-pass.md): the required three-pass
  NLM review before a final manuscript or appendix is released.
- [nlm-network.md](references/nlm-network.md): the Windows/MacBook Clash Verge
  egress gate for `notebooklm.google.com`.
- [nlm-cli-auth.md](references/nlm-cli-auth.md): version-aware `nlm 0.13+`
  capability and authentication checks. `nlm notebook list --json` is the
  authoritative auth proof, and the Clash rule is host-local.
- [thesis-refiner-nlm-contract.md](references/thesis-refiner-nlm-contract.md):
  the handoff contract consumed by the canonical `论文精炼助手` skill.
- [lpa-lca-workflow.md](references/lpa-lca-workflow.md): LCA/LPA class enumeration,
  semantic class naming, posterior classification and category-probability plots.
- [lta-workflow.md](references/lta-workflow.md): LTA measurement invariance,
  transition probabilities, Step-3 boundaries and the Chapter 7 decision to
  separate descriptive Mplus models from R-side logistic regression.
- [ms-lta-workflow.md](references/ms-lta-workflow.md): syntax-first Mover–Stayer
  classification, sparse mover diagnostics, automatic repairs and alluvial
  reporting.
- [chapter7-replay-map.md](references/chapter7-replay-map.md): model-family to
  script/output/manuscript evidence map for the Chapter 7 replay.
- [chapter7-method-source-audit-20261001.json](references/chapter7-method-source-audit-20261001.json):
  citation-key, DOI/URI and attachment-verification boundaries.
- [zotero-windows.md](references/zotero-windows.md): Windows local API,
  reversible stale-lock recovery and attachment/full-text evidence contract.

## Operational Rules

- Resolve and pass `Mplus_command` explicitly. Use native Windows R and Mplus
  when the statistical runtime is on Windows, including WSL-controlled tasks.
- Set `killOnFail=FALSE` in shared environments. Recovery must not terminate
  unrelated Mplus jobs; supervise only processes owned by this run.
- Pre-provision packages in an isolated library. Do not run old scripts'
  installation, clearing or deletion commands in the user's foreground session.
- Keep estimator, seeds, starts, integration, constraints and missing-data
  rules intact. Infrastructure repairs and statistical changes need separate
  records and result namespaces.
- Budget R workers multiplied by Mplus processors, plus memory and disk. The
  number of source scripts is not a sufficient concurrency recommendation.
- Keep a headless local monitor as the durable evidence collector. The executor
  owns long-running polling; the supervisor samples only at startup, terminal
  transitions and resource/heartbeat alerts. If the monitor dies, verify disk
  headroom and restart exactly one collector before considering coordinator
  recovery. Do not treat a visible panel or stale `PROGRESS.md` as model proof.
- Resume only after validating input/specification hashes and prior outputs.
  File existence alone cannot establish a successful prior run.
- Treat queue `deferred` as an intentional, evidenced exclusion from the
  completed-estimate set. It blocks consumers and must remain visible in the
  final manuscript audit; do not silently convert it to success or failure.
- Share synthetic examples and anonymized lessons, not private participant
  data, personal paths or Mplus licenses.

## Windows NLM reliability

Use `scripts/nlm_reliability.py` and `references/windows-nlm-reliability.md` for
Windows UTF-8 query capture, bounded retry classification, source validation
and the `WINDOWS_NLM_E2E_PASS` release marker. `READY_FOR_NLM` from a notebook
list is not equivalent to a successful source query. The Chapter 7 acceptance
receipt is `final_delivery_20260930/nlm_final_manifest_20261001.json`; retain
the two independent A5 result files and exclude empty-source responses.

升级或评估新版Mplus前，读取[版本兼容性与性能验证](references/mplus-version-compatibility.md)。
