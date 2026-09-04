---
name: comparegroups-guide
description: Use when creating publication-ready descriptive statistics or Table 1 outputs with the R compareGroups package, especially from labelled Stata data, panel/repeated-cross-section data, attrition samples, or ClaudeR-managed RStudio workflows.
---

# compareGroups Guide

Use this skill to turn a versioned JSON table specification into reproducible
descriptive statistics, a true three-line Word table, machine-readable numeric
results, retained `compareGroups` objects, validation evidence, and hashes.

`compareGroups` remains the statistical engine. ClaudeR interprets the request,
audits the project, executes the runner, follows async progress, and reconciles
the verified numbers with the manuscript. This skill does not replace either.

## First reads

- Personal output conventions: [user-style-profile.md](references/user-style-profile.md)
- Cross-section, panel, repeated-cross-section, and attrition choices: [data-structures.md](references/data-structures.md)
- Contract fields and parameter mapping: [comparegroups-api.md](references/comparegroups-api.md)
- ClaudeR sync/async workflow: [clauder-integration.md](references/clauder-integration.md)
- Required validation: [validation.md](references/validation.md)

## Standard workflow

1. Copy the nearest template from `assets/` and edit only the copy.
2. Audit the actual input before choosing methods:

   ```bash
   Rscript scripts/check_dependencies.R
   Rscript scripts/audit_input.R --spec /absolute/path/table-spec.json \
     --output /absolute/path/input-audit.json
   ```

3. Verify Stata labels, categorical codes/order/reference, repeated IDs,
   grouping counts, missingness, and the requested independent analysis unit.
4. Run one contract once:

   ```bash
   Rscript scripts/run_comparegroups.R \
     --spec /absolute/path/table-spec.json \
     --output-root /absolute/path/results
   ```

5. Validate the durable outputs independently:

   ```bash
   Rscript scripts/validate_comparegroups.R \
     --output-root /absolute/path/results \
     --stem Table_1
   ```

6. Reconcile the unformatted numeric CSV with the manuscript. Treat the DOCX
   as presentation, not as the numeric source of truth.

## Hard rules

- Never overwrite an input dataset, an old R script, or an existing DOCX.
- A numeric unlabelled categorical variable must declare its levels explicitly;
  unknown labelled codes block the run.
- Prefer Stata variable/value labels, but record every override in metadata.
- Repeated person-wave rows are not independent. With `panel_mode: "dual"`,
  produce a safe primary view and a clearly labelled pooled compatibility view.
- For attrition comparisons, construct retained/deleted status before filtering
  and use one baseline row per person as the formal analysis unit.
- Use one ClaudeR async submission for a batch and poll only its original job
  ID. `running` and transient transport errors are never reasons to resubmit.
- Use workbench fan-out only for genuinely independent table contracts.
- A run passes only when the DOCX reopens, the numeric and display outputs are
  complete, the manifest hashes match, and every validation row is `TRUE`.
