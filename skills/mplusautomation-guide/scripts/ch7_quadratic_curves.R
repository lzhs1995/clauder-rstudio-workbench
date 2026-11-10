# 二次项的对数比值导数；只消费明确的系数和协方差，不读取数据或运行模型。
ch7_quadratic_curve_data <- function(coefficients, vcov, terms, x_grid, scale,
                                     source_id, covariance_type, variable,
                                     variable_scale, outcome, reference,
                                     ci_level = 0.90, ci_rule = "normal_quantile",
                                     critical_value = NULL) {
  text_one <- function(x, field) {
    if (!is.character(x) || length(x) != 1L || is.na(x) || !nzchar(trimws(x)))
      stop(field, " must be an explicit non-empty string", call. = FALSE)
  }
  unique_names <- function(x) {
    !is.null(x) && !anyNA(x) && all(nzchar(trimws(x))) && !anyDuplicated(x)
  }
  for (field in c("scale", "source_id", "covariance_type", "variable",
                  "variable_scale", "outcome", "reference", "ci_rule"))
    text_one(get(field), field)
  if (!scale %in% c("binary_log_odds", "multinomial_log_probability_ratio"))
    stop("scale must be binary_log_odds or multinomial_log_probability_ratio; probability effects are unsupported", call. = FALSE)
  if (identical(outcome, reference))
    stop("outcome and reference must identify different categories", call. = FALSE)
  if (!is.numeric(coefficients) || !is.null(dim(coefficients)) ||
      !length(coefficients) || !unique_names(names(coefficients)) ||
      any(!is.finite(coefficients)))
    stop("coefficients must be a finite numeric vector with unique names", call. = FALSE)
  if (!is.character(terms) || length(terms) != 2L ||
      !unique_names(names(terms)) || !setequal(names(terms), c("linear", "quadratic")) ||
      anyNA(terms) || any(!nzchar(trimws(terms))) || anyDuplicated(unname(terms)))
    stop("terms must map distinct coefficient names using linear and quadratic", call. = FALSE)
  terms <- terms[c("linear", "quadratic")]
  if (!all(terms %in% names(coefficients)))
    stop("mapped terms are missing from coefficients", call. = FALSE)
  if (!is.matrix(vcov) || !is.numeric(vcov) || nrow(vcov) < 2L ||
      nrow(vcov) != ncol(vcov) || any(!is.finite(vcov)) ||
      !unique_names(rownames(vcov)) || !unique_names(colnames(vcov)) ||
      !setequal(rownames(vcov), colnames(vcov)))
    stop("vcov must be a finite square numeric matrix with unique matching row/column names", call. = FALSE)
  if (!all(terms %in% rownames(vcov)))
    stop("mapped terms are missing from vcov", call. = FALSE)
  # 按名字对齐，不把位置相同当作同一参数；不改调用者的原矩阵。
  aligned <- vcov[rownames(vcov), rownames(vcov), drop = FALSE]
  if (any(aligned != t(aligned)))
    stop("vcov is not symmetric after name alignment; it was not repaired", call. = FALSE)
  if (any(diag(aligned) < 0))
    stop("vcov contains a negative parameter variance; it was not clipped", call. = FALSE)
  eigenvalues <- eigen(aligned, symmetric = TRUE, only.values = TRUE)$values
  if (any(!is.finite(eigenvalues)) || min(eigenvalues) < 0)
    stop("vcov is not positive semidefinite at the supplied precision; inspect the original covariance, do not silently repair it", call. = FALSE)
  if (!is.numeric(x_grid) || !is.null(dim(x_grid)) || !length(x_grid) ||
      any(!is.finite(x_grid)))
    stop("x_grid must be an explicit non-empty finite numeric vector", call. = FALSE)
  if (!is.numeric(ci_level) || length(ci_level) != 1L ||
      !is.finite(ci_level) || ci_level <= 0 || ci_level >= 1)
    stop("ci_level must be strictly between 0 and 1", call. = FALSE)
  if (!ci_rule %in% c("normal_quantile", "fixed_critical"))
    stop("ci_rule must be normal_quantile or fixed_critical", call. = FALSE)
  if (ci_rule == "normal_quantile") {
    if (!is.null(critical_value))
      stop("critical_value must be NULL for normal_quantile", call. = FALSE)
    z <- stats::qnorm(1 - (1 - ci_level) / 2)
  } else {
    if (!is.numeric(critical_value) || length(critical_value) != 1L ||
        !is.finite(critical_value) || critical_value <= 0)
      stop("fixed_critical requires an explicit finite positive critical_value", call. = FALSE)
    z <- critical_value
  }
  beta <- coefficients[unname(terms)]
  covariance <- aligned[unname(terms), unname(terms), drop = FALSE]
  # 保留完整交叉协方差。负 x 时交叉项变号；不得省略或取绝对值。
  x <- unname(x_grid)
  estimate <- unname(beta[1] + 2 * beta[2] * x)
  variance <- covariance[1, 1] + 4 * x * covariance[1, 2] +
    4 * x^2 * covariance[2, 2]
  if (any(!is.finite(estimate)) || any(!is.finite(variance)))
    stop("curve calculation is non-finite; input values were not changed", call. = FALSE)
  if (any(variance < 0))
    stop("curve has a negative variance at the supplied precision; it was not clipped", call. = FALSE)
  se <- sqrt(variance)
  lower <- estimate - z * se
  upper <- estimate + z * se
  if (any(!is.finite(lower)) || any(!is.finite(upper)))
    stop("confidence limits are non-finite", call. = FALSE)
  curve <- data.frame(x = x, estimate = estimate, variance = unname(variance),
                      std_error = unname(se), lower = lower, upper = upper)
  structure(list(data = curve,
    semantics = list(scale = scale, variable = variable, variable_scale = variable_scale,
      outcome = outcome, reference = reference, source_id = source_id,
      covariance_type = covariance_type, terms = terms,
      formula = "b_linear + 2 * b_quadratic * x",
      variance_formula = "V_linear,linear + 4*x*V_linear,quadratic + 4*x^2*V_quadratic,quadratic",
      model_term_assumption = "The supplied contrast contains b_linear*x + b_quadratic*x^2 on the declared x scale; caller binds the actual model and covariance.",
      probability_effect = FALSE, covariance_type_is_caller_declared = TRUE,
      intervals = "pointwise normal-approximation intervals, not simultaneous bands",
      ci = list(rule = ci_rule, nominal_level = ci_level, critical_value = z,
                nominal_level_matched_by_rule = ci_rule == "normal_quantile",
                value_rule = if (ci_rule == "normal_quantile") "qnorm(1-(1-ci_level)/2); no rounding" else
                  "caller-supplied numeric critical value retained without rounding; nominal level not certified",
                implied_normal_coverage = 2 * stats::pnorm(z) - 1)),
    parameters = list(coefficients = beta, covariance = covariance),
    quality = list(status = "INPUT_CONTRACT_VALIDATED_ONLY", repaired = FALSE,
      vcov_min_eigenvalue = min(eigenvalues), vcov_dimension = nrow(aligned),
      source_model_verified = FALSE, historical_plot_accepted = FALSE,
      real_data_swap_accepted = FALSE,
      note = "No model, reference-class, clustering or source-data identity is inferred from valid input numbers.")),
    class = "ch7_quadratic_curve")
}

