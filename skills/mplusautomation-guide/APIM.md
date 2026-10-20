---
name: mplusautomation-guide
description: "Use for reproducible RStudio workflows that generate, run, read, and post-process Mplus APIM, APIMeM, moderation, mediation, or conditional mediation models with MplusAutomation and [[init]] templates."
---

# MplusAutomation Guide

Turn a declared dyadic model into an isolated, inspectable workflow:
**R data → `[[init]]` → `createModels()` → `runModels()` → `readModels()` → effect data → tables and figures.**

Use `clauder-rstudio-workbench` for RStudio connection, async progress and transport recovery. This skill owns model inputs, execution identity, result extraction and output checks. A case-specific missing historical file is not a universal prerequisite for new analyses or independent synthetic tests.

## Choose the executable route

- **New data and configurable variables:** read [executable-workflow.md](references/executable-workflow.md), load `scripts/workflow.R`, and adapt `assets/example_config.R`. Stages: check, prepare, compile, fit, parse, effects, render, validate.
- **Existing complete study templates:** read [template-preserving-workflow.md](references/template-preserving-workflow.md). Use `scripts/template_contracts.py` to inventory frozen inputs and `compile_mplus_template_bundle()` to relocate and expand the full template. Preserve equations, controls, covariances and equality labels. Expansion does not execute models or infer effect-label meanings.
- **Authorized archived DAT/INP replay:** read [archived-replay-runtime.md](references/archived-replay-runtime.md) for separate provenance/adoption states, measured resource admission, owned Windows awake requests and readback recovery.
- **Portable synthetic acceptance:** read [synthetic-acceptance.md](references/synthetic-acceptance.md). This verifies technical support within the tested scope, independently of a thesis's historical source or scientific conclusions.
- **Chapter 4 reusable v2 route:** read [apim-v2-implementation-acceptance.md](references/apim-v2-implementation-acceptance.md). It documents the schema-2 configuration, multidimensional `[[init]]` expansion, APIM/APIMeM/APIMoM/b-path APIMeMoM effect mapping, native Mplus acceptance, resource coordination, and migration contract.

The configuration runner supports two distinguishable members, continuous observed variables, explicit complete-case samples, actor/partner paths, mediation, moderation and b-path conditional mediation. Choose COMPLEX/MLR with a declared cluster or ML/native **row** BC bootstrap explicitly. Consult the complete support matrix before replacing a study script. Unsupported specifications need an appropriate reviewed template or a separately implemented extension.

## Chapter 4 v2 reusable contract

`schema_version = 2` keeps the original v1 runner intact and makes the research
specification data-driven. `assets/example_config_v2.R` is the sanitized fixture;
the caller changes only the data path, member-column mapping, sample names,
equation controls, moderator declaration, probes, contrasts, equality groups,
inference and output root. Core model code remains unchanged.

The v2 path is deliberately staged:

```text
config check → isolated source snapshot → selected rows/DAT + dictionaries
→ multidimensional [[init]] expansion → durable queue/Mplus
→ readModels precision mapping → effect dictionary/effect CSV
→ plot data/SVG/PNG/PDF + Word/HTML tables → independent validation
```

The grid axes are explicit (`sample`, member-specific `x/y/m/w`, constraint
`step`). APIM and APIMeM use direct and a/b paths; APIMoM uses product paths for
paired or shared continuous/binary/categorical moderators; APIMeMoM reports the
conditional indirect effect through the moderated b path. Equality labels are
compiled into Mplus and the result reader maps repeated labels by semantic
parameter identity. Native BC intervals are read from Mplus's printed
`CINTERVAL(BCBOOTSTRAP)` section and are never replaced by a Wald interval.

Every run has its own root. Source files are hashed and copied read-only; the
root may not overlap any source or protected directory, and aliases/hardlinks
are rejected. Preparation, compilation, parsing and effect artifacts carry
code/data/output bindings, so resume reuses only an identical completed stage.
The queue admits workers from measured available RAM, commit headroom, disk and
CPU, and can use a second slot only after a native calibration receipt. A high
Windows memory percentage alone does not hold a job when the declared headroom
contract is satisfied.

## Operating sequence

1. Bind exact data, scripts, templates, executable and outputs with hashes and versions. When a script changes, identify affected stages and retain unaffected results. See [source correction and evidence reuse](references/source-correction-and-evidence-reuse.md).
2. Create an independent output root. Declare members, columns, row/cluster IDs, sample filters, missingness, transforms, controls and moderator probes. Keep original IDs as text; save selected-row and variable dictionaries.
3. Prepare with `prepareMplusData()`, expand `[[init]]`, and verify the exact model list. The full template grid, execution selection and manuscript subset are distinct. Do not replace an exact list with a broad path filter.
4. Execute through the bound RStudio session. For long jobs use durable async workers, emit stage/message/time progress and poll the same job ID. Use exact INP paths, an explicit executable and `killOnFail=FALSE`.
5. Read exact OUT files with `readModels()`, retaining summaries, errors and warnings. Verify sample size, inference and precision layout. Preserve native BC endpoints; normal Wald p-values are not BC p-values.
6. Save effect CSV/RDS and plotting data before rendering. Include every configured effect regardless of significance. Check member/path/probe/interval bindings, arithmetic, Word page fit and visual readability separately.
7. Reuse finished work after identity checks. Keep failed attempts, recover unfinished stages explicitly and avoid duplicate estimation. Deliver logs, configuration, hashes, checks and limitations.

## Windows and concurrent work

Read [windows-resource-coordination.md](references/windows-resource-coordination.md). Measure native Windows RAM, commit, owned Mplus CPU service and queue progress. Diagnose pressure; do not merely wait for memory, repeatedly clear caches or treat a working-set drop as reclaimed capacity.

`scripts/windows_coordinator.py` observes or reversibly adjusts only Mplus children of an explicit PID plus creation time. Preserve other RStudio sessions and unsaved research. Reclaim only confirmed inactive, recoverable workloads. Record each change and restoration. Default to one owned Mplus slot; expand only with measured capacity and coordination. Compare the same model/data before claiming a speedup; retain default scheduling if benefits are unstable.

## Completion boundaries

Generation, engine completion, parsing, numerical checks, display checks and scientific adoption are separate. A warning-free synthetic example is technical evidence for that example, not scientific approval of a manuscript.

Do not modify protected sources or rebuild a missing historical workspace outside the requested scope. Record unrecovered provenance honestly while continuing independent authorized skill work. Exclude real research data, participant IDs, private paths and session histories from shareable examples and release evidence.

Use the [reference map](references/reference-map.md) for detailed Chapter 4 lessons, diagnostics, bootstrap distinctions and recovery procedures.
