required_packages <- c(
  "compareGroups", "haven", "labelled", "officer", "flextable",
  "jsonlite", "digest"
)

cg_stop <- function(...) stop(sprintf(...), call. = FALSE)

cg_progress <- function(stage, message) {
  line <- sprintf("COMPAREGROUPS_PROGRESS stage=%s message=%s", stage, message)
  cat(line, "\n")
  flush.console()
  progress_fun <- NULL
  for (frame in rev(sys.frames())) {
    candidate <- get0("clauder_progress", envir = frame, inherits = FALSE)
    if (is.function(candidate)) {
      progress_fun <- candidate
      break
    }
  }
  if (!is.function(progress_fun)) {
    progress_fun <- get0("clauder_progress", envir = .GlobalEnv, inherits = TRUE)
  }
  if (is.function(progress_fun)) {
    try(progress_fun(stage, message), silent = TRUE)
  }
}

cg_parse_args <- function(args = commandArgs(trailingOnly = TRUE)) {
  out <- list()
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (!startsWith(key, "--")) cg_stop("Unexpected argument: %s", key)
    if (i == length(args)) cg_stop("Missing value for %s", key)
    out[[sub("^--", "", key)]] <- args[[i + 1L]]
    i <- i + 2L
  }
  out
}

cg_missing_packages <- function() {
  required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
}

cg_require_packages <- function() {
  missing <- cg_missing_packages()
  if (length(missing)) {
    cg_stop(
      "Missing R packages: %s. Install with install.packages(c(%s))",
      paste(missing, collapse = ", "),
      paste(sprintf("'%s'", missing), collapse = ", ")
    )
  }
}

cg_find_pandoc <- function() {
  if (!requireNamespace("rmarkdown", quietly = TRUE)) {
    cg_stop("compatibility_export2word requires the rmarkdown package and Pandoc")
  }

  executable <- if (.Platform$OS.type == "windows") "pandoc.exe" else "pandoc"
  candidates <- c(
    Sys.getenv("RSTUDIO_PANDOC", unset = ""),
    dirname(Sys.which("pandoc"))
  )
  if (Sys.info()[["sysname"]] == "Darwin") {
    architecture <- if (Sys.info()[["machine"]] %in% c("arm64", "aarch64")) "aarch64" else "x86_64"
    candidates <- c(
      candidates,
      file.path(
        "/Applications/RStudio.app/Contents/Resources/app/quarto/bin/tools",
        architecture
      ),
      "/Applications/RStudio.app/Contents/Resources/app/bin/quarto/bin/tools"
    )
  } else if (.Platform$OS.type == "windows") {
    roots <- unique(c(
      Sys.getenv("ProgramFiles", unset = ""),
      Sys.getenv("ProgramW6432", unset = ""),
      Sys.getenv("LOCALAPPDATA", unset = "")
    ))
    roots <- roots[nzchar(roots)]
    candidates <- c(
      candidates,
      unlist(lapply(roots, function(root) c(
        file.path(root, "RStudio", "resources", "app", "quarto", "bin", "tools"),
        file.path(root, "RStudio", "resources", "app", "bin", "quarto", "bin", "tools")
      )), use.names = FALSE)
    )
  }

  candidates <- unique(candidates[nzchar(candidates)])
  for (candidate in candidates) {
    if (!file.exists(file.path(candidate, executable))) next
    Sys.setenv(RSTUDIO_PANDOC = normalizePath(candidate, winslash = "/", mustWork = TRUE))
    info <- try(rmarkdown::find_pandoc(cache = FALSE), silent = TRUE)
    if (!inherits(info, "try-error") && length(info$version) && info$version >= numeric_version("1.12.3")) {
      return(info)
    }
  }
  cg_stop(
    paste(
      "compatibility_export2word requires Pandoc >= 1.12.3.",
      "Install Pandoc or set RSTUDIO_PANDOC to its containing directory."
    )
  )
}

cg_atomic_path <- function(path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  tempfile(pattern = paste0(".", basename(path), "."), tmpdir = dirname(path))
}

cg_atomic_move <- function(tmp, path) {
  if (file.exists(path)) cg_stop("Refusing to overwrite existing output: %s", path)
  if (!file.rename(tmp, path)) {
    unlink(tmp)
    cg_stop("Atomic rename failed for output: %s", path)
  }
  invisible(path)
}

cg_write_json <- function(value, path, pretty = TRUE) {
  tmp <- cg_atomic_path(path)
  on.exit(if (file.exists(tmp)) unlink(tmp), add = TRUE)
  jsonlite::write_json(value, tmp, auto_unbox = TRUE, pretty = pretty, null = "null", na = "null")
  cg_atomic_move(tmp, path)
}

cg_write_csv <- function(value, path) {
  tmp <- cg_atomic_path(path)
  on.exit(if (file.exists(tmp)) unlink(tmp), add = TRUE)
  utils::write.csv(value, tmp, row.names = FALSE, na = "", fileEncoding = "UTF-8")
  cg_atomic_move(tmp, path)
}

