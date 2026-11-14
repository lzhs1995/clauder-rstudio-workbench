# 第五章静态调节 R 路线合成合同：配置校验、拟合、简单斜率与绘图入口。不读研究文件、不调用 Mplus。
# 独立运行：Rscript test_ch5_moderation_route_20261105.R <新的证据目录>
# 历史协方差增量可复用已拟合的合成对象；参考采用逐项标量公式，不调用新拟合。
test_ch5_historical_covariance <- function(continuous_model, categorical_model, slopes, check, reject, prefix) {
  ck <- function(name, ok) check(paste0(prefix, '_', name), ok)
  no <- function(name, expr) reject(paste0(prefix, '_', name), expr)
  hc <- slopes(continuous_model, .90, covariance = 'historical_ch5')
  ordinary <- slopes(continuous_model, .90, covariance = 'model')
  robust <- slopes(continuous_model, .90, covariance = 'cluster_HC0')
  Vn <- stats::vcov(continuous_model$fit); Vr <- continuous_model$vcov
  w <- continuous_model$spec$probes
  expected <- unlist(lapply(continuous_model$spec$focal, function(x) {
    int <- paste0(x, ':', continuous_model$wterms)
    sqrt(Vr[x, x] + w^2 * Vr[int, int] + 2 * w * Vn[x, int])
  }), use.names = FALSE)
  ck('continuous_equals_historical_scalar_formula', max(abs(hc$se - expected)) < 1e-12)
  ck('continuous_distinguishes_both_unmixed_options',
     max(abs(hc$se - ordinary$se)) > 1e-6 && max(abs(hc$se - robust$se)) > 1e-6)
  ck('historical_changes_covariance_not_point_estimates',
     identical(hc$estimate, ordinary$estimate) && identical(hc$estimate, robust$estimate) &&
       all(hc$covariance == 'historical_ch5'))
  rounded_critical <- round(stats::qnorm(.95), digits = 3L)
  ck('historical_ci_keeps_explicit_normal_quantile',
     max(abs(hc$upper - hc$estimate - stats::qnorm(.95) * hc$se)) < 1e-12 &&
       max(abs(hc$lower - hc$estimate + stats::qnorm(.95) * hc$se)) < 1e-12 &&
       max(abs(hc$upper - hc$estimate - rounded_critical * hc$se)) > 1e-8)
  ck('default_still_exactly_cluster_HC0', identical(slopes(continuous_model, .90), robust))

  # 行列分别重排仍应按名称匹配；历史连续分支不能误读聚类交叉协方差。
  permuted <- continuous_model
  permuted$vcov <- Vr[rev(rownames(Vr)), c(tail(colnames(Vr), -1L), colnames(Vr)[1]), drop = FALSE]
  ck('cluster_variances_aligned_by_parameter_name',
     identical(slopes(permuted, .90, covariance = 'historical_ch5'), hc))
  no_cross <- continuous_model
  no_cross$vcov[row(no_cross$vcov) != col(no_cross$vcov)] <- NA_real_
  ck('continuous_ignores_cluster_cross_covariances',
     identical(slopes(no_cross, .90, covariance = 'historical_ch5'), hc))
  diagonal_only <- unlist(lapply(continuous_model$spec$focal, function(x) {
    int <- paste0(x, ':', continuous_model$wterms)
    sqrt(Vr[x, x] + w^2 * Vr[int, int])
  }), use.names = FALSE)
  ck('ordinary_cross_covariance_is_not_dropped', max(abs(hc$se - diagonal_only)) > 1e-6)

  broken <- continuous_model; broken$vcov <- NULL
  no('missing_cluster_matrix_rejected', slopes(broken, .90, covariance = 'historical_ch5'))
  ck('pure_model_still_ignores_missing_cluster_matrix',
     identical(slopes(broken, .90, covariance = 'model'), ordinary))
  x <- continuous_model$spec$focal[1]
  broken <- continuous_model; broken$vcov[x, x] <- NA_real_
  no('nonfinite_cluster_variance_rejected', slopes(broken, .90, covariance = 'historical_ch5'))
  broken <- continuous_model; broken$vcov <- Vr[rownames(Vr) != x, , drop = FALSE]
  no('missing_named_cluster_variance_rejected', slopes(broken, .90, covariance = 'historical_ch5'))
  broken <- continuous_model; broken$vcov[x, x] <- -1
  no('negative_cluster_variance_rejected', slopes(broken, .90, covariance = 'historical_ch5'))
  broken <- continuous_model; diag(broken$vcov) <- 0
  broken$spec$probes <- c(-1, 1); broken$spec$moderator_labels <- NULL
  no('negative_mixed_slope_variance_not_clamped', slopes(broken, .90, covariance = 'historical_ch5'))

  # 分类历史口径完全等于普通口径，且不应要求无关的聚类矩阵。
  cat_history <- slopes(categorical_model, .90, covariance = 'historical_ch5')
  cat_normal <- slopes(categorical_model, .90, covariance = 'model')
  keep <- setdiff(names(cat_history), 'covariance')
  ck('categorical_equals_complete_model_covariance',
     identical(cat_history[, keep, drop = FALSE], cat_normal[, keep, drop = FALSE]) &&
       all(cat_history$covariance == 'historical_ch5'))
  missing_cat_cluster <- categorical_model; missing_cat_cluster$vcov <- NULL
  ck('categorical_historical_does_not_need_cluster_matrix',
     identical(slopes(missing_cat_cluster, .90, covariance = 'historical_ch5'), cat_history))
  labelled <- categorical_model
  labels <- setNames(c('甲组', '乙组', '参照组'), as.character(labelled$spec$level_order))
  labelled$spec$moderator_labels <- labels
  labelled_slopes <- slopes(labelled, .90, covariance = 'historical_ch5')
  ck('historical_preserves_focal_codes_and_explicit_labels',
     identical(labelled_slopes$focal, cat_history$focal) &&
       identical(labelled_slopes$moderator_code, cat_history$moderator_code) &&
       identical(labelled_slopes$moderator_level, unname(labels[labelled_slopes$moderator_value])) &&
       identical(labelled_slopes$se, cat_history$se))
  if (continuous_model$spec$family == 'binomial')
    ck('historical_logit_or_uses_unchanged_ci_rule',
       identical(hc$odds_ratio, exp(hc$estimate)) && identical(hc$or_lower, exp(hc$lower)) &&
         identical(hc$or_upper, exp(hc$upper)))
  invisible(TRUE)
}

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

  # 6. 多焦点：手写完整交叉公式作参考，不用生成器自比。
  multi <- modifyList(cat_spec, list(focal = c('mc', 'ma', 'mb')))
  mm <- ch5_fit_moderation_spec(multi, d)
  dd <- cbind(d, ch5_effect_code(d$wcat, c(1, 3, 2), prefix = 'modw'))
  hand <- ch5_fit_moderation(ycc ~ mc + ma + mb + modw_effect1 + modw_effect2 +
    mc:modw_effect1 + mc:modw_effect2 + ma:modw_effect1 + ma:modw_effect2 +
    mb:modw_effect1 + mb:modw_effect2 + xc + c1 + c2, dd, cluster = 'cl')
  terms <- attr(stats::terms(mm$fit), 'term.labels')
  want <- c('mc:modw_effect1', 'mc:modw_effect2', 'ma:modw_effect1',
            'ma:modw_effect2', 'mb:modw_effect1', 'mb:modw_effect2')
  check('multifocal_three_categories_has_six_interactions',
        setequal(terms[grepl(':', terms, fixed = TRUE)], want))
  check('multifocal_equals_handwritten_full_cross',
        max(abs(coef(mm$fit) - coef(hand$fit)[names(coef(mm$fit))])) < 1e-12)
  sm <- ch5_simple_slopes(mm, level = .95)
  check('multifocal_slopes_order_and_rows', nrow(sm) == 9L &&
        identical(sm$focal, rep(multi$focal, each = 3L)))
  recoded <- vapply(multi$level_order, function(k) {
    z <- d; z$wf <- stats::relevel(factor(z$wcat), ref = as.character(k))
    fit <- ch5_fit_moderation(ycc ~ (mc + ma + mb) * wf + xc + c1 + c2, z, cluster = 'cl')
    got <- sm[sm$moderator_value == as.character(k), ]
    max(abs(got$estimate - coef(fit$fit)[multi$focal])) < 1e-10 &&
      max(abs(got$se - sqrt(diag(fit$vcov)[multi$focal]))) < 1e-10
  }, logical(1))
  check('multifocal_categorical_slopes_equal_releveled_fits', all(recoded))
  cont <- modifyList(base, list(focal = c('ma', 'mb', 'xc')))
  cm <- ch5_fit_moderation_spec(cont, d); cs <- ch5_simple_slopes(cm, level = .95)
  recentered <- vapply(cont$probes, function(w) {
    z <- d; z$w <- z$w - w
    fit <- ch5_fit_moderation(yc ~ (ma + mb + xc) * w + xa + c1 + c2, z, cluster = 'cl')
    got <- cs[as.numeric(cs$moderator_value) == w, ]
    max(abs(got$estimate - coef(fit$fit)[cont$focal])) < 1e-10 &&
      max(abs(got$se - sqrt(diag(fit$vcov)[cont$focal]))) < 1e-10
  }, logical(1))
  check('multifocal_continuous_slopes_equal_recentered_fits', nrow(cs) == 9L && all(recentered))
  for (bad_focal in list(character(), c('ma', 'ma'), c('ma', NA_character_), c('ma', '')))
    reject(paste0('invalid_focal_', length(checks)),
           ch5_moderation_spec(modifyList(base, list(focal = bad_focal)), d))

  # 7. 原生联合规格等于上游预乘写法；对齐设计矩阵、系数和完整协方差。
  px <- dd
  pairs <- list(c('mc', 'modw_effect1'), c('mc', 'modw_effect2'), c('ma', 'modw_effect1'),
                c('ma', 'modw_effect2'), c('mb', 'modw_effect1'), c('mb', 'modw_effect2'))
  for (j in seq_along(pairs)) px[[paste0('prod', j)]] <- px[[pairs[[j]][1]]] * px[[pairs[[j]][2]]]
  pm <- ch5_fit_moderation(ycc ~ mc + ma + mb + modw_effect1 + modw_effect2 +
    prod1 + prod2 + prod3 + prod4 + prod5 + prod6 + xc + c1 + c2, px, cluster = 'cl')
  map <- setNames(names(coef(mm$fit)), names(coef(mm$fit)))
  map[want] <- paste0('prod', 1:6)
  check('joint_native_design_matches_precomputed_products',
        max(abs(model.matrix(mm$fit) - model.matrix(pm$fit)[, unname(map), drop = FALSE])) == 0)
  check('joint_native_coefficients_and_covariance_match_products',
        max(abs(coef(mm$fit) - coef(pm$fit)[unname(map)])) < 1e-10 &&
        max(abs(mm$vcov - pm$vcov[unname(map), unname(map)])) < 1e-10)

  # 8. 协方差选择显式且不回退；普通口径用重参数化后主效应的普通 SE 验证。
  check('default_covariance_remains_cluster_HC0',
        identical(ch5_simple_slopes(m, .95), ch5_simple_slopes(m, .95, covariance = 'cluster_HC0')))
  ns <- ch5_simple_slopes(mm, .95, covariance = 'model')
  normal_ok <- vapply(multi$level_order, function(k) {
    z <- d; z$wf <- stats::relevel(factor(z$wcat), ref = as.character(k))
    fit <- stats::glm(ycc ~ (mc + ma + mb) * wf + xc + c1 + c2, z, family = gaussian())
    got <- ns[ns$moderator_value == as.character(k), ]
    max(abs(got$se - sqrt(diag(stats::vcov(fit))[multi$focal]))) < 1e-10
  }, logical(1))
  check('model_covariance_equals_ordinary_releveled_fits', all(normal_ok))
  check('covariance_choice_changes_se_not_estimate', identical(ns$estimate, sm$estimate) &&
        max(abs(ns$se - sm$se)) > 1e-4 && all(ns$covariance == 'model'))
  reject('unknown_covariance_rejected', ch5_simple_slopes(m, .95, covariance = 'fallback'))
  broken <- m; broken$vcov <- NULL
  reject('missing_cluster_covariance_does_not_fall_back', ch5_simple_slopes(broken, .95))
  check('explicit_model_covariance_does_not_need_cluster_matrix',
        all(is.finite(ch5_simple_slopes(broken, .95, covariance = 'model')$se)))
  test_ch5_historical_covariance(cm, mm, ch5_simple_slopes, check, reject, 'historical_gaussian')
  bin_cont <- ch5_fit_moderation_spec(modifyList(cont, list(outcome = 'ya', family = 'binomial')), d)
  bin_cat <- ch5_fit_moderation_spec(modifyList(multi, list(outcome = 'ya', family = 'binomial')), d)
  test_ch5_historical_covariance(bin_cont, bin_cat, ch5_simple_slopes, check, reject, 'historical_binomial')

  # 9. 全部效应码可导出；标签按显式键匹配，包含中文且不依赖映射顺序。
  check('categorical_code_contains_all_contrast_columns',
        identical(sm$moderator_code, rep(c('1,0', '0,1', '-1,-1'), 3L)))
  check('labels_absent_without_mapping', !'moderator_level' %in% names(sm))
  labelled <- modifyList(multi, list(moderator_labels = c('2' = '参照组', '1' = '甲组', '3' = '乙组')))
  ls <- ch5_simple_slopes(ch5_fit_moderation_spec(labelled, d), .95)
  check('explicit_chinese_labels_follow_value_keys',
        identical(ls$moderator_level, rep(c('甲组', '乙组', '参照组'), 3L)) && identical(ls$estimate, sm$estimate))
  labelled_cont <- modifyList(base, list(moderator_labels = c('1' = '高', '-1' = '低', '0' = '中')))
  check('explicit_continuous_labels', identical(ch5_simple_slopes(
    ch5_fit_moderation_spec(labelled_cont, d), .95)$moderator_level, c('低', '中', '高')))
  reject('incomplete_label_mapping_rejected', ch5_moderation_spec(
    modifyList(multi, list(moderator_labels = c('1' = '甲组'))), d))
  reject('unnamed_labels_rejected', ch5_moderation_spec(
    modifyList(multi, list(moderator_labels = c('甲', '乙', '丙'))), d))
  utils::write.csv(ls, file.path(output_dir, 'multifocal_slopes.csv'), row.names = FALSE)
  back <- utils::read.csv(file.path(output_dir, 'multifocal_slopes.csv'), stringsAsFactors = FALSE)
  check('display_columns_roundtrip_csv', identical(back$moderator_code, ls$moderator_code) &&
        identical(back$moderator_level, ls$moderator_level) && identical(back$focal, ls$focal))
  plot_multi <- ch5_plot_simple_slopes(ls, file.path(output_dir, 'multifocal.pdf'))
  check('multifocal_plot_preserves_identity_and_labels',
        identical(plot_multi$focal, ls$focal) && identical(plot_multi$moderator_level, ls$moderator_level))
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
