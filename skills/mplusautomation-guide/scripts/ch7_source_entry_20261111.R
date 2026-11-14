# 第七章统一换源入口。只生成输入，不启动引擎；真实估计须走项目已授权的 RStudio/ClaudeR 执行层。
# 新源、Step-1 派生的 Step-3 和归档原样重放分别记账，不覆盖既有目录。
ch7_entry_script_dir <- local({
  files <- vapply(sys.frames(), function(x) if (is.null(x$ofile)) "" else as.character(x$ofile)[1L], "")
  files <- files[nzchar(files)]
  if (length(files)) dirname(normalizePath(tail(files, 1L), winslash = "/", mustWork = TRUE)) else NULL
})

ch7_entry_assert <- function(ok, message) {
  if (!isTRUE(ok)) stop(message, call. = FALSE)
}
ch7_entry_scalar <- function(x) is.character(x) && length(x) == 1L && !is.na(x) && nzchar(x)
ch7_entry_vector <- function(x) {
  if (is.list(x)) x <- unlist(x, recursive = FALSE, use.names = FALSE)
  x
}
ch7_entry_names <- function(x) is.character(x) && length(x) > 0L && !anyNA(x) &&
  all(grepl("^[A-Za-z][A-Za-z0-9_]{0,7}$", x)) && !anyDuplicated(toupper(x))
ch7_entry_sha <- function(path) digest::digest(path, algo = "sha256", file = TRUE)
ch7_entry_file <- function(path, expected) {
  ch7_entry_assert(ch7_entry_scalar(path) && file.exists(path) && !dir.exists(path), "Source file required")
  ch7_entry_assert(ch7_entry_scalar(expected) && grepl("^[0-9a-f]{64}$", expected), "Expected SHA256 required")
  ch7_entry_assert(identical(ch7_entry_sha(path), expected), "Source SHA256 mismatch")
  normalizePath(path, winslash = "/", mustWork = TRUE)
}
ch7_entry_fields <- function(x, required, optional = character(), label) {
  ch7_entry_assert(is.list(x) && !is.null(names(x)) && !anyDuplicated(names(x)) &&
    all(required %in% names(x)) && all(names(x) %in% c(required, optional)), paste("Invalid fields:", label))
}
ch7_entry_records <- function(x, label) {
  if (is.data.frame(x)) x <- lapply(seq_len(nrow(x)), function(i) as.list(x[i, , drop = FALSE]))
  ch7_entry_assert(is.list(x) && length(x) > 0L && all(vapply(x, is.list, logical(1))), paste("Nonempty records required:", label))
  x
}

# 严格十进制解析；不把未知字符串、日期、无限值悄悄改成缺失。
# CSV 字符 token 先 trim 并按数值解析，再与声明的数值缺失码比较；非数值
# 字符哨兵仍按 trim 后文本比较。audit=TRUE 供 manifest 记录摘要，默认返回
# 数值向量以保持既有调用接口。
ch7_entry_numeric <- function(x, codes, name, audit = FALSE) {
  ch7_entry_assert(is.character(x) || (is.numeric(x) && !is.object(x)), paste("Unsupported source type:", name))
  codes <- ch7_entry_vector(codes)
  if (is.null(codes)) codes <- numeric()
  ch7_entry_assert((is.numeric(codes) || is.character(codes)) && !anyNA(codes), "Invalid missing codes")
  code_text <- trimws(as.character(codes))
  code_numeric <- grepl("^[+-]?([0-9]+(\\.[0-9]*)?|\\.[0-9]+)([eE][+-]?[0-9]+)?$", code_text)
  numeric_codes <- suppressWarnings(as.numeric(code_text[code_numeric]))
  text_codes <- code_text[!code_numeric]
  missing_numeric <- logical(length(x)); missing_text <- logical(length(x))
  if (is.numeric(x)) {
    missing_numeric <- is.finite(x) & x %in% numeric_codes
    missing <- is.na(x) | missing_numeric
    ch7_entry_assert(all(missing | is.finite(x)), paste("Nonfinite source values:", name))
    # DTA 已经是 double；不得通过显示字符串的有效位数改变原数值。
    x[missing] <- NA_real_
    result <- x
  } else {
    token <- trimws(as.character(x))
    decimal <- grepl("^[+-]?([0-9]+(\\.[0-9]*)?|\\.[0-9]+)([eE][+-]?[0-9]+)?$", token)
    values <- suppressWarnings(as.numeric(token))
    missing_numeric <- decimal & is.finite(values) & values %in% numeric_codes
    missing_text <- !is.na(token) & token %in% text_codes
    missing <- is.na(x) | missing_numeric | missing_text
    ch7_entry_assert(all(missing | (decimal & is.finite(values))), paste("Non-decimal or nonfinite source values:", name))
    values[missing] <- NA_real_
    result <- values
  }
  if (!isTRUE(audit)) return(result)
  list(values = result, audit = list(column = name, original_type = if (is.numeric(x)) "numeric" else "character",
    declared_numeric_codes = numeric_codes, declared_text_codes = text_codes,
    missing_count = sum(is.na(result)), numeric_code_matches = sum(missing_numeric),
    text_code_matches = sum(missing_text), trim_text_tokens = !is.numeric(x)))
}

