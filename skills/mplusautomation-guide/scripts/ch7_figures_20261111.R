# readModels 对象的显式映射适配器；不估计、不改原对象、不导出文件。
# 已有流图与二次曲线算法分别复用 ch7_transition_flow.R / ch7_quadratic_curves.R。
ch7_figure_frame <- function(x, fields, name) {
  if (!is.data.frame(x) || !nrow(x) || anyDuplicated(names(x)) || !all(fields %in% names(x)))
    stop(name, " requires columns: ", paste(fields, collapse = ", "), call. = FALSE)
  invisible(x)
}
ch7_figure_key <- function(...) {
  xs <- list(...)
  do.call(paste0, lapply(xs, function(x) paste0(nchar(as.character(x)), ":", as.character(x))))
}
ch7_figure_mapping <- function(mapping) {
  if (!is.list(mapping) || !is.character(mapping$source_id) || length(mapping$source_id) != 1L ||
      is.na(mapping$source_id) || !nzchar(mapping$source_id)) stop("mapping needs source_id", call. = FALSE)
  ch7_figure_frame(mapping$variables, c("variable", "label"), "mapping$variables")
  ch7_figure_frame(mapping$classes, c("variable", "class", "label", "colour"), "mapping$classes")
  for (d in list(mapping$variables, mapping$classes)) for (n in names(d))
    if (!is.character(d[[n]]) || anyNA(d[[n]]) || any(!nzchar(d[[n]])))
      stop("mapping columns must contain non-empty strings", call. = FALSE)
  if (anyDuplicated(mapping$variables$variable) ||
      anyDuplicated(ch7_figure_key(mapping$classes$variable, mapping$classes$class)) ||
      anyDuplicated(ch7_figure_key(mapping$classes$variable, mapping$classes$label)) ||
      !setequal(mapping$classes$variable, mapping$variables$variable))
    stop("mapping requires unique variable/class keys and matching coverage", call. = FALSE)
  if (any(!grepl("^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$", mapping$classes$colour)))
    stop("class colours must be explicit hex colours", call. = FALSE)
  invisible(mapping)
}
ch7_figure_labels <- function(d, mapping, variable = "variable", class = "class") {
  k <- match(ch7_figure_key(d[[variable]], d[[class]]),
             ch7_figure_key(mapping$classes$variable, mapping$classes$class))
  if (anyNA(k)) stop("data contains an unmapped variable/class", call. = FALSE)
  d$class_label <- mapping$classes$label[k]
  d$colour <- mapping$classes$colour[k]
  d$variable_label <- mapping$variables$label[match(d[[variable]], mapping$variables$variable)]
  d$source_id <- mapping$source_id
  d
}
ch7_figure_classes <- function(labels, variable, mapping) {
  labels <- as.character(labels)
  direct <- paste0(variable, "#")
  if (all(startsWith(labels, direct))) {
    if (anyDuplicated(labels)) stop("duplicate direct class profile rows", call. = FALSE)
    return(substring(labels, nchar(direct) + 1L))
  }
  if (nrow(mapping$variables) == 1L && all(grepl("^[0-9]+$", labels))) {
    if (anyDuplicated(labels)) stop("duplicate single-class profile rows", call. = FALSE)
    return(labels)
  }
  order <- mapping$latent_order
  if (!is.character(order) || anyNA(order) || anyDuplicated(order) || !variable %in% order)
    stop("joint class labels require explicit latent_order", call. = FALSE)
  parts <- strsplit(labels, ".", fixed = TRUE)
  if (any(lengths(parts) != length(order)) || any(!vapply(parts, function(z) all(grepl("^[0-9]+$", z)), logical(1))))
    stop("unsupported class labels for selected variable", call. = FALSE)
  if (!setequal(order, mapping$variables$variable) || anyDuplicated(labels))
    stop("joint labels need a complete unique latent mapping", call. = FALSE)
  sizes <- vapply(order, function(v) sum(mapping$classes$variable == v), integer(1))
  if (length(labels) != prod(sizes)) stop("incomplete joint-class profile table", call. = FALSE)
  for (j in seq_along(order)) if (!all(vapply(parts, `[`, character(1), j) %in%
    mapping$classes$class[mapping$classes$variable == order[j]])) stop("unknown joint class", call. = FALSE)
  vapply(parts, `[`, character(1), match(variable, order))
}