cg_write_rds <- function(value, path) {
  tmp <- cg_atomic_path(path)
  on.exit(if (file.exists(tmp)) unlink(tmp), add = TRUE)
  saveRDS(value, tmp, version = 3)
  cg_atomic_move(tmp, path)
}

cg_sha256 <- function(path) {
  unname(digest::digest(file = path, algo = "sha256", serialize = FALSE))
}

cg_read_spec <- function(path) {
  if (!file.exists(path)) cg_stop("Spec does not exist: %s", path)
  jsonlite::fromJSON(path, simplifyVector = FALSE)
}

cg_scalar <- function(x, default = NULL) {
  if (is.null(x) || length(x) == 0L) default else x[[1L]]
}

cg_bool <- function(x, default = FALSE) isTRUE(cg_scalar(x, default))

cg_all_variables <- function(spec) {
  unlist(lapply(spec$blocks, function(block) {
    vapply(block$variables, function(variable) cg_scalar(variable$name, ""), character(1))
  }), use.names = FALSE)
}

cg_validate_spec <- function(spec, require_input = TRUE) {
  errors <- character()
  need <- c("spec_version", "analysis_id", "input", "analysis", "blocks", "display", "outputs")
  errors <- c(errors, sprintf("missing top-level field: %s", setdiff(need, names(spec))))
  if (!identical(cg_scalar(spec$spec_version), "1.0")) errors <- c(errors, "spec_version must be 1.0")
  if (!length(spec$blocks)) errors <- c(errors, "blocks must not be empty")
  variables <- cg_all_variables(spec)
  if (any(!nzchar(variables))) errors <- c(errors, "every variable requires a name")
  duplicates <- unique(variables[duplicated(variables)])
  if (length(duplicates)) errors <- c(errors, paste("duplicate variables:", paste(duplicates, collapse = ", ")))
  allowed_methods <- c("normal", "nonnormal", "categorical")
  allowed_types <- c("continuous", "categorical")
  for (block in spec$blocks) {
    if (!nzchar(cg_scalar(block$id, ""))) errors <- c(errors, "every block requires an id")
    if (!length(block$variables)) errors <- c(errors, sprintf("block %s has no variables", cg_scalar(block$id, "?")))
    for (variable in block$variables) {
      method <- cg_scalar(variable$method, "")
      type <- cg_scalar(variable$type, "")
      if (!method %in% allowed_methods) errors <- c(errors, sprintf("invalid method for %s: %s", cg_scalar(variable$name, "?"), method))
      if (!type %in% allowed_types) errors <- c(errors, sprintf("invalid type for %s: %s", cg_scalar(variable$name, "?"), type))
      if (identical(type, "continuous") && identical(method, "categorical")) errors <- c(errors, sprintf("continuous variable %s cannot use categorical", cg_scalar(variable$name, "?")))
      if (identical(type, "categorical") && !identical(method, "categorical")) errors <- c(errors, sprintf("categorical variable %s must use categorical", cg_scalar(variable$name, "?")))
    }
  }
  input_path <- cg_scalar(spec$input$path, "")
  if (require_input && (!nzchar(input_path) || !file.exists(input_path))) errors <- c(errors, sprintf("input does not exist: %s", input_path))
  if (length(errors)) cg_stop("Invalid table specification:\n- %s", paste(errors, collapse = "\n- "))
  invisible(TRUE)
}

cg_read_input <- function(spec) {
  path <- normalizePath(cg_scalar(spec$input$path), winslash = "/", mustWork = TRUE)
  format <- tolower(cg_scalar(spec$input$format, "auto"))
  if (identical(format, "auto")) format <- tolower(tools::file_ext(path))
  data <- switch(
    format,
    dta = haven::read_dta(path),
    sav = haven::read_sav(path),
    csv = utils::read.csv(path, check.names = FALSE, na.strings = c("", "NA")),
    tsv = utils::read.delim(path, check.names = FALSE, na.strings = c("", "NA")),
    rds = readRDS(path),
    cg_stop("Unsupported input format: %s", format)
  )
  if (!is.data.frame(data)) cg_stop("Input did not produce a data frame")
  attr(data, "cg_input_path") <- path
  attr(data, "cg_input_format") <- format
  data
}

cg_apply_subset <- function(data, subset_text) {
  subset_text <- cg_scalar(subset_text, NULL)
  if (is.null(subset_text) || !nzchar(subset_text)) return(data)
  expression <- try(parse(text = subset_text), silent = TRUE)
  if (inherits(expression, "try-error") || length(expression) != 1L) cg_stop("Invalid subset expression")
  keep <- try(eval(expression[[1L]], envir = data, enclos = baseenv()), silent = TRUE)
  if (inherits(keep, "try-error") || !is.logical(keep) || length(keep) != nrow(data)) cg_stop("Subset must return one logical value per row")
  data[!is.na(keep) & keep, , drop = FALSE]
}

