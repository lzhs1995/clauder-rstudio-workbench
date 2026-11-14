# 全部数值均为合成夹具；不读研究数据、不启动Mplus。
test_ch7_figures_20261111 <- function(output_dir = NULL, skill_root = NULL,
                                    script_dir = if (is.null(skill_root)) "scripts" else file.path(skill_root, "scripts")) {
  source(file.path(script_dir, "ch7_figures_20261111.R"), local = TRUE)
  source(file.path(script_dir, "ch7_transition_flow.R"), local = TRUE)
  source(file.path(script_dir, "ch7_quadratic_curves.R"), local = TRUE)
  checks <- 0L
  ok <- function(x) { stopifnot(isTRUE(x)); checks <<- checks + 1L }
  bad <- function(expr) { ok(inherits(tryCatch(force(expr), error = identity), "error")) }
  fixture <- function(waves = c("BASE", "LATER"), K = 2L) {
    cl <- data.frame(variable = rep(waves, each = K), class = rep(as.character(seq_len(K)), length(waves)),
      label = rep(paste("Group", seq_len(K)), length(waves)), colour = rep(grDevices::hcl.colors(K), length(waves)))
    vars <- data.frame(variable = waves, label = paste("Wave", seq_along(waves)))
    profiles <- data.frame(variable = waves, param = paste0("MEASURE", seq_along(waves)), statistic = "mean",
      category = "", label = "Indicator", panel = "Continuous means")
    pars <- data.frame(paramHeader = "Means", param = rep(profiles$param, each = K),
      est = rep(seq_len(K) / K, length(waves)), LatentClass = paste0(cl$variable, "#", cl$class))
    cp <- cl[c("variable", "class")]; cp$count <- 100 / K; cp$proportion <- 1 / K
    matrices <- data.frame(from_variable = head(waves, -1), to_variable = tail(waves, -1), condition = "overall",
      kind = "marginal_transition", label = paste(head(waves, -1), "to", tail(waves, -1)))
    tr <- do.call(rbind, lapply(seq_len(nrow(matrices)), function(i) {
      g <- expand.grid(a = seq_len(K), b = seq_len(K))
      data.frame(from = paste0(matrices$from_variable[i], ".", g$a), to = paste0(matrices$to_variable[i], ".", g$b), probability = 1 / K)
    }))
    list(model = list(parameters = list(unstandardized = pars), class_counts = list(modelEstimated = cp,
      posteriorProb = cp, mostLikely = cp, transitionProbs = tr), summaries = list(LL = -123, BIC = 300, Observations = 100)),
      mapping = list(source_id = "synthetic", variables = vars, classes = cl, profiles = profiles,
        matrices = matrices, latent_order = waves))
  }
  for (waves in list(c("A", "B"), c("FIRST", "MID", "END"), c("Q1", "Q2", "Q3", "Q4"))) {
    for (K in c(2L, 3L, 11L)) {
      f <- fixture(waves, K); m <- f$model; map <- f$mapping
      p <- ch7_profile_data(m, map); cp <- ch7_proportion_data(m, map, "modelEstimated"); tr <- ch7_matrix_data(m, map)
      ok(nrow(p) == length(waves) * K); ok(nrow(cp) == nrow(p)); ok(nrow(tr) == (length(waves) - 1L) * K^2)
      ok(identical(levels(ch7_proportion_plot(cp)$data$class_label), paste("Group", seq_len(K))))
      ok(identical(levels(ch7_matrix_plot(tr)$data$from_label), paste("Group", seq_len(K))))
      ok(all(p$value == rep(seq_len(K) / K, length(waves)))); ok(all(abs(attr(tr, "row_sums")$probability - 1) < 1e-12))
      cm <- map$classes; cm$wave <- cm$variable; cm$semantic <- paste0("group", cm$class)
      flow <- ch7_model_flow_data(m, map, data.frame(wave = waves, label = map$variables$label), cm)
      ok(flow$quality$status == "INTERNALLY_CONSISTENT_ONLY")
      if (K == 2L) {
        ok(nrow(ggplot2::ggplot_build(ch7_profile_plot(p))$data[[2]]) == nrow(p))
        ok(nrow(ggplot2::ggplot_build(ch7_proportion_plot(cp))$data[[1]]) == nrow(cp))
        ok(nrow(ggplot2::ggplot_build(ch7_matrix_plot(tr))$data[[1]]) == nrow(tr))
      }
    }
  }
  f <- fixture(); m <- f$model; map <- f$mapping
  ordered <- ch7_profile_data(m, map)
  ordered$indicator <- rep(c("second", "first"), each = 2)
  ok(identical(levels(ch7_profile_plot(ordered)$data$indicator), c("second", "first")))
  z <- map; z$classes <- z$classes[-1, ]; bad(ch7_profile_data(m, z))
  z <- map; z$classes <- rbind(z$classes, z$classes[1, ]); bad(ch7_proportion_data(m, z, "modelEstimated"))
  z <- map; z$classes$label[2] <- z$classes$label[1]; bad(ch7_proportion_data(m, z, "modelEstimated"))
  bad(ch7_proportion_data(m, map, "mixed"))
  z <- m; z$class_counts$modelEstimated$proportion[1] <- 1.2; bad(ch7_proportion_data(z, map, "modelEstimated"))
  z <- map; z$matrices$condition <- "movers"; bad(ch7_matrix_data(m, z))
  z <- m; z$class_counts$transitionProbs <- z$class_counts$transitionProbs[-1, ]; bad(ch7_matrix_data(z, map))
  # F1 回归：相同显示标题不得合并不同波次的矩阵，也不得把重复格静默叠画。
  same <- fixture(c("C1", "C2", "C3"), 2L)
  same$mapping$matrices$label <- "Transition"
  same$model$class_counts$transitionProbs$probability <- c(.8, .3, .2, .7, .4, .9, .6, .1)
  matrices <- ch7_matrix_data(same$model, same$mapping)
  graph <- ch7_matrix_plot(matrices)
  matrix_built <- ggplot2::ggplot_build(graph)
  tiles <- matrix_built$data[[1L]]; text <- matrix_built$data[[2L]]
  ok(nrow(tiles) == 8L && length(unique(tiles$PANEL)) == 2L)
  ok(!anyDuplicated(ch7_figure_key(tiles$PANEL, tiles$x, tiles$y)))
  ok(length(levels(graph$data$facet)) == 2L)
  titles <- graph$facet$params$labeller(data.frame(facet = levels(graph$data$facet)))[[1L]]
  ok(identical(unname(titles), rep("Transition | overall", 2L)))
  # 各格按PANEL与坐标对应原概率；不以输入行数替代实际绘图正确性。
  expected_panel <- match(as.character(graph$data$facet), as.character(matrix_built$layout$layout$facet))
  expected_x <- as.integer(graph$data$to_label)
  expected_y <- nlevels(graph$data$from_label) + 1L - as.integer(graph$data$from_label)
  expected_key <- ch7_figure_key(expected_panel, expected_x, expected_y)
  actual_key <- ch7_figure_key(text$PANEL, text$x, text$y)
  ok(setequal(expected_key, actual_key))
  ok(identical(as.character(text$label[match(expected_key, actual_key)]), sprintf("%.3f", matrices$probability)))
  ok(identical(tiles$fill, matrix_built$plot$scales$get_scales("fill")$map(matrices$probability)))
  renamed <- matrices; renamed$panel <- "Same new display title"
  renamed_built <- ggplot2::ggplot_build(ch7_matrix_plot(renamed))
  ok(identical(tiles[c("PANEL", "x", "y", "fill")], renamed_built$data[[1L]][c("PANEL", "x", "y", "fill")]))
  bad(ch7_matrix_plot(rbind(matrices, matrices[1, ])))
  conflicting <- matrices; conflicting$panel[1L] <- "Conflicting title"
  bad(ch7_matrix_plot(conflicting))
  missing_identity <- matrices; missing_identity$from_variable <- NULL
  bad(ch7_matrix_plot(missing_identity))
  colliding_labels <- matrices; colliding_labels$from_label[1:4] <- "Same class label"
  bad(ch7_matrix_plot(colliding_labels))
  # 联合类别四条件展开；同一条件值不得被平均掩盖。
  grid <- expand.grid(a = 1:2, b = 1:2, response = 1:2)
  prob <- data.frame(param = "NBASE", category = grid$response, est = ifelse(grid$a == grid$response, .8, .2),
    LatentClass = paste(grid$a, grid$b, sep = "."))
  m$parameters$probability.scale <- prob
  map$profiles <- data.frame(variable = "BASE", param = "NBASE", statistic = "probability", category = c("1", "2"), label = "Assigned", panel = "Response")
  p <- ch7_profile_data(m, map); ok(nrow(p) == 4L); ok(all(p$source_rows == 2L))
  z <- m; z$parameters$probability.scale$est <- as.character(z$parameters$probability.scale$est)
  ok(identical(ch7_profile_data(z, map)$value, p$value))
  z$parameters$probability.scale$est[1] <- "undefined"; bad(ch7_profile_data(z, map))
  ok(nrow(ggplot2::ggplot_build(ch7_fixed_response_plot(p))$data[[1]]) == 4L)
  # 同潜变量两个指标，两个独立panel共8格；按PANEL/x/y核验没有覆盖。
  second <- p; second$param <- "OTHER"; second$indicator <- "Other assigned"; second$value <- rev(second$value)
  two <- rbind(p, second)
  built <- ggplot2::ggplot_build(ch7_fixed_response_plot(two))
  tiles <- built$data[[1]]
  ok(nrow(tiles) == 8L && length(unique(tiles$PANEL)) == 2L)
  ok(!anyDuplicated(ch7_figure_key(tiles$PANEL, tiles$x, tiles$y)))
  ok(identical(levels(ch7_fixed_response_plot(two)$data$facet), c("Wave 1 | NBASE", "Wave 1 | OTHER")))
  bad(ch7_fixed_response_plot(rbind(two, two[1, ])))
  z <- m; z$parameters$probability.scale$est[1] <- .7; bad(ch7_profile_data(z, map))
  z <- map; z$latent_order <- NULL; bad(ch7_profile_data(m, z))
  z <- map; z$profiles$category[1] <- "3"; bad(ch7_profile_data(m, z))
  z <- m; z$input <- list(variable = list(classes = "BASE(2) LATER(2)"))
  ok(nrow(ch7_profile_data(z, map)) == 4L)
  wrong <- map; wrong$latent_order <- rev(map$latent_order); bad(ch7_profile_data(z, wrong))
  z <- m; z$parameters$probability.scale <- z$parameters$probability.scale[-1, ]; bad(ch7_profile_data(z, map))
  # G声明在先、显示映射在后，联合类别必须按声明顺序解码。
  ms <- m; msmap <- map
  msmap$variables <- rbind(msmap$variables, data.frame(variable = "G", label = "Group"))
  msmap$classes <- rbind(msmap$classes, data.frame(variable = "G", class = c("1", "2"), label = c("Mover", "Stayer"), colour = c("#222222", "#777777")))
  msmap$latent_order <- c("G", "BASE", "LATER")
  mg <- expand.grid(g = 1:2, a = 1:2, b = 1:2, response = 1:2)
  ms$parameters$probability.scale <- data.frame(param = "NBASE", category = mg$response,
    est = ifelse(mg$a == mg$response, .8, .2), LatentClass = paste(mg$g, mg$a, mg$b, sep = "."))
  ms$input <- list(variable = list(classes = "G(2) BASE(2) LATER(2)"))
  ok(all(ch7_profile_data(ms, msmap)$source_rows == 4L))
  # 单期readModels以数字潜类、无variable列返回类别表。
  one <- fixture(); one$mapping$variables <- one$mapping$variables[1, , drop = FALSE]
  one$mapping$classes <- one$mapping$classes[1:2, ]; one$mapping$profiles <- one$mapping$profiles[1, , drop = FALSE]
  one$model$parameters$unstandardized <- one$model$parameters$unstandardized[1:2, ]
  one$model$parameters$unstandardized$LatentClass <- c(1, 2)
  one$model$class_counts$modelEstimated <- one$model$class_counts$modelEstimated[1:2, c("class", "count", "proportion")]
  ok(nrow(ch7_profile_data(one$model, one$mapping)) == 2L)
  ok(nrow(ch7_proportion_data(one$model, one$mapping, "modelEstimated")) == 2L)
  e <- data.frame(model_id = c("k1", "k2"), K = c(1, 2), source_id = c("s1", "s2"), dataset_id = "sample", indicator_set = "set")
  models <- list(k1 = f$model, k2 = f$model); models$k2$summaries$LL <- -120
  ed <- ch7_enumeration_data(models, e); ok(nrow(ed) == 2L)
  ok(nrow(ggplot2::ggplot_build(ch7_enumeration_plot(ed))$data[[2]]) == 4L)
  models$k2$summaries$Observations <- 99; bad(ch7_enumeration_data(models, e))
  # TECH3全交叉协方差经显式参数索引传给已验二次函数。
  model <- list(parameters = list(unstandardized = data.frame(paramHeader = "Y.ON", param = c("X", "X2"), est = c(.3, -.1), LatentClass = "")),
    tech3 = list(paramCov = matrix(c(.04, .005, .005, .01), 2)))
  curve_map <- list(terms = data.frame(role = c("linear", "quadratic"), paramHeader = "Y.ON", param = c("X", "X2"), LatentClass = "", covariance_index = 1:2),
    covariance_source = "paramCov", curve = list(x_grid = c(-1, 0, 2), scale = "binary_log_odds", source_id = "synthetic_curve",
      covariance_type = "synthetic full covariance", variable = "X", variable_scale = "raw", outcome = "1", reference = "0"))
  curve <- ch7_model_quadratic_curve(model, curve_map)
  ok(max(abs(curve$data$estimate - c(.5, .3, -.1))) < 1e-12)
  ok(max(abs(curve$data$variance - c(.06, .04, .24))) < 1e-12)
  ok(identical(curve$semantics$probability_effect, FALSE))
  model$tech3 <- list(); bad(ch7_model_quadratic_curve(model, curve_map))
  cat("PASS ch7 figures synthetic checks:", checks, "\n")
  if (!is.null(output_dir)) {
    if (file.exists(output_dir)) stop("Fresh output directory required")
    dir.create(output_dir, recursive = TRUE)
    jsonlite::write_json(list(status = "PASS_SYNTHETIC_MODEL_FIGURE_ADAPTER", checks = checks, engine_starts = 0L,
      reuses_transition_flow = TRUE, reuses_quadratic_curves = TRUE, real_estimates_used = FALSE),
      file.path(output_dir, "CH7_FIGURE_ADAPTER_TEST_RESULT.json"), pretty = TRUE, auto_unbox = TRUE)
  }
  invisible(list(status = "PASS", checks = checks, engine_starts = 0L))
}

if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  filearg <- grep("^--file=", commandArgs(), value = TRUE)
  own <- if (length(filearg)) dirname(normalizePath(sub("^--file=", "", filearg[1]))) else "scripts"
  test_ch7_figures_20261111(script_dir = if (length(args)) args[1] else own)
}
