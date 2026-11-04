# 第七章混合模型工具合同：ch7_mixture_object() 的一般化、INP 家族分类、类别枚举汇总、Step-1→Step-3 绑定。
# 只用合成数据和手写的合成 .out 片段，不读取研究文件，不调用 Mplus。
# 独立运行：Rscript -e 'source("scripts/test_ch7_mixture_tools_20261105.R"); test_ch7_mixture_tools("<新目录>", ".")'

# 合成的 Mplus 混合模型 .out 片段：只含 readModels() 与枚举读出用到的段落
ch7_fake_mixture_out <- function(path, K, n = 320L, ll, npar = 4L * K + 3L, entropy = 0.8, props = rep(1 / K, K),
                                 vlmr_p = 0.01, lmr_p = 0.012, blrt_p = 0.001, replicated = TRUE,
                                 usevariables = "y1 y2 y3 y4", classes = paste0("c(", K, ")")) {
  f3 <- function(x) sprintf("%.3f", x)
  aic <- -2 * ll + 2 * npar; bic <- -2 * ll + npar * log(n); abic <- -2 * ll + npar * log((n + 2) / 24)
  counts <- sprintf("       %d    %12.5f    %10.5f", seq_along(props), props * n, props)
  lrt <- function(title, p, label) c(sprintf("     %s FOR %d (H0) VERSUS %d CLASSES", title, K - 1L, K), "",
    sprintf("          H0 Loglikelihood Value                        %s", f3(ll - 30)),
    "          2 Times the Loglikelihood Difference            60.000",
    "          Difference in the Number of Parameters                4", sprintf("          %s %.4f", label, p), "")
  writeLines(c("Mplus VERSION 8.10", "MUTHEN & MUTHEN", "", "INPUT INSTRUCTIONS", "", "  TITLE: synthetic enumeration;",
    "  DATA: FILE = \"data.dat\";", "  VARIABLE:", paste0("  NAMES = ", usevariables, ";"),
    paste0("  USEVARIABLES = ", usevariables, ";"), paste0("  CLASSES = ", classes, ";"),
    "  ANALYSIS:", "  TYPE = MIXTURE;", "  STARTS = 20 5;", "  OUTPUT: TECH11 TECH14;", "",
    "INPUT READING TERMINATED NORMALLY", "", "SUMMARY OF ANALYSIS", "",
    "Number of groups                                                 1",
    sprintf("Number of observations                                        %3d", n), "",
    if (replicated) "     THE BEST LOGLIKELIHOOD VALUE HAS BEEN REPLICATED.  RERUN WITH AT LEAST TWICE THE"
    else c("     WARNING:  THE BEST LOGLIKELIHOOD VALUE WAS NOT REPLICATED.  THE",
           "     SOLUTION MAY NOT BE TRUSTWORTHY DUE TO LOCAL MAXIMA.  INCREASE THE", "     NUMBER OF RANDOM STARTS."),
    "", "THE MODEL ESTIMATION TERMINATED NORMALLY", "", "MODEL FIT INFORMATION", "",
    sprintf("Number of Free Parameters                       %d", npar), "", "Loglikelihood", "",
    sprintf("          H0 Value                       %s", f3(ll)), "", "Information Criteria", "",
    sprintf("          Akaike (AIC)                    %s", f3(aic)), sprintf("          Bayesian (BIC)                  %s", f3(bic)),
    sprintf("          Sample-Size Adjusted BIC        %s", f3(abic)), "            (n* = (n + 2) / 24)", "",
    "FINAL CLASS COUNTS AND PROPORTIONS FOR THE LATENT CLASSES", "BASED ON THE ESTIMATED MODEL", "",
    "    Latent", "   Classes", "", counts, "",
    "FINAL CLASS COUNTS AND PROPORTIONS FOR THE LATENT CLASSES", "BASED ON ESTIMATED POSTERIOR PROBABILITIES", "",
    "    Latent", "   Classes", "", counts, "",
    "FINAL CLASS COUNTS AND PROPORTIONS FOR THE LATENT CLASSES", "BASED ON THEIR MOST LIKELY LATENT CLASS MEMBERSHIP", "",
    "Class Counts and Proportions", "", "    Latent", "   Classes", "", counts, "",
    if (K > 1L) c("CLASSIFICATION QUALITY", "", sprintf("     Entropy                         %s", f3(entropy)), ""),
    "MODEL RESULTS", "", if (K > 1L) c("TECHNICAL 11 OUTPUT", "",
      lrt("VUONG-LO-MENDELL-RUBIN LIKELIHOOD RATIO TEST", vlmr_p, "P-Value                                        "),
      "     LO-MENDELL-RUBIN ADJUSTED LRT TEST", "", "          Value                                            58.000",
      sprintf("          P-Value                                          %.4f", lmr_p), "", "TECHNICAL 14 OUTPUT", "",
      lrt("PARAMETRIC BOOTSTRAPPED LIKELIHOOD RATIO TEST", blrt_p, "Approximate P-Value                            "),
      "          Successful Bootstrap Draws                          100", ""),
    "MUTHEN & MUTHEN"), path)
}