cg_level_pairs <- function(levels_spec) {
  if (is.null(levels_spec) || !length(levels_spec)) return(NULL)
  values <- vapply(levels_spec, function(x) as.character(cg_scalar(x$value)), character(1))
  labels <- vapply(levels_spec, function(x) as.character(cg_scalar(x$label)), character(1))
  if (anyDuplicated(values) || anyDuplicated(labels)) cg_stop("Categorical levels contain duplicates")
  list(values = values, labels = labels)
}

cg_prepare_categorical <- function(x, variable) {
  pairs <- cg_level_pairs(variable$levels)
  if (!is.null(pairs)) {
    raw <- as.character(x)
    unknown <- setdiff(unique(raw[!is.na(raw)]), pairs$values)
    if (length(unknown)) cg_stop("Unknown categorical codes for %s: %s", cg_scalar(variable$name), paste(unknown, collapse = ", "))
    out <- factor(raw, levels = pairs$values, labels = pairs$labels)
  } else if (inherits(x, "haven_labelled") || inherits(x, "labelled")) {
    label_map <- attr(x, "labels", exact = TRUE)
    if (is.null(label_map) || !length(label_map)) cg_stop("Labelled categorical variable %s has no value labels", cg_scalar(variable$name))
    raw <- as.character(unclass(x))
    known <- as.character(unname(label_map))
    unknown <- setdiff(unique(raw[!is.na(raw)]), known)
    if (length(unknown)) cg_stop("Unknown labelled codes for %s: %s", cg_scalar(variable$name), paste(unknown, collapse = ", "))
    out <- haven::as_factor(x, levels = "labels")
  } else if (is.factor(x)) {
    out <- x
  } else if (is.character(x) || is.logical(x)) {
    out <- factor(x)
  } else {
    cg_stop("Numeric unlabelled categorical variable %s requires explicit levels", cg_scalar(variable$name))
  }
  reference <- cg_scalar(variable$reference, NULL)
  if (!is.null(reference)) {
    if (!reference %in% levels(out)) cg_stop("Reference %s not found for %s", reference, cg_scalar(variable$name))
    out <- stats::relevel(out, ref = reference)
  }
  out <- droplevels(out)
  variable_label <- cg_scalar(variable$label, attr(x, "label", exact = TRUE))
  if (!is.null(variable_label) && nzchar(variable_label)) attr(out, "label") <- variable_label
  out
}

cg_prepare_data <- function(data, spec) {
  required <- unique(c(
    cg_all_variables(spec), cg_scalar(spec$analysis$group, NULL),
    cg_scalar(spec$input$id, NULL), cg_scalar(spec$input$time, NULL)
  ))
  required <- required[!is.na(required) & nzchar(required)]
  missing <- setdiff(required, names(data))
  if (length(missing)) cg_stop("Variables missing from input: %s", paste(missing, collapse = ", "))
  audit <- list()
  for (block in spec$blocks) {
    for (variable in block$variables) {
      name <- cg_scalar(variable$name)
      original <- data[[name]]
      if (identical(cg_scalar(variable$type), "categorical")) {
        data[[name]] <- cg_prepare_categorical(original, variable)
      } else {
        if (!is.numeric(original)) cg_stop("Continuous variable %s is not numeric", name)
        label <- cg_scalar(variable$label, attr(original, "label", exact = TRUE))
        if (!is.null(label) && nzchar(label)) attr(data[[name]], "label") <- label
      }
      audit[[length(audit) + 1L]] <- data.frame(
        block = cg_scalar(block$id), variable = name,
        label = cg_scalar(attr(data[[name]], "label", exact = TRUE), name),
        storage_class = paste(class(original), collapse = "/"),
        prepared_class = paste(class(data[[name]]), collapse = "/"),
        method = cg_scalar(variable$method), n = sum(!is.na(data[[name]])),
        missing = sum(is.na(data[[name]])),
        source_value_labels = if (!is.null(attr(original, "labels", exact = TRUE))) {
          paste(paste0(names(attr(original, "labels", exact = TRUE)), "=", unname(attr(original, "labels", exact = TRUE))), collapse = " | ")
        } else "",
        levels = if (is.factor(data[[name]])) paste(levels(data[[name]]), collapse = " | ") else "",
        stringsAsFactors = FALSE
      )
    }
  }
  group <- cg_scalar(spec$analysis$group, NULL)
  if (!is.null(group)) {
    gx <- data[[group]]
    if (inherits(gx, "haven_labelled") || inherits(gx, "labelled")) gx <- haven::as_factor(gx, levels = "labels")
    if (!is.factor(gx)) gx <- factor(gx)
    if (nlevels(gx) < 2L) cg_stop("Grouping variable %s requires at least two levels", group)
    data[[group]] <- droplevels(gx)
  }
  list(data = data, audit = do.call(rbind, audit), required = required)
}

