# 第七章 Step-1→Step-3 自动链：只读已结束的输出，保留打印 logit 和明确来源，不运行引擎。
# 先 source ch7_mixture_tools.R 和 ch7_mixture_syntax.R；由获准的共用 RStudio 执行层估计。

ch7_chain_sha <- function(path) digest::digest(file = path, algo = "sha256")

# 有输入警告时 Mplus 不一定打印 INPUT READING TERMINATED NORMALLY，仍按 SUMMARY 边界读输入。
ch7_step1_input <- function(text) {
  begin <- grep("^\\s*INPUT INSTRUCTIONS\\s*$", text)
  end <- grep("^\\s*(INPUT READING TERMINATED NORMALLY|SUMMARY OF ANALYSIS)\\s*$", text)
  if (length(begin) != 1L || !length(end) || min(end) <= begin) stop("Cannot delimit Step-1 INPUT section")
  ch7_inp_sections(text[begin:(min(end) - 1L)])
}

# Mplus 的表可按列分页；每个真类别/赋类单元恰好出现一次，不能补零或转置。
ch7_classification_table <- function(lines, K, first_line = 1L) {
  values <- matrix(NA_real_, K, K); bounds <- values
  columns <- integer(); source_rows <- integer()
  number <- "^[+-]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[EeDd][+-]?[0-9]+)?$"
  half_unit <- function(token) {
    pieces <- strsplit(toupper(gsub("D", "E", token)), "E", fixed = TRUE)[[1]]
    digits <- if (grepl(".", pieces[1], fixed = TRUE)) nchar(sub("^[^.]*\\.", "", pieces[1])) else 0L
    exponent <- if (length(pieces) == 2L) as.integer(pieces[2]) else 0L
    .5 * 10^(exponent - digits)
  }
  for (i in seq_along(lines)) {
    line <- trimws(lines[i]); if (!nzchar(line)) next
    if (grepl("^by Latent Class \\(Row\\)$", line)) next
    tokens <- strsplit(line, "\\s+")[[1]]
    if (all(grepl("^[0-9]+$", tokens))) {
      columns <- as.integer(tokens)
      if (anyDuplicated(columns) || any(!columns %in% seq_len(K))) stop("Invalid classification column labels")
      next
    }
    if (grepl("^[0-9]+$", tokens[1])) {
      row <- as.integer(tokens[1])
      if (!length(columns) || !row %in% seq_len(K) || length(tokens) != length(columns) + 1L ||
          any(!grepl(number, tokens[-1], perl = TRUE))) stop("Malformed classification row")
      if (any(!is.na(values[row, columns]))) stop("Duplicate classification cell")
      values[row, columns] <- as.numeric(gsub("[dD]", "E", tokens[-1]))
      bounds[row, columns] <- vapply(tokens[-1], half_unit, numeric(1))
      source_rows <- c(source_rows, first_line + i - 1L)
      next
    }
    if (any(!is.na(values))) break
    stop("Unexpected classification table text")
  }
  if (anyNA(values) || any(!is.finite(values))) stop("Incomplete or nonfinite classification table")
  dimnames(values) <- dimnames(bounds) <- list(as.character(seq_len(K)), as.character(seq_len(K)))
  list(values = values, half_unit = bounds, rows = source_rows)
}