ch7_entry_read_source <- function(config) {
  s <- config$source
  ch7_entry_fields(s, c("path", "sha256", "format", "encoding", "id", "row_grain", "missing_codes"),
    "column_missing_codes", "source")
  path <- ch7_entry_file(s$path, s$sha256)
  ch7_entry_assert(s$format %in% c("csv", "dta") && ch7_entry_scalar(s$encoding), "Source format must be csv/dta with explicit encoding")
  ch7_entry_assert(identical(s$row_grain, "person_wide"), "Only explicitly prepared person_wide sources are supported")
  ch7_entry_fields(config$sample, c("rule", "row_order"), label = "sample")
  ch7_entry_assert(identical(config$sample$rule, "all_rows") && identical(config$sample$row_order, "source"),
    "Prepare sample selection upstream: entry preserves all rows and source order")
  ch7_entry_fields(config$transformations, c("status", "description"), label = "transformations")
  ch7_entry_assert(config$transformations$status %in% c("none", "precomputed") &&
    ch7_entry_scalar(config$transformations$description), "Declare none/precomputed transformations and provenance description")
  if (s$format == "csv") {
    widths <- utils::count.fields(path, sep = ",", quote = '"', comment.char = "", blank.lines.skip = FALSE)
    ch7_entry_assert(length(widths) > 1L && !is.na(widths[1L]) && !is.na(tail(widths, 1L)) &&
      all(widths[!is.na(widths)] == widths[1L]), "CSV record widths must match the header")
    raw <- utils::read.csv(path, colClasses = "character", check.names = FALSE, na.strings = "",
      fileEncoding = s$encoding, strip.white = FALSE)
  } else {
    ch7_entry_assert(requireNamespace("haven", quietly = TRUE), "Missing package: haven")
    raw <- as.data.frame(haven::read_dta(path, encoding = s$encoding), check.names = FALSE)
    # 标签不是数值变换；日期等其他类仍由数字验证拒绝。
    raw[] <- lapply(raw, function(x) if (inherits(x, "haven_labelled")) unclass(x) else x)
  }
  ch7_entry_assert(identical(ch7_entry_sha(path), s$sha256), "Source changed during read")
  ch7_entry_assert(nrow(raw) > 0L && !anyDuplicated(names(raw)), "Source needs rows and unique column names")
  ch7_entry_assert(ch7_entry_scalar(s$id) && s$id %in% names(raw), "Explicit source ID column required")
  map <- ch7_entry_records(config$mapping, "mapping")
  for (m in map) {
    ch7_entry_fields(m, c("wave", "role", "source", "target", "type", "scale"), label = "mapping")
    ch7_entry_assert(all(vapply(m, ch7_entry_scalar, logical(1))), "Mapping fields must be nonempty scalar strings")
    ch7_entry_assert(m$type %in% c("continuous", "binary", "categorical"), "Supported types: continuous or binary categorical")
  }
  sources <- vapply(map, `[[`, "", "source"); targets <- vapply(map, `[[`, "", "target")
  keys <- vapply(map, function(m) paste(m$wave, m$role, sep = "/"), "")
  id_target <- config$id_target
  ch7_entry_assert(ch7_entry_names(c(id_target, targets)) && !anyDuplicated(keys) && !anyDuplicated(sources) &&
    all(sources %in% names(raw)) && !s$id %in% sources, "Mapping needs unique wave/role, source and Mplus target names, separate from ID")
  per_column <- s$column_missing_codes
  if (!is.null(per_column)) ch7_entry_assert(is.list(per_column) && !is.null(names(per_column)) &&
    !anyDuplicated(names(per_column)) && all(names(per_column) %in% c(s$id, sources)), "Unknown/duplicate per-column missing codes")
  missing_audit <- list()
  convert <- function(name) {
    converted <- ch7_entry_numeric(raw[[name]], c(ch7_entry_vector(s$missing_codes),
      ch7_entry_vector(per_column[[name]])), name, audit = TRUE)
    missing_audit[[name]] <<- converted$audit
    converted$values
  }
  if (is.character(raw[[s$id]])) {
    # CSV 身份列先核原字面量，再转 double。小数/科学计数法必须由源准备层显式规范化。
    token <- trimws(raw[[s$id]])
    ch7_entry_assert(!anyNA(token) && all(grepl("^[+-]?[0-9]+$", token)),
      "CSV ID must use exact integer literals; decimal or scientific notation is unsupported")
    magnitude <- sub("^[+-]", "", token)
    magnitude <- sub("^0+", "", magnitude); magnitude[magnitude == ""] <- "0"
    bound <- "9007199254740992"
    ch7_entry_assert(all(nchar(magnitude) < nchar(bound) | (nchar(magnitude) == nchar(bound) & magnitude <= bound)),
      "CSV ID literal exceeds the exact double integer range")
  }
  id <- convert(s$id)
  ch7_entry_assert(!anyNA(id) && all(is.finite(id)) && all(id == trunc(id)) &&
    all(abs(id) <= 2^53) && !anyDuplicated(id), "ID must contain unique exact integers within 2^53 with no missing values")
  data <- data.frame(id, check.names = FALSE); names(data) <- id_target
  for (m in map) {
    value <- convert(m$source)
    ch7_entry_assert(any(!is.na(value)), paste("All-missing indicator:", m$target))
    if (m$type != "continuous") ch7_entry_assert(setequal(unique(value[!is.na(value)]), 0:1),
      paste("Categorical generator requires observed binary 0/1 support:", m$target))
    data[[m$target]] <- value
  }
  list(data = data, mapping = map, source_sha256 = s$sha256, source_path = path,
       source_format = s$format, id = id_target, missing_audit = missing_audit)
}