ch7_profile_data <- function(model, mapping) {
  ch7_figure_mapping(mapping)
  declared <- model$input$variable$classes
  if (is.character(declared) && length(declared) == 1L && !is.null(mapping$latent_order)) {
    tokens <- regmatches(declared, gregexpr("[A-Za-z][A-Za-z0-9_]*[[:space:]]*\\([0-9]+\\)", declared))[[1]]
    order <- toupper(sub("[[:space:]]*\\(.*", "", tokens))
    if (length(order) && !identical(toupper(mapping$latent_order), order))
      stop("latent_order differs from the model's CLASSES declaration", call. = FALSE)
  }
  p <- mapping$profiles
  ch7_figure_frame(p, c("variable", "param", "statistic", "category", "label", "panel"), "mapping$profiles")
  if (!all(p$statistic %in% c("mean", "probability")) ||
      !all(p$variable %in% mapping$variables$variable) ||
      anyDuplicated(ch7_figure_key(p$variable, p$param, p$statistic, p$category)))
    stop("invalid or duplicated profile mapping", call. = FALSE)
  out <- lapply(seq_len(nrow(p)), function(i) {
    spec <- p[i, , drop = FALSE]
    z <- model$parameters[[if (spec$statistic == "mean") "unstandardized" else "probability.scale"]]
    ch7_figure_frame(z, c("param", "est", "LatentClass"), "model parameter table")
    take <- toupper(as.character(z$param)) == toupper(spec$param)
    if (spec$statistic == "mean") {
      if (!"paramHeader" %in% names(z)) stop("mean table lacks paramHeader", call. = FALSE)
      take <- take & toupper(z$paramHeader) == "MEANS"
    } else {
      if (!"category" %in% names(z) || is.na(spec$category) || !nzchar(spec$category))
        stop("probability profile requires an explicit response category", call. = FALSE)
      take <- take & as.character(z$category) == spec$category
    }
    z <- z[take & !is.na(take), , drop = FALSE]
    if (!nrow(z)) stop("mapped profile row is absent: ", spec$param, call. = FALSE)
    # 具名潜类表先筛选；联合表保留全部其他条件用于一致性核验。
    named <- grepl("#", as.character(z$LatentClass), fixed = TRUE)
    if (any(named)) z <- z[startsWith(as.character(z$LatentClass), paste0(spec$variable, "#")), , drop = FALSE]
    if (!nrow(z)) stop("mapped latent variable has no profile rows", call. = FALSE)
    cls <- ch7_figure_classes(z$LatentClass, spec$variable, mapping)
    expected <- mapping$classes$class[mapping$classes$variable == spec$variable]
    if (!setequal(unique(cls), expected)) stop("profile class coverage differs from mapping", call. = FALSE)
    # readModels的概率等值检验尾段可能把整列变为字符；仅转换已明确选中的数值行。
    if (is.character(z$est)) {
      if (anyNA(z$est) || any(!grepl("^[+-]?([0-9]+(\\.[0-9]*)?|\\.[0-9]+)([Ee][+-]?[0-9]+)?$", trimws(z$est))))
        stop("selected profile estimates contain nonnumeric parser text", call. = FALSE)
      z$est <- as.numeric(z$est)
    }
    if (!is.numeric(z$est) || any(!is.finite(z$est)) ||
        (spec$statistic == "probability" && any(z$est < 0 | z$est > 1)))
      stop("profile estimates must be finite and probabilities in [0,1]", call. = FALSE)
    do.call(rbind, lapply(expected, function(k) {
      values <- unique(z$est[cls == k])
      if (length(values) != 1L) stop("profile varies across other joint-class conditions; cannot collapse", call. = FALSE)
      data.frame(variable = spec$variable, class = k, param = spec$param,
        statistic = spec$statistic, category = spec$category, indicator = spec$label,
        panel = spec$panel, value = values, source_rows = sum(cls == k), stringsAsFactors = FALSE)
    }))
  })
  d <- ch7_figure_labels(do.call(rbind, out), mapping)
  attr(d, "mapping") <- mapping
  attr(d, "semantics") <- "Explicit conditional means/probabilities; equal redundant joint conditions collapsed without averaging."
  d
}

