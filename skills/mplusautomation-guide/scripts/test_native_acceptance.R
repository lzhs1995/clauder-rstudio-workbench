# 可移植原生合成验收；路径由调用者提供。

# 独立技能验收：仅合成数据，四类模型乘两种推断再乘两个数据字典。
run_matrix <- function(suite,root,skill,engine,python,attempt='initial',prepare_only=FALSE) {
  source(file.path(skill,'scripts/workflow.R'),local=TRUE)
  source(file.path(skill,'assets/example_config.R'),local=TRUE)
  stopifnot(suite%in%c('base_mlr','base_bc','migration_mlr','migration_bc'))
  dir.create(root,recursive=TRUE,showWarnings=FALSE)
  renamed<-startsWith(suite,'migration');bc<-endsWith(suite,'bc')
  input<-file.path(root,if(renamed)'synthetic_migration.csv' else 'synthetic_base.csv')
  if(!file.exists(input)) {
    write_apim_example_data(input,renamed=renamed,seed=if(renamed)71502L else 71501L)
    if(renamed) {
      d<-read.csv(input,colClasses=c(pair_key='character',record_key='character'))
      d$pair_key<-sub('pair_','household_',d$pair_key,fixed=TRUE)
      d$record_key<-sub('row_','observation_',d$record_key,fixed=TRUE)
      write.csv(d,input,row.names=FALSE)
    }
  }
  cfg<-example_apim_config(input,file.path(root,suite),engine,python,renamed=renamed)
  if(renamed)cfg$models<-lapply(cfg$models,function(m) {
    for(role in intersect(c('x','y','m','w'),names(m)))m[[role]]<-rev(m[[role]])
    if(!is.null(m$probes))m$probes<-list(lo=c(-.75,-1.25),hi=c(.75,1.25))
    m
  })
  if(bc) {
    cfg$inference<-'row_ML_BCbootstrap'
    cfg$bootstrap<-list(draws=1000L,resampling_unit='row',seed_policy='engine_default_not_user_controlled')
  }
  saveRDS(cfg,file.path(root,paste0(suite,'_config.rds')))
  owner<-list(pid=Sys.getpid(),created=as.numeric(ps::ps_create_time(ps::ps_handle())))
  jsonlite::write_json(owner,file.path(root,paste0(suite,'_owner.json')),auto_unbox=TRUE)
  if(suite=='migration_bc' && !prepare_only) {
    original_progress<-apim_progress;live_watch<-NULL
    apim_progress<-function(stage,message) {
      original_progress(stage,message)
      if(stage=='workflow_fit' && message=='apimemom' && is.null(live_watch)) {
        # 对自己拥有的真实子进程短时调度；5秒后在仍运行时恢复优先级。
        live_watch<<-processx::process$new(python,c('-X','utf8','-B',file.path(skill,'scripts/windows_coordinator.py'),
          'watch','--output',file.path(root,'live_restore_watch'),'--owner-pid',owner$pid,
          '--owner-created',sprintf('%.9f',owner$created),'--interval','1','--duration','5'),
          stdout=file.path(root,'live_restore.stdout.log'),stderr=file.path(root,'live_restore.stderr.log'),cleanup=FALSE)
      }
    }
  }
  tag<-paste(suite,attempt,sep='_')
  monitor_dir<-file.path(root,paste0(tag,'_monitor'))
  monitor<-processx::process$new(python,c('-X','utf8','-B',file.path(skill,'scripts/windows_coordinator.py'),
    'observe','--output',monitor_dir,'--owner-pid',owner$pid,'--owner-created',sprintf('%.9f',owner$created),
    '--interval','1','--duration','3600'),stdout=file.path(root,paste0(tag,'_monitor.stdout.log')),
    stderr=file.path(root,paste0(tag,'_monitor.stderr.log')),cleanup=FALSE)
  on.exit({if(dir.exists(monitor_dir))writeLines('task_complete',file.path(monitor_dir,'stop.request'));monitor$wait(5000)},add=TRUE)
  log<-file.path(root,paste0(tag,'_console.log'));sink(log,split=TRUE);on.exit(sink(),add=TRUE)
  started<-Sys.time()
  result<-tryCatch({
    if(prepare_only) {
      run_apim_workflow(cfg,stages=c('check','prepare','compile'))
      clauder_progress('interruption_checkpoint','All synthetic inputs compiled; no Mplus launched; ready for owned-worker interruption')
      jsonlite::write_json(list(status='READY_FOR_CONTROLLED_INTERRUPTION',pid=Sys.getpid()),
        file.path(root,paste0(tag,'_interrupt_ready.json')),auto_unbox=TRUE)
      Sys.sleep(600)
      stop('Interruption test was not performed')
    }
    for(retry in 0:60) {
      attempt_result<-tryCatch({run_apim_workflow(cfg);NULL},error=function(e)e)
      if(is.null(attempt_result))break
      if(!grepl('RESOURCE_HOLD',conditionMessage(attempt_result),fixed=TRUE)||retry==60)stop(attempt_result)
      clauder_progress('resource_wait',paste('Existing Mplus or host resource hold; preserving completed outputs; retry',retry+1))
      Sys.sleep(5)
    }
    receipt<-jsonlite::fromJSON(file.path(cfg$output_dir,'validation.json'))
    stopifnot(isTRUE(receipt$numeric_checks_pass))
    list(status='WORKFLOW_FINISHED_AWAITING_INDEPENDENT_VALIDATION',suite=suite,
      elapsed_seconds=as.numeric(difftime(Sys.time(),started,units='secs')),models=receipt$models,effects=receipt$effects)
  },error=function(e)list(status='FAILED',suite=suite,error=conditionMessage(e)))
  jsonlite::write_json(result,file.path(root,paste0(tag,'_completion.json')),auto_unbox=TRUE,pretty=TRUE)
  print(result);if(result$status=='FAILED')stop(result$error)
  invisible(result)
}