ch7_entry_model_args <- function(model) {
  ch7_entry_assert(model$family %in% c("lpa", "lta", "mslta"), "Unknown mixture family")
  positive <- function(x) is.numeric(x) && length(x) == 1L && is.finite(x) && x == trunc(x) && x > 0
  ch7_entry_assert(positive(model$classes) && positive(model$processors), "Classes/processors must be positive integers")
  ch7_entry_assert(is.logical(model$invariant) && length(model$invariant) == 1L && !is.na(model$invariant), "Explicit logical invariant required")
  ch7_entry_assert(is.logical(model$transitions) && length(model$transitions) == 1L && !is.na(model$transitions),
    "Explicit logical transitions required")
  ch7_entry_assert(ch7_entry_scalar(model$starts) && grepl("^[0-9]+( +[0-9]+)?$", model$starts), "Invalid starts specification")
  ch7_entry_assert(ch7_entry_scalar(model$estimator) && toupper(model$estimator) %in% c("ML", "MLR"), "Estimator must be ML or MLR")
  args <- model[c("family", "classes", "invariant", "transitions", "starts", "estimator", "processors")]
  if (!is.null(model$stayer)) {
    st <- unlist(model$stayer, use.names = TRUE)
    ch7_entry_assert(is.numeric(st) && identical(sort(names(st)), c("intercept", "slope")) && all(is.finite(st)), "Invalid stayer logits")
    args$stayer <- st
  }
  for (name in c("seed", "optseed")) if (!is.null(model[[name]]))
    ch7_entry_assert(positive(model[[name]]) && model[[name]] <= 2147483647, paste("Invalid", name))
  args
}

# 对对象而非已打印输入补充显式随机种子与 ID；不变更测量语义和协方差。
ch7_entry_finish_object <- function(built, model, id) {
  id_index <- match(toupper(id), toupper(names(built$data)))
  ch7_entry_assert(length(id_index) == 1L && !is.na(id_index), "ID column missing from compiled data")
  id <- names(built$data)[id_index]
  if (!grepl("(?i)IDVARIABLE\\s*(=|IS)", built$object$VARIABLE, perl = TRUE))
    built$object$VARIABLE <- paste(built$object$VARIABLE, paste0("IDVARIABLE = ", id, ";"), sep = "\n")
  if (!is.null(model$seed)) built$object$ANALYSIS <- paste(built$object$ANALYSIS,
    paste0("STSEED = ", format(model$seed, scientific = FALSE, trim = TRUE), ";"), sep = "\n")
  if (!is.null(model$optseed)) built$object$ANALYSIS <- paste(built$object$ANALYSIS,
    paste0("OPTSEED = ", format(model$optseed, scientific = FALSE, trim = TRUE), ";"), sep = "\n")
  built$object$TITLE <- paste0("Chapter 7 configured ", model$id, ";")
  built$object$SAVEDATA <- "FILE = posterior.dat; SAVE = CPROBABILITIES;"
  # 写DAT时需要单独定位ID列；将其加入规格元数据，不改变模型变量或数值。
  built$spec$id <- id
  built
}

