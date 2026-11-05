# Windows 单次运行驱动：准备/编译不需要授权；拟合前必须在原生 Windows 上解析同名 grant 并逐项核对（见 charls_apim_moderated_admit_grant）。
charls_apim_moderated_swap_driver <- function(request_path) {
  stopifnot(requireNamespace('jsonlite',quietly=TRUE),requireNamespace('digest',quietly=TRUE))
  request<-jsonlite::read_json(request_path,simplifyVector=TRUE)
  args0<-commandArgs(FALSE);filearg<-sub('^--file=','',args0[grepl('^--file=',args0)])
  stopifnot(length(filearg)==1)
  scripts<-dirname(normalizePath(filearg,winslash='/',mustWork=TRUE))
  source(file.path(scripts,'workflow.R'),local=TRUE)
  source(file.path(scripts,'charls_apim_moderated_swap.R'),local=TRUE)
  source(file.path(dirname(scripts),'assets','charls_apim_moderated_swap_config_v1.R'),local=TRUE)
  expected<-charls_apim_moderated_expected_models()
  charls_mod_assert(is.character(request$request_name)&&length(request$request_name)==1&&grepl('^[A-Za-z0-9_.-]+$',request$request_name),
    'Missing request name')
  charls_mod_assert(is.character(request$attempt_id)&&length(request$attempt_id)==1&&nzchar(request$attempt_id),'Missing attempt identity')
  charls_mod_assert(is.data.frame(request$expected_models)&&identical(request$expected_models[,names(expected)],expected),
    'Unexpected requested model set/order')
  root<-normalizePath(request$root,winslash='/',mustWork=TRUE)
  charls_mod_assert(!file.exists(file.path(root,'DRIVER_COMPLETE.json')),'Completed driver attempt must not be rerun')
  bound<-function(entry,label) {
    charls_mod_assert(is.list(entry)&&is.character(entry$path)&&file.exists(entry$path)&&charls_mod_hex(entry$sha256)&&
      identical(charls_mod_sha(entry$path),entry$sha256),paste('Input hash mismatch:',label))
    entry$path
  }
  couples_data<-bound(request$couples_data,'couples_data');couples_receipt<-bound(request$couples_receipt,'couples_receipt')
  couples_contract<-bound(request$couples_contract,'couples_contract')
  source_path<-bound(request$moderator_source,'moderator_source')
  contract<-charls_apim_moderated_contract_from_json(request$moderated_contract)
  cat('prepare_moderator: validating moderator contract and couple table\n');flush.console()
  moderator<-charls_apim_moderated_read_moderator(source_path,contract)
  prep<-charls_apim_moderated_attach(couples_data,couples_receipt,moderator,contract,file.path(root,'prepared_moderated'),
    couples_contract=couples_contract)
  labels<-if(is.null(request$member_labels))c('Husband','Wife') else request$member_labels
  cfg<-charls_apim_moderated_swap_config(prep$data_path,file.path(root,'models_run'),request$engine,request$python,
    protected_roots=request$protected_roots,member_labels=labels)
  plan<-plan_apim_workflow(cfg)
  actual<-data.frame(id=names(plan$models),family=vapply(plan$models,`[[`,'','family'),
    moderated_paths=vapply(plan$models,function(m)if(is.null(m$moderated_paths))'none' else m$moderated_paths,''),
    row.names=NULL,stringsAsFactors=FALSE)
  charls_mod_assert(identical(actual,expected)&&plan$execution_count==4L,'Exactly one APIMoM and three APIMeMoM models are required')
  cat('compile: preparing four declared models without Mplus\n');flush.console()
  run_apim_workflow(cfg,stages=c('check','prepare','compile'))
  charls_mod_assert(.Platform$OS.type=='windows','Fit gate requires native Windows')
  # grant 由调度者写在 mplus_window/grants/<请求名>.json；操作者把 grant 与对应窗口请求的 SHA256 写进私有请求。
  admitted<-charls_apim_moderated_admit_grant(request$grant,request$window_request,root,request$request_name,nrow(expected))
  cfg<-charls_apim_moderated_swap_config(prep$data_path,file.path(root,'models_run'),request$engine,request$python,
    protected_roots=request$protected_roots,member_labels=labels,hard_cap=admitted$hard_cap)
  charls_mod_assert(plan_apim_workflow(cfg)$execution_count<=admitted$hard_cap$max_engine_starts,'FIT_GRANT_NOT_ADMITTED: engine starts exceed hard_cap')
  started<-list(schema='CHARLS_MODERATED_FIT_STARTED_V1',request_name=request$request_name,attempt_id=request$attempt_id,
    grant_sha256=admitted$grant_sha256,window_request_sha256=admitted$window_request_sha256,hard_cap=admitted$hard_cap,
    granted_by=admitted$granted_by,granted_taipei=admitted$granted_taipei,request_sha256=charls_mod_sha(request_path),models=expected,
    moderated_preparation_sha256=charls_mod_sha(file.path(root,'prepared_moderated','moderated_preparation_receipt.json')))
  connection<-file(file.path(root,'FIT_STARTED.json'),open='wx')
  writeLines(jsonlite::toJSON(started,auto_unbox=TRUE,pretty=TRUE,null='null'),connection);close(connection)
  cat('fit: admitted four-model serial workflow\n');flush.console()
  run_apim_workflow(cfg,stages=c('fit','parse','effects','validate'))
  charls_mod_assert(identical(charls_mod_sha(couples_data),request$couples_data$sha256)&&
    identical(charls_mod_sha(source_path),request$moderator_source$sha256),'Inputs changed during workflow')
  complete<-list(status='WORKFLOW_INTERNAL_VALIDATE_PASS',request_name=request$request_name,attempt_id=request$attempt_id,
    models=expected,scientific_released=FALSE,grant_sha256=admitted$grant_sha256,hard_cap=admitted$hard_cap,
    workflow_validation_sha256=charls_mod_sha(file.path(root,'models_run','validation.json')))
  connection<-file(file.path(root,'DRIVER_COMPLETE.json'),open='wx');on.exit(close(connection),add=TRUE)
  writeLines(jsonlite::toJSON(complete,auto_unbox=TRUE,pretty=TRUE,null='null'),connection)
  cat('finished: internal validation passed; community-cluster display labels and scientific review remain separate\n');flush.console()
  invisible(complete)
}

if(sys.nframe()==0L) {
  args<-commandArgs(TRUE)
  stopifnot(length(args)==2L,identical(args[1],'--request'))
  charls_apim_moderated_swap_driver(args[2])
}
