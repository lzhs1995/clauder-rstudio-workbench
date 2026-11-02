queue_call <- function(config, action, ...) {
  args <- c(config$queue_script, action, "--root", config$root, unlist(list(...)))
  tmpdir <- if(is.null(config$temp_dir))tempdir() else config$temp_dir
  output_file <- tempfile("queue_reply_",tmpdir=tmpdir,fileext=".json")
  error_file <- tempfile("queue_error_",tmpdir=tmpdir,fileext=".log")
  on.exit(unlink(c(output_file,error_file)),add=TRUE)
  status <- system2(config$python,vapply(args,shQuote,character(1)),stdout=output_file,stderr=error_file)
  if(status!=0L)stop(paste(readLines(error_file,warn=FALSE),collapse="\n"))
  jsonlite::fromJSON(output_file,simplifyVector=FALSE)
}

queue_worker <- function(config_file, worker_id, progress=function(...)NULL) {
  config <- jsonlite::read_json(config_file, simplifyVector=TRUE)
  .libPaths(c(config$library, .libPaths()))
  stopifnot(requireNamespace("MplusAutomation", quietly=TRUE), requireNamespace("jsonlite", quietly=TRUE))
  queue_call(config,"register","--worker",worker_id,"--pid",as.character(Sys.getpid()))
  log_dir <- file.path(config$root, "workers", worker_id)
  dir.create(log_dir, recursive=TRUE, showWarnings=FALSE)
  con <- file(file.path(log_dir,"execution.log"), "at")
  sink(con); sink(con,type="message")
  on.exit({sink(type="message");sink();close(con)},add=TRUE)
  tick <- 0L
  repeat {
    task <- queue_call(config,"claim","--worker",worker_id)
    heartbeat <- list(worker=worker_id,pid=Sys.getpid(),stage=task$status,
      message=if(is.null(task$reason))task$task$id else task$reason,updated_at=format(Sys.time(),tz="UTC",usetz=TRUE))
    jsonlite::write_json(heartbeat,file.path(log_dir,"state.json"),auto_unbox=TRUE,pretty=TRUE)
    if(task$status=="claimed") {
      task <- task$task
      progress("model_running",paste(worker_id,task$id,basename(task$input)))
      started <- Sys.time()
      old <- getwd();setwd(dirname(task$input))
      temporary <- file.path(dirname(task$input),"tmp")
      dir.create(temporary,showWarnings=FALSE)
      Sys.setenv(TMPDIR=temporary,TMP=temporary,TEMP=temporary)
      monitor<-NULL
      if(isTRUE(config$apim_v2)) {
        stopifnot(!file.exists('monitor.stop'),!file.exists('resource_measurement.json'))
        monitor<-processx::process$new(config$python,c(
          file.path(dirname(config$queue_script),'apim_resource_monitor.py'),'--pid',as.character(Sys.getpid()),
          '--created',format(as.numeric(ps::ps_create_time(ps::ps_handle())),scientific=FALSE,digits=16),
          '--folder',getwd(),'--engine-sha256',digest::digest(config$mplus,algo='sha256',file=TRUE)),
          stdout='resource_monitor.log',stderr='resource_monitor_error.log',cleanup=FALSE)
        deadline<-Sys.time()+30
        while(!file.exists('monitor.ready')&&monitor$is_alive()&&Sys.time()<deadline)Sys.sleep(.1)
        stopifnot(file.exists('monitor.ready'),monitor$is_alive())
      }
      error <- tryCatch({
        MplusAutomation::runModels(target=basename(task$input),Mplus_command=config$mplus,
          killOnFail=FALSE,logFile="mplus_execution.log",quiet=TRUE,
          replaceOutfile=if(isTRUE(config$apim_v2))'never' else 'always')
        NULL
      },error=function(e)conditionMessage(e))
      if(!is.null(monitor)) {
        writeLines('MplusAutomation returned', 'monitor.stop')
        monitor$wait(timeout=30000)
        stopifnot(!monitor$is_alive(),monitor$get_exit_status()==0L)
      }
      setwd(old)
      result <- queue_call(config,"finish","--worker",worker_id,"--task",task$id,"--output",task$output,
        if(!is.null(error))c("--r-error",error) else character())
      result$r_error <- error
      jsonlite::write_json(result,file.path(dirname(task$input),"validation.json"),auto_unbox=TRUE,pretty=TRUE,null="null")
      record <- task$record
      record$status <- if(isTRUE(result$estimation_ok))if(result$status=="PASS")"estimated" else "estimated_with_warnings" else "estimation_error"
      record$elapsed_sec <- as.numeric(difftime(Sys.time(),started,units="secs"))
      record$utc <- format(Sys.time(),tz="UTC",usetz=TRUE)
      record$output_files <- list.files(dirname(task$input))
      record$error <- error
      jsonlite::write_json(record,file.path(dirname(task$input),"model_status.json"),auto_unbox=TRUE,pretty=TRUE,null="null")
      progress("model_finished",paste(worker_id,task$id,record$status))
      cat(format(Sys.time()),task$id,record$status,"\n");flush(con)
    } else {
      if(tick %% 10L==0L) {
        progress("queue_wait",paste(worker_id,task$reason))
        status <- queue_call(config,"status")
        if(isTRUE(status$producers_done) && status$counts$pending==0 && status$counts$running==0)break
      }
      Sys.sleep(2)
    }
    tick <- tick+1L
  }
  progress("worker_complete",worker_id)
  invisible(TRUE)
}
