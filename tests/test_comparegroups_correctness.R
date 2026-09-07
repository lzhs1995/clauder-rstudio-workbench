args <- commandArgs(trailingOnly = TRUE)
source(if (length(args)) args[[1L]] else "skills/comparegroups-guide/scripts/comparegroups_common.R")
cg_require_packages()
checks <- logical()
check <- function(name, value) {
  checks[[name]] <<- isTRUE(value)
  cat(sprintf("CORRECTNESS %s %s\n", name, if (isTRUE(value)) "PASS" else "FAIL"))
}
rejects <- function(expr, pattern) {
  result <- tryCatch(force(expr), error = identity)
  if (inherits(result, "error") && !grepl(pattern, conditionMessage(result), fixed = TRUE)) {
    cat("UNEXPECTED_REJECTION", conditionMessage(result), "\n")
  }
  inherits(result, "error") && grepl(pattern, conditionMessage(result), fixed = TRUE)
}
rejects_pipeline <- function(data, spec, pattern) {
  input_path <- tempfile(fileext = ".csv")
  utils::write.csv(data, input_path, row.names = FALSE)
  full_spec <- cg_read_spec("tests/fixtures/comparegroups_synthetic.table-spec.json")
  full_spec$spec_version <- "1.1"
  full_spec$input <- c(list(path = input_path, format = "csv"), spec$input)
  full_spec$analysis <- spec$analysis
  full_spec$analysis["subset"] <- list(NULL)
  full_spec$blocks <- list(list(id = "b", label = "Block", variables = list(list(
    name = "x", type = "continuous", method = "normal", digits = 3L,
    label = "X", include_missing = FALSE, reference = NULL, levels = NULL
  ))))
  spec_path <- tempfile(fileext = ".json")
  cg_write_json(full_spec, spec_path)
  rejects(cg_run(spec_path, tempfile("comparegroups-invalid-pipeline-")), pattern)
}

data(regicor, package = "compareGroups")
regicor$bmi <- regicor$age + 100
attr(regicor$age, "label") <- "Same"
attr(regicor$bmi, "label") <- "Same"
model <- compareGroups::compareGroups(sex ~ age + bmi + smoker, data = regicor,
                                     method = c(age = 1, bmi = 1, smoker = 3))
table <- compareGroups::createTable(model)
numeric <- cg_numeric_frame(model, table, "b", "primary")
check("count_groups_are_real", setequal(unique(numeric$group[numeric$statistic == "n_available"]),
                                       c("[ALL]", "Male", "Female")))
for (variable in c("age", "bmi")) {
  observed <- numeric$value[numeric$variable == variable & numeric$statistic == "mean" & numeric$group == "[ALL]"]
  check(paste0("duplicate_label_", variable), length(observed) == 1L &&
          isTRUE(all.equal(observed, mean(regicor[[variable]], na.rm = TRUE))))
}
ungrouped <- compareGroups::compareGroups(~ age + smoker, data = regicor, method = c(age = 1, smoker = 3))
ungrouped_numeric <- try(cg_numeric_frame(ungrouped, compareGroups::createTable(ungrouped), "b", "primary", FALSE), silent = TRUE)
check("ungrouped_numeric", !inherits(ungrouped_numeric, "try-error") &&
        identical(unique(ungrouped_numeric$group), "[ALL]"))

panel <- expand.grid(id = 1:60, wave = 1:2)
panel$g <- factor(rep(rep(c("A", "B", "C"), each = 20), 2))
panel$x <- panel$id + panel$wave / 10
spec <- list(input = list(id = "id", time = "wave"), analysis = list(group = "g", panel_mode = "dual",
  group_levels = lapply(c("A", "B", "C"), function(x) list(value = x, label = x))))
check("automatic_empty_group", rejects_pipeline(panel[!(panel$wave == 2 & panel$g == "C"), ], spec,
                                       "declared grouping levels with no observations"))
