# 可复用双人模型执行入口；不清空.GlobalEnv，不隐式安装包。
# 连续结局、显式完整案例、可区分成员；推断合同禁止隐式替换。
apim_script_dir <- local({
  files<-vapply(sys.frames(),function(e)if(is.null(e$ofile))'' else as.character(e$ofile)[1],character(1))
  files<-files[nzchar(files)];if(!length(files))stop('Load workflow.R using source()')
  dirname(normalizePath(tail(files,1),winslash='/',mustWork=TRUE))
})
source(file.path(apim_script_dir,'results.R'),local=TRUE)
apim_loaded_code_hashes <- vapply(file.path(apim_script_dir,c('workflow.R','results.R')),
  function(p)digest::digest(p,algo='sha256',file=TRUE),character(1))
apim_sha <- function(x, file=FALSE) digest::digest(x, algo='sha256', file=file)
apim_json <- function(x, path) {
  tmp <- paste0(path,'.tmp'); jsonlite::write_json(x,tmp,auto_unbox=TRUE,pretty=TRUE,null='null')
  stopifnot(file.rename(tmp,path))
}
apim_progress <- function(stage, message) {
  cat(stage,message,'\n');flush.console()
  if(exists('clauder_progress',mode='function'))clauder_progress(stage,message)
}

validate_apim_config <- function(config) {
  for(p in c('MplusAutomation','digest','jsonlite','ps'))
    if(!requireNamespace(p,quietly=TRUE))stop('Missing package: ',p)
  required <- c('data','output_dir','engine','python','cluster','row_id','models','missing',
                'missing_policy','transform','inference','resource')
  if(!all(required %in% names(config)))stop('Missing config fields: ',paste(setdiff(required,names(config)),collapse=', '))
  supported_config<-c(required,'bootstrap')
  if(length(setdiff(names(config),supported_config)))stop('Unsupported config fields: ',paste(setdiff(names(config),supported_config),collapse=', '))
  stopifnot(file.exists(config$data),file.exists(config$engine),file.exists(config$python),length(config$models)>0,
    identical(config$missing_policy,'complete_case'), config$transform %in% c('none','pooled_center','pooled_z'),
    length(config$inference)==1,config$inference%in%c('spouse_cluster_MLR_delta','row_ML_BCbootstrap'))
  if(identical(config$inference,'row_ML_BCbootstrap')) {
    b<-config$bootstrap
    stopifnot(is.list(b),setequal(names(b),c('draws','resampling_unit','seed_policy')),
      length(b$draws)==1,is.numeric(b$draws),is.finite(b$draws),b$draws>=2,b$draws<=.Machine$integer.max,
      b$draws==as.integer(b$draws),identical(b$resampling_unit,'row'),
      identical(b$seed_policy,'engine_default_not_user_controlled'))
  } else stopifnot(is.null(config$bootstrap))
  ids <- vapply(config$models,`[[`,'','id')
  stopifnot(!anyDuplicated(ids),all(grepl('^[A-Za-z][A-Za-z0-9_]*$',ids)))
  for(m in config$models) {
    supported<-c('id','family','x','y','m','w','controls','probes','filter','testing_family')
    if(length(setdiff(names(m),supported)))stop('Unsupported model fields: ',paste(setdiff(names(m),supported),collapse=', '))
    stopifnot(m$family %in% c('APIM','APIMeM','APIMoM','APIMeMoM'),
      length(m$x)==2,length(m$y)==2,length(m$testing_family)==1,nzchar(m$testing_family))
    if(m$family %in% c('APIMeM','APIMeMoM'))stopifnot(length(m$m)==2)
    else stopifnot(is.null(m$m))
    if(m$family %in% c('APIMoM','APIMeMoM')) {
      stopifnot(length(m$w)==2,length(m$probes)>=2,all(grepl('^[a-z][a-z0-9]{0,2}$',names(m$probes))),
        !anyDuplicated(names(m$probes)),all(vapply(m$probes,function(v)length(v)==2&&all(is.finite(v)),logical(1))))
      stopifnot(!anyDuplicated(vapply(m$probes,function(v)paste(v,collapse=','),character(1))))
    }
    else stopifnot(is.null(m$w),is.null(m$probes))
    stopifnot(!anyDuplicated(c(m$x,m$y,m$m,m$w,unlist(m$controls))))
    if(length(m$controls))stopifnot(all(lengths(m$controls)==2))
  }
  r<-config$resource
  stopifnot(all(c('ram_reserve_gib','incremental_peak_gib','commit_required_gib','disk_required_gib')%in%names(r)),
    all(is.finite(unlist(r))),all(unlist(r)>0),r$ram_reserve_gib>=.75)
  invisible(TRUE)
}