ch7_proportion_data <- function(model, mapping, method) {
  ch7_figure_mapping(mapping)
  if (length(method) != 1L || !method %in% c("modelEstimated", "posteriorProb", "mostLikely"))
    stop("method must select one declared class-count measure", call. = FALSE)
  d <- model$class_counts[[method]]
  ch7_figure_frame(d, c("class", "count", "proportion"), "class_counts")
  if (!"variable" %in% names(d)) {
    if (nrow(mapping$variables) != 1L) stop("single-class table needs exactly one mapped latent variable", call. = FALSE)
    d$variable <- mapping$variables$variable
  }
  d$class <- as.character(d$class); d$variable <- as.character(d$variable)
  k <- ch7_figure_key(d$variable, d$class)
  expected <- ch7_figure_key(mapping$classes$variable, mapping$classes$class)
  if (anyDuplicated(k) || !setequal(k, expected)) stop("class count coverage differs from mapping", call. = FALSE)
  if (any(!is.finite(d$count)) || any(d$count < 0) || any(!is.finite(d$proportion)) || any(d$proportion < 0 | d$proportion > 1))
    stop("invalid counts/proportions", call. = FALSE)
  d <- d[match(expected, k), , drop = FALSE]; d$method <- method
  d <- ch7_figure_labels(d, mapping)
  attr(d, "mapping") <- mapping
  attr(d, "sums") <- aggregate(proportion ~ variable, d, sum)
  d
}

ch7_matrix_data <- function(model, mapping) {
  ch7_figure_mapping(mapping)
  p <- mapping$matrices
  ch7_figure_frame(p, c("from_variable", "to_variable", "condition", "kind", "label"), "mapping$matrices")
  if (anyNA(p) || any(!nzchar(as.matrix(p))) ||
      anyDuplicated(ch7_figure_key(p$from_variable, p$to_variable))) stop("invalid matrix mapping", call. = FALSE)
  if (any(!p$kind %in% c("marginal_transition", "conditional_initial")) ||
      any(p$kind == "marginal_transition" & p$condition != "overall") ||
      any(p$kind == "conditional_initial" & p$condition != paste0("given ", p$from_variable)))
    stop("printed matrices support overall transitions or explicitly conditioned initial distributions", call. = FALSE)
  z <- model$class_counts$transitionProbs
  ch7_figure_frame(z, c("from", "to", "probability"), "transitionProbs")
  endpoints <- paste(mapping$classes$variable, mapping$classes$class, sep = ".")
  if (anyDuplicated(endpoints)) stop("ambiguous endpoint names", call. = FALSE)
  from <- match(z$from, endpoints); to <- match(z$to, endpoints)
  if (anyNA(from) || anyNA(to)) stop("transition endpoint absent from explicit class mapping", call. = FALSE)
  d <- data.frame(from_variable = mapping$classes$variable[from], from_class = mapping$classes$class[from],
    to_variable = mapping$classes$variable[to], to_class = mapping$classes$class[to], probability = z$probability,
    from_label = mapping$classes$label[from], to_label = mapping$classes$label[to], stringsAsFactors = FALSE)
  d$matrix_index <- match(ch7_figure_key(d$from_variable, d$to_variable), ch7_figure_key(p$from_variable, p$to_variable))
  if (anyNA(d$matrix_index)) stop("every printed matrix requires an explicit condition mapping", call. = FALSE)
  if (any(!is.finite(d$probability)) || any(d$probability < 0 | d$probability > 1) ||
      anyDuplicated(ch7_figure_key(d$from_variable, d$from_class, d$to_variable, d$to_class)))
    stop("invalid or duplicate transition probabilities", call. = FALSE)
  for (i in seq_len(nrow(p))) {
    a <- mapping$classes$class[mapping$classes$variable == p$from_variable[i]]
    b <- mapping$classes$class[mapping$classes$variable == p$to_variable[i]]
    expected <- as.vector(outer(a, b, ch7_figure_key))
    have <- d[d$matrix_index == i, , drop = FALSE]
    if (!length(a) || !length(b) || !setequal(ch7_figure_key(have$from_class, have$to_class), expected))
      stop("matrix must contain every explicitly mapped class pair", call. = FALSE)
  }
  d$condition <- p$condition[d$matrix_index]; d$kind <- p$kind[d$matrix_index]
  d$panel <- p$label[d$matrix_index]; d$source_id <- mapping$source_id
  attr(d, "mapping") <- mapping
  attr(d, "row_sums") <- aggregate(probability ~ from_variable + from_class + to_variable, d, sum)
  d
}