# 只使用 P(赋类|真类) 的打印 logit；平均后验 P(真类|赋类) 不是同一张表。
ch7_classification_error <- function(step1_out, latent, classes) {
  if (!file.exists(step1_out)) stop("Missing Step-1 output")
  if (!is.character(latent) || !length(latent) || anyNA(latent) ||
      any(!grepl("^[A-Za-z][A-Za-z0-9_]{0,7}$", latent)) || anyDuplicated(toupper(latent)))
    stop("latent must give distinct ordered class-variable names")
  if (!is.numeric(classes) || length(classes) != 1L || !is.finite(classes) ||
      classes != round(classes) || classes < 2L) stop("classes must be one integer >= 2")
  K <- as.integer(classes); latent <- toupper(latent)
  text <- readLines(step1_out, warn = FALSE)
  if (!any(trimws(text) == "THE MODEL ESTIMATION TERMINATED NORMALLY")) stop("Step-1 did not terminate normally")
  scopes <- grep("^\\s*Classification Quality for [A-Za-z][A-Za-z0-9_]*\\s*$", text)
  names_scope <- toupper(sub("^\\s*Classification Quality for ", "", trimws(text[scopes])))
  if (anyDuplicated(names_scope)) stop("Duplicate classification-quality sections")
  if (!all(latent %in% names_scope)) stop("A requested latent class variable has no classification section")
  # 输出中的类数同时与 INPUT 中声明核对；不只依靠某张表的维数。
  sec <- ch7_step1_input(text)
  declared <- ch7_classes(ch7_option(ch7_statements(sec$VARIABLE), "CLASSES"))
  if (anyDuplicated(names(declared)) || !all(latent %in% names(declared)) || any(declared[latent] != K))
    stop("Requested latent variables/classes disagree with Step-1 INPUT")
  logits <- error <- printed <- provenance <- stats::setNames(vector("list", length(latent)), latent)
  probability_heading <- "Classification Probabilities for the Most Likely Latent Class Membership (Column)"
  logit_heading <- paste("Logits for the", probability_heading)
  for (v in latent) {
    at <- match(v, names_scope); begin <- scopes[at]
    end <- if (at < length(scopes)) scopes[at + 1L] - 1L else length(text)
    block <- text[begin:end]
    p_at <- which(trimws(block) == probability_heading)
    z_at <- which(trimws(block) == logit_heading)
    if (length(p_at) != 1L || length(z_at) != 1L || p_at >= z_at)
      stop("Expected exactly one forward-probability and one logit table for ", v)
    # 每张表第一条非空下行必须说明真类别是行，防止方向标记被替换。
    parse_at <- function(index) {
      tail <- block[(index + 1L):length(block)]
      nonempty <- which(nzchar(trimws(tail)))
      if (!length(nonempty) || trimws(tail[nonempty[1]]) != "by Latent Class (Row)")
        stop("Classification table orientation is not assigned columns / latent rows")
      ch7_classification_table(tail, K, begin + index)
    }
    p <- parse_at(p_at); z <- parse_at(z_at)
    if (any(z$values[, K] != 0)) stop("Printed logit reference column must be class K with zero logits")
    if (any(p$values < 0 | p$values > 1) || any(abs(rowSums(p$values) - 1) > rowSums(p$half_unit) + 1e-12))
      stop("Invalid printed classification probabilities")
    weights <- exp(z$values - apply(z$values, 1L, max)); prob <- weights / rowSums(weights)
    # softmax 每个坐标对所有非参考 logits 的绝对梯度和 <= 1/2。
    # 两张表都经过打印舍入：概率半单位 + logit误差传播上界；不做任意宽容差。
    bound <- p$half_unit + .5 * apply(z$half_unit[, -K, drop = FALSE], 1L, max) + 1e-12
    if (any(abs(prob - p$values) > bound)) stop("Forward probability table conflicts with printed logits")
    logits[[v]] <- z$values[, -K, drop = FALSE]; error[[v]] <- prob; printed[[v]] <- p$values
    rows <- sort(unique(c(begin + c(p_at, z_at) - 1L, p$rows, z$rows)))
    provenance[[v]] <- list(latent = v, classes = K, reference_class = K,
      direction = "P(assigned class | latent class); rows=latent; columns=assigned",
      logit_heading_line = begin + z_at - 1L, logit_value_lines = z$rows,
      probability_heading_line = begin + p_at - 1L, probability_value_lines = p$rows,
      selected_text_sha256 = digest::digest(paste(text[rows], collapse = "\n"), algo = "sha256", serialize = FALSE),
      max_probability_rounding_difference = max(abs(prob - p$values)))
  }
  list(logits = logits, error = error, printed_probability = printed,
       source = list(file = basename(step1_out), sha256 = ch7_chain_sha(step1_out),
         extraction = "Mplus printed classification logits; no probability smoothing",
         tables = provenance),
       diagnostics = list(normal_termination = TRUE,
         warning_lines = grep("WARNING|STANDARD ERRORS.*COULD NOT|NON-POSITIVE DEFINITE|PARAMETERS.*FIXED", text),
         inference_accepted = FALSE))
}

