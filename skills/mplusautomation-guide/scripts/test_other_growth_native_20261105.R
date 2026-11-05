# OTHER_GROWTH 原生合成验收：需要 Mplus，只在获准的 Windows 窗口运行，托管 CI 不跑。
# 用 test_other_growth_compile_20261105.R 的同一份合成数据，按 reusable-models.md 末节比较
# 参数身份、估计值与标准误：A 与 B（同值换名换序）必须逐项相同，A 与 C（改值）必须不同。
# 运行：Rscript -e 'source("scripts/test_other_growth_native_20261105.R");
#   test_other_growth_native("<新的运行根>", ".", "<mplus.exe>")'
test_other_growth_native <- function(run_root, skill_root, command = Sys.getenv("MPLUS_COMMAND", "")) {
  for (pkg in c("MplusAutomation", "digest", "jsonlite")) {
    if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
  }
  skill_root <- normalizePath(skill_root, winslash = "/")
  if (file.exists(run_root)) stop("Fresh run root required")
  for (file in c("model_mapping.R", "growth_time_basis.R", "mplus_workflow.R", "test_other_growth_compile_20261105.R"))
    source(file.path(skill_root, "scripts", file), local = TRUE)
  syn <- other_growth_synthetic()
  analysis <- "ESTIMATOR = ML; PROCESSORS = 1;"
  b_data <- syn$data[, c(1, 6, 4, 2, 5, 3)]
  names(b_data) <- c("row", "w20", "w15", "w11", "w18", "w13")
  b_map <- c(y11 = "w11", y13 = "w13", y15 = "w15", y18 = "w18", y20 = "w20")
  c_data <- syn$data; c_data[, 2:6] <- c_data[, 2:6] + 0.25
  linear <- growth_model_syntax(syn$waves, names(syn$mapping))$model
  runs <- list(
    linear_A = mplus_from_mapping(syn$data, syn$mapping, linear, analysis),
    linear_B = mplus_from_mapping(b_data, b_map, linear, analysis),
    linear_C = mplus_from_mapping(c_data, syn$mapping, linear, analysis),
    quadratic_A = mplus_from_mapping(syn$data, syn$mapping,
      growth_model_syntax(syn$waves, names(syn$mapping), "quadratic")$model, analysis),
    piecewise_A = mplus_from_mapping(syn$data, syn$mapping,
      growth_model_syntax(syn$waves, names(syn$mapping), "piecewise", knot = 2015)$model, analysis))
  results <- list()
  for (id in names(runs)) {
    cat("[other-growth-native]", id, "start", format(Sys.time(), "%H:%M:%S"), "\n"); flush.console()
    # 单个模型报错（找不到引擎、目录已存在等）也记进回执，不中断其余模型
    results[[id]] <- tryCatch({
      out <- run_mplus_model(runs[[id]], run_root, id, command = command)
      list(status = out$validation$status, reasons = out$validation$reasons, directory = out$directory)
    }, error = function(e) list(status = "ERROR", reasons = conditionMessage(e), directory = NA_character_))
    cat("[other-growth-native]", id, results[[id]]$status, "\n"); flush.console()
  }
  code_sha256 <- lapply(stats::setNames(nm = c("model_mapping.R", "growth_time_basis.R", "mplus_workflow.R")),
    function(f) digest::digest(file = file.path(skill_root, "scripts", f), algo = "sha256"))
  receipt_path <- file.path(run_root, "other_growth_native_receipt.json")
  dir.create(run_root, recursive = TRUE, showWarnings = FALSE)
  # 先看状态再读参数：有模型没通过时只写状态与原因的回执，不去读可能不存在的 parameters.csv
  passed <- vapply(results, function(r) identical(r$status, "PASS"), logical(1))
  if (!all(passed)) {
    receipt <- list(test = "other_growth_native", models = length(runs),
      statuses = lapply(results, `[[`, "status"), reasons = lapply(results[!passed], `[[`, "reasons"),
      checks = list(all_models_pass = FALSE), code_sha256 = code_sha256)
    jsonlite::write_json(receipt, receipt_path, auto_unbox = TRUE, pretty = TRUE)
    stop("OTHER_GROWTH native acceptance failed: models not PASS: ", paste(names(results)[!passed], collapse = ", "))
  }
  read_params <- function(id) utils::read.csv(file.path(results[[id]]$directory, "parameters.csv"))
  key <- function(p) paste(p$paramHeader, p$param)
  a <- read_params("linear_A"); b <- read_params("linear_B"); cc <- read_params("linear_C")
  # 空参数表会让逐项比较空转，所以先要求有行
  same_keys_ab <- nrow(a) > 0L && identical(key(a), key(b))
  same_ab <- same_keys_ab && identical(a$est, b$est) && identical(a$se, b$se)
  differs_ac <- nrow(a) > 0L && identical(key(a), key(cc)) && any(a$est != cc$est)
  factors <- function(id) unique(toupper(read_params(id)$paramHeader))
  checks <- c(
    all_models_pass = TRUE,
    renamed_reordered_identical_estimates = same_ab,
    changed_values_change_estimates = differs_ac,
    # MplusAutomation 把增长语句的载荷头写成「因子名.|」
    quadratic_has_q_factor = "Q.|" %in% factors("quadratic_A"),
    piecewise_has_two_slopes = all(c("S1.|", "S2.|") %in% factors("piecewise_A")))
  # 回执只记状态与计数；估计值留在各模型目录（本机证据），不进公开仓库
  receipt <- list(test = "other_growth_native", models = length(runs),
    statuses = lapply(results, `[[`, "status"), checks = as.list(checks),
    compared_items_ab = nrow(a),
    max_abs_diff_ab = if (same_keys_ab) max(abs(c(a$est - b$est, a$se - b$se))) else NA,
    code_sha256 = code_sha256)
  jsonlite::write_json(receipt, receipt_path, auto_unbox = TRUE, pretty = TRUE, na = "null")
  if (!all(checks)) stop("OTHER_GROWTH native acceptance failed: ", paste(names(checks)[!checks], collapse = ", "))
  cat("OTHER_GROWTH_NATIVE_PASS", length(runs), "models\n")
  invisible(receipt)
}
