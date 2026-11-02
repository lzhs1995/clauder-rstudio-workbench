# 使用真实已安装的两个包库验证绑定和保存输出；不会启动 Mplus。
validate_rstudio_library_binding <- function(driver, config, alternate_library, outputs) {
  stopifnot(requireNamespace("callr", quietly = TRUE))
  inspect <- function(driver, config, alternate_library, outputs, use_alternate) {
    source(driver, local = TRUE)
    read_outputs <- function() {
      lapply(outputs, function(path) {
        before <- digest::digest(path, file = TRUE, algo = "sha256")
        normal <- any(grepl("THE MODEL ESTIMATION TERMINATED NORMALLY",
                            readLines(path, warn = FALSE), fixed = TRUE))
        fit <- suppressWarnings(MplusAutomation::readModels(
          path, what = c("parameters", "summaries"), quiet = TRUE))
        stopifnot(identical(before, digest::digest(path, file = TRUE, algo = "sha256")))
        list(source_sha256 = before, normal_termination = normal,
             parameters = fit$parameters$unstandardized)
      })
    }
    check_rejection <- function(contract, pattern) {
      error <- tryCatch({bind_mplusautomation_library(contract); NULL}, error = identity)
      stopifnot(inherits(error, "error"), grepl(pattern, conditionMessage(error), fixed = TRUE))
      conditionMessage(error)
    }
    if (use_alternate) {
      loadNamespace("MplusAutomation", lib.loc = alternate_library)
      before <- getNamespaceInfo("MplusAutomation", "path")
      error <- check_rejection(config, "已加载其他 MplusAutomation 库")
      stopifnot(identical(before, getNamespaceInfo("MplusAutomation", "path")))
      return(list(test = "LOADED_OTHER_LIBRARY_REJECTED_WITHOUT_UNLOAD", error = error,
                  alternate_version = as.character(getNamespaceVersion("MplusAutomation")),
                  records = read_outputs()))
    }
    binding <- bind_mplusautomation_library(config)
    errors <- list()
    changed <- config; changed$version <- "0.0.0"
    errors$version <- check_rejection(changed, "原版本不匹配")
    changed <- config; changed$file_sha256[["DESCRIPTION"]] <- strrep("0", 64)
    errors$file <- check_rejection(changed, "包文件改变")
    changed <- config; changed$function_sha256[["readModels"]] <- strrep("0", 64)
    errors$function_body <- check_rejection(changed, "已加载函数与原合同不符")
    missing <- tryCatch({bind_mplusautomation_library(NULL); NULL}, error = identity)
    stopifnot(inherits(missing, "error"))
    errors$missing <- conditionMessage(missing)
    list(test = "BOUND_ORIGINAL_LIBRARY_AND_REJECTED_CHANGED_CONTRACTS",
         binding = binding, errors = errors, records = read_outputs())
  }
  alternate <- callr::r(inspect, args = list(driver, config, alternate_library, outputs, TRUE),
                        timeout = 90, user_profile = FALSE)
  original <- callr::r(inspect, args = list(driver, config, alternate_library, outputs, FALSE),
                       timeout = 90, user_profile = FALSE)
  comparisons <- Map(function(a, b) {
    stopifnot(identical(a$source_sha256, b$source_sha256))
    list(source_sha256 = a$source_sha256, normal_termination = b$normal_termination,
         parameter_rows = if (is.null(b$parameters)) 0L else nrow(b$parameters),
         identical_parameter_tables = identical(a$parameters, b$parameters),
         difference = if (identical(a$parameters, b$parameters)) NULL else
           as.character(all.equal(a$parameters, b$parameters)))
  }, alternate$records, original$records)
  stopifnot(comparisons[[1L]]$normal_termination,
            comparisons[[1L]]$parameter_rows > 0L,
            !comparisons[[2L]]$normal_termination,
            comparisons[[2L]]$parameter_rows == 0L)
  alternate$records <- original$records <- NULL
  list(status = "ORIGINAL_PACKAGE_BINDING_ACCEPTED", cases = 6L,
       alternate = alternate, original = original, comparisons = comparisons,
       new_mplus_calls = 0L, individual_data_read = FALSE,
       boundary = "Only these saved parameter tables compared; not full package equivalence")
}
