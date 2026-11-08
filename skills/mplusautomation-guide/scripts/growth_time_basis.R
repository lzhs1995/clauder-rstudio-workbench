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

# 组合两个过程的固定时间增长语句；返回的 variables/model 交给 mplus_from_mapping()。
# 这里只编译协变型 PP-LGCM：所有增长因子两两协变，并回归到各过程声明的协变量。
# 不推断生产模型的跨过程定向路径、逐波残差相关、自由载荷、交互或插补规则。
parallel_growth_model_syntax <- function(processes, covariates = character(), width = 80L) {
  if (!is.list(processes) || is.data.frame(processes) || length(processes) != 2L ||
      is.null(names(processes)) || anyNA(names(processes)) ||
      any(!nzchar(trimws(names(processes)))) || anyDuplicated(toupper(names(processes))))
    stop("processes must contain exactly two uniquely named process roles")
  if (!is.numeric(width) || length(width) != 1L || !is.finite(width) ||
      width != as.integer(width) || width < 40L || width > 90L)
    stop("width must be an integer between 40 and 90 characters")
  valid_names <- function(x) is.character(x) && !anyNA(x) &&
    all(grepl("^[A-Za-z][A-Za-z0-9_]{0,7}$", x))
  check_mapping <- function(x, allow_empty = FALSE) {
    if (!is.character(x) || (!allow_empty && !length(x)) ||
        (length(x) && (is.null(names(x)) || !valid_names(names(x)))) ||
        anyNA(x) || any(!nzchar(trimws(x))))
      stop("Role mappings must be named character vectors: Mplus alias = source column")
  }
  check_mapping(covariates, allow_empty = TRUE)
  syntax <- lapply(processes, function(spec) {
    required <- c("variables", "waves", "factors")
    if (!is.list(spec) || is.data.frame(spec) || is.null(names(spec)) ||
        anyNA(names(spec)) || anyDuplicated(names(spec)) ||
        !all(required %in% names(spec)) ||
        any(!names(spec) %in% c(required, "shape", "knot", "adjust_for")))
      stop("Each process requires variables, waves and factors; only shape, knot and adjust_for are optional")
    check_mapping(spec[["variables"]])
    if (!valid_names(spec[["factors"]]) || !length(spec[["factors"]]))
      stop("Each process requires explicit valid growth factor names")
    # 省略shape只采用linear；明确传NULL/向量/自由载荷类型不能静默回退。
    shape <- if ("shape" %in% names(spec)) spec[["shape"]] else "linear"
    if (!is.character(shape) || length(shape) != 1L || is.na(shape) ||
        !shape %in% c("linear", "quadratic", "piecewise"))
      stop("Parallel growth supports fixed linear, quadratic or piecewise time scores only")
    growth_model_syntax(spec[["waves"]], names(spec[["variables"]]), shape,
      knot = spec[["knot"]], factors = spec[["factors"]], width = width)
  })
  # 去掉过程角色前缀，只保留真正的Mplus别名；声明的波次顺序不能随源列序改变。
  variables <- c(do.call(c, unname(lapply(processes, function(p) p[["variables"]]))), covariates)
  factors <- unname(unlist(lapply(syntax, function(s) s$factors)))
  all_names <- c(names(variables), factors)
  if (anyDuplicated(toupper(all_names)))
    stop("Observed aliases, covariate aliases and growth factors must be globally unique ignoring case")
  if (anyDuplicated(unname(variables)))
    stop("Source columns must have a one-to-one mapping across both processes and covariates")
  covariates_by_process <- lapply(processes, function(spec) {
    # 未写adjust_for时两过程都用全体协变量；显式空向量允许某过程不作调整。
    chosen <- if ("adjust_for" %in% names(spec)) spec[["adjust_for"]] else names(covariates)
    if (is.null(chosen) && !"adjust_for" %in% names(spec)) chosen <- character()
    if (!valid_names(chosen) || anyDuplicated(toupper(chosen)) ||
        any(!toupper(chosen) %in% toupper(names(covariates))))
      stop("adjust_for must select unique declared covariate aliases")
    unname(names(covariates)[match(toupper(chosen), toupper(names(covariates)))])
  })
  if (any(!names(covariates) %in% unlist(covariates_by_process)))
    stop("Each declared covariate must be used by at least one process")
  statements <- unname(unlist(lapply(syntax, function(s) s$statements)))
  # 显式写出协方差，不依赖Mplus对潜变量协方差的隐含默认值。
  pairs <- utils::combn(factors, 2L)
  statements <- c(statements, apply(pairs, 2L, function(pair)
    paste0(pair[[1L]], " WITH ", pair[[2L]], ";")))
  if (length(covariates)) {
    on_statement <- function(factor, aliases) {
      lines <- character(); current <- paste(factor, "ON")
      for (alias in aliases) {
        if (nchar(current) + 1L + nchar(alias) + 1L > width) {
          lines <- c(lines, current); current <- paste0("  ", alias)
        } else current <- paste(current, alias)
      }
      paste(c(lines, paste0(current, ";")), collapse = "\n")
    }
    for (k in seq_along(syntax)) {
      aliases <- covariates_by_process[[k]]
      if (length(aliases)) statements <- c(statements,
        vapply(syntax[[k]]$factors, on_statement, character(1), aliases = aliases))
    }
  }
  list(model = paste(statements, collapse = "\n"), variables = variables,
       processes = syntax, factors = factors, covariates_by_process = covariates_by_process)
}
