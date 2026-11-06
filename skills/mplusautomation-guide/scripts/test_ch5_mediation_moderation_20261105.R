# 第五章合成合同：只生成INP/DAT并检查计算函数，不读取研究文件、不调用Mplus。
# 独立运行：Rscript test_ch5_mediation_moderation_20261105.R <新的证据目录>
test_ch5_mediation_moderation <- function(output_dir, skill_root) {
  for (pkg in c('MplusAutomation', 'sandwich', 'lmtest', 'digest', 'jsonlite')) {
    if (!requireNamespace(pkg, quietly = TRUE)) stop('Missing package: ', pkg)
  }
  skill_root <- normalizePath(skill_root, winslash = '/')
  if (file.exists(output_dir)) stop('Fresh output directory required')
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = '/')
  source(file.path(skill_root, 'scripts/ch5_mediation_moderation.R'), local = TRUE)
  checks <- list()
  check <- function(name, ok) {
    if (!isTRUE(ok)) stop('Contract failed: ', name)
    checks[[name]] <<- TRUE
  }
  reject <- function(name, expr) check(name, inherits(tryCatch(force(expr), error = identity), 'error'))
  # 引擎守卫：生成阶段之后若误调 runModels/detectMplus，立即失败
  ns <- asNamespace('MplusAutomation')
  for (fun in c('runModels', 'detectMplus')) {
    trace(fun, tracer = quote(stop('ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI')), print = FALSE, where = ns)
  }
  on.exit(for (fun in c('runModels', 'detectMplus')) untrace(fun, where = ns), add = TRUE)
  reject('engine_guard_blocks_runModels', MplusAutomation::runModels())

  # 合成数据：固定种子，不取自论文结果或个人记录（scripts/ch5_synthetic_data.R）
  source(file.path(skill_root, 'scripts/ch5_synthetic_data.R'), local = TRUE)
  G <- 400L; n <- 3L * G
  d <- ch5_synthetic_data(5105L, G)
  check('synthetic_shape', nrow(d) == 1200L && length(unique(d$cl)) == 400L)

  # 1. 区间函数：对称抽样 BC=百分位；偏移抽样与手算 z0 公式一致；全部同侧返回 NA
  dr <- c(-rev(seq(.01, 1, length.out = 500)), seq(.01, 1, length.out = 500))
  check('bc_equals_percentile_when_z0_zero', isTRUE(all.equal(ch5_bc_interval(dr, 0), ch5_pc_interval(dr))))
  dr2 <- qnorm(ppoints(999), mean = .2)
  z0 <- qnorm(mean(dr2 < 0)); want <- quantile(dr2, pnorm(2 * z0 + qnorm(c(.05, .95))), type = 7, names = FALSE)
  check('bc_matches_manual_formula', isTRUE(all.equal(ch5_bc_interval(dr2, 0), as.numeric(want))))
  check('bc_shifts_when_point_off_center', abs(ch5_bc_interval(dr2, 0)[1] - ch5_pc_interval(dr2)[1]) > 1e-3)
  check('bc_degenerate_is_na', all(is.na(ch5_bc_interval(rep(-1, 50), 0))))
  check('ci_class_three_levels', identical(c(ch5_ci_class(.1, .5, .05, .6), ch5_ci_class(.1, .5, -.1, .6),
                                             ch5_ci_class(-.1, .5, -.2, .6)),
                                           c('EXCLUDES_95', 'EXCLUDES_90_ONLY', 'INCLUDES_ZERO_90')))
  check('sig_mark_cutpoints', identical(ch5_sig_mark(c(.0005, .005, .03, .07, .2)), c('***', '**', '*', '+', '')))

  # 2. 效应编码：类别顺序 1,3,2 → (1,0)、(0,1)、(-1,-1)；未知类别报错
  e <- ch5_effect_code(c(1, 3, 2), c(1, 3, 2))
  check('effect_code_rows', identical(unname(as.matrix(e)), rbind(c(1, 0), c(0, 1), c(-1, -1))))
  reject('effect_code_unknown_level', ch5_effect_code(c(1, 4), c(1, 3, 2)))

  # 3. 静态调节：交互项可回收；HC0 聚类协方差等于手算夹心式（含 G/(G-1)）
  m <- ch5_fit_moderation(yc ~ xa + ma * w + c1 + c2, d, cluster = 'cl')
  check('interaction_recovered', abs(coef(m$fit)[['ma:w']] - .25) < .12)
  X <- model.matrix(m$fit); r <- residuals(m$fit, type = 'working') * weights(m$fit, 'working')
  S <- rowsum(X * r, d$cl); B <- solve(crossprod(X))
  manual <- B %*% crossprod(S) %*% B * G / (G - 1)
  check('vcovCL_matches_manual_sandwich', max(abs(m$vcov - manual)) < 1e-10)
  check('nobs_recorded', m$nobs == n)
  joint <- ch5_fit_moderation(yc ~ xa + ma * w + c1 + c2, d, cluster = 'cl')
  separ <- ch5_fit_moderation(yc ~ xa + ma * w + c2, d, cluster = 'cl')
  check('control_set_changes_estimates', abs(coef(joint$fit)[['w']] - coef(separ$fit)[['w']]) > .05)
  check('controls_drop_rule', identical(ch5_controls_for_outcome(c('c1', 'c2'), 'yb', list(yb = 'c1')), 'c2'))
  reject('controls_drop_rule_unknown', ch5_controls_for_outcome(c('c1'), 'yb', list(yb = 'c9')))
  # 4. 反事实分解：闭式结果对大样本模拟；分解恒等式；模板 MODEL CONSTRAINT 逐式求值与函数一致
  p <- c(a0 = .4, a1 = .9, b0 = .6, b1 = .5, b2 = 1.1, b3 = -.4)
  ef <- do.call(ch5_counterfactual_effects, as.list(p))
  N <- 400000L
  m0 <- rbinom(N, 1, plogis(-p[['a0']])); m1 <- rbinom(N, 1, plogis(p[['a1']] - p[['a0']]))
  ey1 <- function(mm) plogis(-p[['b0']] + p[['b1']] + (p[['b2']] + p[['b3']]) * mm)
  check('tnie_matches_simulation', abs(ef[['TNIE']] - (mean(ey1(m1)) - mean(ey1(m0)))) < .005)
  check('decomposition_identities', abs(ef[['TE']] - ef[['PNDE']] - ef[['TNIE']]) < 1e-12 &&
          abs(ef[['TE']] - ef[['TNDE']] - ef[['PNIE']]) < 1e-12)
  check('no_mediator_path_no_indirect', abs(ch5_counterfactual_effects(.4, 0, .6, .5, 1.1, -.4)[['TNIE']]) < 1e-12)
  tpl_cf <- file.path(skill_root, 'assets/ch5/counterfactual_mediation_template.txt')
  tpl_mm <- file.path(skill_root, 'assets/ch5/moderated_mediation_mg_template.txt')
  txt <- readLines(tpl_cf, warn = FALSE)
  blk <- txt[(grep('^MODEL CONSTRAINT:', txt) + 1):(grep('^PLOT:', txt) - 1)]
  blk <- trimws(sub('!.*$', '', blk)); blk <- blk[nzchar(blk) & !grepl('^NEW\\(', blk)]
  env <- list2env(as.list(p))
  for (s in blk) eval(parse(text = gsub('EXP\\(', 'exp(', sub(';$', '', s))), envir = env)
  check('template_constraints_equal_function', max(abs(unlist(mget(names(ef), envir = env)) - ef)) < 1e-12)

  # 5. 模板生成：先填常量与输出目录，再 createModels；核文件数、必备语句、行宽、NAMES 与 DAT 列序
  gen <- file.path(output_dir, 'generated'); dir.create(gen)
  dat_cols <- CH5_SYNTHETIC_COLUMNS
  MplusAutomation::prepareMplusData(d[, dat_cols], file.path(gen, 'ch5_synthetic.dat'), inpfile = FALSE)
  wv <- c(w_mean = mean(d$w), w_sd = sd(d$w), w2_mean = mean(d$w2), w2_sd = sd(d$w2))
  reject('fill_requires_every_constant', ch5_fill_template(tpl_mm, file.path(output_dir, 'x.txt'),
                                                           c(list(outdir = gen), as.list(wv[-4]))))
  f_cf <- ch5_fill_template(tpl_cf, file.path(output_dir, 'cf_filled.txt'), list(outdir = gen))
  f_mm <- ch5_fill_template(tpl_mm, file.path(output_dir, 'mm_filled.txt'),
                            c(list(outdir = gen), as.list(wv)))
  MplusAutomation::createModels(f_cf); MplusAutomation::createModels(f_mm)
  inps <- list.files(gen, pattern = '\\.inp$', full.names = TRUE)
  check('cf_expansion_count', sum(grepl('^cf_', basename(inps))) == 16L)
  check('modmed_expansion_count', sum(grepl('^modmed_mg_', basename(inps))) == 8L)
  for (f in inps) {
    x <- readLines(f, warn = FALSE); id <- basename(f); all <- paste(x, collapse = '\n')
    check(paste0(id, ':no_unresolved_tags'), !any(grepl('[[', x, fixed = TRUE)))
    check(paste0(id, ':line_width_le_90'), all(nchar(x, type = 'bytes') <= 90L))
    check(paste0(id, ':bootstrap_1000_bc'), grepl('bootstrap = 1000;', all, fixed = TRUE) &&
            grepl('CINTERVAL(BCBOOTSTRAP)', all, fixed = TRUE))
    nm <- strsplit(trimws(sub(';.*', '', sub('.*NAMES = ', '', grep('^NAMES =', x, value = TRUE)))), ' +')[[1]]
    check(paste0(id, ':names_match_dat_columns'), identical(nm, dat_cols))
    uv <- strsplit(trimws(sub(';.*', '', sub('.*USEVARIABLES = ', '', grep('^USEVARIABLES =', x, value = TRUE)))), ' +')[[1]]
    defined <- sub(' *=.*', '', grep('^[a-z]+ = .*\\*', x, value = TRUE))
    check(paste0(id, ':usevariables_declared_or_defined'), all(uv %in% c(nm, defined)))
    is_cf <- grepl('^cf_', id)
    if (!is_cf) {
      # 每个调节变量的取值常量必须等于当前样本的均值/标准差（换源后不得沿用旧样本）
      wn <- sub('^modmed_mg_[^-]+-[^-]+-([^-]+)-yc\\.inp$', '\\1', id)
      got <- as.numeric(sub('.*= *([-0-9.eE]+);.*', '\\1', grep('^W_(m|sd) =', x, value = TRUE)))
      check(paste0(id, ':probe_constants_equal_current_sample'),
            length(got) == 2L && max(abs(got - c(mean(d[[wn]]), sd(d[[wn]])))) < 1e-12)
    }
    check(paste0(id, ':grouping_route'), if (is_cf) grepl('USEOBSERVATIONS = grp EQ', all) && !grepl('GROUPING', all)
          else grepl('GROUPING = grp', all) && !grepl('USEOBSERVATIONS', all))
  }
  check('no_engine_outputs', length(list.files(output_dir, pattern = '\\.(out|gh5)$', recursive = TRUE)) == 0L)

  receipt <- list(test = 'test_ch5_mediation_moderation', status = 'PASS', checks = length(checks),
                  generated_inp = length(inps), engine_calls = 0L,
                  inp_sha256 = setNames(lapply(inps, function(f) digest::digest(f, algo = 'sha256', file = TRUE)), basename(inps)),
                  r = R.version.string, mplusautomation = as.character(utils::packageVersion('MplusAutomation')))
  jsonlite::write_json(receipt, file.path(output_dir, 'receipt.json'), auto_unbox = TRUE, pretty = TRUE)
  invisible(checks)
}

if (sys.nframe() == 0L) {
  a <- commandArgs(trailingOnly = TRUE)
  if (length(a) != 1L) stop('Usage: Rscript test_ch5_mediation_moderation_20261105.R <fresh_output_dir>')
  me <- sub('^--file=', '', grep('^--file=', commandArgs(FALSE), value = TRUE)[1])
  res <- test_ch5_mediation_moderation(a[[1]], normalizePath(file.path(dirname(me), '..'), winslash = '/'))
  cat('CH5_SYNTHETIC_PASS', length(res), 'checks\n')
}
