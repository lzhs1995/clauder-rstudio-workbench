# Descriptive tables and manuscript claims

During refinement, keep a claim/table inventory tied to the original manuscript
and the exact versioned table specification. An unchanged row still needs review;
a deleted or consolidated row needs a recorded destination for its evidence.

Compare the retained objects and unformatted numeric CSV first, then display CSV,
DOCX and Word PDF. Check sample keys/membership, not just equal N. For every table
record the analysis unit, wave/group, denominator, missingness rule, value labels,
ordered levels, reference category and declared row/column set. Overall N,
available-case N and subgroup N are different quantities.

Differentiate raw storage, display rounding and comparison tolerance. A Stata float
may differ from an R double at hidden decimals; preserve that explanation and the
original tolerance rather than adjusting tolerance until a comparison passes.
Labels are metadata, not a reason to recode IDs or silently drop unknown categories.

Use the workbench's `completion-check --empirical-contract /absolute/trace.json`
when a task needs machine-checked sample/denominator/result lineage. This checks
existing hashed results and runs no statistics. A result-generation change belongs
in a new spec/run; do not rebuild every table for a Word-only layout correction.

An NLM report of missing data, wrong direction or inconsistent N is a review item.
Resolve it against the exact table variant and local data chain, preserve the raw
report and quote, and update only confirmed errors. Then regenerate affected
outputs and invalidate their downstream review. The numerical engine and existing
compareGroups validation remain authoritative; long-text review adds a separate gate.
