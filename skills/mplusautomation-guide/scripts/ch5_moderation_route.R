# 静态调节的 R 拟合路线：显式配置 → glm + 聚类 HC0 → 简单斜率（含协方差项的 delta 法）→ 图。
# 依赖 scripts/ch5_mediation_moderation.R（效应编码、拟合、控制剔除规则）。不调用 Mplus。
CH5_MOD_SPEC_KEYS <- c('outcome', 'focal', 'moderator', 'moderator_type', 'controls', 'family', 'cluster',
                       'probes', 'level_order', 'drop_rules', 'moderator_labels')

ch5_or <- function(a, b) if (is.null(a)) b else a

# 校验配置：未知键、缺列、角色重叠、非显式取值点、效应编码类别不全都报错
ch5_moderation_spec <- function(spec, data) {
  bad <- setdiff(names(spec), CH5_MOD_SPEC_KEYS)
  if (length(bad)) stop('Unknown spec fields: ', paste(bad, collapse = ', '))
  need <- c('outcome', 'focal', 'moderator', 'moderator_type', 'family', 'cluster')
  miss <- need[!need %in% names(spec)]
  if (length(miss)) stop('Missing spec fields: ', paste(miss, collapse = ', '))
  if (!is.character(spec$focal) || !length(spec$focal) || anyNA(spec$focal) ||
      any(!nzchar(spec$focal)) || anyDuplicated(spec$focal))
    stop('focal must be a nonempty vector of unique column names')
  if (!spec$family %in% c('gaussian', 'binomial')) stop('family must be gaussian or binomial')
  if (!spec$moderator_type %in% c('continuous', 'categorical')) stop('moderator_type must be continuous or categorical')
  spec$controls <- ch5_controls_for_outcome(ch5_or(spec$controls, character()), spec$outcome, ch5_or(spec$drop_rules, list()))
  roles <- c(spec$outcome, spec$focal, spec$moderator, spec$cluster)
  if (anyDuplicated(roles) || any(spec$controls %in% roles)) stop('Overlapping variable roles')
  cols <- c(roles, spec$controls)
  if (!all(cols %in% names(data))) stop('Columns not in data: ', paste(setdiff(cols, names(data)), collapse = ', '))
  if (spec$moderator_type == 'continuous') {
    if (!is.numeric(spec$probes) || length(spec$probes) < 2 || any(!is.finite(spec$probes)))
      stop('Continuous moderator needs explicit finite numeric probes')
  } else {
    lv <- spec$level_order
    if (is.null(lv) || length(lv) < 2 || anyNA(lv) || anyDuplicated(lv))
      stop('Categorical moderator needs unique nonmissing level_order')
    if (!all(stats::na.omit(unique(data[[spec$moderator]])) %in% lv)) stop('Data has moderator levels outside level_order')
    # cbind 不会消除同名旧列；公式会取到旧值，因此在拟合前明确拒绝碰撞。
    internal <- paste0('modw_effect', seq_len(length(lv) - 1L))
    collision <- intersect(internal, names(data))
    if (length(collision)) stop('Internal effect-code names already in data: ', paste(collision, collapse = ', '))
  }
  # 显示文本只取调用方的完整命名映射；不从类别顺序猜测社会含义。
  if (!is.null(spec$moderator_labels)) {
    labels <- spec$moderator_labels
    keys <- as.character(if (spec$moderator_type == 'continuous') spec$probes else spec$level_order)
    if (!is.character(labels) || is.null(names(labels)) || anyNA(labels) ||
        anyNA(names(labels)) || any(!nzchar(names(labels))) || anyDuplicated(names(labels)) ||
        !setequal(names(labels), unique(keys)))
      stop('moderator_labels must map each explicit moderator value to a label')
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
  # 完整交叉，避免 paste0 的循环补齐静默丢掉多个焦点与效应码的配对。
  interactions <- unlist(lapply(spec$focal, function(focal) paste0(focal, ':', wterms)), use.names = FALSE)
  rhs <- c(spec$focal, wterms, interactions, spec$controls)
  f <- stats::reformulate(rhs, response = spec$outcome)
  fam <- if (spec$family == 'binomial') stats::binomial() else stats::gaussian()
  m <- ch5_fit_moderation(f, d, family = fam, cluster = spec$cluster)
  m$spec <- spec; m$wterms <- wterms; m$formula <- f
  m
}

# 简单斜率：slope = b_focal + Σ g_k b_int_k，Var = g' V g（g 含协方差项）
# level 必须显式给出（第五章同时用 0.95 与 0.90 两档，不设默认值）
ch5_simple_slopes <- function(m, level, covariance = c('cluster_HC0', 'model', 'historical_ch5')) {
  if (missing(level)) stop('level must be given explicitly, e.g. 0.95')
  if (!is.numeric(level) || length(level) != 1L || !is.finite(level) || level <= 0 || level >= 1) stop('level must be a single number in (0, 1)')
  covariance <- match.arg(covariance)
  spec <- m$spec; b <- stats::coef(m$fit)
  # 默认保留拟合时的聚类 HC0；普通模型协方差只通过显式选项启用，不作回退。
  V <- if (covariance == 'cluster_HC0') m$vcov else stats::vcov(m$fit)
  if (spec$moderator_type == 'continuous') {
    G <- cbind(1, spec$probes); lab <- format(spec$probes)
  } else {
    G <- cbind(1, stats::contr.sum(length(spec$level_order))); lab <- as.character(spec$level_order)
  }
  q <- stats::qnorm(1 - (1 - level) / 2)
  out <- do.call(rbind, lapply(spec$focal, function(focal) {
    idx <- c(focal, paste0(focal, ':', m$wterms))
    if (!all(idx %in% names(b)) || any(!is.finite(b[idx])) || !is.matrix(V) ||
        !all(idx %in% rownames(V)) || !all(idx %in% colnames(V)) ||
        any(!is.finite(V[idx, idx, drop = FALSE])))
      stop('Slope coefficients or selected covariance unavailable for focal: ', focal)
    selected_vcov <- V[idx, idx, drop = FALSE]
    if (covariance == 'historical_ch5' && spec$moderator_type == 'continuous') {
      # 历史连续 SE 混用聚类方差与普通交叉协方差；仅显式复现，不更改默认推断或 CI。
      cluster_vcov <- m$vcov
      if (!is.matrix(cluster_vcov) || !all(idx %in% rownames(cluster_vcov)) ||
          !all(idx %in% colnames(cluster_vcov)))
        stop('Historical continuous slopes require cluster variances for focal: ', focal)
      cluster_variances <- diag(cluster_vcov[idx, idx, drop = FALSE])
      if (any(!is.finite(cluster_variances)) || any(cluster_variances < 0))
        stop('Historical continuous slopes require finite nonnegative cluster variances for focal: ', focal)
      diag(selected_vcov) <- cluster_variances
    }
    est <- as.numeric(G %*% b[idx])
    variance <- rowSums((G %*% selected_vcov) * G)
    if (any(variance < 0)) stop('Negative slope variance for focal: ', focal)
    se <- sqrt(variance)
    z <- est / se
    ans <- data.frame(moderator_value = lab, estimate = est, se = se, z = z,
                      p = 2 * stats::pnorm(-abs(z)), level = level,
                      lower = est - q * se, upper = est + q * se,
                      focal = focal, covariance = covariance, stringsAsFactors = FALSE)
    if (spec$moderator_type == 'categorical') {
      # CSV 可直接保存的完整效应码向量，顺序与 m$wterms 一致，不能只保留第一列。
      ans$moderator_code <- apply(G[, -1L, drop = FALSE], 1L, paste, collapse = ',')
    }
    if (!is.null(spec$moderator_labels)) {
      keys <- as.character(if (spec$moderator_type == 'continuous') spec$probes else spec$level_order)
      ans$moderator_level <- unname(spec$moderator_labels[keys])
    }
    if (spec$family == 'binomial') {
      ans$odds_ratio <- exp(est); ans$or_lower <- exp(ans$lower); ans$or_upper <- exp(ans$upper)
    }
    ans
  }))
  rownames(out) <- NULL
  out
}

# 简单斜率图（base graphics，pdf/png/svg 由扩展名决定）；y 轴标签写明置信水平；返回实际绘制的数据
ch5_plot_simple_slopes <- function(slopes, file, xlab = 'moderator', ylab = 'simple slope') {
  lv <- unique(slopes$level)
  if (length(lv) != 1L || !is.finite(lv)) stop('slopes must carry one confidence level in column level')
  ci_label <- paste0(format(100 * lv, trim = TRUE), '% CI')
  ylab <- paste0(ylab, ' (', ci_label, ')')
  labels <- if ('moderator_level' %in% names(slopes)) slopes$moderator_level else slopes$moderator_value
  if ('focal' %in% names(slopes) && length(unique(slopes$focal)) > 1L)
    labels <- paste(slopes$focal, labels, sep = ': ')
  dev <- switch(tolower(tools::file_ext(file)), pdf = grDevices::pdf, png = grDevices::png,
                svg = grDevices::svg, stop('Unsupported plot format'))
  # 标准 PDF 设备的单字节字体会丢掉中文；中文 PDF 使用支持 UTF-8 的 Cairo。
  if (identical(dev, grDevices::pdf) && any(grepl('[^ -~]', c(labels, xlab, ylab)))) {
    if (!capabilities('cairo')) stop('Non-ASCII PDF labels require Cairo support; use another supported device')
    dev <- grDevices::cairo_pdf
  }
  if (identical(dev, grDevices::png)) dev(file, width = 1500, height = 1200, res = 300) else dev(file, width = 5, height = 4)
  on.exit(grDevices::dev.off())
  x <- seq_len(nrow(slopes))
  graphics::plot(x, slopes$estimate, ylim = range(c(slopes$lower, slopes$upper, 0)), xaxt = 'n', pch = 19,
                 xlab = xlab, ylab = ylab)
  graphics::axis(1, at = x, labels = labels)
  graphics::arrows(x, slopes$lower, x, slopes$upper, angle = 90, code = 3, length = .05)
  graphics::abline(h = 0, lty = 2)
  pd <- slopes[, c('moderator_value', 'estimate', 'lower', 'upper', 'level',
                  intersect(c('focal', 'covariance', 'moderator_code', 'moderator_level'), names(slopes)))]
  attr(pd, 'ylab') <- ylab
  invisible(pd)
}
