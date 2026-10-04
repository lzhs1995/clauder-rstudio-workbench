# CFPS/PP-LGCM 调节效应只读回读
# 只读既有参数 CSV；不调用 Mplus，不修改输入数据或历史输出。

run_cfps_moderation_readback <- function(csv_path, out_dir) {
  stopifnot(length(csv_path) == 1L, nzchar(csv_path), file.exists(csv_path))
  stopifnot(length(out_dir) == 1L, nzchar(out_dir))
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  required <- c("file", "model", "type", "moderator", "paramHeader", "param",
                "est", "se", "pval", "ci_low", "ci_high", "p_bh", "p_bonf")
  d <- read.csv(csv_path, stringsAsFactors = FALSE, check.names = FALSE)
  missing <- setdiff(required, names(d))
  if (length(missing) || !nrow(d)) stop("参数 CSV 缺少字段或为空")
  for (nm in c("est", "se", "pval", "ci_low", "ci_high", "p_bh", "p_bonf"))
    d[[nm]] <- as.numeric(d[[nm]])
  if (any(!is.finite(d$est)) || any(!is.finite(d$se)) || any(!is.finite(d$pval)))
    stop("estimate/SE/p-value 必须为有限数")

  # 保留历史文件内的校正，同时提供预先声明的全局敏感性口径。
  d$p_bh_recorded <- d$p_bh
  d$p_bonf_recorded <- d$p_bonf
  d$p_bh_global <- p.adjust(d$pval, method = "BH")
  d$p_bonf_global <- p.adjust(d$pval, method = "bonferroni")
  d$ci_cross_zero <- d$ci_low <= 0 & d$ci_high >= 0
  d$direction <- ifelse(d$est > 0, "positive", ifelse(d$est < 0, "negative", "zero"))
  d$family <- paste(d$type, d$moderator, sep = "_")

  fam <- do.call(rbind, lapply(split(d, d$family), function(x) {
    data.frame(
      family = unique(x$family), type = unique(x$type), moderator = unique(x$moderator),
      files = length(unique(x$file)), rows = nrow(x),
      nominal_p05 = sum(x$pval < .05),
      recorded_within_output_bh_p05 = sum(x$p_bh_recorded < .05),
      recorded_within_output_bonf_p05 = sum(x$p_bonf_recorded < .05),
      global_all_row_bh_p05 = sum(x$p_bh_global < .05),
      global_all_row_bonf_p05 = sum(x$p_bonf_global < .05),
      ci_excluding_zero = sum(!x$ci_cross_zero),
      positive = sum(x$direction == "positive"),
      negative = sum(x$direction == "negative"),
      median_abs_est = median(abs(x$est)), median_se = median(x$se),
      min_p = min(x$pval), stringsAsFactors = FALSE
    )
  }))
  fam <- fam[order(fam$type, fam$moderator), ]
  write.csv(fam, file.path(out_dir, "cfps_moderation_empirical_family.csv"), row.names = FALSE)
  write.csv(d[, c("file", "model", "type", "moderator", "paramHeader", "param",
                  "est", "se", "ci_low", "ci_high", "pval", "p_bh_recorded",
                  "p_bonf_recorded", "p_bh_global", "p_bonf_global",
                  "ci_cross_zero", "direction")],
            file.path(out_dir, "cfps_moderation_empirical_rows.csv"), row.names = FALSE)

  png(file.path(out_dir, "cfps_moderation_empirical.png"), width = 2000, height = 1300, res = 180)
  par(mfrow = c(2, 1), mar = c(8, 4, 3, 1) + .1)
  bar_mat <- t(as.matrix(fam[, c("nominal_p05", "recorded_within_output_bh_p05",
                                "global_all_row_bh_p05")]))
  colnames(bar_mat) <- fam$family
  barplot(bar_mat, beside = TRUE, las = 2,
          col = c("#999999", "#377EB8", "#984EA3"),
          ylab = "Number of interaction rows",
          main = "Moderation readback: prespecified multiplicity sensitivity")
  legend("topright", legend = c("nominal p<.05", "recorded within-output BH",
                                  "global all-row BH"),
         fill = c("#999999", "#377EB8", "#984EA3"), bty = "n", cex = .8)
  ord <- order(d$pval, decreasing = TRUE)
  plot(seq_len(nrow(d)), d$est[ord], pch = 19,
       col = ifelse(d$p_bh_recorded[ord] < .05, "#377EB8", "#777777"),
       xaxt = "n", xlab = "", ylab = "Interaction estimate",
       main = "Historical estimates with 95% intervals")
  segments(seq_len(nrow(d)), d$ci_low[ord], seq_len(nrow(d)), d$ci_high[ord], col = "#777777")
  abline(h = 0, lty = 2, col = "#CC0000")
  axis(1, at = seq_len(nrow(d)), labels = d$family[ord], las = 2, cex.axis = .45)
  dev.off()

  lines <- c(
    "# Moderation empirical readback",
    "",
    paste0("Rows=", nrow(d), "; files=", length(unique(d$file)),
           "; this is an existing-CSV-only audit; no Mplus was submitted."),
    paste0("Nominal p<.05=", sum(d$pval < .05),
           "; recorded within-output BH/Bonferroni=",
           sum(d$p_bh_recorded < .05), "/", sum(d$p_bonf_recorded < .05), "; global all-row=",
           sum(d$p_bh_global < .05), "/", sum(d$p_bonf_global < .05), "."),
    "Keep the two multiplicity families labelled. Neither replaces a same-model VCOV/joint-Wald contract.",
    "Do not select a specification, cut point, control set, or imputation member by p-value."
  )
  writeLines(lines, file.path(out_dir, "cfps_moderation_empirical_conclusion.md"), useBytes = TRUE)
  invisible(list(rows = nrow(d), files = length(unique(d$file)), families = nrow(fam), family = fam))
}
