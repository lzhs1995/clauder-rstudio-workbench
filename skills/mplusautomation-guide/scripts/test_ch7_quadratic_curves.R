# 仅合成系数/VCOV；核公式、语义和拒绝分支，不运行模型或重绘历史图。
test_ch7_quadratic_curves <- function(output_dir, skill_root) {
  if (file.exists(output_dir)) stop("Fresh output directory required")
  dir.create(output_dir, recursive = TRUE)
  source(file.path(skill_root, "scripts/ch7_quadratic_curves.R"), local = TRUE)
  checks <- list()
  check <- function(name, ok) {
    if (!isTRUE(ok)) stop("Contract failed: ", name)
    checks[[name]] <<- TRUE
  }
  reject <- function(name, expr, pattern) {
    err <- tryCatch({ force(expr); NULL }, error = identity)
    check(name, inherits(err, "error") && grepl(pattern, conditionMessage(err), fixed = TRUE))
  }
  near <- function(a, b, tol = 1e-12) isTRUE(all.equal(unname(a), unname(b), tolerance = tol))
  beta <- c(linear_a = .3, quadratic_a = .05, nuisance = 1)
  V <- matrix(c(.04, .006, 0, .006, .0025, 0, 0, 0, .2), 3,
              dimnames = list(names(beta), names(beta)))
  grid <- c(-3, -1, 0, 2)
  args <- list(coefficients = beta, vcov = V,
    terms = c(linear = "linear_a", quadratic = "quadratic_a"), x_grid = grid,
    scale = "binary_log_odds", source_id = "synthetic_curve_A",
    covariance_type = "cluster_HC0_declared", variable = "duration",
    variable_scale = "years centered on the declared baseline",
    outcome = "event", reference = "no_event")
  make <- function(...) do.call(ch7_quadratic_curve_data, utils::modifyList(args, list(...), keep.null = TRUE))
  original <- serialize(args, NULL)
  f <- make()
  check("explicit_quadratic_derivative", near(f$data$estimate, c(0, .2, .3, .5)))
  # 预先手算的四个方差值包含负 x 的负交叉项，不能用同一实现生成期望值。
  check("cross_covariance_and_negative_x", near(f$data$variance, c(.058, .026, .04, .128)))
  check("standard_error_from_variance", near(f$data$std_error, sqrt(c(.058, .026, .04, .128))))
  check("qnorm90_is_not_rounded_history", near(f$semantics$ci$critical_value, 1.64485362695147) &&
    f$semantics$ci$critical_value != 1.645)
  fixed <- make(ci_rule = "fixed_critical", critical_value = 1.645)
  check("historical_critical_retained", identical(fixed$semantics$ci$critical_value, 1.645) &&
    near(fixed$data$upper - fixed$data$estimate, 1.645 * sqrt(c(.058, .026, .04, .128))))
  check("fixed_nominal_and_implied_coverage_separate", identical(fixed$semantics$ci$nominal_level, .90) &&
    fixed$semantics$ci$implied_normal_coverage != .90 && identical(fixed$semantics$ci$rule, "fixed_critical") &&
    !fixed$semantics$ci$nominal_level_matched_by_rule)
  f95 <- make(ci_level = .95)
  check("95_vs_90_ci", near(f95$semantics$ci$critical_value, 1.95996398454005) &&
    all(f95$data$upper > f$data$upper) && identical(f95$data$estimate, f$data$estimate))
  check("input_bytes_unchanged", identical(original, serialize(args, NULL)))
  check("quality_does_not_claim_scientific_acceptance", !f$quality$repaired &&
    !f$quality$source_model_verified && !f$quality$historical_plot_accepted &&
    !f$quality$real_data_swap_accepted && !f$semantics$probability_effect)
  check("declared_covariance_and_scale_preserved", identical(f$semantics$covariance_type, args$covariance_type) &&
    identical(f$semantics$variable_scale, args$variable_scale) &&
    identical(f$semantics$reference, "no_event"))
  # 重排系数、矩阵行列、terms自身顺序；全都用名字对应，不能依赖数组位置。
  shuffled <- make(coefficients = beta[c(3, 2, 1)], vcov = V[c(2, 3, 1), c(3, 1, 2)],
                    terms = args$terms[2:1])
  check("named_mapping_survives_independent_permutations", identical(f$data, shuffled$data))
  beta2 <- beta; names(beta2) <- c("renamed_x", "renamed_x_squared", "other")
  V2 <- V; dimnames(V2) <- list(names(beta2), names(beta2))
  renamed <- make(coefficients = beta2, vcov = V2,
                  terms = c(quadratic = "renamed_x_squared", linear = "renamed_x"),
                  variable = "renamed_variable", source_id = "synthetic_curve_B")
  check("variable_and_term_renaming", identical(f$data, renamed$data) &&
    identical(renamed$semantics$variable, "renamed_variable"))
  multi <- make(scale = "multinomial_log_probability_ratio", outcome = "group_blue", reference = "group_gold")
  check("multinomial_contrast_is_log_probability_ratio", identical(f$data, multi$data) &&
    identical(multi$semantics$scale, "multinomial_log_probability_ratio") && !multi$semantics$probability_effect)
  unordered <- make(x_grid = grid[c(4, 1, 3, 2)])
  check("input_grid_order_preserved", identical(unordered$data$x, grid[c(4, 1, 3, 2)]))
  zero <- V; zero[,] <- 0
  degenerate <- make(vcov = zero)
  check("explicit_zero_variance_not_invented", all(degenerate$data$std_error == 0) &&
    identical(degenerate$data$lower, degenerate$data$estimate))
  reject("missing_reference_rejected", make(reference = NULL), "reference must be")
  reject("same_reference_rejected", make(reference = "event"), "different categories")
  reject("probability_scale_not_implied", make(scale = "probability"), "probability effects are unsupported")
  reject("undeclared_covariance_rejected", make(covariance_type = " "), "covariance_type must be")
  reject("undeclared_variable_scale_rejected", make(variable_scale = ""), "variable_scale must be")
  reject("missing_coefficient_rejected", make(coefficients = beta[-1]), "mapped terms are missing from coefficients")
  reject("term_alias_collision_rejected", make(terms = c(linear = "linear_a", quadratic = "linear_a")), "distinct coefficient names")
  reject("unnamed_coefficients_rejected", make(coefficients = unname(beta)), "unique names")
  bad <- beta; names(bad)[2] <- names(bad)[1]
  reject("duplicate_coefficient_names_rejected", make(coefficients = bad), "unique names")
  for (value in c(NA_real_, NaN, Inf)) {
    bad <- beta; bad[1] <- value
    reject(paste0("nonfinite_coefficient_", value), make(coefficients = bad), "finite numeric vector")
    reject(paste0("nonfinite_x_", value), make(x_grid = c(0, value)), "finite numeric vector")
  }
  bad <- V; bad[1, 2] <- bad[1, 2] + .001
  reject("asymmetric_vcov_rejected_not_averaged", make(vcov = bad), "not symmetric")
  bad <- V; bad[1, 1] <- -.04
  reject("negative_parameter_variance_rejected", make(vcov = bad), "negative parameter variance")
  bad <- V; bad[1, 2] <- bad[2, 1] <- .02
  reject("indefinite_vcov_rejected_even_if_grid_is_zero", make(vcov = bad, x_grid = 0), "not positive semidefinite")
  bad <- V; bad[2, 1] <- NA_real_
  reject("triangular_missing_vcov_not_filled", make(vcov = bad), "finite square numeric matrix")
  bad <- V; colnames(bad)[2] <- "wrong_name"
  reject("unmatched_vcov_axis_names_rejected", make(vcov = bad), "matching row/column names")
  reject("missing_vcov_term_rejected", make(vcov = V[c(1, 3), c(1, 3)]), "mapped terms are missing from vcov")
  reject("invalid_ci_level_rejected", make(ci_level = 1), "strictly between")
  reject("ambiguous_ci_configuration_rejected", make(critical_value = 1.645), "must be NULL")
  reject("missing_fixed_critical_rejected", make(ci_rule = "fixed_critical"), "explicit finite positive")
  reject("invalid_fixed_critical_rejected", make(ci_rule = "fixed_critical", critical_value = 0), "explicit finite positive")
  reject("overflow_not_repaired", make(x_grid = c(0, 1e308)), "non-finite")
  # 只构造ggplot并读构建层；不启动浏览器或保存任何图片。
  if (requireNamespace("ggplot2", quietly = TRUE)) {
    prior <- serialize(unordered, NULL)
    plot <- ch7_quadratic_curve_plot(unordered)
    layer <- ggplot2::ggplot_build(plot)$data
    check("plot_uses_exact_curve_and_ci", near(layer[[1]]$ymin, f$data$lower) &&
      near(layer[[1]]$ymax, f$data$upper) && near(layer[[2]]$y, f$data$estimate))
    check("plot_sort_does_not_mutate_input", identical(prior, serialize(unordered, NULL)))
    check("plot_metadata_and_scale", identical(attr(plot, "quadratic_curve_semantics"), unordered$semantics) &&
      grepl("Log-odds derivative", plot$labels$y, fixed = TRUE))
    plot_multi <- ch7_quadratic_curve_plot(multi)
    check("plot_multinomial_reference_label", grepl("Log probability-ratio derivative: group_blue vs group_gold", plot_multi$labels$y, fixed = TRUE))
    plot_fixed <- ch7_quadratic_curve_plot(fixed)
    check("plot_fixed_critical_label", grepl("fixed critical=1.645", plot_fixed$labels$caption, fixed = TRUE))
    extreme <- make(ci_rule = "fixed_critical", critical_value = 99)
    check("arbitrary_fixed_critical_does_not_certify_nominal_ci", !extreme$semantics$ci$nominal_level_matched_by_rule &&
      grepl("not certified", ch7_quadratic_curve_plot(extreme)$labels$caption, fixed = TRUE))
  } else {
    reject("missing_ggplot2_readable_error", ch7_quadratic_curve_plot(f), "Rendering requires the R package 'ggplot2'")
  }
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Test receipt requires jsonlite")
  jsonlite::write_json(list(status = "PASS_SYNTHETIC_QUADRATIC_CURVE_CONTRACT_ONLY", checks = checks,
    ggplot_built = requireNamespace("ggplot2", quietly = TRUE), new_model_calls = 0L,
    browser_calls = 0L, historical_plot_acceptance = FALSE, real_data_swap_acceptance = FALSE),
    file.path(output_dir, "QUADRATIC_CURVE_TEST_RESULT.json"), pretty = TRUE, auto_unbox = TRUE)
  cat("CH7_QUADRATIC_CURVES_PASS", length(checks), "checks; models=0; browser=0\n")
  invisible(checks)
}
