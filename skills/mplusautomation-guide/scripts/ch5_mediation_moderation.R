# 第五章（单层中介 / 静态调节 / 有调节中介）可复用小函数。只做计算与文本生成，不调用 Mplus。
# 规格说明见 references/mediation-moderation-workflow.md。

# 保存抽样的偏差校正区间（与 Mplus CINTERVAL(BCBOOTSTRAP) 同一定义；分位用 type=7）
ch5_bc_interval <- function(draws, point, probs = c(0.05, 0.95)) {
  draws <- draws[is.finite(draws)]
  z0 <- stats::qnorm(mean(draws < point))
  if (!is.finite(z0)) return(rep(NA_real_, length(probs)))
  as.numeric(stats::quantile(draws, stats::pnorm(2 * z0 + stats::qnorm(probs)), type = 7, names = FALSE))
}

# 保存抽样的百分位区间
ch5_pc_interval <- function(draws, probs = c(0.05, 0.95)) {
  as.numeric(stats::quantile(draws[is.finite(draws)], probs, type = 7, names = FALSE))
}

# 差值判据：95% 区间排除零 / 仅 90% 排除零 / 90% 含零（论文用 ✓ ◐ ✗ 显示）
ch5_ci_class <- function(l90, u90, l95, u95) {
  if (any(!is.finite(c(l90, u90, l95, u95)))) return(NA_character_)
  if (l95 > 0 || u95 < 0) return("EXCLUDES_95")
  if (l90 > 0 || u90 < 0) return("EXCLUDES_90_ONLY")
  "INCLUDES_ZERO_90"
}

# 交互项显著性标记：p<0.1 用 "+"（论文附录显示为 †），其余为星号
ch5_sig_mark <- function(p) {
  ifelse(!is.finite(p), NA_character_,
    ifelse(p < 0.001, "***", ifelse(p < 0.01, "**", ifelse(p < 0.05, "*", ifelse(p < 0.1, "+", "")))))
}

# 三分类调节变量的效应编码：按 level_order 排列后 contr.sum，最后一类为 (-1,-1)
ch5_effect_code <- function(x, level_order = c(1, 3, 2), prefix = "w") {
  f <- factor(x, levels = level_order)
  if (anyNA(f[!is.na(x)])) stop("Unexpected moderator level")
  cm <- stats::contr.sum(length(level_order))
  out <- cm[as.integer(f), , drop = FALSE]
  colnames(out) <- paste0(prefix, "_effect", seq_len(ncol(out)))
  out[is.na(x), ] <- NA
  as.data.frame(out)
}

# 静态调节：glm 加夫妻（家庭）聚类稳健协方差，HC0，与第五章 R 脚本口径一致
ch5_fit_moderation <- function(formula, data, family = stats::gaussian(), cluster) {
  for (pkg in c("sandwich", "lmtest")) if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
  fit <- stats::glm(formula, data = data, family = family)
  v <- sandwich::vcovCL(fit, cluster = data[[cluster]], type = "HC0")
  list(fit = fit, vcov = v, table = lmtest::coeftest(fit, vcov. = v), nobs = stats::nobs(fit))
}

# 按结果变量剔除控制变量的显式规则（例：某结果不进某组控制）。规则写在配置里，不在代码里猜
ch5_controls_for_outcome <- function(controls, outcome, drop_rules = list()) {
  drop <- drop_rules[[outcome]]
  if (!is.null(drop) && !all(drop %in% controls)) stop("Drop rule names unknown controls for ", outcome)
  setdiff(controls, drop)
}

# 二值 M、二值 Y 的反事实分解（与 assets/ch5/counterfactual_mediation_template.txt 的 MODEL CONSTRAINT 同式）
# a0/b0 是 Mplus 阈值（概率式中带负号），X 取 0 与 1
ch5_counterfactual_effects <- function(a0, a1, b0, b1, b2, b3) {
  inv <- function(z) 1 / (1 + exp(z))
  pm1 <- c(x0 = inv(a0), x1 = inv(a0 - a1))
  ey <- function(x, m) inv(b0 - b1 * x - b2 * m - b3 * x * m)
  e <- function(x, xm) ey(x, 0) * (1 - pm1[[xm]]) + ey(x, 1) * pm1[[xm]]
  y0m0 <- e(0, "x0"); y0m1 <- e(0, "x1"); y1m0 <- e(1, "x0"); y1m1 <- e(1, "x1")
  c(TNIE = y1m1 - y1m0, PNIE = y0m1 - y0m0, PNDE = y1m0 - y0m0, TNDE = y1m1 - y0m1, TE = y1m1 - y0m0)
}

