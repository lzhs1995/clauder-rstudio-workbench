# 可直接执行的合成换源示例；生成完整 JSON 后通过同一入口编译五种测量/纵向组合。
# 不读研究文件，不运行 Mplus，不安装依赖，不改变全局 RStudio 会话。
ch7_source_example_20261111 <- function(output_dir, skill_root) {
  if (file.exists(output_dir)) stop("Fresh example root required")
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = "/")
  source(file.path(skill_root, "scripts/ch7_native_fixture_20261111.R"), local = TRUE)
  source(file.path(skill_root, "scripts/ch7_source_entry_20261111.R"), local = TRUE)
  fixture <- ch7_native_fixture(file.path(output_dir, "source"))
  prepared <- ch7_source_entry(fixture$config_file, file.path(output_dir, "prepared"), skill_root)
  cat("Synthetic configuration:", fixture$config_file, "\n")
  cat("Prepared manifest:", file.path(prepared$output_dir, "manifest.json"), "\n")
  cat("Mplus engine calls: 0; native acceptance requires the authorized execution layer.\n")
  invisible(prepared)
}

if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) != 1L) stop("Usage: Rscript ch7_source_example_20261111.R fresh-demo-root")
  file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
  ch7_source_example_20261111(args[[1L]], file.path(dirname(sub("^--file=", "", file_arg[[1L]])), ".."))
}
