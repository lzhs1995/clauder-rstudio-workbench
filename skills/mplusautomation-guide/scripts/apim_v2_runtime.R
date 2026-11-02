# v2阶段缓存、既有SQLite队列适配和隔离运行。
apim_v2_io <- function(config,action,payload) {
  args<-c(file.path(apim_script_dir,'apim_v2_io.py'),action,'--payload',
    jsonlite::toJSON(payload,auto_unbox=TRUE,null='null'))
  reply<-system2(config$python,vapply(args,shQuote,character(1)),stdout=TRUE,stderr=TRUE)
  if(!is.null(attr(reply,'status'))&&attr(reply,'status')!=0)stop(paste(reply,collapse='\n'))
  jsonlite::fromJSON(paste(reply,collapse='\n'),simplifyVector=FALSE)
}
apim_v2_write_json <- function(x,path) {
  dir.create(dirname(path),recursive=TRUE,showWarnings=FALSE);apim_json(x,path)
}
apim_v2_code_hash <- function(files) {
  p<-file.path(apim_script_dir,files)
  setNames(vapply(p,apim_sha,'',file=TRUE),files)
}
apim_v2_function_hash <- function(names) {
  setNames(vapply(names,function(n)apim_sha(paste(deparse(get(n,mode='function')),collapse='\n')),''),names)
}
apim_v2_adjust <- function(config,e,compiled) {
  # 约束导致的同一数量只计一次；不同模型或样本不按数值相等猜测同一检验。
  e$hypothesis_id<-NA_character_
  for(id in unique(e$model_id)) {
    d<-compiled[[id]]$effects;expanded<-character()
    for(i in seq_len(nrow(d))) {
      expr<-d$expression[i]
      for(label in names(expanded))expr<-gsub(paste0('\\b',tolower(label),'\\b'),paste0('(',expanded[[label]],')'),expr,perl=TRUE)
      expanded[[d$label[i]]]<-gsub('[[:space:]]+','',expr)
    }
    ix<-which(e$model_id==id)
    e$hypothesis_id[ix]<-paste(id,vapply(expanded[e$label[ix]],apim_sha,''),sep=':')
  }
  e$p_BH<-e$p_BY<-e$p_adjusted<-NA_real_
  method<-apim_v2_default(config$testing$adjustment,'none')
  kinds<-apim_v2_default(config$testing$kinds,unique(e$kind))
  apim_v2_assert(all(kinds%in%unique(e$kind)),'Unknown testing kind')
  e$testing_included<-e$kind%in%kinds
  for(f in unique(e$testing_family)) {
    ix<-which(e$testing_family==f&e$testing_included)
    unique_ix<-ix[!duplicated(e$hypothesis_id[ix])]
    for(method_name in c('BH','BY')) {
      adjusted<-p.adjust(e$p[unique_ix],method=method_name)
      e[ix,paste0('p_',method_name)]<-adjusted[match(e$hypothesis_id[ix],e$hypothesis_id[unique_ix])]
    }
  }
  e$p_adjusted<-if(method=='none')e$p else e[[paste0('p_',method)]]
  e$adjustment_method<-method;e
}
apim_v2_queue_setup <- function(config,plan,compiled,prepared) {
  source(file.path(apim_script_dir,'mplus_queue_worker.R'),local=TRUE)
  execution<-apim_v2_default(config$execution,list())
  cap<-as.integer(apim_v2_default(execution$max_parallel,1L));stopifnot(cap%in%1:2)
  policy<-list(memory_hold_percent=90,memory_resume_percent=85,reserve_gib=config$resource$ram_reserve_gib,
    commit_reserve_gib=config$resource$commit_required_gib,cpu_hold_percent=90,cpu_resume_percent=75,
    disk_reserve_gib=config$resource$disk_required_gib,processor_budget=as.integer(apim_v2_default(execution$processor_budget,2L)),
    windows_profile_max_age_sec=30)
  registry<-apim_v2_default(execution$host_registry,
    file.path(Sys.getenv('LOCALAPPDATA'),'mplusautomation','resource-reservations.sqlite'))
  cfg<-list(root=plan$root,library=.libPaths(),python=config$python,mplus=config$engine,
    queue_script=file.path(apim_script_dir,'mplus_queue.py'),resource_policy=policy,
    host_reservation_path=registry,apim_v2=TRUE,parallel_cap=cap,initial_parallel_limit=1L,
    temp_dir=file.path(plan$root,'audit','tmp'))
  if(!is.null(execution$calibration)) {
    cal<-jsonlite::read_json(execution$calibration)
    apim_v2_assert(isTRUE(cal$measured_engine)&&isTRUE(cal$engine_exited)&&!length(cal$errors)&&
      identical(cal$engine_sha256,apim_sha(config$engine,TRUE)),'Invalid native calibration receipt')
    apim_v2_assert(max(cal$peak_private_gib,cal$peak_rss_gib)*1.25<=config$resource$incremental_peak_gib,
      'Declared memory reservation is below the measured worker-plus-engine peak with margin')
    cfg$calibrated<-TRUE
    cfg$initial_parallel_limit<-cap
  }
  dir.create(cfg$temp_dir,recursive=TRUE,showWarnings=FALSE)
  qpath<-file.path(plan$root,'config.json')
  if(file.exists(qpath)) {
    prior<-jsonlite::read_json(qpath,simplifyVector=FALSE)
    apim_v2_assert(identical(prior$mplus,cfg$mplus),'Queue engine changed')
  } else apim_v2_write_json(cfg,qpath)
  queue_call(cfg,'init')
  for(m in plan$models) {
    if(!m$execute)next
    c<-compiled[[m$id]];data<-file.path(c$folder,'data.dat')
    fingerprint<-apim_sha(list(input=apim_sha(c$input,TRUE),data=apim_sha(data,TRUE),engine=apim_sha(config$engine,TRUE)))
    request<-list(id=m$id,script='APIM_v2',fingerprint=fingerprint,input=c$input,output=c$output,
      input_sha256=apim_sha(c$input,TRUE),input_files=list(list(path=data,sha256=apim_sha(data,TRUE))),
      processors=1L,memory_gib=config$resource$incremental_peak_gib,priority=10L,dependencies=list(),
      record=list(model_id=m$id,family=m$family,sample=m$sample,step=m$step,N=prepared[[m$id]]$N))
    request_path<-file.path(c$folder,'request.json');apim_v2_write_json(request,request_path)
    binding<-file.path(c$folder,'output_binding.rds')
    if(!file.exists(binding)&&file.exists(file.path(c$folder,'output_binding.json')))
      saveRDS(jsonlite::read_json(file.path(c$folder,'output_binding.json')),binding)
    if(file.exists(c$output)) {
      apim_v2_assert(file.exists(binding),'UNBOUND_OUTPUT: inspect originating worker and import explicitly')
      b<-readRDS(binding);apim_v2_assert(identical(b$fingerprint,fingerprint)&&identical(b$out_sha256,apim_sha(c$output,TRUE)),
        'Input/output binding mismatch')
      queue_call(cfg,'import-request','--request',request_path)
    } else queue_call(cfg,'enqueue','--request',request_path)
  }
  queue_call(cfg,'producers-done');queue_call(cfg,'enable')
  cfg
}
apim_v2_fit <- function(config,plan,compiled,prepared) {
  stopifnot(.Platform$OS.type=='windows')
  source(file.path(apim_script_dir,'mplus_queue_worker.R'),local=TRUE)
  cfg<-apim_v2_queue_setup(config,plan,compiled,prepared)
  if(!requireNamespace('processx',quietly=TRUE))stop('Missing processx')
  launcher<-file.path(plan$root,'audit','queue_launcher.R')
  writeLines(c('args<-commandArgs(TRUE)',
    sprintf('source(%s,local=TRUE)',encodeString(file.path(apim_script_dir,'mplus_queue_worker.R'),quote='"')),
    'queue_worker(args[1],args[2])'),launcher)
  children<-list();spawn<-function(slot) {
    id<-paste0('apim_',slot,'_',Sys.getpid())
    logdir<-file.path(plan$root,'workers',id);dir.create(logdir,recursive=TRUE,showWarnings=FALSE)
    child_env<-Sys.getenv();child_env[c('TMPDIR','TEMP','TMP','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS')]<-
      c(cfg$temp_dir,cfg$temp_dir,cfg$temp_dir,'1','1')
    child<-processx::process$new(file.path(R.home('bin'),'Rscript.exe'),
      c('--vanilla',launcher,file.path(plan$root,'config.json'),id),wd=plan$root,
      stdout=file.path(logdir,'stdout.log'),stderr=file.path(logdir,'stderr.log'),cleanup=FALSE,
      env=child_env)
    apim_v2_write_json(list(pid=child$get_pid(),created=as.numeric(ps::ps_create_time(ps::ps_handle(child$get_pid()))),
      id=id,launcher_sha256=apim_sha(launcher,TRUE)),file.path(logdir,'owner.json'))
    child
  }
  state<-queue_call(cfg,'status')
  apim_v2_assert(state$counts$running==0,'Prior queue worker still owns a task: observe its original job, do not submit another')
  if(state$counts$pending>0)children[[1]]<-spawn(1)
  started<-Sys.time();last_counts<-NULL
  repeat {
    state<-queue_call(cfg,'status')
    apim_v2_write_json(state,file.path(plan$root,'audit','queue_status.json'))
    counts<-unlist(state$counts)
    apim_progress('queue',paste(names(counts),counts,collapse='; '))
    if(state$counts$pending==0&&state$counts$running==0)break
    # 第二槽只能在首个模型完成、资源连续健康且队列允许时加入。
    measured<-isTRUE(cfg$calibrated)
    if(!measured&&state$counts$completed>0)for(c in compiled) {
      path<-file.path(c$folder,'resource_measurement.json')
      if(file.exists(path)) {
        cal<-jsonlite::read_json(path)
        measured<-measured||(isTRUE(cal$measured_engine)&&isTRUE(cal$engine_exited)&&
          max(cal$peak_private_gib,cal$peak_rss_gib)*1.25<=config$resource$incremental_peak_gib)
      }
    }
    if(cfg$parallel_cap==2L&&length(children)==1L&&measured&&state$limit>=2L)children[[2]]<-spawn(2)
    dead<-vapply(children,function(x)!x$is_alive(),logical(1))
    if(length(dead)&&any(dead))stop('Queue worker exited before drain; preserve job and reconcile original attempts')
    if(as.numeric(difftime(Sys.time(),started,units='secs'))>apim_v2_default(config$execution$wait_limit_seconds,14400))
      stop('Dispatcher wait limit reached; workers preserved, inspect original task identities before recovery')
    Sys.sleep(10)
  }
  for(child in children) {
    child$wait(timeout=60000)
    apim_v2_assert(!child$is_alive()&&identical(child$get_exit_status(),0L),'Worker did not exit cleanly after queue drain')
  }
  apim_v2_assert(state$counts$failed==0&&state$counts$blocked==0&&state$counts$deferred==0,'Queue includes unsuccessful requested models')
  for(m in Filter(function(x)x$execute,plan$models)) {
    c<-compiled[[m$id]];request<-jsonlite::read_json(file.path(c$folder,'request.json'))
    apim_v2_assert(apim_raw_check(c$output,prepared[[m$id]]$N),'Output failed terminal check')
    b<-jsonlite::read_json(file.path(c$folder,'output_binding.json'))
    apim_v2_assert(identical(b$fingerprint,request$fingerprint)&&identical(b$out_sha256,apim_sha(c$output,TRUE)),
      'Worker completion binding mismatch')
    saveRDS(b,file.path(c$folder,'output_binding.rds'))
  }
  invisible(state)
}