# 模板里需要手填的常量：形如 [[name]] 的普通标签（排除 [[init]]、迭代器 [[x#i]] 与条件 [[i = 1]]/[[/i = 1]]）
ch5_template_constants <- function(txt) {
  tags <- unlist(regmatches(txt, gregexpr("\\[\\[[^]]+\\]\\]", txt)))
  tags <- unique(gsub("^\\[\\[|\\]\\]$", "", tags))
  tags[grepl("^[A-Za-z_][A-Za-z0-9_]*$", tags) & !tags %in% c("init")]
}

# 填模板里的手填常量与输出目录；values 必须覆盖模板里每个常量标签，填完不得残留
ch5_fill_template <- function(template, out_path, values, required = NULL) {
  txt <- readLines(template, warn = FALSE, encoding = "UTF-8")
  if (is.null(required)) required <- ch5_template_constants(txt)
  miss <- setdiff(required, names(values))
  if (length(miss)) stop("Missing template constants: ", paste(miss, collapse = ", "))
  for (k in names(values)) {
    v <- values[[k]]
    if (is.numeric(v) && !all(is.finite(v))) stop("Non-finite constant: ", k)
    txt <- gsub(paste0("[[", k, "]]"), format(v, digits = 15), txt, fixed = TRUE)
  }
  left <- required[vapply(required, function(k) any(grepl(paste0("[[", k, "]]"), txt, fixed = TRUE)), logical(1))]
  if (length(left)) stop("Unfilled template constants: ", paste(left, collapse = ", "))
  writeLines(txt, out_path, useBytes = TRUE)
  invisible(out_path)
}

# ---- 换变量守卫：改 name*/var* 列表、NAMES、DAT 列序时只改一侧会静默出错，这里在交引擎前拦下 ----
# 失败时抛 ch5_swap_error，reasons 为原因代码集合，消息逐条写出位置

ch5_swap_fail <- function(items) {
  if (!length(items)) return(invisible(NULL))
  codes <- unique(vapply(items, `[[`, "", 1))
  msg <- paste0("Swap check failed: ", paste(vapply(items, function(x) paste0(x[[1]], " (", x[[2]], ")"), ""), collapse = "; "))
  stop(structure(class = c("ch5_swap_error", "error", "condition"),
                 list(message = msg, call = NULL, reasons = codes, details = items)))
}

