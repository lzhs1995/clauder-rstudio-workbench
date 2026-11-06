# 第五章扩展模板合成合同：连续线性乘积中介、三分类 W 有调节中介（效应编码取值与分样本子样本量）。
# 只生成 INP/DAT 并核约束代数，不读研究文件、不调用 Mplus。
# 独立运行：Rscript test_ch5_templates_extended_20261105.R <新的证据目录>
test_ch5_templates_extended <- function(output_dir, skill_root) {
  for (pkg in c('MplusAutomation', 'jsonlite')) if (!requireNamespace(pkg, quietly = TRUE)) stop('Missing package: ', pkg)
  skill_root <- normalizePath(skill_root, winslash = '/')
  if (file.exists(output_dir)) stop('Fresh output directory required')
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = '/')
  for (f in c('ch5_mediation_moderation.R', 'ch5_synthetic_data.R')) source(file.path(skill_root, 'scripts', f), local = TRUE)
  checks <- list()
  check <- function(name, ok) { if (!isTRUE(ok)) stop('Contract failed: ', name); checks[[name]] <<- TRUE }
  reject <- function(name, expr) check(name, inherits(tryCatch(force(expr), error = identity), 'error'))
  ns <- asNamespace('MplusAutomation')
  for (fun in c('runModels', 'detectMplus')) trace(fun, tracer = quote(stop('ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI')), print = FALSE, where = ns)
  on.exit(for (fun in c('runModels', 'detectMplus')) untrace(fun, where = ns), add = TRUE)
  reject('engine_guard_blocks_runModels', MplusAutomation::runModels())

  d <- ch5_synthetic_data(5105L, 400L)
  gen <- file.path(output_dir, 'generated'); dir.create(gen)
  MplusAutomation::prepareMplusData(d, file.path(gen, 'ch5_synthetic.dat'), inpfile = FALSE)
  tpl_lin <- file.path(skill_root, 'assets/ch5/linear_mediation_template.txt')
  tpl_cat <- file.path(skill_root, 'assets/ch5/moderated_mediation_cat_template.txt')
  # 每个样本各自的三类子样本量；样本筛选与模板的 USEOBSERVATIONS 一致
  samp <- list(tt = d, g0 = d[d$grp == 0, ], g1 = d[d$grp == 1, ])
  cnt <- list()
  for (s in names(samp)) for (k in 1:3) cnt[[sprintf('n_w%d_%s', k, s)]] <- sum(samp[[s]]$wcat == k)
  reject('cat_fill_requires_every_count', ch5_fill_template(tpl_cat, file.path(output_dir, 'x.txt'),
                                                             c(list(outdir = gen), cnt[-1])))
  f_lin <- ch5_fill_template(tpl_lin, file.path(output_dir, 'lin_filled.txt'), list(outdir = gen))
  f_cat <- ch5_fill_template(tpl_cat, file.path(output_dir, 'cat_filled.txt'), c(list(outdir = gen), cnt))
  MplusAutomation::createModels(f_lin); MplusAutomation::createModels(f_cat)
  inps <- list.files(gen, pattern = '\\.inp$', full.names = TRUE)
  check('lin_expansion_count', sum(grepl('^lin_', basename(inps))) == 12L)
  check('cat_expansion_count', sum(grepl('^modmed_cat_', basename(inps))) == 6L)
  # 三分类效应编码行：类别顺序 1,3,2 → (1,0)、(0,1)、(-1,-1)
  rows <- ch5_effect_code(c(1, 3, 2), c(1, 3, 2))
  probe_want <- list(ind_W1 = unlist(rows[1, ]), ind_W3 = unlist(rows[2, ]), ind_W2 = unlist(rows[3, ]))
  for (f in inps) {
    x <- readLines(f, warn = FALSE); id <- basename(f); all <- paste(x, collapse = '\n')
    s <- sub('.*_(tt|g0|g1)\\.inp$', '\\1', id)
    check(paste0(id, ':no_unresolved_tags'), !any(grepl('[[', x, fixed = TRUE)))
    check(paste0(id, ':line_width_le_90'), all(nchar(x, type = 'bytes') <= 90L))
    check(paste0(id, ':bootstrap_1000_bc'), grepl('bootstrap = 1000;', all, fixed = TRUE) && grepl('CINTERVAL(BCBOOTSTRAP)', all, fixed = TRUE))
    nm <- strsplit(trimws(sub(';.*', '', sub('.*NAMES = ', '', grep('^NAMES =', x, value = TRUE)))), ' +')[[1]]
    check(paste0(id, ':names_match_dat_columns'), identical(nm, CH5_SYNTHETIC_COLUMNS))
    uv <- strsplit(trimws(sub(';.*', '', sub('.*USEVARIABLES = ', '', grep('^USEVARIABLES =', x, value = TRUE)))), ' +')[[1]]
    defined <- sub(' *=.*', '', grep('^[a-z0-9]+ = .*\\*', x, value = TRUE))
    check(paste0(id, ':usevariables_declared_or_defined'), all(uv %in% c(nm, defined)))
    uo <- grep('^USEOBSERVATIONS', x, value = TRUE)
    check(paste0(id, ':sample_filter'), switch(s, tt = length(uo) == 0L, g0 = identical(uo, 'USEOBSERVATIONS = grp EQ 0;'),
                                               g1 = identical(uo, 'USEOBSERVATIONS = grp EQ 1;')))
    if (grepl('^modmed_cat_', id)) {
      got <- as.numeric(sub('.*= *([0-9]+);.*', '\\1', grep('^n[123] =', x, value = TRUE)))
      check(paste0(id, ':subsample_sizes_equal_this_sample'),
            identical(got, as.numeric(vapply(1:3, function(k) sum(samp[[s]]$wcat == k), numeric(1)))))
      for (nmw in names(probe_want)) {
        ln <- grep(paste0('^', nmw, ' ='), x, value = TRUE)
        v <- as.numeric(regmatches(ln, gregexpr('\\(-?[0-9]+\\)', ln))[[1]] |> gsub(pattern = '[()]', replacement = ''))
        check(paste0(id, ':', nmw, '_probe_row'), identical(v, unname(as.numeric(probe_want[[nmw]]))))
      }
    }
  }
  # 约束代数：给定 a1、b1、b12、b13，模板的条件间接效应与加权平均等于效应编码直接计算
  x <- readLines(inps[grepl('^modmed_cat_xc-mc-wcat-ycc_tt', basename(inps))], warn = FALSE)
  blk <- x[(grep('^MODEL CONSTRAINT:', x) + 1):(grep('^PLOT:', x) - 1)]
  blk <- trimws(sub('!.*$', '', blk)); blk <- blk[nzchar(blk) & !grepl('^NEW\\(', blk)]
  env <- list2env(list(a1 = .5, b1 = .4, b12 = .2, b13 = 0))
  for (s_ in blk) eval(parse(text = sub(';$', '', s_)), envir = env)
  want <- .5 * (.4 + as.matrix(rows) %*% c(.2, 0))
  check('cat_conditional_indirect_algebra', max(abs(c(env$ind_W1, env$ind_W3, env$ind_W2) - want)) < 1e-12)
  n <- vapply(1:3, function(k) sum(d$wcat == k), numeric(1))
  check('cat_weighted_average_algebra', abs(env$ind_avg - sum(n * c(env$ind_W1, env$ind_W2, env$ind_W3)) / sum(n)) < 1e-12)
  check('no_engine_outputs', length(list.files(output_dir, pattern = '\\.(out|gh5)$', recursive = TRUE)) == 0L)
  jsonlite::write_json(list(test = 'test_ch5_templates_extended', status = 'PASS', checks = length(checks),
                            generated_inp = length(inps), engine_calls = 0L),
                       file.path(output_dir, 'receipt.json'), auto_unbox = TRUE, pretty = TRUE)
  invisible(checks)
}

if (sys.nframe() == 0L) {
  a <- commandArgs(trailingOnly = TRUE)
  if (length(a) != 1L) stop('Usage: Rscript test_ch5_templates_extended_20261105.R <fresh_output_dir>')
  me <- sub('^--file=', '', grep('^--file=', commandArgs(FALSE), value = TRUE)[1])
  res <- test_ch5_templates_extended(a[[1]], normalizePath(file.path(dirname(me), '..'), winslash = '/'))
  cat('CH5_TEMPLATES_EXT_PASS', length(res), 'checks\n')
}
