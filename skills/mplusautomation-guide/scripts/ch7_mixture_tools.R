# 第七章混合模型工具：从 INP 判定家族、类别枚举汇总、Step-1 存盘到 Step-3 输入的哈希绑定。
# 只读文件，不调用 Mplus，不替研究者选类别数；返回的回执只记状态、计数、差值与 SHA，不写估计值。

# ---- INP 解析（分类器、枚举读出、Step-3 绑定共用） ----
`%||%` <- function(a, b) if (is.null(a)) b else a

ch7_inp_sections <- function(text) {
  # 去掉 ! 注释，按 Mplus 顶层命令切段；MODEL c1: 这类类别命名空间留在 MODEL 段内
  lines <- sub("!.*$", "", unlist(strsplit(paste(text, collapse = "\n"), "\r?\n")))
  rx <- paste0("^\\s*(TITLE|DATA(?:\\s+[A-Za-z]+)?|VARIABLE|DEFINE|ANALYSIS|",
               "MODEL(?:\\s+(?:CONSTRAINT|INDIRECT|TEST|PRIORS|POPULATION|MISSING|COVERAGE))?|",
               "OUTPUT|SAVEDATA|PLOT|MONTECARLO)\\s*:(.*)$")
  sections <- list(); current <- NULL
  for (line in lines) {
    m <- regmatches(line, regexec(rx, line, ignore.case = TRUE, perl = TRUE))[[1]]
    if (length(m)) { current <- toupper(gsub("\\s+", " ", trimws(m[2]))); line <- m[3] }
    if (!is.null(current)) sections[[current]] <- c(sections[[current]], line)
  }
  lapply(sections, paste, collapse = "\n")
}

ch7_statements <- function(x) {
  if (is.null(x)) return(character())
  s <- trimws(gsub("\\s+", " ", unlist(strsplit(x, ";", fixed = TRUE))))
  s[nzchar(s)]
}

# 「关键字 = 值」或「关键字 ARE/IS 值」；Mplus 允许至少 4 个字母的缩写
ch7_option <- function(statements, key) {
  m <- regmatches(statements, regexec("^([A-Za-z]+)\\s*(?:=|\\s+(?:ARE|IS)\\s+)\\s*(.*)$", statements,
                                      ignore.case = TRUE, perl = TRUE))
  hit <- vapply(m, function(x) length(x) == 3L && nchar(x[2]) >= 4L && startsWith(toupper(key), toupper(x[2])), logical(1))
  if (any(hit)) paste(vapply(m[hit], `[`, "", 3L), collapse = " ") else NULL
}

# 变量清单：去掉 (*)、(u) 这类选项，展开 y1-y5（优先按 NAMES 的位置）
ch7_varlist <- function(value, names = NULL) {
  if (is.null(value)) return(character())
  tokens <- strsplit(trimws(gsub("\\([^)]*\\)", " ", value)), "\\s+")[[1]]
  out <- character()
  for (tok in tokens[nzchar(tokens)]) {
    ends <- strsplit(tok, "-", fixed = TRUE)[[1]]
    if (length(ends) == 2L && !is.null(names) && all(toupper(ends) %in% toupper(names))) {
      i <- match(toupper(ends), toupper(names)); out <- c(out, names[i[1]:i[2]])
    } else if (length(ends) == 2L && grepl("^[A-Za-z_]+[0-9]+$", ends[1]) && grepl("^[A-Za-z_]*[0-9]+$", ends[2])) {
      out <- c(out, paste0(sub("[0-9]+$", "", ends[1]), as.integer(sub("^[A-Za-z_]+", "", ends[1])):
                                                         as.integer(sub("^[A-Za-z_]*", "", ends[2]))))
    } else out <- c(out, tok)
  }
  toupper(out)
}

ch7_classes <- function(value) {
  if (is.null(value)) return(integer())
  m <- regmatches(value, gregexpr("[A-Za-z][A-Za-z0-9_]*\\s*\\(\\s*[0-9]+\\s*\\)", value))[[1]]
  stats::setNames(as.integer(sub(".*\\(\\s*([0-9]+)\\s*\\)", "\\1", m)), toupper(sub("\\s*\\(.*", "", m)))
}