cg_panel_audit <- function(data, spec) {
  id <- cg_scalar(spec$input$id, NULL)
  time <- cg_scalar(spec$input$time, NULL)
  repeated <- FALSE
  duplicate_rows <- 0L
  if (!is.null(id)) {
    duplicate_rows <- sum(duplicated(data[[id]]) | duplicated(data[[id]], fromLast = TRUE), na.rm = TRUE)
    repeated <- duplicate_rows > 0L
  }
  list(
    id = id, time = time, rows = nrow(data), columns = ncol(data),
    unique_ids = if (is.null(id)) NULL else length(unique(data[[id]][!is.na(data[[id]])])),
    repeated_id_rows = duplicate_rows, repeated_ids = repeated
  )
}

cg_subset_preserve <- function(data, rows) {
  labels <- lapply(data, attr, which = "label", exact = TRUE)
  out <- data[rows, , drop = FALSE]
  for (name in names(out)) {
    if (!is.null(labels[[name]])) attr(out[[name]], "label") <- labels[[name]]
  }
  out
}

cg_variants <- function(data, spec, panel) {
  mode <- cg_scalar(spec$analysis$panel_mode, "cross_section")
  group <- cg_scalar(spec$analysis$group, NULL)
  time <- cg_scalar(spec$input$time, NULL)
  if (!identical(mode, "dual") || !isTRUE(panel$repeated_ids)) {
    return(list(list(id = "primary", label = "Primary", data = data, suppress_p = FALSE,
                     warning = NULL)))
  }
  compatibility_warning <- paste(
    "Compatibility pooled table: repeated person-wave rows are not independent;",
    "ordinary pooled t/chi-square/trend p-values are not formal longitudinal inference."
  )
  compatibility <- list(id = "compatibility_pooled", label = "Compatibility pooled",
                        data = data, suppress_p = FALSE, warning = compatibility_warning)
  if (!is.null(time) && !identical(group, time)) {
    time_values <- unique(data[[time]][!is.na(data[[time]])])
    primary <- lapply(time_values, function(value) {
      selected <- !is.na(data[[time]]) & data[[time]] == value
      list(id = paste0("primary_wave_", gsub("[^A-Za-z0-9._-]", "_", as.character(value))),
           label = paste("Primary wave", as.character(value)), data = cg_subset_preserve(data, selected),
           suppress_p = FALSE, warning = NULL)
    })
    return(c(primary, list(compatibility)))
  }
  primary <- list(id = "primary_safe", label = "Primary safe pooled descriptives",
                  data = data, suppress_p = TRUE,
                  warning = "Primary pooled description suppresses p-values because person-wave rows repeat.")
  list(primary, compatibility)
}

cg_bind_fill <- function(frames) {
  if (!length(frames)) return(data.frame())
  columns <- unique(unlist(lapply(frames, names), use.names = FALSE))
  frames <- lapply(frames, function(frame) {
    for (missing in setdiff(columns, names(frame))) frame[[missing]] <- NA_character_
    frame[columns]
  })
  out <- do.call(rbind, frames)
  row.names(out) <- NULL
  out
}

cg_display_frame <- function(table, block_id, block_label, variant_id, include_header = TRUE) {
  matrix <- table$descr
  frame <- data.frame(row_label = rownames(matrix), matrix, check.names = FALSE, stringsAsFactors = FALSE)
  names(frame) <- c("row_label", colnames(matrix))
  names(frame)[names(frame) == "[ALL]"] <- "全样本"
  names(frame)[names(frame) == "p.overall"] <- "p-value"
  names(frame)[names(frame) == "p.trend"] <- "p-trend"
  names(frame)[names(frame) == "p.mul"] <- "p-multiple"
  frame <- data.frame(variant = variant_id, block = block_id, frame, check.names = FALSE, stringsAsFactors = FALSE)
  if (!include_header) return(frame)
  header <- as.list(rep("", ncol(frame)))
  names(header) <- names(frame)
  header$variant <- variant_id
  header$block <- block_id
  header$row_label <- block_label
  rbind(as.data.frame(header, check.names = FALSE, stringsAsFactors = FALSE), frame)
}

cg_result_names_to_variables <- function(cg, result_names) {
  variables <- attr(cg, "varnames.orig")
  labels <- vapply(variables, function(variable) {
    cg_scalar(attr(attr(cg, "Xlong")[[variable]], "label", exact = TRUE), variable)
  }, character(1))
  reverse <- setNames(variables, labels)
  mapped <- unname(reverse[result_names])
  mapped[is.na(mapped)] <- result_names[is.na(mapped)]
  mapped
}

