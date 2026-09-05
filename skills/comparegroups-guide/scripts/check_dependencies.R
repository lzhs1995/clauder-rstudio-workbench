args_all <- commandArgs(trailingOnly = FALSE)
script_arg <- grep("^--file=", args_all, value = TRUE)
script_dir <- dirname(normalizePath(sub("^--file=", "", script_arg[[1L]]), mustWork = TRUE))
source(file.path(script_dir, "comparegroups_common.R"))
missing <- cg_missing_packages()
if (length(missing)) {
  cat("MISSING:", paste(missing, collapse = ", "), "\n")
  cat("Install with: install.packages(c(", paste(sprintf("'%s'", missing), collapse = ", "), "))\n")
  quit(status = 2L)
}
versions <- vapply(required_packages, function(pkg) as.character(utils::packageVersion(pkg)), character(1))
cg_require_packages()
cat("COMPAREGROUPS_DEPENDENCIES_OK\n")
print(versions)