ch7_entry_write_model <- function(built, folder, syntax_runtime) {
  ch7_entry_assert(dir.create(folder, recursive = FALSE, showWarnings = FALSE), "Cannot create fresh model directory")
  old <- getwd(); on.exit(setwd(old)); setwd(folder)
  MplusAutomation::mplusModeler(built$object, dataout = "source.dat", modelout = "model.inp",
    run = 0L, check = FALSE, hashfilename = FALSE, writeData = "always", quiet = TRUE,
    Mplus_command = "FORBIDDEN_COMPILE_ONLY", killOnFail = FALSE)
  # MplusAutomation 的默认 fwrite 可能以有限显示精度写大整数 ID。
  # 这里用17位有效数字重写全部数值；ID 用整数字面文本，并在成功回执前逐值核原字节语义。
  id <- built$spec$id
  ch7_entry_assert(ch7_entry_scalar(id) && id %in% names(built$data), "Compiled data needs an explicit ID column")
  format_value <- function(value, is_id = FALSE) {
    if (is.na(value)) return(".")
    if (is_id) {
      ch7_entry_assert(is.finite(value) && value == trunc(value) && abs(value) <= 2^53,
        "ID cannot be represented as an exact finite integer")
      token <- format(value, scientific = FALSE, trim = TRUE, digits = 22)
      ch7_entry_assert(grepl("^[+-]?[0-9]+$", token), "ID serialization did not produce an integer literal")
      return(token)
    }
    token <- sprintf("%.17g", value)
    ch7_entry_assert(grepl("^[+-]?([0-9]+(\\.[0-9]*)?|\\.[0-9]+)([eE][+-]?[0-9]+)?$", token),
      "Numeric serialization produced an invalid token")
    token
  }
  id_index <- match(id, names(built$data))
  tokens <- lapply(seq_len(nrow(built$data)), function(i)
    vapply(seq_along(built$data), function(j) format_value(built$data[[j]][[i]], j == id_index), ""))
  lines <- vapply(tokens, paste, "", collapse = " ")
  writeBin(charToRaw(paste0(paste(lines, collapse = "\n"), "\n")), "source.dat")
  # 所有列按17位文本逐 token 核验；ID另作无容差的整数与唯一性检查。
  raw_lines <- readLines("source.dat", warn = FALSE)
  fields <- strsplit(trimws(raw_lines), "[[:space:]]+")
  ch7_entry_assert(length(fields) == nrow(built$data) &&
    all(vapply(fields, length, integer(1)) == ncol(built$data)),
    "Compiled DAT row/column shape changed")
  ch7_entry_assert(identical(unname(unlist(fields)), unname(unlist(tokens))),
    "Compiled DAT numeric tokens or column order changed")
  expected_id <- vapply(built$data[[id]], format_value, "", is_id = TRUE)
  actual_id <- vapply(fields, `[[`, "", id_index)
  ch7_entry_assert(identical(actual_id, expected_id) && !anyDuplicated(actual_id),
    "Compiled DAT ID tokens changed or became duplicated")
  id_back <- suppressWarnings(as.numeric(actual_id))
  ch7_entry_assert(length(id_back) == length(built$data[[id]]) &&
    identical(id_back, as.numeric(built$data[[id]])) && !anyDuplicated(id_back),
    "Compiled DAT ID numeric readback is not exact and unique")
  back <- utils::read.table("source.dat", header = FALSE, na.strings = ".", colClasses = "numeric",
    comment.char = "", quote = "", check.names = FALSE)
  expected_values <- as.numeric(as.matrix(built$data)); actual_values <- as.numeric(as.matrix(back))
  # R的十进制解析器在长小数上可能相差数个ULP；文本保真已独立检查。
  # 此机器精度核验只适用于连续数值，绝不替代上面ID的精确检查。
  close_values <- length(actual_values) == length(expected_values) &&
    all((is.na(actual_values) & is.na(expected_values)) |
      (!is.na(actual_values) & !is.na(expected_values) &
       abs(actual_values - expected_values) <= 4 * .Machine$double.eps *
         pmax(abs(expected_values), .Machine$double.xmin)))
  ch7_entry_assert(identical(dim(back), dim(built$data)) && close_values,
    "Compiled DAT numeric readback differs beyond machine precision")
  # 对完整成品（含MplusAutomation添加的NAMES/TITLE等）安全换行并再核90列。
  wrapped <- syntax_runtime$ch7_wrap_mplus_lines(readLines("model.inp", warn = FALSE), width = 90L)
  writeLines(wrapped, "model.inp", useBytes = TRUE)
  syntax_runtime$ch7_validate_input_width("model.inp")
  text <- paste(readLines("model.inp", warn = FALSE), collapse = "\n")
  ch7_entry_assert(!grepl("FORBIDDEN_COMPILE_ONLY", text, fixed = TRUE), "Unexpected engine marker in input")
  list(input_sha256 = ch7_entry_sha("model.inp"), data_sha256 = ch7_entry_sha("source.dat"),
    rows = nrow(back), columns = ncol(back), column_names = names(built$data), spec = built$spec)
}