check("duplicate_id_time", rejects_pipeline(rbind(panel, panel), spec, "Duplicate id/time"))
missing_id <- panel
missing_id$id[[1L]] <- NA
check("missing_id", rejects_pipeline(missing_id, spec, "Missing id"))
missing_time <- panel
missing_time$wave[[1L]] <- NA
check("missing_time", rejects_pipeline(missing_time, spec, "Missing time"))
cross_spec <- spec
cross_spec$analysis$panel_mode <- "cross_section"
check("cross_section_repeated_ids", rejects_pipeline(panel, cross_spec, "cross_section requires independent"))
pooled_spec <- spec
pooled_spec$analysis$panel_mode <- "pooled_compatibility"
pooled <- cg_variants(panel, pooled_spec)
check("pooled_warning", identical(pooled[[1L]]$id, "compatibility_pooled") && nzchar(pooled[[1L]]$warning))
collision <- panel
collision$wave <- ifelse(collision$wave == 1, "a b", "a/b")
check("automatic_id_collision", rejects_pipeline(collision, spec, "Resolved variant ids must be unique"))

fixture <- cg_read_spec("tests/fixtures/comparegroups_synthetic.table-spec.json")
fixture$spec_version <- "1.1"
fixture$blocks[[1L]]$variables[[1L]]$label <- "Same"
fixture$blocks[[1L]]$variables[[2L]]$label <- "Same"
fixture$analysis$variants <- list(list(id = "all", label = "All", subset = NULL))
spec_path <- tempfile(fileext = ".json")
cg_write_json(fixture, spec_path)
output <- tempfile("comparegroups-correctness-")
cg_run(spec_path, output)
stem <- "Table_synthetic"
validated <- cg_validate_outputs(output, stem)
check("valid_outputs", identical(validated$decision, "PASS"))
if (!identical(validated$decision, "PASS")) print(validated)
rewrite_csv <- function(value, path) utils::write.csv(value, path, row.names = FALSE, na = "", fileEncoding = "UTF-8")
rehash <- function(root) {
  paths <- list.files(root, full.names = TRUE)
  paths <- paths[!basename(paths) %in% c("manifest.csv", "SHA256SUMS.txt")]
  rewrite_csv(cg_manifest(paths, root), file.path(root, "manifest.csv"))
  writeLines(cg_sha256_lines(c(paths, file.path(root, "manifest.csv")), root), file.path(root, "SHA256SUMS.txt"))
}
corruption <- function(name, file, mutate) {
  root <- tempfile(paste0("comparegroups-", name, "-"))
  dir.create(root)
  stopifnot(all(file.copy(list.files(output, full.names = TRUE), root)))
  mutate(file.path(root, file))
  rehash(root)
  check(name, identical(cg_validate_outputs(root, stem)$decision, "FAIL"))
}
change_numeric <- function(path) {
  frame <- utils::read.csv(path, check.names = FALSE)
  frame$value[[1L]] <- frame$value[[1L]] + 1000000
  rewrite_csv(frame, path)
}
corruption("numeric_semantics", paste0(stem, "_numeric_long.csv"), change_numeric)
corruption("display_semantics", paste0(stem, "_display.csv"), function(path) {
  frame <- utils::read.csv(path, check.names = FALSE)
  frame[[4L]][[2L]] <- "999999"
  rewrite_csv(frame, path)
})
corruption("validation_complete", "validation.csv", function(path) {
  frame <- utils::read.csv(path, check.names = FALSE)
  rewrite_csv(frame[1L, ], path)
})
corruption("validation_unique", "validation.csv", function(path) {
  frame <- utils::read.csv(path, check.names = FALSE)
  rewrite_csv(rbind(frame, frame[1L, ]), path)
})
metadata <- jsonlite::fromJSON(file.path(output, paste0(stem, "_metadata.json")), simplifyVector = FALSE)
entry <- metadata$variant_outputs[[1L]]
corruption("variant_numeric_semantics", cg_scalar(entry$files$numeric_long), change_numeric)
corruption("variant_contract_not_vacuous", paste0(stem, "_metadata.json"), function(path) {
  value <- jsonlite::fromJSON(path, simplifyVector = FALSE)
  value$variant_outputs <- list()
  jsonlite::write_json(value, path, auto_unbox = TRUE, null = "null", na = "null")
})
cat(sprintf("CORRECTNESS_TOTAL %d/%d\n", sum(checks), length(checks)))
if (!all(checks)) stop("Correctness regressions failed: ", paste(names(checks)[!checks], collapse = ", "))
