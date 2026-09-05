args_all <- commandArgs(trailingOnly = FALSE)
script_arg <- grep("^--file=", args_all, value = TRUE)
script_dir <- dirname(normalizePath(sub("^--file=", "", script_arg[[1L]]), mustWork = TRUE))
source(file.path(script_dir, "comparegroups_common.R"))
args <- cg_parse_args()
if (is.null(args$manifest) || is.null(args[["output-root"]])) {
  cg_stop("Usage: run_comparegroups_batch.R --manifest <batch-manifest.json> --output-root <new-directory>")
}
result <- cg_run_batch(args$manifest, args[["output-root"]])
cat("COMPAREGROUPS_BATCH_OK decision=", result$decision, " output_root=", result$output_root, "\n", sep = "")
