# 同一 Windows RStudio/ClaudeR 入口：R 持有 MplusAutomation，Python 只负责原调度和 cap。
# 先 source 本文件，再调用 run_rstudio_mplus_batch(config_file)。不在加载时运行模型。
bind_mplusautomation_library <- function(contract) {
  # 切换 agent 或异步 worker 不能悄悄切换原研究的包；拒绝卸载正在用的命名空间。
  stopifnot(is.list(contract), is.character(contract$library),
            length(contract$library) == 1L, nzchar(contract$library),
            is.character(contract$version), length(contract$version) == 1L,
            is.list(contract$file_sha256), is.list(contract$function_sha256))
  stopifnot(requireNamespace("digest", quietly = TRUE))
  canonical <- function(path) {
    value <- normalizePath(path, winslash = "/", mustWork = TRUE)
    if (.Platform$OS.type == "windows") tolower(value) else value
  }
  library_path <- normalizePath(contract$library, winslash = "/", mustWork = TRUE)
  package_path <- file.path(library_path, "MplusAutomation")
  expected_files <- c("DESCRIPTION", "R/MplusAutomation.rdb", "R/MplusAutomation.rdx")
  expected_functions <- c("runModels", "readModels", "mplusModeler")
  stopifnot(setequal(names(contract$file_sha256), expected_files),
            setequal(names(contract$function_sha256), expected_functions))
  check_files <- function() {
    values <- setNames(lapply(expected_files, function(name) {
      digest::digest(file.path(package_path, name), file = TRUE, algo = "sha256")
    }), expected_files)
    for (name in expected_files) {
      if (!identical(values[[name]], contract$file_sha256[[name]])) {
        stop("原 MplusAutomation 包文件改变: ", name)
      }
    }
    values
  }
  file_hashes <- check_files()
  if ("MplusAutomation" %in% loadedNamespaces()) {
    namespace <- asNamespace("MplusAutomation")
    if (!identical(canonical(getNamespaceInfo(namespace, "path")), canonical(package_path))) {
      stop("当前 R worker 已加载其他 MplusAutomation 库；保留会话，使用新异步 worker")
    }
  } else {
    old_paths <- .libPaths()
    on.exit(.libPaths(old_paths), add = TRUE)
    .libPaths(unique(c(library_path, old_paths)))
    namespace <- loadNamespace("MplusAutomation", lib.loc = library_path)
  }
  version <- as.character(getNamespaceVersion(namespace))
  if (!identical(version, contract$version)) stop("MplusAutomation 原版本不匹配")
  function_hashes <- setNames(lapply(expected_functions, function(name) {
    digest::digest(paste(deparse(get(name, envir = namespace)), collapse = "\n"),
                   algo = "sha256", serialize = FALSE)
  }), expected_functions)
  for (name in expected_functions) {
    if (!identical(function_hashes[[name]], contract$function_sha256[[name]])) {
      stop("MplusAutomation 已加载函数与原合同不符: ", name)
    }
  }
  check_files()
  list(version = version, path = normalizePath(getNamespaceInfo(namespace, "path"), winslash = "/"),
       library = library_path, file_sha256 = file_hashes,
       function_sha256 = function_hashes, dependencies_compared = FALSE)
}