# 归档路径替换保留 CRLF、空格、注释和所有非路径字节；仅接受一个 DATA FILE 和至多一个 SAVEDATA FILE。
ch7_entry_replay_paths <- function(text) {
  ch7_entry_assert(is.character(text) && length(text) == 1L && !is.na(text), "One archived input text required")
  # 注释遮罩保持字符长度；带引号的路径内 ! 仍是路径字符。
  chars <- strsplit(text, "", fixed = TRUE)[[1L]]; masked <- chars
  quote <- ""; comment <- FALSE
  for (i in seq_along(chars)) {
    x <- chars[i]
    if (x %in% c("\r", "\n")) { comment <- FALSE; next }
    if (comment) { masked[i] <- " "; next }
    if (nzchar(quote)) { if (x == quote) quote <- ""; next }
    if (x %in% c("'", '"')) { quote <- x; next }
    if (x == "!") { comment <- TRUE; masked[i] <- " " }
  }
  ch7_entry_assert(!nzchar(quote), "Unclosed quote in archived input")
  mask <- paste0(masked, collapse = "")
  heading <- "(?im)^[ \\t]*(TITLE|DATA(?:[ \\t]+[A-Za-z]+)?|VARIABLE|DEFINE|ANALYSIS|MODEL(?:[ \\t]+[A-Za-z0-9_]+)?|OUTPUT|SAVEDATA|PLOT|MONTECARLO)[ \\t]*:"
  h <- gregexpr(heading, mask, perl = TRUE)[[1L]]
  ch7_entry_assert(h[1L] > 0L, "Archived input has no recognized sections")
  lens <- attr(h, "match.length")
  names <- toupper(trimws(sub(":$", "", substring(mask, h, h + lens - 1L))))
  ch7_entry_assert(sum(names == "DATA") == 1L && sum(names == "SAVEDATA") <= 1L &&
    !any(names %in% c("MONTECARLO", "DATA IMPUTATION", "DATA MISSING")), "Unsupported or duplicated archived DATA/SAVEDATA sections")
  replacements <- list()
  for (section in c("DATA", "SAVEDATA")) {
    idx <- which(names == section)
    if (!length(idx)) next
    start <- h[idx] + lens[idx]; finish <- if (idx < length(h)) h[idx + 1L] - 1L else nchar(text)
    block <- substr(mask, start, finish)
    if (section == "DATA") ch7_entry_assert(!grepl("(?i)\\bTYPE\\s*(?:=|IS)\\s*IMPUTATION\\b", block, perl = TRUE),
      "Archived replay supports one concrete DAT, not an imputation file list")
    if (section == "SAVEDATA") {
      statements <- trimws(strsplit(block, ";", fixed = TRUE)[[1L]])
      statements <- statements[nzchar(statements)]
      ch7_entry_assert(all(grepl("(?i)^(FILE|SAVE|FORMAT|MISSFLAG|RECORDLENGTH)\\b", statements, perl = TRUE)),
        "Archived SAVEDATA has an output target outside the FILE whitelist")
    }
    pattern <- "(?i)\\bFILE[ \\t\\r\\n]*(?:=|IS)[ \\t\\r\\n]*(\"[^\"\\r\\n]*\"|'[^'\\r\\n]*'|[^;\\r\\n]+?)[ \\t\\r\\n]*;"
    found <- gregexpr(pattern, block, perl = TRUE)[[1L]]
    ch7_entry_assert(found[1L] > 0L && length(found) == 1L, paste("Exactly one FILE required in", section))
    part <- substr(block, found[1L], found[1L] + attr(found, "match.length")[1L] - 1L)
    cap <- regexec(pattern, part, perl = TRUE)[[1L]]
    from <- start + found[1L] - 1L + cap[2L] - 1L
    to <- from + attr(cap, "match.length")[2L] - 1L
    old <- substr(text, from, to)
    ch7_entry_assert(nzchar(gsub("^['\"]|['\"]$", "", old)), "Empty archived FILE path")
    replacements[[section]] <- list(from = from, to = to, original = old,
      replacement = if (section == "DATA") '"source.dat"' else '"posterior.dat"')
  }
  all_files <- gregexpr("(?i)\\bFILE\\s*(?:=|IS)\\s*", mask, perl = TRUE)[[1L]]
  ch7_entry_assert(all_files[1L] > 0L && length(all_files) == length(replacements),
    "FILE targets outside DATA/SAVEDATA are unsupported")
  # 指令可能紧随另一条语句分号；不得只查行首而漏掉 inline INCLUDE。
  command_mask <- gsub("\"[^\"]*\"|'[^']*'", "", mask, perl = TRUE)
  ch7_entry_assert(!grepl("(?im)(^|[;:])[ \\t\\r\\n]*(INCLUDE|INCLUDEFILE)\\b", command_mask, perl = TRUE),
    "External include files are unsupported")
  # 从右到左替换，原字符串的位置不受前面变化影响。
  result <- text
  for (r in replacements[order(vapply(replacements, `[[`, 0, "from"), decreasing = TRUE)])
    result <- paste0(substr(result, 1L, r$from - 1L), r$replacement, substring(result, r$to + 1L))
  # 以原位置切出的非路径片段逐个保留；新文本由这些片段加已声明的替换值组成。
  list(text = result, changes = lapply(replacements, function(r) list(
    original_path_sha256 = digest::digest(r$original, algo = "sha256", serialize = FALSE),
    replacement = r$replacement)), exact_nonpath_preserved = TRUE)
}