# 原模板路线的独立合成测试：保留分方程控制变量和等值约束。
run_templates <- function(root,skill,engine,python) {
  source(file.path(skill,'scripts/workflow.R'),local=TRUE)
  source(file.path(skill,'scripts/compile_template_bundle.R'),local=TRUE)
  source(file.path(skill,'assets/example_config.R'),local=TRUE)
  stopifnot(!dir.exists(root));dir.create(root,recursive=TRUE)
  input<-file.path(root,'synthetic.csv');write_apim_example_data(input,seed=71503L)
  template<-c('[[init]]','iterators = step;','step = 1:2;',
    'bsecond#step = b2 b1;','filename = "pair_step[[step]].inp";',
    'outputDirectory = "UNUSED_SYNTHETIC_OUTPUT";','[[/init]]',
    'TITLE: paired mediation step [[step]];', 'DATA: FILE = data.dat;',
    'VARIABLE: NAMES = cid x1 x2 y1 y2 m1 m2 w1 w2;',
    'USEVARIABLES = x1 x2 y1 y2 m1 m2 w1 w2; CLUSTER = cid;',
    'ANALYSIS: TYPE = COMPLEX; ESTIMATOR = MLR;',
    'MODEL:', 'm1 ON x1 (a1); m1 ON x2 w1;', 'm2 ON x2 (a2); m2 ON x1 w2;',
    'y1 ON m1 (b1); y1 ON m2 x1 x2 w1;',
    'y2 ON m2 ([[bsecond#step]]); y2 ON m1 x1 x2 w2;',
    'm1 WITH m2; y1 WITH y2;',
    'MODEL CONSTRAINT: NEW(i1 i2 dif);', 'i1=a1*b1; i2=a2*[[bsecond#step]]; dif=i2-i1;',
    'OUTPUT: STANDARDIZED TECH1 TECH3 CINTERVAL;',
    'SAVEDATA: RESULTS = step[[step]]_results.dat;')
  path<-file.path(root,'original_template.txt');writeLines(template,path)
  expanded<-file.path(root,'expanded')
  compiled<-compile_mplus_template_bundle(path,apim_sha(path,TRUE),c('pair_step1.inp','pair_step2.inp'),expanded)
  raw<-read.csv(input);dat<-data.frame(cid=match(raw$couple,unique(raw$couple)),raw[,3:10]);names(dat)<-c('cid','x1','x2','y1','y2','m1','m2','w1','w2')
  MplusAutomation::prepareMplusData(dat,file.path(expanded,'data.dat'),interactive=FALSE,overwrite=TRUE,quiet=TRUE)
  records<-list();fits<-list()
  for(i in 1:2) {
    cfg<-example_apim_config(input,expanded,engine,python)
    for(k in 0:60) {
      admission<-apim_admit(cfg)
      if(isTRUE(admission$admitted))break
      if(k==60)stop('Template resource hold did not clear')
      clauder_progress('template_resource_wait',paste('step',i,'preserving external Mplus'))
      Sys.sleep(5)
    }
    inp<-file.path(expanded,paste0('pair_step',i,'.inp'))
    clauder_progress('template_fit',paste('synthetic original-template step',i))
    MplusAutomation::runModels(inp,Mplus_command=engine,killOnFail=FALSE,replaceOutfile='never',showOutput=FALSE,
      logFile=file.path(expanded,paste0('step',i,'_run.log')))
    out<-sub('inp$','out',inp);stopifnot(apim_raw_check(out,nrow(dat)))
    f<-MplusAutomation::readModels(out,what='all',quiet=TRUE);fits[[i]]<-f
    p<-f$parameters$unstandardized
    get<-function(h,n){v<-p$est[p$paramHeader==h & p$param==n];stopifnot(length(v)==1);v}
    a1<-get('M1.ON','X1');a2<-get('M2.ON','X2');b1<-get('Y1.ON','M1');b2<-get('Y2.ON','M2')
    stopifnot(abs(get('New.Additional.Parameters','I1')-a1*b1)<.002,
      abs(get('New.Additional.Parameters','I2')-a2*b2)<.002)
    if(i==2)stopifnot(b1==b2)
    stopifnot(any(p$paramHeader=='Y1.ON' & p$param=='W1'),!any(p$paramHeader=='Y1.ON' & p$param=='W2'),
      any(p$paramHeader=='Y2.ON' & p$param=='W2'),!any(p$paramHeader=='Y2.ON' & p$param=='W1'))
    write.csv(p,file.path(expanded,paste0('step',i,'_parameters.csv')),row.names=FALSE)
    saveRDS(f,file.path(expanded,paste0('step',i,'_parsed.rds')))
    records[[i]]<-list(step=i,input_sha256=apim_sha(inp,TRUE),out_sha256=apim_sha(out,TRUE),
      data_sha256=apim_sha(file.path(expanded,'data.dat'),TRUE),b1=b1,b2=b2,LL=f$summaries$LL,
      parameters=f$summaries$Parameters,N=f$summaries$Observations,
      diagnostics=f$warnings,equation_controls_verified=TRUE,product_check_tolerance=.002)
    jsonlite::write_json(records[[i]],file.path(expanded,paste0('step',i,'_receipt.json')),auto_unbox=TRUE,pretty=TRUE)
  }
  stopifnot(records[[1]]$parameters-records[[2]]$parameters==1,records[[1]]$LL>=records[[2]]$LL-.001)
  jsonlite::write_json(list(status='PASS_NATIVE_SYNTHETIC_TEMPLATE_MODELS',models=records,
    body_preserved=compiled$body_unchanged,new_mplus_calls=2,study_source_closed=FALSE),
    file.path(root,'validation.json'),auto_unbox=TRUE,pretty=TRUE)
  cat('NATIVE_TEMPLATE_FITS_PASS\n')
}


