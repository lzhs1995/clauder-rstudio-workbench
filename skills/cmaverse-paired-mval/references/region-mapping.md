# Region mapping: monolithic g_formula script -> per-mediator workers

A CMAverse `g_formula` script typically runs every mediator's M=0 and M=1 blocks
sequentially in one long file. To fan it out you must first inventory which line
ranges belong to which mediator, then build one worker per mediator that reuses
**only the M=0 region**.

## Case study: new4.7 (`552:3561`)

| mediator        | original M=0 region | original M=1 region |
|-----------------|--------------------:|--------------------:|
| `msat_c12_2`    | `555:770`           | `2061:2276`         |
| `msat_c12_3`    | `772:987`           | `2278:2493`         |
| `msat_c1_2`     | `989:1197`          | `2495:2703`         |
| `msat_c21_2`    | `1201:1416`         | `2706:2921`         |
| `msat_c21_3`    | `1418:1633`         | `2923:3138`         |
| `msat_c2_2`     | `1635:1843`         | `3140:3348`         |
| `msateco_c2_2`  | `1845:2054`         | `3350:3559`         |

Lines `146:360` set up data but do not affect the CMAverse models, so they are
not part of the per-worker model region. Lines `1:551` (library/setup) and the
shared data preparation are run once inside each worker before its model block.

## Conversion rules

1. **Do not modify the original script.** Treat it as read-only reference.
2. Each worker reuses the original **M=0 region only**.
3. Wrap `cmest()`/`boot()` so the single `mval=list(0)` call produces both M=0
   and M=1 inside the same bootstrap (see worker-contract.md).
4. Never re-execute the original M=1 region; doing so would draw an independent
   bootstrap sample and break the paired contrast.

## Re-inventory for a new script version (mandatory)

The region map above is **version-specific**. `new4.8.*` scripts are longer
(~4565-4645 lines) and may rename mediators or shift ranges. Before reusing this
skill on a new version:

1. Open the new script and locate each mediator's `cmest(...)` call.
2. Record the start/end line of each M=0 block in a fresh table like the one above.
3. Diff mediator names against the 4.7 set; add/remove workers accordingly.
4. Only then generate the fan-out contract.

A worker bound to stale 4.7 line ranges will silently run the wrong block on
4.8. The region inventory is a hard prerequisite, not an optimization.
