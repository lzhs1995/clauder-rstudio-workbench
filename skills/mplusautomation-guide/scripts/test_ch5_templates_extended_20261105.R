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

  # ---- 换变量合同：name*/var* 两套列表、NAMES、DATA: FILE 与 DAT 列序一起改名、换序（四个模板） ----
  # 模拟用户按 references/mediation-moderation-workflow.md §3 第 1、5 条手改模板；守卫函数在 ch5_mediation_moderation.R
  reject_as <- function(name, expr, want) {
    e <- tryCatch({ force(expr); NULL }, ch5_swap_error = identity)
    got <- if (is.null(e)) character() else sort(e$reasons)
    if (!identical(got, sort(want))) stop('Contract failed: ', name, ' reasons [', paste(got, collapse = ' '),
                                          '] want [', paste(want, collapse = ' '), ']')
    checks[[name]] <<- TRUE
  }
  swap_dir <- file.path(output_dir, 'swap'); dir.create(swap_dir)
  tpls <- c(cf = 'counterfactual_mediation', lin = 'linear_mediation', cat = 'moderated_mediation_cat', mg = 'moderated_mediation_mg')
  tpls <- setNames(file.path(skill_root, 'assets/ch5', paste0(tpls, '_template.txt')), names(tpls))
  cols <- CH5_SYNTHETIC_COLUMNS
  ren <- setNames(sprintf('r%02d%s', seq_along(cols), substr(cols, 1, 5)), cols)  # 新名 ≤ 8 字符
  idm <- setNames(cols, cols); inv <- setNames(names(ren), unname(ren))
  # 只换整词标识符；[[...]] 标签与 ! 注释不动；file_mode 时 _ 也算词界（文件名字面量）
  swap_ids <- function(x, map, file_mode = FALSE) {
    wc <- if (file_mode) 'A-Za-z0-9' else 'A-Za-z0-9_'
    for (k in names(map)[order(-nchar(names(map)))])
      x <- gsub(sprintf('(?<![%s])%s(?![%s])', wc, k, wc), map[[k]], x, perl = TRUE)
    x
  }
  swap_line <- function(ln, map, file_mode = FALSE) {
    code <- sub('!.*$', '', ln); com <- substring(ln, nchar(code) + 1L)
    m <- gregexpr('\\[\\[[^]]*\\]\\]', code)
    keep <- regmatches(code, m)[[1]]; rest <- regmatches(code, m, invert = TRUE)[[1]]
    rest <- vapply(rest, swap_ids, '', map = map, file_mode = file_mode, USE.NAMES = FALSE)
    paste0(paste0(rest, c(keep, ''), collapse = ''), com)
  }
  # rename_name / rename_var 分别控制 name* 列表（及文件名字面量）与 var* 列表（及模型语句）；NAMES 写 names_order
  swap_template <- function(tpl, out, map, names_order, dat_name, rename_name = TRUE, rename_var = TRUE,
                            update_data_file = TRUE) {
    x <- readLines(tpl, warn = FALSE); a <- which(x == '[[init]]'); b <- which(x == '[[/init]]')
    for (i in seq_along(x)) {
      ln <- x[i]
      if (i > a && i < b) {
        if (grepl('^name[A-Za-z0-9_]*#', ln) && rename_name || grepl('^var[A-Za-z0-9_]*#', ln) && rename_var)
          x[i] <- paste0(sub('=.*$', '=', ln), swap_line(sub('^[^=]*=', '', ln), map))
        else if (grepl('^filename', ln) && rename_name) x[i] <- swap_line(ln, map, file_mode = TRUE)
      } else if (i > b) {
        if (grepl('^NAMES =', ln)) {
          g <- split(names_order, ceiling(seq_along(names_order) / 6))
          x[i] <- paste0('NAMES = ', paste(vapply(g, paste, '', collapse = ' '), collapse = '\n  '), ';')
        } else if (grepl('^DATA: FILE =', ln)) {
          if (update_data_file) x[i] <- sprintf('DATA: FILE = "%s";', dat_name)
        } else if (rename_var) x[i] <- swap_line(ln, map)
      }
    }
    writeLines(x, out); out
  }
  # 手填常量按本轮数据和映射重算（换源后不得沿用旧值）
  constants <- function(dd, map) {
    v <- list(w_mean = mean(dd[[map[['w']]]]), w_sd = sd(dd[[map[['w']]]]),
              w2_mean = mean(dd[[map[['w2']]]]), w2_sd = sd(dd[[map[['w2']]]]))
    for (s in c('tt', 'g0', 'g1')) {
      ss <- switch(s, tt = dd, g0 = dd[dd[[map[['grp']]]] == 0, ], g1 = dd[dd[[map[['grp']]]] == 1, ])
      for (k in 1:3) v[[sprintf('n_w%d_%s', k, s)]] <- sum(ss[[map[['wcat']]]] == k)
    }
    v
  }
  # 一轮：写 DAT（列序即 names(dd)）、改写并填模板、展开
  gen_round <- function(tag, dd, map, dat_name, only = names(tpls), rewrite = TRUE, ...) {
    g <- file.path(swap_dir, tag); dir.create(g)
    MplusAutomation::prepareMplusData(dd, file.path(g, dat_name), inpfile = FALSE)
    used <- character()
    for (t in only) {
      used[[t]] <- if (rewrite) swap_template(tpls[[t]], file.path(g, paste0(t, '_template.txt')), map, names(dd), dat_name, ...)
                   else tpls[[t]]
      MplusAutomation::createModels(ch5_fill_template(used[[t]], file.path(g, paste0(t, '_filled.txt')),
                                                      c(list(outdir = g), constants(dd, map))))
    }
    list(data = dd, dat = file.path(g, dat_name), templates = used, inps = list.files(g, pattern = '\\.inp$', full.names = TRUE))
  }
  d0 <- d
  d1 <- d[, rev(cols)]; names(d1) <- unname(ren[names(d1)])
  rounds <- list(original = gen_round('original', d0, idm, 'ch5_synthetic.dat', rewrite = FALSE),
                 renamed_reordered = gen_round('renamed_reordered', d1, ren, 'swap_source.dat'))
  lab <- list(original = NULL, renamed_reordered = setNames(unname(ren), unname(ren)))
  for (r in names(rounds)) {
    R <- rounds[[r]]
    for (t in names(R$templates))
      check(paste0('swap:', r, ':', t, ':name_var_pairs'), nrow(ch5_check_template_lists(R$templates[[t]], lab[[r]])) > 0L)
    check(paste0('swap:', r, ':expansion_count'), length(R$inps) == 42L)
    for (f in R$inps) { ch5_check_inp_columns(f, R$data, R$dat); check(paste0('swap:', r, ':', basename(f), ':columns_aligned'), TRUE) }
  }
  # 两轮语义相同：改名轮按逆映射还原后，除 NAMES 与 DATA: FILE 外逐句相同
  canon <- function(f, map) {
    st <- ch5_inp_statements(vapply(readLines(f, warn = FALSE), swap_line, '', map = map, USE.NAMES = FALSE))
    st <- Filter(function(s) !(s$section == 'VARIABLE' && grepl('^NAMES', s$text)) && !(s$section == 'DATA' && grepl('^FILE', s$text)), st)
    vapply(st, function(s) paste(s$section, s$text), '')
  }
  ro <- rounds$original$inps; rr <- rounds$renamed_reordered$inps
  rr_key <- setNames(rr, vapply(basename(rr), swap_ids, '', map = inv, file_mode = TRUE, USE.NAMES = FALSE))
  check('swap:filenames_map_back', identical(sort(names(rr_key)), sort(basename(ro))))
  for (f in ro) {
    g <- rr_key[[basename(f)]]; id <- basename(f)
    check(paste0('swap:', id, ':renamed_syntax_changed'), !identical(readLines(f, warn = FALSE), readLines(g, warn = FALSE)))
    check(paste0('swap:', id, ':canonical_semantics_equal'), identical(canon(f, character()), canon(g, inv)))
    n0 <- ch5_check_inp_columns(f, d0, rounds$original$dat)$names
    n1 <- unname(inv[ch5_check_inp_columns(g, d1, rounds$renamed_reordered$dat)$names])
    check(paste0('swap:', id, ':names_reordered_same_set'), !identical(n0, n1) && setequal(n0, n1))
  }
  # 负例：只改一侧，必须被拒绝且原因精确
  mutate_tpl <- function(tag, tpl, from, to) {
    x <- readLines(tpl, warn = FALSE); y <- sub(from, to, x, fixed = TRUE)
    check(paste0('swap_reject_', tag, ':mutation_applied'), !identical(x, y))
    out <- file.path(swap_dir, paste0('neg_', tag, '.txt')); writeLines(y, out); out
  }
  # 1 只改 var* 不改 name*：.inp 各自自洽（文件名标签过时），只有模板层能抓到
  t1 <- swap_template(tpls[['cf']], file.path(swap_dir, 'neg_var_only.txt'), ren, names(d1), 'swap_source.dat', rename_name = FALSE)
  reject_as('swap_reject_var_renamed_name_kept', ch5_check_template_lists(t1), 'NAME_VAR_MISMATCH')
  reject_as('swap_reject_var_renamed_name_kept_labels', ch5_check_template_lists(t1, lab$renamed_reordered), 'NAME_VAR_MISMATCH')
  n1 <- gen_round('neg_var_only', d1, ren, 'swap_source.dat', only = 'cf', rename_name = FALSE)
  reject_as('swap_neg_var_only_inp_layer_alone_passes', for (f in n1$inps) ch5_check_inp_columns(f, n1$data, n1$dat), character())
  # 1b 不改名、只把 var* 换序：文件名 ma 装的是 mb 的模型
  reject_as('swap_reject_var_reordered_name_kept',
            ch5_check_template_lists(mutate_tpl('var_reorder', tpls[['lin']], 'varmv#mv = mc ma;', 'varmv#mv = ma mc;')), 'NAME_VAR_MISMATCH')
  # 2 只改 name*（及文件名）不改 var* 和模型语句：NAMES 已是新名
  t2 <- swap_template(tpls[['cf']], file.path(swap_dir, 'neg_name_only.txt'), ren, names(d1), 'swap_source.dat', rename_var = FALSE)
  reject_as('swap_reject_name_renamed_var_kept', ch5_check_template_lists(t2, lab$renamed_reordered), 'VAR_NOT_IN_LABELS')
  n2 <- gen_round('neg_name_only', d1, ren, 'swap_source.dat', only = 'cf', rename_var = FALSE)
  check('swap_neg_name_only:expansion_count', length(n2$inps) == 16L)
  for (f in n2$inps) reject_as(paste0('swap_reject_name_renamed_var_kept:', basename(f)), ch5_check_inp_columns(f, n2$data, n2$dat),
                               c('DEFINE_NOT_IN_NAMES', 'USEOBSERVATIONS_NOT_IN_NAMES', 'USEVARIABLES_NOT_IN_NAMES'))
  # 3 NAMES 与 DAT 列序错位：DAT 按倒序写，模板 NAMES 未改
  lin0 <- ro[basename(ro) == 'lin_xc-mc-ycc_tt.inp']; check('swap_neg_fixture_unique', length(lin0) == 1L)
  fx <- file.path(swap_dir, 'neg_order'); dir.create(fx); file.copy(lin0, fx)
  dr <- d0[, rev(cols)]; MplusAutomation::prepareMplusData(dr, file.path(fx, 'ch5_synthetic.dat'), inpfile = FALSE)
  reject_as('swap_reject_names_dat_order', ch5_check_inp_columns(file.path(fx, basename(lin0)), dr, file.path(fx, 'ch5_synthetic.dat')),
            'NAMES_DAT_ORDER_MISMATCH')
  reject_as('swap_reject_dat_written_in_other_order', ch5_check_inp_columns(file.path(fx, basename(lin0)), d0, file.path(fx, 'ch5_synthetic.dat')),
            'DAT_CONTENT_MISMATCH')
  # 4 数据删了一列，NAMES 没跟着删
  fm <- file.path(swap_dir, 'neg_dropped'); dir.create(fm); file.copy(lin0, fm)
  dm <- d0[, setdiff(cols, 'yb')]; MplusAutomation::prepareMplusData(dm, file.path(fm, 'ch5_synthetic.dat'), inpfile = FALSE)
  reject_as('swap_reject_names_dat_set', ch5_check_inp_columns(file.path(fm, basename(lin0)), dm, file.path(fm, 'ch5_synthetic.dat')),
            c('DAT_FIELD_COUNT_MISMATCH', 'NAMES_DAT_SET_MISMATCH'))
  # 5 换了 DAT 文件名，模板 DATA: FILE 还是旧文本
  n5 <- gen_round('neg_stale_file', d1, ren, 'swap_source.dat', only = 'lin', update_data_file = FALSE)
  for (f in n5$inps) reject_as(paste0('swap_reject_stale_data_file:', basename(f)), ch5_check_inp_columns(f, n5$data, n5$dat), 'DATA_FILE_MISMATCH')
  # 6 手改 .inp 时把更长的新名写成一行：超过 90 字节的部分 Mplus 不读（createModels 生成时自己会折行，所以夹具直接改 .inp）
  lin1 <- unname(rr_key['lin_xc-mc-ycc_tt.inp']); f6 <- file.path(swap_dir, 'neg_long_line'); dir.create(f6)
  x6 <- readLines(lin1, warn = FALSE); i6 <- grep('^NAMES =', x6); j6 <- i6 + which(grepl(';', x6[i6:length(x6)]))[1] - 1L
  x6 <- c(x6[seq_len(i6 - 1L)], paste0('NAMES = ', paste(names(d1), collapse = ' '), ';'), x6[-seq_len(j6)])
  writeLines(x6, file.path(f6, basename(lin1))); file.copy(rounds$renamed_reordered$dat, f6)
  check('swap_neg_long_line_fixture_over_90', max(nchar(x6, type = 'bytes')) > 90L)
  reject_as('swap_reject_names_line_too_long', ch5_check_inp_columns(file.path(f6, basename(lin1)), d1, file.path(f6, 'swap_source.dat')),
            'LINE_TOO_LONG')
  # 7 两个变量配成同一个文件名标签：后一个模型覆盖前一个
  lab7 <- idm; lab7[['mb']] <- 'ma'
  reject_as('swap_reject_duplicate_label', ch5_check_template_lists(mutate_tpl('dup_label', tpls[['cf']], 'namemv#mv = ma mb;', 'namemv#mv = ma ma;'), lab7),
            'DUPLICATE_NAME_LABEL')
  # 8 name* 比 var* 多一个；9 没有成对列表时不得空过
  reject_as('swap_reject_name_var_length', ch5_check_template_lists(mutate_tpl('len', tpls[['lin']], 'nameiv#iv = xc xa;', 'nameiv#iv = xc xa xb;')),
            'NAME_VAR_LENGTH_MISMATCH')
  t9 <- mutate_tpl('no_pairs', mutate_tpl('no_pairs_a', tpls[['lin']], 'nameiv#iv', 'labeliv#iv'), 'namemv#mv', 'labelmv#mv')
  reject_as('swap_reject_no_pairs', ch5_check_template_lists(t9), 'NO_NAME_VAR_PAIRS')
  # 10 直接改 .inp 的 VARIABLE 语句：CATEGORICAL 列了不在 USEVARIABLES 的变量、GROUPING 变量不在 NAMES、NAMES 用 a-b 简写
  inp_neg <- function(tag, src, from, to, data, dat) {
    dd <- file.path(swap_dir, paste0('neg_', tag)); dir.create(dd)
    x <- readLines(src, warn = FALSE); y <- sub(from, to, x, fixed = TRUE)
    check(paste0('swap_reject_', tag, ':mutation_applied'), !identical(x, y))
    writeLines(y, file.path(dd, basename(src))); file.copy(dat, dd); file.path(dd, basename(src))
  }
  cf0 <- ro[basename(ro) == 'cf_xa-ma-ya_g0.inp']; mg0 <- ro[basename(ro) == 'modmed_mg_xa-ma-w-yc.inp']
  check('swap_neg_inp_fixtures_unique', length(cf0) == 1L && length(mg0) == 1L)
  reject_as('swap_reject_categorical_not_used', ch5_check_inp_columns(
    inp_neg('categorical', cf0, 'CATEGORICAL = ma ya;', 'CATEGORICAL = ma ya w;', d0, rounds$original$dat), d0,
    file.path(swap_dir, 'neg_categorical', 'ch5_synthetic.dat')), 'CATEGORICAL_NOT_IN_USEVARIABLES')
  reject_as('swap_reject_grouping_not_in_names', ch5_check_inp_columns(
    inp_neg('grouping', mg0, 'GROUPING = grp (', 'GROUPING = grq (', d0, rounds$original$dat), d0,
    file.path(swap_dir, 'neg_grouping', 'ch5_synthetic.dat')), 'GROUPING_NOT_IN_NAMES')
  rng <- inp_neg('range', lin0, 'NAMES = id cl grp xa xb ma mb ya yb w wc1 wc3 c1 c2 yc w2 xc mc wcat ycc;',
                 'NAMES = id-ycc;', d0, rounds$original$dat)
  reject_as('swap_reject_names_range_syntax', ch5_check_inp_columns(rng, d0, file.path(swap_dir, 'neg_range', 'ch5_synthetic.dat')),
            c('DAT_FIELD_COUNT_MISMATCH', 'NAMES_DAT_SET_MISMATCH', 'UNSUPPORTED_LIST_SYNTAX', 'USEVARIABLES_NOT_IN_NAMES'))
  # 11 核的是别处同名 DAT（内容相同）：Mplus 读的是 .inp 旁边那份，必须按路径判，不按文件名
  od <- file.path(swap_dir, 'neg_other_dir'); dir.create(od); file.copy(rounds$original$dat, od)
  reject_as('swap_reject_same_basename_other_dir', ch5_check_inp_columns(lin0, d0, file.path(od, 'ch5_synthetic.dat')), 'DATA_FILE_MISMATCH')
  # 12 Mplus 变量名不分大小写：数据列名大写、NAMES 小写仍算对齐
  du <- d0; names(du) <- toupper(names(du))
  reject_as('swap_columns_case_insensitive', ch5_check_inp_columns(lin0, du, rounds$original$dat), character())
  # 13 列数/列序与内容不变，只删 DAT 最后一行；仍用完整 data 比较，单独覆盖行数门。
  short_dir <- file.path(swap_dir, 'neg_one_row_short'); dir.create(short_dir); file.copy(lin0, short_dir)
  short_dat <- file.path(short_dir, 'ch5_synthetic.dat')
  dat_lines <- readLines(rounds$original$dat, warn = FALSE)
  writeLines(head(dat_lines, -1L), short_dat)
  short_shape <- utils::read.table(short_dat, header = FALSE, na.strings = '.', colClasses = 'numeric')
  check('swap_one_row_short_fixture', ncol(short_shape) == ncol(d0) && nrow(short_shape) == nrow(d0) - 1L)
  reject_as('swap_reject_dat_one_row_short',
            ch5_check_inp_columns(file.path(short_dir, basename(lin0)), d0, short_dat), 'DAT_ROW_COUNT_MISMATCH')
  # 14 条件 DEFINE：条件和 RHS 均按语句进入前的 NAMES/derived 核声明，不静默跳过未知语句。
  define_dir <- file.path(swap_dir, 'define_probes'); dir.create(define_dir)
  file.copy(rounds$original$dat, define_dir)
  define_dat <- file.path(define_dir, 'ch5_synthetic.dat')
  define_base <- readLines(cf0, warn = FALSE)
  check('swap_define_fixture_headers', sum(grepl('^DEFINE:', define_base)) == 1L &&
          sum(grepl('^USEVARIABLES =', define_base)) == 1L)
  probe_define <- function(tag, statements, use = character()) {
    x <- append(define_base, statements, after = grep('^DEFINE:', define_base))
    if (length(use)) {
      i <- grep('^USEVARIABLES =', x)
      x[i] <- sub(';', paste0(' ', paste(use, collapse = ' '), ';'), x[i], fixed = TRUE)
    }
    if (any(nchar(x, type = 'bytes') > 90L)) stop('DEFINE fixture exceeds line limit: ', tag)
    path <- file.path(define_dir, paste0(tag, '.inp')); writeLines(x, path)
    ch5_check_inp_columns(path, d0, define_dat)
  }
  got <- probe_define('conditional_target', 'IF (xa EQ 1) THEN flag = 1;', 'flag')
  check('swap_define_if_target_in_usevariables', 'flag' %in% got$defined && 'flag' %in% got$usevariables)
  got <- probe_define('nested_multiline_prior', c('base = xa;', 'iF ((base EQ 1) AND',
    ' (xb GT 0 OR NOT (ma EQ 1))) tHeN flag = base + log(abs(xb) + 1e-3);',
    'nextvar = flag + 1;'), c('flag', 'nextvar'))
  check('swap_define_nested_multiline_prior', all(c('base', 'flag', 'nextvar') %in% got$defined))
  got <- probe_define('missing_constant', 'IF (xa EQ _MISSING) THEN flag = _MISSING;', 'flag')
  check('swap_define_missing_constant', 'flag' %in% got$defined)
  got <- probe_define('declared_reassignment', c('flag = xa;', 'IF (flag GE 0) THEN flag = flag + 1;'), 'flag')
  check('swap_define_declared_reassignment', 'flag' %in% got$defined)
  got <- probe_define('function_named_variable', c('log = xa;', 'IF (log EQ 1) THEN flag = log;'), 'flag')
  check('swap_define_declared_function_named_variable', all(c('log', 'flag') %in% got$defined))
  missing_reference <- list(
    condition = 'IF (zzundecl EQ 1) THEN flag = 1;',
    rhs = 'IF (xa EQ 1) THEN flag = zzundecl;',
    condition_forward = c('IF (future EQ 1) THEN flag = 1;', 'future = xa;'),
    rhs_forward = c('IF (xa EQ 1) THEN flag = future;', 'future = xa;'),
    self_reference = 'IF (xa EQ 1) THEN flag = flag + 1;',
    bare_function_condition = 'IF (log EQ 1) THEN flag = 1;',
    bare_function_rhs = 'IF (xa EQ 1) THEN flag = mean;',
    unknown_function = 'IF (xa EQ 1) THEN flag = unknown(xa);'
  )
  # 每例只允许声明缺失这一个原因，避免其它门误杀。
  for (tag in names(missing_reference))
    reject_as(paste0('swap_reject_define_reference_', tag), probe_define(tag, missing_reference[[tag]]), 'DEFINE_NOT_IN_NAMES')
  unsupported <- list(
    no_close = 'IF (xa EQ 1 THEN flag = 1;',
    extra_close = 'IF (xa EQ 1)) THEN flag = 1;',
    empty_condition = 'IF ( ) THEN flag = 1;',
    empty_rhs = 'IF (xa EQ 1) THEN flag = ;',
    no_then = 'IF (xa EQ 1) flag = 1;',
    no_target = 'IF (xa EQ 1) THEN = 1;',
    no_equals = 'IF (xa EQ 1) THEN flag 1;',
    rhs_parentheses = 'IF (xa EQ 1) THEN flag = log(xa;',
    else_branch = 'IF (xa EQ 1) THEN flag = 1 ELSE flag = 0;',
    empty_assignment = 'flag = ;',
    center = 'CENTER xa (GRANDMEAN);',
    standardize = 'STANDARDIZE xa;',
    do_loop = 'DO #i = 1 TO 2;')
  for (tag in names(unsupported))
    reject_as(paste0('swap_reject_define_unsupported_', tag), probe_define(tag, unsupported[[tag]]), 'UNSUPPORTED_DEFINE_SYNTAX')
  check('no_engine_outputs', length(list.files(output_dir, pattern = '\\.(out|gh5)$', recursive = TRUE)) == 0L)
  jsonlite::write_json(list(test = 'test_ch5_templates_extended', status = 'PASS', checks = length(checks),
                            generated_inp = length(inps), engine_calls = 0L,
                            swap_rounds = lapply(rounds, function(R) length(R$inps)),
                            swap_reject_checks = sum(grepl('^swap_reject_', names(checks)) & !grepl(':mutation_applied$', names(checks)))),
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