apim_prepare <- function(config,m,folder) {
  # ID按字符读取，避免长整数精度损失；模型列随后显式转换为数值。
  raw<-read.csv(config$data,colClasses='character',check.names=FALSE,na.strings=config$missing)
  pairs<-list(x=m$x,y=m$y)
  if(m$family %in% c('APIMeM','APIMeMoM'))pairs$m<-m$m
  if(m$family %in% c('APIMoM','APIMeMoM'))pairs$w<-m$w
  if(length(m$controls))for(j in seq_along(m$controls))pairs[[paste0('c',j)]]<-m$controls[[j]]
  used<-c(config$cluster,config$row_id,unlist(pairs))
  stopifnot(all(used%in%names(raw)),!anyNA(raw[,c(config$cluster,config$row_id)]),!anyDuplicated(raw[[config$row_id]]))
  # 可选分组筛选必须为明确的列名和值，不执行字符串表达式。
  if(!is.null(m$filter)) {
    stopifnot(all(names(m$filter)%in%names(raw)))
    for(n in names(m$filter))raw<-raw[!is.na(raw[[n]]) & raw[[n]]%in%m$filter[[n]],,drop=FALSE]
  }
  for(n in unlist(pairs)) {
    v<-suppressWarnings(as.numeric(raw[[n]]))
    if(any(!is.na(raw[[n]]) & is.na(v)))stop('Non-numeric model column: ',n)
    raw[[n]]<-v
  }
  selected<-complete.cases(raw[,used,drop=FALSE]);excluded<-raw[!selected,c(config$row_id,config$cluster),drop=FALSE]
  raw<-raw[selected,,drop=FALSE];stopifnot(nrow(raw)>0)
  d<-data.frame(cid=match(raw[[config$cluster]],unique(raw[[config$cluster]])))
  dictionary<-list();moments<-list()
  for(n in names(pairs)) {
    columns<-pairs[[n]]; v<-unlist(raw[,columns,drop=FALSE],use.names=FALSE)
    center<-if(config$transform=='none')0 else mean(v)
    scale<-if(config$transform=='pooled_z')sd(v) else 1
    stopifnot(is.finite(scale),scale>0,all(is.finite(v)))
    moments[[n]]<-list(center=center,scale=scale,sample='selected_model_complete_cases')
    for(k in 1:2) {
      alias<-paste0(n,k);d[[alias]]<-(raw[[columns[k]]]-center)/scale
      dictionary[[length(dictionary)+1L]]<-data.frame(source=columns[k],mplus=alias,role=k,construct=n)
    }
  }
  if(m$family %in% c('APIMoM','APIMeMoM')) {
    pred<-if(m$family=='APIMoM')'x' else 'm'
    for(k in 1:2)for(h in 1:2)d[[paste0('p',k,h)]]<-d[[paste0(pred,k)]]*d[[paste0('w',h)]]
  }
  stopifnot(length(unique(d$cid))>1,all(nchar(names(d))<=8))
  MplusAutomation::prepareMplusData(d,filename=file.path(folder,'data.dat'),inpfile=file.path(folder,'data_block.inp'),
    interactive=FALSE,overwrite=TRUE,quiet=TRUE)
  write.csv(data.frame(row_id=raw[[config$row_id]],cluster=raw[[config$cluster]],cid=d$cid),file.path(folder,'selected_rows.csv'),row.names=FALSE)
  write.csv(excluded,file.path(folder,'excluded_rows.csv'),row.names=FALSE)
  write.csv(do.call(rbind,dictionary),file.path(folder,'variable_dictionary.csv'),row.names=FALSE)
  apim_json(moments,file.path(folder,'transform.json'))
  list(data=d,N=nrow(d),clusters=length(unique(d$cid)),excluded=nrow(excluded),moments=moments)
}

