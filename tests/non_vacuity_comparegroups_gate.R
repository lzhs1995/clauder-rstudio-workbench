args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 1L)
source(normalizePath(args[[1L]], mustWork = TRUE))

# 重复基期必须阻断。
duplicate_data <- data.frame(
  id = c(1, 1, 2, 3, 1, 2), wave = c(1, 1, 1, 1, 2, 2), value = 1:6
)
attrition_spec <- list(
  input = list(id = "id", time = "wave"),
  analysis = list(attrition = list(
    baseline_values = list(1), followup_values = list(2),
    group_name = "retention_status", retained_label = "Retained", deleted_label = "Deleted"
  ))
)
duplicate_error <- try(cg_apply_attrition(duplicate_data, attrition_spec), silent = TRUE)
stopifnot(inherits(duplicate_error, "try-error"))

# 仅随访出现、没有基期行的 ID 也必须阻断。
followup_only_data <- data.frame(
  id = c(1, 2, 3, 1, 2, 99), wave = c(1, 1, 1, 2, 2, 2), value = 1:6
)
followup_only_error <- try(cg_apply_attrition(followup_only_data, attrition_spec), silent = TRUE)
stopifnot(inherits(followup_only_error, "try-error"))

# batch 输出目录不得逃逸 output root。
unsafe_manifest <- tempfile(fileext = ".json")
jsonlite::write_json(
  list(
    manifest_version = "1.0", batch_id = "unsafe",
    jobs = list(list(id = "escape", spec_path = "spec.json", output_dir = "../escape"))
  ),
  unsafe_manifest, auto_unbox = TRUE
)
unsafe_error <- try(cg_read_batch_manifest(unsafe_manifest), silent = TRUE)
stopifnot(inherits(unsafe_error, "try-error"))

fixture_spec_path <- file.path(getwd(), "tests", "fixtures", "comparegroups_synthetic.table-spec.json")
fixture <- cg_read_spec(fixture_spec_path)

# 1.0 数值分组必须保持 v0.5.0 的 factor() 兼容行为。
numeric_group_spec <- fixture
numeric_group_spec$analysis$group <- "person_id"
numeric_group_spec$analysis$panel_mode <- "cross_section"
numeric_group_spec$analysis$subset <- "wave == 1"
numeric_group_path <- tempfile(fileext = ".json")
jsonlite::write_json(numeric_group_spec, numeric_group_path, auto_unbox = TRUE, null = "null")
stopifnot(length(cg_audit(numeric_group_path)$group_counts) == 4L)

# 1.1 严格类型、未知字段和声明空组必须阻断。
strict_spec <- fixture
strict_spec$spec_version <- "1.1"
strict_spec$defaults <- list(continuous_digits = 2.5)
fractional_error <- try(cg_validate_spec(strict_spec), silent = TRUE)
stopifnot(inherits(fractional_error, "try-error"))
strict_spec$defaults$continuous_digits <- 3L
strict_spec$analysis$unexpected_typo <- TRUE
unknown_error <- try(cg_validate_spec(strict_spec), silent = TRUE)
stopifnot(inherits(unknown_error, "try-error"))
strict_spec$analysis$unexpected_typo <- NULL
strict_spec$analysis$group_levels <- list(
  list(value = "A", label = "A"), list(value = "B", label = "B"),
  list(value = "C", label = "Unobserved")
)
empty_group_path <- tempfile(fileext = ".json")
jsonlite::write_json(strict_spec, empty_group_path, auto_unbox = TRUE, null = "null")
empty_group_error <- try(cg_audit(empty_group_path), silent = TRUE)
stopifnot(inherits(empty_group_error, "try-error"))

# variant 过滤掉一个声明组时，即使仍有两组也必须阻断。
variant_group_data <- data.frame(group = factor(c("A", "B"), levels = c("A", "B", "C")))
variant_group_spec <- list(analysis = list(
  group = "group",
  group_levels = list(
    list(value = "A", label = "A"), list(value = "B", label = "B"),
    list(value = "C", label = "C")
  )
))
variant_group_error <- try(cg_validate_variant_data(variant_group_data, variant_group_spec, "drop_c"), silent = TRUE)
stopifnot(inherits(variant_group_error, "try-error"), grepl("C", as.character(variant_group_error), fixed = TRUE))

# 有竖线的 OOXML 即使能打开也不得通过真三线门禁。
invalid_docx <- tempfile(fileext = ".docx")
ft <- flextable::flextable(data.frame(a = 1:2, b = 3:4))
line <- officer::fp_border(color = "black", width = 1.25)
ft <- flextable::border_remove(ft)
ft <- flextable::border_outer(ft, border = line, part = "all")
ft <- flextable::hline_bottom(ft, border = line, part = "header")
doc <- officer::read_docx()
doc <- flextable::body_add_flextable(doc, ft)
print(doc, target = invalid_docx)
structure <- cg_docx_structure(invalid_docx)
stopifnot(structure$reopens, structure$vertical > 0L, !cg_validate_docx(invalid_docx))

# 额外内部横线也不得通过逐表真三线校验。
extra_line_docx <- tempfile(fileext = ".docx")
ft <- flextable::flextable(data.frame(a = 1:3, b = 4:6))
ft <- flextable::border_remove(ft)
ft <- flextable::hline_top(ft, border = line, part = "header")
ft <- flextable::hline_bottom(ft, border = line, part = "header")
ft <- flextable::hline_bottom(ft, border = line, part = "body")
ft <- flextable::hline(ft, i = 1L, border = line, part = "body")
doc <- officer::read_docx()
doc <- flextable::body_add_flextable(doc, ft)
print(doc, target = extra_line_docx)
stopifnot(!cg_validate_docx(extra_line_docx))

