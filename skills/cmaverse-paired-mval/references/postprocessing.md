# Post-processing the saved cmest objects

After all per-mediator workers save their nested RData, a separate post-process
stage turns them into effect-decomposition tables, gt exports, moderation plots,
and sensitivity analyses. In the case-study script this is the original region
`3611:5138`; the paired version reads the nested object instead of two
independent ones.

> The post-process script must **not** modify the original analysis script. It
> only reads the paired nested RData and writes new outputs under a fresh,
> versioned output directory.

## Re-read the paired object

Original (independent-bootstrap) code read two objects:

```r
res_cma_<mediator>_aincc_2_list      # original M=0 region
res_cma_<mediator>_aincc_2_1_list    # original M=1 region
```

The paired version reads a single nested object and still emits the two named
tables for compatibility:

```r
res_cma_<mediator>_aincc_2_1_list[[group]][["0"]]   # -> ..._aincc_2_table   (M=0)
res_cma_<mediator>_aincc_2_1_list[[group]][["1"]]   # -> ..._aincc_2_1_table (M=1)
```

## Effect-decomposition extraction

`extract_decomposition()` logic:

- point estimates from `summary(cma_result)$effect.pe` (17 CMAverse effects);
- p-values from `summary(cma_result)$effect.pval`;
- significance stars (`.`, `*`, `**`, `***`);
- interaction terms (containing `:`) from
  `summary(cma_result[["reg.output"]][["yreg"]])`, appended as `INTxm`;
- one column per group, merged wide on `Effect`.

**Set `model_order` to the groups actually estimated**, not the original full
set. A smoke run with only `sy_female,sy_male` must use:

```r
model_order <- c("sy_female", "sy_male")
```

Reusing the original 25-group `model_order` fails because the nested RData has no
other groups.

## gt export (Windows gotchas)

```r
gtsave(temp_table.t, filename = filename.doc)
gtsave(temp_table.t, filename = filename.png, expand = 30, vwidth = 1400, vheight = 900)
```

- Append a run tag (e.g. `sameboot_n100`) to every output filename so original
  files are never overwritten.
- Repeated `gtsave()` to the same docx on Windows can throw
  `pandoc document conversion failed with error 22`; delete the old docx/png
  before writing, exactly as the original script does.
- Pin Chrome to `C:/Program Files/Google/Chrome/Application/chrome.exe`.

## Moderation plots and sensitivity

Data structures are nested by group and mval:

```r
estimand[[group]][["0"]]; estimand[[group]][["1"]]
tab_univ[[group]][["0"]]; tab_univ[[group]][["1"]]
Evalues[[group]][["0"]];  Evalues[[group]][["1"]]
```

extracted via:

```r
summary(cma_result)$summarydf
cmsens(object = cma_result, sens = "uc")$evalues
```

`estimand` holds `Estimate / Std.error / 95% CIL / 95% CIU` and drives the
controlled-direct-effect (`Rcde`) and proportion-eliminated (`rpe`) plots. Build
the plot panel from the groups actually present (e.g. a 2-panel layout for
sy-only), not the original 8-row patchwork.

## Post-process deliverables

A formal post-process run produces, per run: a manifest CSV, a validation CSV, a
gt-errors CSV, a summary-objects RData, and execution logs; and per mediator a
set of `table_*`, `gt_*` (docx/png), `estimand_*`, `tab_univ_*`, `Evalues_*`, and
`plot_*` (CDE/rpe) files. Keep `gt_errors` empty as an explicit gate
(`gt_error_rows=0`).