cg_numeric_frame <- function(cg, table, block_id, variant_id, include_p = TRUE) {
  array <- compareGroups::getResults(cg, "descr")
  methods <- attr(cg, "method")
  variables <- attr(cg, "varnames.orig")
  # createTable records exact row counts; for the numeric array, match labels in order.
  labels <- vapply(variables, function(variable) {
    cg_scalar(attr(attr(cg, "Xlong")[[variable]], "label", exact = TRUE), variable)
  }, character(1))
  variable_for_row <- character(dim(array)[1L])
  cursor <- 1L
  for (index in seq_along(variables)) {
    label <- labels[[index]]
    rows <- which(dimnames(array)[[1L]] == label | startsWith(dimnames(array)[[1L]], paste0(label, ":")))
    rows <- setdiff(rows, which(nzchar(variable_for_row)))
    if (!length(rows)) rows <- cursor
    variable_for_row[rows] <- variables[[index]]
    cursor <- max(rows) + 1L
  }
  variable_for_row[!nzchar(variable_for_row)] <- NA_character_
  indices <- which(!is.na(array), arr.ind = TRUE)
  out <- data.frame(
    variant = variant_id,
    block = block_id,
    variable = variable_for_row[indices[, "dim1"]],
    row_label = dimnames(array)[[1L]][indices[, "dim1"]],
    statistic = dimnames(array)[[2L]][indices[, "dim2"]],
    group = dimnames(array)[[3L]][indices[, "dim3"]],
    value = as.numeric(array[indices]),
    method_code = unname(methods[variable_for_row[indices[, "dim1"]]]),
    stringsAsFactors = FALSE
  )
  available <- table$avail
  if (!is.null(available) && length(available)) {
    count_columns <- setdiff(colnames(available), c("method", "select"))
    counts <- available[, count_columns, drop = FALSE]
    count_values <- suppressWarnings(matrix(
      as.numeric(gsub(",", "", as.character(counts), fixed = TRUE)),
      nrow = nrow(counts), dimnames = dimnames(counts)
    ))
    count_indices <- which(is.finite(count_values), arr.ind = TRUE)
    if (nrow(count_indices)) {
      count_labels <- rownames(counts)[count_indices[, 1L]]
      count_variables <- cg_result_names_to_variables(cg, count_labels)
      count_frame <- data.frame(
        variant = variant_id,
        block = block_id,
        variable = count_variables,
        row_label = count_labels,
        statistic = "n_available",
        group = colnames(counts)[count_indices[, 2L]],
        value = count_values[count_indices],
        method_code = unname(methods[count_variables]),
        stringsAsFactors = FALSE
      )
      out <- rbind(out, count_frame)
    }
  }
  for (what in if (include_p) c("p.overall", "p.trend", "p.mul") else character()) {
    values <- try(compareGroups::getResults(cg, what), silent = TRUE)
    if (!inherits(values, "try-error") && length(values)) {
      statistic <- gsub("\\.", "_", what)
      if (is.null(dim(values))) {
        result_names <- names(values)
        if (is.null(result_names) && length(values) == length(variables)) result_names <- variables
        if (is.null(result_names)) next
        mapped <- cg_result_names_to_variables(cg, result_names)
        p_frame <- data.frame(
          variant = variant_id, block = block_id, variable = mapped,
          row_label = result_names, statistic = statistic,
          group = "", value = as.numeric(values), method_code = unname(methods[mapped]),
          stringsAsFactors = FALSE
        )
      } else if (length(dim(values)) == 2L) {
        indices <- which(!is.na(values), arr.ind = TRUE)
        row_labels <- dimnames(values)[[1L]][indices[, 1L]]
        mapped <- cg_result_names_to_variables(cg, row_labels)
        p_frame <- data.frame(
          variant = variant_id, block = block_id, variable = mapped,
          row_label = row_labels, statistic = statistic,
          group = dimnames(values)[[2L]][indices[, 2L]],
          value = as.numeric(values[indices]), method_code = unname(methods[mapped]),
          stringsAsFactors = FALSE
        )
      } else {
        next
      }
      out <- rbind(out, p_frame)
    }
  }
  out
}

