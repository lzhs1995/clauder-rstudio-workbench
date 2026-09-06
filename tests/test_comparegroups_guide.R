repo <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
common <- file.path(repo, "skills", "comparegroups-guide", "scripts", "comparegroups_common.R")
source(common)

stopifnot(length(cg_missing_packages()) == 0L)

local({
  stages <- character()
  clauder_progress <- function(stage, message = NULL, percent = NULL) {
    stages <<- c(stages, stage)
  }
  cg_progress("scope_test", "ClaudeR work-environment discovery")
  stopifnot(identical(stages, "scope_test"))
})

data(regicor, package = "compareGroups")
regicor_check <- compareGroups::compareGroups(sex ~ age + bmi + smoker, data = regicor,
                                               method = c(age = 1, bmi = 2, smoker = 3))
regicor_numeric <- compareGroups::getResults(regicor_check, "descr")
stopifnot(isTRUE(all.equal(unname(regicor_numeric["Age", "mean", "[ALL]"]),
                          mean(regicor$age, na.rm = TRUE))))

spec_path <- file.path(repo, "tests", "fixtures", "comparegroups_synthetic.table-spec.json")
spec <- cg_read_spec(spec_path)
stopifnot(cg_validate_spec(spec))
audit <- cg_audit(spec_path)
stopifnot(audit$dimensions$rows == 8L)
stopifnot(audit$panel$repeated_ids)
stopifnot(audit$panel$unique_ids == 4L)

input_hash <- cg_sha256(file.path(repo, "tests", "fixtures", "comparegroups_synthetic.csv"))
output <- tempfile("comparegroups-guide-r-test-")
result <- cg_run(spec_path, output)
stopifnot(identical(result$decision, "PASS"))
stopifnot(identical(input_hash, cg_sha256(file.path(repo, "tests", "fixtures", "comparegroups_synthetic.csv"))))
independent <- cg_validate_outputs(output, "Table_synthetic")
stopifnot(identical(independent$decision, "PASS"))
stopifnot(!cg_docx_structure(file.path(output, "Table_synthetic.docx"))$landscape)

numeric <- utils::read.csv(file.path(output, "Table_synthetic_numeric_long.csv"), check.names = FALSE)
observed <- subset(numeric, variant == "primary_wave_1" & variable == "outcome" & statistic == "mean" & group == "[ALL]")$value
stopifnot(length(observed) == 1L, isTRUE(all.equal(observed, 12.825)))
observed_n <- subset(numeric, variant == "primary_wave_1" & variable == "outcome" & statistic == "n_available" & group == "[ALL]")$value
stopifnot(length(observed_n) == 1L, identical(observed_n, 4))

# v1.1：默认值、分组标签、variants、自动 attrition 与 DOCX 设置。
panel_data <- rbind(
  data.frame(person_id = 1:8, wave = 1, treatment = rep(c(0, 1), 4),
             sex = rep(c(1, 2), 4), age = 30:37,
             answer = rep(c("No", "Yes"), 4), stringsAsFactors = FALSE),
  data.frame(person_id = 1:5, wave = 2, treatment = c(0, 1, 0, 1, 0),
             sex = c(1, 2, 1, 2, 1), age = 31:35,
             answer = c("No", "Yes", "Yes", "No", "Yes"), stringsAsFactors = FALSE)
)
panel_path <- tempfile(fileext = ".csv")
utils::write.csv(panel_data, panel_path, row.names = FALSE)