run_rstudio_mplus_batch <- function(config_file) {
  stopifnot(.Platform$OS.type == "windows")
  stopifnot(requireNamespace("jsonlite", quietly = TRUE), requireNamespace("ps", quietly = TRUE),
            requireNamespace("processx", quietly = TRUE), requireNamespace("digest", quietly = TRUE))
  config <- jsonlite::fromJSON(config_file, simplifyVector = FALSE)
  stopifnot(identical(config$schema, "rstudio-mplus-batch-driver/1"))
  package <- bind_mplusautomation_library(config$mplusautomation)
  sha <- function(path) digest::digest(path, file = TRUE, algo = "sha256")
  write_once <- function(value, path) {
    stopifnot(!file.exists(path))
    temporary <- paste0(path, ".part")
    stopifnot(!file.exists(temporary))
    jsonlite::write_json(value, temporary, auto_unbox = TRUE, pretty = TRUE,
                         digits = NA, null = "null")
    stopifnot(file.rename(temporary, path))
  }
  say <- function(stage, message) {
    cat(format(Sys.time(), tz = "UTC"), stage, message, "\n"); flush.console()
    if (exists("clauder_progress", mode = "function", inherits = TRUE)) {
      clauder_progress(stage, message)
    }
  }
  # 原生 RStudio 或 ClaudeR 的异步后代都可用；普通离线 Rscript 不满足身份。
  current <- ps::ps_handle()
  ancestor <- current
  found <- FALSE
  for (i in seq_len(64L)) {
    if (grepl("^rsession", ps::ps_name(ancestor), ignore.case = TRUE)) {
      found <- TRUE
      break
    }
    parent <- ps::ps_parent(ancestor)
    if (is.null(parent) || as.numeric(ps::ps_create_time(parent)) >
        as.numeric(ps::ps_create_time(ancestor)) + 0.01) break
    ancestor <- parent
  }
  stopifnot(found)
  studio <- ps::ps_parent(ancestor)
  stopifnot(grepl("^rstudio", ps::ps_name(studio), ignore.case = TRUE))
  stopifnot(identical(sha(config$coordinator), config$coordinator_sha256))
  channel <- config$channel
  stopifnot(!dir.exists(channel), dir.create(channel, recursive = TRUE))
  stopifnot(dir.create(file.path(channel, "requests")))
  owner <- list(r_pid = Sys.getpid(), r_created = as.numeric(ps::ps_create_time(current)),
                rstudio_r_pid = ps::ps_pid(ancestor),
                rstudio_r_created = as.numeric(ps::ps_create_time(ancestor)),
                rstudio_pid = ps::ps_pid(studio),
                rstudio_created = as.numeric(ps::ps_create_time(studio)),
                R_version = R.version.string,
                MplusAutomation = package$version,
                MplusAutomation_path = package$path,
                MplusAutomation_contract = package,
                config_sha256 = sha(config_file))
  write_once(owner, file.path(channel, "R_OWNER.json"))
  say("BATCH_START", "RStudio R worker starts the original batch coordinator")
  coordinator <- processx::process$new(
    config$python, c("-X", "utf8", "-B", config$coordinator,
                     unlist(config$arguments, use.names = FALSE),
                     "--rstudio-channel", channel),
    stdout = file.path(channel, "coordinator.stdout.log"),
    stderr = file.path(channel, "coordinator.stderr.log"),
    cleanup = FALSE, cleanup_tree = FALSE, supervise = FALSE
  )
  write_once(list(pid = coordinator$get_pid(), at = format(Sys.time(), tz = "UTC")),
             file.path(channel, "COORDINATOR.json"))
  began <- proc.time()[["elapsed"]]
  invocation_count <- 0L
  last_progress <- ""
  repeat {
    requests <- list.files(file.path(channel, "requests"), pattern = "REQUEST.json$",
                           recursive = TRUE, full.names = TRUE)
    pending <- requests[!file.exists(file.path(dirname(requests), "R_WRAPPER_RETURN.json"))]
    stopifnot(length(pending) <= 1L)
    if (length(pending)) {
      request_file <- pending[[1L]]
      request <- jsonlite::fromJSON(request_file, simplifyVector = FALSE)
      folder <- dirname(request_file)
      stopifnot(identical(sha(request$target), request$input_sha256),
                identical(sha(request$wrapper), request$wrapper_sha256),
                identical(sha(request$contract), request$contract_sha256),
                identical(as.integer(request$owner$r_pid), Sys.getpid()),
                !file.exists(file.path(folder, "R_MPLUSAUTOMATION_CALL.json")))
      call <- list(at = format(Sys.time(), tz = "UTC", usetz = TRUE),
                   member = request$member,
                   request_sha256 = sha(request_file), r_pid = Sys.getpid(),
                   r_created = owner$r_created, rstudio_r_pid = owner$rstudio_r_pid,
                   package_version = owner$MplusAutomation,
                   package_path = owner$MplusAutomation_path,
                   target_sha256 = request$input_sha256,
                   Mplus_command_sha256 = request$wrapper_sha256)
      # "function" 是 R 关键字，使用命名赋值保留跨语言字段名。
      call[["function"]] <- "MplusAutomation::runModels"
      write_once(call, file.path(folder, "R_MPLUSAUTOMATION_CALL.json"))
      say("MPLUSAUTOMATION_RUNMODELS", request$member)
      error <- NULL; warnings <- character(); started <- proc.time()[["elapsed"]]
      invocation_count <- invocation_count + 1L
      withCallingHandlers(tryCatch({
        MplusAutomation::runModels(
          target = request$target, recursive = FALSE, showOutput = TRUE,
          replaceOutfile = "never", Mplus_command = request$wrapper,
          killOnFail = FALSE, logFile = file.path(folder, "MplusAutomation.log")
        )
      }, error = function(e) { error <<- conditionMessage(e) }),
      warning = function(w) { warnings <<- c(warnings, conditionMessage(w)); invokeRestart("muffleWarning") })
      parsed_rows <- NULL; readback_error <- NULL
      output <- file.path(folder, "model.out")
      if (file.exists(output) && any(grepl("THE MODEL ESTIMATION TERMINATED NORMALLY",
                                          readLines(output, warn = FALSE), fixed = TRUE))) {
        say("MPLUSAUTOMATION_READBACK", request$member)
        parsed <- tryCatch(suppressWarnings(MplusAutomation::readModels(
          output, what = c("parameters", "summaries"), quiet = TRUE)),
          error = function(e) { readback_error <<- conditionMessage(e); NULL })
        if (!is.null(parsed$parameters$unstandardized)) parsed_rows <- nrow(parsed$parameters$unstandardized)
      }
      write_once(list(status = "WRAPPER_RETURNED", at = format(Sys.time(), tz = "UTC"),
                      request_sha256 = sha(request_file), r_pid = Sys.getpid(),
                      error = error, warnings = warnings,
                      elapsed_seconds = proc.time()[["elapsed"]] - started,
                      readModels_parameter_rows = parsed_rows, readModels_error = readback_error),
                 file.path(folder, "R_WRAPPER_RETURN.json"))
      say("MODEL_WRAPPER_RETURNED", request$member)
    }
    if (!coordinator$is_alive()) break
    if (!is.null(config$progress_file) && file.exists(config$progress_file)) {
      text <- paste(readLines(config$progress_file, warn = FALSE), collapse = "\n")
      if (!identical(last_progress, text)) {
        progress <- tryCatch(jsonlite::fromJSON(text), error = function(e) NULL)
        if (!is.null(progress)) {
          say(progress$stage, if (is.null(progress$member)) "batch checkpoint" else progress$member)
          last_progress <- text
        }
      }
    }
    if (proc.time()[["elapsed"]] - began > config$maximum_driver_seconds) {
      stop("原批次 R 等待期限已过；原 coordinator/引擎证据保留，禁止自动再提交")
    }
    Sys.sleep(0.25)
  }
  status <- coordinator$get_exit_status()
  result <- list(status = if (identical(status, 0L)) "BATCH_RETURNED" else "BATCH_HOLD",
                 coordinator_exit_code = status,
                 MplusAutomation_invocations = invocation_count,
                 elapsed_seconds = proc.time()[["elapsed"]] - began,
                 result_file = config$result_file, r_owner = owner,
                 native_MCP_verified = FALSE)
  write_once(result, file.path(channel, "R_DRIVER_RESULT.json"))
  say(result$status, paste("coordinator exit", status))
  result
}