cg_run_variant <- function(variant, spec) {
  data <- variant$data
  group <- cg_scalar(spec$analysis$group, NULL)
  display <- spec$display
  block_objects <- list()
  display_frames <- list()
  numeric_frames <- list()
  for (block in spec$blocks) {
    block_id <- cg_scalar(block$id)
    include_flags <- vapply(block$variables, function(v) cg_bool(v$include_missing), logical(1))
    # compareGroups 4.10.2 removes mixed-method variables when include.miss is
    # passed as a vector. Run contiguous same-policy parts with a scalar flag,
    # preserving row order and every original statistical object.
    part_ids <- cumsum(c(TRUE, diff(as.integer(include_flags)) != 0L))
    part_objects <- list()
    part_displays <- list()
    part_numerics <- list()
    for (part_index in unique(part_ids)) {
      part <- block$variables[part_ids == part_index]
      variables <- vapply(part, function(v) cg_scalar(v$name), character(1))
      methods <- setNames(vapply(part, function(v) {
        switch(cg_scalar(v$method), normal = 1, nonnormal = 2, categorical = 3)
      }, numeric(1)), variables)
      digits <- setNames(vapply(part, function(v) as.integer(cg_scalar(v$digits, 3L)), integer(1)), variables)
      formula <- if (is.null(group)) stats::reformulate(variables) else stats::reformulate(variables, response = group)
      model_data <- data[, unique(c(group, variables)), drop = FALSE]
      cg <- compareGroups::compareGroups(
        formula, data = model_data, method = methods,
        include.miss = include_flags[which(part_ids == part_index)[1L]],
        include.label = TRUE
      )
      removed <- setdiff(variables, attr(cg, "varnames.orig"))
      if (length(removed)) cg_stop("compareGroups removed variables in block %s: %s", block_id, paste(removed, collapse = ", "))
      suppress <- isTRUE(variant$suppress_p) || is.null(group)
      table <- compareGroups::createTable(
        cg, digits = digits, digits.ratio = 2,
        show.all = cg_bool(display$show_all, TRUE), show.n = cg_bool(display$show_n, TRUE),
        show.p.overall = cg_bool(display$show_p_overall, TRUE) && !suppress,
        show.p.mul = cg_bool(display$show_p_multiple, FALSE) && !suppress,
        show.p.trend = cg_bool(display$show_p_trend, FALSE) && !suppress,
        digits.p = as.integer(cg_scalar(display$p_digits, 3L))
      )
      part_name <- paste0("part_", part_index)
      part_objects[[part_name]] <- list(compareGroups = cg, createTable = table,
                                        include_missing = include_flags[which(part_ids == part_index)[1L]])
      part_displays[[part_name]] <- cg_display_frame(
        table, block_id, cg_scalar(block$label), variant$id,
        include_header = identical(part_index, unique(part_ids)[1L])
      )
      part_numerics[[part_name]] <- cg_numeric_frame(cg, table, block_id, variant$id, include_p = !suppress)
    }
    block_objects[[block_id]] <- list(parts = part_objects)
    display_frames[[block_id]] <- cg_bind_fill(part_displays)
    numeric_frames[[block_id]] <- do.call(rbind, part_numerics)
  }
  list(
    id = variant$id, label = variant$label, warning = variant$warning,
    rows = nrow(data), group_counts = if (is.null(group)) list(all = nrow(data)) else as.list(table(data[[group]], useNA = "ifany")),
    objects = block_objects, display = cg_bind_fill(display_frames),
    numeric = do.call(rbind, numeric_frames)
  )
}

cg_render_docx <- function(results, path, title, spec, note = NULL) {
  doc <- officer::read_docx()
  doc <- officer::body_add_par(doc, title, style = "heading 1")
  for (result in results) {
    doc <- officer::body_add_par(doc, result$label, style = "heading 2")
    frame <- result$display
    frame <- frame[, setdiff(names(frame), c("variant", "block")), drop = FALSE]
    ft <- flextable::flextable(frame)
    ft <- flextable::border_remove(ft)
    line <- officer::fp_border(color = "black", width = 1.25)
    ft <- flextable::hline_top(ft, border = line, part = "header")
    ft <- flextable::hline_bottom(ft, border = line, part = "header")
    ft <- flextable::hline_bottom(ft, border = line, part = "body")
    section_rows <- which(frame$row_label %in% vapply(spec$blocks, function(b) cg_scalar(b$label), character(1)))
    if (length(section_rows)) ft <- flextable::bold(ft, i = section_rows, bold = TRUE, part = "body")
    ft <- flextable::align(ft, j = 1L, align = "left", part = "all")
    if (ncol(frame) > 1L) ft <- flextable::align(ft, j = 2:ncol(frame), align = "center", part = "all")
    ft <- flextable::autofit(ft)
    doc <- flextable::body_add_flextable(doc, ft)
    if (!is.null(result$warning)) doc <- officer::body_add_par(doc, paste("Note:", result$warning), style = "Normal")
  }
  if (!is.null(note) && nzchar(note)) doc <- officer::body_add_par(doc, paste("Note:", note), style = "Normal")
  tmp <- cg_atomic_path(path)
  if (!grepl("\\.docx$", tmp, ignore.case = TRUE)) tmp_docx <- paste0(tmp, ".docx") else tmp_docx <- tmp
  on.exit({ if (file.exists(tmp)) unlink(tmp); if (exists("tmp_docx") && file.exists(tmp_docx)) unlink(tmp_docx) }, add = TRUE)
  print(doc, target = tmp_docx)
  cg_atomic_move(tmp_docx, path)
}

cg_validate_docx <- function(path) {
  if (!file.exists(path) || file.info(path)$size <= 0) return(FALSE)
  listing <- try(utils::unzip(path, list = TRUE), silent = TRUE)
  !inherits(listing, "try-error") && "word/document.xml" %in% listing$Name
}

