# M2/M3/N2 合成边界回归：保留列潜类名冲突、最终 INP 行宽和显式测量/转移结构。
# 独立运行：Rscript test_ch7_syntax_boundaries_20261113.R <新的证据目录>
test_ch7_syntax_boundaries_20261113 <- function(output_dir, skill_root) {
  source(file.path(skill_root, "scripts/ch7_mixture_syntax.R"), local = TRUE)
  for (pkg in c("MplusAutomation", "digest", "jsonlite"))
    if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
  if (file.exists(output_dir)) stop("Fresh output directory required")
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = "/")
  checks <- list(); artifacts <- list()
  check <- function(name, ok) {
    if (!isTRUE(ok)) stop("Syntax boundary failed: ", name)
    checks[[name]] <<- TRUE
  }
  reject <- function(name, expr, message = NULL) {
    result <- tryCatch(force(expr), error = identity)
    check(name, inherits(result, "error") &&
      (is.null(message) || grepl(message, conditionMessage(result), fixed = TRUE)))
  }
  # run=0 之外另设引擎负控；该套件只读合成产物。
  ns <- asNamespace("MplusAutomation")
  traced <- character()
  on.exit(for (fun in traced) untrace(fun, where = ns), add = TRUE)
  for (fun in c("runModels", "detectMplus")) {
    # 外层 family 套件可能已设门禁，不覆盖其 tracer 或在退出时移除它。
    if (!inherits(get(fun, envir = ns), "functionWithTrace")) {
      trace(fun, tracer = quote(stop("ENGINE_CALL_FORBIDDEN_SYNTAX_BOUNDARIES")),
            print = FALSE, where = ns)
      traced <- c(traced, fun)
    }
  }
  reject("engine_run_forbidden", MplusAutomation::runModels(), "ENGINE_CALL_FORBIDDEN")
  reject("engine_discovery_forbidden", MplusAutomation::detectMplus(), "ENGINE_CALL_FORBIDDEN")
  data <- data.frame(id = seq_len(16L), x1 = seq_len(16L) / 10,
    x2 = seq_len(16L) / 20, n1 = rep(1:2, 8L), n2 = rep(2:1, 8L))
  build <- function(family, id_name = "id", step3 = FALSE, retain_id = TRUE) {
    d <- data; names(d)[names(d) == "id"] <- id_name
    used <- if (step3) c("n1", "n2") else if (family == "lpa") "x1" else c("x1", "x2")
    ch7_mixture_object(d, family, classes = 2L,
      waves = if (step3) NULL else if (family == "lpa") list("x1") else list("x1", "x2"),
      step3 = if (step3) list(nominal = used, logits = matrix(c(1, -1), 2L, 1L)) else NULL,
      keep = c(if (retain_id) id_name, used))
  }
  for (family in c("lpa", "lta", "mslta")) {
    reserved <- switch(family, lpa = c("c", "C"), lta = c("c1", "C1", "c2", "C2"),
                       mslta = c("g", "G", "c1", "C1", "c2", "C2"))
    for (name in reserved) {
      reject(paste("retained_id_collision", family, name, sep = ":"), build(family, name),
             "All kept observed names")
      check(paste("discarded_column_allowed", family, name, sep = ":"),
            is.list(build(family, name, retain_id = FALSE)))
      if (family != "lpa") reject(paste("step3_id_collision", family, name, sep = ":"),
        build(family, name, step3 = TRUE), "All kept observed names")
    }
    check(paste0("normal_id_allowed:", family), is.list(build(family)))
  }
  check("lpa_nonreserved_c1_allowed", is.list(build("lpa", "c1")))
  check("lta_nonreserved_g_allowed", is.list(build("lta", "g")))

  compile <- function(id, built) {
    folder <- file.path(output_dir, id); dir.create(folder)
    prior <- getwd()
    tryCatch({
      setwd(folder)
      MplusAutomation::mplusModeler(built$object, modelout = "model.inp", dataout = "source.dat",
        run = 0L, check = FALSE, hashfilename = FALSE, writeData = "always", quiet = TRUE,
        Mplus_command = "FORBIDDEN_SYNTAX_BOUNDARIES", killOnFail = FALSE)
    }, finally = setwd(prior))
    path <- file.path(folder, "model.inp")
    lines <- readLines(path, warn = FALSE)
    check(paste0(id, ":actual_input_width"), all(nchar(lines, type = "bytes") <= 90L))
    check(paste0(id, ":final_width_gate"), ch7_validate_input_width(path))
    artifacts[[id]] <<- list(input = paste0(id, "/model.inp"),
      input_sha256 = digest::digest(path, algo = "sha256", file = TRUE),
      max_bytes = max(nchar(lines, type = "bytes")))
    paste(lines, collapse = "\n")
  }
  # N2：四波测量不变/自由模型及参考类 K 的 Step-1 不估计转移。
  # 使用合成的四连续+两分类结构，检查每个类/波的测量标签，不读取研究值。
  structure_data <- data.frame(sid = seq_len(16L))
  structure_waves <- lapply(seq_len(4L), function(w) paste0("t", w, "i", seq_len(6L)))
  structure_binary <- unlist(lapply(structure_waves, function(v) v[5:6]))
  for (v in unlist(structure_waves)) structure_data[[v]] <- if (v %in% structure_binary)
    rep(0:1, 8L) else seq_len(16L) / 7
  for (invariant in c(TRUE, FALSE)) {
    built <- ch7_mixture_object(structure_data, "lta", waves = structure_waves,
      categorical = structure_binary, classes = 4L, invariant = invariant,
      transitions = FALSE, keep = names(structure_data))
    id <- if (invariant) "n2_step1_invariant_k4" else "n2_step1_free_k4"
    text <- compile(id, built)
    check(paste0(id, ":no_transition_regressions"), !grepl("\\bON\\b", text))
    check(paste0(id, ":four_class_declaration"), grepl("c1(4) c2(4) c3(4) c4(4)", text, fixed = TRUE))
    check(paste0(id, ":all_measurement_blocks"), all(vapply(unlist(lapply(1:4,
      function(w) paste0("%c", w, "#", 1:4, "%"))), function(block) grepl(block, text, fixed = TRUE), TRUE)))
    check(paste0(id, ":metadata_matches_structure"), identical(built$spec$transitions, FALSE))
    expected <- if (invariant) "[t4i6$1] (mk4i6);" else "[t4i6$1] (w4k4i6);"
    check(paste0(id, ":measurement_labels"), grepl(expected, text, fixed = TRUE))
  }
  transition_text <- compile("n2_lta_transitions_true", ch7_mixture_object(structure_data,
    "lta", waves = structure_waves, categorical = structure_binary, classes = 4L,
    transitions = TRUE))
  check("n2_explicit_transition_regressions", all(vapply(paste0("c", 2:4, " ON c", 1:3, ";"),
    function(line) grepl(line, transition_text, fixed = TRUE), TRUE)))
  reject("n2_mslta_measurement_only_rejected", ch7_mixture_object(structure_data, "mslta",
    waves = structure_waves, categorical = structure_binary, classes = 4L, transitions = FALSE),
    "MS-LTA requires transitions = TRUE")
  for (bad in list(NA, 1L, "FALSE", c(TRUE, FALSE)))
    reject(paste0("n2_invalid_transitions_", paste(bad, collapse = "_")),
      ch7_mixture_object(structure_data, "lta", waves = structure_waves,
        categorical = structure_binary, classes = 4L, transitions = bad), "transitions must")
  source(file.path(skill_root, "scripts/ch7_native_fixture_20261111.R"), local = TRUE)
  fixture <- ch7_native_fixture(file.path(output_dir, "native_fixture"), n = 100L)
  fixture_models <- setNames(fixture$config$models, vapply(fixture$config$models, `[[`, "", "id"))
  check("n2_fixture_step1_measurement_only", identical(fixture_models$SYN_LTA4_MI_STEP1$transitions, FALSE))
  check("n2_fixture_mslta_retains_transitions", identical(fixture_models$SYN_MSLTA4_MI$transitions, TRUE))
  check("n2_fixture_all_structure_flags_explicit", all(vapply(fixture_models,
    function(x) is.logical(x$transitions) && length(x$transitions) == 1L && !is.na(x$transitions), TRUE)))

  names_long <- sprintf("x%07d", seq_len(56L))
  long_data <- as.data.frame(setNames(lapply(seq_along(names_long), function(i)
    seq_len(16L) / (i + 1L)), names_long))
  waves <- split(names_long, rep(seq_len(4L), each = 14L))
  for (family in c("lpa", "lta", "mslta")) {
    selected <- if (family == "lpa") waves[1L] else waves
    built <- ch7_mixture_object(long_data, family, waves = selected, classes = 12L,
      center = unlist(selected), keep = unlist(selected))
    text <- compile(paste0(family, "_long_k12"), built)
    flat <- gsub("[[:space:]]+", " ", text)
    check(paste0(family, ":all_long_names_kept"), all(vapply(unlist(selected),
      function(v) grepl(v, flat, fixed = TRUE), logical(1))))
    if (family == "lpa") {
      expected <- paste0("[", paste(waves[[1L]], collapse = " "), "];")
      check("lpa_long_means_tokens_preserved", length(regmatches(flat,
        gregexpr(expected, flat, fixed = TRUE))[[1]]) == 12L)
    } else check(paste0(family, ":invariance_labels_preserved"),
      all(vapply(paste0("(mk12i", seq_len(14L), ");"), function(v)
        grepl(v, text, fixed = TRUE), logical(1))))
    if (family == "mslta") check("mslta_large_k_fixed_values_preserved",
      grepl("c1#11@20", text, fixed = TRUE) && grepl("c1#10@0", text, fixed = TRUE))
  }
  binary_data <- long_data[, seq_len(14L)]
  binary_data[] <- lapply(binary_data, function(x) rep(0:1, 8L))
  binary <- ch7_mixture_object(binary_data, "lpa", waves = list(names(binary_data)),
    categorical = names(binary_data), classes = 12L)
  binary_text <- compile("lca_long_k12", binary)
  check("lca_long_threshold_tokens_preserved", all(vapply(paste0(names(binary_data), "$1"),
    function(v) grepl(v, binary_text, fixed = TRUE), logical(1))))
  nominal <- as.data.frame(setNames(rep(list(rep(seq_len(12L), length.out = 16L)), 4L),
    paste0("nominal", seq_len(4L))))
  logits <- matrix(seq_len(132L) / 13 - 5, nrow = 12L, ncol = 11L)
  for (family in c("lta", "mslta")) {
    built <- ch7_mixture_object(nominal, family, classes = 12L, transitions = TRUE,
      step3 = list(nominal = names(nominal), logits = logits))
    text <- compile(paste0(family, "_step3_k12"), built)
    expected <- paste0("[nominal4#11@", sprintf("%.12f", logits[12L, 11L]), "];")
    check(paste0(family, ":step3_fixed_value_preserved"), grepl(expected, text, fixed = TRUE))
    check(paste0(family, ":step3_transitions_retained"), grepl("c4 ON c3;", text, fixed = TRUE))
    reject(paste0(family, ":step3_without_transitions_rejected"),
      ch7_mixture_object(nominal, family, classes = 12L, transitions = FALSE,
        step3 = list(nominal = names(nominal), logits = logits)))
  }

  # 白盒以外再核最终 token 序列：换行不改变量、固定值、标签或引号内空格。
  long_statement <- paste0("[", paste(sprintf("v%07d@-1.234567890123", 1:8), collapse = " "), "] (label1);")
  wrapped <- ch7_wrap_mplus_lines(long_statement)
  check("wrap_fixed_tokens_and_labels_exact", identical(gsub("\n", " ", wrapped, fixed = TRUE), long_statement))
  quoted <- paste(paste(rep("TECH1;", 12L), collapse = " "), 'FILE = "folder with spaces/result.dat";')
  quoted_wrapped <- ch7_wrap_mplus_lines(quoted)
  check("wrap_quoted_path_exact", grepl('"folder with spaces/result.dat"', quoted_wrapped, fixed = TRUE) &&
    identical(gsub("\n", " ", quoted_wrapped, fixed = TRUE), quoted))
  commented <- paste(paste(rep("TECH1;", 12L), collapse = " "), "! keep comment whole")
  check("wrap_comment_stays_comment", grepl("! keep comment whole", ch7_wrap_mplus_lines(commented), fixed = TRUE))
  reject("unbreakable_token_rejected", ch7_wrap_mplus_lines(paste(rep("x", 91L), collapse = "")))
  reject("unbreakable_comment_rejected", ch7_wrap_mplus_lines(paste0("!", paste(rep("x", 91L), collapse = ""))))
  invalid <- file.path(output_dir, "overlong_negative.inp")
  writeLines(paste(rep("x", 91L), collapse = ""), invalid)
  reject("actual_overlong_input_rejected", ch7_validate_input_width(invalid), "exceeds 90 bytes")
  check("no_native_outputs", !length(list.files(output_dir, pattern = "\\.(out|gh5)$", recursive = TRUE)))
  receipt <- list(status = "PASS_SYNTHETIC_SYNTAX_BOUNDARIES", checks = checks,
    compiled_inputs = length(artifacts), artifacts = artifacts, engine_calls = 0L,
    native_acceptance = FALSE, research_data_read = FALSE)
  jsonlite::write_json(receipt, file.path(output_dir, "receipt.json"), auto_unbox = TRUE, pretty = TRUE)
  cat("CH7_SYNTAX_BOUNDARIES_PASS", length(checks), "checks; engine_calls=0\n")
  invisible(receipt)
}

if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) != 1L) stop("Usage: Rscript test_ch7_syntax_boundaries_20261113.R <fresh-output-dir>")
  file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
  test_ch7_syntax_boundaries_20261113(args[[1]],
    file.path(dirname(sub("^--file=", "", file_arg[[1]])), ".."))
}
