# OTHER_GROWTH 合成合同：mplus_from_mapping() 与 growth_time_basis()/growth_model_syntax() 的
# 换名、换序、改值复用检查（reusable-models.md 末节），只生成 INP/DAT，不调用 Mplus。
# 独立运行：Rscript -e 'source("scripts/test_other_growth_compile_20261105.R"); test_other_growth_compile("<新目录>", ".")'
other_growth_synthetic <- function(seed = 2011L, n = 240L) {
  # 合成纵向数据：固定种子，不取自论文结果或个人记录；保存并恢复调用者的随机数状态
  old_seed <- if (exists(".Random.seed", envir = globalenv())) get(".Random.seed", envir = globalenv()) else NULL
  on.exit(if (is.null(old_seed)) rm(".Random.seed", envir = globalenv()) else
    assign(".Random.seed", old_seed, envir = globalenv()), add = TRUE)
  set.seed(seed)
  waves <- c(2011, 2013, 2015, 2018, 2020)
  time <- waves - waves[1L]
  level <- rnorm(n, 5, 1); slope <- rnorm(n, 0.3, 0.1)
  scores <- sapply(time, function(t) level + slope * t + rnorm(n, 0, 0.5))
  # 源列名故意用长名与非 ASCII 名，映射层必须照样处理
  data <- data.frame(row = seq_len(n), scores)
  names(data) <- c("row", "depression_score_wave2011", "depression_score_wave2013",
                   "抑郁_2015", "depression_score_wave2018", "depression_score_wave2020")
  data[c(3, 17, 40), 3] <- NA
  list(data = data, waves = waves,
       mapping = stats::setNames(names(data)[-1], c("y11", "y13", "y15", "y18", "y20")))
}