apim_model <- function(m) {
  mediation<-m$family%in%c('APIMeM','APIMeMoM'); moderation<-m$family%in%c('APIMoM','APIMeMoM')
  lines<-character(); definitions<-character();effects<-list()
  add<-function(s)lines<<-c(lines,s)
  derived<-function(label,expression,kind,source,via,target,probe='none') {
    definitions<<-c(definitions,paste0(label,' = ',expression,';'))
    effects[[length(effects)+1L]]<<-data.frame(label=toupper(label),kind=kind,source=source,via=via,target=target,probe=probe)
  }
  for(j in 1:2) {
    for(k in 1:2) {
      add(sprintf('y%d ON x%d (c%d%d);',j,k,j,k))
      if(mediation){add(sprintf('m%d ON x%d (a%d%d);',j,k,j,k));add(sprintf('y%d ON m%d (b%d%d);',j,k,j,k))}
    }
    if(length(m$controls))for(v in seq_along(m$controls))for(k in 1:2) {
      add(sprintf('y%d ON c%d%d;',j,v,k));if(mediation)add(sprintf('m%d ON c%d%d;',j,v,k))
    }
    if(moderation) {
      add(sprintf('y%d ON w1 w2;',j))
      for(k in 1:2)for(h in 1:2)add(sprintf('y%d ON p%d%d (z%d%d%d);',j,k,h,j,k,h))
    }
  }
  add('y1 WITH y2;');if(mediation)add('m1 WITH m2;')
  for(j in 1:2)for(k in 1:2)derived(paste0('d',j,k),paste0('c',j,k),'direct',k,NA,j)
  if(moderation)for(pr in names(m$probes))for(j in 1:2)for(k in 1:2) {
    w<-m$probes[[pr]];base<-paste0(if(mediation)'b' else 'c',j,k)
    expr<-sprintf('%s + z%d%d1*(%.12g) + z%d%d2*(%.12g)',base,j,k,w[1],j,k,w[2])
    derived(paste0('s',j,k,pr),expr,'simple_slope',k,NA,j,pr)
  }
  if(mediation)for(j in 1:2)for(k in 1:2) {
    for(v in 1:2)derived(paste0('i',j,v,k),sprintf('a%d%d*b%d%d',v,k,j,v),'indirect',k,v,j)
    derived(paste0('t',j,k),sprintf('c%d%d+i%d1%d+i%d2%d',j,k,j,k,j,k),'total',k,NA,j)
    if(moderation)for(pr in names(m$probes))for(v in 1:2)
      derived(paste0('i',j,v,k,pr),sprintf('a%d%d*s%d%d%s',v,k,j,v,pr),'conditional_indirect',k,v,j,pr)
  }
  if(moderation) {
    lo<-names(m$probes)[1];hi<-names(m$probes)[2]
    for(j in 1:2)for(k in 1:2) {
      if(mediation)for(v in 1:2)derived(paste0('q',j,v,k),sprintf('i%d%d%d%s-i%d%d%d%s',j,v,k,hi,j,v,k,lo),'conditional_contrast',k,v,j,paste(hi,lo,sep='-'))
      else derived(paste0('q',j,k),sprintf('s%d%d%s-s%d%d%s',j,k,hi,j,k,lo),'slope_contrast',k,NA,j,paste(hi,lo,sep='-'))
    }
  }
  metadata<-do.call(rbind,effects);stopifnot(!anyDuplicated(metadata$label),all(nchar(metadata$label)<=8))
  new<-paste0('NEW(',paste(tolower(metadata$label),collapse=' '),');')
  # 一行一个名称，避免Mplus长行被截断。
  new<-c('NEW(',paste0('  ',tolower(metadata$label)),');')
  list(model=lines,constraints=c(new,definitions),effects=metadata)
}