apim_v2_effects <- function(config,m,prep,c) {
  apim_effects(m,prep,c$folder,config,out_path=c$output)
  e<-readRDS(file.path(c$folder,'effects.rds'));e$sample<-m$sample;e$constraint_step<-m$step
  e$member_source<-config$members[e$source];e$member_target<-config$members[e$target]
  e$member_via<-ifelse(is.na(e$via),'',config$members[e$via])
  e$reference_condition<-if(is.null(m$w))'not_applicable' else 'analysis_W_equals_zero; categorical_reference_levels'
  e$display_label<-paste(e$kind,paste0(e$member_source,' → ',e$member_target),
    ifelse(is.na(e$via),'',paste0(' via ',e$member_via)),e$probe)
  write.csv(e,file.path(c$folder,'effects.csv'),row.names=FALSE);saveRDS(e,file.path(c$folder,'effects.rds'))
  e
}

apim_v2_render <- function(config,plan,e) {
  apim_render(plan$root)
  if(!requireNamespace('ggplot2',quietly=TRUE))stop('Missing ggplot2')
  plots<-list();figdir<-file.path(plan$root,'figures')
  for(id in unique(e$model_id)) {
    d<-e[e$model_id==id&e$kind%in%c('simple_slope','conditional_indirect','conditional_total'),,drop=FALSE]
    if(!nrow(d))next
    m<-plan$models[[id]];d$scenario<-factor(d$probe,levels=names(m$probes))
    d$path<-paste(d$member_source,d$member_via,d$member_target,sep=' → ')
    d<-d[order(d$kind,d$path,d$scenario),,drop=FALSE]
    p<-ggplot2::ggplot(d,ggplot2::aes(x=scenario,y=estimate,group=path,color=path))+
      ggplot2::geom_point(position=ggplot2::position_dodge(.3))+
      ggplot2::geom_errorbar(ggplot2::aes(ymin=lower95,ymax=upper95),width=.1,position=ggplot2::position_dodge(.3))+
      ggplot2::facet_wrap(~kind,scales='free_y')+ggplot2::theme_bw()+
      ggplot2::labs(x='Explicit moderator scenario',y='Conditional effect and 95% interval',color='Member path',
        subtitle=paste(m$sample,m$step,unique(d$interval_method),sep=' | '))
    base<-file.path(figdir,paste0(id,'_conditions'))
    write.csv(d,paste0(base,'_plot_data.csv'),row.names=FALSE)
    ggplot2::ggsave(paste0(base,'.svg'),p,width=11,height=7,device=svglite::svglite)
    ggplot2::ggsave(paste0(base,'.png'),p,width=11,height=7,dpi=160)
    ggplot2::ggsave(paste0(base,'.pdf'),p,width=11,height=7)
    plots[[id]]<-c(paste0(base,'.svg'),paste0(base,'.png'),paste0(base,'.pdf'))
  }
  # HTML使用已绑定的效应数表；不另算数值、不按显著性删选。
  escape<-function(x)gsub('"','&quot;',gsub('>','&gt;',gsub('<','&lt;',gsub('&','&amp;',as.character(x),fixed=TRUE),fixed=TRUE),fixed=TRUE),fixed=TRUE)
  columns<-c('model_id','display_label','estimate','se','lower95','upper95','interval_method')
  html<-c('<!doctype html><meta charset="utf-8"><title>APIM results</title>',
    '<style>table{border-collapse:collapse;font:14px sans-serif}th,td{border:1px solid #bbb;padding:6px}thead{display:table-header-group}</style>',
    '<table><thead><tr>',paste0('<th>',escape(columns),'</th>'),'</tr></thead><tbody>')
  for(i in seq_len(nrow(e)))html<-c(html,'<tr>',paste0('<td>',escape(unlist(e[i,columns],use.names=FALSE)),'</td>'),'</tr>')
  writeLines(c(html,'</tbody></table>'),file.path(plan$root,'tables','effects.html'),useBytes=TRUE)
  apim_v2_write_json(plots,file.path(plan$root,'audit','conditional_figures.json'))
}

