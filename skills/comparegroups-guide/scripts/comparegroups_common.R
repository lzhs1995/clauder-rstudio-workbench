required_packages <- c(
  "compareGroups", "haven", "labelled", "officer", "flextable",
  "jsonlite", "digest"
)
required_versions <- c(compareGroups = "4.10.2")
comparegroups_guide_version <- "0.6.0"

cg_skill_versions <- function() list(comparegroups_guide = comparegroups_guide_version)

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
  too_old <- names(required_versions)[vapply(names(required_versions), function(pkg) {
    utils::packageVersion(pkg) < numeric_version(required_versions[[pkg]])
  }, logical(1))]
  if (length(too_old)) {
    cg_stop(
      "R packages below minimum version: %s",
      paste(sprintf("%s>=%s", too_old, required_versions[too_old]), collapse = ", ")
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

cg_write_text <- function(value, path) {
  tmp <- cg_atomic_path(path)
  on.exit(if (file.exists(tmp)) unlink(tmp), add = TRUE)
  writeLines(enc2utf8(value), tmp, useBytes = TRUE)
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

cg_character_vector <- function(x) {
  if (is.null(x) || !length(x)) return(character())
  unname(vapply(x, function(value) as.character(cg_scalar(value)), character(1)))
}

cg_safe_id <- function(x) gsub("[^A-Za-z0-9._-]", "_", as.character(x))

cg_unknown_field_errors <- function(value, allowed, path) {
  if (is.null(value) || !is.list(value)) return(character())
  unknown <- setdiff(names(value), allowed)
  if (!length(unknown)) character() else sprintf("unknown %s fields: %s", path, paste(unknown, collapse = ", "))
}

cg_required_field_errors <- function(value, required, path) {
  missing <- if (is.list(value)) setdiff(required, names(value)) else required
  if (!length(missing)) character() else sprintf("missing %s fields: %s", path, paste(missing, collapse = ", "))
}

cg_is_string <- function(value, allow_null = FALSE) {
  (allow_null && is.null(value)) || (is.character(value) && length(value) == 1L && !is.na(value))
}

cg_is_boolean <- function(value) is.logical(value) && length(value) == 1L && !is.na(value)

cg_is_integer_number <- function(value) {
  is.numeric(value) && length(value) == 1L && is.finite(value) && identical(as.numeric(value), floor(as.numeric(value)))
}

cg_is_scalar_value <- function(value) {
  length(value) == 1L && (is.character(value) || is.numeric(value) || is.logical(value)) && !is.na(value)
}

cg_level_spec_errors <- function(levels_spec, path, require_nonempty_labels = FALSE) {
  if (is.null(levels_spec)) return(character())
  if (!is.list(levels_spec) || !length(levels_spec)) return(sprintf("%s must be null or a non-empty array", path))
  errors <- character()
  for (item in levels_spec) {
    errors <- c(
      errors,
      cg_required_field_errors(item, c("value", "label"), paste0(path, " item")),
      cg_unknown_field_errors(item, c("value", "label"), paste0(path, " item"))
    )
    if (!cg_is_scalar_value(item$value)) errors <- c(errors, sprintf("%s item value must be a scalar", path))
    if (!cg_is_string(item$label) || (require_nonempty_labels && !nzchar(item$label))) {
      errors <- c(errors, sprintf("%s item label must be a non-empty string", path))
    }
  }
  if (!length(errors)) {
    values <- vapply(levels_spec, function(item) as.character(cg_scalar(item$value)), character(1))
    labels <- vapply(levels_spec, function(item) cg_scalar(item$label), character(1))
    if (anyDuplicated(values)) errors <- c(errors, sprintf("%s contains duplicate values", path))
    if (anyDuplicated(labels)) errors <- c(errors, sprintf("%s contains duplicate labels", path))
  }
  errors
}

cg_safe_relative_paths <- function(paths) {
  if (!length(paths)) return(logical())
  vapply(paths, function(path) {
    path <- as.character(path)
    nzchar(path) && !grepl("^(/|[A-Za-z]:[/\\\\])|//|\\\\\\\\", path) &&
      !any(strsplit(path, "[/\\\\]")[[1L]] %in% c("", ".", ".."))
  }, logical(1))
}

cg_spec_resolution <- function(spec) {
  resolution <- attr(spec, "cg_resolution", exact = TRUE)
  if (is.null(resolution)) list(input_spec_version = cg_scalar(spec$spec_version), defaults = list()) else resolution
}

cg_normalize_spec <- function(spec) {
  version <- cg_scalar(spec$spec_version, "")
  resolution <- list(input_spec_version = version, defaults = list(), variables = list(), display = list())
  if (identical(version, "1.0")) {
    attr(spec, "cg_resolution") <- resolution
    return(spec)
  }
  if (!identical(version, "1.1")) cg_stop("Unsupported spec_version: %s", version)

  defaults <- list(
    continuous_digits = as.integer(cg_scalar(spec$defaults$continuous_digits, 3L)),
    categorical_digits = as.integer(cg_scalar(spec$defaults$categorical_digits, 2L)),
    p_digits = as.integer(cg_scalar(spec$defaults$p_digits, 3L)),
    include_missing = cg_bool(spec$defaults$include_missing, FALSE)
  )
  resolution$defaults <- defaults
  for (block_index in seq_along(spec$blocks)) {
    for (variable_index in seq_along(spec$blocks[[block_index]]$variables)) {
      variable <- spec$blocks[[block_index]]$variables[[variable_index]]
      name <- cg_scalar(variable$name, "")
      digits_explicit <- !is.null(variable$digits) && length(variable$digits)
      missing_explicit <- !is.null(variable$include_missing) && length(variable$include_missing)
      if (!digits_explicit) {
        variable$digits <- if (identical(cg_scalar(variable$type), "categorical")) {
          defaults$categorical_digits
        } else defaults$continuous_digits
      }
      if (!missing_explicit) variable$include_missing <- defaults$include_missing
      spec$blocks[[block_index]]$variables[[variable_index]] <- variable
      resolution$variables[[name]] <- list(
        digits = as.integer(cg_scalar(variable$digits)),
        digits_source = if (digits_explicit) "variable" else "defaults",
        include_missing = cg_bool(variable$include_missing),
        include_missing_source = if (missing_explicit) "variable" else "defaults"
      )
    }
  }
  p_explicit <- !is.null(spec$display$p_digits) && length(spec$display$p_digits)
  if (!p_explicit) spec$display$p_digits <- defaults$p_digits
  resolution$display$p_digits <- list(
    value = as.integer(cg_scalar(spec$display$p_digits)),
    source = if (p_explicit) "display" else "defaults"
  )

  docx_defaults <- list(
    font_family = "Times New Roman", font_size = 10,
    orientation = "portrait", repeat_header = TRUE,
    title = NULL, footnote = NULL, column_widths = NULL
  )
  if (is.null(spec$display$docx)) spec$display$docx <- list()
  for (name in names(docx_defaults)) {
    if (is.null(spec$display$docx[[name]])) spec$display$docx[[name]] <- docx_defaults[[name]]
  }
  if (!is.null(spec$analysis$attrition)) {
    attrition_defaults <- list(
      group_name = "retention_status",
      retained_label = "Retained",
      deleted_label = "Deleted"
    )
    for (name in names(attrition_defaults)) {
      if (is.null(spec$analysis$attrition[[name]])) spec$analysis$attrition[[name]] <- attrition_defaults[[name]]
    }
    resolved_group <- cg_scalar(spec$analysis$attrition$group_name)
    requested_group <- cg_scalar(spec$analysis$group, NULL)
    if (!is.null(requested_group) && !identical(requested_group, resolved_group)) {
      cg_stop("analysis.group must be null or match attrition.group_name (%s)", resolved_group)
    }
    spec$analysis$group <- resolved_group
  }
  attr(spec, "cg_resolution") <- resolution
  spec
}

cg_all_variables <- function(spec) {
  unlist(lapply(spec$blocks, function(block) {
    vapply(block$variables, function(variable) cg_scalar(variable$name, ""), character(1))
  }), use.names = FALSE)
}

cg_validate_spec <- function(spec, require_input = TRUE, normalized = FALSE) {
  errors <- character()
  need <- c("spec_version", "analysis_id", "input", "analysis", "blocks", "display", "outputs")
  errors <- c(errors, sprintf("missing top-level field: %s", setdiff(need, names(spec))))
  version <- cg_scalar(spec$spec_version, "")
  if (!version %in% c("1.0", "1.1")) errors <- c(errors, "spec_version must be 1.0 or 1.1")
  allowed_top <- c(need, if (identical(version, "1.1")) "defaults" else character())
  unknown_top <- setdiff(names(spec), allowed_top)
  if (length(unknown_top)) errors <- c(errors, paste("unknown top-level fields:", paste(unknown_top, collapse = ", ")))
  analysis_id <- cg_scalar(spec$analysis_id, "")
  if (!cg_is_string(spec$analysis_id) || !grepl("^[A-Za-z0-9][A-Za-z0-9._-]*$", analysis_id)) errors <- c(errors, "analysis_id must be a safe non-empty string identifier")
  stem <- cg_scalar(spec$outputs$stem, "")
  if (!cg_is_string(spec$outputs$stem) || !grepl("^[A-Za-z0-9_][A-Za-z0-9._-]*$", stem)) errors <- c(errors, "outputs.stem must be a safe non-empty string file stem")
  analysis_fields <- c("group", "panel_mode", "subset", "note")
  display_fields <- c("show_all", "show_n", "show_p_overall", "show_p_multiple", "show_p_trend", "p_digits", "compatibility_export2word")
  if (identical(version, "1.1")) {
    analysis_fields <- c(analysis_fields, "group_reference", "group_levels", "variants", "attrition")
    display_fields <- c(display_fields, "hide_no", "docx")
  }
  errors <- c(
    errors,
    cg_required_field_errors(spec$input, c("path", "format"), "input"),
    cg_required_field_errors(spec$analysis, c("group", "panel_mode", "subset"), "analysis"),
    cg_required_field_errors(spec$display, c("show_all", "show_n", "show_p_overall", "show_p_multiple", "show_p_trend", if (identical(version, "1.0")) "p_digits" else character()), "display"),
    cg_required_field_errors(spec$outputs, c("stem", "formats"), "outputs"),
    cg_unknown_field_errors(spec$input, c("path", "format", "id", "time"), "input"),
    cg_unknown_field_errors(spec$analysis, analysis_fields, "analysis"),
    cg_unknown_field_errors(spec$display, display_fields, "display"),
    cg_unknown_field_errors(spec$outputs, c("stem", "formats"), "outputs")
  )
  if (identical(version, "1.1")) {
    errors <- c(
      errors,
      cg_unknown_field_errors(spec$defaults, c("continuous_digits", "categorical_digits", "p_digits", "include_missing"), "defaults"),
      cg_unknown_field_errors(spec$display$docx, c("font_family", "font_size", "orientation", "repeat_header", "title", "footnote", "column_widths"), "display.docx")
    )
  }
  if (!cg_is_string(spec$input$path) || !nzchar(spec$input$path)) errors <- c(errors, "input.path must be a non-empty string")
  if (!cg_is_string(spec$input$format) || !spec$input$format %in% c("auto", "dta", "sav", "csv", "tsv", "rds")) errors <- c(errors, "input.format is invalid")
  for (name in c("id", "time")) {
    if (!is.null(spec$input[[name]]) && !cg_is_string(spec$input[[name]])) errors <- c(errors, sprintf("input.%s must be a string or null", name))
  }
  for (name in c("group", "subset", "note")) {
    if (!is.null(spec$analysis[[name]]) && !cg_is_string(spec$analysis[[name]])) errors <- c(errors, sprintf("analysis.%s must be a string or null", name))
  }
  for (name in c("show_all", "show_n", "show_p_overall", "show_p_multiple", "show_p_trend")) {
    if (!cg_is_boolean(spec$display[[name]])) errors <- c(errors, sprintf("display.%s must be boolean", name))
  }
  if (!is.null(spec$display$compatibility_export2word) && !cg_is_boolean(spec$display$compatibility_export2word)) {
    errors <- c(errors, "display.compatibility_export2word must be boolean")
  }
  formats <- cg_character_vector(spec$outputs$formats)
  if (!is.list(spec$outputs$formats) || !length(formats) || anyDuplicated(formats) || any(!formats %in% c("docx", "csv", "rds"))) {
    errors <- c(errors, "outputs.formats must be a non-empty unique array of docx/csv/rds")
  }
  if (!length(spec$blocks)) errors <- c(errors, "blocks must not be empty")
  variables <- cg_all_variables(spec)
  if (any(!nzchar(variables))) errors <- c(errors, "every variable requires a name")
  duplicates <- unique(variables[duplicated(variables)])
  if (length(duplicates)) errors <- c(errors, paste("duplicate variables:", paste(duplicates, collapse = ", ")))
  allowed_methods <- c("normal", "nonnormal", "categorical")
  allowed_types <- c("continuous", "categorical")
  block_ids <- vapply(spec$blocks, function(block) cg_scalar(block$id, ""), character(1))
  if (anyDuplicated(block_ids)) errors <- c(errors, "block ids must be unique")
  for (block in spec$blocks) {
    errors <- c(
      errors,
      cg_required_field_errors(block, c("id", "label", "variables"), "block"),
      cg_unknown_field_errors(block, c("id", "label", "variables"), "block")
    )
    if (!cg_is_string(block$id) || !nzchar(cg_scalar(block$id, ""))) errors <- c(errors, "every block requires a string id")
    if (!cg_is_string(block$label) || !nzchar(block$label)) errors <- c(errors, sprintf("block %s requires a non-empty label", cg_scalar(block$id, "?")))
    if (!length(block$variables)) errors <- c(errors, sprintf("block %s has no variables", cg_scalar(block$id, "?")))
    for (variable in block$variables) {
      variable_required <- c("name", "type", "method", if (identical(version, "1.0")) c("digits", "label", "include_missing") else character())
      errors <- c(
        errors,
        cg_required_field_errors(variable, variable_required, "variable"),
        cg_unknown_field_errors(variable, c("name", "type", "method", "digits", "label", "include_missing", "reference", "levels"), "variable")
      )
      method <- cg_scalar(variable$method, "")
      type <- cg_scalar(variable$type, "")
      if (!cg_is_string(variable$name) || !nzchar(cg_scalar(variable$name, ""))) errors <- c(errors, "every variable requires a non-empty string name")
      if (!cg_is_string(variable$method)) errors <- c(errors, sprintf("method for %s must be a string", cg_scalar(variable$name, "?")))
      if (!cg_is_string(variable$type)) errors <- c(errors, sprintf("type for %s must be a string", cg_scalar(variable$name, "?")))
      if (!method %in% allowed_methods) errors <- c(errors, sprintf("invalid method for %s: %s", cg_scalar(variable$name, "?"), method))
      if (!type %in% allowed_types) errors <- c(errors, sprintf("invalid type for %s: %s", cg_scalar(variable$name, "?"), type))
      if (identical(type, "continuous") && identical(method, "categorical")) errors <- c(errors, sprintf("continuous variable %s cannot use categorical", cg_scalar(variable$name, "?")))
      if (identical(type, "categorical") && !identical(method, "categorical")) errors <- c(errors, sprintf("categorical variable %s must use categorical", cg_scalar(variable$name, "?")))
      if (identical(version, "1.1") && identical(type, "continuous") && (!is.null(variable$reference) || !is.null(variable$levels))) {
        errors <- c(errors, sprintf("continuous variable %s cannot declare reference or levels", cg_scalar(variable$name, "?")))
      }
      if (!is.null(variable$label) && !cg_is_string(variable$label)) errors <- c(errors, sprintf("variable %s label must be a string or null", cg_scalar(variable$name, "?")))
      if (!is.null(variable$reference) && !cg_is_string(variable$reference)) errors <- c(errors, sprintf("variable %s reference must be a string or null", cg_scalar(variable$name, "?")))
      if (!is.null(variable$include_missing) && !cg_is_boolean(variable$include_missing)) errors <- c(errors, sprintf("variable %s include_missing must be boolean", cg_scalar(variable$name, "?")))
      errors <- c(errors, cg_level_spec_errors(variable$levels, sprintf("variable %s levels", cg_scalar(variable$name, "?")), require_nonempty_labels = identical(version, "1.1")))
      if ((identical(version, "1.0") || normalized) && (is.null(variable$digits) || !length(variable$digits))) {
        errors <- c(errors, sprintf("variable %s requires digits", cg_scalar(variable$name, "?")))
      }
      if ((identical(version, "1.0") || normalized) && (is.null(variable$include_missing) || !length(variable$include_missing))) {
        errors <- c(errors, sprintf("variable %s requires include_missing", cg_scalar(variable$name, "?")))
      }
      digits_value <- cg_scalar(variable$digits, NA_real_)
      if ((identical(version, "1.0") || normalized) && (!cg_is_integer_number(digits_value) || digits_value < 0L || digits_value > 8L)) {
        errors <- c(errors, sprintf("invalid digits for %s", cg_scalar(variable$name, "?")))
      }
    }
  }
  panel_mode <- cg_scalar(spec$analysis$panel_mode, "")
  if (!cg_is_string(spec$analysis$panel_mode) || !panel_mode %in% c("cross_section", "dual", "pooled_compatibility")) errors <- c(errors, "invalid panel_mode")
  if (identical(version, "1.1")) {
    for (name in c("continuous_digits", "categorical_digits", "p_digits")) {
      if (!is.null(spec$defaults[[name]])) {
        value <- cg_scalar(spec$defaults[[name]], NA_real_)
        if (!cg_is_integer_number(value) || value < 0L || value > 8L) errors <- c(errors, sprintf("defaults.%s must be an integer from 0 to 8", name))
      }
    }
    if (!is.null(spec$defaults$include_missing) && !is.logical(cg_scalar(spec$defaults$include_missing))) {
      errors <- c(errors, "defaults.include_missing must be boolean")
    }
  }
  p_digits <- cg_scalar(spec$display$p_digits, NA_real_)
  if ((identical(version, "1.0") || normalized) && (!cg_is_integer_number(p_digits) || p_digits < 0L || p_digits > 8L)) {
    errors <- c(errors, "display.p_digits must be an integer from 0 to 8")
  }
  if (!is.null(spec$display$hide_no)) {
    hide_no_value <- spec$display$hide_no
    hide_no <- try(cg_character_vector(hide_no_value), silent = TRUE)
    hide_no_types <- if (is.character(hide_no_value)) length(hide_no_value) == 1L else is.list(hide_no_value) && all(vapply(hide_no_value, cg_is_string, logical(1)))
    if (!hide_no_types || inherits(hide_no, "try-error") || !length(hide_no) || any(!nzchar(hide_no))) errors <- c(errors, "display.hide_no must contain non-empty strings")
  }
  errors <- c(errors, cg_level_spec_errors(spec$analysis$group_levels, "analysis.group_levels", require_nonempty_labels = TRUE))
  if (!is.null(spec$analysis$group_reference) && !cg_is_string(spec$analysis$group_reference)) errors <- c(errors, "analysis.group_reference must be a string or null")
  if (is.null(cg_scalar(spec$analysis$group, NULL)) && !is.null(spec$analysis$group_reference) && is.null(spec$analysis$attrition)) {
    errors <- c(errors, "analysis.group_reference requires analysis.group or analysis.attrition")
  }
  if (is.null(cg_scalar(spec$analysis$group, NULL)) && !is.null(spec$analysis$group_levels) && is.null(spec$analysis$attrition)) {
    errors <- c(errors, "analysis.group_levels requires analysis.group or analysis.attrition")
  }
  variants <- spec$analysis$variants
  if (!is.null(variants)) {
    if (!is.list(variants) || !length(variants)) errors <- c(errors, "analysis.variants must be a non-empty array")
    if (identical(version, "1.1")) {
      for (variant in variants) errors <- c(errors, cg_unknown_field_errors(variant, c("id", "label", "subset"), "analysis.variants item"))
    }
    variant_ids <- vapply(variants, function(variant) cg_scalar(variant$id, ""), character(1))
    if (any(!nzchar(variant_ids))) errors <- c(errors, "every analysis variant requires an id")
    if (any(!grepl("^[A-Za-z0-9][A-Za-z0-9._-]*$", variant_ids))) errors <- c(errors, "analysis variant ids must be safe identifiers")
    if (anyDuplicated(variant_ids)) errors <- c(errors, "analysis variant ids must be unique")
    for (variant in variants) {
      errors <- c(errors, cg_required_field_errors(variant, c("id", "subset"), "analysis.variants item"))
      if (!is.null(variant$label) && !cg_is_string(variant$label)) errors <- c(errors, "analysis variant label must be a string or null")
      if (!is.null(variant$subset) && !cg_is_string(variant$subset)) errors <- c(errors, "analysis variant subset must be a string or null")
    }
  }
  if (!is.null(spec$analysis$attrition)) {
    if (identical(version, "1.1")) {
      errors <- c(errors, cg_unknown_field_errors(
        spec$analysis$attrition,
        c("baseline_values", "followup_values", "group_name", "retained_label", "deleted_label"),
        "analysis.attrition"
      ))
    }
    id <- cg_scalar(spec$input$id, NULL)
    time <- cg_scalar(spec$input$time, NULL)
    if (is.null(id) || !nzchar(id) || is.null(time) || !nzchar(time)) errors <- c(errors, "attrition requires input.id and input.time")
    baseline <- cg_character_vector(spec$analysis$attrition$baseline_values)
    followup <- cg_character_vector(spec$analysis$attrition$followup_values)
    if (!is.list(spec$analysis$attrition$baseline_values) || !length(baseline) || any(!vapply(spec$analysis$attrition$baseline_values, cg_is_scalar_value, logical(1))) || anyDuplicated(baseline)) errors <- c(errors, "attrition baseline_values must be a non-empty unique scalar array")
    if (!is.list(spec$analysis$attrition$followup_values) || !length(followup) || any(!vapply(spec$analysis$attrition$followup_values, cg_is_scalar_value, logical(1))) || anyDuplicated(followup)) errors <- c(errors, "attrition followup_values must be a non-empty unique scalar array")
    if (length(intersect(baseline, followup))) errors <- c(errors, "attrition baseline_values and followup_values must not overlap")
    for (name in c("group_name", "retained_label", "deleted_label")) {
      if (!is.null(spec$analysis$attrition[[name]]) && (!cg_is_string(spec$analysis$attrition[[name]]) || !nzchar(spec$analysis$attrition[[name]]))) {
        errors <- c(errors, sprintf("analysis.attrition.%s must be a non-empty string", name))
      }
    }
    retained_label <- cg_scalar(spec$analysis$attrition$retained_label, "Retained")
    deleted_label <- cg_scalar(spec$analysis$attrition$deleted_label, "Deleted")
    if (identical(retained_label, deleted_label)) errors <- c(errors, "attrition retained_label and deleted_label must differ")
  }
  if (!is.null(spec$display$docx)) {
    orientation <- cg_scalar(spec$display$docx$orientation, "portrait")
    if (!cg_is_string(orientation) || !orientation %in% c("portrait", "landscape")) errors <- c(errors, "display.docx.orientation must be portrait or landscape")
    size <- cg_scalar(spec$display$docx$font_size, 10)
    if (!is.numeric(size) || length(size) != 1L || !is.finite(size) || size <= 0 || size > 72) errors <- c(errors, "display.docx.font_size must be a number within (0, 72]")
    if (!is.null(spec$display$docx$font_family) && (!cg_is_string(spec$display$docx$font_family) || !nzchar(spec$display$docx$font_family))) errors <- c(errors, "display.docx.font_family must be a non-empty string")
    if (!is.null(spec$display$docx$repeat_header) && !cg_is_boolean(spec$display$docx$repeat_header)) errors <- c(errors, "display.docx.repeat_header must be boolean")
    for (name in c("title", "footnote")) {
      if (!is.null(spec$display$docx[[name]]) && !cg_is_string(spec$display$docx[[name]])) errors <- c(errors, sprintf("display.docx.%s must be a string or null", name))
    }
    widths <- spec$display$docx$column_widths
    if (!is.null(widths)) {
      width_values <- unlist(widths, use.names = FALSE)
      if (!is.list(widths) || !length(width_values) || !is.numeric(width_values) || any(!is.finite(width_values)) || any(width_values <= 0)) {
        errors <- c(errors, "display.docx.column_widths must be null or a non-empty array of positive numbers")
      }
    }
  }
  input_path <- cg_scalar(spec$input$path, "")
  if (require_input && (!nzchar(input_path) || !file.exists(input_path))) errors <- c(errors, sprintf("input does not exist: %s", input_path))
  if (length(errors)) cg_stop("Invalid table specification:\n- %s", paste(errors, collapse = "\n- "))
  invisible(TRUE)
}

cg_read_normalized_spec <- function(path, require_input = TRUE) {
  raw <- cg_read_spec(path)
  cg_validate_spec(raw, require_input = require_input, normalized = FALSE)
  normalized <- cg_normalize_spec(raw)
  cg_validate_spec(normalized, require_input = require_input, normalized = TRUE)
  list(raw = raw, normalized = normalized, resolution = cg_spec_resolution(normalized))
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

cg_subset_preserve <- function(data, rows) {
  labels <- lapply(data, attr, which = "label", exact = TRUE)
  out <- data[rows, , drop = FALSE]
  for (name in names(out)) {
    if (!is.null(labels[[name]])) attr(out[[name]], "label") <- labels[[name]]
    if (is.factor(out[[name]])) out[[name]] <- droplevels(out[[name]])
  }
  out
}

cg_value_key <- function(x) {
  if (inherits(x, "haven_labelled") || inherits(x, "labelled")) x <- unclass(x)
  if (is.factor(x)) as.character(x) else as.character(x)
}

cg_apply_attrition <- function(data, spec) {
  attrition <- spec$analysis$attrition
  if (is.null(attrition)) return(list(data = data, metadata = NULL))
  id <- cg_scalar(spec$input$id, NULL)
  time <- cg_scalar(spec$input$time, NULL)
  missing <- setdiff(c(id, time), names(data))
  if (length(missing)) cg_stop("Attrition variables missing from input: %s", paste(missing, collapse = ", "))
  if (any(is.na(data[[id]]))) cg_stop("Attrition id %s contains missing values", id)

  baseline_values <- cg_character_vector(attrition$baseline_values)
  followup_values <- cg_character_vector(attrition$followup_values)
  time_key <- cg_value_key(data[[time]])
  baseline_rows <- !is.na(data[[time]]) & time_key %in% baseline_values
  followup_rows <- !is.na(data[[time]]) & time_key %in% followup_values
  if (!any(baseline_rows)) cg_stop("Attrition baseline_values matched no rows")
  if (!any(followup_rows)) cg_stop("Attrition followup_values matched no rows")

  baseline <- cg_subset_preserve(data, baseline_rows)
  baseline_ids <- cg_value_key(baseline[[id]])
  duplicate_ids <- unique(baseline_ids[duplicated(baseline_ids)])
  if (length(duplicate_ids)) {
      cg_stop("Attrition requires exactly one baseline row per id; duplicates: %s", paste(utils::head(duplicate_ids, 10L), collapse = ", "))
  }
  all_ids <- unique(cg_value_key(data[[id]]))
  missing_baseline_ids <- setdiff(all_ids, baseline_ids)
  if (length(missing_baseline_ids)) {
    cg_stop(
      "Attrition requires exactly one baseline row per non-missing id; ids without baseline: %s",
      paste(utils::head(missing_baseline_ids, 10L), collapse = ", ")
    )
  }
  followup_ids <- unique(cg_value_key(data[[id]][followup_rows]))
  group_name <- cg_scalar(attrition$group_name, "retention_status")
  if (group_name %in% names(baseline)) cg_stop("Attrition refuses to overwrite existing column: %s", group_name)
  retained_label <- cg_scalar(attrition$retained_label, "Retained")
  deleted_label <- cg_scalar(attrition$deleted_label, "Deleted")
  status <- ifelse(baseline_ids %in% followup_ids, retained_label, deleted_label)
  baseline[[group_name]] <- factor(status, levels = c(deleted_label, retained_label))
  counts <- table(baseline[[group_name]])
  if (any(counts == 0L)) cg_stop("Attrition requires both retained and deleted groups")
  list(
    data = baseline,
    metadata = list(
      id = id, time = time, baseline_values = baseline_values,
      followup_values = followup_values, group_name = group_name,
      baseline_rows = nrow(baseline), retained = unname(counts[[retained_label]]),
      deleted = unname(counts[[deleted_label]])
    )
  )
}

cg_prepare_analysis_data <- function(data, spec) {
  attrition <- cg_apply_attrition(data, spec)
  selected <- cg_apply_subset(attrition$data, spec$analysis$subset)
  if (!nrow(selected)) cg_stop("Analysis subset produced zero rows")
  list(data = selected, attrition = attrition$metadata)
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

cg_prepare_group <- function(x, spec) {
  pairs <- cg_level_pairs(spec$analysis$group_levels)
  if (!is.null(pairs)) {
    raw <- cg_value_key(x)
    unknown <- setdiff(unique(raw[!is.na(raw)]), pairs$values)
    if (length(unknown)) cg_stop("Unknown grouping codes: %s", paste(unknown, collapse = ", "))
    out <- factor(raw, levels = pairs$values, labels = pairs$labels)
    empty <- levels(out)[table(out) == 0L]
    if (length(empty)) cg_stop("Declared grouping levels have no observations: %s", paste(empty, collapse = ", "))
  } else if (inherits(x, "haven_labelled") || inherits(x, "labelled")) {
    label_map <- attr(x, "labels", exact = TRUE)
    if (is.null(label_map) || !length(label_map)) cg_stop("Labelled grouping variable has no value labels")
    raw <- as.character(unclass(x))
    unknown <- setdiff(unique(raw[!is.na(raw)]), as.character(unname(label_map)))
    if (length(unknown)) cg_stop("Unknown labelled grouping codes: %s", paste(unknown, collapse = ", "))
    out <- haven::as_factor(x, levels = "labels")
  } else if (is.factor(x)) {
    out <- x
  } else if (is.character(x) || is.logical(x)) {
    out <- factor(x)
  } else if (identical(cg_scalar(spec$spec_version), "1.0") && is.numeric(x)) {
    out <- factor(x)
  } else {
    cg_stop("Numeric unlabelled grouping variable requires analysis.group_levels")
  }
  out <- droplevels(out)
  reference <- cg_scalar(spec$analysis$group_reference, NULL)
  if (!is.null(reference)) {
    if (!reference %in% levels(out)) cg_stop("Grouping reference %s not found", reference)
    out <- stats::relevel(out, ref = reference)
  }
  if (nlevels(out) < 2L) cg_stop("Grouping variable requires at least two non-empty levels")
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
    data[[group]] <- cg_prepare_group(data[[group]], spec)
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

cg_panel_variants <- function(data, spec, panel) {
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

cg_validate_variant_data <- function(data, spec, variant_id) {
  if (!nrow(data)) cg_stop("Variant %s produced zero rows", variant_id)
  group <- cg_scalar(spec$analysis$group, NULL)
  if (!is.null(group)) {
    declared <- cg_level_pairs(spec$analysis$group_levels)
    if (!is.null(declared)) {
      observed <- unique(as.character(data[[group]][!is.na(data[[group]])]))
      empty <- setdiff(declared$labels, observed)
      if (length(empty)) {
        cg_stop(
          "Variant %s has declared grouping levels with no observations: %s",
          variant_id, paste(empty, collapse = ", ")
        )
      }
    }
    data[[group]] <- droplevels(data[[group]])
    if (nlevels(data[[group]]) < 2L) cg_stop("Variant %s has fewer than two non-empty groups", variant_id)
  }
  data
}

cg_variants <- function(data, spec, panel = NULL) {
  requested <- spec$analysis$variants
  if (is.null(requested) || !length(requested)) {
    return(cg_panel_variants(data, spec, if (is.null(panel)) cg_panel_audit(data, spec) else panel))
  }
  out <- list()
  for (variant in requested) {
    base_id <- cg_scalar(variant$id)
    base_label <- cg_scalar(variant$label, base_id)
    selected <- cg_apply_subset(data, variant$subset)
    selected <- cg_validate_variant_data(selected, spec, base_id)
    children <- cg_panel_variants(selected, spec, cg_panel_audit(selected, spec))
    for (child in children) {
      # cross_section 的 primary 不增加冗余后缀；dual 后缀固定且可预测。
      child_id <- if (length(children) == 1L && identical(child$id, "primary")) {
        base_id
      } else paste(base_id, child$id, sep = "__")
      child$id <- child_id
      child$label <- if (length(children) == 1L && identical(children[[1L]]$id, "primary")) {
        base_label
      } else paste(base_label, child$label, sep = " — ")
      child$data <- cg_validate_variant_data(child$data, spec, child_id)
      out[[length(out) + 1L]] <- child
    }
  }
  ids <- vapply(out, `[[`, character(1), "id")
  if (anyDuplicated(ids)) cg_stop("Resolved variant ids must be unique")
  out
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
  hide_no <- cg_character_vector(display$hide_no)
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
      table_args <- list(
        x = cg, digits = digits, digits.ratio = digits,
        show.all = cg_bool(display$show_all, TRUE), show.n = cg_bool(display$show_n, TRUE),
        show.p.overall = cg_bool(display$show_p_overall, TRUE) && !suppress,
        show.p.mul = cg_bool(display$show_p_multiple, FALSE) && !suppress,
        show.p.trend = cg_bool(display$show_p_trend, FALSE) && !suppress,
        digits.p = as.integer(cg_scalar(display$p_digits, 3L))
      )
      if (length(hide_no)) table_args$hide.no <- hide_no
      table <- do.call(compareGroups::createTable, table_args)
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
  docx <- spec$display$docx
  if (is.null(docx)) docx <- list()
  resolved_title <- cg_scalar(docx$title, title)
  font_family <- cg_scalar(docx$font_family, "Times New Roman")
  font_size <- as.numeric(cg_scalar(docx$font_size, 10))
  repeat_header <- cg_bool(docx$repeat_header, TRUE)
  doc <- officer::read_docx()
  doc <- officer::body_add_par(doc, resolved_title, style = "heading 1")
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
    ft <- flextable::font(ft, fontname = font_family, part = "all")
    ft <- flextable::fontsize(ft, size = font_size, part = "all")
    widths <- suppressWarnings(as.numeric(unlist(docx$column_widths, use.names = FALSE)))
    if (length(widths)) {
      if (length(widths) != ncol(frame) || any(!is.finite(widths)) || any(widths <= 0)) {
        cg_stop("display.docx.column_widths must contain one positive width per rendered column")
      }
      ft <- flextable::width(ft, j = seq_len(ncol(frame)), width = widths, unit = "in")
    } else {
      ft <- flextable::autofit(ft)
    }
    ft <- flextable::paginate(ft, init = repeat_header, hdr_ftr = repeat_header)
    doc <- flextable::body_add_flextable(doc, ft)
    if (!is.null(result$warning)) doc <- officer::body_add_par(doc, paste("Note:", result$warning), style = "Normal")
  }
  if (!is.null(note) && nzchar(note)) doc <- officer::body_add_par(doc, paste("Note:", note), style = "Normal")
  footnote <- cg_scalar(docx$footnote, NULL)
  if (!is.null(footnote) && nzchar(footnote)) doc <- officer::body_add_par(doc, footnote, style = "Normal")
  if (identical(cg_scalar(docx$orientation, "portrait"), "landscape")) {
    doc <- officer::body_end_section_landscape(doc)
  }
  tmp <- cg_atomic_path(path)
  if (!grepl("\\.docx$", tmp, ignore.case = TRUE)) tmp_docx <- paste0(tmp, ".docx") else tmp_docx <- tmp
  on.exit({ if (file.exists(tmp)) unlink(tmp); if (exists("tmp_docx") && file.exists(tmp_docx)) unlink(tmp_docx) }, add = TRUE)
  print(doc, target = tmp_docx)
  cg_atomic_move(tmp_docx, path)
}

cg_count_pattern <- function(pattern, text) {
  hits <- gregexpr(pattern, text, perl = TRUE)[[1L]]
  if (identical(hits[[1L]], -1L)) 0L else length(hits)
}

cg_matches <- function(pattern, text) {
  matches <- gregexpr(pattern, text, perl = TRUE)[[1L]]
  if (identical(matches[[1L]], -1L)) character() else regmatches(text, list(matches))[[1L]]
}

cg_active_border_count <- function(text, tag) {
  border_blocks <- c(
    cg_matches("<w:tcBorders(?:\\s[^>]*)?>.*?</w:tcBorders>", text),
    cg_matches("<w:tblBorders(?:\\s[^>]*)?>.*?</w:tblBorders>", text)
  )
  if (!length(border_blocks)) return(0L)
  tags <- cg_matches(sprintf("<w:%s(?:\\s[^>]*)?/>", tag), paste(border_blocks, collapse = ""))
  if (!length(tags)) return(0L)
  sum(!grepl("w:val=\\\"(?:nil|none)\\\"", tags, perl = TRUE) &
        !grepl("w:w=\\\"0\\\"", tags, perl = TRUE))
}

cg_docx_table_structure <- function(xml) {
  rows <- cg_matches("<w:tr(?:\\s[^>]*)?>.*?</w:tr>", xml)
  if (length(rows) < 2L) {
    return(list(rows = length(rows), top = 0L, bottom = 0L, vertical = 0L,
                internal_horizontal = 0L, three_line = FALSE))
  }
  top_by_row <- vapply(rows, cg_active_border_count, integer(1), tag = "top")
  bottom_by_row <- vapply(rows, cg_active_border_count, integer(1), tag = "bottom")
  vertical <- sum(vapply(c("left", "right", "start", "end", "insideV"), function(tag) cg_active_border_count(xml, tag), integer(1)))
  internal_horizontal <- cg_active_border_count(xml, "insideH")
  allowed_top_rows <- seq_len(min(2L, length(rows)))
  allowed_bottom_rows <- unique(c(1L, length(rows)))
  exact_horizontal <- top_by_row[[1L]] > 0L &&
    (bottom_by_row[[1L]] > 0L || top_by_row[[2L]] > 0L) &&
    bottom_by_row[[length(rows)]] > 0L &&
    all(top_by_row[-allowed_top_rows] == 0L) &&
    all(bottom_by_row[-allowed_bottom_rows] == 0L)
  list(
    rows = length(rows), top = sum(top_by_row), bottom = sum(bottom_by_row),
    vertical = vertical, internal_horizontal = internal_horizontal,
    three_line = exact_horizontal && vertical == 0L && internal_horizontal == 0L
  )
}

cg_docx_structure <- function(path) {
  failed <- list(reopens = FALSE, tables = 0L, table_details = list(), top = 0L, bottom = 0L, vertical = 0L, internal_horizontal = 0L, landscape = FALSE, three_line = FALSE)
  if (!file.exists(path) || file.info(path)$size <= 0) return(failed)
  listing <- try(utils::unzip(path, list = TRUE), silent = TRUE)
  reopens <- !inherits(listing, "try-error") && "word/document.xml" %in% listing$Name
  if (!reopens) return(failed)
  unpack <- tempfile("comparegroups-docx-")
  dir.create(unpack)
  on.exit(unlink(unpack, recursive = TRUE), add = TRUE)
  extracted <- try(utils::unzip(path, files = "word/document.xml", exdir = unpack), silent = TRUE)
  if (inherits(extracted, "try-error") || !length(extracted)) return(failed)
  xml <- paste(readLines(extracted[[1L]], warn = FALSE, encoding = "UTF-8"), collapse = "")
  tables <- cg_matches("<w:tbl(?:\\s[^>]*)?>.*?</w:tbl>", xml)
  details <- lapply(tables, cg_docx_table_structure)
  top <- sum(vapply(details, `[[`, integer(1), "top"))
  bottom <- sum(vapply(details, `[[`, integer(1), "bottom"))
  vertical <- sum(vapply(details, `[[`, integer(1), "vertical"))
  internal_horizontal <- sum(vapply(details, `[[`, integer(1), "internal_horizontal"))
  list(
    reopens = TRUE, tables = length(tables), table_details = details,
    top = top, bottom = bottom, vertical = vertical, internal_horizontal = internal_horizontal,
    landscape = grepl("<w:pgSz[^>]*w:orient=\"landscape\"", xml, perl = TRUE),
    three_line = length(details) > 0L && all(vapply(details, `[[`, logical(1), "three_line"))
  )
}

cg_validate_docx <- function(path) isTRUE(cg_docx_structure(path)$three_line)

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

cg_sha256_lines <- function(paths, root) {
  root <- normalizePath(root, winslash = "/", mustWork = TRUE)
  vapply(paths, function(path) {
    normalized <- normalizePath(path, winslash = "/", mustWork = TRUE)
    prefix <- paste0(root, "/")
    relative <- if (startsWith(normalized, prefix)) substring(normalized, nchar(prefix) + 1L) else normalized
    sprintf("%s  %s", cg_sha256(normalized), relative)
  }, character(1))
}

cg_validation_frame <- function(check, passed, expected, actual) {
  actual <- as.character(actual)
  expected <- as.character(expected)
  detail <- ifelse(passed, "", sprintf("expected=%s; actual=%s", expected, actual))
  data.frame(
    check = check, passed = as.logical(passed), expected = expected,
    actual = actual, detail = detail, details = actual,
    stringsAsFactors = FALSE
  )
}

cg_output_validation_frame <- function(
  input_hash_before, input_hash_after, display, numeric, objects_path,
  docx_structure, spec, panel, results, variant_outputs, output_root
) {
  compatibility_ids <- grepl("(^|__)compatibility_pooled$", names(results))
  cg_validation_frame(
    check = c(
      "input_hash_unchanged", "display_nonempty", "numeric_nonempty", "objects_reload",
      "docx_reopens", "docx_true_three_line", "docx_no_vertical_grid",
      "all_variables_present", "panel_dual_has_compatibility",
      "variant_outputs_exist", "variant_docx_true_three_line"
    ),
    passed = c(
      identical(input_hash_before, input_hash_after), nrow(display) > 0L, nrow(numeric) > 0L,
      !inherits(try(readRDS(objects_path), silent = TRUE), "try-error"), docx_structure$reopens,
      docx_structure$three_line, docx_structure$vertical == 0L,
      all(cg_all_variables(spec) %in% unique(numeric$variable)),
      !identical(cg_scalar(spec$analysis$panel_mode), "dual") || !isTRUE(panel$repeated_ids) || any(compatibility_ids),
      all(file.exists(variant_outputs$paths)),
      !length(variant_outputs$entries) || all(vapply(variant_outputs$entries, function(entry) {
        cg_validate_docx(file.path(output_root, cg_scalar(entry$files$docx)))
      }, logical(1)))
    ),
    expected = c(
      input_hash_before, ">0", ">0", "readable RDS", "valid DOCX",
      "each table has exactly top/header-bottom/final-bottom", "0", "all variables",
      "compatibility_pooled", "all files present", "all true three-line"
    ),
    actual = c(
      input_hash_after, nrow(display), nrow(numeric), basename(objects_path), docx_structure$reopens,
      sprintf(
        "tables=%s,three_line=%s,top=%s,bottom=%s,internal_horizontal=%s",
        docx_structure$tables, docx_structure$three_line, docx_structure$top,
        docx_structure$bottom, docx_structure$internal_horizontal
      ),
      docx_structure$vertical,
      paste(setdiff(cg_all_variables(spec), unique(numeric$variable)), collapse = ","),
      paste(names(results), collapse = ","),
      paste(basename(variant_outputs$paths[!file.exists(variant_outputs$paths)]), collapse = ","),
      paste(names(variant_outputs$entries), collapse = ",")
    )
  )
}

cg_audit <- function(spec_path) {
  cg_require_packages()
  bundle <- cg_read_normalized_spec(spec_path)
  spec <- bundle$normalized
  analysis_data <- cg_prepare_analysis_data(cg_read_input(spec), spec)
  prepared <- cg_prepare_data(analysis_data$data, spec)
  panel <- cg_panel_audit(prepared$data, spec)
  group <- cg_scalar(spec$analysis$group, NULL)
  list(
    spec_version = cg_scalar(bundle$raw$spec_version), analysis_id = cg_scalar(spec$analysis_id),
    input = normalizePath(cg_scalar(spec$input$path), winslash = "/", mustWork = TRUE),
    input_sha256 = cg_sha256(cg_scalar(spec$input$path)),
    dimensions = list(rows = nrow(prepared$data), columns = ncol(prepared$data)),
    panel = panel, attrition = analysis_data$attrition,
    group_counts = if (is.null(group)) list(all = nrow(prepared$data)) else as.list(table(prepared$data[[group]], useNA = "ifany")),
    resolution = bundle$resolution, normalized_spec = spec,
    variables = prepared$audit
  )
}

cg_write_variant_outputs <- function(results, output_root, stem, raw_spec, spec, resolution, input_path, input_hash, panel, attrition, variable_audit) {
  if (is.null(spec$analysis$variants) || !length(spec$analysis$variants)) {
    return(list(entries = list(), paths = character()))
  }
  entries <- list()
  paths <- character()
  package_versions <- as.list(vapply(required_packages, function(pkg) as.character(utils::packageVersion(pkg)), character(1)))
  for (result in results) {
    variant_id <- result$id
    variant_stem <- paste0(stem, "__", cg_safe_id(variant_id))
    variant_paths <- c(
      display = file.path(output_root, paste0(variant_stem, "_display.csv")),
      numeric_long = file.path(output_root, paste0(variant_stem, "_numeric_long.csv")),
      objects = file.path(output_root, paste0(variant_stem, "_objects.rds")),
      metadata = file.path(output_root, paste0(variant_stem, "_metadata.json")),
      docx = file.path(output_root, paste0(variant_stem, ".docx"))
    )
    cg_write_csv(result$display, variant_paths[["display"]])
    cg_write_csv(result$numeric, variant_paths[["numeric_long"]])
    cg_write_rds(list(
      spec = raw_spec, input_spec = raw_spec, normalized_spec = spec, resolution = resolution,
      results = setNames(list(result[c("id", "label", "warning", "rows", "group_counts", "objects")]), variant_id)
    ), variant_paths[["objects"]])
    cg_render_docx(
      list(result), variant_paths[["docx"]],
      paste("Descriptive table:", cg_scalar(spec$analysis_id), "-", result$label),
      spec, cg_scalar(spec$analysis$note, NULL)
    )
    variant_docx <- cg_docx_structure(variant_paths[["docx"]])
    variant_metadata <- list(
      spec_version = cg_scalar(raw_spec$spec_version), analysis_id = cg_scalar(spec$analysis_id),
      variant_id = variant_id, generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
      input = input_path, input_sha256 = input_hash,
      rows = result$rows, group_counts = result$group_counts,
      panel = panel, attrition = attrition, variables = variable_audit,
      normalized_spec = spec, resolution = resolution,
      package_versions = package_versions,
      skill_versions = cg_skill_versions(),
      docx_structure = variant_docx,
      output_contract = list(
        stem = variant_stem, display_rows = nrow(result$display), numeric_rows = nrow(result$numeric),
        files = as.list(vapply(variant_paths, basename, character(1)))
      )
    )
    cg_write_json(variant_metadata, variant_paths[["metadata"]])
    entries[[variant_id]] <- list(
      stem = variant_stem, rows = result$rows, group_counts = result$group_counts,
      files = as.list(vapply(variant_paths, basename, character(1)))
    )
    paths <- c(paths, unname(variant_paths))
  }
  list(entries = entries, paths = paths)
}

cg_run <- function(spec_path, output_root) {
  cg_progress("preflight", "validating dependencies and table specification")
  cg_require_packages()
  bundle <- cg_read_normalized_spec(spec_path)
  raw_spec <- bundle$raw
  spec <- bundle$normalized
  output_root <- normalizePath(output_root, winslash = "/", mustWork = FALSE)
  if (dir.exists(output_root) && length(list.files(output_root, all.files = TRUE, no.. = TRUE))) cg_stop("Output root must be new or empty: %s", output_root)
  dir.create(output_root, recursive = TRUE, showWarnings = FALSE)
  stem <- cg_scalar(spec$outputs$stem)

  cg_progress("import", "reading the source data without modifying it")
  input_data <- cg_read_input(spec)
  analysis_data <- cg_prepare_analysis_data(input_data, spec)
  input_path <- normalizePath(cg_scalar(spec$input$path), winslash = "/", mustWork = TRUE)
  input_hash_before <- cg_sha256(input_path)

  cg_progress("labels", "validating variables, labels, levels, references, and panel structure")
  prepared <- cg_prepare_data(analysis_data$data, spec)
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
  sums_path <- file.path(output_root, "SHA256SUMS.txt")
  compatibility_path <- NULL

  cg_write_csv(display, display_path)
  cg_write_csv(numeric, numeric_path)
  cg_write_rds(list(
    spec = raw_spec, input_spec = raw_spec, normalized_spec = spec, resolution = bundle$resolution,
    results = lapply(results, function(x) x[c("id", "label", "warning", "rows", "group_counts", "objects")])
  ), objects_path)

  cg_progress("render", "creating a three-line DOCX with no vertical grid")
  cg_render_docx(results, docx_path, paste("Descriptive table:", cg_scalar(spec$analysis_id)), spec, cg_scalar(spec$analysis$note, NULL))
  if (cg_bool(spec$display$compatibility_export2word, FALSE)) {
    if (length(results) != 1L) cg_stop("compatibility_export2word is unavailable for multi-variant output")
    compatibility_path <- file.path(output_root, paste0(stem, "_export2word_compatibility.docx"))
    cg_export2word_compatibility(results[[1L]], compatibility_path, spec)
  }

  variant_outputs <- cg_write_variant_outputs(
    results, output_root, stem, raw_spec, spec, bundle$resolution,
    input_path, input_hash_before, panel, analysis_data$attrition, prepared$audit
  )

  docx_structure <- cg_docx_structure(docx_path)
  metadata <- list(
    spec_version = cg_scalar(raw_spec$spec_version), analysis_id = cg_scalar(spec$analysis_id),
    generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
    input = input_path, input_sha256 = input_hash_before,
    dimensions = list(rows = nrow(prepared$data), columns = ncol(prepared$data)),
    panel = panel, attrition = analysis_data$attrition, variables = prepared$audit,
    normalized_spec = spec, resolution = bundle$resolution,
    variants = lapply(results, function(x) x[c("id", "label", "warning", "rows", "group_counts")]),
    package_versions = as.list(vapply(required_packages, function(pkg) as.character(utils::packageVersion(pkg)), character(1))),
    skill_versions = cg_skill_versions(),
    statistical_tests = list(
      normal = "compareGroups method 1: t test or ANOVA as applicable",
      nonnormal = "compareGroups method 2: non-parametric rank test",
      categorical = "compareGroups method 3: categorical comparison selected by compareGroups"
    ),
    r_version = R.version.string, docx_structure = docx_structure,
    variant_outputs = variant_outputs$entries,
    output_contract = list(
      requested_formats = cg_character_vector(spec$outputs$formats),
      semantics = "delivery preferences; durable validation artifacts are always generated",
      display = basename(display_path), numeric_long = basename(numeric_path),
      objects = basename(objects_path), docx = basename(docx_path),
      display_rows = nrow(display), numeric_rows = nrow(numeric),
      variant_stems = lapply(variant_outputs$entries, `[[`, "stem")
    )
  )
  cg_write_json(metadata, metadata_path)

  cg_progress("validate", "checking input immutability and durable outputs")
  input_hash_after <- cg_sha256(input_path)
  validation <- cg_output_validation_frame(
    input_hash_before, input_hash_after, display, numeric, objects_path,
    docx_structure, spec, panel, results, variant_outputs, output_root
  )
  cg_write_csv(validation, validation_path)
  output_paths <- c(display_path, numeric_path, objects_path, metadata_path, docx_path, validation_path)
  if (!is.null(compatibility_path)) output_paths <- c(output_paths, compatibility_path)
  output_paths <- c(output_paths, variant_outputs$paths)
  manifest <- cg_manifest(output_paths, output_root)
  cg_write_csv(manifest, manifest_path)
  cg_write_text(cg_sha256_lines(c(output_paths, manifest_path), output_root), sums_path)
  if (!all(validation$passed)) cg_stop("Validation failed; inspect %s", validation_path)
  cg_progress("complete", sprintf("PASS outputs=%s", output_root))
  invisible(list(
    decision = "PASS", output_root = output_root, manifest = manifest_path,
    validation = validation_path, sha256sums = sums_path
  ))
}

cg_verify_sha256_file <- function(path, root) {
  if (!file.exists(path)) return(FALSE)
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  if (!length(lines) || any(!grepl("^[a-f0-9]{64}  .+", lines))) return(FALSE)
  relative_paths <- substring(lines, 67L)
  if (!all(cg_safe_relative_paths(relative_paths))) return(FALSE)
  all(vapply(lines, function(line) {
    expected <- substring(line, 1L, 64L)
    relative <- substring(line, 67L)
    target <- file.path(root, relative)
    file.exists(target) && identical(cg_sha256(target), expected)
  }, logical(1)))
}

cg_sha256_file_paths <- function(path) {
  if (!file.exists(path)) return(character())
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  if (!length(lines) || any(!grepl("^[a-f0-9]{64}  .+", lines))) return(character())
  substring(lines, 67L)
}

cg_validate_outputs <- function(output_root, stem) {
  cg_require_packages()
  output_root <- normalizePath(output_root, winslash = "/", mustWork = TRUE)
  manifest_path <- file.path(output_root, "manifest.csv")
  validation_path <- file.path(output_root, "validation.csv")
  sums_path <- file.path(output_root, "SHA256SUMS.txt")
  required <- c(
    paste0(stem, "_display.csv"), paste0(stem, "_numeric_long.csv"),
    paste0(stem, "_objects.rds"), paste0(stem, "_metadata.json"),
    paste0(stem, ".docx"), "validation.csv", "manifest.csv", "SHA256SUMS.txt"
  )
  missing <- required[!file.exists(file.path(output_root, required))]
  if (length(missing)) cg_stop("Missing outputs: %s", paste(missing, collapse = ", "))
  manifest <- utils::read.csv(manifest_path, check.names = FALSE, stringsAsFactors = FALSE)
  manifest_columns <- all(c("path", "bytes", "sha256") %in% names(manifest))
  manifest_paths_safe <- manifest_columns && nrow(manifest) > 0L && !anyDuplicated(manifest$path) && all(cg_safe_relative_paths(manifest$path))
  manifest_bytes_match <- manifest_paths_safe && all(vapply(seq_len(nrow(manifest)), function(index) {
    path <- file.path(output_root, manifest$path[[index]])
    expected <- suppressWarnings(as.numeric(manifest$bytes[[index]]))
    file.exists(path) && is.finite(expected) && expected >= 0 &&
      identical(expected, as.numeric(unname(file.info(path)$size)))
  }, logical(1)))
  hash_ok <- if (!manifest_paths_safe) FALSE else vapply(seq_len(nrow(manifest)), function(index) {
    path <- file.path(output_root, manifest$path[[index]])
    file.exists(path) && identical(cg_sha256(path), manifest$sha256[[index]])
  }, logical(1))
  validation <- utils::read.csv(validation_path, check.names = FALSE, stringsAsFactors = FALSE)
  required_columns <- c("check", "passed", "expected", "actual", "detail", "details")
  validation_columns <- all(required_columns %in% names(validation))
  values <- if (validation_columns && nrow(validation) > 0L) tolower(as.character(validation$passed)) %in% c("true", "t", "1") else FALSE
  docx <- cg_docx_structure(file.path(output_root, paste0(stem, ".docx")))
  sums_ok <- cg_verify_sha256_file(sums_path, output_root)
  metadata <- try(jsonlite::fromJSON(file.path(output_root, paste0(stem, "_metadata.json")), simplifyVector = FALSE), silent = TRUE)
  objects <- try(readRDS(file.path(output_root, paste0(stem, "_objects.rds"))), silent = TRUE)
  metadata_ok <- !inherits(metadata, "try-error") && cg_scalar(metadata$spec_version, "") %in% c("1.0", "1.1")
  objects_ok <- !inherits(objects, "try-error") && is.list(objects$results) && length(objects$results) > 0L
  spec_version_ok <- metadata_ok && objects_ok &&
    identical(cg_scalar(metadata$spec_version), cg_scalar(objects$input_spec$spec_version)) &&
    identical(cg_scalar(metadata$spec_version), cg_scalar(objects$normalized_spec$spec_version))
  variant_contract_ok <- FALSE
  if (metadata_ok && objects_ok && identical(names(metadata$variants), names(objects$results))) {
    metadata_contract <- lapply(metadata$variants, function(x) x[c("rows", "group_counts")])
    object_contract <- lapply(objects$results, function(x) x[c("rows", "group_counts")])
    variant_contract_ok <- identical(
      jsonlite::toJSON(metadata_contract, auto_unbox = TRUE, null = "null", digits = NA),
      jsonlite::toJSON(object_contract, auto_unbox = TRUE, null = "null", digits = NA)
    )
  }
  display <- try(utils::read.csv(file.path(output_root, paste0(stem, "_display.csv")), check.names = FALSE, stringsAsFactors = FALSE), silent = TRUE)
  numeric <- try(utils::read.csv(file.path(output_root, paste0(stem, "_numeric_long.csv")), check.names = FALSE, stringsAsFactors = FALSE), silent = TRUE)
  row_counts_ok <- metadata_ok && !inherits(display, "try-error") && !inherits(numeric, "try-error") &&
    identical(as.numeric(cg_scalar(metadata$output_contract$display_rows, NA_real_)), as.numeric(nrow(display))) &&
    identical(as.numeric(cg_scalar(metadata$output_contract$numeric_rows, NA_real_)), as.numeric(nrow(numeric)))
  variant_ids_ok <- objects_ok && !inherits(display, "try-error") && !inherits(numeric, "try-error") &&
    "variant" %in% names(display) && "variant" %in% names(numeric) &&
    identical(unique(display$variant), names(objects$results)) && identical(unique(numeric$variant), names(objects$results))
  present_files <- list.files(output_root, recursive = TRUE, all.files = FALSE, include.dirs = FALSE)
  expected_output_manifest_paths <- setdiff(present_files, c("manifest.csv", "SHA256SUMS.txt"))
  manifest_entries_complete <- manifest_paths_safe && setequal(manifest$path, expected_output_manifest_paths)
  sums_paths <- cg_sha256_file_paths(sums_path)
  sha256_entries_complete <- sums_ok && !anyDuplicated(sums_paths) && setequal(sums_paths, c(manifest$path, "manifest.csv"))
  variant_files_ok <- metadata_ok && all(vapply(metadata$variant_outputs, function(entry) {
    files <- cg_character_vector(entry$files)
    length(files) == 5L && all(cg_safe_relative_paths(files)) && all(file.exists(file.path(output_root, files)))
  }, logical(1)))
  variant_docx_ok <- metadata_ok && all(vapply(metadata$variant_outputs, function(entry) {
    cg_validate_docx(file.path(output_root, cg_scalar(entry$files$docx)))
  }, logical(1)))
  skill_version_ok <- metadata_ok && identical(cg_scalar(metadata$skill_versions$comparegroups_guide), comparegroups_guide_version)
  ok <- !length(missing) && manifest_paths_safe && manifest_bytes_match && manifest_entries_complete && validation_columns && all(hash_ok) && all(values) &&
    docx$three_line && sums_ok && sha256_entries_complete && spec_version_ok && variant_contract_ok &&
    row_counts_ok && variant_ids_ok && variant_files_ok && variant_docx_ok && skill_version_ok
  list(
    decision = if (ok) "PASS" else "FAIL", manifest_hashes = all(hash_ok), manifest_paths_safe = manifest_paths_safe,
    manifest_entries_complete = manifest_entries_complete, manifest_bytes_match = manifest_bytes_match,
    sha256_entries_complete = sha256_entries_complete,
    validations = all(values), validation_columns = validation_columns,
    metadata_spec_version = spec_version_ok, skill_version = skill_version_ok,
    variant_contract = variant_contract_ok, row_counts = row_counts_ok, variant_ids = variant_ids_ok,
    variant_files = variant_files_ok, variant_docx = variant_docx_ok,
    docx = docx, sha256sums = sums_ok
  )
}

cg_resolve_path <- function(path, base) {
  if (grepl("^(/|[A-Za-z]:[/\\\\])", path)) path else file.path(base, path)
}

cg_read_batch_manifest <- function(path) {
  if (!file.exists(path)) cg_stop("Batch manifest does not exist: %s", path)
  manifest <- jsonlite::fromJSON(path, simplifyVector = FALSE)
  unknown_top <- cg_unknown_field_errors(manifest, c("manifest_version", "batch_id", "jobs"), "batch manifest")
  if (length(unknown_top)) cg_stop("Invalid batch manifest: %s", unknown_top)
  if (!cg_is_string(manifest$manifest_version) || !identical(cg_scalar(manifest$manifest_version), "1.0")) cg_stop("Batch manifest_version must be the string 1.0")
  if (!cg_is_string(manifest$batch_id) || !grepl("^[A-Za-z0-9][A-Za-z0-9._-]*$", manifest$batch_id)) cg_stop("Batch requires a safe string batch_id")
  if (is.null(manifest$jobs) || !length(manifest$jobs)) cg_stop("Batch jobs must not be empty")
  ids <- vapply(manifest$jobs, function(job) cg_scalar(job$id, ""), character(1))
  output_dirs <- vapply(manifest$jobs, function(job) cg_scalar(job$output_dir, ""), character(1))
  if (any(!nzchar(ids)) || anyDuplicated(ids)) cg_stop("Batch job ids must be non-empty and unique")
  unknown_jobs <- unlist(lapply(manifest$jobs, cg_unknown_field_errors, allowed = c("id", "spec_path", "output_dir"), path = "batch job"), use.names = FALSE)
  if (length(unknown_jobs)) cg_stop("Invalid batch manifest: %s", paste(unknown_jobs, collapse = "; "))
  invalid_jobs <- vapply(manifest$jobs, function(job) {
    !cg_is_string(job$id) || !grepl("^[A-Za-z0-9][A-Za-z0-9._-]*$", job$id) ||
      !cg_is_string(job$spec_path) || !nzchar(job$spec_path) ||
      !cg_is_string(job$output_dir) || !nzchar(job$output_dir)
  }, logical(1))
  if (any(invalid_jobs)) cg_stop("Batch jobs require safe string ids and non-empty string spec_path/output_dir")
  if (any(!nzchar(output_dirs)) || anyDuplicated(output_dirs)) cg_stop("Batch output_dir values must be non-empty and unique")
  unsafe <- grepl("^(/|[A-Za-z]:[/\\\\])|//|\\\\\\\\", output_dirs) |
    vapply(strsplit(output_dirs, "[/\\\\]"), function(parts) any(parts %in% c("", ".", "..")), logical(1))
  if (any(unsafe)) cg_stop("Batch output_dir must be a safe relative path")
  manifest
}

cg_run_batch <- function(manifest_path, output_root) {
  cg_progress("batch_preflight", "validating batch manifest and output ownership")
  manifest <- cg_read_batch_manifest(manifest_path)
  manifest_dir <- dirname(normalizePath(manifest_path, winslash = "/", mustWork = TRUE))
  output_root <- normalizePath(output_root, winslash = "/", mustWork = FALSE)
  if (dir.exists(output_root) && length(list.files(output_root, all.files = TRUE, no.. = TRUE))) cg_stop("Batch output root must be new or empty: %s", output_root)
  dir.create(output_root, recursive = TRUE, showWarnings = FALSE)

  rows <- list()
  failed <- FALSE
  for (index in seq_along(manifest$jobs)) {
    job <- manifest$jobs[[index]]
    job_id <- cg_scalar(job$id)
    spec_path <- cg_resolve_path(cg_scalar(job$spec_path), manifest_dir)
    job_output <- file.path(output_root, cg_scalar(job$output_dir))
    cg_progress("batch_job", sprintf("running %s (%d/%d)", job_id, index, length(manifest$jobs)))
    started <- format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z")
    result <- try(cg_run(spec_path, job_output), silent = TRUE)
    ok <- !inherits(result, "try-error") && identical(result$decision, "PASS")
    message <- if (ok) "PASS" else as.character(result)
    rows[[length(rows) + 1L]] <- data.frame(
      order = index, job_id = job_id, spec_path = normalizePath(spec_path, winslash = "/", mustWork = FALSE),
      output_dir = cg_scalar(job$output_dir), status = if (ok) "PASS" else "FAIL",
      started_at = started, finished_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
      detail = message, stringsAsFactors = FALSE
    )
    if (!ok) {
      failed <- TRUE
      if (index < length(manifest$jobs)) {
        for (skipped in (index + 1L):length(manifest$jobs)) {
          pending <- manifest$jobs[[skipped]]
          rows[[length(rows) + 1L]] <- data.frame(
            order = skipped, job_id = cg_scalar(pending$id),
            spec_path = cg_resolve_path(cg_scalar(pending$spec_path), manifest_dir),
            output_dir = cg_scalar(pending$output_dir), status = "SKIPPED",
            started_at = "", finished_at = "", detail = "stopped after prior failure",
            stringsAsFactors = FALSE
          )
        }
      }
      break
    }
  }

  summary_path <- file.path(output_root, "batch_summary.csv")
  validation_path <- file.path(output_root, "batch_validation.csv")
  manifest_output_path <- file.path(output_root, "batch_manifest.csv")
  sums_path <- file.path(output_root, "SHA256SUMS.txt")
  summary <- do.call(rbind, rows)
  cg_write_csv(summary, summary_path)
  validation <- cg_validation_frame(
    check = c("all_jobs_pass", "job_order_preserved", "output_dirs_unique"),
    passed = c(!failed && all(summary$status == "PASS"), identical(summary$order, seq_len(nrow(summary))), !anyDuplicated(summary$output_dir)),
    expected = c("all PASS", paste(seq_len(nrow(summary)), collapse = ","), "unique"),
    actual = c(paste(summary$status, collapse = ","), paste(summary$order, collapse = ","), paste(summary$output_dir, collapse = ","))
  )
  cg_write_csv(validation, validation_path)
  paths <- list.files(output_root, recursive = TRUE, full.names = TRUE, all.files = FALSE)
  paths <- paths[file.info(paths)$isdir %in% FALSE]
  paths <- setdiff(paths, c(manifest_output_path, sums_path))
  batch_manifest <- cg_manifest(paths, output_root)
  cg_write_csv(batch_manifest, manifest_output_path)
  cg_write_text(cg_sha256_lines(c(paths, manifest_output_path), output_root), sums_path)
  if (failed) cg_stop("Batch failed; inspect %s", summary_path)
  cg_progress("batch_complete", sprintf("PASS jobs=%d outputs=%s", nrow(summary), output_root))
  invisible(list(decision = "PASS", output_root = output_root, summary = summary_path, validation = validation_path))
}

cg_validate_batch_outputs <- function(output_root) {
  output_root <- normalizePath(output_root, winslash = "/", mustWork = TRUE)
  required <- c("batch_summary.csv", "batch_validation.csv", "batch_manifest.csv", "SHA256SUMS.txt")
  missing <- required[!file.exists(file.path(output_root, required))]
  if (length(missing)) cg_stop("Missing batch outputs: %s", paste(missing, collapse = ", "))
  validation <- utils::read.csv(file.path(output_root, "batch_validation.csv"), stringsAsFactors = FALSE, check.names = FALSE)
  validation_columns <- all(c("check", "passed", "expected", "actual", "detail", "details") %in% names(validation))
  values <- if (validation_columns && nrow(validation) > 0L) tolower(as.character(validation$passed)) %in% c("true", "t", "1") else FALSE
  summary <- utils::read.csv(file.path(output_root, "batch_summary.csv"), stringsAsFactors = FALSE, check.names = FALSE)
  summary_ok <- all(c("order", "job_id", "output_dir", "status") %in% names(summary)) && nrow(summary) > 0L &&
    identical(summary$order, seq_len(nrow(summary))) && all(summary$status == "PASS") && !anyDuplicated(summary$output_dir)
  manifest <- utils::read.csv(file.path(output_root, "batch_manifest.csv"), stringsAsFactors = FALSE, check.names = FALSE)
  manifest_paths_safe <- all(c("path", "bytes", "sha256") %in% names(manifest)) && nrow(manifest) > 0L && !anyDuplicated(manifest$path) && all(cg_safe_relative_paths(manifest$path))
  manifest_bytes_match <- manifest_paths_safe && all(vapply(seq_len(nrow(manifest)), function(index) {
    path <- file.path(output_root, manifest$path[[index]])
    expected <- suppressWarnings(as.numeric(manifest$bytes[[index]]))
    file.exists(path) && is.finite(expected) && expected >= 0 &&
      identical(expected, as.numeric(unname(file.info(path)$size)))
  }, logical(1)))
  hashes <- if (!manifest_paths_safe) FALSE else vapply(seq_len(nrow(manifest)), function(index) {
    path <- file.path(output_root, manifest$path[[index]])
    file.exists(path) && identical(cg_sha256(path), manifest$sha256[[index]])
  }, logical(1))
  sums <- cg_verify_sha256_file(file.path(output_root, "SHA256SUMS.txt"), output_root)
  present_files <- list.files(output_root, recursive = TRUE, all.files = FALSE, include.dirs = FALSE)
  expected_manifest_paths <- setdiff(present_files, c("batch_manifest.csv", "SHA256SUMS.txt"))
  manifest_entries_complete <- manifest_paths_safe && setequal(manifest$path, expected_manifest_paths)
  sums_paths <- cg_sha256_file_paths(file.path(output_root, "SHA256SUMS.txt"))
  sha256_entries_complete <- sums && !anyDuplicated(sums_paths) && setequal(sums_paths, c(manifest$path, "batch_manifest.csv"))
  child_outputs_ok <- summary_ok && all(vapply(summary$output_dir, function(output_dir) {
    child_root <- file.path(output_root, output_dir)
    metadata_files <- list.files(child_root, pattern = "_metadata\\.json$", full.names = TRUE)
    primary_metadata <- metadata_files[vapply(metadata_files, function(path) {
      metadata <- try(jsonlite::fromJSON(path, simplifyVector = FALSE), silent = TRUE)
      !inherits(metadata, "try-error") && is.null(metadata$variant_id)
    }, logical(1))]
    if (length(primary_metadata) != 1L) return(FALSE)
    child_stem <- sub("_metadata\\.json$", "", basename(primary_metadata[[1L]]))
    child_validation <- try(cg_validate_outputs(child_root, child_stem), silent = TRUE)
    !inherits(child_validation, "try-error") && identical(child_validation$decision, "PASS")
  }, logical(1)))
  ok <- validation_columns && all(values) && summary_ok && manifest_paths_safe && manifest_bytes_match && all(hashes) && sums &&
    manifest_entries_complete && sha256_entries_complete && child_outputs_ok
  list(
    decision = if (ok) "PASS" else "FAIL", validations = all(values), validation_columns = validation_columns,
    summary = summary_ok, child_outputs = child_outputs_ok, manifest_paths_safe = manifest_paths_safe,
    manifest_bytes_match = manifest_bytes_match,
    manifest_hashes = all(hashes), manifest_entries_complete = manifest_entries_complete,
    sha256sums = sums, sha256_entries_complete = sha256_entries_complete
  )
}
