# 第五章（单层中介 / 静态调节 / 有调节中介）可复用小函数。只做计算与文本生成，不调用 Mplus。
# 规格说明见 references/mediation-moderation-workflow.md。

# 保存抽样的偏差校正区间（与 Mplus CINTERVAL(BCBOOTSTRAP) 同一定义；分位用 type=7）
ch5_bc_interval <- function(draws, point, probs = c(0.05, 0.95)) {
  draws <- draws[is.finite(draws)]
  z0 <- stats::qnorm(mean(draws < point))
  if (!is.finite(z0)) return(rep(NA_real_, length(probs)))
  as.numeric(stats::quantile(draws, stats::pnorm(2 * z0 + stats::qnorm(probs)), type = 7, names = FALSE))
}

# 保存抽样的百分位区间
ch5_pc_interval <- function(draws, probs = c(0.05, 0.95)) {
  as.numeric(stats::quantile(draws[is.finite(draws)], probs, type = 7, names = FALSE))
}

# 差值判据：95% 区间排除零 / 仅 90% 排除零 / 90% 含零（论文用 ✓ ◐ ✗ 显示）
ch5_ci_class <- function(l90, u90, l95, u95) {
  if (any(!is.finite(c(l90, u90, l95, u95)))) return(NA_character_)
  if (l95 > 0 || u95 < 0) return("EXCLUDES_95")
  if (l90 > 0 || u90 < 0) return("EXCLUDES_90_ONLY")
  "INCLUDES_ZERO_90"
}

# 交互项显著性标记：p<0.1 用 "+"（论文附录显示为 †），其余为星号
ch5_sig_mark <- function(p) {
  ifelse(!is.finite(p), NA_character_,
    ifelse(p < 0.001, "***", ifelse(p < 0.01, "**", ifelse(p < 0.05, "*", ifelse(p < 0.1, "+", "")))))
}

# 三分类调节变量的效应编码：按 level_order 排列后 contr.sum，最后一类为 (-1,-1)
ch5_effect_code <- function(x, level_order = c(1, 3, 2), prefix = "w") {
  f <- factor(x, levels = level_order)
  if (anyNA(f[!is.na(x)])) stop("Unexpected moderator level")
  cm <- stats::contr.sum(length(level_order))
  out <- cm[as.integer(f), , drop = FALSE]
  colnames(out) <- paste0(prefix, "_effect", seq_len(ncol(out)))
  out[is.na(x), ] <- NA
  as.data.frame(out)
}

# 静态调节：glm 加夫妻（家庭）聚类稳健协方差，HC0，与第五章 R 脚本口径一致
ch5_fit_moderation <- function(formula, data, family = stats::gaussian(), cluster) {
  for (pkg in c("sandwich", "lmtest")) if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
  fit <- stats::glm(formula, data = data, family = family)
  v <- sandwich::vcovCL(fit, cluster = data[[cluster]], type = "HC0")
  list(fit = fit, vcov = v, table = lmtest::coeftest(fit, vcov. = v), nobs = stats::nobs(fit))
}

# 按结果变量剔除控制变量的显式规则（例：某结果不进某组控制）。规则写在配置里，不在代码里猜
ch5_controls_for_outcome <- function(controls, outcome, drop_rules = list()) {
  drop <- drop_rules[[outcome]]
  if (!is.null(drop) && !all(drop %in% controls)) stop("Drop rule names unknown controls for ", outcome)
  setdiff(controls, drop)
}

# 二值 M、二值 Y 的反事实分解（与 assets/ch5/counterfactual_mediation_template.txt 的 MODEL CONSTRAINT 同式）
# a0/b0 是 Mplus 阈值（概率式中带负号），X 取 0 与 1
ch5_counterfactual_effects <- function(a0, a1, b0, b1, b2, b3) {
  inv <- function(z) 1 / (1 + exp(z))
  pm1 <- c(x0 = inv(a0), x1 = inv(a0 - a1))
  ey <- function(x, m) inv(b0 - b1 * x - b2 * m - b3 * x * m)
  e <- function(x, xm) ey(x, 0) * (1 - pm1[[xm]]) + ey(x, 1) * pm1[[xm]]
  y0m0 <- e(0, "x0"); y0m1 <- e(0, "x1"); y1m0 <- e(1, "x0"); y1m1 <- e(1, "x1")
  c(TNIE = y1m1 - y1m0, PNIE = y0m1 - y0m0, PNDE = y1m0 - y0m0, TNDE = y1m1 - y0m1, TE = y1m1 - y0m0)
}

# 模板里需要手填的常量：形如 [[name]] 的普通标签（排除 [[init]]、迭代器 [[x#i]] 与条件 [[i = 1]]/[[/i = 1]]）
ch5_template_constants <- function(txt) {
  tags <- unlist(regmatches(txt, gregexpr("\\[\\[[^]]+\\]\\]", txt)))
  tags <- unique(gsub("^\\[\\[|\\]\\]$", "", tags))
  tags[grepl("^[A-Za-z_][A-Za-z0-9_]*$", tags) & !tags %in% c("init")]
}

# 填模板里的手填常量与输出目录；values 必须覆盖模板里每个常量标签，填完不得残留
ch5_fill_template <- function(template, out_path, values, required = NULL) {
  txt <- readLines(template, warn = FALSE, encoding = "UTF-8")
  if (is.null(required)) required <- ch5_template_constants(txt)
  miss <- setdiff(required, names(values))
  if (length(miss)) stop("Missing template constants: ", paste(miss, collapse = ", "))
  for (k in names(values)) {
    v <- values[[k]]
    if (is.numeric(v) && !all(is.finite(v))) stop("Non-finite constant: ", k)
    txt <- gsub(paste0("[[", k, "]]"), format(v, digits = 15), txt, fixed = TRUE)
  }
  left <- required[vapply(required, function(k) any(grepl(paste0("[[", k, "]]"), txt, fixed = TRUE)), logical(1))]
  if (length(left)) stop("Unfilled template constants: ", paste(left, collapse = ", "))
  writeLines(txt, out_path, useBytes = TRUE)
  invisible(out_path)
}