# MODEL 段按命名空间（OVERALL、c1、g …）和类别块（%c1#2%、%g#1%）切成语句表；跨行语句先拼回再按分号切
ch7_model_blocks <- function(model) {
  empty <- data.frame(namespace = character(), block = character(), statement = character())
  if (is.null(model)) return(empty)
  chunks <- list(); namespace <- "OVERALL"; block <- "OVERALL"; buffer <- character()
  flush <- function() {
    s <- ch7_statements(paste(buffer, collapse = " "))
    if (length(s)) chunks[[length(chunks) + 1L]] <<- data.frame(namespace = namespace, block = block, statement = s)
    buffer <<- character()
  }
  for (line in unlist(strsplit(model, "\n", fixed = TRUE))) {
    header <- regmatches(line, regexec("^\\s*MODEL\\s+([A-Za-z][A-Za-z0-9_]*)\\s*:(.*)$", line, ignore.case = TRUE))[[1]]
    if (length(header)) { flush(); namespace <- toupper(header[2]); block <- namespace; line <- header[3] }
    for (part in regmatches(line, gregexpr("%[^%]+%", line), invert = NA)[[1]]) {
      if (grepl("^%[^%]+%$", part)) { flush(); block <- toupper(gsub("%|\\s", "", part)) }
      else buffer <- c(buffer, part)
    }
  }
  flush()
  if (length(chunks)) do.call(rbind, chunks) else empty
}

# 「左 ON 右」；去掉 (标签)，右侧每项记是否 @ 固定
ch7_on <- function(statement) {
  s <- trimws(gsub("\\([^)]*\\)", " ", statement))
  m <- regmatches(s, regexec("^(.*?)\\s+ON\\s+(.*)$", s, ignore.case = TRUE, perl = TRUE))[[1]]
  if (!length(m)) return(NULL)
  lhs <- toupper(strsplit(trimws(m[2]), "\\s+")[[1]]); rhs <- strsplit(trimws(m[3]), "\\s+")[[1]]
  list(lhs = lhs, rhs = toupper(sub("[@*].*$", "", rhs)), fixed = grepl("@", rhs),
       values = suppressWarnings(as.numeric(sub("^[^@]*@", "", rhs))))
}

# 从 ON 图恢复唯一有向次序；声明顺序没有波次含义，分叉歧义或环不认作链。
ch7_transition_chain <- function(nodes, pairs) {
  ordered <- character(); remaining <- nodes
  while (length(remaining)) {
    incoming <- pairs$to[pairs$from %in% remaining & pairs$to %in% remaining]
    ready <- setdiff(remaining, incoming)
    if (length(ready) != 1L) return(character())
    ordered <- c(ordered, ready); remaining <- setdiff(remaining, ready)
  }
  if (length(ordered) < 2L || !all(vapply(2:length(ordered), function(t)
      any(pairs$from == ordered[t - 1L] & pairs$to == ordered[t]), logical(1)))) return(character())
  ordered
}

# 保守核 stayer：只接受块内逐项写出的完整固定截距/斜率，不推断继承或简写约束。
# 最后一类为 logit 参照；每个相邻转移都必须在 tolerance 内接近单位矩阵。
ch7_stayer_block <- function(statements, chain, classes, tolerance, overall = character()) {
  worst <- 0
  for (t in 2:length(chain)) {
    from <- chain[t - 1L]; to <- chain[t]; K <- unname(classes[to])
    if (K < 2L || classes[from] != K) return(NULL)
    # OVERALL 中的额外预测变量仍会影响该块，不能忽略后宣称无条件的 stayer。
    for (statement in overall) {
      r <- ch7_on(statement)
      if (!is.null(r) && any(sub("#.*$", "", r$lhs) == to) &&
          any(sub("#.*$", "", r$rhs) != from)) return(NULL)
    }
    targets <- paste0(to, "#", seq_len(K - 1L)); sources <- paste0(from, "#", seq_len(K - 1L))
    intercept <- rep(NA_real_, K - 1L); slope <- matrix(NA_real_, K - 1L, K - 1L)
    for (statement in statements) {
      m <- regmatches(statement, regexec("^\\s*\\[([^]]+)\\]\\s*(?:\\([^)]*\\))?\\s*$",
                                        statement, perl = TRUE))[[1]]
      if (length(m)) {
        tokens <- strsplit(toupper(trimws(m[2])), "\\s+")[[1]]
        tokens <- tokens[sub("#.*$", "", tokens) == to]
        if (length(tokens)) {
          idx <- match(sub("@.*$", "", tokens), targets)
          values <- suppressWarnings(as.numeric(sub("^[^@]*@", "", tokens)))
          if (anyNA(idx) || any(!grepl("@", tokens)) || any(!is.finite(values)) ||
              anyDuplicated(idx) || any(!is.na(intercept[idx]))) return(NULL)
          intercept[idx] <- values
        }
      }
      r <- ch7_on(statement)
      if (!is.null(r) && any(sub("#.*$", "", r$lhs) == to)) {
        rows <- match(r$lhs, targets); cols <- match(r$rhs, sources)
        if (anyNA(rows) || anyNA(cols) || any(!r$fixed) || any(!is.finite(r$values)) ||
            anyDuplicated(rows) || anyDuplicated(cols) || any(!is.na(slope[rows, cols]))) return(NULL)
        slope[rows, cols] <- rep(r$values, each = length(rows))
      }
    }
    if (anyNA(intercept) || anyNA(slope)) return(NULL)
    # 行为来源类别，列为去向类别；稳定 softmax 避免极端有限 logit 溢出。
    logits <- rbind(t(sweep(slope, 1L, intercept, "+")), intercept)
    logits <- cbind(logits, 0)
    weights <- exp(logits - apply(logits, 1L, max))
    probabilities <- weights / rowSums(weights)
    worst <- max(worst, abs(probabilities - diag(K)))
  }
  if (worst > tolerance) NULL else list(max_identity_difference = worst)
}

