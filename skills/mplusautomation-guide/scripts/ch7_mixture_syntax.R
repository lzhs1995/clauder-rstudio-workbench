# 第七章混合模型语法生成：按显式规格写 mplusObject（LPA/LCA、LTA、MS-LTA 及其 Step-3），不估计。
# 只做规格里写明的东西：不选类别数、不推断变量类型、不读取研究文件。潜变量名固定为 c（单期）、
# c1..cT（各波）和 g（mover/stayer 高阶类别）。
# 返回 list(object, data, spec)；object 交给 mplusModeler(run = 0L) 生成 INP/DAT，或交给共用执行层估计。

# 仅在引号外的空白处分行；标识符、固定值、标签及带空格的文件名保持为完整 token。
# 短行逐字保留。注释尾部不作为可拆语句，无法安全容纳的 token 明确拒绝。
ch7_wrap_mplus_lines <- function(text, width = 80L) {
  if (!is.character(text) || anyNA(text) || !is.numeric(width) || length(width) != 1L ||
      !is.finite(width) || width != trunc(width) || width < 1L)
    stop("Mplus text and a positive integer width are required")
  lines <- unlist(strsplit(text, "\n", fixed = TRUE), use.names = FALSE)
  wrap_line <- function(line) {
    if (nchar(line, type = "bytes") <= width) return(line)
    chars <- strsplit(line, "", fixed = TRUE)[[1]]
    tokens <- character(); token <- ""; quote <- ""; comment <- FALSE
    for (ch in chars) {
      if (comment) token <- paste0(token, ch)
      else if (nzchar(quote)) {
        token <- paste0(token, ch)
        if (ch == quote) quote <- ""
      } else if (ch %in% c("\"", "'")) {
        token <- paste0(token, ch); quote <- ch
      } else if (ch == "!") {
        if (nzchar(token)) tokens <- c(tokens, token)
        token <- ch; comment <- TRUE
      } else if (grepl("[[:space:]]", ch)) {
        if (nzchar(token)) tokens <- c(tokens, token)
        token <- ""
      } else token <- paste0(token, ch)
    }
    if (nzchar(quote)) stop("Cannot safely wrap an unterminated quoted Mplus token")
    if (nzchar(token)) tokens <- c(tokens, token)
    if (any(nchar(tokens, type = "bytes") > width))
      stop("A Mplus token or comment exceeds the permitted input width")
    result <- character(); current <- ""
    for (token in tokens) {
      candidate <- if (nzchar(current)) paste(current, token) else token
      if (nchar(candidate, type = "bytes") > width) {
        result <- c(result, current); current <- token
      } else current <- candidate
    }
    c(result, current)
  }
  paste(unlist(lapply(lines, wrap_line), use.names = FALSE), collapse = "\n")
}

# 最终 INP 的独立写后门禁；入口追加 TITLE/IDVARIABLE 等字段后也必须调用。
ch7_validate_input_width <- function(path, max_bytes = 90L) {
  if (!is.character(path) || length(path) != 1L || is.na(path) || !file.exists(path) ||
      !is.numeric(max_bytes) || length(max_bytes) != 1L || !is.finite(max_bytes) ||
      max_bytes != trunc(max_bytes) || max_bytes < 1L)
    stop("An existing INP file and a positive integer width are required")
  widths <- nchar(readLines(path, warn = FALSE), type = "bytes")
  if (any(widths > max_bytes)) stop("Mplus input exceeds ", max_bytes,
    " bytes at line(s): ", paste(which(widths > max_bytes), collapse = ", "))
  invisible(TRUE)
}

