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

## From verified entries to bounded interaction pilots

Freeze the estimand, data hashes, controls, lower-order terms and runtime limits
before fitting. In the follow-up, each verified complete-case scope received a
same-sample parent and one `SX XWITH Z0` interaction. Both models retained the
baseline indicator paths `x1 y1 ON z0`; consequently the Z0-to-latent-intercept
coefficient is conditional on those paths, not the total baseline association.
The observed baseline contrast is not interchangeable with a third latent growth
intercept. Preserve this distinction in filenames, tables and interpretation.

Use the no-interaction parent as the common source for two separately specified
interaction starts. Perturb nonvariance parent starts and give the interaction
opposite signed starts. Do not resume two almost identical interaction endpoints
and call them independent starts. A second start is a diagnostic call, never a
second imputation. Predeclare numerical comparison tolerances and retain any
failure; do not introduce successively tighter checks after the batch ends.

The actual CHARLS follow-up completed four parents and eight interaction calls
in about 595 seconds of engine/launcher wall time, with one engine slot. All four
families passed their two-start pilot checks; all four interaction intervals
crossed zero. This proves neither absence of moderation nor complete MI
inference. The existing additive 20/40-imputation results remain additive results.
Their small missing fraction or FMI cannot establish interaction compatibility.
Do not launch unchanged failed CFPS specifications because a different CHARLS
sample now yields a legal pilot.

Read saved parameter vectors and TECH3 covariance directly, independently of the
R table producer. Bind path identities to raw TECH1, reconstruct the triangular
covariance, and verify standard errors before calculating conditional slopes.
For `bss + dc*z`, retain the `2*z*Cov(bss,dc)` term. Label plotted intervals as
pointwise complete-case Wald intervals, not pooled MI or simultaneous bands.
Check original outcome-missing masks and original baseline control completeness
when choosing the pilot population; previously recovered values need not redefine
the original complete-case comparator.

Publish files by explicit statistical role. `estimates.dat` and `tech3.dat` can
contain aggregate model parameters, while a neighboring `data.dat` contains
individual records. A blanket extension allowlist or CSV-row-count heuristic
cannot distinguish them. Keep the per-file role, hash and original-source hash,
redact local user paths, and independently replay the downloaded public package.
Do not duplicate the raw participant data to make the public verifier runnable.

## Audit the control's item definition before choosing MI

A nonmissing harmonized score need not mean every item was observed. The local
2011 CHARLS ADL construction sums available items when at least one is observed.
Raw db010–db015, including the documented skip rule, reproduced its item coding.
Of 3,006 participants, 2 had partial-item totals and 20 had all six items missing;
none of those 20 totals could be recovered from the same-wave raw items. Retain
the official definition and item-completeness flags. Do not silently turn partial
totals into complete totals, fill all-missing scores with zero, or call an official
partial-sum definition a coding error without a scientific reason.

In the four verified moderator scopes, residual missing core controls were only
ADL (18, 15, 18 and 18 participants). Small counts do not establish ignorability
or compatibility with an interaction model. Existing additive MI does not become
interaction-compatible because its diagnostics are favorable.

Test exact software combinations on synthetic data before expanding a queue:

- In Mplus 9, the tested single-level Bayes interaction with an ordinal control
  and `PREDICTOR=OBSERVED` was accepted, but its short chains did not converge
  and produced no usable imputations. Syntax acceptance is not MI validation.
- The tested two-level version explicitly rejected `PREDICTOR=OBSERVED`.
  This is a restriction on that combination, not a claim that all two-level
  Bayes interactions are unsupported. Removing the option can change an
  observed category predictor into its underlying latent-response predictor.
- Joint ordinal-control MLR reproduced the conditional model's complete-data
  structural paths to about 0.000004 reference SE. Adding missing ADL required
  Monte Carlo integration. Two fixed-seed 5,000-point synthetic runs reached
  their four-minute limits; neither yielded usable missing-control inference.
  Preserve both outputs. Do not turn a concrete interface correction into
  unlimited point/iteration escalation or automatically admit real data.

Record the exact error, estimator, predictor treatment, clustering, actual job ID
and runtime. A model with small RSS and increasing CPU time need not be memory
bound. Timeout accounting includes polling and process cleanup; report the
observed overhead instead of silently enlarging the original budget.

When inspecting synthetic cluster-robust covariance, its score rank is at most
the number of clusters minus one. A 50-parameter model with 40 clusters cannot
have a full-rank robust covariance. Do not misclassify this algebraic limit as
structural nonidentification or relax the real-data inference checks. A synthetic
interface test is not a scientific acceptance result.