# 同一合成模型、数据、引擎，交替两轮只读与AboveNormal；不改变CPU亲和性。
run_benchmark <- function(source_dir,root,skill,engine,python) {
  source(file.path(skill,'scripts/workflow.R'),local=TRUE)
  stopifnot(!dir.exists(root));dir.create(root,recursive=TRUE)
  original<-file.path(source_dir,'model_1.inp');data<-file.path(source_dir,'data.dat')
  owner<-list(pid=Sys.getpid(),created=as.numeric(ps::ps_create_time(ps::ps_handle())))
  result<-list()
  for(i in 1:4) {
    mode<-if(i%%2==1)'observe' else 'watch';trial<-file.path(root,paste0('trial',i,'_',mode));dir.create(trial)
    file.copy(original,file.path(trial,'model_1.inp'));file.copy(data,file.path(trial,'data.dat'))
    for(k in 0:60) {
      admission<-apim_admit(list(python=python,output_dir=trial,
        resource=list(ram_reserve_gib=.75,incremental_peak_gib=.6,commit_required_gib=1.2,disk_required_gib=2)))
      if(isTRUE(admission$admitted))break
      if(k==60)stop('Benchmark resources unavailable')
      clauder_progress('benchmark_wait','Preserving external Mplus tasks');Sys.sleep(5)
    }
    jsonlite::write_json(admission,file.path(trial,'admission.json'),auto_unbox=TRUE,pretty=TRUE)
    monitor<-processx::process$new(python,c('-X','utf8','-B',file.path(skill,'scripts/windows_coordinator.py'),
      mode,'--output',file.path(trial,'monitor'),'--owner-pid',owner$pid,'--owner-created',sprintf('%.9f',owner$created),
      '--interval','1','--duration','3600'),stdout=file.path(trial,'monitor.stdout.log'),stderr=file.path(trial,'monitor.stderr.log'),cleanup=FALSE)
    Sys.sleep(1);clauder_progress('benchmark_fit',paste('trial',i,mode));started<-Sys.time()
    tryCatch(MplusAutomation::runModels(file.path(trial,'model_1.inp'),Mplus_command=engine,
      killOnFail=FALSE,showOutput=FALSE,replaceOutfile='never',logFile=file.path(trial,'run.log')),
      finally={writeLines('complete',file.path(trial,'monitor','stop.request'))})
    elapsed<-as.numeric(difftime(Sys.time(),started,units='secs'));monitor$wait(5000)
    out<-file.path(trial,'model_1.out');stopifnot(apim_raw_check(out,400))
    result[[i]]<-list(trial=i,mode=mode,elapsed_seconds=elapsed,input_sha256=apim_sha(file.path(trial,'model_1.inp'),TRUE),
      data_sha256=apim_sha(file.path(trial,'data.dat'),TRUE),out_sha256=apim_sha(out,TRUE))
    jsonlite::write_json(result,file.path(root,'timings.json'),auto_unbox=TRUE,pretty=TRUE)
  }
  cat('BENCHMARK_COMPLETE\n')
}