# 从 INP 判定家族：只看语法（CLASSES、KNOWNCLASS、类别变量之间的 ON、类别块约束），不看 TITLE 或注释
ch7_classify_inp <- function(path = NULL, text = NULL, stayer_tolerance = 1e-3) {
  if (!is.numeric(stayer_tolerance) || length(stayer_tolerance) != 1L ||
      !is.finite(stayer_tolerance) || stayer_tolerance < 0 || stayer_tolerance >= 0.5)
    stop("stayer_tolerance must be one finite number in [0, 0.5)")
  if (is.null(text)) text <- readLines(path, warn = FALSE)
  sec <- ch7_inp_sections(text)
  var <- ch7_statements(sec[["VARIABLE"]]); ana <- ch7_statements(sec[["ANALYSIS"]])
  names_all <- ch7_varlist(ch7_option(var, "NAMES"))
  classes <- ch7_classes(ch7_option(var, "CLASSES"))
  known <- ch7_varlist(ch7_option(var, "KNOWNCLASS"))[1]
  if (is.na(known)) known <- character()
  categorical <- ch7_varlist(ch7_option(var, "CATEGORICAL"), names_all)
  nominal <- ch7_varlist(ch7_option(var, "NOMINAL"), names_all)
  used <- ch7_varlist(ch7_option(var, "USEVARIABLES"), names_all)
  if (!length(used)) used <- names_all
  type <- toupper(ch7_option(ana, "TYPE") %||% "")
  starts <- trimws(ch7_option(ana, "STARTS") %||% "")
  blocks <- ch7_model_blocks(sec[["MODEL"]])
  ons <- lapply(blocks$statement, ch7_on)
  is_factor <- grepl("\\s(BY|\\|)\\s|\\|", blocks$statement, ignore.case = TRUE)
  evidence <- character(); approximations <- character()
  base <- function(family, subtype = NA_character_)
    list(family = family, registry_family = switch(family, LPA = , LCA = , LPA_LCA_MIXED = "LPA_LCA",
         LTA = "LTA", MS_LTA = "MS_LTA", APIM = "APIM", NA_character_), subtype = subtype,
         step3 = FALSE, classes = classes, higher_order = NA_character_, knownclass = if (length(known)) known else NA_character_,
         used = used, categorical = categorical, nominal = nominal, evidence = evidence, approximations = approximations)
  mixture <- grepl("MIXTURE", type) || length(classes) > 0L
  if (!mixture) {
    # APIM：两个结局各自回归到同一组（至少两个）预测变量上，且两结局残差相关；只认结构，不核二人含义
    reg <- Filter(Negate(is.null), ons)
    by_y <- list()
    for (r in reg) for (y in r$lhs) by_y[[y]] <- unique(c(by_y[[y]], r$rhs))
    withs <- lapply(blocks$statement[grepl("\\sWITH\\s", blocks$statement, ignore.case = TRUE)], function(s)
      toupper(strsplit(trimws(gsub("\\([^)]*\\)|[@*][^ ]*", " ", s)), "\\s+WITH\\s+|\\s+", perl = TRUE)[[1]]))
    ys <- names(by_y)
    for (i in seq_along(ys)) for (j in seq_along(ys)) if (i < j) {
      shared <- intersect(by_y[[ys[i]]], by_y[[ys[j]]])
      linked <- any(vapply(withs, function(w) all(c(ys[i], ys[j]) %in% w), logical(1)))
      if (length(shared) >= 2L && linked) {
        evidence <- c(evidence, sprintf("%s and %s share predictors %s and have a residual WITH", ys[i], ys[j],
                                        paste(shared, collapse = " ")))
        out <- base("APIM", "structure match; dyadic roles not verified"); out$evidence <- evidence
        return(out)
      }
    }
    out <- base("OTHER", if (any(is_factor)) "continuous latent model" else "no mixture or APIM structure")
    return(out)
  }
  latent <- names(classes)
  evidence <- c(evidence, paste("CLASSES =", paste0(latent, "(", classes, ")", collapse = " ")))
  if (any(is_factor)) {
    evidence <- c(evidence, "continuous latent factor (BY or |) inside a mixture")
    out <- base("OTHER_MIXTURE", "factor or growth mixture (for example RI-LTA, GMM)"); out$evidence <- evidence
    return(out)
  }
  # 类别变量之间的 ON：去掉 #k 下标
  edges <- do.call(rbind, lapply(seq_along(ons), function(i) {
    r <- ons[[i]]; if (is.null(r)) return(NULL)
    lhs <- sub("#.*$", "", r$lhs); rhs <- sub("#.*$", "", r$rhs)
    grid <- expand.grid(to = unique(lhs[lhs %in% latent]), k = seq_along(rhs), stringsAsFactors = FALSE)
    grid <- grid[rhs[grid$k] %in% latent & rhs[grid$k] != grid$to, , drop = FALSE]
    if (!nrow(grid)) return(NULL)
    data.frame(from = rhs[grid$k], to = grid$to, fixed = r$fixed[grid$k], value = r$values[grid$k],
               namespace = blocks$namespace[i], block = blocks$block[i], stringsAsFactors = FALSE)
  }))
  if (is.null(edges)) edges <- data.frame(from = character(), to = character(), fixed = logical(), value = numeric(),
                                          namespace = character(), block = character())
  # 高阶类别：自己的命名空间里写了其他类别变量之间的转移
  higher <- latent[vapply(latent, function(h) any(edges$namespace == h & edges$from != h & edges$to != h), logical(1))]
  chain <- setdiff(latent, c(higher, known))
  indicators <- setdiff(used, c(latent, known, unlist(lapply(Filter(Negate(is.null), ons), function(r)
    if (any(sub("#.*$", "", r$lhs) %in% latent)) setdiff(r$rhs, latent)))))
  step3 <- length(nominal) > 0L && starts == "0" && all(vapply(nominal, function(n)
    any(grepl(paste0("\\[\\s*", n, "#[0-9]+\\s*@"), blocks$statement, ignore.case = TRUE)), logical(1)))
  finish <- function(family, subtype = NA_character_) {
    out <- base(family, subtype); out$step3 <- step3; out$evidence <- evidence
    out$approximations <- approximations; out$higher_order <- if (length(higher)) paste(higher, collapse = " ") else NA_character_
    if (step3) out$evidence <- c(out$evidence, "STARTS = 0 with fixed nominal thresholds (Step-3 input)")
    out
  }
  if (length(chain) == 1L && !length(higher)) {
    measured <- setdiff(indicators, nominal)
    kind <- if (step3) "LCA" else if (length(measured) && all(measured %in% categorical)) "LCA"
            else if (!any(measured %in% categorical)) "LPA" else "LPA_LCA_MIXED"
    return(finish(kind, if (length(known)) paste("multiple-group by KNOWNCLASS", known) else NA_character_))
  }
  pairs <- unique(edges[edges$from %in% chain & edges$to %in% chain, c("from", "to")])
  chain <- ch7_transition_chain(chain, pairs)
  if (!length(chain)) {
    evidence <- c(evidence, "class variables do not define an unambiguous directed transition chain")
    return(finish("OTHER_MIXTURE", "several class variables without a transition chain"))
  }
  evidence <- c(evidence, paste("transition chain", paste(chain, collapse = " -> ")))
  extra <- nrow(pairs) - (length(chain) - 1L)
  if (extra > 0L) evidence <- c(evidence, sprintf("%d additional class-to-class paths (not first-order only)", extra))
  if (length(higher) == 1L && !length(known)) {
    h <- higher
    groups <- unique(blocks$block[blocks$namespace == h & grepl("#", blocks$block)])
    state <- vapply(groups, function(b) {
      e <- edges[edges$namespace == h & edges$block == b & edges$from %in% chain & edges$to %in% chain, ]
      if (!nrow(e)) "none" else if (all(e$fixed)) "fixed" else "free"
    }, character(1))
    evidence <- c(evidence, paste0("MODEL ", h, ": ", paste0(groups, "=", state, collapse = " ")))
    if (any(state == "fixed") && any(state != "fixed")) {
      verified <- lapply(groups[state == "fixed"], function(b)
        ch7_stayer_block(blocks$statement[blocks$namespace == h & blocks$block == b],
                         chain, classes, stayer_tolerance,
                         blocks$statement[blocks$namespace == "OVERALL" & blocks$block == "OVERALL"]))
      verified <- Filter(Negate(is.null), verified)
      if (length(verified)) {
        difference <- max(vapply(verified, `[[`, 0, "max_identity_difference"))
        approximations <- c(approximations, sprintf(
          "stayer transitions verified from finite logits: max identity difference %s <= tolerance %s; not exact 0/1",
          format(difference), format(stayer_tolerance)))
        return(finish("MS_LTA", paste("mover/stayer by", h)))
      }
    }
    return(finish("OTHER_MIXTURE", paste("higher-order", h, "without a verified stayer transition block")))
  }
  if (length(higher) || length(known)) {
    g <- c(known, higher)[1]
    return(finish("LTA", paste("multiple-group by", if (length(known)) "KNOWNCLASS" else "latent", g)))
  }
  finish("LTA")
}