# 兼容 Save file 在变量序之前/之后；格式读取交给同一既有解析器。
ch7_step1_savedata_info <- function(text) {
  info <- ch7_savedata_info(text)
  if (is.null(info)) stop("Missing or malformed SAVEDATA INFORMATION")
  if (anyDuplicated(info$names)) stop("Duplicate savedata column names")
  info
}

ch7_read_step1_savedata <- function(path, info) {
  lines <- readLines(path, warn = FALSE)
  if (!length(lines) || any(!nzchar(trimws(lines)))) stop("Savedata contains empty records")
  widths <- as.integer(sub("^[FEG]([0-9]+)\\..*$", "\\1", info$formats))
  if (length(widths) != length(info$names) || anyNA(widths) || any(widths <= 0L)) stop("Unsupported savedata format")
  # 优先严格固定宽度，能正确读相邻的负值。外部自由格式必须每行恰好同样列数。
  fixed <- all(nchar(lines, type = "chars") == sum(widths))
  if (fixed) {
    ends <- cumsum(widths); starts <- c(1L, head(ends, -1L) + 1L)
    tokens <- lapply(lines, function(line) trimws(substring(line, starts, ends)))
  } else tokens <- strsplit(trimws(lines), "\\s+")
  if (any(lengths(tokens) != length(info$names))) stop("Savedata width differs from its declared variable order")
  number <- "^[+-]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[EeDd][+-]?[0-9]+)?$"
  raw <- matrix(unlist(tokens), ncol = length(info$names), byrow = TRUE)
  missing <- raw %in% c("*", ".")
  if (any(!missing & !grepl(number, raw, perl = TRUE))) stop("Savedata has nonnumeric or overflow values")
  raw[missing] <- NA_character_
  data <- matrix(as.numeric(gsub("[dD]", "E", raw)), nrow(raw), ncol(raw), dimnames = list(NULL, info$names))
  if (any(!is.na(data) & !is.finite(data))) stop("Savedata contains nonfinite values")
  as.data.frame(data, check.names = FALSE)
}

