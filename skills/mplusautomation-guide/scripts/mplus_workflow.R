mplus_executable <- function(command = Sys.getenv("MPLUS_COMMAND", "")) {
  if(!nzchar(command))command <- MplusAutomation::detectMplus()
  if(length(command)!=1L || !nzchar(command))stop("One Mplus executable is required")
  # detectMplus() 可能返回裸命令；同名目录不是可执行文件。
  if(!grepl("[/\\\\]",command))command <- unname(Sys.which(command))
  if(!nzchar(command) || !file.exists(command) || dir.exists(command))stop("Mplus executable was not found")
  normalizePath(command,winslash="/",mustWork=TRUE)
}

validate_mplus_output <- function(path, expected_imputations = NULL) {
  if(!file.exists(path))return(list(status="FAIL",reasons="Missing output",path=path))
  text <- readLines(path,warn=FALSE)
  failures <- grep("\\*\\*\\* ERROR|DID NOT TERMINATE NORMALLY|FAILED TO CONVERGE|NO CONVERGENCE",text,value=TRUE)
  warnings <- grep("\\*\\*\\* WARNING|NOT POSITIVE DEFINITE|COULD NOT BE COMPUTED",text,value=TRUE)
  estimated <- any(grepl("^\\s*MODEL RESULTS\\s*$",text))
  normal <- any(grepl("THE MODEL ESTIMATION TERMINATED NORMALLY",text,fixed=TRUE))
  count <- function(label) {
    pattern <- paste0("^\\s*",label,"\\s+([0-9]+)\\s*$")
    found <- grep(pattern,text,value=TRUE)
    if(length(found))as.integer(sub(pattern,"\\1",found[[1]])) else NA_integer_
  }
  requested <- count("Requested");completed <- count("Completed")
  reasons <- character()
  if(!estimated)reasons <- c(reasons,"No MODEL RESULTS section")
  if(length(failures))reasons <- c(reasons,trimws(failures))
  if(!is.na(requested) && (is.na(completed) || completed!=requested))
    reasons <- c(reasons,"Not all requested imputations completed")
  if(!is.null(expected_imputations)) {
    if(length(expected_imputations)!=1L || is.na(expected_imputations) || expected_imputations<1L || expected_imputations%%1!=0)stop("Expected imputations must be a positive integer")
    if(is.na(requested) || is.na(completed) || requested!=expected_imputations || completed!=expected_imputations)
      reasons <- c(reasons,"Imputation counts do not match the contract")
  } else if(!normal && is.na(completed))reasons <- c(reasons,"Normal termination was not verified")
  list(status=if(length(reasons))"FAIL" else if(length(warnings))"REVIEW" else "PASS",
    reasons=reasons,warnings=trimws(warnings),requested=requested,completed=completed,path=path)
}

run_mplus_model <- function(object, run_root, model_id, command = "", expected_imputations = NULL) {
  stopifnot(requireNamespace("MplusAutomation",quietly=TRUE),requireNamespace("jsonlite",quietly=TRUE),requireNamespace("digest",quietly=TRUE))
  if(length(run_root)!=1L || !nzchar(run_root))stop("An explicit run root is required")
  if(length(model_id)!=1L || !grepl("^[A-Za-z0-9][A-Za-z0-9_-]*$",model_id))stop("Use a simple unique model ID")
  if(!is.null(object$DATA) && grepl("(?i)\\bFILE\\s*=",object$DATA,perl=TRUE))stop("External DATA FILE dependencies require explicit staging")
  saved <- paste(object$SAVEDATA,collapse="\n")
  if(grepl("[A-Za-z]:[/\\\\]|/|\\\\|\\.\\.",saved))stop("SAVEDATA must use local filenames in this model directory")
  executable <- mplus_executable(command)
  dir.create(run_root,recursive=TRUE,showWarnings=FALSE)
  run_root <- normalizePath(run_root,winslash="/",mustWork=TRUE)
  directory <- file.path(run_root,model_id)
  if(!dir.create(directory,showWarnings=FALSE))stop("Model directory already exists; choose a new ID or explicitly validate a resume")
  old <- getwd();on.exit(setwd(old),add=TRUE);setwd(directory)
  fingerprint <- digest::digest(object,algo="sha256")
  started <- Sys.time()
  state_file <- file.path(directory,"state.json")
  update <- function(status,detail=NULL)jsonlite::write_json(list(model_id=model_id,status=status,detail=detail,
    fingerprint=fingerprint,updated_at=format(Sys.time(),tz="UTC",usetz=TRUE)),state_file,auto_unbox=TRUE,pretty=TRUE,null="null")
  update("running")
  error <- NULL
  fit <- tryCatch(MplusAutomation::mplusModeler(object,dataout="data.dat",modelout="model.inp",run=TRUE,
    Mplus_command=executable,writeData="always",hashfilename=FALSE,killOnFail=FALSE,quiet=TRUE),error=function(e){error<<-conditionMessage(e);NULL})
  diagnostics <- validate_mplus_output("model.out",expected_imputations)
  parameters <- if(!is.null(fit))fit$results$parameters$unstandardized else NULL
  if(!is.null(error)){diagnostics$status<-"FAIL";diagnostics$reasons<-c(diagnostics$reasons,error)}
  if(!is.data.frame(parameters) || !nrow(parameters) || !all(c("est","se")%in%names(parameters)) ||
    any(!is.finite(parameters$est)) || any(!is.finite(parameters$se))) {
    diagnostics$status<-"FAIL";diagnostics$reasons<-c(diagnostics$reasons,"Finite parameter estimates and standard errors were not verified")
  }
  if(is.data.frame(parameters))write.csv(parameters,"parameters.csv",row.names=FALSE)
  if(!is.null(fit))saveRDS(fit,"fit.rds")
  jsonlite::write_json(diagnostics,"validation.json",auto_unbox=TRUE,pretty=TRUE,null="null",na="null")
  update(diagnostics$status,diagnostics$reasons)
  files <- list.files(directory,full.names=TRUE)
  files <- files[!dir.exists(files)]
  manifest <- data.frame(file=basename(files),bytes=file.info(files)$size,
    sha256=vapply(files,digest::digest,character(1),file=TRUE,algo="sha256"))
  write.csv(manifest,"manifest.csv",row.names=FALSE)
  invisible(list(directory=directory,validation=diagnostics,elapsed_seconds=as.numeric(difftime(Sys.time(),started,units="secs"))))
}
