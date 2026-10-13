# 资源变化属于可重试状态；损坏的资源契约仍为致命错误。
assert_incremental_capacity <- function(gate, age_seconds, available_gib) {
  required<-c('eligible','new_R_workers','incremental_budget_gib','reserved_free_gib')
  if(!all(required %in% names(gate)) || !is.logical(gate$eligible) ||
     length(gate$eligible)!=1L || is.na(gate$eligible) ||
     !identical(as.numeric(gate$new_R_workers),0) ||
     length(gate$incremental_budget_gib)!=1L || !is.finite(gate$incremental_budget_gib) ||
     gate$incremental_budget_gib<=0 || length(gate$reserved_free_gib)!=1L ||
     !is.finite(gate$reserved_free_gib) || gate$reserved_free_gib<0)
    stop('Invalid incremental resource contract')
  reason<-if(length(age_seconds)!=1L || !is.finite(age_seconds) || age_seconds<0 || age_seconds>=300)
    'Resource measurement expired; sample again' else if(!isTRUE(gate$eligible))
    'Resource admission currently held' else if(length(available_gib)!=1L ||
      !is.finite(available_gib) || available_gib<gate$incremental_budget_gib+gate$reserved_free_gib)
    'Available RAM fell below measured budget before launch' else NULL
  if(!is.null(reason))stop(structure(list(message=reason,call=NULL),
    class=c('mplus_resource_wait','error','condition')))
  invisible(TRUE)
}