test_ch7_mixture_tools <- function(output_dir, skill_root) {
  for (pkg in c("MplusAutomation", "digest", "jsonlite")) {
    if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
  }
  skill_root <- normalizePath(skill_root, winslash = "/")
  if (file.exists(output_dir)) stop("Fresh output directory required")
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = "/")
  source(file.path(skill_root, "scripts/ch7_mixture_syntax.R"), local = TRUE)
  source(file.path(skill_root, "scripts/ch7_mixture_tools.R"), local = TRUE)
  checks <- list()
  check <- function(name, ok) {
    if (!isTRUE(ok)) stop("Contract failed: ", name)
    checks[[name]] <<- TRUE
  }
  reject <- function(name, expr) check(name, inherits(tryCatch(force(expr), error = identity), "error"))
  ns <- asNamespace("MplusAutomation")
  for (fun in c("runModels", "detectMplus")) {
    trace(fun, tracer = quote(stop("ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI")), print = FALSE, where = ns)
  }
  on.exit(for (fun in c("runModels", "detectMplus")) untrace(fun, where = ns), add = TRUE)
  reject("engine_guard_blocks_runModels", MplusAutomation::runModels())
  compile <- function(label, built) {
    folder <- file.path(output_dir, label); dir.create(folder, recursive = TRUE); prior <- getwd()
    tryCatch({
      setwd(folder)
      MplusAutomation::mplusModeler(built$object, modelout = "model.inp", dataout = "data.dat", run = 0L, check = FALSE,
        hashfilename = FALSE, writeData = "always", quiet = TRUE, Mplus_command = "FORBIDDEN_IN_SYNTHETIC_CI", killOnFail = FALSE)
    }, finally = setwd(prior))
    file.path(folder, "model.inp")
  }
  model_text <- function(built) built$object$MODEL

  # 合成数据：固定种子；保存并恢复调用者的随机数状态
  old_seed <- if (exists(".Random.seed", envir = globalenv())) get(".Random.seed", envir = globalenv()) else NULL
  on.exit(if (is.null(old_seed)) rm(".Random.seed", envir = globalenv()) else
    assign(".Random.seed", old_seed, envir = globalenv()), add = TRUE)
  set.seed(7205L)
  n <- 200L
  syn <- data.frame(pid = seq_len(n))
  for (t in 1:3) {
    syn[[paste0("x", t, "a")]] <- rnorm(n); syn[[paste0("x", t, "b")]] <- rnorm(n)
    syn[[paste0("u", t, "a")]] <- rbinom(n, 1, .4); syn[[paste0("u", t, "b")]] <- rbinom(n, 1, .6)
    syn[[paste0("n", t)]] <- sample.int(4L, n, replace = TRUE)
  }
  wave <- function(t) paste0(c("x", "x", "u", "u"), t, c("a", "b", "a", "b"))
  binary <- unlist(lapply(1:3, function(t) paste0("u", t, c("a", "b"))))

  # 1. 生成器的一般化（第七章测试只覆盖 4 波、3 类、4 连续 + 2 二分类）
  lca <- ch7_mixture_object(syn, "lpa", waves = list(c("u1a", "u1b")), categorical = c("u1a", "u1b"), classes = 3L)
  check("lca_has_no_overall_block", !grepl("%OVERALL%", model_text(lca), fixed = TRUE) &&
    grepl("%c#3%\n[u1a$1 u1b$1];", model_text(lca), fixed = TRUE))
  lpa <- ch7_mixture_object(syn, "lpa", waves = list(c("x1a", "x1b")), classes = 2L)
  check("lpa_has_no_threshold_line", !grepl("$1", model_text(lpa), fixed = TRUE) && grepl("%OVERALL%\nx1a x1b;", model_text(lpa), fixed = TRUE))
  lta3 <- ch7_mixture_object(syn, "lta", waves = lapply(1:3, wave), categorical = binary, classes = 2L)
  check("lta_three_waves_two_classes", grepl("c2 ON c1;\nc3 ON c2;", model_text(lta3), fixed = TRUE) &&
    grepl("MODEL c3:", model_text(lta3), fixed = TRUE) && !grepl("MODEL c4:", model_text(lta3), fixed = TRUE) &&
    lengths(regmatches(model_text(lta3), gregexpr("(mk2i4)", model_text(lta3), fixed = TRUE))) == 3L)
  lta_free <- ch7_mixture_object(syn, "lta", waves = lapply(1:3, wave), categorical = binary, classes = 2L, invariant = FALSE)
  check("lta_free_labels_by_wave", grepl("(w3k2i4)", model_text(lta_free), fixed = TRUE) && !grepl("(mk", model_text(lta_free), fixed = TRUE))
  ms4 <- ch7_mixture_object(syn, "mslta", waves = lapply(1:3, wave), categorical = binary, classes = 4L)
  check("mslta_k4_stayer_rows", grepl("c3#3 ON c2#1@0 c2#2@0 c2#3@20;", model_text(ms4), fixed = TRUE) &&
    grepl("[c3#1@-10 c3#2@-10 c3#3@-10];", model_text(ms4), fixed = TRUE) &&
    grepl("%g#1%\n[c2#1 c2#2 c2#3];", model_text(ms4), fixed = TRUE))
  e1 <- matrix(c(.7, .1, .1, .1, .1, .7, .1, .1, .1, .1, .7, .1, .1, .1, .1, .7), 4, byrow = TRUE)
  e2 <- matrix(c(.85, .05, .05, .05, .05, .85, .05, .05, .05, .05, .85, .05, .05, .05, .05, .85), 4, byrow = TRUE)
  asym4 <- rbind(c(.70, .15, .10, .05), c(.10, .70, .15, .05), c(.05, .10, .75, .10), c(.05, .05, .10, .80))
  s3 <- ch7_mixture_object(syn, "lta", classes = 4L, step3 = list(nominal = c("n1", "n2", "n3"), error = list(asym4, e2, e1)))
  check("step3_rows_are_true_classes", grepl(sprintf("%%c1#1%%\n[n1#1@%.12f];\n[n1#2@%.12f];", log(.70 / .05), log(.15 / .05)),
    model_text(s3), fixed = TRUE))
  check("step3_per_wave_error", grepl(sprintf("[n1#1@%.12f];", log(.7 / .05)), model_text(s3), fixed = TRUE) &&
    grepl(sprintf("[n2#1@%.12f];", log(.85 / .05)), model_text(s3), fixed = TRUE) &&
    grepl("STARTS = 0;", s3$object$ANALYSIS, fixed = TRUE))
  reject("rejects_lpa_with_two_waves", ch7_mixture_object(syn, "lpa", waves = list(wave(1), wave(2)), classes = 2L))
  reject("rejects_lta_with_one_wave", ch7_mixture_object(syn, "lta", waves = list(wave(1)), classes = 2L))
  reject("rejects_categorical_outside_waves", ch7_mixture_object(syn, "lpa", waves = list(c("x1a", "x1b")), categorical = "u1a", classes = 2L))
  reject("rejects_unequal_invariant_pattern", ch7_mixture_object(syn, "lta", waves = list(wave(1), c("x2a", "u2a", "x2b", "u2b")),
    categorical = binary, classes = 2L))
  reject("rejects_latent_name_clash", ch7_mixture_object(transform(syn, c1 = x1a), "lta", waves = list(c("c1", "x1b"), c("x2a", "x2b")), classes = 2L))
  reject("rejects_missing_variable", ch7_mixture_object(syn, "lpa", waves = list(c("x1a", "zz")), classes = 2L))
  reject("rejects_long_name", ch7_mixture_object(transform(syn, x1aaaaaaa = x1a), "lpa", waves = list("x1aaaaaaa"), classes = 2L))
  reject("rejects_bad_error_rows", ch7_mixture_object(syn, "lta", classes = 4L, step3 = list(nominal = c("n1", "n2"), error = e1 * 0.9)))
  zero <- e1; zero[1, ] <- c(.9, .1, 0, 0)
  reject("rejects_zero_error_cell", ch7_mixture_object(syn, "lta", classes = 4L, step3 = list(nominal = c("n1", "n2"), error = zero)))
  reject("rejects_nominal_outside_1_to_K", ch7_mixture_object(syn, "lta", classes = 3L, step3 = list(nominal = c("n1", "n2"),
    error = diag(.7, 3) + .1)))
  reject("rejects_step3_for_lpa", ch7_mixture_object(syn, "lpa", classes = 4L, step3 = list(nominal = c("n1", "n2"), error = e1)))
  reject("rejects_non_numeric", ch7_mixture_object(transform(syn, x1a = as.character(x1a)), "lpa", waves = list(c("x1a", "x1b")), classes = 2L))
  # 2. INP 家族分类：生成的输入 + 手写边界例（只看语法，标题和注释不算）
  family_of <- function(x) { r <- if (is.character(x) && length(x) == 1L && file.exists(x)) ch7_classify_inp(x) else ch7_classify_inp(text = x); r }
  generated <- list(lca = c("LCA", FALSE), lpa = c("LPA", FALSE), lta3 = c("LTA", FALSE), lta_free = c("LTA", FALSE),
                    ms4 = c("MS_LTA", FALSE), s3 = c("LTA", TRUE))
  objects <- list(lca = lca, lpa = lpa, lta3 = lta3, lta_free = lta_free, ms4 = ms4, s3 = s3)
  for (id in names(generated)) {
    r <- family_of(compile(file.path("classify", id), objects[[id]]))
    check(paste0("classify_generated_", id), r$family == generated[[id]][1] && r$step3 == as.logical(generated[[id]][2]))
  }
  check("classify_mslta_notes_finite_logits", any(grepl("finite logits", family_of(compile("classify/ms4_again", ms4))$approximations)))
  check("classify_registry_family", identical(family_of(compile("classify/lpa_again", lpa))$registry_family, "LPA_LCA"))
  head <- "DATA: FILE = d.dat;\nVARIABLE: NAMES = g y1-y4 u1-u4 x1 x2 i1 i2;\n"
  hand <- list(
    knownclass_titled_mslta = c("MG-LTA", paste0("TITLE: MS-LTA movers stayers;\n", head,
      "USEVARIABLES = y1-y4; CLASSES = g(2) c1(2) c2(2); KNOWNCLASS = g (g = 0 g = 1);\nANALYSIS: TYPE = MIXTURE;\n",
      "MODEL:\n%OVERALL%\nc2 ON c1;\nMODEL g:\n%g#1%\nc2 ON c1;\n%g#2%\nc2 ON c1;\nOUTPUT: TECH1;")),
    knownclass_plain = c("MG-LTA", paste0(head, "USEVARIABLES = y1-y4; CLASSES = g(2) c1(2) c2(2); KNOWNCLASS = g (g = 0 g = 1);\n",
      "ANALYSIS: TYPE = MIXTURE;\nMODEL:\n%OVERALL%\nc2 ON c1;\nOUTPUT: TECH1;")),
    apim_without_with = c("OTHER", paste0(head, "USEVARIABLES = y1 y2 x1 x2;\nMODEL:\ny1 ON x1 x2;\ny2 ON x2 x1;\nOUTPUT: STDYX;")),
    ri_lta = c("OTHER_MIXTURE", paste0(head, "USEVARIABLES = y1-y4; CLASSES = c1(2) c2(2);\nANALYSIS: TYPE = MIXTURE;\n",
      "MODEL:\n%OVERALL%\nc2 ON c1;\nf BY y1-y4@1;\nOUTPUT: TECH1;")),
    gmm = c("OTHER_MIXTURE", paste0(head, "USEVARIABLES = y1-y4; CLASSES = c(2);\nANALYSIS: TYPE = MIXTURE;\n",
      "MODEL:\n%OVERALL%\ni s | y1@0 y2@1 y3@2 y4@3;\nOUTPUT: TECH1;")),
    no_chain = c("OTHER_MIXTURE", paste0(head, "USEVARIABLES = y1-y4; CLASSES = c1(2) c2(2);\nANALYSIS: TYPE = MIXTURE;\n",
      "MODEL:\n%OVERALL%\nc1 ON x1;\nOUTPUT: TECH1;")),
    no_stayer_block = c("OTHER_MIXTURE", paste0(head, "USEVARIABLES = y1-y4; CLASSES = g(2) c1(2) c2(2);\nANALYSIS: TYPE = MIXTURE;\n",
      "MODEL:\n%OVERALL%\nc2 ON c1;\nMODEL g:\n%g#1%\nc2 ON c1;\n%g#2%\nc2 ON c1;\nOUTPUT: TECH1;")),
    commented_edge = c("OTHER_MIXTURE", paste0("TITLE: LTA;\n", head, "USEVARIABLES = y1-y4; CLASSES = c1(2) c2(2);\n",
      "ANALYSIS: TYPE = MIXTURE;\nMODEL:\n%OVERALL%\n! c2 ON c1;\nOUTPUT: TECH1;")),
    abbreviated_lca = c("LCA", paste0(head, "usev are u1-u4;\ncateg = u1-u4;\nclasses = c (3);\nanalysis: type = mixture;\n",
      "model:\n%overall%\noutput: tech1;")),
    apim = c("APIM", paste0(head, "USEVARIABLES = y1 y2 x1 x2;\nMODEL:\ny1 ON x1 (a1);\ny1 ON x2 (p12);\n",
      "y2 ON x2 (a2);\ny2 ON x1 (p21);\ny1 WITH y2;\nx1 WITH x2;\nOUTPUT: STDYX;")),
    regression = c("OTHER", paste0(head, "USEVARIABLES = y1 x1 x2;\nMODEL:\ny1 ON x1 x2;\nOUTPUT: STDYX;")),
    growth = c("OTHER", paste0(head, "USEVARIABLES = y1-y4;\nMODEL:\ni s | y1@0 y2@1 y3@2 y4@3;\nOUTPUT: TECH1;")))
  for (id in names(hand)) {
    r <- family_of(hand[[id]][2])
    expected <- hand[[id]][1]
    ok <- if (expected == "MG-LTA") r$family == "LTA" && grepl("KNOWNCLASS", r$subtype) else r$family == expected
    check(paste0("classify_hand_", id), ok)
  }
  check("classify_apim_says_structure_only", grepl("not verified", family_of(hand$apim[2])$subtype))

  # 3. 类别枚举：BIC 与 AIC/aBIC 选的 K 不同、K=4 最优 LL 未复现、K=4 有小类
  spec <- data.frame(K = 1:4, npar = c(9L, 14L, 19L, 24L), ll = c(-2000, -1900, -1850, -1840),
                     entropy = c(NA, .70, .85, .82), vlmr = c(NA, .001, .004, .30), lmr = c(NA, .002, .006, .33),
                     blrt = c(NA, .001, .001, .02), replicated = c(TRUE, TRUE, TRUE, FALSE))
  props <- list(1, c(.6, .4), c(.5, .3, .2), c(.5, .28, .18, .04))
  paths <- file.path(output_dir, "enumeration", sprintf("c%d.out", spec$K)); dir.create(dirname(paths[1]))
  for (i in seq_len(nrow(spec))) ch7_fake_mixture_out(paths[i], spec$K[i], ll = spec$ll[i], npar = spec$npar[i],
    entropy = spec$entropy[i], props = props[[i]], vlmr_p = spec$vlmr[i], lmr_p = spec$lmr[i], blrt_p = spec$blrt[i],
    replicated = spec$replicated[i])
  tab <- ch7_enumeration_table(rev(paths), min_class_prop = .05, min_entropy = .8)
  check("enum_sorted_by_K", identical(tab$K, 1:4))
  check("enum_reads_fit", isTRUE(all.equal(tab$LL, spec$ll)) && identical(as.integer(tab$parameters), spec$npar) &&
    isTRUE(all.equal(tab$BIC, -2 * spec$ll + spec$npar * log(320), tolerance = 1e-6)))
  check("enum_bic_and_aic_disagree", identical(which(tab$lowest_BIC), 3L) && identical(which(tab$lowest_AIC), 4L) &&
    identical(which(tab$lowest_aBIC), 4L))
  check("enum_lrt_flags", identical(tab$LMR_significant, c(FALSE, TRUE, TRUE, FALSE)) &&
    identical(tab$BLRT_significant, c(FALSE, TRUE, TRUE, TRUE)) && is.na(tab$entropy[1]))
  check("enum_thresholds", identical(tab$entropy_ok, c(FALSE, FALSE, TRUE, TRUE)) &&
    identical(tab$class_size_ok, c(TRUE, TRUE, TRUE, FALSE)))
  check("enum_replication_flag", identical(tab$best_ll_replicated, spec$replicated) && tab$warnings[4] >= 1L)
  check("enum_does_not_pick_K", !any(grepl("select|best_K|chosen", names(tab), ignore.case = TRUE)) &&
    grepl("interpretability", attr(tab, "selection")) && all(nchar(tab$sha256) == 64L))
  check("enum_thresholds_optional", all(is.na(ch7_enumeration_table(paths)$entropy_ok)))
  bad <- file.path(output_dir, "enumeration_bad"); dir.create(bad)
  one <- function(name, ...) { p <- file.path(bad, name); ch7_fake_mixture_out(p, ...); p }
  reject("enum_rejects_duplicate_K", ch7_enumeration_table(c(paths[2], one("dup.out", 2L, ll = -1900))))
  reject("enum_rejects_other_variables", ch7_enumeration_table(c(paths[2], one("vars.out", 3L, ll = -1850, usevariables = "y1 y2 y3 y5"))))
  reject("enum_rejects_other_n", ch7_enumeration_table(c(paths[2], one("n.out", 3L, ll = -1850, n = 300L))))
  reject("enum_rejects_two_class_variables", ch7_enumeration_table(one("two.out", 2L, ll = -1900, classes = "c1(2) c2(2)")))
  reject("enum_rejects_count_table_mismatch", ch7_enumeration_table(one("rows.out", 3L, ll = -1850, props = c(.5, .5))))
  # 4. Step-1 存盘 → Step-3 输入绑定：合成的 Step-1 .out 片段与存盘，经生成器写出的 Step-3 INP/DAT
  base <- file.path(output_dir, "binding", "base"); dir.create(base, recursive = TRUE)
  m <- 60L
  save1 <- data.frame(Y = round(rnorm(m), 3), PID = sample(1000L + seq_len(m)), CPROB1 = .5, CPROB2 = .3, CPROB3 = .2,
                      C1 = sample.int(3L, m, replace = TRUE), C2 = sample.int(3L, m, replace = TRUE))
  write_save <- function(d, path) writeLines(apply(d, 1, function(r) paste(formatC(r, width = 10, format = "f", digits = 3), collapse = "")), path)
  write_save(save1, file.path(base, "step1_cprob.dat"))
  step1_text <- c("Mplus VERSION 8.10", "", "THE MODEL ESTIMATION TERMINATED NORMALLY", "", "SAVEDATA INFORMATION", "",
    "  Order and format of variables", "", paste0("    ", names(save1), "           F10.3"), "",
    "  Save file", "    step1_cprob.dat", "", "  Save file format", "    7F10.3", "", "  Save file record length    10000", "")
  writeLines(step1_text, file.path(base, "step1.out"))
  # 第 1 波：行列和都为 1 但不对称，转置后仍是合法矩阵，只能靠行列约定区分
  err <- list(rbind(c(.7, .2, .1), c(.1, .7, .2), c(.2, .1, .7)), diag(.4, 3) + .2)
  step3_data <- data.frame(pid = save1$PID, n1 = save1$C1, n2 = save1$C2, y = save1$Y)
  built3 <- ch7_mixture_object(step3_data, "lta", classes = 3L, keep = c("pid", "n1", "n2", "y"),
                               step3 = list(nominal = c("n1", "n2"), error = err))
  inp3 <- compile("binding/base_step3", built3)
  for (f in c("model.inp", "data.dat")) file.copy(file.path(dirname(inp3), f), file.path(base, f))
  variant <- function(label, mutate = NULL, nominal_map = c(n1 = "C1", n2 = "C2"), error = err, step3_dat = NULL) {
    folder <- file.path(output_dir, "binding", label); dir.create(folder)
    file.copy(list.files(base, full.names = TRUE), folder)
    if (!is.null(mutate)) mutate(folder)
    ch7_step3_binding(file.path(folder, "step1.out"), file.path(folder, "step1_cprob.dat"), file.path(folder, "model.inp"),
                      if (is.null(step3_dat)) NULL else file.path(folder, step3_dat), id = "pid",
                      nominal_map = nominal_map, error = error)
  }
  edit_dat <- function(folder, f) {
    d <- utils::read.table(file.path(folder, "data.dat"), header = FALSE)
    utils::write.table(f(d), file.path(folder, "data.dat"), row.names = FALSE, col.names = FALSE)
  }
  good <- variant("good")
  check("binding_good_passes", identical(good$status, "PASS") && isTRUE(good$row_order_identical) &&
    all(vapply(good$max_abs_logit_diff, function(x) x < 1e-9, logical(1))) && good$rows == m)
  check("binding_records_four_sha256", length(good$files) == 4L && all(vapply(good$files, function(f) nchar(f$sha256) == 64L, logical(1))))
  check("binding_receipt_has_no_data_values", !any(c("data", "values", "logits", "error") %in% names(good)))
  shuffled <- variant("shuffled", function(folder) edit_dat(folder, function(d) d[rev(seq_len(nrow(d))), ]))
  check("binding_rows_matched_by_id", identical(shuffled$status, "PASS") && identical(shuffled$row_order_identical, FALSE))
  fails <- function(name, result, key) check(name, identical(result$status, "FAIL") && identical(result$checks[[key]], FALSE))
  fails("binding_detects_changed_value", variant("tampered", function(folder) edit_dat(folder, function(d) { d[5, 4] <- d[5, 4] + 0.5; d })),
        "projected_values_match")
  fails("binding_detects_dropped_row", variant("dropped", function(folder) edit_dat(folder, function(d) d[-1, ])), "same_ids")
  fails("binding_detects_duplicate_id", variant("dup_id", function(folder) {
    d <- save1; d$PID[2] <- d$PID[1]; write_save(d, file.path(folder, "step1_cprob.dat")) }), "ids_unique")
  fails("binding_detects_wrong_error_matrix", variant("wrong_error", error = rev(err)), "N1_fixed_logits_match_error")
  fails("binding_detects_transposed_error_matrix", variant("transposed_error", error = list(t(err[[1]]), err[[2]])),
        "N1_fixed_logits_match_error")
  fails("binding_detects_other_savedata", variant("other_save", function(folder) writeLines(sub("step1_cprob.dat", "other.dat",
    step1_text, fixed = TRUE), file.path(folder, "step1.out"))), "step1_savedata_name_matches")
  fails("binding_detects_abnormal_step1", variant("not_terminated", function(folder) writeLines(step1_text[-3],
    file.path(folder, "step1.out"))), "step1_terminated_normally")
  fails("binding_detects_incomplete_nominal_map", variant("partial_map", nominal_map = c(n1 = "C1")), "nominal_map_covers_nominal")
  fails("binding_detects_inp_reads_other_dat", variant("other_dat", function(folder)
    file.copy(file.path(folder, "data.dat"), file.path(folder, "other.dat")), step3_dat = "other.dat"), "step3_inp_reads_step3_dat")
  fails("binding_detects_edited_logit", variant("edited_logit", function(folder) {
    text <- readLines(file.path(folder, "model.inp")); target <- grep("[n2#1@", text, fixed = TRUE)[1]
    text[target] <- sub("@(-?[0-9.]+)", "@0.123", text[target]); writeLines(text, file.path(folder, "model.inp")) }),
    "N2_fixed_logits_match_error")
  check("binding_step3_inp_classified_as_lta_step3", isTRUE(family_of(file.path(base, "model.inp"))$step3))

  check("no_engine_outputs", !length(list.files(output_dir, pattern = "\\.(gh5)$", recursive = TRUE)) &&
    !length(list.files(file.path(output_dir, "classify"), pattern = "\\.out$", recursive = TRUE)))
  manifest <- list(test = "ch7_mixture_tools", mplus_calls = 0L, checks = names(checks),
    enumeration_outputs = basename(paths), binding_good = good[c("status", "checks", "files", "rows", "columns")])
  jsonlite::write_json(manifest, file.path(output_dir, "ch7_mixture_tools_manifest.json"), auto_unbox = TRUE, pretty = TRUE)
  cat("CH7_MIXTURE_TOOLS_PASS", length(checks), "checks; Mplus calls: 0\n")
  invisible(manifest)
}
