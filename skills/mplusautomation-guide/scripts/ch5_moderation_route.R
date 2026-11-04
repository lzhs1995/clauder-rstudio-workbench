# 静态调节的 R 拟合路线：显式配置 → glm + 聚类 HC0 → 简单斜率（含协方差项的 delta 法）→ 图。
# 依赖 scripts/ch5_mediation_moderation.R（效应编码、拟合、控制剔除规则）。不调用 Mplus。
CH5_MOD_SPEC_KEYS <- c('outcome', 'focal', 'moderator', 'moderator_type', 'controls', 'family', 'cluster',
                       'probes', 'level_order', 'drop_rules')

ch5_or <- function(a, b) if (is.null(a)) b else a

# 校验配置：未知键、缺列、角色重叠、非显式取值点、效应编码类别不全都报错
ch5_moderation_spec <- function(spec, data) {
  bad <- setdiff(names(spec), CH5_MOD_SPEC_KEYS)
  if (length(bad)) stop('Unknown spec fields: ', paste(bad, collapse = ', '))
  need <- c('outcome', 'focal', 'moderator', 'moderator_type', 'family', 'cluster')
  miss <- need[!need %in% names(spec)]
  if (length(miss)) stop('Missing spec fields: ', paste(miss, collapse = ', '))
  if (!spec$family %in% c('gaussian', 'binomial')) stop('family must be gaussian or binomial')
  if (!spec$moderator_type %in% c('continuous', 'categorical')) stop('moderator_type must be continuous or categorical')
  spec$controls <- ch5_controls_for_outcome(ch5_or(spec$controls, character()), spec$outcome, ch5_or(spec$drop_rules, list()))
  roles <- c(spec$outcome, spec$focal, spec$moderator, spec$cluster)
  if (anyDuplicated(roles) || any(spec$controls %in% roles)) stop('Overlapping variable roles')
  cols <- c(roles, spec$controls)
  if (!all(cols %in% names(data))) stop('Columns not in data: ', paste(setdiff(cols, names(data)), collapse = ', '))
  if (spec$moderator_type == 'continuous') {
    if (!is.numeric(spec$probes) || length(spec$probes) < 2) stop('Continuous moderator needs explicit numeric probes')
  } else {
    lv <- spec$level_order
    if (is.null(lv) || length(lv) < 2) stop('Categorical moderator needs level_order')
    if (!all(stats::na.omit(unique(data[[spec$moderator]])) %in% lv)) stop('Data has moderator levels outside level_order')
  }
  spec
}

# 拟合：分类调节变量先效应编码，交互项由 R 公式构造
ch5_fit_moderation_spec <- function(spec, data) {
  spec <- ch5_moderation_spec(spec, data)
  d <- data
  if (spec$moderator_type == 'categorical') {
    ec <- ch5_effect_code(d[[spec$moderator]], spec$level_order, prefix = 'modw')
    d <- cbind(d, ec)
    wterms <- names(ec)
  } else wterms <- spec$moderator
  rhs <- c(spec$focal, wterms, paste0(spec$focal, ':', wterms), spec$controls)
  f <- stats::reformulate(rhs, response = spec$outcome)
  fam <- if (spec$family == 'binomial') stats::binomial() else stats::gaussian()
  m <- ch5_fit_moderation(f, d, family = fam, cluster = spec$cluster)
  m$spec <- spec; m$wterms <- wterms; m$formula <- f
  m
}

# 简单斜率：slope = b_focal + Σ g_k b_int_k，Var = g' V g（g 含协方差项）
ch5_simple_slopes <- function(m, level = 0.90) {
  spec <- m$spec; b <- stats::coef(m$fit); V <- m$vcov
  ints <- paste0(spec$focal, ':', m$wterms)
  if (spec$moderator_type == 'continuous') {
    G <- cbind(1, spec$probes); lab <- format(spec$probes)
  } else {
    G <- cbind(1, stats::contr.sum(length(spec$level_order))); lab <- as.character(spec$level_order)
  }
  idx <- c(spec$focal, ints)
  est <- as.numeric(G %*% b[idx])
  se <- sqrt(rowSums((G %*% V[idx, idx]) * G))
  z <- est / se; q <- stats::qnorm(1 - (1 - level) / 2)
  out <- data.frame(moderator_value = lab, estimate = est, se = se, z = z, p = 2 * stats::pnorm(-abs(z)),
                    lower = est - q * se, upper = est + q * se, stringsAsFactors = FALSE)
  if (spec$family == 'binomial') {
    out$odds_ratio <- exp(est); out$or_lower <- exp(out$lower); out$or_upper <- exp(out$upper)
  }
  out
}

# 简单斜率图（base graphics，pdf/png/svg 由扩展名决定）；返回实际绘制的数据
ch5_plot_simple_slopes <- function(slopes, file, xlab = 'moderator', ylab = 'simple slope') {
  dev <- switch(tolower(tools::file_ext(file)), pdf = grDevices::pdf, png = grDevices::png,
                svg = grDevices::svg, stop('Unsupported plot format'))
  if (identical(dev, grDevices::png)) dev(file, width = 1500, height = 1200, res = 300) else dev(file, width = 5, height = 4)
  on.exit(grDevices::dev.off())
  x <- seq_len(nrow(slopes))
  graphics::plot(x, slopes$estimate, ylim = range(c(slopes$lower, slopes$upper, 0)), xaxt = 'n', pch = 19,
                 xlab = xlab, ylab = ylab)
  graphics::axis(1, at = x, labels = slopes$moderator_value)
  graphics::arrows(x, slopes$lower, x, slopes$upper, angle = 90, code = 3, length = .05)
  graphics::abline(h = 0, lty = 2)
  invisible(slopes[, c('moderator_value', 'estimate', 'lower', 'upper')])
}