run_apim_workflow_v2 <- function(config,stages=c('check','prepare','compile','fit','parse','effects','render','validate'),resume=TRUE) {
  plan<-plan_apim_workflow(config)
  apim_v2_assert(all(stages%in%c('check','prepare','compile','fit','parse','effects','render','validate'))&&!anyDuplicated(stages),'Invalid stages')
  if(identical(stages,'check'))return(invisible(plan))
  sources<-c(config$data,vapply(config$template_bundles,function(b)b$template,''))
  source_hashes<-vapply(sources,apim_sha,'',file=TRUE)
  # c(data, named template-bundle paths) retains the bundle name; unnamed
  # JSON arrays are required because the Python boundary iterates source paths.
  boundary<-apim_v2_io(config,'check',list(root=plan$root,sources=unname(as.list(sources)),protected=unname(as.list(config$protected_roots))))
  for(d in c('audit','config','prepared','templates','models','results','figures','tables'))dir.create(file.path(plan$root,d),recursive=TRUE,showWarnings=FALSE)
  lock<-file.path(plan$root,'workflow.lock')
  apim_v2_assert(dir.create(lock,showWarnings=FALSE),'Workflow already owned; reconcile original worker before resume')
  on.exit(unlink(lock,recursive=TRUE),add=TRUE)
  on.exit({
    unchanged<-identical(vapply(sources,apim_sha,'',file=TRUE),source_hashes)
    apim_v2_write_json(list(sources=as.list(source_hashes),original_unchanged=unchanged),file.path(plan$root,'audit','source_integrity.json'))
    if(!unchanged)warning('Original input changed during run')
  },add=TRUE)
  apim_json(list(pid=Sys.getpid(),created=as.numeric(ps::ps_create_time(ps::ps_handle()))),file.path(lock,'owner.json'))
  scientific<-config[setdiff(names(config),c('presentation','testing','execution','resource','output_dir','protected_roots'))]
  contract<-apim_sha(list(config=scientific,data=plan$source_sha256,engine=apim_sha(config$engine,TRUE)))
  contract_path<-file.path(plan$root,'config','contract.rds')
  if(file.exists(contract_path))apim_v2_assert(resume&&identical(readRDS(contract_path)$hash,contract),'Scientific contract changed: create a new run root')
  else saveRDS(list(hash=contract,config=scientific),contract_path)
  apim_v2_write_json(config,file.path(plan$root,'config',paste0('resolved_',apim_sha(config),'.json')))
  snap<-apim_v2_io(config,'snapshot',list(root=plan$root,sources=unname(as.list(sources)),protected=unname(as.list(config$protected_roots))))
  apim_v2_write_json(snap,file.path(plan$root,'audit','source_snapshot.json'))
  raw<-apim_v2_read(config,snap$sources[[1]]$snapshot)
  if(length(config$template_bundles))for(i in seq_along(config$template_bundles))
    config$template_bundles[[i]]$template<-snap$sources[[i+1]]$snapshot
  prepared<-list();prep_code<-apim_v2_function_hash(c('apim_v2_read','apim_v2_prepare','apim_v2_filter'))
  for(m in plan$models) {
    folder<-file.path(plan$root,'models',m$id,'attempts','001');dir.create(folder,recursive=TRUE,showWarnings=FALSE)
    path<-file.path(folder,'prepared.rds');binding<-file.path(folder,'prepared_binding.rds')
    if(!file.exists(path)) {
      apim_v2_assert('prepare'%in%stages,paste('Preparation missing:',m$id))
      apim_progress('prepare',m$id);p<-apim_v2_prepare(config,m,raw,folder,snap$sources[[1]]$snapshot);saveRDS(p,path)
      saveRDS(list(code=prep_code,data=apim_sha(file.path(folder,'data.dat'),TRUE),object=apim_sha(path,TRUE)),binding)
    }
    b<-readRDS(binding)
    apim_v2_assert(identical(b$code,prep_code)&&identical(b$data,apim_sha(file.path(folder,'data.dat'),TRUE))&&identical(b$object,apim_sha(path,TRUE)),
      'Preparation/code changed: preserve original run and use a fresh root')
    prepared[[m$id]]<-readRDS(path)
  }
  compile_path<-file.path(plan$root,'config','compiled.rds')
  if(!any(stages%in%c('compile','fit','parse','effects','render','validate')))return(invisible(plan))
  if(!file.exists(compile_path)) {
    apim_v2_assert('compile'%in%stages,'Compilation missing')
    apim_progress('compile','Native multidimensional template expansion')
    compiled<-apim_v2_compile(config,plan,prepared);saveRDS(compiled,compile_path)
    saveRDS(apim_v2_function_hash(c('apim_v2_compile','apim_v2_input','apim_v2_model')),paste0(compile_path,'.code'))
  } else {
    compiled<-readRDS(compile_path)
    apim_v2_assert(identical(readRDS(paste0(compile_path,'.code')),apim_v2_function_hash(c('apim_v2_compile','apim_v2_input','apim_v2_model'))),
      'Model compiler changed: preserve attempts and use a new run root')
  }
  for(c in compiled)apim_v2_assert(identical(c$input_sha256,apim_sha(c$input,TRUE)),'Expanded INP changed')
  if('fit'%in%stages)apim_v2_fit(config,plan,compiled,prepared)
  selected<-Filter(function(x)x$execute,plan$models);all_effects<-list();manifest<-list()
  for(m in selected) {
    c<-compiled[[m$id]];prep<-prepared[[m$id]];needed<-any(stages%in%c('parse','effects','render','validate'))
    if(!needed)next
    apim_v2_assert(apim_raw_check(c$output,prep$N),paste('No complete estimate:',m$id))
    binding<-file.path(c$folder,'output_binding.rds');apim_v2_assert(file.exists(binding),'UNBOUND_OUTPUT')
    b<-readRDS(binding);apim_v2_assert(identical(b$out_sha256,apim_sha(c$output,TRUE))&&
      identical(b$results_sha256,apim_sha(file.path(c$folder,'results.dat'),TRUE)),'Output/results hash changed')
    parse_key<-apim_sha(list(b,parser=apim_v2_code_hash('results.R'),N=prep$N,clusters=prep$clusters))
    parse_receipt<-file.path(c$folder,'v2_parse_key.rds')
    if('parse'%in%stages&&(!file.exists(parse_receipt)||!identical(readRDS(parse_receipt),parse_key))) {
      apim_progress('parse',m$id);apim_parse(m,prep,c$folder,c$output,config);saveRDS(parse_key,parse_receipt)
    }
    apim_v2_assert(file.exists(parse_receipt)&&identical(readRDS(parse_receipt),parse_key),'Parsing cache is stale: include parse stage')
    effects_key<-apim_sha(list(parse=parse_key,dictionary=apim_sha(file.path(c$folder,'effect_dictionary.csv'),TRUE),
      code=apim_v2_function_hash(c('apim_v2_effects','apim_effects')),members=config$members))
    effect_receipt<-file.path(c$folder,'v2_effect_key.rds')
    if('effects'%in%stages&&(!file.exists(effect_receipt)||!identical(readRDS(effect_receipt),effects_key))) {
      apim_v2_effects(config,m,prep,c);saveRDS(effects_key,effect_receipt)
    }
    if(any(stages%in%c('effects','render','validate')))apim_v2_assert(file.exists(effect_receipt)&&identical(readRDS(effect_receipt),effects_key),
      'Effects cache is stale: include effects stage')
    epath<-file.path(c$folder,'effects.rds')
    if(file.exists(epath))all_effects[[m$id]]<-readRDS(epath)
    manifest[[m$id]]<-data.frame(model_id=m$id,family=m$family,N=prep$N,clusters=prep$clusters,input_sha256=c$input_sha256,
      data_sha256=apim_sha(file.path(c$folder,'data.dat'),TRUE),out_sha256=b$out_sha256,executed=TRUE,scientific_released=FALSE)
  }
  if(length(manifest))write.csv(do.call(rbind,manifest),file.path(plan$root,'manifest.csv'),row.names=FALSE)
  if(length(all_effects)) {
    e<-apim_v2_adjust(config,do.call(rbind,all_effects),compiled);rownames(e)<-NULL
    saveRDS(e,file.path(plan$root,'effects.rds'));write.csv(e,file.path(plan$root,'effects.csv'),row.names=FALSE)
  }
  if('render'%in%stages){apim_v2_assert(length(all_effects)==length(selected),'Missing effects for rendering');apim_v2_render(config,plan,e)}
  if('validate'%in%stages) {
    apim_v2_assert(length(all_effects)==length(selected)&&!anyDuplicated(paste(e$model_id,e$effect_id)), 'Effect coverage mismatch')
    apim_v2_assert(all(is.finite(e$estimate))&&all(is.finite(e$lower95))&&all(e$lower95<=e$upper95),'Invalid numeric result')
    apim_v2_write_json(list(status='INTERNAL_NUMERIC_CHECKS_ONLY',models=length(selected),effects=nrow(e),
      independent_validation='pending',visual_review='pending',scientific_adoption=FALSE),file.path(plan$root,'validation.json'))
  }
  apim_v2_assert(identical(apim_sha(config$data,TRUE),plan$source_sha256),'Original input changed during run')
  apim_v2_write_json(list(source_sha256=plan$source_sha256,original_unchanged=TRUE),file.path(plan$root,'audit','source_integrity.json'))
  writeLines(capture.output(sessionInfo()),file.path(plan$root,'audit','sessionInfo.txt'))
  apim_progress('workflow_finished','Requested stages complete; retain independent acceptance requirements')
  invisible(list(plan=plan,compiled=compiled,manifest=manifest))
}