# ---- 类别枚举汇总（lpa-lca-workflow.md 第 2 节） ----
# 读一个 K 的 .out：拟合、分类质量、LRT、最小类比例、最优 LL 是否复现；单个类别变量才收
ch7_enumeration_row <- function(path) {
  text <- readLines(path, warn = FALSE)
  start <- grep("^\\s*INPUT INSTRUCTIONS\\s*$", text); stop_at <- grep("INPUT READING TERMINATED", text)
  if (length(start) != 1L || !length(stop_at)) stop(basename(path), ": echoed INPUT INSTRUCTIONS not found")
  inp <- ch7_classify_inp(text = text[(start + 1L):(stop_at[1] - 1L)])
  if (length(inp$classes) != 1L) stop(basename(path), ": enumeration needs exactly one latent class variable")
  m <- MplusAutomation::readModels(path, what = c("summaries", "class_counts", "warn_err"), quiet = TRUE)
  s <- m$summaries
  value_of <- function(k) if (!is.null(s[[k]]) && length(s[[k]])) as.numeric(s[[k]][1]) else NA_real_
  K <- unname(inp$classes)
  props <- function(x) if (is.data.frame(x) && "proportion" %in% names(x)) x$proportion else numeric()
  estimated <- props(m$class_counts$modelEstimated); likely <- props(m$class_counts$mostLikely)
  terminated <- any(grepl("THE MODEL ESTIMATION TERMINATED NORMALLY", text, fixed = TRUE))
  # 未收敛时可以没有最终类别表，保留诊断行；已有但损坏的表及成功输出仍严格核 K。
  if (length(estimated) != K && (terminated || length(estimated) > 0L))
    stop(basename(path), ": estimated class table has ", length(estimated), " rows for K = ", K)
  joined <- paste(text, collapse = " ")
  replicated <- if (grepl("BEST LOGLIKELIHOOD VALUE HAS BEEN REPLICATED", joined, fixed = TRUE)) TRUE
                else if (grepl("BEST LOGLIKELIHOOD VALUE WAS NOT REPLICATED", joined, fixed = TRUE)) FALSE else NA
  data.frame(file = basename(path), sha256 = digest::digest(file = path, algo = "sha256"), K = K,
    latent = names(inp$classes), terminated_normally = terminated,
    best_ll_replicated = replicated, parameters = value_of("Parameters"), observations = value_of("Observations"),
    LL = value_of("LL"), AIC = value_of("AIC"), BIC = value_of("BIC"), aBIC = value_of("aBIC"),
    entropy = if (K == 1L) NA_real_ else value_of("Entropy"),
    min_prop_estimated = if (length(estimated)) min(estimated) else NA_real_,
    min_prop_most_likely = if (length(likely)) min(likely) else NA_real_,
    VLMR_p = value_of("T11_VLMR_PValue"), LMR_p = value_of("T11_LMR_PValue"), BLRT_p = value_of("BLRT_PValue"),
    warnings = length(m$warnings), errors = length(m$errors),
    usevariables = paste(sort(inp$used), collapse = " "),
    stringsAsFactors = FALSE)
}