ch7_step3_from_step1 <- function(step1_out, step1_savedata = NULL, id, nominal_map, latent, classes,
                                family = c("lta", "mslta"), keep = NULL, ...) {
  family <- match.arg(family)
  extracted <- ch7_classification_error(step1_out, latent, classes)
  info <- ch7_step1_savedata_info(readLines(step1_out, warn = FALSE))
  declared <- ch7_data_path(info$file, dirname(step1_out))
  if (is.null(step1_savedata)) step1_savedata <- declared
  if (!identical(normalizePath(step1_savedata, winslash = "/", mustWork = TRUE), declared))
    stop("Step-1 SAVEDATA declaration does not identify the supplied file")
  d <- ch7_read_step1_savedata(step1_savedata, info)
  if (!is.character(id) || length(id) != 1L || is.na(id)) stop("id must be one savedata column")
  id <- toupper(id)
  if (!id %in% names(d) || anyNA(d[[id]]) || anyDuplicated(d[[id]]) ||
      any(d[[id]] != round(d[[id]]) | abs(d[[id]]) > 2^53)) stop("Savedata needs unique exact nonmissing integer IDs")
  if (!is.character(nominal_map) || is.null(names(nominal_map)) || length(nominal_map) != length(latent) ||
      length(latent) < 2L || anyNA(nominal_map) || anyNA(names(nominal_map)) ||
      any(!grepl("^[A-Za-z][A-Za-z0-9_]{0,7}$", names(nominal_map))) ||
      anyDuplicated(toupper(names(nominal_map))) || anyDuplicated(toupper(unname(nominal_map))))
    stop("nominal_map must uniquely name one output variable per ordered latent variable")
  source <- toupper(unname(nominal_map)); nominal <- names(nominal_map)
  if (!all(source %in% names(d))) stop("nominal_map refers to unavailable savedata columns")
  # 多潜变量的 MLCCn 以声明的 CLASSES 顺序编号，不能把联合类 MLCJOINT 当某波类。
  sec <- ch7_step1_input(readLines(step1_out, warn = FALSE))
  if (!identical(toupper(ch7_option(ch7_statements(sec$VARIABLE), "IDVARIABLE")), id))
    stop("id must match the IDVARIABLE declared in Step-1 INPUT")
  declared_classes <- ch7_classes(ch7_option(ch7_statements(sec$VARIABLE), "CLASSES"))
  expected_source <- paste0("MLCC", match(toupper(latent), names(declared_classes)))
  if (!identical(source, expected_source)) stop("nominal_map must match each latent variable's declared MLCC position")
  for (column in source) if (anyNA(d[[column]]) || !all(d[[column]] %in% seq_len(classes)))
    stop("Most-likely classifications must be nonmissing integers in 1..K")
  keep <- unique(c(id, toupper(keep)))
  if (!all(keep %in% names(d)) || any(toupper(nominal) %in% keep)) stop("keep columns missing or collide with nominal output names")
  data <- d[, keep, drop = FALSE]
  for (i in seq_along(nominal)) data[[nominal[i]]] <- d[[source[i]]]
  step3 <- list(nominal = nominal, logits = unname(extracted$logits))
  built <- ch7_mixture_object(data, family = family, classes = classes, step3 = step3, keep = names(data), ...)
  built$object$VARIABLE <- paste(built$object$VARIABLE, paste0("IDVARIABLE = ", id, ";"), sep = "\n")
  built$step3 <- step3
  built$lineage <- list(status = "COMPILED_FROM_STEP1_PRINTED_LOGITS_NOT_ESTIMATED", source = extracted$source,
    savedata = list(file = basename(step1_savedata), sha256 = ch7_chain_sha(step1_savedata),
      columns = info$names, formats = info$formats), id_column = id,
    rows = nrow(data), output_columns = names(data),
    mapping = data.frame(latent = toupper(latent), nominal = nominal, savedata = source),
    diagnostics = extracted$diagnostics,
    input_paths = list(step1_out = normalizePath(step1_out, winslash = "/"),
                       step1_savedata = normalizePath(step1_savedata, winslash = "/")))
  # 运行时路径仅保留在独立私有字段，公开 receipt 不携带机器绝对路径。
  built$private_paths <- built$lineage$input_paths; built$lineage$input_paths <- NULL
  built$error_source <- extracted
  built
}