ch7_mixture_object <- function(data, family = c("lpa", "lta", "mslta"), waves = NULL, categorical = character(),
                               classes, invariant = TRUE, step3 = NULL, center = NULL, keep = NULL,
                               title = NULL, starts = NULL, estimator = "MLR", processors = 1L,
                               output = "TECH1 TECH8;",
                               savedata = "FILE = posterior.dat; SAVE = CPROBABILITIES;",
                               stayer = c(intercept = -10, slope = 20), transitions = TRUE) {
  family <- match.arg(family)
  if (!is.data.frame(data) || !nrow(data)) stop("A nonempty data.frame is required")
  if (!is.numeric(classes) || length(classes) != 1L || !is.finite(classes) || classes != round(classes) || classes < 1)
    stop("classes must be one positive integer")
  K <- as.integer(classes)
  if (!is.logical(transitions) || length(transitions) != 1L || is.na(transitions))
    stop("transitions must be one explicit logical value")
  if (family == "mslta" && !isTRUE(transitions))
    stop("MS-LTA requires transitions = TRUE; use LTA for a measurement-only Step-1")
  mplus_name <- function(x) is.character(x) && length(x) > 0L && all(grepl("^[A-Za-z][A-Za-z0-9_]{0,7}$", x))
  if (!is.null(step3)) {
    if (family == "lpa") stop("Step-3 syntax is defined for lta and mslta only")
    if (K < 2L) stop("Step-3 needs at least two classes")
    if (!is.list(step3) || !mplus_name(step3$nominal) || length(step3$nominal) < 2L)
      stop("step3$nominal must name one most-likely-class variable per wave")
    nw <- length(step3$nominal)
    # 直接使用 Step-1 打印的 logit，避免先对三位小数的概率取 log 或擅自平滑零值。
    # 行为真类别，列为赋类 1..K-1；最后一类 K 是唯一参考类。
    if (!isTRUE(transitions)) stop("Step-3 requires transitions = TRUE")
    if (is.null(step3$error) == is.null(step3$logits))
      stop("Provide exactly one of step3$error and step3$logits")
    if (!is.null(step3$logits)) {
      logits <- if (is.matrix(step3$logits)) rep(list(step3$logits), nw) else step3$logits
      if (!is.list(logits) || length(logits) != nw)
        stop("step3$logits must be one Kx(K-1) matrix or one per wave")
      for (z in logits) if (!is.matrix(z) || !is.numeric(z) ||
          !identical(as.integer(dim(z)), c(K, K - 1L)) || any(!is.finite(z)))
        stop("Each classification logit matrix must be finite Kx(K-1), reference class K")
      error <- NULL
      step3$logits <- logits
    } else {
      error <- if (is.matrix(step3$error)) rep(list(step3$error), nw) else step3$error
      if (!is.list(error) || length(error) != nw) stop("step3$error must be one KxK matrix or one per wave")
      for (e in error) {
        if (!is.matrix(e) || !is.numeric(e) || any(dim(e) != K) || any(!is.finite(e)) || any(e <= 0) ||
            any(abs(rowSums(e) - 1) > 1e-9))
          stop("Each classification error matrix must be KxK, strictly positive, with rows summing to 1")
      }
    }
    used <- step3$nominal
    cat_statement <- c("NOMINAL", used)
    center <- NULL
  } else {
    if (!is.list(waves) || !length(waves) || !all(vapply(waves, mplus_name, logical(1))))
      stop("waves must be a list of Mplus indicator names, one character vector per wave")
    nw <- length(waves)
    if (family == "lpa" && nw != 1L) stop("lpa takes exactly one wave")
    if (family != "lpa" && (nw < 2L || K < 2L)) stop("lta and mslta need at least two waves and two classes")
    if (!is.character(categorical) || !all(categorical %in% unlist(waves)))
      stop("categorical must list indicators that appear in waves")
    pattern <- lapply(waves, function(w) w %in% categorical)
    if (family != "lpa" && invariant && length(unique(pattern)) != 1L)
      stop("Invariant measurement needs the same indicator count and type pattern in every wave")
    used <- unlist(waves)
    cat_statement <- c("CATEGORICAL", used[used %in% categorical])
  }
  if (anyDuplicated(toupper(used))) stop("Each indicator may appear only once")
  latent <- if (family == "lpa") "c" else c(if (family == "mslta") "g", paste0("c", seq_len(nw)))
  if (!is.null(center) && !mplus_name(center)) stop("center must name Mplus variables")
  if (is.null(keep)) keep <- unique(c(used, center))
  if (!mplus_name(keep) || !all(c(used, center) %in% keep) || !all(keep %in% names(data)))
    stop("keep must contain every used and centred variable, and all must exist in data")
  if (any(toupper(keep) %in% toupper(latent)))
    stop("All kept observed names, including ID, must differ from latent class names")
  dataset <- data[, names(data)[names(data) %in% keep], drop = FALSE]
  if (!all(vapply(dataset, is.numeric, logical(1)))) stop("Kept columns must be numeric")
  if (!is.null(step3)) for (n in step3$nominal) {
    values <- dataset[[n]][!is.na(dataset[[n]])]
    if (!all(values %in% seq_len(K))) stop("Most-likely-class variable ", n, " must take values 1..", K)
  }
  if (family == "mslta" && (!is.numeric(stayer) || !all(c("intercept", "slope") %in% names(stayer))))
    stop("stayer needs named intercept and slope logits")

  body <- if (family == "lpa") ch7_lpa_body(waves[[1]], categorical, K)
          else ch7_lta_body(family, nw, K, waves, categorical, invariant, transitions, step3,
            if (!is.null(step3)) error, stayer)
  classes_text <- if (family == "lpa") paste0("c(", K, ")")
                  else paste(c(if (family == "mslta") "g(2)", paste0("c", seq_len(nw), "(", K, ")")), collapse = " ")
  wrap <- ch7_wrap_mplus_lines
  variable <- c(paste0("USEVARIABLES = ", paste(used, collapse = " "), ";"),
                if (length(cat_statement) > 1L)
                  paste0(cat_statement[1], " = ", paste(cat_statement[-1], collapse = " "), ";"),
                paste0("CLASSES = ", classes_text, ";"))
  define <- if (length(center)) paste0("CENTER ", paste(center, collapse = " "), " (GRANDMEAN);")
  if (is.null(starts)) starts <- if (is.null(step3)) "20 5" else "0"
  object <- MplusAutomation::mplusObject(
    TITLE = wrap(if (is.null(title)) paste0("Chapter 7 ", family, if (!is.null(step3)) " step 3", ";") else title),
    VARIABLE = wrap(variable), DEFINE = if (is.null(define)) NULL else wrap(define),
    ANALYSIS = wrap(c("TYPE = MIXTURE;", paste0("ESTIMATOR = ", estimator, ";"), paste0("STARTS = ", starts, ";"),
                     paste0("PROCESSORS = ", processors, ";"))),
    MODEL = wrap(body), OUTPUT = wrap(output), SAVEDATA = wrap(savedata),
    rdata = dataset, usevariables = names(dataset), autov = FALSE, quiet = TRUE)
  list(object = object, data = dataset,
       spec = list(family = family, step3 = !is.null(step3), waves = nw, classes = K, invariant = invariant,
                   latent = latent, transitions = transitions, used = used))
}

