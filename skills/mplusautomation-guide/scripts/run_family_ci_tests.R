# 按 families.json 跑托管 CI 能跑的 R 合同测试（needs_mplus=false），不启动 Mplus。
# 用法：Rscript scripts/run_family_ci_tests.R <workflow 文件名> <新的输出根目录>
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 2)
workflow <- args[[1]]
out_root <- args[[2]]
stopifnot(!dir.exists(out_root))
dir.create(out_root, recursive = TRUE)
# 定位 skill 根：本脚本位于 scripts/ 下
file_arg <- grep('^--file=', commandArgs(FALSE), value = TRUE)
skill_root <- normalizePath(file.path(dirname(sub('^--file=', '', file_arg[[1]])), '..'), winslash = '/')
registry <- jsonlite::read_json(file.path(skill_root, 'families.json'))
# engine 只用于准备/编译合同检查；占位为当前 Rscript
engine <- file.path(R.home('bin'), if (.Platform$OS.type == 'windows') 'Rscript.exe' else 'Rscript')
python <- unname(Sys.which('python'))
if (!nzchar(python)) python <- unname(Sys.which('python3'))
stopifnot(nzchar(python))
values <- list(skill_root = skill_root, scripts_dir = file.path(skill_root, 'scripts'),
  engine = engine, python = python)
selected <- Filter(function(t) identical(t$lang, 'R') && isFALSE(t$needs_mplus) &&
  identical(t$ci, workflow), registry$tests)
stopifnot(length(selected) > 0)
# ci_os 限定平台（取值同 GitHub runner.os）；本机核验可设 FAMILY_CI_IGNORE_OS=1 全部运行
os_name <- switch(Sys.info()[['sysname']], Darwin = 'macOS', Linux = 'Linux', Windows = 'Windows', 'other')
ignore_os <- identical(Sys.getenv('FAMILY_CI_IGNORE_OS'), '1')
results <- list()
for (id in names(selected)) {
  test <- selected[[id]]
  if (!ignore_os && length(test$ci_os) && !os_name %in% unlist(test$ci_os)) {
    results[[id]] <- list(path = test$path, result = 'SKIPPED_OS', seconds = 0)
    cat('[family-ci]', id, 'SKIPPED_OS on', os_name, '\n'); flush.console()
    next
  }
  cat('[family-ci]', id, 'start', format(Sys.time(), '%H:%M:%S'), '\n'); flush.console()
  started <- proc.time()[['elapsed']]
  # 每个测试在独立环境中 source，避免函数和全局对象互相覆盖
  env <- new.env(parent = globalenv())
  outcome <- tryCatch({
    sys.source(file.path(skill_root, test$path), envir = env)
    call_args <- lapply(unlist(test$args), function(a)
      if (a == 'out_dir') file.path(out_root, id) else values[[a]])
    do.call(get(test$`function`, envir = env), call_args)
    'PASS'
  }, error = function(e) paste('FAIL:', conditionMessage(e)))
  seconds <- round(proc.time()[['elapsed']] - started, 2)
  results[[id]] <- list(path = test$path, result = outcome, seconds = seconds)
  cat('[family-ci]', id, outcome, seconds, 's\n'); flush.console()
}
jsonlite::write_json(results, file.path(out_root, 'family_ci_results.json'), auto_unbox = TRUE, pretty = TRUE)
failed <- names(Filter(function(r) !r$result %in% c('PASS', 'SKIPPED_OS'), results))
if (length(failed)) stop('Family CI tests failed: ', paste(failed, collapse = ', '))
cat('FAMILY_CI_TESTS_PASS', sum(vapply(results, function(r) r$result == 'PASS', logical(1))), 'run,',
  sum(vapply(results, function(r) r$result == 'SKIPPED_OS', logical(1))), 'skipped by ci_os; Mplus calls: 0\n')