ch7_enumeration_data <- function(models, mapping) {
  ch7_figure_frame(mapping, c("model_id", "K", "source_id", "dataset_id", "indicator_set"), "enumeration mapping")
  if (!is.list(models) || is.null(names(models)) || anyDuplicated(names(models)) ||
      !setequal(names(models), mapping$model_id) || anyDuplicated(mapping$model_id) ||
      !is.numeric(mapping$K) || any(!is.finite(mapping$K) | mapping$K < 1 | mapping$K != floor(mapping$K)) ||
      anyDuplicated(mapping$K) || length(unique(mapping$dataset_id)) != 1L || length(unique(mapping$indicator_set)) != 1L)
    stop("enumeration needs unique model/K keys on the same declared data and indicators", call. = FALSE)
  rows <- lapply(seq_len(nrow(mapping)), function(i) {
    s <- models[[mapping$model_id[i]]]$summaries
    vals <- vapply(c("LL", "BIC", "Observations"), function(n) {
      x <- s[[n]]
      if (!is.numeric(x) || length(x) != 1L || !is.finite(x)) stop("missing finite enumeration summary: ", n, call. = FALSE)
      x
    }, numeric(1))
    data.frame(model_id = mapping$model_id[i], K = mapping$K[i], source_id = mapping$source_id[i],
      LL = unname(vals["LL"]), BIC = unname(vals["BIC"]), N = unname(vals["Observations"]), stringsAsFactors = FALSE)
  })
  d <- do.call(rbind, rows)
  if (length(unique(d$N)) != 1L) stop("enumeration sample sizes differ", call. = FALSE)
  d <- d[order(d$K), , drop = FALSE]
  attr(d, "selection") <- "No automatic K selection; dataset and indicator identities are caller-declared."
  d
}

