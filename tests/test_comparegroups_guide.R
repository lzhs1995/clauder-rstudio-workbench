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

numeric <- utils::read.csv(file.path(output, "Table_synthetic_numeric_long.csv"), check.names = FALSE)
observed <- subset(numeric, variant == "primary_wave_1" & variable == "outcome" & statistic == "mean" & group == "[ALL]")$value
stopifnot(length(observed) == 1L, isTRUE(all.equal(observed, 12.825)))
observed_n <- subset(numeric, variant == "primary_wave_1" & variable == "outcome" & statistic == "n_available" & group == "[ALL]")$value
stopifnot(length(observed_n) == 1L, identical(observed_n, 4))

cat("COMPAREGROUPS_R_TESTS_OK\n")