# 多个 K 的汇总表：每个准则单列标记，不合成一个「最优 K」；最终取舍按联合判据由研究者记录
ch7_enumeration_table <- function(paths, min_class_prop = NULL, min_entropy = NULL, alpha = 0.05) {
  if (!length(paths) || !all(file.exists(paths))) stop("Every enumeration output must exist")
  rows <- do.call(rbind, lapply(paths, ch7_enumeration_row))
  rows <- rows[order(rows$K), , drop = FALSE]; rownames(rows) <- NULL
  if (anyDuplicated(rows$K)) stop("Each class count may appear only once")
  if (length(unique(rows$latent)) != 1L || length(unique(rows$usevariables)) != 1L ||
      length(unique(rows$observations[!is.na(rows$observations)])) > 1L)
    stop("Enumeration outputs must share the latent variable, USEVARIABLES and number of observations")
  # 全部输出失败时没有拟合值，不产生 min(numeric(0)) 警告或最优标记。
  lowest <- function(x) if (all(is.na(x))) rep(FALSE, length(x)) else !is.na(x) & x == min(x, na.rm = TRUE)
  rows$lowest_BIC <- lowest(rows$BIC); rows$lowest_aBIC <- lowest(rows$aBIC); rows$lowest_AIC <- lowest(rows$AIC)
  for (k in c("VLMR", "LMR", "BLRT")) rows[[paste0(k, "_significant")]] <- !is.na(rows[[paste0(k, "_p")]]) & rows[[paste0(k, "_p")]] < alpha
  rows$entropy_ok <- if (is.null(min_entropy)) NA else !is.na(rows$entropy) & rows$entropy >= min_entropy
  rows$class_size_ok <- if (is.null(min_class_prop)) NA else rows$min_prop_estimated >= min_class_prop
  attr(rows, "selection") <- paste("Not selected automatically: combine fit, classification quality, class size,",
                                   "replication and substantive interpretability (lpa-lca-workflow.md section 2).")
  rows
}