cg_export2word_compatibility <- function(result, path, spec) {
  cg_find_pandoc()
  block_tables <- lapply(spec$blocks, function(block) {
    parts <- result$objects[[cg_scalar(block$id)]]$parts
    if (length(parts) != 1L) {
      cg_stop("compatibility_export2word requires one include_missing policy per block")
    }
    parts[[1L]]$createTable
  })
  names(block_tables) <- vapply(spec$blocks, function(block) cg_scalar(block$label), character(1))
  combined <- do.call(rbind, block_tables)
  tmp <- cg_atomic_path(path)
  if (!grepl("\\.docx$", tmp, ignore.case = TRUE)) tmp_docx <- paste0(tmp, ".docx") else tmp_docx <- tmp
  on.exit({ if (file.exists(tmp)) unlink(tmp); if (exists("tmp_docx") && file.exists(tmp_docx)) unlink(tmp_docx) }, add = TRUE)
  compareGroups::export2word(
    combined, file = tmp_docx, which.table = "descr",
    header.labels = c("p.overall" = "p-value", "all" = "全样本"), nmax = TRUE
  )
  cg_atomic_move(tmp_docx, path)
}

cg_manifest <- function(paths, root) {
  root_normalized <- normalizePath(root, winslash = "/", mustWork = TRUE)
  relative_path <- function(path) {
    normalized <- normalizePath(path, winslash = "/", mustWork = TRUE)
    prefix <- paste0(root_normalized, "/")
    if (startsWith(normalized, prefix)) substring(normalized, nchar(prefix) + 1L) else normalized
  }
  data.frame(
    path = vapply(paths, relative_path, character(1)),
    bytes = vapply(paths, function(path) unname(file.info(path)$size), numeric(1)),
    sha256 = vapply(paths, cg_sha256, character(1)),
    stringsAsFactors = FALSE
  )
}

cg_audit <- function(spec_path) {
  cg_require_packages()
  spec <- cg_read_spec(spec_path)
  cg_validate_spec(spec)
  data <- cg_apply_subset(cg_read_input(spec), spec$analysis$subset)
  prepared <- cg_prepare_data(data, spec)
  panel <- cg_panel_audit(prepared$data, spec)
  group <- cg_scalar(spec$analysis$group, NULL)
  list(
    spec_version = "1.0", analysis_id = cg_scalar(spec$analysis_id),
    input = normalizePath(cg_scalar(spec$input$path), winslash = "/", mustWork = TRUE),
    input_sha256 = cg_sha256(cg_scalar(spec$input$path)),
    dimensions = list(rows = nrow(prepared$data), columns = ncol(prepared$data)),
    panel = panel,
    group_counts = if (is.null(group)) list(all = nrow(prepared$data)) else as.list(table(prepared$data[[group]], useNA = "ifany")),
    variables = prepared$audit
  )
}