# variants 必须生成带确定性 stem 后缀的独立文件，metadata 必须携带 skill 版本。
variant_spec <- fixture
variant_spec$spec_version <- "1.1"
variant_spec$analysis$variants <- list(list(id = "subset_a", label = "Subset A", subset = "person_id <= 4"))
variant_path <- tempfile(fileext = ".json")
jsonlite::write_json(variant_spec, variant_path, auto_unbox = TRUE, null = "null")
variant_output <- tempfile("comparegroups-non-vacuity-output-")
stopifnot(identical(cg_run(variant_path, variant_output)$decision, "PASS"))
metadata <- jsonlite::fromJSON(file.path(variant_output, "Table_synthetic_metadata.json"), simplifyVector = FALSE)
variant_files <- unlist(lapply(metadata$variant_outputs, function(entry) cg_character_vector(entry$files)), use.names = FALSE)
stopifnot(length(variant_files) == 15L, all(file.exists(file.path(variant_output, variant_files))))
stopifnot(identical(cg_scalar(metadata$skill_versions$comparegroups_guide), "0.6.1"))
stopifnot(identical(cg_validate_outputs(variant_output, "Table_synthetic")$decision, "PASS"))

# 同一生产函数对七类真实失败生成可定位的 validation.csv 行。
objects <- readRDS(file.path(variant_output, "Table_synthetic_objects.rds"))
display <- utils::read.csv(file.path(variant_output, "Table_synthetic_display.csv"), check.names = FALSE)
numeric <- utils::read.csv(file.path(variant_output, "Table_synthetic_numeric_long.csv"), check.names = FALSE)
variant_paths <- file.path(variant_output, variant_files)
context <- list(
  input_hash_before = cg_scalar(metadata$input_sha256), input_hash_after = cg_scalar(metadata$input_sha256),
  display = display, numeric = numeric,
  objects_path = file.path(variant_output, "Table_synthetic_objects.rds"),
  docx_structure = cg_docx_structure(file.path(variant_output, "Table_synthetic.docx")),
  spec = objects$normalized_spec, panel = metadata$panel, results = objects$results,
  variant_outputs = list(entries = metadata$variant_outputs, paths = variant_paths),
  output_root = variant_output
)
failures <- list(
  list(check = "input_hash_unchanged", change = function(x) { x$input_hash_after <- "changed"; x }),
  list(check = "display_nonempty", change = function(x) { x$display <- x$display[0, , drop = FALSE]; x }),
  list(check = "numeric_nonempty", change = function(x) { x$numeric <- x$numeric[0, , drop = FALSE]; x }),
  list(check = "objects_reload", change = function(x) { x$objects_path <- file.path(x$output_root, "missing.rds"); x }),
  list(check = "docx_reopens", change = function(x) { x$docx_structure$reopens <- FALSE; x }),
  list(check = "docx_true_three_line", change = function(x) { x$docx_structure$three_line <- FALSE; x$docx_structure$top <- 0L; x }),
  list(check = "docx_no_vertical_grid", change = function(x) { x$docx_structure$vertical <- 1L; x$docx_structure$three_line <- FALSE; x })
)
diagnostic_root <- tempfile("comparegroups-non-vacuity-diagnostics-")
dir.create(diagnostic_root)
for (failure in failures) {
  diagnostic <- do.call(cg_output_validation_frame, failure$change(context))
  diagnostic_path <- file.path(diagnostic_root, paste0(failure$check, ".csv"))
  cg_write_csv(diagnostic, diagnostic_path)
  persisted <- utils::read.csv(diagnostic_path, check.names = FALSE, stringsAsFactors = FALSE)
  row <- persisted[persisted$check == failure$check, , drop = FALSE]
  stopifnot(
    nrow(row) == 1L, !isTRUE(row$passed[[1L]]), nzchar(row$detail[[1L]]),
    identical(row$detail[[1L]], sprintf("expected=%s; actual=%s", row$expected[[1L]], row$actual[[1L]]))
  )
}

# manifest bytes 错误或少一个条目后，即使重算 SHA-256 也必须失败。
manifest_path <- file.path(variant_output, "manifest.csv")
manifest_original <- utils::read.csv(manifest_path, check.names = FALSE, stringsAsFactors = FALSE)
sums_path <- file.path(variant_output, "SHA256SUMS.txt")
manifest <- manifest_original
manifest$bytes[[1L]] <- manifest$bytes[[1L]] + 1
utils::write.csv(manifest, manifest_path, row.names = FALSE, fileEncoding = "UTF-8")
writeLines(cg_sha256_lines(c(file.path(variant_output, manifest$path), manifest_path), variant_output), sums_path)
tampered_bytes <- cg_validate_outputs(variant_output, "Table_synthetic")
stopifnot(identical(tampered_bytes$decision, "FAIL"), !tampered_bytes$manifest_bytes_match)

manifest <- manifest_original[-1L, , drop = FALSE]
utils::write.csv(manifest, manifest_path, row.names = FALSE, fileEncoding = "UTF-8")
writeLines(
  cg_sha256_lines(c(file.path(variant_output, manifest$path), manifest_path), variant_output),
  sums_path
)
tampered <- cg_validate_outputs(variant_output, "Table_synthetic")
stopifnot(identical(tampered$decision, "FAIL"), !tampered$manifest_entries_complete)

cat("COMPAREGROUPS_NON_VACUITY_GATE_OK\n")