ch7_figure_theme <- function() {
  if (!requireNamespace("ggplot2", quietly = TRUE)) stop("Rendering requires ggplot2", call. = FALSE)
  ggplot2::theme_minimal(base_size = 11) + ggplot2::theme(legend.position = "bottom", panel.grid.minor = ggplot2::element_blank())
}
ch7_figure_palette <- function(d) {
  keys <- unique(d$class_label)
  colours <- vapply(keys, function(k) {
    z <- unique(d$colour[d$class_label == k])
    if (length(z) != 1L) stop("one class label must use one explicit colour", call. = FALSE)
    z
  }, character(1))
  stats::setNames(colours, keys)
}
ch7_profile_plot <- function(data, title = NULL, caption = NULL, ncol = NULL) {
  ch7_figure_frame(data, c("indicator", "value", "class_label", "colour", "panel", "variable_label"), "profile data")
  palette <- ch7_figure_palette(data)
  d <- data; d$indicator <- factor(d$indicator, levels = unique(d$indicator))
  d$class_label <- factor(d$class_label, levels = unique(d$class_label))
  d$facet <- paste(d$variable_label, d$panel, sep = " | ")
  ggplot2::ggplot(d, ggplot2::aes(indicator, value, colour = class_label, group = class_label)) +
    ggplot2::geom_line(linewidth = .7) + ggplot2::geom_point(size = 2.3) +
    ggplot2::facet_wrap(~facet, ncol = ncol, scales = "free") +
    ggplot2::scale_colour_manual(values = palette) +
    ggplot2::labs(title = title, caption = caption, x = NULL, y = "Conditional value", colour = NULL) + ch7_figure_theme()
}
ch7_fixed_response_plot <- function(data, title = NULL, caption = NULL) {
  ch7_figure_frame(data, c("variable", "param", "class", "category", "class_label", "value", "statistic", "variable_label"), "response profile")
  if (any(data$statistic != "probability")) stop("fixed response plot requires probabilities", call. = FALSE)
  if (anyDuplicated(ch7_figure_key(data$variable, data$param, data$class, data$category)))
    stop("duplicate variable/indicator/class/response cells", call. = FALSE)
  d <- data; d$category <- factor(d$category, levels = unique(d$category))
  d$class_label <- factor(d$class_label, levels = unique(d$class_label))
  # 同一潜变量可有多个分类指标，每个指标独立分面，避免格位相互覆盖。
  facet_key <- ch7_figure_key(d$variable, d$param)
  facet_levels <- unique(facet_key)
  facet_labels <- paste(d$variable_label[match(facet_levels, facet_key)],
    d$param[match(facet_levels, facet_key)], sep = " | ")
  if (anyDuplicated(facet_labels)) stop("response facet labels are ambiguous", call. = FALSE)
  d$facet <- factor(facet_key, levels = facet_levels, labels = facet_labels)
  ggplot2::ggplot(d, ggplot2::aes(category, class_label, fill = value)) +
    ggplot2::geom_tile(colour = "white") + ggplot2::geom_text(ggplot2::aes(label = sprintf("%.3f", value)), size = 3) +
    ggplot2::facet_wrap(~facet) + ggplot2::scale_fill_gradient(low = "#f7fbff", high = "#08519c", limits = c(0, 1)) +
    ggplot2::labs(title = title, caption = caption, x = "Response category", y = "Latent class", fill = "Probability") + ch7_figure_theme()
}
ch7_proportion_plot <- function(data, title = NULL, caption = NULL) {
  ch7_figure_frame(data, c("variable_label", "proportion", "class_label", "colour", "method"), "proportion data")
  if (length(unique(data$method)) != 1L) stop("cannot mix class proportion measures", call. = FALSE)
  palette <- ch7_figure_palette(data); d <- data
  d$variable_label <- factor(d$variable_label, levels = unique(d$variable_label))
  d$class_label <- factor(d$class_label, levels = unique(d$class_label))
  ggplot2::ggplot(d, ggplot2::aes(variable_label, proportion, fill = class_label)) +
    ggplot2::geom_col(width = .68) + ggplot2::geom_text(ggplot2::aes(label = sprintf("%.1f%%", 100 * proportion)),
      position = ggplot2::position_stack(vjust = .5), colour = "white", size = 3) +
    ggplot2::scale_fill_manual(values = palette) + ggplot2::scale_y_continuous(limits = c(0, 1.001)) +
    ggplot2::labs(title = title, caption = caption, x = "Latent variable", y = paste(unique(data$method), "proportion"), fill = NULL) + ch7_figure_theme()
}
ch7_matrix_plot <- function(data, title = NULL, caption = NULL, ncol = NULL) {
  ch7_figure_frame(data, c("from_label", "to_label", "probability", "panel", "condition", "kind"), "matrix data")
  d <- data; d$facet <- paste(d$panel, d$condition, sep = " | ")
  map <- attr(data, "mapping")
  from_levels <- if (is.list(map)) unique(map$classes$label[map$classes$variable %in% d$from_variable]) else unique(d$from_label)
  to_levels <- if (is.list(map)) unique(map$classes$label[map$classes$variable %in% d$to_variable]) else unique(d$to_label)
  d$from_label <- factor(d$from_label, levels = from_levels); d$to_label <- factor(d$to_label, levels = to_levels)
  ggplot2::ggplot(d, ggplot2::aes(to_label, from_label, fill = probability)) + ggplot2::geom_tile(colour = "white") +
    ggplot2::geom_text(ggplot2::aes(label = sprintf("%.3f", probability)), size = 3) +
    ggplot2::facet_wrap(~facet, ncol = ncol, scales = "free") +
    ggplot2::scale_fill_gradient(low = "#f7fbff", high = "#08519c", limits = c(0, 1)) + ggplot2::scale_y_discrete(limits = rev) +
    ggplot2::labs(title = title, caption = caption, x = "Destination class", y = "Origin class", fill = "Probability") + ch7_figure_theme()
}
ch7_enumeration_plot <- function(data, title = NULL, caption = NULL) {
  ch7_figure_frame(data, c("K", "LL", "BIC", "source_id"), "enumeration data")
  d <- rbind(data.frame(K = data$K, value = data$LL, metric = "LL"), data.frame(K = data$K, value = data$BIC, metric = "BIC"))
  ggplot2::ggplot(d, ggplot2::aes(K, value)) + ggplot2::geom_line() + ggplot2::geom_point() +
    ggplot2::facet_wrap(~metric, scales = "free_y") + ggplot2::scale_x_continuous(breaks = data$K) +
    ggplot2::labs(title = title, caption = caption, x = "Classes K", y = "Printed fit value") + ch7_figure_theme()
}

