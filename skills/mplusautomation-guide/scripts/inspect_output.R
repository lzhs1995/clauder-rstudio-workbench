# 只读核验；返回执行、解析和统计诊断的独立标志。
inspect_mplus_output <- function(path) {
  stopifnot(file.exists(path), requireNamespace("MplusAutomation"))
  text <- readLines(path, warn=FALSE)
  ended <- any(grepl("^\\s*Ending Time:", text))
  normal <- any(grepl("THE MODEL ESTIMATION TERMINATED NORMALLY",text,fixed=TRUE))
  if (!ended) return(list(path=path,status="incomplete",ended=FALSE,normal=normal))
  result <- MplusAutomation::readModels(path,what=c("parameters","summaries","warn_err"))
  stopifnot(all(c("warnings","errors") %in% names(result)))
  n <- if(is.null(result$parameters$unstandardized)) 0L else nrow(result$parameters$unstandardized)
  fatal <- any(grepl("^\\s*\\*\\*\\* ERROR|NO CONVERGENCE|ESTIMATION DID NOT TERMINATE",text))
  # MplusAutomation 1.2可能漏掉未以WARNING或正常终止行开头的识别诊断。
  start <- grep("^\\s*THE STANDARD ERRORS OF THE MODEL PARAMETER ESTIMATES MAY NOT BE",text)
  end <- grep("^\\s*MODEL FIT INFORMATION\\s*$",text)
  raw_diagnostics <- if(length(start) && any(end > start[1]))
    text[seq.int(start[1],min(end[end > start[1]])-1L)] else character()
  status <- if (fatal || !n) "failed" else if (!normal || length(result$errors) ||
    length(result$warnings) || length(raw_diagnostics)) "review" else "estimated"
  list(path=path,status=status,ended=ended,normal=normal,parameter_rows=n,
       summaries=result$summaries,warnings=result$warnings,diagnostics=result$errors,
       raw_diagnostics=raw_diagnostics)
}
