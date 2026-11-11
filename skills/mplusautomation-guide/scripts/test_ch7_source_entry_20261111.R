# 统一换源入口的合成测试：实际编译 INP/DAT，禁止任何 Mplus 调用。
test_ch7_source_entry_20261111 <- function(output_dir, skill_root) {
  for (p in c("MplusAutomation", "digest", "jsonlite")) if (!requireNamespace(p, quietly = TRUE)) stop("Missing package: ", p)
  if (file.exists(output_dir)) stop("Fresh output directory required")
  dir.create(output_dir, recursive = TRUE); output_dir <- normalizePath(output_dir, winslash = "/")
  source(file.path(skill_root, "scripts/ch7_source_entry_20261111.R"), local = TRUE)
  source(file.path(skill_root, "scripts/ch7_native_fixture_20261111.R"), local = TRUE)
  checks <- list()
  check <- function(name, ok) { if (!isTRUE(ok)) stop("Contract failed: ", name); checks[[name]] <<- TRUE }
  reject <- function(name, expression) check(name, inherits(tryCatch(force(expression), error = identity), "error"))
  sha <- function(p) digest::digest(p, algo = "sha256", file = TRUE)
  ns <- asNamespace("MplusAutomation")
  for (f in c("runModels", "detectMplus")) trace(f, tracer = quote(stop("ENGINE_FORBIDDEN_SOURCE_ENTRY_TEST")), print = FALSE, where = ns)
  on.exit(for (f in c("runModels", "detectMplus")) untrace(f, where = ns), add = TRUE)
  for (f in c("runModels", "detectMplus")) check(paste0("guard_", f), identical(
    tryCatch(get(f, ns)(), error = conditionMessage), "ENGINE_FORBIDDEN_SOURCE_ENTRY_TEST"))
  invalid_seeds <- list(NA_real_, Inf, -1, 0, 1.5, 2147483648, c(1, 2))
  for (i in seq_along(invalid_seeds)) {
    target <- file.path(output_dir, paste0("invalid_fixture_seed_", i))
    check(paste0("fixture_seed_rejected_before_write_", i),
      inherits(tryCatch(ch7_native_fixture(target, seed = invalid_seeds[[i]]), error = identity), "error") &&
        !file.exists(target))
  }
  # 全部值是确定性的合成数据；不依赖论文估计值、个人记录或本机固定目录。
  d <- data.frame(person_key = seq_len(48L))
  mapping <- list()
  for (w in 1:4) for (role in c("signal", "binary", "extra")) {
    n <- paste0("wave_", w, "_", role)
    d[[n]] <- if (role == "binary") (seq_len(48L) + w) %% 2L else
      sin(seq_len(48L) * .17 + w) + if (role == "extra") .4 else 0
    mapping[[length(mapping) + 1L]] <- list(wave = paste0("w", w), role = role, source = n,
      target = paste0("v", w, substr(role, 1L, 1L)),
      type = if (role == "binary") "categorical" else "continuous", scale = "synthetic_untransformed")
  }
  write_source <- function(data, name) {
    path <- file.path(output_dir, paste0(name, ".csv")); utils::write.csv(data, path, row.names = FALSE, na = "")
    list(path = path, sha256 = sha(path), format = "csv", encoding = "UTF-8", id = "person_key",
      row_grain = "person_wide", missing_codes = numeric())
  }
  model <- function(id, family = "lta", waves = paste0("w", 1:4), roles = c("signal", "binary"), k = 2L)
    list(id = id, family = family, wave_ids = waves, roles = roles, classes = k,
      invariant = TRUE, starts = "20 5", estimator = "MLR", processors = 1L, seed = 71111L)
  cfg <- list(schema_version = 1L, mode = "new_source", source = write_source(d, "source"),
    sample = list(rule = "all_rows", row_order = "source"),
    transformations = list(status = "none", description = "Synthetic scale fixed before entry"),
    waves = lapply(1:4, function(w) list(wave = paste0("w", w), label = paste("Wave", w), time = w * 2)),
    mapping = mapping, id_target = "sid", models = list(model("base")))
  prepare <- function(c, name) ch7_source_entry(c, file.path(output_dir, name), skill_root)
  inp <- function(result, id = names(result$models)[1L]) paste(readLines(result$models[[id]]$input, warn = FALSE), collapse = "\n")
  dat <- function(result, id = names(result$models)[1L]) utils::read.table(result$models[[id]]$data, na.strings = ".")
  base <- prepare(cfg, "base")
  check("compile_state", base$manifest$status == "PREPARED_NO_ENGINE" && base$manifest$engine_calls == 0L)
  check("names_dat_order", identical(as.numeric(dat(base)[, 1L]), as.numeric(d$person_key)) && ncol(dat(base)) == 9L)
  check("idvariable_present", grepl("IDVARIABLE = sid;", inp(base), fixed = TRUE))
  check("seed_preserved", grepl("STSEED = 71111;", inp(base), fixed = TRUE))
  check("four_wave_syntax", grepl("CLASSES = c1(2) c2(2) c3(2) c4(2);", inp(base), fixed = TRUE))
  check("no_absolute_manifest_path", !grepl(output_dir, paste(readLines(file.path(base$output_dir, "manifest.json")), collapse = ""), fixed = TRUE))

  c <- cfg; c$source <- write_source(d, "same_values_new_source"); same <- prepare(c, "same_values")
  check("same_values_source_swap", identical(sha(base$models$base$data), sha(same$models$base$data)))
  d2 <- d; d2$wave_1_signal <- d2$wave_1_signal + .5
  c <- cfg; c$source <- write_source(d2, "changed_values"); changed <- prepare(c, "changed")
  check("changed_source_changes_dat", sha(base$models$base$data) != sha(changed$models$base$data))
  check("changed_source_changes_provenance", base$manifest$source_sha256 != changed$manifest$source_sha256)
  # 换名与输入列序变化后映射回同一模型角色；输出列序仍由合同确定。
  renamed <- d[, rev(names(d))]; old <- names(renamed); names(renamed) <- paste0("new_", old)
  c <- cfg; c$source <- write_source(renamed, "renamed_reordered"); c$source$id <- "new_person_key"
  c$mapping <- lapply(c$mapping, function(m) { m$source <- paste0("new_", m$source); m })
  rename <- prepare(c, "rename")
  check("rename_dat_equal", identical(sha(base$models$base$data), sha(rename$models$base$data)))
  check("rename_inp_equal", identical(inp(base), inp(rename)))
  c <- cfg; c$mapping <- lapply(c$mapping, function(m) { m$target <- paste0("z", substring(m$target, 2L)); m })
  new_names <- prepare(c, "target_names")
  check("new_target_names", grepl("z1s", inp(new_names), fixed = TRUE) && !grepl("v1s", inp(new_names), fixed = TRUE))
  check("new_target_values_equal", identical(dat(new_names), dat(base)))

  c <- cfg; c$models <- list(model("two_wave", waves = c("w1", "w3")), model("three_wave", waves = c("w1", "w2", "w4")),
    model("k3", k = 3L), model("continuous", "lpa", "w1", c("signal", "extra")),
    model("binary", "lpa", "w1", "binary"), model("k1", "lpa", "w1", "signal", 1L), model("mslta", "mslta"))
  combos <- prepare(c, "combinations")
  check("two_waves", grepl("CLASSES = c1(2) c2(2);", inp(combos, "two_wave"), fixed = TRUE))
  check("three_waves", grepl("CLASSES = c1(2) c2(2) c3(2);", inp(combos, "three_wave"), fixed = TRUE))
  check("k3", grepl("CLASSES = c1(3) c2(3) c3(3) c4(3);", inp(combos, "k3"), fixed = TRUE))
  check("continuous_combination", !grepl("CATEGORICAL", inp(combos, "continuous"), fixed = TRUE) && grepl("v1e", inp(combos, "continuous"), fixed = TRUE))
  check("binary_combination", grepl("CATEGORICAL = v1b;", inp(combos, "binary"), fixed = TRUE))
  check("k1", grepl("CLASSES = c(1);", inp(combos, "k1"), fixed = TRUE))
  check("mslta", grepl("CLASSES = g(2)", inp(combos, "mslta"), fixed = TRUE) && grepl("%g#2%", inp(combos, "mslta"), fixed = TRUE))
  c <- cfg; c$models[[1L]]$invariant <- FALSE; free <- prepare(c, "free_measurement")
  check("explicit_free_measurement", grepl("(w1k1i1)", inp(free), fixed = TRUE) && grepl("(w4k1i1)", inp(free), fixed = TRUE))
  c <- cfg; dm <- d; dm$wave_1_signal[2L] <- -999
  c$source <- write_source(dm, "missing_code"); c$source$missing_codes <- -999
  missing <- prepare(c, "missing"); check("missing_code_recode", is.na(dat(missing)[2L, 2L]) && nrow(dat(missing)) == nrow(d))
  json <- file.path(output_dir, "config.json"); jsonlite::write_json(cfg, json, auto_unbox = TRUE, pretty = TRUE)
  from_json <- prepare(json, "json_config")
  check("json_api_equal", identical(inp(base), inp(from_json)) && identical(dat(base), dat(from_json)))

  reject("reject_existing_output", prepare(cfg, "base"))
  invalid <- function(name, mutate) { c <- mutate(cfg); reject(name, prepare(c, paste0("rejected_", name))) }
  invalid("wrong_sha", function(c) { c$source$sha256 <- paste(rep("0", 64L), collapse = ""); c })
  invalid("reverse_waves", function(c) { c$models[[1L]]$wave_ids <- c("w3", "w1"); c })
  invalid("duplicate_wave", function(c) { c$models[[1L]]$wave_ids <- c("w1", "w1"); c })
  invalid("unknown_role", function(c) { c$models[[1L]]$roles <- "unknown"; c })
  invalid("missing_column", function(c) { c$mapping[[1L]]$source <- "absent"; c })
  invalid("duplicate_target", function(c) { c$mapping[[2L]]$target <- c$mapping[[1L]]$target; c })
  invalid("implicit_transform", function(c) { c$transformations$status <- "auto_scale"; c })
  invalid("implicit_subset", function(c) { c$sample$rule <- "complete_cases"; c })
  invalid("unknown_model_option", function(c) { c$models[[1L]]$typo_seed <- 99; c })
  invalid("unused_mode_fields", function(c) { c$step1 <- list(out = "unexpected"); c })
  invalid("unavailable_wave_mapping", function(c) { c$mapping[[1L]]$wave <- "w9"; c })
  bad_source <- function(name, mutate) {
    c <- cfg; c$source <- write_source(mutate(d), paste0("bad_", name)); reject(name, prepare(c, paste0("rejected_", name)))
  }
  bad_source("duplicate_id", function(x) { x$person_key[2L] <- x$person_key[1L]; x })
  bad_source("fractional_id", function(x) { x$person_key[1L] <- 1.5; x })
  bad_source("missing_id", function(x) { x$person_key[1L] <- NA; x })
  bad_source("unrepresentable_integer_literal", function(x) { x$person_key <- as.character(x$person_key); x$person_key[1L] <- "9007199254740993"; x })
  bad_source("fraction_rounded_to_integer", function(x) { x$person_key <- as.character(x$person_key); x$person_key[1L] <- "1.00000000000000001"; x })
  bad_source("scientific_id_ambiguous", function(x) { x$person_key <- as.character(x$person_key); x$person_key[1L] <- "1e0"; x })
  bad_source("non_binary", function(x) { x$wave_1_binary[1L] <- 2L; x })
  bad_source("string_indicator", function(x) { x$wave_1_signal[1L] <- "oops"; x })
  bad_source("nonfinite_indicator", function(x) { x$wave_1_signal[1L] <- Inf; x })
  bad_source("all_missing", function(x) { x$wave_1_signal <- NA_real_; x })
  if (requireNamespace("haven", quietly = TRUE)) {
    c <- cfg; path <- file.path(output_dir, "source.dta"); haven::write_dta(d, path)
    c$source$path <- path; c$source$sha256 <- sha(path); c$source$format <- "dta"
    # write.csv 的显示精度可能低于 DTA 原 double；格式比较容许该已知舍入，DTA 输入另做逐位检查。
    stata <- prepare(c, "stata_source"); check("dta_same_values", max(abs(as.matrix(dat(base)) - as.matrix(dat(stata)))) < 1e-14)
    precision <- 0.12345678901234567
    check("numeric_input_bitwise_preserved", identical(ch7_entry_numeric(precision, numeric(), "synthetic"), precision))
    c <- cfg; dd <- d; dd$wave_1_signal[1L] <- precision
    path <- file.path(output_dir, "precision_source.dta"); haven::write_dta(dd, path)
    c$source$path <- path; c$source$sha256 <- sha(path); c$source$format <- "dta"
    check("dta_adapter_preserves_double", identical(ch7_entry_read_source(c)$data$v1s[1L], precision))
  }

  # 归档模拟保留原有十核、注释、CRLF 和其他字节，只替换两个 FILE 值。
  archived <- paste(c("TITLE: synthetic replay", "DATA:", ' FILE = "old source.dat"; ! data comment',
    "VARIABLE:", " NAMES = sid n1 n2;", " NOMINAL = n1 n2;", " CLASSES = c1(2) c2(2);",
    "ANALYSIS:", " TYPE = MIXTURE; STARTS = 0; PROCESSORS = 10;", "MODEL:",
    " %OVERALL%", " c2 ON c1;", "SAVEDATA:", ' FILE = "old posterior.dat"; ! saved comment',
    " SAVE = CPROBABILITIES;", ""), collapse = "\r\n")
  old_inp <- file.path(output_dir, "archive.inp"); old_dat <- file.path(output_dir, "archive.dat")
  writeBin(charToRaw(archived), old_inp); writeLines(c("1 1 2", "2 2 1"), old_dat)
  replay_cfg <- list(schema_version = 1L, mode = "historical_replay", models = list(list(id = "replay",
    inp = old_inp, inp_sha256 = sha(old_inp), dat = old_dat, dat_sha256 = sha(old_dat))))
  replay <- prepare(replay_cfg, "replay")
  expected <- sub('"old source.dat"', '"source.dat"', archived, fixed = TRUE)
  expected <- sub('"old posterior.dat"', '"posterior.dat"', expected, fixed = TRUE)
  actual <- readBin(replay$models$replay$input, "raw", n = file.info(replay$models$replay$input)$size)
  check("replay_exact_nonpath_bytes", identical(actual, charToRaw(expected)))
  check("replay_dat_identity", identical(sha(old_dat), sha(replay$models$replay$data)))
  check("replay_does_not_change_processors", grepl("PROCESSORS = 10", rawToChar(actual), fixed = TRUE))
  reject("replay_duplicate_file", ch7_entry_replay_paths(sub('FILE = "old source.dat";', 'FILE = "x"; FILE = "y";', archived, fixed = TRUE)))
  reject("replay_other_output_target", ch7_entry_replay_paths(sub("SAVE = CPROBABILITIES;", "SAVE = CPROBABILITIES; RESULTS = outside.txt;", archived, fixed = TRUE)))
  reject("replay_plot_output_target", ch7_entry_replay_paths(paste0(archived, "PLOT:\r\n FILE = outside.txt;\r\n")))
  reject("replay_imputation_list", ch7_entry_replay_paths(sub("DATA:", "DATA:\r\n TYPE = IMPUTATION;", archived, fixed = TRUE)))
  reject("replay_inline_include", ch7_entry_replay_paths(sub("TYPE = MIXTURE;", "TYPE = MIXTURE; INCLUDE = outside.inp;", archived, fixed = TRUE)))
  check("replay_comment_file_ignored", grepl("comment", ch7_entry_replay_paths(sub("data comment", 'data comment FILE = "fake";', archived, fixed = TRUE))$text, fixed = TRUE))

  # 单独的合成 Step-1 输出夹具，验证同入口完成两波 Step-3 编译及其来源哈希。
  step_root <- file.path(output_dir, "synthetic_step1"); dir.create(step_root)
  step_out <- file.path(step_root, "step1.out"); step_dat <- file.path(step_root, "posterior.dat")
  lines <- c("Mplus VERSION 8.10", "INPUT INSTRUCTIONS", "VARIABLE:", "CLASSES = c1(2) c2(2);", "IDVARIABLE = SID;",
    "INPUT READING TERMINATED NORMALLY", "THE MODEL ESTIMATION TERMINATED NORMALLY")
  for (v in c("C1", "C2")) lines <- c(lines, paste("Classification Quality for", v),
    "Classification Probabilities for the Most Likely Latent Class Membership (Column)", "by Latent Class (Row)",
    "", "1 2", "", "1 0.800 0.200", "2 0.300 0.700", "",
    "Logits for the Classification Probabilities for the Most Likely Latent Class Membership (Column)", "by Latent Class (Row)",
    "", "1 2", "", "1 1.386 0.000", "2 -0.847 0.000", "")
  lines <- c(lines, "MODEL RESULTS", "SAVEDATA INFORMATION", "", "  Save file", "    posterior.dat", "",
    "  Order and format of variables", "", "SID F12.0", "MLCC1 F10.3", "MLCC2 F10.3", "",
    "  Save file format", "    synthetic fixture", "", "  Save missing symbol        *")
  writeLines(lines, step_out); writeLines(vapply(1:8, function(i) paste0(sprintf("%12.0f", i),
    sprintf("%10.3f", (i %% 2) + 1), sprintf("%10.3f", ((i + 1) %% 2) + 1)), ""), step_dat)
  step_cfg <- list(schema_version = 1L, mode = "step3_from_output", step1 = list(out = step_out, savedata = step_dat,
    out_sha256 = sha(step_out), savedata_sha256 = sha(step_dat), id = "SID", nominal_map = c(n1 = "MLCC1", n2 = "MLCC2"),
    latent = c("c1", "c2"), classes = 2L), models = list(list(id = "step3", family = "lta", classes = 2L,
    invariant = TRUE, starts = "0", estimator = "MLR", processors = 1L)))
  step <- prepare(step_cfg, "step3")
  check("step3_bound_lineage", step$manifest$artifacts$step3$lineage$status == "PASS_COMPILED_LINEAGE")
  check("step3_direct_logit", grepl("n1#1@1.386", inp(step), fixed = TRUE))
  check("step3_id_preserved", identical(as.numeric(dat(step)[, 1L]), as.numeric(1:8)))
  c <- step_cfg; c$step1$savedata_sha256 <- paste(rep("0", 64L), collapse = "")
  reject("step3_savedata_sha_mismatch", prepare(c, "step3_bad_sha"))
  c <- step_cfg; c$models[[1L]]$classes <- 3L
  reject("step3_k_mismatch", prepare(c, "step3_bad_k"))
  check("no_engine_outputs", length(list.files(output_dir, pattern = "model[.]out$", recursive = TRUE)) == 0L)
  receipt <- list(status = "PASS_SOURCE_ENTRY_SYNTHETIC_COMPILE_ONLY", checks = checks,
    check_count = length(checks), engine_calls = 0L, native_acceptance = FALSE,
    real_data_read = FALSE, R = as.character(getRversion()),
    MplusAutomation = as.character(utils::packageVersion("MplusAutomation")))
  jsonlite::write_json(receipt, file.path(output_dir, "receipt.json"), auto_unbox = TRUE, pretty = TRUE)
  cat("CH7_SOURCE_ENTRY_PASS", length(checks), "checks; engine_calls=0\n")
  invisible(receipt)
}

if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) != 1L) stop("Usage: Rscript test_ch7_source_entry_20261111.R fresh-output-dir")
  file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
  test_ch7_source_entry_20261111(args[[1L]], file.path(dirname(sub("^--file=", "", file_arg[[1L]])), ".."))
}