ch7_quadratic_curve_plot <- function(curve, title = NULL) {
  if (!inherits(curve, "ch7_quadratic_curve"))
    stop("curve must come from ch7_quadratic_curve_data()", call. = FALSE)
  if (!is.null(title) && (!is.character(title) || length(title) != 1L || is.na(title)))
    stop("title must be NULL or one string", call. = FALSE)
  if (length(unique(curve$data$x)) < 2L)
    stop("Rendering a curve requires at least two distinct x_grid values", call. = FALSE)
  if (!requireNamespace("ggplot2", quietly = TRUE))
    stop("Rendering requires the R package 'ggplot2' in the selected R environment; no package was installed", call. = FALSE)
  # 渲染副本按 x 排序；数据函数仍保留输入网格原顺序，不写图片或文件。
  d <- curve$data[order(curve$data$x), , drop = FALSE]
  s <- curve$semantics
  y_label <- paste0(if (s$scale == "binary_log_odds") "Log-odds derivative: " else "Log probability-ratio derivative: ",
                    s$outcome, " vs ", s$reference)
  ci_label <- if (s$ci$rule == "fixed_critical")
    paste0("fixed critical=", format(s$ci$critical_value, digits = 12),
           "; declared nominal=", 100 * s$ci$nominal_level, "% (not certified)") else
    paste0("normal-quantile CI=", 100 * s$ci$nominal_level, "%")
  p <- ggplot2::ggplot(d, ggplot2::aes(x = x, y = estimate)) +
    ggplot2::geom_ribbon(ggplot2::aes(ymin = lower, ymax = upper), fill = "#235789", alpha = .18) +
    ggplot2::geom_line(colour = "#235789", linewidth = .7) +
    ggplot2::geom_hline(yintercept = 0, linetype = 2, colour = "grey50") +
    ggplot2::theme_bw(base_size = 11) +
    ggplot2::labs(x = paste0(s$variable, " [", s$variable_scale, "]"),
      y = y_label, title = title,
      caption = paste(s$source_id, s$covariance_type, ci_label, "pointwise; model/source not verified", sep = " | "))
  attr(p, "quadratic_curve_semantics") <- s
  attr(p, "quadratic_curve_quality") <- curve$quality
  p
}