ch7_entry_replay <- function(model, folder) {
  ch7_entry_fields(model, c("id", "inp", "inp_sha256", "dat", "dat_sha256"), label = "historical model")
  inp <- ch7_entry_file(model$inp, model$inp_sha256)
  dat <- ch7_entry_file(model$dat, model$dat_sha256)
  text <- rawToChar(readBin(inp, "raw", n = file.info(inp)$size))
  rewritten <- ch7_entry_replay_paths(text)
  ch7_entry_assert(dir.create(folder, recursive = FALSE, showWarnings = FALSE), "Cannot create fresh replay directory")
  ch7_entry_assert(file.copy(dat, file.path(folder, "source.dat"), overwrite = FALSE), "Archived DAT copy failed")
  writeBin(charToRaw(rewritten$text), file.path(folder, "model.inp"))
  ch7_entry_assert(identical(ch7_entry_sha(file.path(folder, "source.dat")), model$dat_sha256) &&
    identical(ch7_entry_sha(inp), model$inp_sha256) && identical(ch7_entry_sha(dat), model$dat_sha256),
    "Archived input/data changed during replay preparation")
  list(input_sha256 = ch7_entry_sha(file.path(folder, "model.inp")), data_sha256 = model$dat_sha256,
    source_input_sha256 = model$inp_sha256, changes = rewritten$changes,
    exact_nonpath_preserved = TRUE, status = "PREPARED_ARCHIVED_REPLAY_NO_ENGINE")
}

