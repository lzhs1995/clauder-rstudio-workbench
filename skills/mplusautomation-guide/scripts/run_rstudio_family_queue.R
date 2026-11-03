# 在同一个 Windows RStudio/ClaudeR 异步 worker 中执行现成家族；模型驱动不分叉。
run_rstudio_family_queue <- function(queue_file) {
  stopifnot(.Platform$OS.type == "windows")
  stopifnot(requireNamespace("jsonlite", quietly=TRUE), requireNamespace("processx", quietly=TRUE),
            requireNamespace("digest", quietly=TRUE), requireNamespace("ps", quietly=TRUE))
  queue <- jsonlite::fromJSON(queue_file, simplifyVector=FALSE)
  stopifnot(identical(queue$schema, "rstudio-family-queue/1"), queue$maximum_parallel_mplus == 1L)
  parent <- ps::ps_handle(); bound <- FALSE
  for (i in seq_len(64L)) {
    if (grepl("^rsession", ps::ps_name(parent), ignore.case=TRUE)) {
      bound <- ps::ps_pid(parent) == queue$rstudio_r_pid &&
        abs(as.numeric(ps::ps_create_time(parent)) - queue$rstudio_r_created) < 0.01
      break
    }
    parent <- ps::ps_parent(parent)
    if (is.null(parent)) break
  }
  stopifnot(bound)
  stopifnot(identical(digest::digest(queue$admission_script, file=TRUE, algo="sha256"),
                      queue$admission_script_sha256))
  dir.create(queue$state_dir, recursive=TRUE, showWarnings=FALSE)
  # 一个排队作业只提交一次；目录是原子领取，重开客户端不会重新启动家族。
  stopifnot(dir.create(file.path(queue$state_dir, "RUN_CLAIM"), showWarnings=FALSE))
  events <- file.path(queue$state_dir, "EVENTS.jsonl")
  original_progress <- if (exists("clauder_progress", mode="function", inherits=TRUE))
    get("clauder_progress", mode="function", inherits=TRUE) else function(...) NULL
  family <- "queue"
  event <- function(stage, message, detail=NULL) {
    row <- list(at=format(Sys.time(), tz="UTC", usetz=TRUE), family=family,
                stage=stage, message=message, detail=detail)
    text <- jsonlite::toJSON(row, auto_unbox=TRUE, null="null", digits=NA)
    stopifnot(nchar(text, type="bytes") <= 8192L)
    con <- file(events, open="at", encoding="UTF-8")
    tryCatch({writeLines(text, con); flush(con)}, finally=close(con))
    original_progress(stage, message)
  }
  event("QUEUE_STARTED", queue$id, list(r_pid=Sys.getpid(), rstudio_r_pid=queue$rstudio_r_pid))
  began <- proc.time()[["elapsed"]]
  completed <- list()
  for (entry in queue$families) {
    family <- entry$id
    if (!identical(entry$dispatch, "READY")) {
      event("FAMILY_HELD", entry$reason)
      completed[[family]] <- list(status=entry$dispatch, reason=entry$reason)
      next
    }
    wait_started <- proc.time()[["elapsed"]]
    repeat {
      if (file.exists(file.path(queue$state_dir, "STOP"))) {
        event("QUEUE_STOPPED", "STOP observed before a new family")
        return(invisible(list(status="STOPPED", families=completed)))
      }
      if (proc.time()[["elapsed"]] - began > queue$maximum_wall_seconds) stop("原队列等待期限已过")
      probe <- processx::run(queue$python, c("-B", queue$admission_script,
                           "--queue", queue_file, "--family", family),
                           error_on_status=FALSE, timeout=60000)
      if (probe$status != 0L) {
        event("HOLD_ADMISSION", substr(probe$stdout, 1L, 2048L))
        stop("家族准入未通过；原输出与未知状态保留")
      }
      ready <- jsonlite::fromJSON(probe$stdout, simplifyVector=FALSE)
      if (identical(ready$status, "ADMITTED")) break
      if (identical(ready$status, "STOPPED")) return(invisible(list(status="STOPPED")))
      stopifnot(identical(ready$status, "WAIT_RESOURCES"))
      event("WAIT_RESOURCES", family, ready$observed)
      if (proc.time()[["elapsed"]] - wait_started >= queue$resource_wait_seconds) {
        event("HOLD_RESOURCES", "No family engine was started; preserve the unsubmitted candidate")
        return(invisible(list(status="HOLD_RESOURCES", family=family)))
      }
      Sys.sleep(queue$resource_poll_seconds)
    }
    event("FAMILY_ADMITTED", family, list(historical_calls=ready$historical_calls,
                                          historical_seconds=ready$historical_seconds))
    stopifnot(identical(digest::digest(ready$driver, file=TRUE, algo="sha256"), ready$driver_sha256))
    scope <- new.env(parent=environment())
    scope$clauder_progress <- function(stage, message, ...) event(stage, message)
    sys.source(ready$driver, envir=scope)
    result <- scope$run_rstudio_mplus_batch(ready$config)
    # 外层 R 正常返回不是科研完成；单独保留 BATCH_HOLD 与未合并状态。
    completed[[family]] <- list(status=result$status, result_file=result$result_file,
                               MplusAutomation_invocations=result$MplusAutomation_invocations)
    event("FAMILY_RETURNED", result$status, completed[[family]])
    if (!identical(result$status, "BATCH_RETURNED")) break
  }
  family <- "queue"
  event("QUEUE_RETURNED", "Inspect family outcomes; pooled inference is a separate gate", completed)
  invisible(list(status="QUEUE_RETURNED", families=completed))
}