# 模板层：[[init]] 里同后缀、同迭代器的 name*/var* 列表按下标成对，文件名标签必须对应同一下标的变量
# labels：模型变量名 → 文件名标签（命名字符向量）；NULL 表示标签与变量名相同（本 skill 合成模板的约定）
ch5_check_template_lists <- function(template, labels = NULL) {
  if (!is.null(labels) && (!is.character(labels) || is.null(names(labels)) || anyNA(names(labels))))
    stop("labels must be a named character vector")
  txt <- if (length(template) == 1L && file.exists(template)) readLines(template, warn = FALSE, encoding = "UTF-8") else template
  a <- which(trimws(txt) == "[[init]]"); b <- which(trimws(txt) == "[[/init]]")
  if (length(a) != 1L || length(b) != 1L || b <= a) ch5_swap_fail(list(list("TEMPLATE_INIT_MISSING", "one [[init]] ... [[/init]] block")))
  rx <- "^\\s*(name|var)([A-Za-z0-9_]*)#([A-Za-z0-9_]+)\\s*=\\s*(.*?);?\\s*$"
  ent <- list()
  for (ln in txt[(a + 1L):(b - 1L)]) {
    m <- regmatches(ln, regexec(rx, ln, perl = TRUE))[[1]]
    if (length(m)) ent[[length(ent) + 1L]] <- list(kind = m[2], suffix = m[3], iter = m[4],
                                                   values = strsplit(trimws(m[5]), "\\s+")[[1]])
  }
  bad <- list(); pairs <- list()
  keys <- unique(vapply(ent, function(e) paste0(e$suffix, "#", e$iter), ""))
  for (k in keys) {
    nm <- Filter(function(e) e$kind == "name" && paste0(e$suffix, "#", e$iter) == k, ent)
    vr <- Filter(function(e) e$kind == "var" && paste0(e$suffix, "#", e$iter) == k, ent)
    if (length(nm) != 1L || length(vr) != 1L) next  # 只有一侧的列表（如样本名、varwv1）不成对，不核
    n <- nm[[1]]$values; v <- vr[[1]]$values
    if (length(n) != length(v)) {
      bad[[length(bad) + 1L]] <- list("NAME_VAR_LENGTH_MISMATCH", sprintf("name%s has %d, var%s has %d", k, length(n), k, length(v)))
      next
    }
    for (i in seq_along(v)) {
      want <- if (is.null(labels)) v[i] else unname(labels[v[i]])
      if (!is.null(labels) && !v[i] %in% names(labels)) {
        bad[[length(bad) + 1L]] <- list("VAR_NOT_IN_LABELS", sprintf("var%s[%d] = %s", k, i, v[i])); next
      }
      if (!identical(n[i], want))
        bad[[length(bad) + 1L]] <- list("NAME_VAR_MISMATCH", sprintf("name%s[%d] = %s but var%s[%d] = %s expects %s", k, i, n[i], k, i, v[i], want))
    }
    if (anyDuplicated(n)) bad[[length(bad) + 1L]] <- list("DUPLICATE_NAME_LABEL", sprintf("name%s repeats %s (same filename, later model overwrites)", k, n[anyDuplicated(n)]))
    pairs[[k]] <- data.frame(pair = k, index = seq_along(v), var = v, name = n)
  }
  if (!length(pairs) && !length(bad)) bad[[1]] <- list("NO_NAME_VAR_PAIRS", "no name*/var* list pair sharing a suffix and iterator")
  ch5_swap_fail(bad)
  invisible(do.call(rbind, pairs))
}
# .inp 拆成（段, 语句）；去掉 ! 注释，语句以分号结束，可跨行
ch5_inp_statements <- function(lines) {
  heads <- c("TITLE", "DATA", "VARIABLE", "DEFINE", "ANALYSIS", "MODEL", "MODEL INDIRECT", "MODEL CONSTRAINT",
             "MODEL TEST", "MODEL PRIORS", "OUTPUT", "SAVEDATA", "PLOT", "MONTECARLO")
  sec <- ""; buf <- character(); out <- list()
  emit <- function() {
    s <- trimws(paste(buf, collapse = " "))
    if (nzchar(s)) out[[length(out) + 1L]] <<- list(section = sec, text = gsub("\\s+", " ", s))
    buf <<- character()
  }
  for (ln in sub("!.*$", "", lines)) {
    m <- regmatches(ln, regexec("^\\s*([A-Za-z][A-Za-z ]*?)\\s*:(.*)$", ln, perl = TRUE))[[1]]
    if (length(m) && toupper(m[2]) %in% heads) { emit(); sec <- toupper(m[2]); ln <- m[3] }
    parts <- strsplit(paste0(ln, " "), ";", fixed = TRUE)[[1]]
    if (length(parts) > 1L) for (p in parts[-length(parts)]) { buf <- c(buf, p); emit() }
    buf <- c(buf, parts[length(parts)])
  }
  emit()
  out
}

