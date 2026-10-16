# Templates and Data

MplusAutomation's parser, rather than an ad hoc replacement loop, owns template
expansion. See the [official vignette](https://cran.r-project.org/web/packages/MplusAutomation/vignettes/vignette.html).

`[[init]]` declares iterators, their values, linked lists, output filenames and
directories. The body contains Mplus syntax, list tags (`[[name#iterator]]`) and
conditional blocks whose closing tags must match exactly. All init assignments
need semicolons. Give every generated input a unique path.

Before `createModels()`, copy the template and rewrite only its outputDirectory
assignment to an absolute sandbox path. Record the original and adapted hashes.
After expansion, check model count, filename uniqueness, remaining `[[` tags,
DATA paths, NAMES order, selected observations, labels and output filenames.
Repeated section headers are a lint finding; do not invent a failure diagnosis
without a completed Mplus diagnostic.

For historical replication, the INP and its historical DAT form a pair. A current
same-name DAT may have a different N, column order or income definition. Record
both current and recorded-sample input paths. Never infer input equivalence from
sample size alone. A model-name DAT produced by SAVEDATA RESULTS is an output,
not the raw data read by DATA FILE.

For a new-data rerun, export ordered numeric columns with `prepareMplusData()`.
Keep an explicit ordinal column dictionary and missing-value policy. Verify the
export's columns against NAMES, including unused variables. Dyad/person/wave IDs
must retain their intended identity; do not use a long numeric ID that was rounded
on import as a sole join key.

In the Chapter 4 workflow, spouse-wide f/m columns are stacked to compute pooled
means and SDs, then standardized columns return to the wide input. The stage
samples are standardized separately and row-bound for USEOBSERVATIONS filtering.
Those transforms differ from applying full-sample SDs to each subgroup. Directory
names containing 2sd or 3sd do not prove the formula used.

Templates can expand more candidate models than the manuscript uses. Keep an
expansion inventory and a separate execution manifest; neither count substitutes
for the other. Do not run all candidates merely because createModels generated them.

Before expanding a large execution queue, distinguish a variable's roles in
NAMES, DEFINE and MODEL. A raw NAMES variable may be used only to construct an
interaction in DEFINE without entering USEVARIABLES itself. If that same raw
variable is also a main effect in a MODEL ON statement, it must be admitted to
USEVARIABLES. Do not add every DEFINE operand indiscriminately or silently remove
a main effect to make the input run. Check conditional iterator branches, strip
comments and parameter labels, and preserve reference-category/model semantics.

Chapter 4's two APIMoM `*_1n.txt` templates illustrate this distinction: 24 existing
outputs reject SIBM_1/SIBM_3; static branch checking exposes 120 affected candidates
(40 total, 80 lifecycle), none among the manuscript's 612 dependencies. Missing
female/main-effect variables must also be checked even when Mplus reports only
the first male variable. Keep repairs in a separate candidate template and require
native validation after execution is authorized; a missing-variable lint pass is
not complete Mplus syntax or inference acceptance.

While execution is gated, prepare review-only diffs against hash-bound historical
inputs. Check both affected and unaffected branches; verify the change is confined
to the declared variable admission and rehash originals afterward. These diffs
are expected changes for later native template expansion, not a substitute for
`createModels()` or evidence of successful estimation. Keep runnable inputs and
data generation out of this review step.

The 2328-candidate historical inventory has 781 existing outputs: 757 terminal
results with screen flags and 24 errors; 1547 have no output. A screen flag can be
an ordinary input warning, so it does not establish statistical failure. Bind
each existing output by hash and classify errors/ending/results/diagnostics before
deciding what can be reused under the selected data/engine contract. The counts
describe this audit, not a universal expected workflow size.

Hash registration of INP and OUT separately is not a same-run binding. Compare
effective INP code with the historical OUT input echo, using quote-aware comment
handling and retaining reviewable differences. A long comment can trigger input
truncation warnings without changing code, while the same file pair may still
have unrelated parameter/probe edits. In the expanded Chapter 4 inventory, 13 of
781 pairs differ although all 612 manuscript dependencies match. Probe assignments
and their formula references can change together and algebraically cancel; test
the resulting estimand before equating textual drift with changed inference.

Use exact substitution for probe constants before comparing derived expressions.
In this case, 8 lifecycle models preserve all 96 simple slopes despite changed
constant names/values, while 4 total-sample models change 32 of 48 slopes. This
does not prove that every NEW parameter is identical. For alternative dummy
reference categories, verify binary, exhaustive, mutually exclusive indicators
and missingness on the consumed sample. With a free intercept, d1=1-d2-d3 gives
`a+b1*d1+b2*d2=(a+b1)+(b2-b1)*d2-b1*d3`; additional constraints and the inference
contract still require review. Matching a few GH5 columns is not full row-ID or
upstream CSV provenance.
