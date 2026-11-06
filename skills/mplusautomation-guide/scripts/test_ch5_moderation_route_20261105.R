# 第五章静态调节 R 路线合成合同：配置校验、拟合、简单斜率与绘图入口。不读研究文件、不调用 Mplus。
# 独立运行：Rscript test_ch5_moderation_route_20261105.R <新的证据目录>
test_ch5_moderation_route <- function(output_dir, skill_root) {
  for (pkg in c('sandwich', 'lmtest', 'jsonlite')) if (!requireNamespace(pkg, quietly = TRUE)) stop('Missing package: ', pkg)
  skill_root <- normalizePath(skill_root, winslash = '/')
  if (file.exists(output_dir)) stop('Fresh output directory required')
  dir.create(output_dir, recursive = TRUE)
  for (f in c('ch5_mediation_moderation.R', 'ch5_synthetic_data.R', 'ch5_moderation_route.R')) {
    source(file.path(skill_root, 'scripts', f), local = TRUE)
  }
  checks <- list()
  check <- function(name, ok) { if (!isTRUE(ok)) stop('Contract failed: ', name); checks[[name]] <<- TRUE }
  reject <- function(name, expr) check(name, inherits(tryCatch(force(expr), error = identity), 'error'))
  d <- ch5_synthetic_data(5105L, 400L)
  base <- list(outcome = 'yc', focal = 'ma', moderator = 'w', moderator_type = 'continuous', controls = c('xa', 'c1', 'c2'),
               family = 'gaussian', cluster = 'cl', probes = c(-1, 0, 1))

  # 1. 配置负例
  reject('unknown_field', ch5_moderation_spec(c(base, list(extra = 1)), d))
  reject('missing_column', ch5_moderation_spec(modifyList(base, list(controls = c('c1', 'zz'))), d))
  reject('role_overlap', ch5_moderation_spec(modifyList(base, list(controls = c('w', 'c1'))), d))
  reject('probes_required', ch5_moderation_spec(modifyList(base, list(probes = NULL)), d))
  reject('family_checked', ch5_moderation_spec(modifyList(base, list(family = 'poisson')), d))
  cat_spec <- modifyList(base, list(outcome = 'ycc', focal = 'mc', moderator = 'wcat', moderator_type = 'categorical',
                                    controls = c('xc', 'c1', 'c2'), probes = NULL, level_order = c(1, 3, 2)))
  reject('level_order_complete', ch5_moderation_spec(modifyList(cat_spec, list(level_order = c(1, 3))), d))
  # 未使用的旧编码列也可能遮蔽内部列，必须在配置阶段拒绝。
  for (k in 1:2) {
    collision <- d; collision[[paste0('modw_effect', k)]] <- sin(seq_len(nrow(d)))
    reject(paste0('internal_effect_name_collision_', k), ch5_moderation_spec(cat_spec, collision))
  }
  unrelated <- d; unrelated$unused_column <- sin(seq_len(nrow(d)))
  check('unrelated_column_still_allowed', identical(ch5_moderation_spec(cat_spec, unrelated), ch5_moderation_spec(cat_spec, d)))
  for (entry in c('Inf', 'NA', 'NaN')) {
    invalid <- list('Inf' = Inf, 'NA' = NA_real_, 'NaN' = NaN)[[entry]]
    reject(paste0('nonfinite_probe_', entry), ch5_moderation_spec(modifyList(base, list(probes = c(0, invalid))), d))
  }
  sp <- ch5_moderation_spec(modifyList(base, list(drop_rules = list(yc = 'c2'))), d)
  check('drop_rule_applied', identical(sp$controls, c('xa', 'c1')))

  # 2. 拟合等于手写公式；连续调节：简单斜率 SE 等于把 W 平移到取值点后重拟合的主效应 SE
  m <- ch5_fit_moderation_spec(base, d)
  ref <- ch5_fit_moderation(yc ~ ma + w + ma:w + xa + c1 + c2, d, cluster = 'cl')
  check('fit_equals_handwritten_formula', max(abs(coef(m$fit) - coef(ref$fit)[names(coef(m$fit))])) < 1e-12)
  # 形参不得带默认值；带默认值时 missing() 仍为 TRUE，单靠报错负例抓不到
  check('slopes_level_has_no_default', identical(formals(ch5_simple_slopes)$level, quote(expr = )))
  reject('slopes_level_required', ch5_simple_slopes(m))
  reject('slopes_level_range', ch5_simple_slopes(m, level = 95))
  s <- ch5_simple_slopes(m, level = 0.95)
  check('slopes_level_column', identical(unique(s$level), 0.95))
  s90 <- ch5_simple_slopes(m, level = 0.90)
  q95 <- qnorm(.975); q90 <- qnorm(.95)
  check('slopes_interval_matches_level', max(abs((s$upper - s$estimate) - q95 * s$se)) < 1e-12 &&
          max(abs((s90$upper - s90$estimate) - q90 * s90$se)) < 1e-12)
  shift_ok <- vapply(seq_along(base$probes), function(i) {
    dd <- d; dd$w <- dd$w - base$probes[i]
    r <- ch5_fit_moderation(yc ~ ma + w + ma:w + xa + c1 + c2, dd, cluster = 'cl')
    abs(coef(r$fit)[['ma']] - s$estimate[i]) < 1e-10 && abs(sqrt(r$vcov['ma', 'ma']) - s$se[i]) < 1e-10
  }, logical(1))
  check('continuous_slopes_equal_recentered_fits', all(shift_ok))
  # 有限且不等距的取值点应保持合法，并与逐点平移重拟合一致。
  uneven <- modifyList(base, list(probes = c(-.75, .2, 1.6)))
  uneven_slopes <- ch5_simple_slopes(ch5_fit_moderation_spec(uneven, d), level = .95)
  uneven_ok <- vapply(seq_along(uneven$probes), function(i) {
    dd <- d; dd$w <- dd$w - uneven$probes[i]
    r <- ch5_fit_moderation(yc ~ ma + w + ma:w + xa + c1 + c2, dd, cluster = 'cl')
    abs(coef(r$fit)[['ma']] - uneven_slopes$estimate[i]) < 1e-10 &&
      abs(sqrt(r$vcov['ma', 'ma']) - uneven_slopes$se[i]) < 1e-10
  }, logical(1))
  check('finite_uneven_probes_equal_recentered_fits', all(uneven_ok))
  V <- m$vcov; no_cov <- sqrt(V['ma', 'ma'] + base$probes[3]^2 * V['ma:w', 'ma:w'])
  check('covariance_term_matters', abs(no_cov - s$se[3]) > 1e-4)

  # 3. 三分类调节：第 k 类的简单斜率等于以 k 为参照类的处理编码重拟合的主效应
  mc_ <- ch5_fit_moderation_spec(cat_spec, d)
  sc <- ch5_simple_slopes(mc_, level = 0.90)
  cat_ok <- vapply(seq_along(cat_spec$level_order), function(k) {
    dd <- d; dd$wf <- stats::relevel(factor(dd$wcat), ref = as.character(cat_spec$level_order[k]))
    r <- ch5_fit_moderation(ycc ~ mc + wf + mc:wf + xc + c1 + c2, dd, cluster = 'cl')
    abs(coef(r$fit)[['mc']] - sc$estimate[k]) < 1e-10 && abs(sqrt(r$vcov['mc', 'mc']) - sc$se[k]) < 1e-10
  }, logical(1))
  check('categorical_slopes_equal_releveled_fits', all(cat_ok))
  check('categorical_slopes_recover_truth', max(abs(sc$estimate - c(.6, .4, .2))) < .12)

  # 4. logit：OR 列与 exp(斜率) 一致
  lb <- modifyList(base, list(outcome = 'ya', focal = 'xa', moderator = 'w', controls = c('c1', 'c2'), family = 'binomial'))
  sl <- ch5_simple_slopes(ch5_fit_moderation_spec(lb, d), level = 0.95)
  check('logit_or_columns', max(abs(sl$odds_ratio - exp(sl$estimate))) < 1e-12 && all(sl$or_lower < sl$or_upper))

  # 5. 绘图入口：文件非空，返回的绘制数据等于斜率表
  for (ext in c('pdf', 'png')) {
    f <- file.path(output_dir, paste0('slopes.', ext))
    pd <- ch5_plot_simple_slopes(sc, f, xlab = 'W category')
    check(paste0('plot_', ext, '_written'), file.exists(f) && file.info(f)$size > 1000)
    check(paste0('plot_', ext, '_data_equals_table'), isTRUE(all.equal(pd$estimate, sc$estimate)))
    check(paste0('plot_', ext, '_ylab_states_level'), grepl('(90% CI)', attr(pd, 'ylab'), fixed = TRUE))
  }
  reject('plot_format_checked', ch5_plot_simple_slopes(sc, file.path(output_dir, 'x.gif')))
  reject('plot_requires_level_column', ch5_plot_simple_slopes(sc[, names(sc) != 'level'], file.path(output_dir, 'nolevel.pdf')))
  utils::write.csv(sc, file.path(output_dir, 'categorical_slopes.csv'), row.names = FALSE)
  jsonlite::write_json(list(test = 'test_ch5_moderation_route', status = 'PASS', checks = length(checks), engine_calls = 0L),
                       file.path(output_dir, 'receipt.json'), auto_unbox = TRUE, pretty = TRUE)
  invisible(checks)
}

if (sys.nframe() == 0L) {
  a <- commandArgs(trailingOnly = TRUE)
  if (length(a) != 1L) stop('Usage: Rscript test_ch5_moderation_route_20261105.R <fresh_output_dir>')
  me <- sub('^--file=', '', grep('^--file=', commandArgs(FALSE), value = TRUE)[1])
  res <- test_ch5_moderation_route(a[[1]], normalizePath(file.path(dirname(me), '..'), winslash = '/'))
  cat('CH5_MOD_ROUTE_PASS', length(res), 'checks\n')
}
