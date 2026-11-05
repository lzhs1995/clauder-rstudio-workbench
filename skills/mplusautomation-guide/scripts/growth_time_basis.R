# 根据真实观测时间生成增长载荷；不替研究者选择趋势或分段点。
growth_time_basis <- function(waves, shape = c("linear", "quadratic", "piecewise"), knot = NULL) {
  shape <- match.arg(shape)
  if (!is.numeric(waves) || length(waves) < 3L || any(!is.finite(waves)) ||
      any(diff(waves) <= 0)) stop("waves must contain at least three strictly increasing finite times")
  time <- waves - waves[1L]
  if (shape != "piecewise" && !is.null(knot)) stop("knot is only used for piecewise growth")
  basis <- switch(shape,
    linear = cbind(intercept = 1, slope = time),
    quadratic = cbind(intercept = 1, slope = time, quadratic = time^2),
    piecewise = {
      if (!is.numeric(knot) || length(knot) != 1L || !is.finite(knot) ||
          knot <= waves[1L] || knot >= waves[length(waves)])
        stop("Specify one interior knot on the original wave-time scale")
      centered_knot <- knot - waves[1L]
      cbind(intercept = 1, before = pmin(time, centered_knot), after = pmax(0, time - centered_knot))
    })
  rownames(basis) <- as.character(waves)
  basis
}

# 把 growth_time_basis() 的载荷写成 Mplus 增长语句（`|` 简写），供研究者审核后放进 MODEL。
# 只写增长因子与时间分数；协变量、残差结构、ANALYSIS 都由研究者另写。
# 返回 list(model, statements, basis, factors)；model 可直接传给 mplus_from_mapping(model = ...)。
growth_model_syntax <- function(waves, aliases, shape = c("linear", "quadratic", "piecewise"), knot = NULL,
                                factors = NULL, width = 80L) {
  shape <- match.arg(shape)
  basis <- growth_time_basis(waves, shape, knot)
  if (any(!is.finite(basis))) stop("Growth loadings must remain finite after centering and transformation")
  if (is.null(factors)) factors <- switch(shape, linear = c("i", "s"), quadratic = c("i", "s", "q"),
                                          piecewise = c("i", "s1", "s2"))
  if (!is.character(aliases) || length(aliases) != length(waves) || anyNA(aliases))
    stop("aliases must name one observed variable per wave")
  names_ok <- function(x) all(grepl("^[A-Za-z][A-Za-z0-9_]{0,7}$", x))
  if (!names_ok(aliases) || anyDuplicated(toupper(aliases)))
    stop("Mplus aliases must be unique, case-insensitive, and at most 8 characters")
  if (!is.character(factors) || length(factors) != ncol(basis) || !names_ok(factors) ||
      anyDuplicated(toupper(factors)) || any(toupper(factors) %in% toupper(aliases)))
    stop("Growth factor names must be valid, unique, and different from the observed aliases")
  if (!is.numeric(width) || length(width) != 1L || width < 40L || width > 90L)
    stop("width must be between 40 and 90 characters (Mplus reads at most 90 per line)")
  # 定点小数：不出现科学计数，去掉末尾的 0
  score <- function(x) {
    text <- formatC(round(x, 10), format = "f", digits = 10)
    text <- sub("0+$", "", text)
    text <- sub("\\.$", "", text)
    # 小间隔不能静默压成同一个时间分数；重复的分段载荷仍然允许。
    if (anyDuplicated(text[!duplicated(x)]))
      stop("Distinct growth loadings collapse at 10 decimal places; rescale the wave-time unit")
    text
  }
  statement <- function(lhs, loadings) {
    tokens <- paste0(aliases, "@", score(loadings))
    # 单个载荷不可拆行；缩进与终止分号也属于行宽。
    if (any(nchar(tokens) + 3L > width))
      stop("A growth loading token cannot fit within width; rescale the wave-time unit or increase width")
    lines <- character(); current <- paste(lhs, "|")
    for (token in tokens) {
      if (nchar(current) + 1L + nchar(token) + 1L > width) {
        lines <- c(lines, current); current <- paste0("  ", token)
      } else current <- paste(current, token)
    }
    paste(c(lines, paste0(current, ";")), collapse = "\n")
  }
  statements <- switch(shape,
    linear = statement(paste(factors[1:2], collapse = " "), basis[, "slope"]),
    # Mplus 的二次项载荷取时间分数的平方，与 basis[, "quadratic"] 一致
    quadratic = statement(paste(factors, collapse = " "), basis[, "slope"]),
    # 分段：两段共用截距因子，前段在分段点之后保持不变，后段在分段点之前为 0
    piecewise = c(statement(paste(factors[1:2], collapse = " "), basis[, "before"]),
                  statement(paste(factors[c(1, 3)], collapse = " "), basis[, "after"])))
  result <- list(model = paste(statements, collapse = "\n"), statements = statements,
                 basis = basis, factors = factors)
  check_growth_statements(result, aliases)
  result
}

# cross-dataset-migration.md 要求的核对：每个观测变量在每条载荷向量里恰好出现一次，载荷与 basis 一致。
check_growth_statements <- function(syntax, aliases) {
  basis <- syntax$basis
  columns <- switch(as.character(ncol(basis)), "2" = "slope", "3" = if ("quadratic" %in% colnames(basis))
    "slope" else c("before", "after"))
  if (is.null(columns) || length(syntax$statements) != length(columns))
    stop("Growth statements do not match the loading basis")
  for (k in seq_along(columns)) {
    body <- sub("^[^|]*\\|", "", gsub("\n", " ", syntax$statements[[k]]))
    tokens <- strsplit(trimws(sub(";\\s*$", "", body)), "\\s+")[[1]]
    variables <- sub("@.*$", "", tokens)
    loadings <- as.numeric(sub("^[^@]*@", "", tokens))
    if (!identical(sort(toupper(variables)), sort(toupper(aliases))) || anyDuplicated(toupper(variables)))
      stop("Each observed variable must appear exactly once in loading vector ", k)
    expected <- basis[match(toupper(variables), toupper(aliases)), columns[[k]]]
    if (anyNA(loadings) || any(abs(loadings - expected) > 1e-9))
      stop("Loadings in statement ", k, " do not match the time basis")
  }
  invisible(TRUE)
}
