# Windows 外层准入器调用本驱动；仅准备/编译不获得拟合许可，拟合前必须再次通过 gate-fit。
charls_apim_swap_driver <- function(request_path) {
  stopifnot(requireNamespace('jsonlite',quietly=TRUE),requireNamespace('digest',quietly=TRUE))
  request<-jsonlite::read_json(request_path,simplifyVector=TRUE)
  args0<-commandArgs(FALSE);filearg<-sub('^--file=','',args0[grepl('^--file=',args0)])
  stopifnot(length(filearg)==1)
  scripts<-dirname(normalizePath(filearg,winslash='/',mustWork=TRUE))
  source(file.path(scripts,'workflow.R'),local=TRUE)
  source(file.path(scripts,'charls_apim_swap.R'),local=TRUE)
  source(file.path(dirname(scripts),'assets','charls_apim_swap_config_v2.R'),local=TRUE)
  expected<-data.frame(id=c('apim_sample1_x1_y1_m1_w1_step1','apimem_sample1_x1_y1_m1_w1_step1'),family=c('APIM','APIMeM'))
  charls_swap_assert(identical(request$expected_models[,c('id','family')],expected),'Unexpected requested model set/order')
  charls_swap_assert(is.character(request$attempt_id)&&length(request$attempt_id)==1&&nzchar(request$attempt_id),'Missing attempt identity')
  root<-normalizePath(request$root,winslash='/',mustWork=TRUE)
  charls_swap_assert(!file.exists(file.path(root,'DRIVER_COMPLETE.json')),'Completed driver attempt must not be rerun')
  contract<-request$scientific_contract
  # JSON 的数组解码为向量；空 missing-code 对象保留 list 语义。
  paths<-vapply(request$sources,`[[`,'','path')
  hashes<-vapply(request$sources,`[[`,'','sha256')
  charls_swap_assert(identical(unname(vapply(paths,charls_swap_sha,'')),unname(hashes)),'Source snapshot hash mismatch')
  for(p in paths)charls_swap_assert(startsWith(normalizePath(p,winslash='/',mustWork=TRUE),paste0(root,'/source_snapshot/')),
    'Driver reads only owned source snapshots')
  cat('prepare_sources: validating documented reciprocal spouse contract\n');flush.console()
  persons<-charls_swap_read_sources(paths,contract)
  prep<-charls_prepare_apim_swap(persons,contract,file.path(root,'prepared_swap'),source_paths=paths)
  cfg<-charls_apim_swap_config(prep$data_path,file.path(root,'models_run'),request$engine,request$python,
    protected_roots=request$protected_roots,member_labels=contract$member_labels)
  plan<-plan_apim_workflow(cfg)
  actual<-data.frame(id=names(plan$models),family=vapply(plan$models,`[[`,'','family'),row.names=NULL)
  charls_swap_assert(identical(actual,expected)&&plan$execution_count==2L,'Exactly one APIM and APIMeM are required')
  cat('compile: preparing two declared models without Mplus\n');flush.console()
  run_apim_workflow(cfg,stages=c('check','prepare','compile'))
  charls_swap_assert(.Platform$OS.type=='windows','Fit gate requires native Windows')
  gate_args<-c(request$gate_script,'gate-fit','--run-root',root,'--attempt-id',request$attempt_id)
  code<-system2(request$python,vapply(gate_args,shQuote,''))
  charls_swap_assert(identical(as.integer(code),0L),'FIT_GATE_NOT_ADMITTED')
  receipt_path<-file.path(root,'FIT_ADMITTED.json')
  charls_swap_assert(file.exists(receipt_path),'Missing FIT_ADMITTED receipt')
  gate<-jsonlite::read_json(receipt_path,simplifyVector=TRUE)
  charls_swap_assert(identical(gate$schema,'CHARLS_SWAP_FIT_ADMISSION_V1')&&
    identical(gate$attempt_id,request$attempt_id)&&identical(gate$models[,c('id','family')],expected)&&
    identical(gate$config_sha256,request$config_sha256)&&identical(gate$grant_sha256,request$grant_sha256),
    'Fit admission receipt binding mismatch')
  cat('fit: admitted two-model serial workflow\n');flush.console()
  run_apim_workflow(cfg,stages=c('fit','parse','effects','validate'))
  charls_render_apim_swap(cfg,file.path(root,'report_swap'))
  charls_swap_assert(identical(unname(vapply(paths,charls_swap_sha,'')),unname(hashes)),'Source snapshot changed during workflow')
  complete<-list(status='WORKFLOW_INTERNAL_VALIDATE_PASS',attempt_id=request$attempt_id,models=expected,
    scientific_released=FALSE,config_sha256=request$config_sha256,grant_sha256=request$grant_sha256,
    source_hashes=as.list(hashes),preparation_sha256=charls_swap_sha(file.path(root,'prepared_swap','preparation_receipt.json')),
    display_receipt_sha256=charls_swap_sha(file.path(root,'report_swap','audit','community_display_receipt.json')),
    workflow_validation_sha256=charls_swap_sha(file.path(root,'models_run','validation.json')))
  destination<-file.path(root,'DRIVER_COMPLETE.json')
  connection<-file(destination,open='wx');on.exit(close(connection),add=TRUE)
  writeLines(jsonlite::toJSON(complete,auto_unbox=TRUE,pretty=TRUE,null='null'),connection)
  cat('finished: internal validation passed; independent scientific adoption remains pending\n');flush.console()
  invisible(complete)
}

if(sys.nframe()==0L) {
  args<-commandArgs(TRUE)
  stopifnot(length(args)==2L,identical(args[1],'--request'))
  charls_apim_swap_driver(args[2])
}