cg_run <- function(spec_path, output_root) {
  cg_progress("preflight", "validating dependencies and table specification")
  cg_require_packages()
  spec <- cg_read_spec(spec_path)
  cg_validate_spec(spec)
  output_root <- normalizePath(output_root, winslash = "/", mustWork = FALSE)
  if (dir.exists(output_root) && length(list.files(output_root, all.files = TRUE, no.. = TRUE))) cg_stop("Output root must be new or empty: %s", output_root)
  dir.create(output_root, recursive = TRUE, showWarnings = FALSE)
  stem <- cg_scalar(spec$outputs$stem)

  cg_progress("import", "reading the source data without modifying it")
  data <- cg_apply_subset(cg_read_input(spec), spec$analysis$subset)
  input_path <- normalizePath(cg_scalar(spec$input$path), winslash = "/", mustWork = TRUE)
  input_hash_before <- cg_sha256(input_path)

  cg_progress("labels", "validating variables, labels, levels, references, and panel structure")
  prepared <- cg_prepare_data(data, spec)
  panel <- cg_panel_audit(prepared$data, spec)
  variants <- cg_variants(prepared$data, spec, panel)

  cg_progress("compute", sprintf("running %d table variant(s)", length(variants)))
  results <- lapply(variants, cg_run_variant, spec = spec)
  names(results) <- vapply(results, `[[`, character(1), "id")
  display <- cg_bind_fill(lapply(results, `[[`, "display"))
  numeric <- do.call(rbind, lapply(results, `[[`, "numeric"))

  display_path <- file.path(output_root, paste0(stem, "_display.csv"))
  numeric_path <- file.path(output_root, paste0(stem, "_numeric_long.csv"))
  objects_path <- file.path(output_root, paste0(stem, "_objects.rds"))
  metadata_path <- file.path(output_root, paste0(stem, "_metadata.json"))
  docx_path <- file.path(output_root, paste0(stem, ".docx"))
  validation_path <- file.path(output_root, "validation.csv")
  manifest_path <- file.path(output_root, "manifest.csv")
  compatibility_path <- NULL

  cg_write_csv(display, display_path)
  cg_write_csv(numeric, numeric_path)
  cg_write_rds(list(spec = spec, results = lapply(results, function(x) x[c("id", "label", "warning", "rows", "group_counts", "objects")])), objects_path)

  cg_progress("render", "creating a three-line DOCX with no vertical grid")
  cg_render_docx(results, docx_path, paste("Descriptive table:", cg_scalar(spec$analysis_id)), spec, cg_scalar(spec$analysis$note, NULL))
  if (cg_bool(spec$display$compatibility_export2word, FALSE)) {
    if (length(results) != 1L) cg_stop("compatibility_export2word is unavailable for multi-variant panel output")
    compatibility_path <- file.path(output_root, paste0(stem, "_export2word_compatibility.docx"))
    cg_export2word_compatibility(results[[1L]], compatibility_path, spec)
  }

  metadata <- list(
    spec_version = "1.0", analysis_id = cg_scalar(spec$analysis_id),
    generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
    input = input_path, input_sha256 = input_hash_before,
    dimensions = list(rows = nrow(prepared$data), columns = ncol(prepared$data)),
    panel = panel, variables = prepared$audit,
    variants = lapply(results, function(x) x[c("id", "label", "warning", "rows", "group_counts")]),
    package_versions = as.list(vapply(required_packages, function(pkg) as.character(utils::packageVersion(pkg)), character(1))),
    statistical_tests = list(
      normal = "compareGroups method 1: t test or ANOVA as applicable",
      nonnormal = "compareGroups method 2: non-parametric rank test",
      categorical = "compareGroups method 3: categorical comparison selected by compareGroups"
    ),
    r_version = R.version.string,
    output_contract = list(display = basename(display_path), numeric_long = basename(numeric_path),
                           objects = basename(objects_path), docx = basename(docx_path))
  )
  cg_write_json(metadata, metadata_path)

  cg_progress("validate", "checking input immutability and durable outputs")
  input_hash_after <- cg_sha256(input_path)
  validation <- data.frame(
    check = c("input_hash_unchanged", "display_nonempty", "numeric_nonempty", "objects_reload", "docx_reopens", "all_variables_present", "panel_dual_has_compatibility"),
    passed = c(
      identical(input_hash_before, input_hash_after), nrow(display) > 0L, nrow(numeric) > 0L,
      !inherits(try(readRDS(objects_path), silent = TRUE), "try-error"), cg_validate_docx(docx_path),
      all(cg_all_variables(spec) %in% unique(numeric$variable)),
      !identical(cg_scalar(spec$analysis$panel_mode), "dual") || !isTRUE(panel$repeated_ids) || "compatibility_pooled" %in% names(results)
    ),
    details = c(input_hash_after, nrow(display), nrow(numeric), basename(objects_path), basename(docx_path),
                paste(setdiff(cg_all_variables(spec), unique(numeric$variable)), collapse = ","),
                paste(names(results), collapse = ",")),
    stringsAsFactors = FALSE
  )
  cg_write_csv(validation, validation_path)
  output_paths <- c(display_path, numeric_path, objects_path, metadata_path, docx_path, validation_path)
  if (!is.null(compatibility_path)) output_paths <- c(output_paths, compatibility_path)
  manifest <- cg_manifest(output_paths, output_root)
  cg_write_csv(manifest, manifest_path)
  if (!all(validation$passed)) cg_stop("Validation failed; inspect %s", validation_path)
  cg_progress("complete", sprintf("PASS outputs=%s", output_root))
  invisible(list(decision = "PASS", output_root = output_root, manifest = manifest_path, validation = validation_path))
}

cg_validate_outputs <- function(output_root, stem) {
  cg_require_packages()
  output_root <- normalizePath(output_root, winslash = "/", mustWork = TRUE)
  manifest_path <- file.path(output_root, "manifest.csv")
  validation_path <- file.path(output_root, "validation.csv")
  required <- c(paste0(stem, "_display.csv"), paste0(stem, "_numeric_long.csv"),
                paste0(stem, "_objects.rds"), paste0(stem, "_metadata.json"),
                paste0(stem, ".docx"), "validation.csv", "manifest.csv")
  missing <- required[!file.exists(file.path(output_root, required))]
  if (length(missing)) cg_stop("Missing outputs: %s", paste(missing, collapse = ", "))
  manifest <- utils::read.csv(manifest_path, check.names = FALSE, stringsAsFactors = FALSE)
  hash_ok <- vapply(seq_len(nrow(manifest)), function(index) {
    path <- file.path(output_root, manifest$path[[index]])
    file.exists(path) && identical(cg_sha256(path), manifest$sha256[[index]])
  }, logical(1))
  validation <- utils::read.csv(validation_path, check.names = FALSE, stringsAsFactors = FALSE)
  values <- tolower(as.character(validation$passed)) %in% c("true", "t", "1")
  ok <- !length(missing) && all(hash_ok) && all(values) && cg_validate_docx(file.path(output_root, paste0(stem, ".docx")))
  list(decision = if (ok) "PASS" else "FAIL", manifest_hashes = all(hash_ok), validations = all(values), docx = cg_validate_docx(file.path(output_root, paste0(stem, ".docx"))))
}
