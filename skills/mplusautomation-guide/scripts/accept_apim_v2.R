# 原生RStudio异步调用入口；每阶段有持久状态，重入复用既有输出。
accept_apim_v2 <- function(skill_root,root,engine,python,stage=c('prepare','matrix','templates','benchmark','report')) {
  source(file.path(skill_root,'scripts','workflow.R'),local=TRUE)
  source(file.path(skill_root,'assets','example_config_v2.R'),local=TRUE)
  dir.create(root,recursive=TRUE,showWarnings=FALSE)
  # Inputs live beside the run root.  Keeping them outside the root is part of
  # the isolation contract and also makes the acceptance script safe to rerun.
  fixture<-file.path(dirname(root),paste0(basename(root),'_inputs'));dir.create(fixture,recursive=TRUE,showWarnings=FALSE)
  for(b in c(FALSE,TRUE)) {
    path<-file.path(fixture,if(b)'B.csv' else 'A.csv')
    if(!file.exists(path))write_apim_v2_example_data(path,seed=if(b)9519L else 4105L,renamed=b)
  }
  status<-function(phase,message) {
    apim_progress(phase,message)
    apim_json(list(stage=phase,message=message,worker=Sys.getpid(),updated_at=format(Sys.time(),tz='UTC',usetz=TRUE)),file.path(root,'acceptance_state.json'))
  }
  configs<-list()
  for(b in c(FALSE,TRUE))for(method in c('spouse_cluster_MLR_delta','row_ML_BCbootstrap')) {
    id<-paste(if(b)'B' else 'A',if(method=='spouse_cluster_MLR_delta')'MLR' else 'BC',sep='_')
    configs[[id]]<-example_apim_config_v2(file.path(fixture,if(b)'B.csv' else 'A.csv'),file.path(root,'runs',id),engine,python,b,method)
  }
  for(id in names(configs)) {
    cfg<-configs[[id]]
    if('prepare'%in%stage){status('acceptance_compile',id);run_apim_workflow(cfg,stages=c('check','prepare','compile'))}
    if('matrix'%in%stage){status('acceptance_matrix',id);run_apim_workflow(cfg)}
  }
  if('templates'%in%stage) {
    if(!file.exists(file.path(configs$A_MLR$output_dir,'templates','apim.txt')))
      run_apim_workflow(configs$A_MLR,stages=c('check','prepare','compile'))
    cfg<-configs$A_MLR;cfg$output_dir<-file.path(root,'runs','complete_template');cfg$designs<-cfg$designs['apim']
    template<-file.path(configs$A_MLR$output_dir,'templates','apim.txt')
    cfg$template_bundles<-list(apim=list(template=template,sha256=apim_sha(template,TRUE),
      expected_files=paste0(names(plan_apim_workflow(cfg)$models),'.inp')))
    status('acceptance_complete_template','Two complete template fits');run_apim_workflow(cfg)
    configs$complete_template<-cfg
  }
  if('benchmark'%in%stage) {
    calibration<-file.path(configs$A_BC$output_dir,'models','apim_sample1_x1_y1_m1_w1_step1','attempts','001','resource_measurement.json')
    for(cap in 1:2) {
      cfg<-configs$A_BC;cfg$output_dir<-file.path(root,'runs',paste0('benchmark_',cap));cfg$designs<-cfg$designs['apim']
      cfg$designs$apim$steps<-setNames(rep(list(list(equal=list())),4),paste0('replicate',1:4))
      cfg$execution$max_parallel<-cap;cfg$execution$calibration<-calibration
      status('acceptance_benchmark',paste('slots',cap,'four fixed-specification calls'))
      started<-Sys.time();run_apim_workflow(cfg)
      apim_json(list(slots=cap,elapsed_seconds=as.numeric(difftime(Sys.time(),started,units='secs')),
        actual_overlap='verify worker and engine intervals before asserting parallel speedup'),file.path(cfg$output_dir,'benchmark.json'))
      configs[[paste0('benchmark_',cap)]]<-cfg
    }
  }
  saveRDS(configs,file.path(root,'acceptance_configs.rds'))
  status('acceptance_stage_finished',paste(stage,collapse=', '))
  invisible(configs)
}
