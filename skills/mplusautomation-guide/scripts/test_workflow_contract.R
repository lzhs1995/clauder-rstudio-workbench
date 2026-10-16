# 在原生RStudio中调用；沙盒测试，不运行Mplus、不改研究数据。
test_apim_contract <- function(skill_root,output_dir,engine,python) {
  source(file.path(skill_root,'workflow.R'),local=TRUE)
  source(file.path(dirname(skill_root),'assets/example_config.R'),local=TRUE)
  dir.create(output_dir,recursive=TRUE,showWarnings=FALSE)
  input<-file.path(output_dir,'renamed.csv');write_apim_example_data(input,renamed=TRUE,seed=4106L)
  cfg<-example_apim_config(input,file.path(output_dir,'renamed_run'),engine,python,renamed=TRUE)
  run_apim_workflow(cfg,stages=c('check','prepare','compile'))
  saveRDS(cfg,file.path(output_dir,'renamed_config.rds'))
  checks<-list(four_families_compiled=TRUE)
  bad<-cfg;bad$models[[1]]$family<-'unsupported'
  checks$unsupported_family_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$inference<-'unverified_BC'
  checks$unsupported_inference_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$models[[1]]$y<-bad$models[[1]]$x
  checks$overlapping_roles_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$models[[2]]$id<-bad$models[[1]]$id
  checks$duplicate_ids_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$models[[3]]$probes$lo<-c(0,NA)
  checks$invalid_probe_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$bootstrap<-5000L
  checks$unknown_top_level_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$models[[4]]$moderation_stage<-'a'
  checks$unknown_model_option_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$models[[3]]$probes$hi<-bad$models[[3]]$probes$lo
  checks$duplicate_probe_values_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$models[[1]]$w<-c('context_a','context_b')
  checks$inapplicable_role_rejected<-inherits(try(validate_apim_config(bad),silent=TRUE),'try-error')
  bad<-cfg;bad$transform<-'none'
  checks$changed_contract_rejected<-inherits(try(run_apim_workflow(bad,stages='compile'),silent=TRUE),'try-error')
  for(m in cfg$models) {
    folder<-file.path(cfg$output_dir,m$id);prepared<-readRDS(file.path(folder,'prepared.rds'))
    checks[[paste0(m$id,'_N_G')]]<-prepared$N==400L && prepared$clusters==200L
    dictionary<-read.csv(file.path(folder,'variable_dictionary.csv'))
    checks[[paste0(m$id,'_renamed_mapping')]]<-all(dictionary$source%in%c('exposure_a','exposure_b','response_a','response_b','mediator_a','mediator_b','context_a','context_b'))
    # 独立公式检查：已知a/b/c/z值代入生成的约束，比较直接路径乘积和条件点。
    model<-apim_model(m);env<-new.env(parent=baseenv())
    for(j in 1:2)for(k in 1:2) {
      assign(paste0('a',j,k),.1*j+.03*k,env);assign(paste0('b',j,k),.2*j+.04*k,env)
      assign(paste0('c',j,k),.3*j+.05*k,env)
      for(h in 1:2)assign(paste0('z',j,k,h),.01*j+.02*k+.03*h,env)
    }
    definitions<-model$constraints[grepl(' = ',model$constraints,fixed=TRUE)]
    for(line in definitions)eval(parse(text=sub(' = ',' <- ',line,fixed=TRUE)),env)
    ok<-TRUE
    for(j in 1:2)for(k in 1:2) {
      ok<-ok && abs(get(paste0('d',j,k),env)-(.3*j+.05*k))<1e-12
      if(m$family%in%c('APIMeM','APIMeMoM'))for(v in 1:2) {
        expected<-(.1*v+.03*k)*(.2*j+.04*v)
        ok<-ok && abs(get(paste0('i',j,v,k),env)-expected)<1e-12
        if(m$family=='APIMeMoM')for(pr in names(m$probes)) {
          w<-m$probes[[pr]]
          b<-(.2*j+.04*v)+(.01*j+.02*v+.03)*w[1]+(.01*j+.02*v+.06)*w[2]
          ok<-ok && abs(get(paste0('i',j,v,k,pr),env)-(.1*v+.03*k)*b)<1e-12
        }
      }
    }
    checks[[paste0(m$id,'_formula')]]<-ok
  }
  stopifnot(all(unlist(checks)))
  apim_json(list(checks=checks,all_pass=TRUE,new_seed=4106L,engine_fits_performed=0,scientific_closed=FALSE),file.path(output_dir,'contract_tests.json'))
  cat('WORKFLOW_CONTRACT_TESTS_PASS',length(checks),'\n')
  invisible(checks)
}