base_v11 <- list(
  spec_version = "1.1", analysis_id = "v11-test",
  input = list(path = panel_path, format = "csv", id = "person_id", time = "wave"),
  defaults = list(continuous_digits = 4L, categorical_digits = 1L, p_digits = 2L, include_missing = TRUE),
  analysis = list(
    group = "treatment", panel_mode = "dual", subset = NULL, note = NULL,
    group_reference = "Control",
    group_levels = list(list(value = 0, label = "Control"), list(value = 1, label = "Treatment")),
    variants = list(
      list(id = "first", label = "First subset", subset = "person_id <= 5"),
      list(id = "second", label = "Second subset", subset = "person_id >= 3")
    )
  ),
  blocks = list(list(
    id = "baseline", label = "Baseline",
    variables = list(
      list(name = "age", type = "continuous", method = "normal", label = "Age", reference = NULL, levels = NULL),
      list(name = "answer", type = "categorical", method = "categorical", label = "Answer", reference = "No",
           levels = list(list(value = "No", label = "No"), list(value = "Yes", label = "Yes")))
    )
  )),
  display = list(
    show_all = TRUE, show_n = TRUE, show_p_overall = TRUE,
    show_p_multiple = FALSE, show_p_trend = FALSE, hide_no = "No",
    compatibility_export2word = FALSE,
    docx = list(font_family = "Arial", font_size = 9, orientation = "landscape",
                repeat_header = TRUE, title = "V1.1 test", footnote = "Verified footnote",
                column_widths = list(2.5, 1, 1, 1, 1, 1))
  ),
  outputs = list(stem = "Table_v11", formats = list("docx", "csv", "rds"))
)
raw_v11_path <- tempfile(fileext = ".json")
jsonlite::write_json(base_v11, raw_v11_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
bundle <- cg_read_normalized_spec(raw_v11_path)
stopifnot(bundle$normalized$blocks[[1]]$variables[[1]]$digits == 4L)
stopifnot(bundle$normalized$blocks[[1]]$variables[[2]]$digits == 1L)
stopifnot(bundle$normalized$display$p_digits == 2L)
stopifnot(identical(bundle$resolution$variables$age$digits_source, "defaults"))
prepared_v11 <- cg_prepare_data(panel_data, bundle$normalized)
stopifnot(identical(levels(prepared_v11$data$treatment), c("Control", "Treatment")))

v11_output <- tempfile("comparegroups-v11-")
v11_result <- cg_run(raw_v11_path, v11_output)
stopifnot(identical(v11_result$decision, "PASS"))
v11_metadata <- jsonlite::fromJSON(file.path(v11_output, "Table_v11_metadata.json"), simplifyVector = FALSE)
v11_ids <- names(v11_metadata$variants)
stopifnot(identical(v11_ids, c(
  "first__primary_wave_1", "first__primary_wave_2", "first__compatibility_pooled",
  "second__primary_wave_1", "second__primary_wave_2", "second__compatibility_pooled"
)))
variant_files <- unlist(lapply(v11_metadata$variant_outputs, function(entry) cg_character_vector(entry$files)), use.names = FALSE)
stopifnot(length(variant_files) == 30L, all(file.exists(file.path(v11_output, variant_files))))
stopifnot(all(grepl("^Table_v11__", vapply(v11_metadata$variant_outputs, function(entry) cg_scalar(entry$stem), character(1)))))
stopifnot(identical(cg_scalar(v11_metadata$skill_versions$comparegroups_guide), "0.6.1"))
stopifnot(isTRUE(cg_docx_structure(file.path(v11_output, "Table_v11.docx"))$landscape))
v11_display <- utils::read.csv(file.path(v11_output, "Table_v11_display.csv"), check.names = FALSE)
stopifnot(!any(grepl("No", v11_display$row_label, fixed = TRUE)))
v11_objects <- readRDS(file.path(v11_output, "Table_v11_objects.rds"))
first_table <- v11_objects$results$first__primary_wave_1$objects$baseline$parts$part_1$createTable
stopifnot(identical(attr(first_table, "hide.no", exact = TRUE), "No"))
docx_unpack <- tempfile("comparegroups-v11-docx-")
dir.create(docx_unpack)
docx_xml_path <- utils::unzip(file.path(v11_output, "Table_v11.docx"), files = "word/document.xml", exdir = docx_unpack)
docx_xml <- paste(readLines(docx_xml_path, warn = FALSE, encoding = "UTF-8"), collapse = "")
stopifnot(grepl("Arial", docx_xml, fixed = TRUE))
stopifnot(grepl("<w:sz w:val=\"18\"", docx_xml, fixed = TRUE))
stopifnot(grepl("<w:gridCol w:w=\"3600\"", docx_xml, fixed = TRUE))
stopifnot(grepl("V1.1 test", docx_xml, fixed = TRUE))
stopifnot(grepl("Verified footnote", docx_xml, fixed = TRUE))
stopifnot(grepl("<w:tblHeader", docx_xml, fixed = TRUE))
v11_validation <- utils::read.csv(file.path(v11_output, "validation.csv"), check.names = FALSE)
stopifnot(all(c("check", "passed", "expected", "actual", "detail", "details") %in% names(v11_validation)))
stopifnot(file.exists(file.path(v11_output, "SHA256SUMS.txt")))

# 生产 validation 生成器的七类真实失败必须分别落出准确诊断。
v11_numeric <- utils::read.csv(file.path(v11_output, "Table_v11_numeric_long.csv"), check.names = FALSE)
v11_docx_structure <- cg_docx_structure(file.path(v11_output, "Table_v11.docx"))
v11_variant_paths <- file.path(v11_output, unlist(lapply(
  v11_metadata$variant_outputs, function(entry) cg_character_vector(entry$files)
), use.names = FALSE))
validation_context <- list(
  input_hash_before = cg_scalar(v11_metadata$input_sha256),
  input_hash_after = cg_scalar(v11_metadata$input_sha256),
  display = v11_display, numeric = v11_numeric,
  objects_path = file.path(v11_output, "Table_v11_objects.rds"),
  docx_structure = v11_docx_structure, spec = v11_objects$normalized_spec,
  panel = v11_metadata$panel, results = v11_objects$results,
  variant_outputs = list(entries = v11_metadata$variant_outputs, paths = v11_variant_paths),
  output_root = v11_output
)
failure_cases <- list(
  list(check = "input_hash_unchanged", expected = cg_scalar(v11_metadata$input_sha256), actual = "tampered-hash", change = function(x) { x$input_hash_after <- "tampered-hash"; x }),
  list(check = "display_nonempty", expected = ">0", actual = "0", change = function(x) { x$display <- x$display[0, , drop = FALSE]; x }),
  list(check = "numeric_nonempty", expected = ">0", actual = "0", change = function(x) { x$numeric <- x$numeric[0, , drop = FALSE]; x }),
  list(check = "objects_reload", expected = "readable RDS", actual = "missing_objects.rds", change = function(x) { x$objects_path <- file.path(x$output_root, "missing_objects.rds"); x }),
  list(check = "docx_reopens", expected = "valid DOCX", actual = "FALSE", change = function(x) { x$docx_structure$reopens <- FALSE; x }),
  list(check = "docx_true_three_line", expected = "each table has exactly top/header-bottom/final-bottom", actual = "three_line=FALSE", change = function(x) { x$docx_structure$three_line <- FALSE; x$docx_structure$top <- 0L; x }),
  list(check = "docx_no_vertical_grid", expected = "0", actual = "1", change = function(x) { x$docx_structure$vertical <- 1L; x$docx_structure$three_line <- FALSE; x })
)
diagnostic_root <- tempfile("comparegroups-failure-diagnostics-")
dir.create(diagnostic_root)
for (failure in failure_cases) {
  diagnostic <- do.call(cg_output_validation_frame, failure$change(validation_context))
  diagnostic_path <- file.path(diagnostic_root, paste0(failure$check, ".csv"))
  cg_write_csv(diagnostic, diagnostic_path)
  persisted <- utils::read.csv(diagnostic_path, check.names = FALSE, stringsAsFactors = FALSE)
  row <- persisted[persisted$check == failure$check, , drop = FALSE]
  stopifnot(
    nrow(row) == 1L, !isTRUE(row$passed[[1L]]), nzchar(row$detail[[1L]]),
    identical(row$detail[[1L]], sprintf("expected=%s; actual=%s", row$expected[[1L]], row$actual[[1L]])),
    grepl(failure$expected, row$expected[[1L]], fixed = TRUE),
    grepl(failure$actual, row$actual[[1L]], fixed = TRUE)
  )
}

attrition_spec <- base_v11
attrition_spec$analysis_id <- "attrition-test"
attrition_spec$analysis <- list(
  group = NULL, panel_mode = "cross_section", subset = NULL, note = NULL,
  group_reference = "Deleted", group_levels = NULL,
  attrition = list(
    baseline_values = list(1), followup_values = list(2), group_name = "retention_status",
    retained_label = "Retained", deleted_label = "Deleted"
  )
)
attrition_spec$outputs$stem <- "Table_attrition"
attrition_spec$display$docx$orientation <- "portrait"
attrition_spec$display$docx$column_widths <- NULL
attrition_path <- tempfile(fileext = ".json")
jsonlite::write_json(attrition_spec, attrition_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
attrition_output <- tempfile("comparegroups-attrition-")
attrition_result <- cg_run(attrition_path, attrition_output)
stopifnot(identical(attrition_result$decision, "PASS"))
attrition_metadata <- jsonlite::fromJSON(file.path(attrition_output, "Table_attrition_metadata.json"), simplifyVector = FALSE)
stopifnot(attrition_metadata$attrition$baseline_rows == 8L)
stopifnot(attrition_metadata$attrition$retained == 5L)
stopifnot(attrition_metadata$attrition$deleted == 3L)
stopifnot(identical(cg_validate_outputs(attrition_output, "Table_attrition")$decision, "PASS"))
stopifnot(!cg_docx_structure(file.path(attrition_output, "Table_attrition.docx"))$landscape)

duplicate_data <- rbind(panel_data, panel_data[1, ])
duplicate_path <- tempfile(fileext = ".csv")
utils::write.csv(duplicate_data, duplicate_path, row.names = FALSE)
duplicate_spec <- attrition_spec
duplicate_spec$input$path <- duplicate_path
duplicate_spec_path <- tempfile(fileext = ".json")
jsonlite::write_json(duplicate_spec, duplicate_spec_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
duplicate_error <- try(cg_audit(duplicate_spec_path), silent = TRUE)
stopifnot(inherits(duplicate_error, "try-error"), grepl("exactly one baseline row", as.character(duplicate_error), fixed = TRUE))

followup_only_data <- rbind(panel_data, data.frame(
  person_id = 99, wave = 2, treatment = 0, sex = 1, age = 40, answer = "No"
))
followup_only_path <- tempfile(fileext = ".csv")
utils::write.csv(followup_only_data, followup_only_path, row.names = FALSE)
followup_only_spec <- attrition_spec
followup_only_spec$input$path <- followup_only_path
followup_only_spec_path <- tempfile(fileext = ".json")
jsonlite::write_json(followup_only_spec, followup_only_spec_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
followup_only_error <- try(cg_audit(followup_only_spec_path), silent = TRUE)
stopifnot(inherits(followup_only_error, "try-error"), grepl("ids without baseline", as.character(followup_only_error), fixed = TRUE))

empty_group_spec <- base_v11
empty_group_spec$analysis$group_levels <- c(
  empty_group_spec$analysis$group_levels,
  list(list(value = 2, label = "Unobserved"))
)
empty_group_path <- tempfile(fileext = ".json")
jsonlite::write_json(empty_group_spec, empty_group_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
empty_group_error <- try(cg_audit(empty_group_path), silent = TRUE)
stopifnot(inherits(empty_group_error, "try-error"), grepl("no observations", as.character(empty_group_error), fixed = TRUE))

# 总样本三组均存在时，variant 删除声明组仍必须硬阻断。
variant_group_spec <- bundle$normalized
variant_group_spec$analysis$panel_mode <- "cross_section"
variant_group_spec$analysis$group_levels <- c(
  variant_group_spec$analysis$group_levels,
  list(list(value = 2, label = "Third"))
)
variant_group_spec$analysis$variants <- list(list(id = "drop_third", label = "Drop third", subset = "treatment != 'Third'"))
variant_group_data <- rbind(panel_data, data.frame(
  person_id = 100, wave = 1, treatment = 2, sex = 1, age = 40,
  answer = "No", stringsAsFactors = FALSE
))
variant_group_prepared <- cg_prepare_data(variant_group_data, variant_group_spec)
variant_group_error <- try(cg_variants(variant_group_prepared$data, variant_group_spec), silent = TRUE)
stopifnot(
  inherits(variant_group_error, "try-error"),
  grepl("Variant drop_third", as.character(variant_group_error), fixed = TRUE),
  grepl("Third", as.character(variant_group_error), fixed = TRUE)
)

fractional_spec <- base_v11
fractional_spec$defaults$continuous_digits <- 2.5
fractional_path <- tempfile(fileext = ".json")
jsonlite::write_json(fractional_spec, fractional_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
fractional_error <- try(cg_audit(fractional_path), silent = TRUE)
stopifnot(inherits(fractional_error, "try-error"), grepl("must be an integer", as.character(fractional_error), fixed = TRUE))

unknown_spec <- base_v11
unknown_spec$analysis$unexpected_typo <- TRUE
unknown_path <- tempfile(fileext = ".json")
jsonlite::write_json(unknown_spec, unknown_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
unknown_error <- try(cg_audit(unknown_path), silent = TRUE)
stopifnot(inherits(unknown_error, "try-error"), grepl("unknown analysis fields", as.character(unknown_error), fixed = TRUE))

# 1.0 保持 v0.5.0 的无标签数值分组行为。
v10_numeric_group <- cg_read_spec(spec_path)
v10_numeric_group$analysis$group <- "person_id"
v10_numeric_group$analysis$panel_mode <- "cross_section"
v10_numeric_group$analysis$subset <- "wave == 1"
v10_numeric_group_path <- tempfile(fileext = ".json")
jsonlite::write_json(v10_numeric_group, v10_numeric_group_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
v10_numeric_audit <- cg_audit(v10_numeric_group_path)
stopifnot(length(v10_numeric_audit$group_counts) == 4L)

# batch 保留声明顺序、独立输出目录与顶层哈希。
batch_spec_2 <- attrition_spec
batch_spec_2$analysis_id <- "attrition-test-2"
batch_spec_2$outputs$stem <- "Table__attrition_2"
batch_spec_2_path <- tempfile(fileext = ".json")
jsonlite::write_json(batch_spec_2, batch_spec_2_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
batch_manifest <- list(
  manifest_version = "1.0", batch_id = "batch-test",
  jobs = list(
    list(id = "one", spec_path = attrition_path, output_dir = "01_one"),
    list(id = "two", spec_path = batch_spec_2_path, output_dir = "02_two")
  )
)
batch_path <- tempfile(fileext = ".json")
jsonlite::write_json(batch_manifest, batch_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
batch_output <- tempfile("comparegroups-batch-")
batch_result <- cg_run_batch(batch_path, batch_output)
stopifnot(identical(batch_result$decision, "PASS"))
stopifnot(identical(cg_validate_batch_outputs(batch_output)$decision, "PASS"))
batch_summary <- utils::read.csv(file.path(batch_output, "batch_summary.csv"), stringsAsFactors = FALSE)
stopifnot(identical(batch_summary$job_id, c("one", "two")), all(batch_summary$status == "PASS"))

batch_manifest_path <- file.path(batch_output, "batch_manifest.csv")
batch_sums_path <- file.path(batch_output, "SHA256SUMS.txt")
batch_manifest_original <- utils::read.csv(batch_manifest_path, check.names = FALSE, stringsAsFactors = FALSE)
batch_manifest_tampered <- batch_manifest_original
batch_manifest_tampered$bytes[[1L]] <- batch_manifest_tampered$bytes[[1L]] + 1
utils::write.csv(batch_manifest_tampered, batch_manifest_path, row.names = FALSE, fileEncoding = "UTF-8")
writeLines(cg_sha256_lines(c(file.path(batch_output, batch_manifest_tampered$path), batch_manifest_path), batch_output), batch_sums_path)
batch_bytes_validation <- cg_validate_batch_outputs(batch_output)
stopifnot(identical(batch_bytes_validation$decision, "FAIL"), !batch_bytes_validation$manifest_bytes_match)
utils::write.csv(batch_manifest_original, batch_manifest_path, row.names = FALSE, fileEncoding = "UTF-8")
writeLines(cg_sha256_lines(c(file.path(batch_output, batch_manifest_original$path), batch_manifest_path), batch_output), batch_sums_path)
stopifnot(identical(cg_validate_batch_outputs(batch_output)$decision, "PASS"))

occupied_batch <- tempfile("comparegroups-batch-occupied-")
dir.create(occupied_batch)
writeLines("occupied", file.path(occupied_batch, "existing.txt"))
occupied_error <- try(cg_run_batch(batch_path, occupied_batch), silent = TRUE)
stopifnot(inherits(occupied_error, "try-error"), grepl("must be new or empty", as.character(occupied_error), fixed = TRUE))

# 即使攻击者重算哈希，错误 bytes 或删掉 manifest 条目也必须由独立门禁检出。
v11_manifest_path <- file.path(v11_output, "manifest.csv")
v11_sums_path <- file.path(v11_output, "SHA256SUMS.txt")
v11_manifest_original <- utils::read.csv(v11_manifest_path, check.names = FALSE, stringsAsFactors = FALSE)
v11_manifest <- v11_manifest_original
v11_manifest$bytes[[1L]] <- v11_manifest$bytes[[1L]] + 1
utils::write.csv(v11_manifest, v11_manifest_path, row.names = FALSE, fileEncoding = "UTF-8")
writeLines(cg_sha256_lines(c(file.path(v11_output, v11_manifest$path), v11_manifest_path), v11_output), v11_sums_path)
tampered_bytes_validation <- cg_validate_outputs(v11_output, "Table_v11")
stopifnot(identical(tampered_bytes_validation$decision, "FAIL"), !tampered_bytes_validation$manifest_bytes_match)
utils::write.csv(v11_manifest_original, v11_manifest_path, row.names = FALSE, fileEncoding = "UTF-8")
writeLines(cg_sha256_lines(c(file.path(v11_output, v11_manifest_original$path), v11_manifest_path), v11_output), v11_sums_path)

v11_manifest <- v11_manifest_original[-1L, , drop = FALSE]
utils::write.csv(v11_manifest, v11_manifest_path, row.names = FALSE, fileEncoding = "UTF-8")
writeLines(cg_sha256_lines(c(file.path(v11_output, v11_manifest$path), v11_manifest_path), v11_output), v11_sums_path)
tampered_validation <- cg_validate_outputs(v11_output, "Table_v11")
stopifnot(identical(tampered_validation$decision, "FAIL"), !tampered_validation$manifest_entries_complete)

cat("COMPAREGROUPS_R_TESTS_OK\n")