# 生成的 .inp 与它读的 DAT 对齐：Mplus 按位置读自由格式 DAT，NAMES 列序错了不报错，只会把数读进错的变量
# data：写 DAT 时用的 data.frame（列序即 DAT 列序）；dat_file：该 DAT 路径（存在就读回逐列核内容）
ch5_check_inp_columns <- function(inp, data, dat_file, max_width = 90L) {
  lines <- readLines(inp, warn = FALSE)
  bad <- list(); add <- function(code, what) bad[[length(bad) + 1L]] <<- list(code, what)
  w <- which(nchar(lines, type = "bytes") > max_width)
  if (length(w)) add("LINE_TOO_LONG", sprintf("line %s exceeds %d bytes; Mplus ignores the rest", paste(w, collapse = ","), max_width))
  st <- ch5_inp_statements(lines)
  kv <- function(section, key) {
    rx <- paste0("^(?i:", key, ")[A-Za-z]*\\s*(?:=|\\s(?i:are|is)\\s)\\s*(.*)$")
    hit <- Filter(function(s) s$section == section && grepl(rx, s$text, perl = TRUE), st)
    if (!length(hit)) return(NULL)
    trimws(sub(rx, "\\1", hit[[length(hit)]]$text, perl = TRUE))
  }
  toks <- function(x) if (is.null(x)) NULL else strsplit(tolower(x), "\\s+")[[1]]
  cols <- tolower(names(data))
  nm <- toks(kv("VARIABLE", "name"))
  if (is.null(nm)) add("NAMES_MISSING", "no NAMES statement")
  if (any(grepl("-", nm, fixed = TRUE))) add("UNSUPPORTED_LIST_SYNTAX", "NAMES uses a range (a-b); list every name")
  if (anyDuplicated(nm)) add("NAMES_DUPLICATE", nm[anyDuplicated(nm)])
  if (!is.null(nm)) {
    if (!setequal(nm, cols)) {
      add("NAMES_DAT_SET_MISMATCH", sprintf("only in NAMES: %s; only in DAT: %s",
                                           paste(setdiff(nm, cols), collapse = " "), paste(setdiff(cols, nm), collapse = " ")))
    } else if (!identical(nm, cols)) {
      i <- which(nm != cols)[1]
      add("NAMES_DAT_ORDER_MISMATCH", sprintf("position %d: NAMES has %s, DAT column is %s", i, nm[i], cols[i]))
    }
  }
  # DATA: FILE 按 .inp 所在目录解析，必须就是这个 DAT
  f <- kv("DATA", "file")
  if (is.null(f)) add("DATA_FILE_MISSING", "no DATA: FILE statement") else {
    f <- gsub('^"|"$', "", f)
    p <- if (grepl("^(/|[A-Za-z]:)", f)) f else file.path(dirname(normalizePath(inp)), f)
    if (!file.exists(p) || normalizePath(p) != normalizePath(dat_file, mustWork = FALSE))
      add("DATA_FILE_MISMATCH", sprintf("DATA: FILE = %s, expected %s", f, basename(dat_file)))
  }
  # DAT 读回：字段数、行数、逐列内容（因子按整数编码，与 prepareMplusData 一致）
  if (file.exists(dat_file)) {
    x <- utils::read.table(dat_file, header = FALSE, na.strings = ".", colClasses = "numeric")
    if (!is.null(nm) && ncol(x) != length(nm)) add("DAT_FIELD_COUNT_MISMATCH", sprintf("DAT has %d fields, NAMES has %d", ncol(x), length(nm)))
    if (nrow(x) != nrow(data)) add("DAT_ROW_COUNT_MISMATCH", sprintf("DAT has %d rows, data has %d", nrow(x), nrow(data)))
    if (ncol(x) == ncol(data) && nrow(x) == nrow(data)) {
      num <- lapply(data, function(v) if (is.factor(v) || is.logical(v)) as.integer(v) else as.numeric(v))
      off <- names(data)[!vapply(seq_along(num), function(j) {
        a <- x[[j]]; b <- num[[j]]
        identical(is.na(a), is.na(b)) && isTRUE(all(abs(a[!is.na(a)] - b[!is.na(b)]) <= 1e-10 * pmax(1, abs(b[!is.na(b)]))))
      }, logical(1))]
      if (length(off)) add("DAT_CONTENT_MISMATCH", sprintf("DAT columns differ from data for: %s", paste(off, collapse = " ")))
    }
  }
  # DEFINE 按出现顺序核声明；仅支持单变量赋值与 IF (...) THEN 单变量赋值。
  reserved <- c("log", "log10", "exp", "sqrt", "abs", "sin", "cos", "tan", "asin", "acos", "atan", "eq", "ne", "gt",
                "lt", "ge", "le", "and", "or", "not", "if", "then", "else", "center", "grandmean", "groupmean", "cut",
                "mean", "sum", "standardize", "do", "missing")
  ids <- function(s, ignored = reserved) setdiff(unique(tolower(unlist(regmatches(s, gregexpr("\\b[A-Za-z][A-Za-z0-9_]*\\b",
                                                                          gsub("\\b[0-9.]+([eE][-+]?[0-9]+)?\\b", " ", s), perl = TRUE))))), ignored)
  define_ids <- function(s) {
    # 只排除真正的函数调用；裸 log/mean 等仍是需要声明的变量。_MISSING 是 Mplus 常量。
    functions <- c("log", "log10", "exp", "sqrt", "abs", "sin", "cos", "tan", "asin", "acos", "atan", "mean", "sum")
    s <- gsub(paste0("(?i)\\b(?:", paste(functions, collapse = "|"), ")\\b(?=\\s*\\()"), " ", s, perl = TRUE)
    s <- gsub("(?i)\\b_MISSING\\b", " ", s, perl = TRUE)
    ids(s, c("eq", "ne", "gt", "lt", "ge", "le", "and", "or", "not"))
  }
  balanced <- function(s) {
    chars <- strsplit(s, "", fixed = TRUE)[[1]]
    depth <- cumsum((chars == "(") - (chars == ")"))
    !length(depth) || (all(depth >= 0L) && tail(depth, 1L) == 0L)
  }
  assignment <- "^([A-Za-z][A-Za-z0-9_]*)\\s*=\\s*(.+)$"
  defined <- character()
  for (s in Filter(function(s) s$section == "DEFINE", st)) {
    text <- s$text; condition <- ""; supported <- TRUE
    if (grepl("^(?i:IF)\\b", text, perl = TRUE)) {
      rest <- trimws(sub("^(?i:IF)\\s*", "", text, perl = TRUE))
      chars <- strsplit(rest, "", fixed = TRUE)[[1]]
      depth <- cumsum((chars == "(") - (chars == ")"))
      end <- which(depth == 0L)[1]
      supported <- startsWith(rest, "(") && !is.na(end) && end > 2L
      if (supported) {
        # 找到最外层条件的首个闭括号，支持嵌套；不让贪婪正则吞掉后续控制语句。
        condition <- trimws(substr(rest, 2L, end - 1L))
        suffix <- trimws(substring(rest, end + 1L))
        supported <- nzchar(condition) && grepl("^(?i:THEN)\\s+", suffix, perl = TRUE)
        text <- sub("^(?i:THEN)\\s+", "", suffix, perl = TRUE)
      }
    }
    m <- regmatches(text, regexec(assignment, text, perl = TRUE))[[1]]
    if (!supported || !length(m) || !nzchar(trimws(m[3])) || !balanced(condition) || !balanced(m[3]) ||
        grepl("(?i)\\b(if|then|else|do|enddo)\\b", paste(condition, m[3]), perl = TRUE)) {
      add("UNSUPPORTED_DEFINE_SYNTAX", s$text); next
    }
    miss <- setdiff(define_ids(paste(condition, m[3])), c(nm, defined))
    if (length(miss)) add("DEFINE_NOT_IN_NAMES", sprintf("%s condition/RHS uses %s", m[2], paste(miss, collapse = " ")))
    defined <- c(defined, tolower(m[2]))
  }
  uv <- toks(kv("VARIABLE", "usev"))
  if (any(grepl("-", uv, fixed = TRUE))) add("UNSUPPORTED_LIST_SYNTAX", "USEVARIABLES uses a range (a-b); list every name")
  miss <- setdiff(uv, c(nm, defined))
  if (length(miss)) add("USEVARIABLES_NOT_IN_NAMES", paste(miss, collapse = " "))
  ct <- kv("VARIABLE", "cate")
  ct <- if (is.null(ct)) character() else toks(trimws(gsub("\\([^)]*\\)", " ", ct)))
  miss <- setdiff(ct[nzchar(ct)], if (is.null(uv)) nm else uv)
  if (length(miss)) add("CATEGORICAL_NOT_IN_USEVARIABLES", paste(miss, collapse = " "))
  uo <- kv("VARIABLE", "useo")
  miss <- if (is.null(uo)) character() else setdiff(ids(uo), nm)
  if (length(miss)) add("USEOBSERVATIONS_NOT_IN_NAMES", paste(miss, collapse = " "))
  g <- kv("VARIABLE", "grou")
  gv <- if (is.null(g)) character() else tolower(sub("^([A-Za-z][A-Za-z0-9_]*).*$", "\\1", g))
  if (length(gv) && !gv %in% nm) add("GROUPING_NOT_IN_NAMES", gv)
  ch5_swap_fail(bad)
  invisible(list(names = nm, usevariables = uv, defined = defined))
}