ch7_source_entry <- function(config, output_dir, skill_root = NULL) {
  for (p in c("MplusAutomation", "digest", "jsonlite"))
    ch7_entry_assert(requireNamespace(p, quietly = TRUE), paste("Missing package:", p))
  config_file_sha <- NULL
  config_path <- NULL
  if (is.character(config) && length(config) == 1L) {
    config_path <- normalizePath(config, winslash = "/", mustWork = TRUE)
    config_file_sha <- ch7_entry_sha(config)
    config <- jsonlite::read_json(config, simplifyVector = FALSE)
    ch7_entry_file(config_path, config_file_sha)
  }
  ch7_entry_fields(config, c("schema_version", "mode", "models"),
    c("source", "sample", "transformations", "waves", "mapping", "id_target", "step1"), "config")
  ch7_entry_assert(config$schema_version == 1 && ch7_entry_scalar(config$mode) &&
    config$mode %in% c("new_source", "historical_replay", "step3_from_output"), "Unsupported config version/mode")
  mode_fields <- switch(config$mode, new_source = c("source", "sample", "transformations", "waves", "mapping", "id_target"),
    step3_from_output = "step1", historical_replay = character())
  ch7_entry_fields(config, c("schema_version", "mode", "models", mode_fields), label = "mode-specific config")
  link <- Sys.readlink(output_dir)
  ch7_entry_assert(ch7_entry_scalar(output_dir) && !file.exists(output_dir) &&
    !dir.exists(output_dir) && (is.na(link) || !nzchar(link)), "Fresh output directory required")
  if (is.null(skill_root)) script_dir <- ch7_entry_script_dir else {
    script_dir <- if (file.exists(file.path(skill_root, "ch7_mixture_syntax.R"))) skill_root else file.path(skill_root, "scripts")
  }
  ch7_entry_assert(!is.null(script_dir) && file.exists(file.path(script_dir, "ch7_mixture_syntax.R")), "Resolve skill_root explicitly")
  runtime <- new.env(parent = environment(ch7_source_entry))
  scripts <- c("ch7_mixture_tools.R", "ch7_mixture_syntax.R")
  if (config$mode == "step3_from_output") scripts <- c(scripts, "ch7_step_chain_20261111.R")
  for (script in scripts) sys.source(file.path(script_dir, script), envir = runtime)
  code_sha <- setNames(lapply(scripts, function(p) ch7_entry_sha(file.path(script_dir, p))), scripts)
  self <- file.path(script_dir, "ch7_source_entry_20261111.R")
  if (file.exists(self)) code_sha[[basename(self)]] <- ch7_entry_sha(self)
  models <- ch7_entry_records(config$models, "models")
  ids <- vapply(models, function(m) if (ch7_entry_scalar(m$id)) m$id else "", "")
  ch7_entry_assert(all(grepl("^[A-Za-z][A-Za-z0-9_-]{0,79}$", ids)) && !anyDuplicated(tolower(ids)), "Unique safe model IDs required")
  data_source <- NULL; built <- list(); chains <- list()
  model_required <- c("id", "family", "classes", "invariant", "transitions", "starts", "estimator", "processors")
  if (config$mode == "new_source") {
    ch7_entry_assert(is.null(config$step1), "new_source cannot carry prior Step-1 outputs")
    data_source <- ch7_entry_read_source(config)
    waves <- ch7_entry_records(config$waves, "waves")
    for (w in waves) {
      ch7_entry_fields(w, c("wave", "label", "time"), label = "waves")
      ch7_entry_assert(ch7_entry_scalar(w$wave) && ch7_entry_scalar(w$label) && is.numeric(w$time) &&
        length(w$time) == 1L && is.finite(w$time), "Wave ID/label/time must be explicit")
    }
    wave_ids <- vapply(waves, `[[`, "", "wave")
    ch7_entry_assert(!anyDuplicated(wave_ids) && all(diff(vapply(waves, `[[`, 0, "time")) > 0), "Wave order must have strictly increasing times")
    ch7_entry_assert(all(vapply(data_source$mapping, function(m) m$wave %in% wave_ids, logical(1))), "Mapping contains an undeclared wave")
    for (model in models) {
      ch7_entry_fields(model, c(model_required, "wave_ids", "roles"), c("seed", "optseed", "stayer"), "model")
      args <- ch7_entry_model_args(model)
      selected_waves <- ch7_entry_vector(model$wave_ids); roles <- ch7_entry_vector(model$roles)
      ch7_entry_assert(is.character(selected_waves) && length(selected_waves) > 0L &&
        !anyDuplicated(selected_waves) && all(selected_waves %in% wave_ids) &&
        all(diff(match(selected_waves, wave_ids)) > 0), "Model waves must be unique and follow declared chronology")
      ch7_entry_assert(is.character(roles) && length(roles) > 0L && !anyNA(roles) && !anyDuplicated(roles), "Explicit unique role combination required")
      selected <- lapply(selected_waves, function(w) {
        m <- Filter(function(x) x$wave == w && x$role %in% roles, data_source$mapping)
        ch7_entry_assert(length(m) == length(roles), "Each selected wave must supply each requested role")
        m[match(roles, vapply(m, `[[`, "", "role"))]
      })
      args$waves <- lapply(selected, function(m) vapply(m, `[[`, "", "target"))
      flat <- unlist(selected, recursive = FALSE)
      args$categorical <- vapply(Filter(function(m) m$type != "continuous", flat), `[[`, "", "target")
      args$keep <- c(data_source$id, unlist(args$waves, use.names = FALSE))
      args$data <- data_source$data[, args$keep, drop = FALSE]
      built[[model$id]] <- ch7_entry_finish_object(do.call(runtime$ch7_mixture_object, args), model, data_source$id)
    }
  } else if (config$mode == "step3_from_output") {
    ch7_entry_assert(is.null(config$source), "Step-3 source must be its bound Step-1 savedata")
    s <- config$step1
    ch7_entry_fields(s, c("out", "savedata", "out_sha256", "savedata_sha256", "id", "nominal_map", "latent", "classes"), "keep", "step1")
    ch7_entry_file(s$out, s$out_sha256); ch7_entry_file(s$savedata, s$savedata_sha256)
    nominal_map <- unlist(s$nominal_map, use.names = TRUE)
    latent <- ch7_entry_vector(s$latent)
    for (model in models) {
      ch7_entry_fields(model, model_required, c("seed", "optseed", "stayer"), "step3 model")
      args <- ch7_entry_model_args(model)
      ch7_entry_assert(model$classes == s$classes, "Step-3 K must equal its Step-1 K")
      args$step1_out <- s$out; args$step1_savedata <- s$savedata
      args$id <- s$id; args$nominal_map <- nominal_map; args$latent <- latent
      args$keep <- ch7_entry_vector(s$keep)
      chains[[model$id]] <- do.call(runtime$ch7_step3_from_step1, args)
      built[[model$id]] <- ch7_entry_finish_object(chains[[model$id]], model, s$id)
    }
    ch7_entry_file(s$out, s$out_sha256); ch7_entry_file(s$savedata, s$savedata_sha256)
  } else {
    ch7_entry_assert(is.null(config$source) && is.null(config$step1), "Archived replay does not regenerate or reinterpret source data")
    for (m in models) {
      ch7_entry_fields(m, c("id", "inp", "inp_sha256", "dat", "dat_sha256"), label = "historical model")
      ch7_entry_file(m$inp, m$inp_sha256); ch7_entry_file(m$dat, m$dat_sha256)
      ch7_entry_replay_paths(rawToChar(readBin(m$inp, "raw", n = file.info(m$inp)$size)))
    }
  }
  ch7_entry_assert(dir.create(output_dir, recursive = TRUE, showWarnings = FALSE), "Cannot create fresh output directory")
  output_dir <- normalizePath(output_dir, winslash = "/", mustWork = TRUE)
  artifacts <- list(); model_paths <- list()
  for (model in models) {
    folder <- file.path(output_dir, model$id)
    info <- if (config$mode == "historical_replay") ch7_entry_replay(model, folder) else
      ch7_entry_write_model(built[[model$id]], folder, runtime)
    model_paths[[model$id]] <- list(input = file.path(folder, "model.inp"), data = file.path(folder, "source.dat"))
    if (config$mode == "step3_from_output") {
      info$lineage <- runtime$ch7_step3_chain_receipt(chains[[model$id]], model_paths[[model$id]]$input,
        model_paths[[model$id]]$data)
    }
    artifacts[[model$id]] <- c(list(model_id = model$id, input = paste0(model$id, "/model.inp"),
      data = paste0(model$id, "/source.dat")), info)
  }
  if (!is.null(data_source)) ch7_entry_file(data_source$source_path, data_source$source_sha256)
  if (!is.null(config_path)) ch7_entry_file(config_path, config_file_sha)
  for (script in names(code_sha)) ch7_entry_assert(identical(ch7_entry_sha(file.path(script_dir, script)), code_sha[[script]]),
    "Loaded compilation code changed during preparation")
  manifest <- list(schema = "ch7-source-entry/1", mode = config$mode, status = "PREPARED_NO_ENGINE",
    config_sha256 = if (is.null(config_file_sha)) digest::digest(config, algo = "sha256") else config_file_sha,
    code_sha256 = code_sha, engine_calls = 0L, engine_acceptance = FALSE, statistical_acceptance = FALSE,
    source_sha256 = if (!is.null(data_source)) data_source$source_sha256 else NULL,
    source_contract = if (!is.null(data_source)) config$source[setdiff(names(config$source), "path")] else NULL,
    sample = if (!is.null(data_source)) config$sample else NULL,
    mapping = if (!is.null(data_source)) config$mapping else NULL,
    missing_audit = if (!is.null(data_source)) data_source$missing_audit else NULL,
    waves = if (!is.null(data_source)) config$waves else NULL,
    transformations = if (!is.null(data_source)) config$transformations else NULL,
    rows_removed = 0L, row_order = "source", model_count = length(artifacts), artifacts = artifacts,
    R = as.character(getRversion()), MplusAutomation = as.character(utils::packageVersion("MplusAutomation")),
    boundary = "Compile-only; run through authorized execution layer; preserve native diagnostics and compare fresh outputs separately")
  jsonlite::write_json(manifest, file.path(output_dir, "manifest.json"), auto_unbox = TRUE, pretty = TRUE, digits = NA)
  invisible(list(manifest = manifest, output_dir = output_dir, models = model_paths, chains = chains))
}

if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) != 2L) stop("Usage: Rscript ch7_source_entry_20261111.R config.json fresh-output-dir")
  file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
  skill_root <- file.path(dirname(sub("^--file=", "", file_arg[[1L]])), "..")
  result <- ch7_source_entry(args[[1L]], args[[2L]], skill_root)
  cat("CH7_SOURCE_PREPARED", result$manifest$model_count, "models; engine_calls=0\n")
}
