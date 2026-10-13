# mplusautomation-guide

This subskill documents reproducible Mplus 9 workflows driven by
`MplusAutomation` through a live ClaudeR/RStudio session. It covers isolated
Windows/macOS/WSL paths, asynchronous polling, memory-aware parallelism,
historical-output reuse, multiple-imputation and LRT contracts, Mplus output
readback, and manuscript table/figure provenance.

The examples and evidence references are sanitized. They do not contain
participant data, licensed Mplus files, or machine-specific result trees.
Project-specific receipts belong in an external run directory and should be
linked by a manifest rather than copied into this skill.

This v1 guide keeps project acceptance separate from software execution.
Every requested model family and manuscript cell must have an explicit
disposition; not estimated, deferred and rejected are distinct from a valid
null result. A successful Mplus process or `readModels()` call is not by itself
a scientific or manuscript acceptance decision. See the
[scoped closeout workflow](references/scoped-manuscript-closeout.md) for
author-approved stopping rules and evidence-bound manuscript delivery.