# ---- Step-1 存盘 → Step-3 输入绑定（lta-workflow.md：每个 Step-3 输入与 Step-1 savedata 有明确 hash 关系） ----
# Step-1 .out 的 SAVEDATA INFORMATION：列序与存盘文件名
ch7_savedata_info <- function(text) {
  i <- grep("^\\s*SAVEDATA INFORMATION\\s*$", text)
  if (length(i) != 1L) return(NULL)
  tail <- text[i[1]:length(text)]
  order_at <- grep("Order and format of variables", tail, fixed = TRUE); save_at <- grep("^\\s*Save file\\s*$", tail)
  if (length(order_at) != 1L || length(save_at) != 1L || save_at[1] == length(tail)) return(NULL)
  # Mplus 新版把 Save file 放在变量序之前；两种布局都只读紧接的格式行。
  rows <- character(); row_at <- order_at[1] + 1L
  while (row_at <= length(tail) && !nzchar(trimws(tail[row_at]))) row_at <- row_at + 1L
  while (row_at <= length(tail) && grepl("^\\s*[A-Za-z][A-Za-z0-9_]*\\s+[FEG][0-9]+\\.[0-9]+\\s*$", tail[row_at])) {
    rows <- c(rows, trimws(tail[row_at])); row_at <- row_at + 1L
  }
  if (!length(rows)) return(NULL)
  file_at <- save_at[1] + 1L
  while (file_at <= length(tail) && !nzchar(trimws(tail[file_at]))) file_at <- file_at + 1L
  if (file_at > length(tail)) return(NULL)
  list(names = toupper(sub("\\s+[FEG][0-9]+\\.[0-9]+$", "", rows)),
       formats = sub("^.*\\s+([FEG][0-9]+\\.[0-9]+)$", "\\1", rows),
       file = sub("^([\"'])(.*)\\1$", "\\2", trimws(tail[file_at])))
}

# DATA FILE 按 INP 所在目录解析，不能用同名文件代替真正的数据源。
ch7_data_path <- function(value, input_dir) {
  if (length(value) != 1L || is.na(value) || !nzchar(value)) stop("Step-3 INP has no DATA FILE")
  windows <- .Platform$OS.type == "windows"
  if (!windows && (grepl("^[A-Za-z]:", value) || grepl("\\\\", value)))
    stop("Windows DATA FILE paths cannot be resolved on this platform")
  if (windows && grepl("^[A-Za-z]:[^/\\\\]", value)) stop("Drive-relative DATA FILE paths are unsupported")
  absolute <- grepl("^/", value) || (windows && grepl("^[A-Za-z]:[/\\\\]|^\\\\\\\\", value))
  path <- if (absolute) value else file.path(input_dir, value)
  normalizePath(path, winslash = "/", mustWork = TRUE)
}

# 先把 INP 声明的数值缺失码按列还原成 NA，再与 Step-1 的存盘投影比较。
# 支持全局代码、ALL(code) 和变量清单(code)；复杂或不识别的形式明确拒绝。
ch7_missing_codes <- function(value, names) {
  result <- stats::setNames(rep(list(numeric()), length(names)), names)
  if (is.null(value)) return(result)
  value <- trimws(value)
  if (value %in% c("*", ".")) return(result)
  number <- "[-+]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[Ee][-+]?[0-9]+)?"
  codes <- function(x) {
    tokens <- strsplit(trimws(x), "[ ,]+")[[1]]
    if (!length(tokens) || any(!grepl(paste0("^", number, "$"), tokens, perl = TRUE)))
      stop("Unsupported MISSING declaration: expected finite numeric codes")
    values <- as.numeric(tokens)
    if (any(!is.finite(values))) stop("Unsupported MISSING declaration: non-finite code")
    values
  }
  if (!grepl("[()]", value)) {
    result[] <- rep(list(codes(value)), length(names))
    return(result)
  }
  groups <- regmatches(value, gregexpr("[^()]+\\([^()]*\\)", value, perl = TRUE))[[1]]
  remainder <- trimws(gsub("[^()]+\\([^()]*\\)", "", value, perl = TRUE))
  if (!length(groups) || nzchar(remainder)) stop("Unsupported MISSING declaration")
  for (group in groups) {
    m <- regmatches(group, regexec("^\\s*([^()]+)\\(([^()]*)\\)$", group, perl = TRUE))[[1]]
    targets <- if (toupper(trimws(m[2])) == "ALL") names else ch7_varlist(trimws(m[2]), names)
    if (!length(targets) || any(!targets %in% names)) stop("Unsupported MISSING variable list")
    for (n in targets) result[[n]] <- unique(c(result[[n]], codes(m[3])))
  }
  result
}

