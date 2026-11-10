# 转移流数据与显示分离；不读取原研究数据、不估计模型、不安装包、不导出文件。
# 完整输入合同及合成例子：references/chapter7-transition-flow.md。

ch7_transition_flow_data <- function(distribution, transitions, wave_map, class_map,
                                    mode, condition, source_id, scale = NULL,
                                    tolerance = 1e-8) {
  fail <- function(...) stop(..., call. = FALSE)
  text <- function(x, name) {
    if (!is.character(x) || anyNA(x) || any(!nzchar(trimws(x))))
      fail(name, " must contain non-empty character values")
  }
  scalar_text <- function(x, name) {
    text(x, name)
    if (length(x) != 1L) fail(name, " must be one string")
  }
  frame <- function(x, fields, name) {
    if (!is.data.frame(x) || !nrow(x) || anyDuplicated(names(x)) ||
        !all(fields %in% names(x))) fail(name, " requires columns: ", paste(fields, collapse = ", "))
  }
  numeric_values <- function(x, name, probability = FALSE) {
    if (!is.numeric(x) || any(!is.finite(x)) || any(x < 0) ||
        (probability && any(x > 1))) fail(name, " must be finite, non-negative numeric values",
                                         if (probability) " in [0, 1]" else "")
  }
  # 长度前缀防止波次/类别名称中的分隔符产生键碰撞。
  key <- function(w, c) paste0(nchar(w), ":", w, nchar(c), ":", c)
  scalar_text(mode, "mode"); scalar_text(condition, "condition"); scalar_text(source_id, "source_id")
  if (!mode %in% c("posterior_count", "mover_scaled")) fail("mode must be posterior_count or mover_scaled")
  if (mode == "posterior_count" && condition != "overall") fail("posterior_count requires condition='overall'")
  if (mode == "mover_scaled" && condition == "overall") fail("mover_scaled requires an explicit mover condition")
  if (!is.numeric(tolerance) || length(tolerance) != 1L || !is.finite(tolerance) || tolerance < 0)
    fail("tolerance must be one finite non-negative number")
  if (mode == "posterior_count" && !is.null(scale)) fail("scale applies only to mover_scaled")
  if (mode == "mover_scaled" && (!is.numeric(scale) || length(scale) != 1L || !is.finite(scale) || scale <= 0))
    fail("mover_scaled requires an explicit finite positive scale")
  frame(wave_map, c("wave", "label"), "wave_map")
  frame(class_map, c("wave", "class", "semantic", "label", "colour"), "class_map")
  value_name <- if (mode == "posterior_count") "count" else "proportion"
  frame(distribution, c("wave", "class", value_name), "distribution")
  edge_fields <- c("from_wave", "from_class", "to_wave", "to_class")
  frame(transitions, c(edge_fields, "probability"), "transitions")
  for (f in c("wave", "label")) text(wave_map[[f]], paste0("wave_map$", f))
  for (f in c("wave", "class", "semantic", "label", "colour")) text(class_map[[f]], paste0("class_map$", f))
  for (f in c("wave", "class")) text(distribution[[f]], paste0("distribution$", f))
  for (f in edge_fields) text(transitions[[f]], paste0("transitions$", f))
  if (nrow(wave_map) < 2L || anyDuplicated(wave_map$wave)) fail("wave_map needs at least two distinct ordered waves")
  if (!setequal(class_map$wave, wave_map$wave)) fail("class_map must cover exactly the declared waves")
  if (any(!grepl("^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$", class_map$colour)))
    fail("class_map$colour must use explicit #RRGGBB or #RRGGBBAA colours")
  cm_key <- key(class_map$wave, class_map$class)
  d_key <- key(distribution$wave, distribution$class)
  if (anyDuplicated(cm_key) || anyDuplicated(d_key) || !setequal(cm_key, d_key))
    fail("distribution and class_map must have exactly one matching row per wave/class")
  if (anyDuplicated(key(class_map$wave, class_map$semantic))) fail("semantic classes must be unique within each wave")
  for (s in unique(class_map$semantic)) {
    rows <- class_map$semantic == s
    if (length(unique(class_map$label[rows])) != 1L || length(unique(toupper(class_map$colour[rows]))) != 1L)
      fail("one semantic class must retain its declared label and colour across waves")
  }
  numeric_values(distribution[[value_name]], paste0("distribution$", value_name), mode == "mover_scaled")
  numeric_values(transitions$probability, "transitions$probability", TRUE)

  # 节点顺序由显式波次顺序和各波 class_map 行顺序决定；不解析类别编号末位。
  nodes <- class_map[order(match(class_map$wave, wave_map$wave), seq_len(nrow(class_map))), , drop = FALSE]
  rownames(nodes) <- NULL
  node_key <- key(nodes$wave, nodes$class)
  nodes$id <- seq_len(nrow(nodes)) - 1L
  nodes$wave_label <- wave_map$label[match(nodes$wave, wave_map$wave)]
  nodes$input_value <- distribution[[value_name]][match(node_key, d_key)]
  totals <- vapply(wave_map$wave, function(w) sum(nodes$input_value[nodes$wave == w]), numeric(1))
  if (any(!is.finite(totals)) || any(totals <= 0)) fail("each wave must have finite positive total mass")
  nodes$proportion <- if (mode == "posterior_count") nodes$input_value / totals[match(nodes$wave, wave_map$wave)] else nodes$input_value
  nodes$weight <- if (mode == "posterior_count") nodes$input_value else round(nodes$input_value * scale)
  if (any(!is.finite(nodes$weight))) fail("scaled node weights overflowed")
  from <- match(key(transitions$from_wave, transitions$from_class), node_key)
  to <- match(key(transitions$to_wave, transitions$to_class), node_key)
  if (anyNA(from) || anyNA(to)) fail("every transition endpoint must have an explicit wave/class mapping")
  from_wave <- match(transitions$from_wave, wave_map$wave)
  to_wave <- match(transitions$to_wave, wave_map$wave)
  if (any(to_wave != from_wave + 1L)) fail("transitions must run forward between adjacent declared waves")
  edge_key <- paste(from, to, sep = ":")
  if (anyDuplicated(edge_key)) fail("duplicate transition endpoint pair")
  expected <- unlist(lapply(seq_len(nrow(wave_map) - 1L), function(i) {
    a <- which(nodes$wave == wave_map$wave[i]); b <- which(nodes$wave == wave_map$wave[i + 1L])
    as.vector(outer(a, b, paste, sep = ":"))
  }), use.names = FALSE)
  if (!setequal(edge_key, expected)) fail("all adjacent class pairs must be explicit; missing edges are not zero-filled")
  links <- transitions[order(from, to), c(edge_fields, "probability"), drop = FALSE]
  rownames(links) <- NULL
  from <- match(key(links$from_wave, links$from_class), node_key)
  to <- match(key(links$to_wave, links$to_class), node_key)
  links$source <- nodes$id[from]; links$target <- nodes$id[to]
  links$source_weight <- nodes$weight[from]
  links$value <- links$probability * links$source_weight
  if (any(!is.finite(links$value))) fail("edge weights overflowed")
  links$semantic <- nodes$semantic[from]
  # 独立group key避免真实语义名称恰好等于transparent时发生碰撞。
  semantics <- unique(nodes$semantic)
  nodes$group <- paste0("class_", match(nodes$semantic, semantics))
  links$group <- ifelse(links$value == 0, "zero_flow", nodes$group[from])
  palette <- data.frame(group = c(paste0("class_", seq_along(semantics)), "zero_flow"),
                        colour = c(nodes$colour[match(semantics, nodes$semantic)], "#00000000"),
                        stringsAsFactors = FALSE)

  # 舍入/模型口径不一致只报告；绝不重新归一化概率或平衡节点流量。
  sources <- which(nodes$wave != tail(wave_map$wave, 1))
  row_sums <- data.frame(wave = nodes$wave[sources], class = nodes$class[sources],
    total = vapply(nodes$id[sources], function(id) sum(links$probability[links$source == id]), numeric(1)),
    stringsAsFactors = FALSE)
  row_sums$delta <- row_sums$total - 1
  row_sums$within_tolerance <- abs(row_sums$delta) <= tolerance
  wave_sums <- data.frame(wave = wave_map$wave,
    total = vapply(wave_map$wave, function(w) sum(nodes$proportion[nodes$wave == w]), numeric(1)), stringsAsFactors = FALSE)
  wave_sums$delta <- wave_sums$total - 1
  wave_sums$within_tolerance <- abs(wave_sums$delta) <= tolerance
  balance <- data.frame(wave = nodes$wave, class = nodes$class, declared_weight = nodes$weight,
    incoming = vapply(nodes$id, function(id) sum(links$value[links$target == id]), numeric(1)),
    outgoing = vapply(nodes$id, function(id) sum(links$value[links$source == id]), numeric(1)), stringsAsFactors = FALSE)
  balance$incoming_delta <- ifelse(nodes$wave == wave_map$wave[1], NA_real_, balance$incoming - nodes$weight)
  balance$outgoing_delta <- ifelse(nodes$wave == tail(wave_map$wave, 1), NA_real_, balance$outgoing - nodes$weight)
  issues <- character()
  if (!all(row_sums$within_tolerance)) issues <- c(issues, "TRANSITION_ROW_SUM_DIFFERS_FROM_ONE")
  if (!all(wave_sums$within_tolerance)) issues <- c(issues, "DISTRIBUTION_SUM_DIFFERS_FROM_ONE")
  if (any(abs(c(balance$incoming_delta, balance$outgoing_delta)) > tolerance, na.rm = TRUE))
    issues <- c(issues, "FLOW_DIFFERS_FROM_DECLARED_NODE_WEIGHT")
  if (!any(links$value > 0)) issues <- c(issues, "NO_POSITIVE_FLOW")
  units <- if (mode == "posterior_count") "posterior-weighted expected flow" else paste0("scaled mover weight (scale=", format(scale, scientific = FALSE, trim = TRUE), ")")
  structure(list(nodes = nodes, links = links, palette = palette,
    semantics = list(mode = mode, condition = condition, source_id = source_id, units = units,
      formula = if (mode == "posterior_count") "posterior count * transition probability" else "round(proportion * scale) * conditional transition probability",
      scale = scale, rounding = if (mode == "mover_scaled") "R round() of each scaled node proportion; no probability rounding" else "none",
      observed_transition_counts = FALSE, normalized = FALSE),
    quality = list(status = if (length(issues)) "LIMITED" else "INTERNALLY_CONSISTENT_ONLY",
      issues = issues, tolerance = tolerance, row_sums = row_sums, wave_sums = wave_sums,
      node_balance = balance, renderable = any(links$value > 0),
      note = "NetworkD3 sizes nodes from link totals; declared proportions are labels, not independent node heights. Internal consistency does not validate model fit or class equivalence.")),
    class = "ch7_transition_flow")
}

