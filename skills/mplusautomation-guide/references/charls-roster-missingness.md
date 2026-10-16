# Child-roster identity before moderation or imputation

Use this when a family-level exposure or moderator is derived from child records.
Reuse valid parent-model outputs, but verify the child universe before extending
their interpretation from available reports to every listed child.

## Source identity

A legacy script can first require two valid child responses and then drop missing
child rows. Recomputing its mean and SD exactly proves that available-report
definition, not complete living-child coverage. Hash the source and compare keys,
values and the respondent scope separately.

Do not concatenate the household roster and a family-module child loop merely
because their row identifiers look different. The same co-resident child can
occur in both. Prefer an explicit constructed-child to household-member crosswalk;
do not deduplicate on sex and birth year, since twins and genuine shared values
exist. Verify the crosswalk's actual fields against both raw modules.

In the 2011 CHARLS audit, the local constructed `child.dta` supplied `childID` and
`HHmemberID`. Sex, birth year and non-household residence matched the raw sources.
The questionnaire directs household children past CB049–CB063 to CB064. CB048
belongs to a deceased-child loop; CB052 is the living-child birth-calendar item.
A generic label such as “solar or lunar calendar” is insufficient to identify
the correct loop. Check the question's surrounding routing rules.

An official listed child can have every selected response missing, so “any
nonmissing response” is not an exhaustive roster detector. Conversely, an old
valid-response row can lack a key in the constructed file. Preserve both versions
and report exact differences. Do not force equality, silently replace the cohort,
or infer the cause of a source discrepancy without evidence.

## Define absence before imputing

- No sons and one-sex-only families create structurally undefined contrasts.
  Do not impute an oldest-son contrast for an all-daughter family.
- Missing contact, sex or birth year is a different issue. Preserve child-level
  missingness and derive the family contrast after any justified imputation.
- A tied earliest birth year is ambiguous rank. Do not break ties by row order
  or use an unknown/incompatible birth month to manufacture ordering.
- If a missingness table uses mutually exclusive priority categories, state that
  these are not independent prevalences of each missing field.
- An ordinal contact score's absolute differences depend on its numeric coding;
  dividing by its mean adds dependence on the scale origin. Register scale choice
  by meaning, not by which version yields significance.

## Scoped model entry and reuse

The audit retained the published 3,006-person trajectory cohort and generated
separate complete-case pilot entries with verified roster scope. Four entries
contained 2,726, 2,156, 2,510 and 2,369 people. They are data-ready scopes, not
estimates or complete MI families. Their child-count and age distributions differ
from excluded participants; a complete-case pilot does not establish unbiased
population inference. Keep original baseline missing flags when distinguishing
complete cases from legitimate cross-wave source recovery.

Preserve existing trajectory scaling and missing masks; record the moderator's
sample-specific centering and scale explicitly. Reuse additive core/resource MI
results only for their existing purpose. A future latent interaction requires a
justified compatible imputation or joint model; convergence and small FMI from
an additive model do not supply that justification.

Independent verification should reread raw files, not merely rerun the producer.
The audit used pandas/Stata and R/haven and matched 42,084 person fields within
double precision. Private records, IDs, DAT and RDS remain local; publish only
aggregate checks and code. Do not add an Mplus run to settle a roster identity
problem or rerun an unchanged failed CFPS specification.