# 单期：%OVERALL% 写连续指标方差，各类别写连续均值与二分类阈值
ch7_lpa_body <- function(indicators, categorical, K) {
  continuous <- indicators[!indicators %in% categorical]
  binary <- indicators[indicators %in% categorical]
  body <- if (length(continuous)) c("%OVERALL%", paste0(paste(continuous, collapse = " "), ";"))
  for (j in seq_len(K)) body <- c(body, paste0("%c#", j, "%"),
    if (length(continuous)) paste0("[", paste(continuous, collapse = " "), "];"),
    if (length(binary)) paste0("[", paste0(binary, "$1", collapse = " "), "];"))
  body
}

# 纵向：显式选择测量模型或相邻一阶转移；不变模型跨波共用测量标签，
# Step-3 改为固定分类误差 logit，MS-LTA 的 mover/stayer 结构须保留转移。
ch7_lta_body <- function(family, nw, K, waves, categorical, invariant, transitions, step3, error, stayer) {
  body <- "%OVERALL%"
  if (isTRUE(transitions)) body <- c(body, paste0("c", 2:nw, " ON c", 1:(nw - 1), ";"))
  if (family == "mslta") {
    body <- c(body, "c1 ON g;", "MODEL g:", "%g#1%",
              vapply(2:nw, function(t) paste0("[", paste0("c", t, "#", seq_len(K - 1), collapse = " "), "];"), ""),
              if (isTRUE(transitions)) paste0("c", 2:nw, " ON c", 1:(nw - 1), ";") else character(), "%g#2%")
    # 有限 logit 逼近 stayer 的对角线转移，不是精确的 0/1 概率
    num <- function(x) as.character(x)
    for (t in 2:nw) {
      body <- c(body, paste0("[", paste0("c", t, "#", seq_len(K - 1), "@", num(stayer[["intercept"]]), collapse = " "), "];"))
      for (j in seq_len(K - 1)) body <- c(body, paste0("c", t, "#", j, " ON ",
        paste0("c", t - 1, "#", seq_len(K - 1), "@", ifelse(seq_len(K - 1) == j, num(stayer[["slope"]]), "0"),
               collapse = " "), ";"))
    }
  }
  for (t in seq_len(nw)) {
    body <- c(body, paste0("MODEL c", t, ":"))
    for (j in seq_len(K)) {
      body <- c(body, paste0("%c", t, "#", j, "%"))
      if (!is.null(step3)) {
        # 行 = 潜在真类别 j，列 = 赋类；logit 以最后一类为参照
        logits <- if (!is.null(step3$logits)) step3$logits[[t]][j, ]
                  else log(error[[t]][j, -K] / error[[t]][j, K])
        body <- c(body, paste0("[", step3$nominal[[t]], "#", seq_len(K - 1), "@", sprintf("%.12f", logits), "];"))
      } else for (a in seq_along(waves[[t]])) {
        variable <- waves[[t]][[a]]
        label <- paste0(if (invariant) "m" else paste0("w", t), "k", j, "i", a)
        body <- c(body, paste0("[", variable, if (variable %in% categorical) "$1", "] (", label, ");"))
      }
    }
  }
  body
}
