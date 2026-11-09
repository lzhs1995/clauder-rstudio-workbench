# 双过程固定载荷增长模型的合成编译合同；不运行 Mplus，不使用真实记录或估计值。
# 从 skill 根运行：source("scripts/test_pp_lgcm_compile_20261108.R")
# test_pp_lgcm_compile("<新的输出目录>", ".")
test_pp_lgcm_compile <- function(output_dir, skill_root) {
  for (pkg in c("MplusAutomation", "digest", "jsonlite")) {
    if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
  }
  skill_root <- normalizePath(skill_root, winslash = "/", mustWork = TRUE)
  if (file.exists(output_dir)) stop("Fresh output directory required")
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = "/", mustWork = TRUE)
  source(file.path(skill_root, "scripts/model_mapping.R"), local = TRUE)
  source(file.path(skill_root, "scripts/growth_time_basis.R"), local = TRUE)
  checks <- list()
  check <- function(name, ok) {
    if (!isTRUE(ok)) stop("Contract failed: ", name)
    checks[[name]] <<- TRUE
  }
  reject <- function(name, expr, pattern = NULL) {
    error <- tryCatch({ force(expr); NULL }, error = identity)
    check(name, inherits(error, "error") &&
      (is.null(pattern) || grepl(pattern, conditionMessage(error), fixed = TRUE)))
  }
  ns <- asNamespace("MplusAutomation")
  for (fun in c("runModels", "detectMplus")) {
    trace(fun, tracer = quote(stop("ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI")), print = FALSE, where = ns)
  }
  on.exit(for (fun in c("runModels", "detectMplus")) untrace(fun, where = ns), add = TRUE)
  reject("engine_guard_blocks_runModels", MplusAutomation::runModels(), "ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI")
  reject("engine_guard_blocks_detectMplus", MplusAutomation::detectMplus(), "ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI")
  check("parallel_growth_api_available", is.function(parallel_growth_model_syntax))

  # 两过程具有不同数量、不等间隔的波次；确定性合成值不污染调用者随机数状态。
  n <- 72L
  sources <- c("mood_score_long_source_wave_2010", "情绪_2012", "mood_wave_2015",
    "情绪_2017", "mood_wave_2020", "health_long_source_wave_2001", "健康_2004",
    "health_wave_2006", "健康_2009", "baseline_age_long_source", "基线资源")
  data <- as.data.frame(lapply(seq_along(sources), function(j) seq_len(n) * (j + 1) / 16 + j),
                        check.names = FALSE)
  names(data) <- sources
  data[c(3L, 17L), 2L] <- NA_real_
  data[5L, 7L] <- NA_real_
  data[12L, 11L] <- NA_real_
  data$unused_identifier <- seq_len(n)
  base_processes <- list(
    mood = list(variables = stats::setNames(sources[1:5], c("m10", "m12", "m15", "m17", "m20")),
                waves = c(2010, 2012, 2015, 2017, 2020), factors = c("im", "sm")),
    health = list(variables = stats::setNames(sources[6:9], c("h01", "h04", "h06", "h09")),
                  waves = c(2001, 2004, 2006, 2009), factors = c("ih", "sh")))
  covariates <- stats::setNames(sources[10:11], c("age", "res"))
  analysis <- "ESTIMATOR = ML; PROCESSORS = 1;"
  compact <- function(x) gsub("\\s+", "", x)
  statements <- function(model) {
    result <- trimws(strsplit(gsub("\\s+", " ", model), ";", fixed = TRUE)[[1]])
    result[nzchar(result)]
  }
  sha <- function(path) digest::digest(file = path, algo = "sha256")
  expected_map <- function(processes, covs) c(processes[[1]]$variables, processes[[2]]$variables, covs)
  compile <- function(label, object) {
    folder <- file.path(output_dir, label)
    dir.create(folder, recursive = TRUE)
    prior <- getwd()
    tryCatch({
      setwd(folder)
      MplusAutomation::mplusModeler(object, modelout = "model.inp", dataout = "data.dat", run = 0L,
        check = FALSE, hashfilename = FALSE, writeData = "always", quiet = TRUE,
        Mplus_command = "FORBIDDEN_IN_SYNTHETIC_CI", killOnFail = FALSE)
    }, finally = setwd(prior))
    list(folder = label, inp = paste(readLines(file.path(folder, "model.inp"), warn = FALSE), collapse = "\n"),
      inp_sha256 = sha(file.path(folder, "model.inp")), dat_sha256 = sha(file.path(folder, "data.dat")),
      dat = utils::read.table(file.path(folder, "data.dat"), header = FALSE, na.strings = "."),
      fingerprint = digest::digest(object, algo = "sha256"))
  }
  equal_values <- function(left, right) {
    identical(dim(left), dim(right)) && identical(unname(is.na(as.matrix(left))), unname(is.na(as.matrix(right)))) &&
      isTRUE(all.equal(unname(as.matrix(left)), unname(as.matrix(right)), tolerance = 1e-8))
  }
  # 独立展开 WITH/ON 的左右两侧，防止漏项、重复项、残差相关或跨过程定向路径混入。
  check_relations <- function(label, syntax, covs) {
    all <- statements(syntax$model)
    with_lines <- all[grepl(" WITH ", toupper(all), fixed = TRUE)]
    on_lines <- all[grepl(" ON ", toupper(all), fixed = TRUE)]
    growth_lines <- all[grepl("|", all, fixed = TRUE)]
    check(paste0(label, "_only_growth_with_on"),
      length(all) == length(with_lines) + length(on_lines) + length(growth_lines))
    split_relation <- function(line, op) {
      sides <- strsplit(toupper(line), paste0(" ", op, " "), fixed = TRUE)[[1]]
      if (length(sides) != 2L) stop("Malformed relation: ", line)
      list(left = strsplit(trimws(sides[1]), "\\s+")[[1]], right = strsplit(trimws(sides[2]), "\\s+")[[1]])
    }
    pair_key <- function(a, b) paste(sort(c(a, b)), collapse = ":")
    observed <- unlist(lapply(with_lines, function(line) {
      rel <- split_relation(line, "WITH")
      as.vector(outer(rel$left, rel$right, Vectorize(pair_key)))
    }), use.names = FALSE)
    expected <- apply(utils::combn(toupper(syntax$factors), 2L), 2L,
                      function(pair) pair_key(pair[1], pair[2]))
    check(paste0(label, "_all_factor_pairs_once"),
      length(observed) == length(expected) && !anyDuplicated(observed) && identical(sort(observed), sort(expected)))
    if (length(covs)) {
      rels <- lapply(on_lines, split_relation, op = "ON")
      check(paste0(label, "_one_on_statement_per_factor"), length(rels) == length(syntax$factors) &&
        all(vapply(rels, function(r) length(r$left) == 1L &&
          identical(r$right, toupper(names(covs))), logical(1))) &&
        identical(sort(unlist(lapply(rels, `[[`, "left"))), sort(toupper(syntax$factors))))
    } else check(paste0(label, "_no_on_without_covariates"), length(on_lines) == 0L)
  }

  # 参考载荷直接列出，不从被测生成器计算；二次载荷同时核显式 basis 和 Mplus 的三因子简写。
  cases <- list(linear_linear = base_processes, quadratic_linear = base_processes,
                piecewise_quadratic = base_processes)
  cases$quadratic_linear$mood$shape <- "quadratic"
  cases$quadratic_linear$mood$factors <- c("im", "sm", "qm")
  cases$piecewise_quadratic$mood$shape <- "piecewise"
  cases$piecewise_quadratic$mood$knot <- 2015
  cases$piecewise_quadratic$mood$factors <- c("im", "smb", "sma")
  cases$piecewise_quadratic$health$shape <- "quadratic"
  cases$piecewise_quadratic$health$factors <- c("ih", "sh", "qh")
  expected_growth <- list(
    linear_linear = c("im sm | m10@0 m12@2 m15@5 m17@7 m20@10", "ih sh | h01@0 h04@3 h06@5 h09@8"),
    quadratic_linear = c("im sm qm | m10@0 m12@2 m15@5 m17@7 m20@10", "ih sh | h01@0 h04@3 h06@5 h09@8"),
    piecewise_quadratic = c("im smb | m10@0 m12@2 m15@5 m17@5 m20@5",
      "im sma | m10@0 m12@0 m15@0 m17@2 m20@5", "ih sh qh | h01@0 h04@3 h06@5 h09@8"))
  expected_bases <- list(
    linear_linear = list(cbind(intercept = 1, slope = c(0, 2, 5, 7, 10)),
                         cbind(intercept = 1, slope = c(0, 3, 5, 8))),
    quadratic_linear = list(cbind(intercept = 1, slope = c(0, 2, 5, 7, 10), quadratic = c(0, 4, 25, 49, 100)),
                            cbind(intercept = 1, slope = c(0, 3, 5, 8))),
    piecewise_quadratic = list(cbind(intercept = 1, before = c(0, 2, 5, 5, 5), after = c(0, 0, 0, 2, 5)),
                              cbind(intercept = 1, slope = c(0, 3, 5, 8), quadratic = c(0, 9, 25, 64))))
  compiled_manifest <- list()
  for (id in names(cases)) {
    process <- cases[[id]]
    syntax <- parallel_growth_model_syntax(process, covariates, width = 40L)
    mapping <- expected_map(process, covariates)
    check(paste0(id, "_returned_mapping_role_order"), identical(syntax$variables, mapping))
    check(paste0(id, "_returned_process_roles"), identical(names(syntax$processes), names(process)))
    check(paste0(id, "_returned_factors_role_order"),
      identical(syntax$factors, unname(unlist(lapply(process, `[[`, "factors")))))
    actual_growth <- statements(syntax$model)
    actual_growth <- actual_growth[grepl("|", actual_growth, fixed = TRUE)]
    check(paste0(id, "_fixed_loading_statements"), identical(compact(actual_growth), compact(expected_growth[[id]])))
    for (k in seq_along(process)) {
      basis <- syntax$processes[[k]]$basis
      check(paste0(id, "_basis_process_", k), identical(unname(basis), unname(expected_bases[[id]][[k]])) &&
        identical(colnames(basis), colnames(expected_bases[[id]][[k]])) &&
        identical(rownames(basis), as.character(process[[k]]$waves)))
    }
    check(paste0(id, "_syntax_width"), all(nchar(strsplit(syntax$model, "\n")[[1]]) <= 40L))
    check_relations(id, syntax, covariates)
    expected <- stats::setNames(data[, unname(mapping), drop = FALSE], names(mapping))
    a_obj <- mplus_from_mapping(data, syntax$variables, syntax$model, analysis)
    check(paste0(id, "_mapping_values_na_and_order"), identical(a_obj$usevariables, names(mapping)) &&
      identical(names(a_obj$rdata), names(mapping)) && equal_values(a_obj$rdata, expected) && sum(is.na(a_obj$rdata)) == 4L)

    # 所有源列改名，再逆序并添加无关列；同步更新映射，角色和别名保持不变。
    renamed <- data
    new_names <- paste0("重命名的很长源列_", seq_along(renamed))
    rename_map <- stats::setNames(new_names, names(renamed))
    names(renamed) <- new_names
    renamed <- renamed[, rev(seq_along(renamed)), drop = FALSE]
    renamed$unused_extra <- -100
    b_process <- lapply(process, function(p) {
      p$variables <- stats::setNames(unname(rename_map[p$variables]), names(p$variables)); p
    })
    b_covs <- stats::setNames(unname(rename_map[covariates]), names(covariates))
    b_syntax <- parallel_growth_model_syntax(b_process, b_covs, width = 40L)
    b_obj <- mplus_from_mapping(renamed, b_syntax$variables, b_syntax$model, analysis)
    changed <- data
    changed[, sources] <- lapply(changed[, sources, drop = FALSE], function(x) x + 0.25)
    c_obj <- mplus_from_mapping(changed, syntax$variables, syntax$model, analysis)
    a <- compile(file.path(id, "original"), a_obj)
    b <- compile(file.path(id, "renamed_reordered"), b_obj)
    changed_run <- compile(file.path(id, "changed_values"), c_obj)
    check(paste0(id, "_rename_model_semantics"), identical(syntax$model, b_syntax$model))
    check(paste0(id, "_rename_same_inp_dat_fingerprint"), identical(a$inp, b$inp) &&
      identical(a$dat_sha256, b$dat_sha256) && identical(a$fingerprint, b$fingerprint))
    check(paste0(id, "_changed_values_same_inp_new_dat"), identical(a$inp, changed_run$inp) &&
      !identical(a$dat_sha256, changed_run$dat_sha256) && !identical(a$fingerprint, changed_run$fingerprint))
    check(paste0(id, "_dat_original_values_na_order"), equal_values(a$dat, expected))
    check(paste0(id, "_dat_renamed_values_na_order"), equal_values(b$dat, expected))
    check(paste0(id, "_dat_changed_values_na_order"), equal_values(changed_run$dat, expected + 0.25))
    check(paste0(id, "_inp_contains_full_model"), grepl(compact(syntax$model), compact(a$inp), fixed = TRUE))
    check(paste0(id, "_compiled_lines_within_90"), all(nchar(strsplit(a$inp, "\n")[[1]]) <= 90L))
    compiled_manifest[[id]] <- lapply(list(original = a, renamed_reordered = b, changed_values = changed_run),
      function(x) x[c("folder", "inp_sha256", "dat_sha256", "fingerprint")])
  }
  no_cov <- parallel_growth_model_syntax(base_processes)
  check("no_covariates_mapping_only_processes", identical(no_cov$variables, expected_map(base_processes, character())))
  check_relations("no_covariates", no_cov, character())

  # 过程可以分别选择已声明协变量；不凭因子名称猜测哪个过程需要调整。
  adjusted <- base_processes
  adjusted$mood$adjust_for <- "age"
  adjusted$health$adjust_for <- "res"
  adjusted_syntax <- parallel_growth_model_syntax(adjusted, covariates)
  adjusted_on <- statements(adjusted_syntax$model)
  adjusted_on <- adjusted_on[grepl(" ON ", toupper(adjusted_on), fixed = TRUE)]
  check("process_specific_covariates_on_exact_factors", identical(sort(compact(adjusted_on)),
    sort(compact(c("im ON age", "sm ON age", "ih ON res", "sh ON res")))))
  check("process_specific_covariates_preserve_mapping", identical(adjusted_syntax$variables,
    expected_map(base_processes, covariates)))
  adjusted$mood$adjust_for <- character()
  adjusted$health$adjust_for <- c("age", "res")
  unadjusted_on <- statements(parallel_growth_model_syntax(adjusted, covariates)$model)
  unadjusted_on <- unadjusted_on[grepl(" ON ", toupper(unadjusted_on), fixed = TRUE)]
  check("explicit_empty_adjustment_has_no_on", identical(sort(compact(unadjusted_on)),
    sort(compact(c("ih ON age res", "sh ON age res")))))
  adjusted$mood$adjust_for <- "unknown"
  reject("reject_unknown_adjust_for", parallel_growth_model_syntax(adjusted, covariates))
  adjusted$mood$adjust_for <- c("age", "age")
  reject("reject_duplicate_adjust_for", parallel_growth_model_syntax(adjusted, covariates))
  adjusted$mood$adjust_for <- character()
  adjusted$health$adjust_for <- "age"
  reject("reject_unused_declared_covariate", parallel_growth_model_syntax(adjusted, covariates))

  # 拒绝路径只改一个合同条件，避免错误被无关参数掩盖。
  reject("reject_one_process", parallel_growth_model_syntax(base_processes[1]))
  reject("reject_three_processes", parallel_growth_model_syntax(c(base_processes, list(third = base_processes[[1]]))))
  reject("reject_unnamed_processes", parallel_growth_model_syntax(unname(base_processes)))
  bad <- base_processes; bad$mood$variables <- NULL
  reject("reject_missing_variable_role", parallel_growth_model_syntax(bad))
  bad <- base_processes; bad$mood$waves <- NULL
  reject("reject_missing_wave_role", parallel_growth_model_syntax(bad))
  bad <- base_processes; bad$mood$factors <- NULL
  reject("reject_missing_explicit_factors", parallel_growth_model_syntax(bad))
  bad <- base_processes; bad$mood$variables <- bad$mood$variables[-2]
  reject("reject_missing_wave_alias", parallel_growth_model_syntax(bad))
  bad <- base_processes; bad$mood$variables <- unname(bad$mood$variables)
  reject("reject_unnamed_mapping", parallel_growth_model_syntax(bad))
  bad <- base_processes; names(bad$health$variables)[1] <- "M10"
  reject("reject_cross_process_case_alias", parallel_growth_model_syntax(bad))
  bad <- base_processes; bad$health$factors[1] <- "IM"
  reject("reject_cross_process_case_factor", parallel_growth_model_syntax(bad))
  bad <- base_processes; bad$health$factors[1] <- "M10"
  reject("reject_factor_other_process_alias", parallel_growth_model_syntax(bad))
  bad_cov <- covariates; names(bad_cov)[1] <- "M10"
  reject("reject_covariate_observed_alias", parallel_growth_model_syntax(base_processes, bad_cov))
  bad_cov <- covariates; names(bad_cov)[1] <- "SH"
  reject("reject_covariate_factor_alias", parallel_growth_model_syntax(base_processes, bad_cov))
  bad_cov <- covariates; names(bad_cov)[2] <- "AGE"
  reject("reject_covariate_case_duplicate", parallel_growth_model_syntax(base_processes, bad_cov))
  bad <- base_processes; bad$health$variables[1] <- bad$mood$variables[1]
  reject("reject_cross_process_duplicate_source", parallel_growth_model_syntax(bad))
  bad_cov <- covariates; bad_cov[1] <- base_processes$mood$variables[1]
  reject("reject_covariate_duplicate_source", parallel_growth_model_syntax(base_processes, bad_cov))
  invalid_times <- list(character = as.character(base_processes$mood$waves), short = c(1, 2),
                       unsorted = c(1, 3, 2, 4, 5), duplicate = c(1, 2, 2, 4, 5),
                       nonfinite = c(1, 2, Inf, 4, 5), missing = c(1, 2, NA_real_, 4, 5))
  for (invalid in names(invalid_times)) {
    bad <- base_processes; bad$mood$waves <- invalid_times[[invalid]]
    reject(paste0("reject_invalid_times_", invalid), parallel_growth_model_syntax(bad))
  }
  bad <- base_processes; bad$mood$shape <- "free"
  reject("reject_free_loading_shape", parallel_growth_model_syntax(bad))
  for (field in c("loadings", "cross_paths", "residual_correlations", "interactions")) {
    bad <- base_processes; bad$mood[[field]] <- "UNSUPPORTED"
    reject(paste0("reject_unknown_spec_", field), parallel_growth_model_syntax(bad))
  }
  bad <- cases$piecewise_quadratic; bad$mood$knot <- NULL
  reject("reject_piecewise_missing_knot", parallel_growth_model_syntax(bad))
  reject("reject_invalid_width", parallel_growth_model_syntax(base_processes, width = 91L))
  reject("reject_absent_source_data_wave", mplus_from_mapping(data[, -2L], no_cov$variables, no_cov$model, analysis))

  manifest <- list(test = "pp_lgcm_compile", status = "PASS", mplus_calls = 0L,
    synthetic_rows = n, shape_pairs = names(cases), source_variants = 3L, compiled_inputs = 9L,
    checks = names(checks), runs = compiled_manifest)
  jsonlite::write_json(manifest, file.path(output_dir, "pp_lgcm_compile_manifest.json"),
                       auto_unbox = TRUE, pretty = TRUE)
  cat("PP_LGCM_COMPILE_PASS", length(checks), "checks; Mplus calls: 0\n")
  invisible(manifest)
}
