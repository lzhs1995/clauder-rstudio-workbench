# 合成输出/固定宽度存盘 → 自动解析 → mplusObject → INP/DAT 的离线验收；Mplus 调用数为零。
test_ch7_step_chain_20261111 <- function(output_dir, skill_root) {
  for (pkg in c("MplusAutomation", "digest", "jsonlite")) if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
  if (file.exists(output_dir)) stop("Fresh output directory required")
  dir.create(output_dir, recursive = TRUE); output_dir <- normalizePath(output_dir, winslash = "/")
  for (f in c("ch7_mixture_tools.R", "ch7_mixture_syntax.R", "ch7_step_chain_20261111.R"))
    source(file.path(skill_root, "scripts", f), local = TRUE)
  checks <- list()
  check <- function(name, value) { if (!isTRUE(value)) stop("Contract failed: ", name); checks[[name]] <<- TRUE }
  reject <- function(name, expression) check(name, inherits(tryCatch(force(expression), error = identity), "error"))
  ns <- asNamespace("MplusAutomation")
  for (f in c("runModels", "detectMplus")) trace(f, tracer = quote(stop("ENGINE_CALL_FORBIDDEN_SYNTHETIC_CHAIN")), print = FALSE, where = ns)
  on.exit(for (f in c("runModels", "detectMplus")) untrace(f, where = ns), add = TRUE)
  msg <- tryCatch(MplusAutomation::runModels(), error = conditionMessage)
  check("engine_guard_is_active", identical(msg, "ENGINE_CALL_FORBIDDEN_SYNTHETIC_CHAIN"))

  fixture <- function(name, K = 3L, waves = 2L, save_first = TRUE, split_columns = FALSE) {
    root <- file.path(output_dir, name); dir.create(root)
    latent <- paste0("v", seq_len(waves)); z <- matrix(seq_len(K * (K - 1L)) / 5 - 2, K, K - 1L)
    z[1, 1] <- 14 # 打印概率可为零，仍须直接保留有限 logit。
    full <- cbind(z, 0); p <- exp(full - apply(full, 1L, max)); p <- p / rowSums(p)
    table <- function(x) {
      groups <- if (split_columns) split(seq_len(K), ceiling(seq_len(K) / 2)) else list(seq_len(K))
      unlist(lapply(groups, function(columns) c("", paste(columns, collapse = "  "), "",
        vapply(seq_len(K), function(row) paste(row, paste(sprintf("%.3f", x[row, columns]), collapse = "  ")), ""))))
    }
    text <- c("Mplus VERSION 8.10", "INPUT INSTRUCTIONS", "VARIABLE:",
      paste0("CLASSES = ", paste0(latent, "(", K, ")", collapse = " "), ";"), "IDVARIABLE = SID;",
      "INPUT READING TERMINATED NORMALLY", "THE MODEL ESTIMATION TERMINATED NORMALLY")
    for (v in latent) text <- c(text, paste("Classification Quality for", toupper(v)), "",
      "Average Latent Class Probabilities for Most Likely Latent Class Membership (Row)", "by Latent Class (Column)",
      table(t(p)), "",
      "Classification Probabilities for the Most Likely Latent Class Membership (Column)", "by Latent Class (Row)", table(p), "",
      "Logits for the Classification Probabilities for the Most Likely Latent Class Membership (Column)",
      "by Latent Class (Row)", table(full), "")
    text <- c(text, "MODEL RESULTS", "")
    d <- data.frame(SID = seq_len(K * 4L), VALUE = -(seq_len(K * 4L) + .125))
    for (wave in seq_len(waves)) d[[paste0("MLCC", wave)]] <- rep(seq_len(K), 4L)
    formats <- c("F12.0", "F10.3", rep("F10.3", waves))
    rows <- paste(names(d), formats)
    sections <- list(c("  Save file", "    posterior.dat", ""), c("  Order and format of variables", "", rows, ""))
    text <- c(text, "SAVEDATA INFORMATION", "", unlist(sections[if (save_first) c(1, 2) else c(2, 1)]),
      "  Save file format", "    synthetic fixture", "", "  Save missing symbol        *")
    path <- file.path(root, "step1.out"); writeLines(text, path)
    saved <- file.path(root, "posterior.dat")
    formatted <- vapply(seq_len(nrow(d)), function(i) paste0(sprintf("%12.0f", d$SID[i]),
      paste(sprintf("%10.3f", as.numeric(d[i, -1])), collapse = "")), "")
    writeLines(formatted, saved)
    list(root = root, out = path, saved = saved, text = text, data = d, logits = z,
         latent = latent, K = K, nominal_map = stats::setNames(paste0("MLCC", seq_len(waves)), paste0("n", seq_len(waves))))
  }
  build <- function(f, family = "lta", ...) ch7_step3_from_step1(f$out, f$saved, id = "SID", nominal_map = f$nominal_map,
    latent = f$latent, classes = f$K, family = family, keep = "VALUE", ...)
  compile <- function(chain, folder) {
    dir.create(folder); old <- getwd(); on.exit(setwd(old), add = TRUE); setwd(folder)
    MplusAutomation::mplusModeler(chain$object, modelout = "model.inp", dataout = "data.dat", run = 0L,
      check = FALSE, hashfilename = FALSE, writeData = "always", quiet = TRUE,
      Mplus_command = "FORBIDDEN_IN_SYNTHETIC_CHAIN", killOnFail = FALSE)
    file.path(folder, "model.inp")
  }
  for (K in 2:4) {
    f <- fixture(paste0("k", K), K, if (K == 4L) 4L else 2L, save_first = K != 3L, split_columns = K == 4L)
    chain <- build(f)
    check(paste0("extract_direct_logits_k", K), all(vapply(chain$step3$logits,
      function(z) isTRUE(all.equal(unname(z), unname(f$logits))), logical(1))))
    check(paste0("fixed_width_savedata_k", K), identical(chain$data$VALUE, f$data$VALUE))
    check(paste0("id_and_nominal_names_k", K), identical(names(chain$data), c("SID", "VALUE", names(f$nominal_map))))
    check(paste0("reference_and_direction_k", K), all(vapply(chain$lineage$source$tables,
      function(x) x$reference_class == K && grepl("rows=latent; columns=assigned", x$direction, fixed = TRUE), logical(1))))
    inp <- compile(chain, file.path(f$root, "compiled"))
    receipt <- ch7_step3_chain_receipt(chain, inp)
    check(paste0("compiled_lineage_k", K), identical(receipt$status, "PASS_COMPILED_LINEAGE") && !receipt$engine_estimated &&
      receipt$logit_cells == length(f$latent) * K * (K - 1L))
    check(paste0("receipt_has_no_values_or_paths_k", K),
      !grepl(output_dir, jsonlite::toJSON(receipt, auto_unbox = TRUE), fixed = TRUE) && is.null(receipt$data))
  }
  f <- fixture("negative_controls", 3L, 2L); baseline <- f$text
  mutate <- function(name, fn, call = function() ch7_classification_error(f$out, f$latent, f$K)) {
    writeLines(fn(baseline), f$out)
    on.exit(writeLines(baseline, f$out), add = TRUE)
    reject(name, call())
  }
  mutate("reject_abnormal_termination", function(x) sub("THE MODEL ESTIMATION TERMINATED NORMALLY", "ABNORMAL TERMINATION", x))
  mutate("reject_duplicate_scope", function(x) c(x, "Classification Quality for V1"))
  mutate("reject_missing_wave", function(x) sub("Classification Quality for V2", "Classification Quality for V3", x))
  mutate("reject_wrong_class_count", function(x) sub("v1(3)", "v1(4)", x, fixed = TRUE))
  mutate("reject_wrong_orientation", function(x) sub("by Latent Class (Row)", "by Latent Class (Column)", x, fixed = TRUE))
  mutate("reject_conflicting_probability", function(x) {
    at <- which(x == "Classification Probabilities for the Most Likely Latent Class Membership (Column)")[1]
    row <- at + which(grepl("^1 [+-]?[0-9]+[.]", x[(at + 1L):length(x)]))[1]
    x[row] <- "1 0.333 0.333 0.334"; x
  })
  mutate("reject_nonzero_reference", function(x) {
    at <- which(grepl("^Logits for", x))[1]
    row <- at + which(grepl("^1 [+-]?[0-9]+[.]", x[(at + 1L):length(x)]))[1]
    x[row] <- sub("0.000$", "1.000", x[row]); x
  })
  mutate("reject_nonfinite_logit", function(x) {
    at <- which(grepl("^Logits for", x))[1]
    row <- at + which(grepl("^1 [+-]?[0-9]+[.]", x[(at + 1L):length(x)]))[1]
    x[row] <- sub("14.000", "********", x[row], fixed = TRUE); x
  })
  mutate("reject_missing_class_row", function(x) {
    at <- which(grepl("^Logits for", x))[1]
    row <- at + which(grepl("^3 [+-]?[0-9]+[.]", x[(at + 1L):length(x)]))[1]
    x[-row]
  })
  mutate("reject_duplicate_cell", function(x) {
    at <- which(grepl("^Logits for", x))[1]
    row <- at + which(grepl("^1 [+-]?[0-9]+[.]", x[(at + 1L):length(x)]))[1]
    append(x, x[row], after = row)
  })
  mutate("reject_wrong_savedata_declaration", function(x) sub("posterior.dat", "missing.dat", x, fixed = TRUE), function() build(f))
  mutate("reject_duplicate_savedata_section", function(x) c(x, "SAVEDATA INFORMATION"), function() build(f))
  mutate("reject_wrong_id_declaration", function(x) sub("IDVARIABLE = SID", "IDVARIABLE = VALUE", x, fixed = TRUE), function() build(f))
  # N4：缺失符号来自 Step-1 SAVEDATA INFORMATION，不能固定假设 * 或 .。
  missing_fixture <- fixture("declared_missing_symbol", 2L, 2L)
  missing_text <- sub("Save missing symbol        *", "Save missing symbol        -999", missing_fixture$text, fixed = TRUE)
  writeLines(missing_text, missing_fixture$out)
  missing_rows <- readLines(missing_fixture$saved)
  missing_rows[1L] <- paste0(substr(missing_rows[1L], 1L, 12L), sprintf("%10s", "-999"), substr(missing_rows[1L], 23L, nchar(missing_rows[1L])))
  writeLines(missing_rows, missing_fixture$saved)
  missing_chain <- build(missing_fixture)
  check("declared_numeric_missing_symbol_bound", is.na(missing_chain$data$VALUE[1L]) &&
    identical(missing_chain$lineage$savedata$missing_symbol, "-999"))
  # 不接受未声明的另一种字符缺失符号；数值 marker 则允许合法 F/E/D 格式。
  mismatch_rows <- missing_rows; mismatch_rows[1L] <- sub("-999", "*", mismatch_rows[1L], fixed = TRUE)
  writeLines(mismatch_rows, missing_fixture$saved)
  reject("reject_savedata_missing_symbol_mismatch", build(missing_fixture))
  numeric_rows <- missing_rows
  numeric_rows[1L] <- paste0(substr(missing_rows[1L], 1L, 12L), sprintf("%10.3f", -999),
    substr(missing_rows[1L], 23L, nchar(missing_rows[1L])))
  writeLines(numeric_rows, missing_fixture$saved)
  numeric_chain <- build(missing_fixture)
  check("numeric_missing_marker_fixed_format", is.na(numeric_chain$data$VALUE[1L]))
  numeric_compiled <- compile(numeric_chain, file.path(missing_fixture$root, "compiled_numeric_missing"))
  check("numeric_missing_marker_compiled_roundtrip",
    identical(ch7_step3_chain_receipt(numeric_chain, numeric_compiled)$status, "PASS_COMPILED_LINEAGE"))
  check("numeric_missing_marker_exact_decimal_equivalence",
    identical(ch7_savedata_missing(c("-999", "-999.000", "-9.99E2", "-9.99D2", "-999.00000000000000001"), "-999"),
      c(TRUE, TRUE, TRUE, TRUE, FALSE)))
  check("shared_savedata_parser_exposes_missing_symbol",
    identical(ch7_savedata_info(missing_text)$missing_symbol, "-999"))
  reject("reject_duplicate_missing_symbol_declaration", {
    writeLines(c(missing_text, " Save missing symbol -999"), missing_fixture$out)
    build(missing_fixture)
  })
  writeLines(missing_text, missing_fixture$out)
  writeLines(missing_rows, missing_fixture$saved)
  reject("reject_missing_symbol_declaration_absent", {
    writeLines(missing_text[!grepl("Save missing symbol", missing_text, fixed = TRUE)], missing_fixture$out)
    build(missing_fixture)
  })
  writeLines(missing_text, missing_fixture$out)
  dot_text <- sub("Save missing symbol        -999", "Save missing symbol        .", missing_text, fixed = TRUE)
  writeLines(dot_text, missing_fixture$out)
  dot_rows <- missing_rows; dot_rows[1L] <- sub("-999", ".", dot_rows[1L], fixed = TRUE)
  writeLines(dot_rows, missing_fixture$saved)
  dot_chain <- build(missing_fixture)
  check("declared_dot_missing_symbol_bound", is.na(dot_chain$data$VALUE[1L]) &&
    identical(dot_chain$lineage$savedata$missing_symbol, "."))
  writeLines(missing_text, missing_fixture$out); writeLines(missing_rows, missing_fixture$saved)
  writeLines(sub("INPUT READING TERMINATED NORMALLY", "SUMMARY OF ANALYSIS", baseline), f$out)
  check("supports_summary_input_boundary", length(build(f)$step3$logits) == 2L)
  writeLines(baseline, f$out)
  reject("reject_latent_order_with_wrong_mlcc", ch7_step3_from_step1(f$out, f$saved, id = "SID", nominal_map = f$nominal_map,
    latent = rev(f$latent), classes = f$K))
  saved_base <- readLines(f$saved)
  writeLines(c(saved_base[1], saved_base[1], saved_base[-c(1, 2)]), f$saved)
  reject("reject_duplicate_ids", build(f)); writeLines(saved_base, f$saved)
  writeLines(sub("^.{12}", "           *", saved_base), f$saved)
  reject("reject_missing_ids", build(f)); writeLines(saved_base, f$saved)
  # R2：在原始固定宽度 ID 上复现边界与舍入负例，不能让 as.numeric 先抹掉小数或越界。
  wide <- fixture("exact_savedata_ids", 2L, 2L)
  writeLines(sub("F12.0", "F24.0", wide$text, fixed = TRUE), wide$out)
  narrow_rows <- readLines(wide$saved)
  wide_rows <- paste0(sprintf("%24s", trimws(substr(narrow_rows, 1L, 12L))),
    substr(narrow_rows, 13L, nchar(narrow_rows)))
  id_case <- function(token) {
    rows <- wide_rows
    rows[1L] <- paste0(sprintf("%24s", token), substr(narrow_rows[1L], 13L, nchar(narrow_rows[1L])))
    writeLines(rows, wide$saved)
    build(wide)
  }
  valid_ids <- c(upper = "9007199254740992", upper_minus_one = "9007199254740991",
    lower = "-9007199254740992", decimal_zero_tail = "9007199254740992.000",
    exponent = "9.007199254740992D15", integer_exponent = "+00100E-1", negative_zero = "-0.000")
  expected_ids <- c(2^53, 2^53 - 1, -2^53, 2^53, 2^53, 10, 0)
  for (i in seq_along(valid_ids)) check(paste0("savedata_exact_id_", names(valid_ids)[i]),
    identical(id_case(valid_ids[i])$data$SID[1L], expected_ids[i]))
  invalid_ids <- c(above_range = "9007199254740993", below_range = "-9007199254740993",
    rounded_fraction = "1.00000000000000001", fractional_exponent = "100000000000000001E-17",
    tiny_fraction = "1E-9999", huge_exponent = "1E9999", nondecimal = "0x10")
  for (i in seq_along(invalid_ids)) reject(paste0("reject_savedata_id_", names(invalid_ids)[i]), id_case(invalid_ids[i]))
  reject("reject_savedata_normalized_duplicate", id_case("2.000D0"))
  # 同样的严格整数合同适用于自由格式存盘。
  writeLines(c("9007199254740993 -1.125 1 1", "2 -2.125 2 2"), wide$saved)
  reject("reject_free_format_rounded_id", build(wide))
  other <- file.path(f$root, "other"); dir.create(other); file.copy(f$saved, other)
  reject("reject_same_name_other_path", ch7_step3_from_step1(f$out, file.path(other, "posterior.dat"), id = "SID",
    nominal_map = f$nominal_map, latent = f$latent, classes = f$K))
  ms <- build(f, family = "mslta"); inp <- compile(ms, file.path(f$root, "ms_compiled"))
  check("ms_lta_compiled_chain", ch7_step3_chain_receipt(ms, inp)$status == "PASS_COMPILED_LINEAGE")
  inp_base <- readLines(inp)
  # R1：数据和固定logit不变时，额外输入变换仍必须被拒；保留注释说明的正例。
  insert_at <- grep("^ANALYSIS:", inp_base)[1L] - 1L
  for (variant in c("DEFINE:\n n1 = 1;", "defi: n1 = 1;", "OUTPUT: TECH1; DEFINE: n1 = 1;")) {
    writeLines(append(inp_base, variant, after = insert_at), inp)
    reject(paste0("reject_step3_define_variant_", match(variant, c("DEFINE:\n n1 = 1;", "defi: n1 = 1;", "OUTPUT: TECH1; DEFINE: n1 = 1;"))),
      ch7_step3_chain_receipt(ms, inp))
  }
  writeLines(append(inp_base, "! DEFINE: n1 = 1; is not an active statement", after = insert_at), inp)
  check("define_in_comment_is_not_a_transform", ch7_step3_chain_receipt(ms, inp)$status == "PASS_COMPILED_LINEAGE")
  writeLines(inp_base, inp)
  writeLines(sub("c1(3)", "c1(4)", inp_base, fixed = TRUE), inp)
  reject("reject_step3_wrong_classes", ch7_step3_chain_receipt(ms, inp)); writeLines(inp_base, inp)
  writeLines(sub("n1#1@14.000000000000", "n1#1@13.000000000000", inp_base, fixed = TRUE), inp)
  reject("reject_modified_fixed_logit", ch7_step3_chain_receipt(ms, inp)); writeLines(inp_base, inp)
  writeLines(sub("MODEL c1:", "MODEL c4:", inp_base, fixed = TRUE), inp)
  reject("reject_logit_wrong_namespace", ch7_step3_chain_receipt(ms, inp)); writeLines(inp_base, inp)
  writeLines(c(baseline, "changed source"), f$out)
  reject("reject_step1_changed_after_build", ch7_step3_chain_receipt(ms, inp)); writeLines(baseline, f$out)
  dat <- file.path(dirname(inp), "data.dat"); d <- utils::read.table(dat, header = FALSE)
  dat_base <- readLines(dat)
  writeLines(sub("^[^[:space:]]+", "1.00000000000000001", dat_base), dat)
  reject("reject_step3_dat_rounded_id", ch7_step3_chain_receipt(ms, inp))
  writeLines(dat_base, dat)
  utils::write.table(d[rev(seq_len(nrow(d))), ], dat, row.names = FALSE, col.names = FALSE)
  check("rows_compared_by_id", !ch7_step3_chain_receipt(ms, inp)$row_order_identical)
  d[1, 2] <- d[1, 2] + 1
  utils::write.table(d, dat, row.names = FALSE, col.names = FALSE)
  reject("reject_modified_projection", ch7_step3_chain_receipt(ms, inp))
  manifest <- list(test = "ch7_step_chain_20261111", status = "PASS_SYNTHETIC_GENERATION_AND_PARSE",
    native_fresh_chain = "NOT_RUN", mplus_calls = 0L, checks = names(checks))
  jsonlite::write_json(manifest, file.path(output_dir, "ch7_step_chain_manifest.json"), auto_unbox = TRUE, pretty = TRUE)
  cat("CH7_STEP_CHAIN_PASS", length(checks), "checks; Mplus calls: 0\n")
  invisible(manifest)
}
