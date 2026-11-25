# CHARLS son × education full MI: runner recovery and independent readback

This reference records the 2026-10-22 Windows run of a CHARLS H4.2 family using
the `son` within-family contrast and baseline education (`C3`) in the latent
`SX XWITH IZ` model.

## Contract and result

- Isolated root example: `<research-root>/<task-dir>` (substitute the local research root).
- N=2263, communities=`见本机证据 <r1d-charls-son-community-count>`, education counts `见本机证据 <r1d-charls-son-education-frequencies>`.
- Twenty A working-MI members plus one MI01 B start sensitivity; one Mplus
  process at a time; 21 real engine calls.
- Every A member and MI01 B had usable normal termination. Independent
  verification reconstructed 2,814 parameters, 21 contrasts, the full
  covariance transform and Rubin pooling.
- Keep the primary `SY:SXIZ` education-group estimate, interval, raw p-value
  and planned-family adjustment in the local study evidence, under the logical
  name `CHARLS_SON_EDU_FULL_MI_PRIMARY_CONTRAST`. Bind that name to the exact
  pooling receipt and source hashes in the study manifest.
- Keep `original_CFPS_four_complete=false` and `full_H4_complete=false`.
  This is one completed CHARLS family, not complete four-family moderation or
  complete H4.

## The runner failure that must be preserved

The first family attempt created MI01 A/B directories for a static compile
check. `run_family.R` unconditionally recompiles each member, so the existing
directory caused `FileExistsError` before Mplus started. The attempt is recorded
as `STOPPED_BEFORE_MPLUS` with zero engine calls. Move precompiled directories
to an audit-only location or use a separate staging root before a real run;
never delete or rewrite the failed receipt and never classify it as a model
failure.

## Correct retry sequence

1. Generate a new guard/task key and verify the native Windows contract uses
   `C:/...` paths, the correct indicator (`son`), N=2263 and community count
   `见本机证据 <r1d-charls-son-community-count>`.
2. Start from empty member directories. Register the original native
   `execute_r_async(source(..., local=TRUE))` job id immediately.
3. If ClaudeR still displays `started`, inspect `runtime/PROGRESS.jsonl`,
   per-member `engine_receipt.json`, `receipt.json` and worker identity before
   acting. A stale display does not establish an idle worker. In this case the
   entrypoint omitted `local=TRUE`; later urban submissions retained the async
   environment and exposed advancing native `stage/message/updated_at`.
   Durable files permit safe recovery; they do not excuse leaving future jobs
   without native progress.
4. Keep one Mplus slot on a 16-GiB Windows host unless a fresh measured
   resource contract authorizes more. On this run the serialized family was
   stable and completed in about 2,096 seconds of engine time.
5. After all 20 A members are usable, pool them and run the MI01 B check.
   Then run the final independent verifier, which requires all 21 outputs.
   B is a sensitivity call, never a 21st imputation or a replacement for A.

## Corrected reporting details

The original son terminal counted all calls as `A_members=21`; actual membership
is 20 A plus one B. Use the frozen `primary_sequence` and member-source table.
The three education families also inherited `dfcom=见本机证据 <r1d-sd-complete-data-df>` from the larger SD
sample. Their actual community counts imply `见本机证据 <r1d-gender-communities-minus-one>` (gender), `见本机证据 <r1d-oldest-communities-minus-one>` (oldest), and
`见本机证据 <r1d-son-communities-minus-one>` (son) under this project's communities-minus-one sensitivity convention.
This convention is not an exact finite-sample robust-cluster correction.

Recompute only derived finite-df sensitivity tables from the saved parameter
vectors and covariance matrices, verify actual cluster counts independently,
and retain main Rubin results unchanged. The 2026-10-22 correction required
zero Mplus calls and zero new MI. A verifier sharing a copied constant can
confirm arithmetic while missing a sample-definition error.

## MI auxiliary-file gate

The MI preparation can be valid while the public independent verifier still
fails if `AUXILIARY_INPUTS.csv` is absent. Export it from the admitted MI
object before verification. This export is a readback/audit operation: it does
not sample, rerun imputation or call Mplus. Record the export receipt and keep
the original MI contract and hashes unchanged.

## Publication and scientific boundary

Public packages may include sanitized contracts, input/output text, parameter
and covariance matrices, audit receipts and independent verification code.
Exclude `data.dat`, MI_INPUTS/RDS/MIDS, `AUXILIARY_INPUTS.csv`, individual
scores and participant records in **every directory, including failure-audit
backups**. An early local staging copy contained two archived `data.dat`
files; they were removed from staging and the ZIP was rebuilt before any
push. Use an explicit per-file allowlist, inspect archive members and verify
hashes; file size or CSV row count does not establish privacy. A package can support transparent readback
without permitting a new Mplus run. The scientific receipt must continue to
state: **四项调节完整推断、完整 H4 仍未完成。**