apim_compile <- function(config,m,prepared,folder) {
  specification<-apim_model(m)
  native_bc<-identical(config$inference,'row_ML_BCbootstrap')
  analysis<-if(native_bc)c('ANALYSIS: TYPE = GENERAL; ESTIMATOR = ML;',
    sprintf('BOOTSTRAP = %d;',config$bootstrap$draws)) else
    c('CLUSTER = cid;','ANALYSIS: TYPE = COMPLEX; ESTIMATOR = MLR;')
  output<-if(native_bc)'OUTPUT: TECH1 CINTERVAL(BCBOOTSTRAP);' else
    'OUTPUT: STANDARDIZED TECH1 TECH3 CINTERVAL;'
  template<-c('[[init]]','iterators = run;','run = 1;',
    'filename = "model_[[run]].inp";',sprintf('outputDirectory = "%s";',normalizePath(folder,winslash='/',mustWork=TRUE)),
    '[[/init]]',paste0('TITLE: ',m$id,' [[run]];'),'DATA: FILE = data.dat;','VARIABLE:',
    'NAMES =',paste0('  ',names(prepared$data)),';',
    'USEVARIABLES =',paste0('  ',setdiff(names(prepared$data),'cid')),';',
    analysis,
    'MODEL:',specification$model,'MODEL CONSTRAINT:',specification$constraints,
    output,'SAVEDATA: RESULTS = results.dat;')
  writeLines(template,file.path(folder,'template.txt'))
  MplusAutomation::createModels(file.path(folder,'template.txt'))
  inp<-file.path(folder,'model_1.inp'); stopifnot(file.exists(inp))
  expanded<-readLines(inp,warn=FALSE)
  stopifnot(!any(grepl('[[',expanded,fixed=TRUE)),all(nchar(expanded)<=90))
  write.csv(specification$effects,file.path(folder,'effect_dictionary.csv'),row.names=FALSE)
  list(input=inp,effects=specification$effects)
}

apim_raw_check <- function(out,N) {
  if(!file.exists(out))return(FALSE)
  text<-readLines(out,warn=FALSE)
  any(grepl('THE MODEL ESTIMATION TERMINATED NORMALLY',text,fixed=TRUE)) &&
    any(grepl('Ending Time:',text,fixed=TRUE)) && !any(grepl('\\*\\*\\* ERROR',text))
}

apim_admit <- function(config) {
  # Windows宿主原生R；不能使用WSL内存替代。与其他Mplus串行，避免竞争生产队列。
  stopifnot(.Platform$OS.type=='windows')
  mem<-ps::ps_system_memory();disk<-ps::ps_disk_usage(config$output_dir)
  names_now<-tolower(ps::ps()$name)
  probe<-system2(config$python,c('-c',shQuote(paste0(
    'import ctypes,json;from ctypes import wintypes;',
    'P=type("P",(ctypes.Structure,),{"_fields_":[("cb",wintypes.DWORD)]+',
    '[(n,ctypes.c_size_t) for n in ["CommitTotal","CommitLimit","CommitPeak","PhysicalTotal","PhysicalAvailable","SystemCache","KernelTotal","KernelPaged","KernelNonpaged","PageSize"]]+',
    '[(n,wintypes.DWORD) for n in ["HandleCount","ProcessCount","ThreadCount"]]});',
    'p=P();p.cb=ctypes.sizeof(p);ok=ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(p),p.cb);',
    'assert ok;print(json.dumps({"commit_headroom_gib":(p.CommitLimit-p.CommitTotal)*p.PageSize/2**30}))'
  ))),stdout=TRUE,stderr=file.path(config$output_dir,'resource_probe.stderr.txt'))
  stopifnot(is.null(attr(probe,'status')),length(probe)>0)
  commit<-jsonlite::fromJSON(paste(probe,collapse='\n'))$commit_headroom_gib
  required<-config$resource$ram_reserve_gib+config$resource$incremental_peak_gib
  result<-list(checked_at=as.character(Sys.time()),available_gib=mem$avail/1024^3,required_gib=required,
    commit_headroom_gib=commit,disk_available_gib=as.numeric(disk$available[1])/1024^3,
    other_mplus=sum(names_now=='mplus.exe',na.rm=TRUE))
  result$admitted<-is.finite(commit)&&result$available_gib>=required&&commit>=config$resource$commit_required_gib&&
    result$disk_available_gib>=config$resource$disk_required_gib&&result$other_mplus==0
  result
}