See the official [PREDICTOR option](https://www.statmodel.com/HTML_UG/chapter16V8.htm),
[imputation documentation](https://www.statmodel.com/HTML_UG/chapter11V8.htm) and
[version history](https://www.statmodel.com/verhistory.shtml). The retained raw
Mplus output establishes which exact combination was rejected in this test.

## Observed resource interactions and complete MI families

An observed baseline contrast multiplied by observed education or urban status
is a different estimand from a latent slope interaction. Bind it to the original
hypothesis before estimating. The CHARLS H4.1 follow-up covers baseline contrast
paths by education and residence; it does not complete income heterogeneity,
contrast-trajectory associations, CFPS replication, or H4.2.

Generate imputation inputs for the actual analysis scope and include its observed
contrast and resource products. In this follow-up, four separate 20-member ADL
families retained `Z0`, `Z0*education` and `Z0*urban`. Original values, donor
support and outcome missing masks were checked independently. This is an
interaction-aware FCS working approximation, not proof of substantive-model
compatibility or MAR, and not evidence for reusing it in a latent interaction.

Retain lower-order terms and the chosen indicator direct paths in all members.
If `x1/y1 ON Z0 Z0*G` are included, latent-intercept contrasts are conditional
on those paths. Report group 0, group 1 and their difference using the full
parameter covariance, and test the group differences directly with a pooled
joint test. Its rejection alone does not establish “stronger” or “weaker”
association: inspect group-specific direction, scale and uncertainty. Signed
child contrasts and nonnegative SD do not share one direction of disharmony.

Before reopening an income family, resolve the original grouping in the actual
data. The CFPS source code used personal income above its median. In its original
export, corrected pre-MI input and all ten frozen members, that median was zero;
the stored grouping agreed with both `income > median` and `income > 0`. Different
wording was not a numerical discrepancy and did not justify another engine run.
Retain the substantive interpretation: above a zero median need not mean affluent.

Do not substitute CHARLS household income or respondent earnings for that
personal-income construct without labeling the new estimand. The local household
total had 734 missing values among 3,006 participants; the four roster scopes had
670, 529, 605 and 568 missing values. An observed-resource ADL-only MI cannot be
reused as a complete income-interaction family. Preserve negative net income and
derive each product from its own member. A passive transformation enforces an
identity; it does not prove substantive-model compatibility.

Before imputing a household resource on person rows, join the actual participant
keys back to the official household identifier and count respondents per household
within each analysis scope. A unique temporary analysis ID is not that check.
The retained CHARLS cohort had 3,006 respondents from 3,006 official households;
all four scopes also had one respondent per household. Consequently there was no
within-household duplicate income-group draw to reconcile in this particular
batch. Do not generalize that sampling fact to another CHARLS cohort. With
multiple respondents per household, household resources require shared draws or
a justified household-level imputation design; a community random intercept does
not enforce equality of household values.

Check the installed imputer's code as well as current online documentation.
The inspected `mice 3.19.0` binary two-level function lacked the newer
`random.effects` argument and did not implement the documented current default
in the same way. A new option supplied through `...` is not evidence it took
effect. If that binary route is chosen, pin and test the intended implementation
in a separate library. This finding does not invalidate previous `miceadds`
continuous PMM families, which used a different function. A source audit and
proposed MI budget must remain labeled **not imputed / not estimated**.
The [income source supplement](https://github.com/lzhs1995/PP-lcgm-paper/tree/4f1fee8662bd8ea34e52ac699feac19d64d18f60/charls_income_scope_20261016)
records the observed scope and zero additional Mplus/MI calls.

### Test the binary imputer before scaling its family

The income pilot pinned the maintainer's development `mice 3.19.10` build in an
isolated library. Label that provenance explicitly; do not call it a stable CRAN
release or mix its namespace with an older foreground-session version. Test in
a fresh child process. Global `mice` options can travel through `...` into a
conditional fitting function: filter arguments rather than assuming every
imputer accepts them. The inspected binary imputer catches a failed GLMM and can
return the current missing-cell values. A binary range check alone therefore
cannot establish that imputation ran. Require a recorded successful conditional
fit as well as fresh draws, preserved observed cells, passive identities and
the actual predictor matrix.

If a high-dimensional GLMM is slow, benchmark the same formula before changing
the scientific specification. In the retained SD benchmark, TMB and warm-start
lme4 estimates agreed within about 0.00006 reference SE, but their reported SEs
differed by up to 6%. The installed lme4 fit had no finite-difference Hessian and
used its RX approximation. A finite-difference check of the TMB likelihood
gradient reproduced its full fixed-parameter covariance to within 0.000001 in
relative SE. Point-estimate agreement alone would not have established this.

Also inspect random-effect uncertainty, not just fixed-effect covariance. For
this unit-weight binary-logit **random-intercept-only** model, the conditional
Laplace variance at fitted parameters is
`1 / (sum_j p_j * (1-p_j) + 1 / psi)` within each community. The saved TMB
`ranef(..., condVar=TRUE)` variance differed from this conditional curvature by
up to 16.5%, whereas lme4's saved `postVar` agreed to about 0.002%. Renaming the
attribute was not an equivalent backend substitution. The local adapter now
calculates the conditional curvature explicitly, rejects unsupported random
slopes/weights/families, and retains the original stochastic draw sequence.
This remains a disclosed FCS approximation, not an official unchanged imputer
or proof of congeniality. Keep the pre-correction pilot as such; do not promote
its completed draws into the formal family.

Use observed timing to budget the next family. Here the four two-chain,
two-iteration interface pilots took about 348 seconds, with 11 fresh binary
fits, five exact fit-cache hits and 16 ADL fits. A full income family is materially
more costly than the previous ADL-only family: other imputed predictors change
the fitting data. Never reuse a fit for changed data. Save immutable iteration
checkpoints with source and artifact hashes; resume the saved MIDS/RNG state,
not a new seed. Admit complete families only after the declared mixing and
cell-level checks, then estimate and pool them with their own resource group.

For native ClaudeR async scripts, use `source(path, local=TRUE)` so the script
can see the job's injected `clauder_progress` callback. An otherwise healthy
job may stay at `started` when a default global source loses that environment.
Repair the progress connection without resubmitting the estimator: verify the
job owner/PID, then relay its actual durable progress through ClaudeR's progress
API. Preserve the source timestamp so a stale heartbeat cannot look current.

Inspect per-logical-core CPU load before diagnosing slow estimation as a RAM
problem. During the formal income follow-up, eight logical cores were saturated
while eight were lightly loaded; the verified MI worker received only about
0.28 core-seconds per wall second. After a bounded, reversible priority/affinity
adjustment restricted to that owned worker, a 115-second observation showed about
1.00 core-second per wall second. This is an observed scheduling improvement,
not a controlled 3.6-fold model-speed benchmark or proof about CPU topology.
The one-worker memory limit remained in force. Choose from currently available
cores, record the previous mask and PID creation time, preserve the statistical
specification, and recheck load/child affinity. Do not permanently encode CPU
numbers, change another task's mask, or use high/realtime priority. Any coordinator
mask adjustment must be checked on the actual later child and restored if load
conditions change. The observed worker's RSS was about 555 MiB and host free
memory about 1.31 GiB; global CPU utilization or nominal 16 GiB RAM alone would
have concealed this scheduling constraint.

The registered follow-up completed all eight education/residence families, each
with 20 usable imputations, a complete-case comparison and a second-start check:
176 calls in total. Independent raw-parameter/TECH3 calculations reproduced all
eight pooled families. Joint group-difference P values ranged from 0.204 to
0.883; this is inconclusive evidence, not proof of equal associations. Complete
conditional families do not resolve the stated FCS compatibility limitation or
the income and dynamic branches that were unestimated at that stage. Engine/launcher time totaled about
50 minutes; coordinator process wall time including preparation and readback
was about 90 minutes. Report both timing scopes.
The [fixed-commit evidence package](https://github.com/lzhs1995/PP-lcgm-paper/tree/950a01ea8599e0782cc3685563c98265c4fc924f/charls_h41_mi_20261016)
contains aggregate outputs and an independent verifier, with no participant data.

## Save preparation time without duplicating engines

Profile preparation, engine/launcher and readback separately. In the first 64
calls of the H4.1 batch, median engine/launcher time was about 16.7 seconds,
readback 6.7 seconds and preparation gap 6.8 seconds. These are observations
from retained receipts, not a randomized benchmark or proof of a memory limit.

The existing coordinator accepted immutable prepared jobs. A separate native R
task prepared 88 still-unclaimed future inputs in about 58 seconds, caching four
deterministic parent-start calculations with 84 hits. The key included the full
target specification, parent-output hash and perturbation choice; the original
input builder and actual per-member data were retained. No engine or new model
specification was launched. This saved repeated source parsing while preserving
the one-engine memory limit. Only use this approach when ownership of future
inputs is unambiguous; do not race an active writer or mutate a running job.

An input-ready receipt must say **not estimated**. Continue recording each real
Mplus result, and distinguish a second start from an imputation. Cache
deterministic calculations only, never completed random draws or another MI
member's data. A light watcher can bind to the coordinator PID plus creation
time, then pool and independently verify complete families after terminal exit;
it must not restart engines or convert partial families into pooled results.

## Resource deferral and ambiguous async submission

A one-engine limit for this batch must not silently become a ban on every
external Mplus process. In the income follow-up, the original supervisor closed
the first SD member after a 120-second wait solely because another task had an
engine. No Mplus call or budget reservation had occurred. Its label
`INCOMPLETE_STOPPED` incorrectly mixed resource deferral with estimation failure.
The four same-specification complete-case runs had a measured launcher/engine
tree peak of about 179 MiB. Retain a separate `RESOURCE_DEFERRED` state, actual
host memory/commit/CPU gates, and a bounded later retry for never-started members.
Apply the same distinction to second-start checks. Reuse every already valid
member; do not retry a scientific failure under this rule.

Revise admission at a safe checkpoint with the original contract and code
archived. Verify PID creation times, ensure no owned engine is active, preserve
completed MI/RNG states, and reconcile the budget database before recovery.
The observed repair retained one owned engine and allowed at most one observed
external engine at admission, with the existing 1 GiB physical/2 GiB commit
headroom gates. This is a host-snapshot policy, not an atomic shared lease over
unrelated queues, and is not a universal safe threshold. Preserve external
processes and keep an absolute batch deadline across coordinator restarts.
Interrupted partial iterations remain in cost logs; only completed checkpoints
are restored and only the final complete imputations count as MI members.

An async submission can return a communication error after RStudio has accepted
it. Before resubmitting, check durable ownership, session history and the
server's real background-job registry. Here that recovered an actual job ID;
`get_async_result` then confirmed progress and the async guard registered that
same ID. Never invent a replacement ID or start another coordinator because the
client did not receive the acknowledgement.

For WSL `UtilAcceptVsock ... accept4 failed 110`, check the active interop socket
and use a verified working socket for a bounded child-command probe. Socket-file
existence alone does not prove liveness. Preserve Windows Python and USERPROFILE;
do not restart WSL/RStudio or bypass native R's system-command restriction.
Record command-launch delays separately from MI and Mplus computation.

## Keep optional fit caches out of the recovery critical path

A complete MIDS/RNG checkpoint does not guarantee that a separately written
warm-start cache is complete. In this follow-up, an identity-verified stop
preserved iteration 1 but interrupted a non-atomic `saveRDS(fit, ...)`. The
next worker failed in `readRDS(lastfit)` before resuming any imputation. The
16.8 MB truncated cache was archived; the immutable MIDS hash, 40 chains,
saved RNG and 151 valid conditional-fit records remained intact. Classify this
as a recovery I/O failure, not statistical nonconvergence or failed mixing.

Preserve complete fit diagnostics separately, but avoid serializing a whole
fitted object after every draw merely to recover its optimizer starting values.
Such objects can retain large environments. Prefer a small, optional beta/theta
sidecar beside a complete iteration checkpoint, written by temporary file plus
same-directory rename. Validate its shape and finite values on reading. An
absent or unreadable optional sidecar can use a cold optimizer start; invalid
MIDS, changed input hashes, or missing RNG state must still block recovery.
Do not change the stochastic draw rule or optimizer acceptance criteria under
the label of cache repair, and do not count replayed partial-iteration work as
additional completed imputations.

The repaired continuation restored the original checkpoint hash and produced
new complete iterations. Its first observed lightweight warm-start sidecar was
902 bytes, beside a roughly 241 KiB MIDS checkpoint, instead of writing the
16.8 MB full fitted object after each binary draw. This validates the new storage
path, not a claim that the entire statistical family is already complete.

Distinguish conditional-fit timings from total imputation time. One retained
snapshot had 508 conditional fits totaling about 1,174 logged fit-seconds,
against about 2,204 stage wall-seconds. Serialization, draws, diagnostics and
other overhead were outside that fit timer; the difference alone does not
identify their individual costs. A smaller cache is a concrete overhead repair,
not evidence of a measured speedup until the continuation has been observed.

Bind phase-specific watchdogs to the current worker's PID and creation identity.
A later recovery reused a progress file from a dead worker and applied the
150-second conditional-fit watchdog while the new R process was still loading
packages. It killed that new process before any additional conditional fit.
Treat old-PID progress as `WORKER_BOOTSTRAP`, preserve the old source timestamp,
use a separately bounded startup limit, and arm the conditional-fit timer only
after the current worker emits that phase. Do not raise the model's fit limit
to hide a stale-heartbeat classification bug.

CPU masks also belong to a process instance, not permanently to its task label.
The new coordinator had reverted to all logical CPUs; eight were saturated
while others were lightly loaded. An owned pooling worker accumulated only about
six CPU seconds over 140 wall seconds. Re-evaluate host load before each new
stage, select currently available permitted cores, verify the child's inherited
mask and record previous settings. Above-normal priority, when justified, stays
restricted to the owned computation worker; never use high/realtime priority.
Apply the same ownership discipline to a slow verification child. Restarting a
coordinator without restoring its operational policy can undo an earlier speed
repair even when every statistical option remains identical.

Keep real fitting failures distinct. The oldest-son income imputer reached its
120-second elapsed-time limit at iteration 6, conditional call 411, without a
valid fit. Its earlier five-iteration checkpoint was below the declared minimum
and was not promoted to a completed family. Preserve that timeout and its
underlying backend log; the inherited warning mentioning `glmer` does not prove
that the fitted backend was lme4. The zero-fit bootstrap recovery is not a reason
to retry this genuinely attempted conditional fit or silently relax its budget.

## Adjudicate complete families and include postprocessing in scheduling

The income follow-up ultimately retained three complete 40-member families and
one unadmitted oldest-son family. Its 127 engine calls were 120 MI members,
three second-start checks and four complete-case comparisons; the latter seven
must not increase the MI denominator. Raw parameter and TECH3 verification
reproduced three pools and 18 contrasts. Engine/launcher time was about 18
minutes, whereas imputation, resource waits and recovery took much longer.
Measure these stages separately before attributing the whole elapsed time to
Mplus. Preserve the fixed four-family and combined twelve-family testing
denominators, with untested P values left missing. Complete conditional H4.1
families do not complete dynamic moderation or H4.2.

The same host scheduling issue affected packaging: its owned Python process
accumulated only 14.75 CPU seconds in about 429 wall seconds while cores 8–15
were saturated. A fresh sample selected six lightly loaded permitted cores and
the existing packager finished after its recorded adjustment. This is not an
isolated speed experiment or proof that all waiting was CPU-related. Apply
bounded owned-process scheduling to final verification and compression too;
record PID creation time, prior mask and priority, and keep private data out of
published logs. Do not restart a slow packager or rebuild an already verified
archive merely to collect another benchmark.

## Diagnose a failed conditional entry before reopening its family

A timeout records an attempted failure; it does not, by itself, distinguish
an optimizer problem from scheduling, serialization or another elapsed-time
cost. If the original log lacks input identity and phase/CPU timers, state that
limitation. Do not relabel the old attempt as successful after a later probe.

For the oldest-son income failure, a separate diagnostic used the pinned MICE
sampler to assemble the next iteration's conditional inputs from the last
complete MIDS/RNG checkpoint. Capture-only imputation functions returned the
previous missing values without fitting or drawing; every completed chain was
checked unchanged and this artificial MIDS was never saved or adopted. Five
captured inputs exactly matched hashes of the five preceding historical binary
calls. Only then was the sixth entry identified as the failed conditional input.
This depends on verified visit order and chain independence; it is not a generic
shortcut for imputers whose preceding draws alter the target's inputs.

Two bounded fits of that entry, using the prior valid optimizer start and a
cold start, both passed the unchanged numerical checks in about 5.12 and 7.23
seconds. They supplied evidence for one isolated checkpoint continuation, not
a unique diagnosis of the old 128-second timeout or proof of complete MI.
Keep the diagnostic fits outside the imputation-member count and preserve the
old terminal batch. Resume all original chains from the complete checkpoint
and saved RNG; replaying an incomplete iteration is not replacing a failed
member or selecting successful chains. Record deterministic-fit hashes before
fitting, CPU and wall times, and the current process identity so a future failure
can be localized. Reuse already completed families and complete-case estimates.

The isolated continuation subsequently passed the original mixing rule at
iteration 10 for all 40 chains. Forty Mplus members plus one second-start check
completed; the previous complete-case estimate and eleven other CHARLS families
were reused. Independent raw-parameter/TECH3 and input checks closed this
conditional H4.1 family. Twelve completed baseline-resource families still do
not complete dynamic moderation or H4.2, and a nominal joint P value must retain
its fixed-family multiplicity corrections.

Terminal progress schemas may legitimately omit elapsed time. An R wrapper
called `round(NULL)` after the analysis and pooling had completed, producing
`Async job error: non-numeric argument ...`; the tool response nevertheless had
`isError=false`. Inspect terminal content and durable receipts, not that flag
alone. Guard nullable fields before formatting and test the actual terminal
shape. Archive the wrapper error; validate saved outputs in a distinct zero-fit
readback job instead of restarting the analysis or relabeling the failed wrapper
as successful. Record which job estimated and which only reconciled completion.

## Check whether chained iteration is actually needed

Before multiplying imputations by iteration counts, inspect the dependency graph.
In the four observed-baseline CHARLS moderation sensitivity scopes, only ADL was
incomplete. Every conditional predictor was a fixed, fully populated auxiliary
representation. The numeric PMM routine fitted only observed ADL and used only
observed donors; prior imputations did not enter the fit. Twenty independent
conditional draws therefore required one pass per member, not twenty rounds of
burn-in. Each scope's deterministic mixed-model fit was identical across the
twenty calls, while coefficient, random-effect and donor draws remained fresh.
Cache exact fits only, and record the actual predictor matrix, package versions,
fit hashes and draw count. Do not apply this shortcut to mutually incomplete
income/ADL targets, changing passive predictors or latent-variable samplers.

Adding observed Z-by-wave terms and missingness-flag products makes a working
imputer more responsive to the analysis structure; it does not establish exact
substantive-model compatibility for a latent interaction. Keep its complete-MI
sensitivity results separate from complete inference for the original mechanism
and from H4.2. Fixed auxiliary fills are not actual longitudinal observations:
restore and verify the original outcome values and FIML masks in every engine
input. Undefined family contrasts remain outside ordinary imputation.

`mice::complete()` can reset data-frame row names. An `identical()` comparison of
whole frames then fails even when every non-imputed numeric column is unchanged
in the original order. Inspect the difference, preserve the error and verify
column names, order, source binding, values and masks; do not simply disable all
identity checks. If the complete MIDS was already saved, resume its export and
validation without drawing another set. In this case all 51 non-ADL columns
matched and the original twenty SD draws were reused after the metadata-only
check was repaired.

## Verify scheduling in the actual engine descendants

Raising the coordinator priority does not prove that its Python, Rscript and
Mplus descendants inherited that priority. The observed Windows process tree
contained an above-normal coordinator but normal-priority descendants, and its
allowed CPU mask still included a newly saturated core. Inspect actual PID
creation times, parent chains, masks and priorities. A lightweight sidecar may
adjust only verified owned descendants to currently available permitted cores
and above-normal priority, recording before/after settings for each identity.
Do not change input files, estimator settings or acceptance thresholds as a
performance repair. Let the sidecar exit when its verified coordinator exits;
never follow a recycled PID or alter another task's process. Resource admission
and a single owned engine slot remain in force. Report CPU, engine/launcher wall
time and total pipeline time separately; this observation alone is not a
controlled speed benchmark.

Do not repeatedly remove every currently busy core from an already reduced mask:
the owned fit itself can make its core busy, producing a shrinking-mask feedback
loop. Select and record a stage mask, retain its original permitted set, and
check each new child identity once. Prefer the owned heartbeat's PID/create-time
records to repeated whole-host descendant enumeration. If a scheduling sidecar
misbehaves, preserve its log, stop only that verified sidecar, restore the owned
worker's admitted mask and replace the monitor without restarting estimation.

When memory admission fails, count supervisor memory as well as model memory.
An idle ClaudeR background R wrapper supervising Python, which then starts a
second R queue worker, can consume the headroom needed by a small Mplus fit.
After all old process identities and budget reservations close, a distinct native
async job can source the same queue directly, reusing saved imputations and
completed receipts. Keep the engine watchdog, hashes and memory/commit limits;
removing a redundant supervisor is not a reason to weaken admission. Preserve
the earlier partial terminal and bind the new job to its own terminal artifact.

WSL interop errors are separate from Windows computation. A stale socket can
report `UtilAcceptVsock ... accept4 failed 110` while native RStudio and an
already-started Windows worker remain healthy. Verify a current socket with a
small read-only command; inspect durable PID/create-time records before any
resubmission. For 64-bit `ctypes` scheduling calls, declare the handle return and
argument types, check the API's return value and read back affinity. An untyped
pseudo-handle call silently failed in the diagnostic helper; an intended mask is
not evidence that the process received it.

## Recover a lost async submission acknowledgement without duplicate work

During the CHARLS H4.2 preparation, native `execute_r_async` returned a
communication error although the background process had started. A read-only
lookup of the assigned RStudio session's ClaudeR job registry recovered the
actual job ID, submitted code and process PID. Polling that same ID returned
all 24 prepared inputs. Preserve the failed submission response and recovery
evidence separately; never create a successful submission response by hand.
The inspected bridge used a 10-second HTTP timeout for its generic async POST,
so a missing acknowledgement was not evidence of a missing job. The subsequent
model submission returned its ID normally. Do not restart an active bridge or
RStudio merely to repair an observation error.

The Windows R `ps` APIs are `ps_get_cpu_affinity()` and
`ps_set_cpu_affinity()`, with `ps_set_nice(handle, "above_normal")` for priority.
Validate scheduling in the library-loading phase as well as in the model loop;
otherwise a worker can spend minutes waiting before it reaches its own scheduler.
An installed harness also used the cancellation reason in its archive filename.
A prose reason containing `/` produced a Windows path error; a short ASCII
reason code archived the record while the detailed explanation stayed in the
audit log. This is a portability defect to fix in the harness, not a reason to
discard or fabricate the original tool evidence.

For a three-way `SX × Z0 × G` extension, reuse a successful H4.1 parent only
after checking identical data bytes, sample size, variable coding and the full
set of lower-order paths. Add `SX × Z0`, `SX × G` and `SX × (Z0G)` together,
and directly test the last coefficient. Keep the two group-specific moderation
contrasts and conditional slopes with their full covariance. A complete-case
pilot does not complete its MI family; an imputer built for a different
interaction cannot be relabeled as substantively compatible.

## Resume a rebooted batch before adding statistical work

A Windows reboot invalidates both the RStudio process and its asynchronous job
registry. Verify PID plus creation time, archive stale ownership/lock records,
check SQLite integrity and unsettled reservations, and reload saved MIDS and
input/output hashes before resuming. The H4.2 recovery reused 37 legal outputs
and all 80 ADL imputations without estimating them again. A null-filled progress
JSON was retained as evidence; it did not invalidate the intact statistical
artifacts. Rebind the new native RStudio session and record a fresh native-tool
smoke rather than reusing the old session's proof.

The local ClaudeR background registry lives in the package namespace,
`get('.claude_bg_jobs', envir=asNamespace('ClaudeR'))`. An unsuccessful lookup in
`.GlobalEnv` does not prove no task was submitted. Prefer the public polling
tool; inspect the namespace only to recover a lost acknowledgement.

Verify an awake helper's supported lifetime before invoking it. A requested
25,200 seconds exceeded this helper's 14,400-second maximum and caused the
helper to exit. A process handle alone had not proved protection was active.
The repaired coordinator checks an actual `ACTIVE` receipt, matching owner PID
and creation time, and terminates its phase within the helper's lease. This
prevents idle sleep; it does not prevent power loss, reboot or intentional sleep.

Keep startup timeouts separate from statistical failures. One preserved timeout
had zero sampled Mplus CPU and no output. A single separately named recovery
attempt was registered without changing the model or total engine-time budget;
the old timeout was not overwritten or called nonconvergence. In contrast, an
incomplete conditional-imputation fit is not an imputed member and cannot be
replaced silently. R's elapsed-time limit may not interrupt a native optimizer;
use a Windows watchdog bound to worker identity and a per-fit BEGIN/END record.
Keep that record for ADL fits as well as binary-income fits.

Record memory admission separately from process-count admission. After reboot,
two external Mplus processes each used about one core and under 60 MiB RSS,
while Windows had about 2.95 GiB available and 13 GiB commit headroom. The
documented revision allowed those two external processes plus one owned engine,
retaining physical-memory, commit and CPU limits. Those measurements are local
evidence, not a universal three-engine setting or a claim that unrelated queues
share a lease. Never terminate another research queue to satisfy a count gate.

For MI contrasts, pool the full selected covariance matrix. Group moderation is
`dc` and `dc + dcg`; the direct group difference is `dcg`. A conditional slope is
`bss + dc*z + bxg*g + dcg*z*g`. When missing income changes group membership
across imputations, display slopes only within the groups' common observed
support. Retain the predeclared multiplicity family, MCSE, and finite-community
degrees-of-freedom sensitivity. A complete working-MI family does not establish
exact compatibility with latent interactions or complete the original CFPS H4.

Use a distinct awake receipt for each owner identity. A recovery attempt read a
previous owner's `RELEASED` receipt before the new helper published `ACTIVE`,
and correctly stopped before any estimate. The fixed wait checks the new PID,
creation time and state, rather than merely waiting for a filename to exist.

A later coordinator connection error occurred while Mplus itself finished and
wrote valid parameters. The engine supervisor had been tied to R's automatic
process cleanup, leaving no final engine receipt. Recovery retained the
`CLAIMED` row and old lock, verified all owners had exited, validated the saved
output and runner-end marker, then recorded `RECOVERED_SAVED_OUTPUT` with an
unknown exit code and a conservative full-cap time charge. It did not fabricate
an observed successful exit or rerun the model. Bounded JSON retries and
noncritical progress publication now protect the estimator; its independently
bounded supervisor survives an R display-layer failure. Preserve a call trace
on future errors instead of claiming an unobserved root cause.

Dispatch independent admitted families while the next family's imputation is
running. A barrier requiring every income imputation to finish left an available
Mplus slot idle. The revised sequence independently verifies a family's actual
40 datasets, estimates it with the existing single-engine lease, and lets the
next imputation worker continue. Shared result registries still have one writer.
If an imputation worker is replaced, consumers must consult its updated PID and
creation-time lease instead of treating the old worker's exit as a statistical
rejection. This changes scheduling, not the model or missing-data contract.

Check that a receipt exists before passing its path to `jsonlite::fromJSON()`.
A missing path can be parsed as literal JSON and produce a misleading lexical
error. In a Windows startup failure, the R worker exited before either helper
published its receipt; both helpers later correctly rejected the now-dead owner.
There were zero conditional fits and zero checkpoints. Recovery preserved the
logs, increased only the bounded startup wait, and required identity-matched
`ACTIVE` and `WATCHING` receipts before drawing. The recovered job actually
advanced into its second iteration. Keep such infrastructure recovery separate
from retrying a failed statistical fit.

Public path redaction changes bytes even when parameter values are unchanged.
Retain both the original-source hash and the distributed-file hash. Public
verification checks the package bytes against the latter and their source
binding against the former before recomputing parameters and TECH3 contrasts.
A targeted check accepted correctly redacted text and rejected altered bytes;
this is not permission to bypass either hash or to claim byte identity.

Persist the actual native terminal response on the first completed poll. In this
ClaudeR installation, returning a completed response retires the background-job
registry entry; a second poll can return `No job found`. That later response is
neither the original completion log nor proof of failure. Use one observer per
job, save the full first response, and only then close its async guard. The last
income worker and the final modeling coordinator both followed this sequence.
Do not submit another estimate to reconstruct a lost polling transcript.

Close each registered scope at its evidenced state. This batch pooled all 280
members of 11 admitted families (eight with 20 imputations, three with 40),
while retaining the twelfth scope as imputation-not-admitted. Independent raw
parameter/TECH3 replay passed for the complete families. This is evidence for
those conditional working-MI analyses, not a completed original H4, an exact
latent-interaction imputation method, or a reason to drop the excluded scope
from the fixed multiplicity family. Preserve the distinction in the report,
public manifest and next-task handoff.

## Reopen a failed imputation only with new numerical evidence

An unfinished SD-income conditional fit was revisited without rerunning the
failed CFPS specifications. Capture its exact design before changing the
optimizer: the saved design hash matched the historical call, with 67 fixed
effects, full column rank and condition number 30.129. A linear-programming
check found no fixed-effect complete or quasi-complete separation. These checks
do not establish mixed-model identification or the missing-at-random assumption.

For this design, `glmmTMBControl(profile=TRUE)` was the sole numerical change.
The [official control documentation](https://glmmtmb.github.io/glmmTMB/reference/glmmTMBControl.html)
describes this experimental option for models with many fixed effects. Two
bounded, separately initialized diagnostic fits used the same data, formula
and Laplace likelihood. They completed in 11.614 and 11.824 seconds, with
optimizer code zero, positive-definite Hessians and fixed-effect covariance,
positive random-effect variance, and a log-likelihood difference of
2.27e-12. The maximum coefficient difference was 1.24e-10 reference standard
errors. Retain the reported gradient and all diagnostics rather than hiding
them behind a success flag. The unfinished historical fit is not a timed
baseline, so these observations do not establish a controlled speedup ratio.

Numerical feasibility of the first conditional fit is not a completed MI
analysis. A separate two-chain, two-iteration interface pilot passed; its draws
were excluded from the fresh 40-chain formal run. That run retained the original
formula, stochastic rules, seed, data, convergence gates and remaining engine
budget. Its admission and downstream Mplus results must be read from actual
terminal artifacts. Do not describe a running family as complete or replace a
failed member with a successful diagnostic fit.

An external watchdog must exclude its own PID when terminating the worker's
descendants. Otherwise it can terminate itself before stopping the owner or
writing a terminal receipt. A disposable Windows root/child test reproduced
the lifecycle and verified the corrected watchdog stopped both owned processes,
wrote its receipt and left the caller alive. Bind the owner by PID and creation
time, and wait for an identity-matched `WATCHING` receipt before starting work.
No historical watchdog receipt existed for the old SD timeout; the newly found
defect therefore cannot be asserted as that timeout's proven cause.

## Distinguish a publishing timeout from a failed push

A Git push client timed out after 180 seconds. The remote initially still showed
the old commit and later showed the intended new commit. Recovery checked the
remote identity and verified the published bytes before deciding whether to
retry; no second push was needed. Treat a transport timeout as an unknown
publication outcome, preserve its transcript and inspect the remote branch.
Do not attribute success to a buffer or retry option that was never exercised.


## Follow-up waves can invalidate a technically completed family

An October 2026 Windows/ClaudeR run completed all 40 income-interaction
imputations, and independent parameter/TECH3 pooling checks passed. A later
raw-wave audit found that the input builder omitted 2018 children who reported
12 months of co-residence and therefore skipped the frequency question.
Current residential address did not recover every such record. The independent
R/pandas check found 235 omitted child records for 206 parents; in the unchanged
legacy roster, 163 observed means changed and 36 previously missing means became
defined. Every actual model DAT in the 40-member family contained the old X4.

Model execution, parameter extraction and MI pooling acceptance therefore remain
true statements about the **old input**. They do not establish correct survey
semantics. Publish an incremental input-correction notice, preserve old outputs,
and mark corrected-input adoption pending. Do not overwrite history or predict
whether corrected estimates will be significant.

For every wave, bind five layers: raw variable and value labels; questionnaire
routing; child/household identity; derived value and missingness reason; actual
model DAT column and hash. A baseline roster check cannot stand in for all
follow-up waves. Keep PDF hash, printed page and physical page separately:
different questionnaire layouts can have the same printed page but different
PDF page numbers.

An unmatched key first requires a source-map diagnosis. In the measured 2013
case, 1,207 official child-to-household links matched raw xchildmembercv exactly.
Do not concatenate both records as different children. Keep identity agreement
separate from disagreements in sex, birth year or contact, and record the chosen
same-wave source rule. Conversely, 248 observed 2015 contact cells were outside
the same-wave child count and had no constructed-child record. Preserve these
values and quarantine the unsupported identity; a valid response range alone
does not prove that a cell represents an additional child. Do not invent the
unique cause of such a release inconsistency.

Rebuild one isolated candidate across all affected waves before refitting each
family. A separate pandas reader verified 32,795 child records and 72,144
person-by-wave indicator cells against the R rebuild. This establishes numeric
agreement under the stated roster/proxy rules, not the truth of every survey
answer or the identifiability of a longitudinal interaction.

Keep available-contact contrasts and full-listed-child contrasts distinct.
The oldest observed child need not be the oldest child on the roster. Structural
absence, missing attributes/contact and tied earliest birth years need separate
statuses; do not impute every resulting NA as ordinary missing data. Report
source eligibility and per-wave observation coverage before defining a latent
trajectory sample, without requiring a balanced panel merely for convenience.

When X participates in imputation auxiliaries, changing X also invalidates a
claim that old completed imputations arose from the corrected procedure. Rebuild
the affected MI inputs and diagnostics; reuse verified runners and pooling code.
Only then run the bounded necessary parent checks and complete affected families.
This does not authorize unchanged failed CFPS reruns or a significance search.

Aggregate evidence and the fixed-input boundary are available in the
[public source-correction packet](https://github.com/lzhs1995/PP-lcgm-paper/tree/cd7d6ec3218dc313272228a21b93c7368326b062/charls_latent_trajectory_readiness_20261018).
It contains no participant-level data. The original four latent moderation
families and full H4 are still incomplete; this lesson does not close them.


## Preserve statistical state when Windows infrastructure fails

A progress display is not the analysis checkpoint. In the corrected CHARLS
income run, `file.rename()` of a progress JSON failed under a real Windows
sharing lock after a complete MIDS/RNG checkpoint. Keep critical checkpoint
writes fatal, but make the replaceable progress cache nonfatal and append a
small event journal. A watcher can read the newer journal when the cache is
stale. Test with an actual Windows handle denying delete sharing; a mocked
rename alone does not exercise this failure mode.

Checkpoint recovery must distinguish `iteration < target` from
`iteration == target`. The former continues sampling; the latter only checks
and exports. A repair accidentally changed the sampling loop to `<=` and
started an extra iteration. Preserve the deviation, freeze the complete target
checkpoint and its hash, exclude partial extra draws, and finalize with zero
new fits. Do not hide those calls in the accepted-iteration count or silently
adopt them as a better result. Check both boundary cases before submitting.

If an async submission response is lost, look up the existing job by its actual
code, agent, PID and creation time before submitting again. Conversely, after
a verified host reboot, old jobs cannot be revived merely by their IDs. Confirm
the new boot time and disappearance of the old identities, validate every saved
input/output hash, reuse completed members, and resume only the first unfinished
member. A prepared input with no engine receipt is different from a failed fit.
Preserve consumed budget across the new worker and never reset it to zero.

RStudio discovery can recover while an isolated replacement UI is starting.
Recheck the user-assigned port before activating the replacement. Bind to the
actual session and rerun the native wrapper smoke for its new PID. If the
assigned session has already recovered, close only the extra empty project that
this run created, using PID/creation/ancestry evidence. Never kill another
chapter's RStudio or Mplus processes. Windows RStudio's R process can be named
`rsession-utf8.exe`; checking only `rsession.exe` incorrectly reports no R.

## Reduce orchestration cost without changing the estimator

Measure input preparation, R/Mplus launch, estimation and readback separately.
Repeated Python numerical-library imports can cost more than a short model.
A batch-owned persistent helper may call the same frozen compiler and reader;
keep one model slot, explicit request IDs, bounded calls and an owned shutdown.
Verify identical generated/readback bytes and unchanged start comparisons before
using it. The CHARLS helper test compared nine readback files and the double-start
decision without adding an estimate. An initially invalid cleanup API was fixed
and tested separately; preserve that failed cleanup receipt.

`processx::run(timeout=...)` takes seconds, while process `wait()` and `poll_io()`
use milliseconds. Do not mistake `timeout=120000` for a two-minute limit. Model
engine caps and auxiliary-process caps are separate. Also create and validate
the isolated output directories before launching the queue; a missing `models`
directory is a preparation error, not nonconvergence.

One incomplete covariate with fully observed, fixed conditional predictors can
use independent conditional draws. Cache only its identical deterministic fit;
retain fresh parameter, random-effect and donor draws. Do not extend this shortcut
to two variables whose missing values predict one another. Observed products in
working FCS still do not establish exact latent-interaction compatibility or MAR.

For audit metadata, R named atomic vectors can lose their names during JSON
serialization. Export a path-to-hash dictionary as `as.list(named_hashes)` and
validate its shape. A metadata-only verification failure does not justify
re-estimating models whose raw parameters already passed. Preserve the failure,
repair the mapping from its authoritative object, and rerun only verification.

Report completed corrected-input families separately from older-input families,
and conditional working MI separately from the original full latent moderation
and H4 objectives. Runtime reliability and guide publication do not close those
scientific requirements.


## Readiness, parallel FCS and verification-only recovery

Treat a watcher's missing dependency or readiness timeout as an infrastructure
failure, distinct from an invalid statistical fit. Check the owned PID, process
creation time and ancestry before publishing an identity-bound ready marker.
Do not put an expensive whole-machine process scan before that marker. On a
loaded Windows host, allow a bounded startup window with visible progress;
do not accept a stale marker from a previous process. In the CHARLS run, failed
zero-fit startup attempts were retained, and the already successful pilot was
reused while only the unstarted scopes were recovered.

A native ClaudeR error saying the addin is unavailable does not establish that
the submitted worker died. Reconcile the assigned session, original job ID,
owned process identity and durable progress before resubmitting. A successful
HTTP diagnostic is evidence for that fallback, not a fabricated native receipt.
Retain the actual terminal response when closing an async registration.

When changing from serial to parallel FCS, hand over at a complete checkpoint.
Save the original MIDS, RNG state, fit count and hashes; stop the old coordinator
before its next block, not during a valid draw. Assign disjoint scopes to the new
queues and preserve already completed blocks. A scheduling handoff is not a
failed imputation. Keep the original iteration limits and cumulative budgets;
continuing from iteration 10 to 20 must charge the earlier active time.

Admit workers from measured incremental memory, commit headroom and current
CPU demand. Do not assume that free logical CPUs imply enough memory. This
Windows run admitted its second worker only after available memory exceeded
the existing reserve plus its observed approximately 0.46 GiB increment.
The thresholds belong to the run contract, not a universal 16 GiB-host rule.
Measure each owned worker's actual CPU time: a broad affinity mask may still
place both workers on busy cores. A reversible change to separately observed
idle cores improved the short-window utilization here. Keep PID/creation-time
checks, preserve the old mask, and leave other projects' processes untouched.
Do not interpret that brief sample as a fixed overall speedup.

Verify observed values by their statistical type as well as missingness masks
and support. R's `identical()` can reject an integer vector and an exactly equal
double vector. For a binary numeric variable, explicitly compare numeric values
after checking the binary domain and unchanged observation mask; do not relax
numeric tolerances or recode factors to hide discrepancies. In the SD scope,
verification-only replay passed all 40 original imputations, with hashes of both
block checkpoints, the combined MIDS and all exported DAT files unchanged.
No sampling or Mplus fit was needed to repair this verifier error.

Keep complete-imputation acceptance separate from subsequent model acceptance.
Passing FCS checks does not prove MAR or exact compatibility with latent
interaction models. Completed observed-baseline H4.1 families do not establish
the four original dynamic moderation families or full H4. Include dependencies
of the public verifier in its file allowlist; repair a missing package dependency
by rebuilding the package, not by refitting accepted models.