test_other_growth_compile <- function(output_dir, skill_root) {
  for (pkg in c("MplusAutomation", "digest", "jsonlite")) {
    if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
  }
  skill_root <- normalizePath(skill_root, winslash = "/")
  if (file.exists(output_dir)) stop("Fresh output directory required")
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = "/")
  source(file.path(skill_root, "scripts/model_mapping.R"), local = TRUE)
  source(file.path(skill_root, "scripts/growth_time_basis.R"), local = TRUE)
  checks <- list()
  check <- function(name, ok) {
    if (!isTRUE(ok)) stop("Contract failed: ", name)
    checks[[name]] <<- TRUE
  }
  reject <- function(name, expr) check(name, inherits(tryCatch(force(expr), error = identity), "error"))
  # 引擎守卫：生成阶段若误调 runModels/detectMplus，立即失败
  ns <- asNamespace("MplusAutomation")
  for (fun in c("runModels", "detectMplus")) {
    trace(fun, tracer = quote(stop("ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI")), print = FALSE, where = ns)
  }
  on.exit(for (fun in c("runModels", "detectMplus")) untrace(fun, where = ns), add = TRUE)
  reject("engine_guard_blocks_runModels", MplusAutomation::runModels())

  # 1. growth_time_basis：不规则波次（CHARLS 式 2011/2013/2015/2018/2020）
  waves <- c(2011, 2013, 2015, 2018, 2020)
  linear <- growth_time_basis(waves)
  check("basis_linear_uses_observed_times", identical(unname(linear[, "slope"]), c(0, 2, 4, 7, 9)) &&
    all(linear[, "intercept"] == 1) && identical(rownames(linear), as.character(waves)))
  quad <- growth_time_basis(waves, "quadratic")
  check("basis_quadratic_is_time_squared", identical(unname(quad[, "quadratic"]), c(0, 4, 16, 49, 81)))
  piece <- growth_time_basis(waves, "piecewise", knot = 2015)
  check("basis_piecewise_continuous_at_knot",
    identical(unname(piece[, "before"]), c(0, 2, 4, 4, 4)) && identical(unname(piece[, "after"]), c(0, 0, 0, 3, 5)) &&
    isTRUE(all.equal(unname(piece[, "before"] + piece[, "after"]), unname(linear[, "slope"]))))
  reject("basis_rejects_two_waves", growth_time_basis(c(1, 2)))
  reject("basis_rejects_unsorted_waves", growth_time_basis(c(1, 3, 2)))
  reject("basis_rejects_nonfinite", growth_time_basis(c(1, 2, Inf)))
  reject("basis_rejects_knot_without_piecewise", growth_time_basis(waves, "linear", knot = 2015))
  reject("basis_rejects_missing_knot", growth_time_basis(waves, "piecewise"))
  reject("basis_rejects_boundary_knot", growth_time_basis(waves, "piecewise", knot = 2011))

  # 2. growth_model_syntax：语句、换行、核对
  aliases <- c("y11", "y13", "y15", "y18", "y20")
  check("syntax_linear", identical(growth_model_syntax(waves, aliases)$model, "i s | y11@0 y13@2 y15@4 y18@7 y20@9;"))
  check("syntax_quadratic", identical(growth_model_syntax(waves, aliases, "quadratic")$model,
    "i s q | y11@0 y13@2 y15@4 y18@7 y20@9;"))
  check("syntax_piecewise_shares_intercept", identical(growth_model_syntax(waves, aliases, "piecewise", knot = 2015)$model,
    "i s1 | y11@0 y13@2 y15@4 y18@4 y20@4;\ni s2 | y11@0 y13@0 y15@0 y18@3 y20@5;"))
  fraction <- growth_model_syntax(c(0, 1 / 3, 1, 2.5), c("a", "b", "c", "d"))$model
  check("syntax_fixed_point_scores", identical(fraction, "i s | a@0 b@0.3333333333 c@1 d@2.5;"))
  long <- growth_model_syntax(seq(0, 11), sprintf("score%02d", 1:12), width = 60L)
  check("syntax_wraps_long_statements", all(nchar(strsplit(long$model, "\n")[[1]]) <= 60L) &&
    length(strsplit(long$model, "\n")[[1]]) > 1L)
  check("syntax_check_passes_on_output", isTRUE(check_growth_statements(long, sprintf("score%02d", 1:12))))
  tampered <- growth_model_syntax(waves, aliases)
  tampered$statements[[1]] <- sub("y15@4", "y15@4 y15@4", tampered$statements[[1]], fixed = TRUE)
  reject("syntax_check_rejects_repeated_variable", check_growth_statements(tampered, aliases))
  tampered <- growth_model_syntax(waves, aliases)
  tampered$statements[[1]] <- sub("y18@7", "y18@6", tampered$statements[[1]], fixed = TRUE)
  reject("syntax_check_rejects_wrong_loading", check_growth_statements(tampered, aliases))
  reject("syntax_rejects_alias_count", growth_model_syntax(waves, aliases[-1]))
  reject("syntax_rejects_long_alias", growth_model_syntax(waves, c("y11", "y13", "y15", "y18", "y2020abcd")))
  reject("syntax_rejects_factor_alias_clash", growth_model_syntax(waves, c("i", "y13", "y15", "y18", "y20")))
  reject("syntax_rejects_wide_lines", growth_model_syntax(waves, aliases, width = 120L))
  # 3. mplus_from_mapping：只换名，不改行、值、NA
  syn <- other_growth_synthetic()
  model <- growth_model_syntax(syn$waves, names(syn$mapping))$model
  analysis <- "ESTIMATOR = ML; PROCESSORS = 1;"
  object <- mplus_from_mapping(syn$data, syn$mapping, model, analysis)
  expected <- stats::setNames(syn$data[, unname(syn$mapping)], names(syn$mapping))
  check("mapping_keeps_alias_order", identical(object$usevariables, names(syn$mapping)))
  check("mapping_keeps_rows_values_na", isTRUE(all.equal(object$rdata, expected, check.attributes = FALSE)) &&
    identical(names(object$rdata), names(syn$mapping)) && sum(is.na(object$rdata)) == 3L)
  bad <- syn$mapping
  reject("mapping_rejects_non_frame", mplus_from_mapping(as.matrix(syn$data), syn$mapping, model, analysis))
  reject("mapping_rejects_empty_frame", mplus_from_mapping(syn$data[0, ], syn$mapping, model, analysis))
  reject("mapping_rejects_unnamed", mplus_from_mapping(syn$data, unname(syn$mapping), model, analysis))
  names(bad)[2] <- "Y11"
  reject("mapping_rejects_case_duplicate_alias", mplus_from_mapping(syn$data, bad, model, analysis))
  bad <- syn$mapping; names(bad)[1] <- "y2011score"
  reject("mapping_rejects_long_alias", mplus_from_mapping(syn$data, bad, model, analysis))
  bad <- syn$mapping; bad[[1]] <- "no_such_column"
  reject("mapping_rejects_missing_source", mplus_from_mapping(syn$data, bad, model, analysis))
  bad <- syn$mapping; bad[[2]] <- bad[[1]]
  reject("mapping_rejects_repeated_source", mplus_from_mapping(syn$data, bad, model, analysis))
  dup <- syn$data; names(dup)[1] <- names(dup)[2]
  reject("mapping_rejects_duplicate_data_names", mplus_from_mapping(dup, syn$mapping, model, analysis))
  text_col <- syn$data; text_col[[2]] <- as.character(text_col[[2]])
  reject("mapping_rejects_non_numeric", mplus_from_mapping(text_col, syn$mapping, model, analysis))
  inf_col <- syn$data; inf_col[5, 2] <- Inf
  reject("mapping_rejects_infinite", mplus_from_mapping(inf_col, syn$mapping, model, analysis))
  na_col <- syn$data; na_col[[2]] <- NA_real_
  reject("mapping_rejects_all_missing", mplus_from_mapping(na_col, syn$mapping, model, analysis))
  reject("mapping_rejects_empty_model", mplus_from_mapping(syn$data, syn$mapping, " ", analysis))
  reject("mapping_rejects_missing_analysis", mplus_from_mapping(syn$data, syn$mapping, model, NA_character_))
  # 4. 复用检查（reusable-models.md 末节）：A 原始；B 同值换名换序并多一列无关列；C 同名改值
  sha <- function(path) digest::digest(file = path, algo = "sha256")
  compile <- function(label, object) {
    folder <- file.path(output_dir, label); dir.create(folder, recursive = TRUE)
    prior <- getwd()
    tryCatch({
      setwd(folder)
      MplusAutomation::mplusModeler(object, modelout = "model.inp", dataout = "data.dat", run = 0L, check = FALSE,
        hashfilename = FALSE, writeData = "always", quiet = TRUE,
        Mplus_command = "FORBIDDEN_IN_SYNTHETIC_CI", killOnFail = FALSE)
    }, finally = setwd(prior))
    list(folder = label, inp = paste(readLines(file.path(folder, "model.inp"), warn = FALSE), collapse = "\n"),
         inp_sha256 = sha(file.path(folder, "model.inp")), dat_sha256 = sha(file.path(folder, "data.dat")),
         dat = utils::read.table(file.path(folder, "data.dat"), header = FALSE, na.strings = "."),
         fingerprint = digest::digest(object, algo = "sha256"))
  }
  b_data <- syn$data[, c(1, 6, 4, 2, 5, 3)]
  names(b_data) <- c("row", "w20", "w15", "w11", "w18", "w13")
  b_data$unused_note <- 99
  b_map <- c(y11 = "w11", y13 = "w13", y15 = "w15", y18 = "w18", y20 = "w20")
  c_data <- syn$data; c_data[, 2:6] <- c_data[, 2:6] + 0.25
  ca <- compile("reuse/A_original", mplus_from_mapping(syn$data, syn$mapping, model, analysis))
  cb <- compile("reuse/B_renamed_reordered", mplus_from_mapping(b_data, b_map, model, analysis))
  cc <- compile("reuse/C_changed_values", mplus_from_mapping(c_data, syn$mapping, model, analysis))
  check("reuse_renamed_same_inp", identical(ca$inp, cb$inp))
  check("reuse_renamed_same_dat_bytes", identical(ca$dat_sha256, cb$dat_sha256))
  check("reuse_renamed_same_fingerprint", identical(ca$fingerprint, cb$fingerprint))
  check("reuse_changed_values_same_inp", identical(ca$inp, cc$inp))
  check("reuse_changed_values_new_dat", !identical(ca$dat_sha256, cc$dat_sha256))
  check("reuse_changed_values_new_fingerprint", !identical(ca$fingerprint, cc$fingerprint))
  check("dat_matches_mapped_values", nrow(ca$dat) == nrow(expected) && ncol(ca$dat) == ncol(expected) &&
    isTRUE(all.equal(unname(as.matrix(ca$dat)), unname(as.matrix(expected)), tolerance = 1e-6)))
  check("inp_contains_growth_statement", grepl(gsub("\\s+", "", model), gsub("\\s+", "", ca$inp), fixed = TRUE))

  # 5. 三种形状都能编译进 INP，且每行不超过 Mplus 的 90 字符
  shapes <- list()
  for (shape in c("linear", "quadratic", "piecewise")) {
    syntax <- growth_model_syntax(syn$waves, names(syn$mapping), shape, knot = if (shape == "piecewise") 2015 else NULL)
    compiled <- compile(file.path("shapes", shape), mplus_from_mapping(syn$data, syn$mapping, syntax$model, analysis))
    flat <- gsub("\\s+", "", compiled$inp)
    check(paste0("shape_", shape, "_statements_in_inp"),
      all(vapply(syntax$statements, function(s) grepl(gsub("\\s+", "", s), flat, fixed = TRUE), logical(1))))
    check(paste0("shape_", shape, "_lines_within_90"), all(nchar(strsplit(compiled$inp, "\n")[[1]]) <= 90L))
    shapes[[shape]] <- compiled[c("folder", "inp_sha256", "dat_sha256")]
  }

  manifest <- list(test = "other_growth_compile", mplus_calls = 0L, checks = names(checks),
    reuse = lapply(list(A = ca, B = cb, C = cc), function(x) x[c("folder", "inp_sha256", "dat_sha256", "fingerprint")]),
    shapes = shapes)
  jsonlite::write_json(manifest, file.path(output_dir, "other_growth_compile_manifest.json"),
    auto_unbox = TRUE, pretty = TRUE)
  cat("OTHER_GROWTH_COMPILE_PASS", length(checks), "checks; Mplus calls: 0\n")
  invisible(manifest)
}
