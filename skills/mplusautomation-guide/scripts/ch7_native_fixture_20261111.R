# 第七章原生验收的独立合成生成器；只生成数据及统一入口配置，绝不调用引擎。
# 连续量采用条件独立正态，分类量为二元；种子和设计写入回执，数值不来自研究。
ch7_native_fixture <- function(output_dir, n = 400L, seed = 71111L) {
  stopifnot(requireNamespace("jsonlite", quietly = TRUE), requireNamespace("digest", quietly = TRUE))
  if (length(n) != 1L || !is.finite(n) || n != as.integer(n) || n < 100L)
    stop("n must be an integer >=100")
  if (!is.numeric(seed) || length(seed) != 1L || !is.finite(seed) ||
      seed != trunc(seed) || seed <= 0 || seed > 2147483647)
    stop("seed must be a positive integer <=2147483647")
  if (file.exists(output_dir)) stop("Fresh fixture root required")
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = "/", mustWork = TRUE)
  had_seed <- exists(".Random.seed", envir = .GlobalEnv, inherits = FALSE)
  if (had_seed) old_seed <- get(".Random.seed", envir = .GlobalEnv)
  on.exit(if (had_seed) assign(".Random.seed", old_seed, envir = .GlobalEnv)
          else if (exists(".Random.seed", envir = .GlobalEnv, inherits = FALSE))
            rm(".Random.seed", envir = .GlobalEnv), add = TRUE)
  set.seed(seed)
  # mover 的转移仍可留在对角；stayer 的生成状态精确不变，与模型有限 logit 近似分开。
  stayer <- rbinom(n, 1L, .30) == 1L
  states <- matrix(NA_integer_, n, 4L)
  states[, 1L] <- sample.int(2L, n, replace = TRUE)
  for (w in 2:4) {
    states[, w] <- states[, w - 1L]
    flip <- !stayer & runif(n) < .24
    states[flip, w] <- 3L - states[flip, w - 1L]
  }
  data <- data.frame(sid = seq_len(n))
  mapping <- list()
  for (w in 1:4) for (j in 1:6) {
    binary <- j > 3L
    role <- paste0(if (binary) "b" else "x", if (binary) j - 3L else j)
    target <- paste0("t", w, role)
    source <- paste0("synthetic_wave", w, "_", role)
    data[[source]] <- if (binary) rbinom(n, 1L, ifelse(states[, w] == 1L, .20, .80))
                      else rnorm(n, ifelse(states[, w] == 1L, -1.0, 1.0), 1)
    mapping[[length(mapping) + 1L]] <- list(wave = paste0("w", w), role = role,
      source = source, target = target, type = if (binary) "categorical" else "continuous",
      scale = if (binary) "binary_0_1" else "synthetic_normal_no_transform")
  }
  csv <- file.path(output_dir, "synthetic_source.csv")
  utils::write.csv(data, csv, row.names = FALSE, na = "")
  spec <- function(id, family, wave_ids, roles) list(id = id, family = family,
    wave_ids = wave_ids, roles = roles, classes = 2L, invariant = TRUE,
    starts = "40 10", estimator = "MLR", processors = 1L, seed = seed)
  continuous <- paste0("x", 1:3); binary <- paste0("b", 1:3)
  config <- list(schema_version = 1L, mode = "new_source",
    source = list(path = csv, sha256 = digest::digest(csv, algo = "sha256", file = TRUE),
      format = "csv", encoding = "UTF-8", id = "sid", row_grain = "person_wide", missing_codes = numeric()),
    sample = list(rule = "all_rows", row_order = "source"),
    transformations = list(status = "none", description = "Synthetic values already on declared model scales"),
    waves = lapply(1:4, function(w) list(wave = paste0("w", w), label = paste("Wave", w), time = w)),
    mapping = mapping, id_target = "sid",
    models = list(
      spec("SYN_LPA", "lpa", "w1", continuous),
      spec("SYN_LCA", "lpa", "w1", binary),
      spec("SYN_MIXED", "lpa", "w1", c(continuous, binary)),
      spec("SYN_LTA4_MI_STEP1", "lta", paste0("w", 1:4), c(continuous, binary)),
      spec("SYN_MSLTA4_MI", "mslta", paste0("w", 1:4), c(continuous, binary))))
  config_file <- file.path(output_dir, "synthetic_config.json")
  jsonlite::write_json(config, config_file, auto_unbox = TRUE, pretty = TRUE, digits = NA)
  design <- list(schema = "ch7-native-fixture/1", seed = seed, rows = n,
    columns = ncol(data), waves = 4L, classes = 2L, source_sha256 = config$source$sha256,
    config_sha256 = digest::digest(config_file, algo = "sha256", file = TRUE),
    synthetic_only = TRUE, mplus_calls = 0L, acceptance = "GENERATED_NOT_ENGINE_VALIDATED",
    measurement = "3 continuous normal + 3 binary indicators; within-class independent; invariant population parameters",
    stayer = "data generation exact no-change; model uses declared finite logit approximation",
    downstream = c("SYN_LTA4_STEP3", "SYN_MSLTA4_STEP3"),
    downstream_dependency = "SYN_LTA4_MI_STEP1 fresh OUT and its own savedata; never reuse prior CPROB")
  jsonlite::write_json(design, file.path(output_dir, "fixture_receipt.json"),
                      auto_unbox = TRUE, pretty = TRUE, digits = NA)
  list(config = config, config_file = config_file, design = design)
}