# 编译后独立核 DATA 绑定、按ID投影和每个固定logit；不把编译通过写成引擎已估计。
ch7_step3_chain_receipt <- function(chain, step3_inp, step3_dat = NULL, value_tolerance = 1e-6) {
  if (!is.numeric(value_tolerance) || length(value_tolerance) != 1L || !is.finite(value_tolerance) || value_tolerance < 0)
    stop("value_tolerance must be finite and nonnegative")
  if (ch7_chain_sha(chain$private_paths$step1_out) != chain$lineage$source$sha256 ||
      ch7_chain_sha(chain$private_paths$step1_savedata) != chain$lineage$savedata$sha256) stop("Step-1 source changed after extraction")
  sec <- ch7_inp_sections(readLines(step3_inp, warn = FALSE)); variable <- ch7_statements(sec$VARIABLE)
  path <- ch7_option(ch7_statements(sec$DATA), "FILE")
  path <- sub("^([\"'])(.*)\\1$", "\\2", path)
  declared <- ch7_data_path(path, dirname(step3_inp))
  if (is.null(step3_dat)) step3_dat <- declared
  if (!identical(normalizePath(step3_dat, winslash = "/", mustWork = TRUE), declared)) stop("Step-3 reads a different DAT")
  names3 <- ch7_varlist(ch7_option(variable, "NAMES"))
  d <- utils::read.table(step3_dat, header = FALSE, na.strings = c("*", "."), colClasses = "numeric")
  if (ncol(d) != length(names3) || anyDuplicated(names3)) stop("Step-3 DAT width or NAMES invalid")
  names(d) <- names3; expected <- chain$data; names(expected) <- toupper(names(expected))
  if (!setequal(names3, names(expected))) stop("Step-3 columns differ from compiled projection")
  missing <- ch7_missing_codes(ch7_option(variable, "MISSING"), names3)
  for (n in names3) d[[n]][d[[n]] %in% missing[[n]]] <- NA_real_
  id <- chain$lineage$id_column
  if (anyNA(d[[id]]) || anyDuplicated(d[[id]]) || !setequal(d[[id]], expected[[id]])) stop("Step-3 ID set changed")
  rows <- match(d[[id]], expected[[id]])
  for (n in names3) {
    a <- d[[n]]; b <- expected[[n]][rows]
    if (!identical(is.na(a), is.na(b)) || any(abs(a[!is.na(a)] - b[!is.na(b)]) > value_tolerance))
      stop("Step-3 projection differs for ", n)
  }
  nominal <- toupper(chain$step3$nominal)
  if (!setequal(ch7_varlist(ch7_option(variable, "NOMINAL"), names3), nominal)) stop("Step-3 nominal declaration changed")
  if (!setequal(ch7_varlist(ch7_option(variable, "USEVARIABLES"), names3), nominal) ||
      !identical(toupper(ch7_option(variable, "IDVARIABLE")), id)) stop("Step-3 analysis variables or ID declaration changed")
  declared_classes <- ch7_classes(ch7_option(variable, "CLASSES"))
  expected_classes <- stats::setNames(rep(chain$spec$classes, length(nominal)), paste0("C", seq_along(nominal)))
  if (chain$spec$family == "mslta") expected_classes <- c(G = 2L, expected_classes)
  if (!setequal(names(declared_classes), names(expected_classes)) ||
      !identical(as.integer(declared_classes[names(expected_classes)]), as.integer(expected_classes)))
    stop("Step-3 class declarations changed")
  blocks <- ch7_model_blocks(sec$MODEL); maxdiff <- 0; cells <- 0L
  for (wave in seq_along(nominal)) {
    target <- chain$step3$logits[[wave]]; K <- nrow(target); found <- matrix(NA_real_, K, K - 1L)
    rx <- paste0("(?i)(?<![A-Za-z0-9_])", nominal[wave], "#([0-9]+)\\s*@\\s*([+-]?[0-9]*\\.?[0-9]+(?:[eE][+-]?[0-9]+)?)")
    for (i in seq_len(nrow(blocks))) {
      hits <- regmatches(blocks$statement[i], gregexpr(rx, blocks$statement[i], perl = TRUE))[[1]]
      for (hit in hits) {
        expected_ns <- paste0("C", wave)
        if (blocks$namespace[i] != expected_ns || !grepl(paste0("^", expected_ns, "#[0-9]+$"), blocks$block[i]))
          stop("Fixed classification logit appears in the wrong latent block")
        row <- as.integer(sub(".*#", "", blocks$block[i])); m <- regmatches(hit, regexec(rx, hit, perl = TRUE))[[1]]
        col <- as.integer(m[2]); value <- as.numeric(m[3])
        if (!row %in% seq_len(K) || !col %in% seq_len(K - 1L) || !is.na(found[row, col])) stop("Invalid or duplicate fixed logit")
        found[row, col] <- value
      }
    }
    if (anyNA(found)) stop("Missing fixed classification logits")
    diff <- max(abs(found - target)); if (diff > 5e-12) stop("Fixed logits differ from Step-1 printed logits")
    maxdiff <- max(maxdiff, diff); cells <- cells + length(target)
  }
  list(status = "PASS_COMPILED_LINEAGE", engine_estimated = FALSE, lineage = chain$lineage,
       step3 = list(inp = list(file = basename(step3_inp), sha256 = ch7_chain_sha(step3_inp)),
                    dat = list(file = basename(step3_dat), sha256 = ch7_chain_sha(step3_dat))),
       rows = nrow(d), columns = ncol(d), logit_cells = cells, max_abs_logit_difference = maxdiff,
       row_order_identical = identical(rows, seq_len(nrow(expected))))
}