run_apim_workflow <- function(config, stages=c('check','prepare','compile','fit','parse','effects','render','validate'), resume=TRUE) {
  if(!is.null(config$schema_version)&&identical(as.integer(config$schema_version),2L))
    return(run_apim_workflow_v2(config,stages=stages,resume=resume))
  validate_apim_config(config)
  allowed<-c('check','prepare','compile','fit','parse','effects','render','validate')
  stopifnot(all(stages%in%allowed),!anyDuplicated(stages))
  if(identical(stages,'check'))return(invisible(list(config_valid=TRUE)))
  dir.create(config$output_dir,recursive=TRUE,showWarnings=FALSE)
  root<-normalizePath(config$output_dir,winslash='/',mustWork=TRUE)
  lock<-file.path(root,'workflow.lock')
  if(!dir.create(lock,showWarnings=FALSE))stop('Workflow lock exists; verify owner identity before recovery')
  on.exit(unlink(lock,recursive=TRUE),add=TRUE)
  apim_json(list(pid=Sys.getpid(),created=as.numeric(ps::ps_create_time(ps::ps_handle()))),file.path(lock,'owner.json'))
  config_hash<-apim_sha(list(config=config,data=apim_sha(config$data,TRUE),engine=apim_sha(config$engine,TRUE),
    MplusAutomation=as.character(utils::packageVersion('MplusAutomation')),
    code=apim_loaded_code_hashes))
  checkpoint<-file.path(root,'contract.rds')
  if(file.exists(checkpoint)) {
    if(!identical(readRDS(checkpoint)$hash,config_hash))stop('Contract changed: use a new output_dir')
    if(!resume)stop('Output exists and resume=FALSE; use a new output_dir')
  } else saveRDS(list(hash=config_hash,config=config),checkpoint)
  manifest<-list()
  for(m in config$models) {
    apim_progress('workflow_model',paste(m$id,m$family))
    folder<-file.path(root,m$id);dir.create(folder,showWarnings=FALSE)
    if('prepare'%in%stages && !file.exists(file.path(folder,'prepared.rds')))
      saveRDS(apim_prepare(config,m,folder),file.path(folder,'prepared.rds'))
    prep<-readRDS(file.path(folder,'prepared.rds'))
    if('compile'%in%stages && !file.exists(file.path(folder,'compiled.rds')))
      saveRDS(apim_compile(config,m,prep,folder),file.path(folder,'compiled.rds'))
    if(!any(c('compile','fit','parse','effects','render','validate')%in%stages)) {
      manifest[[length(manifest)+1L]]<-data.frame(model_id=m$id,family=m$family,N=prep$N,clusters=prep$clusters,
        input_sha256=NA_character_,data_sha256=apim_sha(file.path(folder,'data.dat'),TRUE),executed=FALSE,scientific_released=FALSE)
      next
    }
    compiled<-readRDS(file.path(folder,'compiled.rds'));out<-sub('\\.inp$','.out',compiled$input)
    binding_file<-file.path(folder,'input_binding.rds')
    binding<-list(input=apim_sha(compiled$input,TRUE),data=apim_sha(file.path(folder,'data.dat'),TRUE))
    if(file.exists(binding_file))stopifnot(identical(readRDS(binding_file),binding)) else saveRDS(binding,binding_file)
    valid_out<-apim_raw_check(out,prep$N)
    output_binding<-file.path(folder,'output_binding.rds')
    if(valid_out && !file.exists(output_binding))stop('UNBOUND_OUTPUT: existing OUT has no verified provenance binding; review/import explicitly before reuse: ',out)
    if(valid_out && file.exists(output_binding))stopifnot(identical(readRDS(output_binding),apim_sha(out,TRUE)))
    if('fit'%in%stages && !valid_out) {
      if(file.exists(out))stop('Incomplete/failed output retained: archive and investigate before refit: ',out)
      admission<-apim_admit(config);apim_json(admission,file.path(folder,'admission.json'))
      if(!isTRUE(admission$admitted))stop('RESOURCE_HOLD; rerun the same contract after resource review')
      started<-Sys.time()
      apim_progress('workflow_fit',m$id)
      MplusAutomation::runModels(compiled$input,Mplus_command=config$engine,killOnFail=FALSE,
        replaceOutfile='never',showOutput=FALSE,logFile=file.path(folder,'run.log'))
      apim_json(list(elapsed_seconds=as.numeric(difftime(Sys.time(),started,units='secs'))),file.path(folder,'timing.json'))
      valid_out<-apim_raw_check(out,prep$N);if(!valid_out)stop('Mplus execution failed: ',out)
    }
    if(any(c('parse','effects','render','validate')%in%stages)&&!valid_out)stop('No completed output for requested stage: ',m$id)
    if(valid_out && !file.exists(output_binding))saveRDS(apim_sha(out,TRUE),output_binding)
    if('parse'%in%stages) {
      apim_progress('workflow_parse',m$id)
      cache<-file.path(folder,'parse_validation.json')
      receipt<-if(file.exists(cache))jsonlite::fromJSON(cache) else NULL
      cache_ok<-!is.null(receipt) && identical(receipt$out_sha256,apim_sha(out,TRUE)) &&
        file.exists(file.path(folder,'results.dat')) &&
        identical(receipt$results_sha256,apim_sha(file.path(folder,'results.dat'),TRUE)) &&
        identical(receipt$parser_sha256,unname(apim_loaded_code_hashes[2])) &&
        all(file.exists(file.path(folder,c('parsed.rds','precision_parameters.rds'))))
      if(!cache_ok)apim_parse(m,prep,folder,out,config)
    }
    if('effects'%in%stages)apim_effects(m,prep,folder,config)
    manifest[[length(manifest)+1L]]<-data.frame(model_id=m$id,family=m$family,N=prep$N,clusters=prep$clusters,
      input_sha256=binding$input,data_sha256=binding$data,executed=valid_out,scientific_released=FALSE)
  }
  manifest<-do.call(rbind,manifest);write.csv(manifest,file.path(root,'manifest.csv'),row.names=FALSE)
  if('effects'%in%stages) {
    e<-do.call(rbind,lapply(config$models,function(m)readRDS(file.path(root,m$id,'effects.rds'))))
    # 每个模型一次估计、每个命名效应一次检验；同族精确相同的派生表达式另列别名。
    e$p_BH<-e$p_BY<-NA_real_
    for(f in unique(e$testing_family)) {
      idx<-which(e$testing_family==f & is.finite(e$p))
      e$p_BH[idx]<-p.adjust(e$p[idx],'BH');e$p_BY[idx]<-p.adjust(e$p[idx],'BY')
    }
    write.csv(e,file.path(root,'effects.csv'),row.names=FALSE);saveRDS(e,file.path(root,'effects.rds'))
  }
  if('render'%in%stages){apim_progress('workflow_render',root);apim_render(root)}
  if('validate'%in%stages) {
    e<-readRDS(file.path(root,'effects.rds'))
    stopifnot(all(manifest$executed),!anyDuplicated(paste(e$model_id,e$label)),all(is.finite(e$estimate)),
      all(is.finite(e$lower95)),all(is.finite(e$upper95)),all(e$lower95<=e$upper95),
      all(e$lower95<=e$lower90 & e$upper90<=e$upper95),all(e$lower90<=e$upper90),
      all(!e$scientific_released))
    apim_json(list(models=nrow(manifest),effects=nrow(e),numeric_checks_pass=TRUE,
      visual_review='pending',scientific_closed=FALSE,contract_sha256=config_hash),file.path(root,'validation.json'))
  }
  writeLines(capture.output(sessionInfo()),file.path(root,'sessionInfo.txt'))
  apim_progress('workflow_finished','Requested stages finished; scientific adoption remains separate')
  invisible(manifest)
}

# v2为显式选择的扩展入口；v1默认语义保持不变。
for(apim_module in c('apim_v2_config.R','apim_v2_models.R','apim_v2_runtime.R'))
  source(file.path(apim_script_dir,apim_module),local=TRUE)
