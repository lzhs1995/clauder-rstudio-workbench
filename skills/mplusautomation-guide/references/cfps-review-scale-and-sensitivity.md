# CFPS review: measurement identity and targeted sensitivity

Use when a completed reproduction is followed by manuscript criticism. Preserve
the completed reproduction checkpoint, the user's selected primary scale, and
any explicitly paused dataset. A scientific adoption issue does not imply that
historical estimates need to be rerun.

## Score identity before modeling

- Establish the actual coding in the installed data, not just the theoretical
  instrument range. The reviewed CFPS official CESD20sc was 20–80: subtracting
  20 aligned it with a 0–60 score calculated from actual 2012 items. In 5,304
  complete 2016 long-form cases, the official score exactly matched the item
  total on the 20–80 scale. An initial assumption that the official field was
  already 0–60 was rejected and its exports retained as superseded diagnostics.
- Check score translations record by record, including missingness. The common
  eight-item sums on 1–4 and 0–3 coding differed by exactly eight when all items
  were valid. Equality of means alone would not establish this.
- Responses to the additional twelve items can support a provisional long/short
  form classification. They are not an official assignment flag and do not
  verify random assignment. Describe the inference and its sample explicitly.

## Pre-register a useful small comparison

Hold people constant across windows and scales, and label a complete-covariate
subset separately from the original MI population. A four-wave latent intercept
anchored in 2016 is not the same estimand as a five-wave 2012 intercept. With
free intermediate loadings, an endpoint of 0/10 does not make the change factor
a constant annual slope. Report the implied wave means as well.

The worked review used eight specifications: two windows × two scales × a
univariate and a direct-association family. The final disposition was three
inadmissible solutions, two nonconverged fits and three reviewable direct fits.
Reviewable fits still had mixed global fit indices. The CESD8 five-wave baseline
had a negative change-factor residual variance, so additional interactions were
not automatically appended. Do not select a scale/window by its p value.

## Input repair is distinct from scientific respecification

Mplus input lines are limited to 90 characters. `mplusModeler()` does not ensure
that every custom VARIABLE string respects this. Prefer explicit short lines
or validated variable ranges, and check actual generated inputs before launch.

Parameter labels require valid Mplus grammar. Write separate statements such as
`sy ON ix (bis);` and `sy ON sx (bss);`; do not put additional predictors after
the closing label in `sy ON ix (bis) sx (bss) iy;`. Preserve a rejected input and
output; repair the syntax in a new directory, verify identical data bytes, and
do not count the retry as a distinct scientific model.

Normalize whitespace when detecting raw diagnostic phrases: Mplus may split
`NOT POSITIVE` and `DEFINITE` across lines. A nonconverged parameter table may
have estimates but no SE or p-value columns. Record unavailable fields as NA;
do not compute inferential intervals or treat a missing diagnostic field as a
pass. Negative Est./SE with a positive SE can reveal a printed `0.000` variance
whose underlying sign is negative.

## Resource lessons specific to this run

The Windows profiler requires at least three samples. Validate its invocation
contract and preserve command stderr before interpreting an admission failure.
Its metrics are nested at `profile.system`; absent metrics must not silently
pass a gate. Sample before each new model, release the completed readback object,
and avoid copying the full R environment to workers.

Four direct fits took about 13–17 seconds each including execution and readback.
Very short univariate attempts fell between ten-second monitor samples; their
unobserved peak memory is unknown, not zero. Those times do not establish a
version-upgrade benefit or a universal concurrency budget. Keep a single slot
until measured pressure and actual model ownership justify more.

For audit delivery, allowlist complete input/output text, source scripts,
aggregate tables and documentation. Keep individual score files, analysis data,
MI RDS objects and ID mappings local. Make unresolved covariance, MI pairing,
failure-history and reference-code items explicit in the package.
