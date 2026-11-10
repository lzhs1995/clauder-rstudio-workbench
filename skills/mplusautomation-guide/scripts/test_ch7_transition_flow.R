# 只用合成节点/概率；不启动Mplus、浏览器或读取私有研究资料。
test_ch7_transition_flow <- function(output_dir, skill_root) {
  if (file.exists(output_dir)) stop("Fresh output directory required")
  dir.create(output_dir, recursive = TRUE)
  source(file.path(skill_root, "scripts/ch7_transition_flow.R"), local = TRUE)
  checks <- list()
  check <- function(name, ok) {
    if (!isTRUE(ok)) stop("Contract failed: ", name)
    checks[[name]] <<- TRUE
  }
  reject <- function(name, expr, pattern) {
    err <- tryCatch({ force(expr); NULL }, error = identity)
    check(name, inherits(err, "error") && grepl(pattern, conditionMessage(err), fixed = TRUE))
  }
  waves <- data.frame(wave = c("first", "middle", "last"), label = c("Baseline", "Follow-up", "Final"))
  classes <- data.frame(wave = c("first", "first", "middle", "middle", "middle", "last", "last"),
    class = c("local.10", "local.20", "X", "Y", "Z", "other#9", "other#1"),
    semantic = c("near", "far", "near", "middle", "far", "near", "far"),
    label = c("Near", "Far", "Near", "Middle", "Far", "Near", "Far"),
    colour = c("#2A9D8F", "#264653", "#2A9D8F", "#E9C46A", "#264653", "#2A9D8F", "#264653"))
  distribution <- classes[c("wave", "class")]
  distribution$count <- c(10, 30, 20, 9, 11, 14.4, 25.6)
  make_edges <- function(a, b, probabilities) {
    z <- expand.grid(from_class = classes$class[classes$wave == a],
                     to_class = classes$class[classes$wave == b], stringsAsFactors = FALSE)
    z$from_wave <- a; z$to_wave <- b; z$probability <- as.vector(probabilities); z
  }
  edges <- rbind(make_edges("first", "middle", matrix(c(.2, .3, .5, .6, .2, .2), 2, byrow = TRUE)),
                 make_edges("middle", "last", matrix(c(.1, .9, .4, .6, .8, .2), 3, byrow = TRUE)))
  build <- function(d = distribution, t = edges, w = waves, c = classes,
                    mode = "posterior_count", condition = "overall", scale = NULL) {
    ch7_transition_flow_data(d, t, w, c, mode, condition, source_id = "synthetic_three_wave", scale = scale)
  }
  f <- build()
  check("three_waves_2_3_2_classes", nrow(f$nodes) == 7L && nrow(f$links) == 12L)
  check("expected_weight_and_direction", identical(f$nodes$id, 0:6) &&
    isTRUE(all.equal(f$links$value, c(2, 3, 5, 18, 6, 6, 2, 18, 3.6, 5.4, 8.8, 2.2))) &&
    all(f$links$source < f$links$target))
  check("internal_balance_only", identical(f$quality$status, "INTERNALLY_CONSISTENT_ONLY") &&
    !f$semantics$observed_transition_counts && !f$semantics$normalized)
  check("posterior_unit_is_not_observed_count", identical(f$semantics$units, "posterior-weighted expected flow"))
  check("link_colour_follows_source_semantics", identical(f$links$semantic, f$nodes$semantic[f$links$source + 1L]))
  shuffled <- build(d = distribution[c(7, 2, 3, 1, 6, 5, 4), ], t = edges[12:1, ])
  check("input_row_permutation_preserves_result", identical(f$nodes, shuffled$nodes) && identical(f$links, shuffled$links))
  # 显式改名，不靠类别编号或原年号；类别映射使相同语义保持相同颜色和流量。
  w2 <- waves; w2$wave <- c("phase-2011", "phase.future", "phase:end")
  c2 <- classes; c2$wave <- w2$wave[match(c2$wave, waves$wave)]
  c2$class <- paste0("id_", c(81, 12, 49, 72, 5, 60, 3))
  d2 <- distribution; d2$wave <- c2$wave; d2$class <- c2$class
  e2 <- edges
  for (side in c("from", "to")) {
    old <- paste(edges[[paste0(side, "_wave")]], edges[[paste0(side, "_class")]])
    ix <- match(old, paste(classes$wave, classes$class))
    e2[[paste0(side, "_wave")]] <- c2$wave[ix]; e2[[paste0(side, "_class")]] <- c2$class[ix]
  }
  renamed <- build(d2, e2, w2, c2)
  check("renamed_wave_and_class_ids", identical(renamed$links$value, f$links$value) &&
    identical(renamed$links$group, f$links$group) && identical(renamed$nodes$label, f$nodes$label))
  two <- build(distribution[1:5, ], edges[edges$from_wave == "first", ], waves[1:2, ], classes[1:5, ])
  check("two_waves_different_class_counts", nrow(two$nodes) == 5L && nrow(two$links) == 6L)
  md <- distribution[c("wave", "class")]; md$proportion <- distribution$count / 40
  m <- build(md, mode = "mover_scaled", condition = "G=declared_movers", scale = 11)
  check("explicit_mover_scale_rounds_nodes_only", identical(m$nodes$weight, c(3, 8, 6, 2, 3, 4, 7)) &&
    abs(m$links$value[1] - .6) < 1e-12 && identical(m$links$probability, f$links$probability))
  check("scaled_weights_not_people", identical(m$semantics$units, "scaled mover weight (scale=11)") &&
    !m$semantics$observed_transition_counts && identical(m$semantics$condition, "G=declared_movers"))
  check("rounding_imbalance_reported_not_repaired", "FLOW_DIFFERS_FROM_DECLARED_NODE_WEIGHT" %in% m$quality$issues &&
    identical(m$quality$status, "LIMITED") && !m$semantics$normalized)
  rounded <- edges; rounded$probability[1] <- .199
  rf <- build(t = rounded)
  check("probability_row_sum_report_only", "TRANSITION_ROW_SUM_DIFFERS_FROM_ONE" %in% rf$quality$issues &&
    identical(rf$links$probability[1], .199) && abs(rf$links$value[1] - 1.99) < 1e-12)
  md2 <- md; md2$proportion[1] <- md2$proportion[1] + .001
  mf <- build(md2, mode = "mover_scaled", condition = "G=movers", scale = 11)
  check("conditional_distribution_not_normalized", "DISTRIBUTION_SUM_DIFFERS_FROM_ONE" %in% mf$quality$issues &&
    identical(mf$nodes$proportion, md2$proportion))
  zero <- edges; zero$probability[1] <- 0
  z <- build(t = zero)
  check("zero_is_explicit_transparent_edge", z$links$value[1] == 0 && z$links$group[1] == "zero_flow" && nrow(z$links) == 12)
  reject("reject_missing_mapping", build(c = classes[-1, ]), "exactly one matching row")
  reject("reject_missing_edge", build(t = edges[-1, ]), "missing edges are not zero-filled")
  reject("reject_duplicate_edge", build(t = rbind(edges, edges[1, ])), "duplicate transition")
  reverse <- edges; reverse$to_wave[1] <- reverse$from_wave[1]; reverse$to_class[1] <- reverse$from_class[1]
  reject("reject_wrong_direction", build(t = reverse), "forward between adjacent")
  unknown <- edges; unknown$to_class[1] <- "unmapped"
  reject("reject_unknown_class", build(t = unknown), "explicit wave/class mapping")
  for (v in c(NA_real_, Inf, NaN, -.01, 1.01)) {
    bad <- edges; bad$probability[1] <- v
    reject(paste0("reject_probability_", v), build(t = bad), "finite, non-negative")
  }
  bad <- distribution; bad$count[1] <- Inf
  reject("reject_nonfinite_count", build(d = bad), "finite, non-negative")
  bad <- classes; bad$semantic[2] <- bad$semantic[1]
  reject("reject_duplicate_semantic_within_wave", build(c = bad), "unique within each wave")
  bad <- classes; bad$colour[3] <- "#FFFFFF"
  reject("reject_conflicting_semantic_colour", build(c = bad), "retain its declared label and colour")
  reject("reject_mover_without_scale", build(md, mode = "mover_scaled", condition = "G=movers"), "explicit finite positive scale")
  reject("reject_mover_as_overall", build(md, mode = "mover_scaled", scale = 11), "explicit mover condition")
  reject("reject_posterior_with_conditional_label", build(condition = "G=movers"), "condition='overall'")
  # 只构造widget检查其原生载荷，不启动浏览器或保存PNG。
  if (requireNamespace("networkD3", quietly = TRUE)) {
    widget <- ch7_transition_sankey(f)
    check("widget_matches_flow_values", inherits(widget, "htmlwidget") && identical(widget$x$links$value, f$links$value))
    check("widget_units_and_wave_labels", identical(widget$x$options$units, f$semantics$units) &&
      grepl("Baseline - Near", widget$x$nodes$name[1], fixed = TRUE))
    check("widget_keeps_quality_metadata", identical(attr(widget, "transition_flow_quality"), f$quality))
  } else {
    reject("missing_networkD3_readable_error", ch7_transition_sankey(f), "Rendering requires the R package 'networkD3'")
  }
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Test receipt requires jsonlite")
  jsonlite::write_json(list(status = "PASS_SYNTHETIC_FLOW_CONTRACT_ONLY", checks = checks,
    widget_constructed = requireNamespace("networkD3", quietly = TRUE), new_mplus_calls = 0L,
    browser_calls = 0L, historical_figure_acceptance = FALSE, real_data_swap_acceptance = FALSE),
    file.path(output_dir, "TRANSITION_FLOW_TEST_RESULT.json"), pretty = TRUE, auto_unbox = TRUE)
  cat("CH7_TRANSITION_FLOW_PASS", length(checks), "checks; Mplus=0; browser=0\n")
  invisible(checks)
}