# 只把显式总体边际表交给已验流图算法；不把G条件初始组成误称为mover转移。
ch7_model_flow_data <- function(model, mapping, wave_map, class_map, tolerance = 1e-8) {
  if (!exists("ch7_transition_flow_data", mode = "function")) stop("Source ch7_transition_flow.R first", call. = FALSE)
  cp <- ch7_proportion_data(model, mapping, "posteriorProb")
  tr <- ch7_matrix_data(model, mapping)
  cp <- cp[cp$variable %in% wave_map$wave, , drop = FALSE]
  tr <- tr[tr$kind == "marginal_transition" & tr$from_variable %in% wave_map$wave & tr$to_variable %in% wave_map$wave, , drop = FALSE]
  d <- data.frame(wave = cp$variable, class = cp$class, count = cp$count)
  t <- data.frame(from_wave = tr$from_variable, from_class = tr$from_class, to_wave = tr$to_variable,
    to_class = tr$to_class, probability = tr$probability)
  ch7_transition_flow_data(d, t, wave_map, class_map, mode = "posterior_count", condition = "overall",
    source_id = mapping$source_id, tolerance = tolerance)
}

# TECH3参数编号必须由调用者显式绑定到TECH1；不从SE猜协方差、不补零。
ch7_model_quadratic_curve <- function(model, mapping) {
  if (!exists("ch7_quadratic_curve_data", mode = "function")) stop("Source ch7_quadratic_curves.R first", call. = FALSE)
  t <- mapping$terms
  ch7_figure_frame(t, c("role", "paramHeader", "param", "LatentClass", "covariance_index"), "curve terms")
  if (nrow(t) != 2L || !setequal(t$role, c("linear", "quadratic")) || anyDuplicated(t$covariance_index))
    stop("curve requires distinct linear/quadratic parameter mappings", call. = FALSE)
  z <- model$parameters$unstandardized
  ch7_figure_frame(z, c("paramHeader", "param", "est"), "unstandardized parameters")
  if (!"LatentClass" %in% names(z)) z$LatentClass <- ""
  k <- match(ch7_figure_key(t$paramHeader, t$param, t$LatentClass), ch7_figure_key(z$paramHeader, z$param, z$LatentClass))
  if (anyNA(k) || anyDuplicated(ch7_figure_key(z$paramHeader, z$param, z$LatentClass))) stop("curve parameters absent or ambiguous", call. = FALSE)
  source <- mapping$covariance_source
  if (length(source) != 1L || !source %in% c("paramCov", "paramCov.savedata")) stop("select an explicit TECH3 covariance source", call. = FALSE)
  cov <- model$tech3[[source]]; ix <- t$covariance_index
  if (!is.matrix(cov) || !is.numeric(ix) || any(!is.finite(ix) | ix < 1 | ix != floor(ix)) ||
      any(ix > nrow(cov)) || nrow(cov) != ncol(cov)) stop("TECH3 covariance/index mapping unavailable", call. = FALSE)
  cov <- cov[ix, ix, drop = FALSE]; dimnames(cov) <- list(t$role, t$role)
  args <- mapping$curve
  if (!is.list(args) || any(c("coefficients", "vcov", "terms") %in% names(args))) stop("invalid curve argument mapping", call. = FALSE)
  out <- do.call(ch7_quadratic_curve_data, c(list(coefficients = stats::setNames(z$est[k], t$role), vcov = cov,
    terms = c(linear = "linear", quadratic = "quadratic")), args))
  out$semantics$covariance_source <- source
  out$semantics$parameter_mapping <- t
  out$quality$tech1_parameter_binding <- "caller-declared; numeric TECH3 indices retained"
  out
}
