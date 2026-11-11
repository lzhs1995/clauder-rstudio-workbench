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
  other <- file.path(f$root, "other"); dir.create(other); file.copy(f$saved, other)
  reject("reject_same_name_other_path", ch7_step3_from_step1(f$out, file.path(other, "posterior.dat"), id = "SID",
    nominal_map = f$nominal_map, latent = f$latent, classes = f$K))
  ms <- build(f, family = "mslta"); inp <- compile(ms, file.path(f$root, "ms_compiled"))
  check("ms_lta_compiled_chain", ch7_step3_chain_receipt(ms, inp)$status == "PASS_COMPILED_LINEAGE")
  inp_base <- readLines(inp)
  writeLines(sub("c1(3)", "c1(4)", inp_base, fixed = TRUE), inp)
  reject("reject_step3_wrong_classes", ch7_step3_chain_receipt(ms, inp)); writeLines(inp_base, inp)
  writeLines(sub("n1#1@14.000000000000", "n1#1@13.000000000000", inp_base, fixed = TRUE), inp)
  reject("reject_modified_fixed_logit", ch7_step3_chain_receipt(ms, inp)); writeLines(inp_base, inp)
  writeLines(sub("MODEL c1:", "MODEL c4:", inp_base, fixed = TRUE), inp)
  reject("reject_logit_wrong_namespace", ch7_step3_chain_receipt(ms, inp)); writeLines(inp_base, inp)
  writeLines(c(baseline, "changed source"), f$out)
  reject("reject_step1_changed_after_build", ch7_step3_chain_receipt(ms, inp)); writeLines(baseline, f$out)
  dat <- file.path(dirname(inp), "data.dat"); d <- utils::read.table(dat, header = FALSE)
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