# 绑定核对：Step-1 正常结束且存盘名一致；Step-3 INP 读的就是这份 DAT；按 ID 对行，Step-3 每列都能
# 从 Step-1 存盘投影出来；Step-3 固定的分类误差 logit 与给定的误差矩阵（行 = 真类别，列 = 赋类）一致。
# 误差矩阵由调用方从 Step-1 输出取得并记录来源；本函数不解析 Step-1 的分类概率表。
ch7_step3_binding <- function(step1_out, step1_savedata, step3_inp, step3_dat = NULL, id, nominal_map, error,
                              value_tolerance = 1e-6, logit_tolerance = 1e-6) {
  for (p in c(step1_out, step1_savedata, step3_inp)) if (!file.exists(p)) stop("Missing file: ", p)
  sha <- function(p) digest::digest(file = p, algo = "sha256")
  checks <- list(); reasons <- character(); extra <- list()
  check <- function(name, ok, why) { checks[[name]] <<- isTRUE(ok); if (!isTRUE(ok)) reasons <<- c(reasons, why) }
  out1 <- readLines(step1_out, warn = FALSE)
  check("step1_terminated_normally", any(grepl("THE MODEL ESTIMATION TERMINATED NORMALLY", out1, fixed = TRUE)),
        "Step-1 output does not report normal termination")
  info <- ch7_savedata_info(out1)
  check("step1_savedata_declared", !is.null(info), "Step-1 output has no SAVEDATA INFORMATION block")
  check("step1_savedata_name_matches", !is.null(info) && toupper(basename(info$file)) == toupper(basename(step1_savedata)),
        "Step-1 output saved a different file")
  sec <- ch7_inp_sections(readLines(step3_inp, warn = FALSE))
  data_file <- trimws(ch7_option(ch7_statements(sec[["DATA"]]), "FILE") %||% "")
  data_file <- sub("^([\"'])(.*)\\1$", "\\2", data_file)
  declared_dat <- ch7_data_path(data_file, dirname(step3_inp))
  if (is.null(step3_dat)) step3_dat <- declared_dat
  if (!file.exists(step3_dat)) stop("Missing file: ", step3_dat)
  check("step3_inp_reads_step3_dat", identical(declared_dat, normalizePath(step3_dat, winslash = "/", mustWork = TRUE)),
        "Step-3 INP DATA FILE is not the Step-3 DAT under review")
  finish <- function() c(list(status = if (length(reasons)) "FAIL" else "PASS", checks = checks, reasons = reasons,
    files = lapply(list(step1_out = step1_out, step1_savedata = step1_savedata, step3_inp = step3_inp, step3_dat = step3_dat),
                   function(p) list(file = basename(p), sha256 = sha(p))),
    error_matrix = "supplied by the caller; record which Step-1 output table it came from"), extra)
  variable <- ch7_statements(sec[["VARIABLE"]])
  names3 <- ch7_varlist(ch7_option(variable, "NAMES")); nominal3 <- ch7_varlist(ch7_option(variable, "NOMINAL"), names3)
  read_dat <- function(p) as.matrix(utils::read.table(p, header = FALSE, na.strings = c("*", "."), colClasses = "numeric"))
  d1 <- read_dat(step1_savedata); d3 <- read_dat(step3_dat)
  names1 <- if (is.null(info)) character() else info$names
  check("step1_columns_match_declared_order", length(names1) == ncol(d1), "Step-1 savedata column count differs from its declared order")
  check("step3_columns_match_names", length(names3) == ncol(d3), "Step-3 DAT column count differs from NAMES")
  if (length(names1) != ncol(d1) || length(names3) != ncol(d3)) return(finish())
  colnames(d1) <- names1; colnames(d3) <- names3; id <- toupper(id)
  missing <- ch7_missing_codes(ch7_option(variable, "MISSING"), names3)
  for (n in names3) d3[d3[, n] %in% missing[[n]], n] <- NA_real_
  check("id_in_both", id %in% names1 && id %in% names3, "ID column missing from Step-1 savedata or Step-3 DAT")
  if (!(id %in% names1 && id %in% names3)) return(finish())
  check("ids_unique", !anyNA(d1[, id]) && !anyNA(d3[, id]) && !anyDuplicated(d1[, id]) && !anyDuplicated(d3[, id]),
        "IDs are missing or repeated")
  check("same_ids", nrow(d1) == nrow(d3) && setequal(d1[, id], d3[, id]), "Step-1 and Step-3 rows do not have the same IDs")
  map <- stats::setNames(toupper(unname(nominal_map)), toupper(names(nominal_map)))
  source_of <- vapply(names3, function(v) if (v %in% names(map)) map[[v]] else v, character(1))
  check("nominal_map_covers_nominal", setequal(names(map), nominal3), "nominal_map must name exactly the NOMINAL variables")
  check("every_step3_column_has_a_source", all(source_of %in% names1),
        paste("Step-3 columns without a Step-1 source:", paste(names3[!source_of %in% names1], collapse = " ")))
  extra$row_order_identical <- NA
  if (isTRUE(checks$ids_unique) && isTRUE(checks$same_ids) && isTRUE(checks$every_step3_column_has_a_source)) {
    rows <- match(d3[, id], d1[, id])
    projected <- vapply(names3, function(v) {
      a <- unname(d3[, v]); b <- unname(d1[rows, source_of[[v]]])
      identical(is.na(a), is.na(b)) && all(abs(a[!is.na(a)] - b[!is.na(b)]) <= value_tolerance)
    }, logical(1))
    check("projected_values_match", all(projected), paste("Step-3 values differ from Step-1 for:", paste(names3[!projected], collapse = " ")))
    extra$row_order_identical <- identical(rows, seq_len(nrow(d1)))
  }
  # 一个矩阵用于各波；未命名的列表按 NOMINAL 顺序对应（与 ch7_mixture_object 的 step3$error 相同）
  error <- if (is.matrix(error)) stats::setNames(rep(list(error), length(nominal3)), nominal3) else error
  if (is.list(error) && is.null(names(error)) && length(error) == length(nominal3)) names(error) <- nominal3
  names(error) <- toupper(names(error))
  check("error_given_for_each_nominal", setequal(names(error), nominal3), "error must give one matrix per NOMINAL variable")
  model <- ch7_model_blocks(sec[["MODEL"]]); extra$max_abs_logit_diff <- list()
  for (n in intersect(nominal3, names(error))) {
    e <- error[[n]]; K <- if (is.matrix(e)) nrow(e) else 0L
    valid <- is.matrix(e) && is.numeric(e) && K >= 2L && ncol(e) == K && all(e > 0) && all(abs(rowSums(e) - 1) < 1e-9)
    check(paste0(n, "_error_matrix_valid"), valid, paste("Classification error matrix for", n, "is not a valid KxK probability matrix"))
    if (!valid) next
    observed <- d3[, n][!is.na(d3[, n])]
    check(paste0(n, "_values_in_1_to_K"), all(observed %in% seq_len(K)), paste(n, "takes values outside 1..K"))
    # [n#a@v] 所在块 %c#j% 的 j 是真类别
    pattern <- paste0("(?i)(?<![A-Za-z0-9_])", n, "#([0-9]+)\\s*@\\s*(-?[0-9]*\\.?[0-9]+(?:[eE][-+]?[0-9]+)?)")
    found <- matrix(NA_real_, K, K - 1L); clash <- FALSE
    for (i in seq_len(nrow(model))) {
      j <- suppressWarnings(as.integer(sub("^.*#", "", model$block[i])))
      for (x in regmatches(model$statement[i], gregexpr(pattern, model$statement[i], perl = TRUE))[[1]]) {
        parts <- regmatches(x, regexec(pattern, x, perl = TRUE))[[1]]
        a <- as.integer(parts[2]); v <- as.numeric(parts[3])
        if (is.na(j) || j < 1L || j > K || a < 1L || a > K - 1L || !is.na(found[j, a])) { clash <- TRUE; next }
        found[j, a] <- v
      }
    }
    complete <- !clash && !anyNA(found)
    check(paste0(n, "_fixed_logits_present"), complete, paste("Step-3 INP does not fix exactly one logit per class and category for", n))
    if (complete) {
      diff <- max(abs(found - log(e[, -K, drop = FALSE] / e[, K])))
      extra$max_abs_logit_diff[[n]] <- diff
      check(paste0(n, "_fixed_logits_match_error"), diff <= logit_tolerance,
            paste("Fixed logits for", n, "differ from the classification error matrix"))
    }
  }
  extra$rows <- nrow(d3); extra$columns <- ncol(d3)
  finish()
}
