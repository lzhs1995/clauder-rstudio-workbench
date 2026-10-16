# 非估计验收：仅合成数据的配置/模板及伪造解析对象的拒绝分支。
# 不调用runModels，不启动Mplus，不触碰研究源文件。
test_native_bc_contract <- function(skill_root,output_dir,engine,python) {
  source(file.path(skill_root,'scripts/workflow.R'),local=TRUE)
  source(file.path(skill_root,'assets/example_config.R'),local=TRUE)
  dir.create(output_dir,recursive=TRUE,showWarnings=FALSE)
  data<-file.path(output_dir,'synthetic.csv');write_apim_example_data(data,renamed=TRUE)
  cfg<-example_apim_config(data,file.path(output_dir,'compiled'),engine,python,renamed=TRUE)
  cfg$inference<-'row_ML_BCbootstrap'
  cfg$bootstrap<-list(draws=1000L,resampling_unit='row',seed_policy='engine_default_not_user_controlled')
  check<-list();record<-function(name,value){stopifnot(isTRUE(value));check[[name]]<<-TRUE}
  rejected<-function(expr)inherits(tryCatch(force(expr),error=function(e)e),'error')
  record('valid_explicit_row_BC_config',isTRUE(validate_apim_config(cfg)))
  bad<-cfg;bad$bootstrap$resampling_unit<-'couple';record('reject_cluster_substitution',rejected(validate_apim_config(bad)))
  bad<-cfg;bad$bootstrap$seed_policy<-'BSEED';record('reject_bayes_seed_as_bootstrap_seed',rejected(validate_apim_config(bad)))
  bad<-cfg;bad$bootstrap$draws<-10.5;record('reject_fractional_draw_count',rejected(validate_apim_config(bad)))
  bad<-cfg;bad$inference<-'spouse_cluster_MLR_delta';record('reject_MLR_with_bootstrap',rejected(validate_apim_config(bad)))
  run_apim_workflow(cfg,stages=c('check','prepare','compile'))
  for(m in cfg$models) {
    inp<-readLines(file.path(cfg$output_dir,m$id,'model_1.inp'),warn=FALSE)
    record(paste0(m$family,'_ML_BC_no_CLUSTER'),any(grepl('ESTIMATOR = ML;',inp,fixed=TRUE)) &&
      any(grepl('CINTERVAL(BCBOOTSTRAP)',inp,fixed=TRUE)) && !any(grepl('CLUSTER =',inp,fixed=TRUE)))
  }
  # 特意把CI点放在区间外：BC允许此现象，不能沿用正态区间的点包含条件。
  tab<-data.frame(paramHeader='New.Additional.Parameters',param='I111',
    low.5=1,low2.5=2,low5=3,est=0,up5=4,up2.5=5,up.5=6,check.names=FALSE)
  f<-list(summaries=list(Estimator='ML'),input=list(analysis=list(type='GENERAL',bootstrap='1000'),
    variable=list(),output='CINTERVAL(BCBOOTSTRAP);'),parameters=list(ci.unstandardized=tab))
  raw<-c('Number of bootstrap draws','  Requested 1000','  Completed 1000')
  keys<-tab[,c('paramHeader','param')]
  ci<-apim_native_bc_intervals(f,raw,keys,requested=1000L)
  record('asymmetric_BC_point_outside_allowed',ci$native_ci_point==0 && ci$lower95==2 && ci$upper95==5)
  wrong<-f;wrong$input$output<-'CINTERVAL; ! CINTERVAL(BCBOOTSTRAP);'
  record('reject_commented_BC_declaration',rejected(apim_native_bc_intervals(wrong,raw,keys)))
  wrong<-f;wrong$parameters$ci.unstandardized<-rbind(tab,tab)
  record('reject_duplicate_parameter_key',rejected(apim_native_bc_intervals(wrong,raw,keys)))
  wrong<-f;wrong$parameters$ci.unstandardized$low2.5<-NA_real_
  record('reject_missing_endpoint',rejected(apim_native_bc_intervals(wrong,raw,keys)))
  chars<-f;chars$parameters$ci.unstandardized$low2.5<-'2.000D+0'
  record('accept_verified_numeric_character_column',apim_native_bc_intervals(chars,raw,keys)$lower95==2)
  wrong<-chars;wrong$parameters$ci.unstandardized$low2.5<-'********'
  record('reject_unavailable_numeric_string',rejected(apim_native_bc_intervals(wrong,raw,keys)))
  wrong<-f;wrong$input$variable$cluster<-'CID'
  record('reject_native_cluster_claim',rejected(apim_native_bc_intervals(wrong,raw,keys)))
  record('reject_incomplete_bootstrap',rejected(apim_native_bc_intervals(f,sub('Completed 1000','Completed 999',raw),keys)))
  record('reject_changed_draw_contract',rejected(apim_native_bc_intervals(f,raw,keys,requested=500)))
  wrong<-keys;wrong$param<-'I999';record('reject_missing_effect_key',rejected(apim_native_bc_intervals(f,raw,wrong)))
  wrong<-f;wrong$parameters$ci.unstandardized$Group<-'MALE'
  record('reject_unmapped_group_dimension',rejected(apim_native_bc_intervals(wrong,raw,keys)))
  result<-list(status='PASS_NON_ESTIMATING_CONTRACT_TESTS',checks=check,new_mplus_calls=0,
    native_fit_acceptance=FALSE,scientific_closed=FALSE,code_sha256=apim_loaded_code_hashes)
  apim_json(result,file.path(output_dir,'non_estimating_tests.json'))
  cat('PASS non-estimating BC checks:',length(check),'\n');invisible(result)
}
