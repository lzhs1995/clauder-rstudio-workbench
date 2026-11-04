# 第五章原生合成验收：四个模板各取一个代表模型，在 Windows 获准窗口用 Mplus 跑合成数据后读回核对。
# run = FALSE 只准备运行包（DAT、INP、manifest），不调用 Mplus；run = TRUE 需要 Mplus 与计算窗口授权。
# 用法：Rscript test_ch5_native_synthetic_20261105.R <新的目录> [--run]
test_ch5_native_synthetic <- function(output_dir, skill_root, run = FALSE) {
  for (pkg in c('MplusAutomation', 'digest', 'jsonlite')) if (!requireNamespace(pkg, quietly = TRUE)) stop('Missing package: ', pkg)
  skill_root <- normalizePath(skill_root, winslash = '/')
  if (file.exists(output_dir)) stop('Fresh output directory required')
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = '/')
  for (f in c('ch5_mediation_moderation.R', 'ch5_synthetic_data.R')) source(file.path(skill_root, 'scripts', f), local = TRUE)
  d <- ch5_synthetic_data(5105L, 400L)
  MplusAutomation::prepareMplusData(d, file.path(output_dir, 'ch5_synthetic.dat'), inpfile = FALSE)
  samp <- list(tt = d, g0 = d[d$grp == 0, ], g1 = d[d$grp == 1, ])
  cnt <- list()
  for (s in names(samp)) for (k in 1:3) cnt[[sprintf('n_w%d_%s', k, s)]] <- sum(samp[[s]]$wcat == k)
  vals <- list(counterfactual_mediation_template.txt = list(),
               moderated_mediation_mg_template.txt = list(w_mean = mean(d$w), w_sd = sd(d$w), w2_mean = mean(d$w2), w2_sd = sd(d$w2)),
               linear_mediation_template.txt = list(), moderated_mediation_cat_template.txt = cnt)
  gen <- file.path(output_dir, 'all'); dir.create(gen)
  for (t in names(vals)) {
    f <- ch5_fill_template(file.path(skill_root, 'assets/ch5', t), file.path(output_dir, paste0('filled_', t)),
                           c(list(outdir = gen), vals[[t]]))
    MplusAutomation::createModels(f)
  }
  # 代表模型：每个模板一个
  pick <- c('cf_xa-ma-ya_g0.inp', 'modmed_mg_xa-ma-w-yc.inp', 'lin_xc-mc-ycc_tt.inp', 'modmed_cat_xc-mc-wcat-ycc_tt.inp')
  stopifnot(all(file.exists(file.path(gen, pick))))
  for (p in pick) file.copy(file.path(gen, p), file.path(output_dir, p))
  unlink(gen, recursive = TRUE)
  files <- c('ch5_synthetic.dat', pick)
  manifest <- list(test = 'test_ch5_native_synthetic', models = length(pick), bootstrap = 1000L,
                   sha256 = setNames(lapply(files, function(f) digest::digest(file.path(output_dir, f), algo = 'sha256', file = TRUE)), files))
  jsonlite::write_json(manifest, file.path(output_dir, 'manifest.json'), auto_unbox = TRUE, pretty = TRUE)
  if (!run) return(invisible(list(prepared = pick)))

  # 以下在 Windows 获准窗口运行：逐模型串行，读回后核对
  MplusAutomation::runModels(output_dir, filefilter = 'cf_|modmed_|lin_', replaceOutfile = 'never')
  checks <- list()
  check <- function(name, ok) { if (!isTRUE(ok)) stop('Contract failed: ', name); checks[[name]] <<- TRUE }
  for (p in pick) {
    o <- sub('\\.inp$', '.out', file.path(output_dir, p)); id <- basename(p)
    txt <- readLines(o, warn = FALSE)
    check(paste0(id, ':normal_termination'), any(grepl('THE MODEL ESTIMATION TERMINATED NORMALLY', txt)))
    check(paste0(id, ':no_se_failure'), !any(grepl('STANDARD ERRORS OF THE MODEL PARAMETER ESTIMATES COULD NOT BE', txt)))
    comp <- as.numeric(sub('.*Completed +', '', grep('^ +Completed +[0-9]+', txt, value = TRUE)[1]))
    check(paste0(id, ':bootstrap_completed_1000'), identical(comp, 1000))
    m <- MplusAutomation::readModels(o, what = 'parameters', quiet = TRUE)
    u <- m$parameters$unstandardized
    est <- function(name) as.numeric(u$est[toupper(u$param) == toupper(name) & u$paramHeader == 'New.Additional.Parameters'][1])
    lab <- function(h, pr) as.numeric(u$est[toupper(u$paramHeader) == toupper(h) & toupper(u$param) == toupper(pr)][1])
    if (startsWith(id, 'cf_')) {
      ef <- ch5_counterfactual_effects(lab('Thresholds', 'MA$1'), lab('MA.ON', 'XA'), lab('Thresholds', 'YA$1'),
                                       lab('YA.ON', 'XA'), lab('YA.ON', 'MA'), lab('YA.ON', 'INTEM'))
      check(paste0(id, ':tnie_equals_printed_parameters'), abs(ef[['TNIE']] - est('TNIE')) < 2e-3)
    } else if (startsWith(id, 'lin_')) {
      check(paste0(id, ':ind_equals_a_times_b'), abs(est('IND') - lab('MC.ON', 'XC') * lab('YCC.ON', 'MC')) < 2e-3)
    } else if (startsWith(id, 'modmed_cat_')) {
      n <- vapply(1:3, function(k) est(paste0('N', k)), numeric(1))
      w <- c(est('IND_W1'), est('IND_W2'), est('IND_W3'))
      check(paste0(id, ':weighted_average'), abs(est('IND_AVG') - sum(n * w) / sum(n)) < 2e-3)
    } else {
      check(paste0(id, ':dimm_equals_group_difference'), abs(est('DIMM') - (est('IMM0') - est('IMM1'))) < 2e-3)
    }
  }
  jsonlite::write_json(list(test = 'test_ch5_native_synthetic', status = 'PASS', checks = length(checks)),
                       file.path(output_dir, 'native_receipt.json'), auto_unbox = TRUE, pretty = TRUE)
  invisible(checks)
}

if (sys.nframe() == 0L) {
  a <- commandArgs(trailingOnly = TRUE)
  if (!length(a)) stop('Usage: Rscript test_ch5_native_synthetic_20261105.R <fresh_dir> [--run]')
  me <- sub('^--file=', '', grep('^--file=', commandArgs(FALSE), value = TRUE)[1])
  res <- test_ch5_native_synthetic(a[[1]], normalizePath(file.path(dirname(me), '..'), winslash = '/'), run = '--run' %in% a)
  cat('CH5_NATIVE_SYNTHETIC', if ('--run' %in% a) 'RUN_PASS' else 'PREPARED', length(res), '\n')
}