ch7_transition_sankey <- function(flow, show_wave = TRUE, percentage_digits = 1L,
                                  node_width = 40, font_size = 13, node_padding = 20) {
  if (!inherits(flow, "ch7_transition_flow")) stop("flow must come from ch7_transition_flow_data()", call. = FALSE)
  if (!is.logical(show_wave) || length(show_wave) != 1L || is.na(show_wave) ||
      !is.numeric(percentage_digits) || length(percentage_digits) != 1L || !is.finite(percentage_digits) ||
      percentage_digits != as.integer(percentage_digits) || percentage_digits < 0 || percentage_digits > 6)
    stop("show_wave must be TRUE/FALSE; percentage_digits must be an integer from 0 to 6", call. = FALSE)
  for (x in list(node_width, font_size, node_padding))
    if (!is.numeric(x) || length(x) != 1L || !is.finite(x) || x <= 0) stop("render sizes must be finite positive numbers", call. = FALSE)
  if (!isTRUE(flow$quality$renderable)) stop("No positive flow to render", call. = FALSE)
  if (!requireNamespace("networkD3", quietly = TRUE))
    stop("Rendering requires the R package 'networkD3'; install it in the selected R environment. No package was installed.", call. = FALSE)
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Rendering requires the R package 'jsonlite'; no package was installed.", call. = FALSE)
  if (length(flow$quality$issues)) warning("Flow quality is LIMITED: ", paste(flow$quality$issues, collapse = ", "), "; inputs are unchanged", call. = FALSE)
  nodes <- flow$nodes
  nodes$name <- paste0(if (show_wave) paste0(nodes$wave_label, " - ") else "", nodes$label,
                       " (", round(nodes$proportion * 100, percentage_digits), "%)")
  colours <- paste0("d3.scaleOrdinal().domain(", jsonlite::toJSON(flow$palette$group), ")",
                    ".range(", jsonlite::toJSON(flow$palette$colour), ")")
  p <- networkD3::sankeyNetwork(Links = flow$links, Nodes = nodes, Source = "source", Target = "target",
    Value = "value", NodeID = "name", NodeGroup = "group", LinkGroup = "group", colourScale = colours,
    nodeWidth = node_width, fontSize = font_size, nodePadding = node_padding, units = flow$semantics$units,
    iterations = 0, sinksRight = TRUE)
  attr(p, "transition_flow_semantics") <- flow$semantics
  attr(p, "transition_flow_quality") <- flow$quality
  p
}
