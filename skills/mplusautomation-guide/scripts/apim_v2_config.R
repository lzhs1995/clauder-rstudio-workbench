# v2配置与只读执行计划；不根据变量名推测研究角色。
apim_v2_assert <- function(ok, message) if(!isTRUE(ok))stop(message,call.=FALSE)
apim_v2_default <- function(x, fallback) if(is.null(x))fallback else x
apim_v2_fields <- function(x, allowed, label) {
  bad<-setdiff(names(x),allowed)
  apim_v2_assert(!length(bad),paste(label,'unsupported fields:',paste(bad,collapse=', ')))
}
apim_v2_names <- function(x,label) {
  apim_v2_assert(is.list(x)&&length(x)>0&&!is.null(names(x))&&
    all(grepl('^[A-Za-z][A-Za-z0-9_]*$',names(x)))&&!anyDuplicated(tolower(names(x))),paste('Invalid names:',label))
}
apim_v2_root <- function(path) {
  apim_v2_assert(length(path)==1&&is.character(path)&&nzchar(path)&&
    !grepl('[\r\n";]',path)&&!any(strsplit(gsub('\\','/',path,fixed=TRUE),'/',fixed=TRUE)[[1]]=='..'),
    'Unsafe path')
  path<-gsub('\\','/',path,fixed=TRUE)
  apim_v2_assert(grepl('^(/|[A-Za-z]:/)',path),'Use an absolute path')
  tail<-character();p<-path
  while(!file.exists(p)&&!dir.exists(p)){tail<-c(basename(p),tail);q<-dirname(p);stopifnot(q!=p);p<-q}
  p<-normalizePath(p,winslash='/',mustWork=TRUE)
  for(x in tail)p<-file.path(p,x)
  sub('/+$','',gsub('\\','/',p,fixed=TRUE))
}
apim_v2_inside <- function(path,root) {
  a<-tolower(apim_v2_root(path));b<-tolower(apim_v2_root(root))
  identical(a,b)||startsWith(a,paste0(b,'/'))
}
apim_v2_path_check <- function(config) {
  root<-apim_v2_root(config$output_dir)
  sources<-c(config$data,unlist(lapply(config$template_bundles,function(x)c(x$template,x$data)),use.names=FALSE))
  for(p in sources) {
    apim_v2_assert(file.exists(p),paste('Missing source:',p))
    apim_v2_assert(!apim_v2_inside(p,root)&&!apim_v2_inside(root,dirname(p)),
      paste('Run root overlaps source directory:',p))
  }
  for(p in config$protected_roots)apim_v2_assert(!apim_v2_inside(root,p)&&!apim_v2_inside(p,root),'Protected root overlap')
  root
}
apim_v2_filter <- function(data,filter) {
  if(!length(filter))return(data)
  apim_v2_assert(all(names(filter)%in%names(data)),'Missing sample filter column')
  keep<-rep(TRUE,nrow(data))
  for(n in names(filter))keep<-keep & !is.na(data[[n]]) & data[[n]]%in%filter[[n]]
  data[keep,,drop=FALSE]
}
apim_v2_pairs <- function(x,label) {
  apim_v2_names(x,label)
  apim_v2_assert(all(vapply(x,function(z)is.character(z)&&length(z)==2&&!anyNA(z)&&!anyDuplicated(z),logical(1))),
    paste('Expected distinct two-member columns:',label))
}
apim_v2_validate_w <- function(w) {
  apim_v2_fields(w,c('columns','scope','type','levels','reference'), 'moderator')
  apim_v2_assert(w$scope%in%c('paired','shared')&&w$type%in%c('continuous','binary','categorical'),'Invalid moderator declaration')
  apim_v2_assert(is.character(w$columns)&&length(w$columns)==if(w$scope=='shared')1L else 2L,'Moderator column count')
  apim_v2_assert(!anyDuplicated(w$columns),'Shared W must use scope=shared, not duplicate columns')
  if(w$type!='continuous') {
    apim_v2_assert(length(w$levels)>=2&&!anyDuplicated(as.character(w$levels))&&length(w$reference)==1&&w$reference%in%w$levels,
      'Categorical moderator requires levels and reference')
    if(w$type=='binary')apim_v2_assert(length(w$levels)==2,'Binary moderator needs two levels')
  } else apim_v2_assert(is.null(w$levels)&&is.null(w$reference),'Continuous moderator cannot have categorical levels')
}
plan_apim_workflow <- function(config) {
  if(is.null(config$schema_version)||identical(as.integer(config$schema_version),1L)) {
    validate_apim_config(config)
    return(list(schema_version=1L,models=config$models,new_mplus_calls=0L))
  }
  apim_v2_assert(identical(as.integer(config$schema_version),2L),'Unsupported schema_version')
  apim_v2_fields(config,c('schema_version','data','output_dir','engine','python','row_id','cluster','members',
    'missing','missing_policy','samples','transform','designs','inference','bootstrap','resource','protected_roots',
    'execution','presentation','testing','template_bundles','data_mode','data_columns','data_expected_sha256'), 'config')
  needed<-c('data','output_dir','engine','python','row_id','cluster','members','missing','missing_policy','samples','transform','designs','inference','resource')
  apim_v2_assert(all(needed%in%names(config)),paste('Missing config fields:',paste(setdiff(needed,names(config)),collapse=',')))
  apim_v2_assert(identical(config$missing_policy,'complete_case'),'Only explicit complete_case is implemented for new data')
  apim_v2_assert(apim_v2_default(config$data_mode,'csv')%in%c('csv','archived_dat'),'Unsupported data mode')
  apim_v2_assert(file.exists(config$engine)&&file.exists(config$python),'Resolve engine and native Python explicitly')
  apim_v2_assert(length(config$members)==2&&!anyDuplicated(config$members),'Declare two distinguishable member labels')
  apim_v2_assert(length(config$row_id)==1&&length(config$cluster)==1,'One record ID and one cluster ID required')
  apim_v2_fields(config$resource,c('ram_reserve_gib','incremental_peak_gib','commit_required_gib','disk_required_gib'),'resource')
  rv<-unlist(config$resource)
  apim_v2_assert(length(rv)==4&&is.numeric(rv)&&all(is.finite(rv))&&all(rv>0)&&config$resource$ram_reserve_gib>=.75,'Invalid resource reservations')
  apim_v2_fields(config$execution,c('max_parallel','processor_budget','wait_limit_seconds','host_registry','calibration'),'execution')
  apim_v2_assert(apim_v2_default(config$execution$max_parallel,1L)%in%1:2,'Supported local slots: one or two')
  apim_v2_fields(config$presentation,c('profile','title','digits'),'presentation')
  apim_v2_assert(apim_v2_default(config$presentation$profile,'generic')%in%c('generic','chapter4'),'Unsupported presentation profile')
  apim_v2_fields(config$testing,c('adjustment','kinds'),'testing')
  apim_v2_assert(apim_v2_default(config$testing$adjustment,'none')%in%c('none','BH','BY'),'Choose none, BH or BY explicitly')
  apim_v2_assert(config$inference%in%c('spouse_cluster_MLR_delta','row_ML_BCbootstrap'),'Unsupported inference')
  if(config$inference=='row_ML_BCbootstrap') {
    b<-config$bootstrap
    apim_v2_assert(is.list(b)&&is.numeric(b$draws)&&length(b$draws)==1&&is.finite(b$draws)&&b$draws>=2&&b$draws==as.integer(b$draws)&&
      identical(b$resampling_unit,'row')&&identical(b$seed_policy,'engine_default_not_user_controlled'),'Explicit native row BC contract required')
  } else apim_v2_assert(is.null(config$bootstrap),'Bootstrap must not be silently ignored in MLR mode')
  root<-apim_v2_path_check(config)
  apim_v2_names(config$samples,'samples');apim_v2_names(config$designs,'designs')
  for(s in config$samples)apim_v2_fields(s,c('filter'),'sample')
  tr<-config$transform
  apim_v2_fields(tr,c('scheme','reference','overrides'),'transform')
  apim_v2_assert(tr$scheme%in%c('none','pooled_center','pooled_z')&&tr$reference%in%c('analysis_rows',names(config$samples)),'Invalid scale/reference sample')
  if(length(tr$overrides))apim_v2_assert(all(names(tr$overrides)%in%c('x','m','w','y'))&&all(unlist(tr$overrides)%in%c('none','pooled_center','pooled_z')),'Invalid transform override')
  if(identical(config$data_mode,'archived_dat'))apim_v2_assert(length(config$data_columns)>0&&!is.null(config$data_expected_sha256)&&
    identical(config$data_expected_sha256,apim_sha(config$data,TRUE))&&tr$scheme=='none'&&!length(tr$overrides),
    'Archived DAT requires exact hash, columns and no transformation')
  models<-list();grids<-list()
  for(did in names(config$designs)) {
    d<-config$designs[[did]]
    apim_v2_fields(d,c('family','x','y','m','w','samples','steps','controls','covariances','probes','contrasts','probes_by_w','contrasts_by_w','testing_family','execute'),paste('design',did))
    apim_v2_assert(d$family%in%c('APIM','APIMeM','APIMoM','APIMeMoM'),'Unsupported family')
    med<-d$family%in%c('APIMeM','APIMeMoM');mod<-d$family%in%c('APIMoM','APIMeMoM')
    apim_v2_pairs(d$x,'x');apim_v2_pairs(d$y,'y')
    if(med)apim_v2_pairs(d$m,'m') else apim_v2_assert(is.null(d$m),'Unexpected mediator')
    if(mod){apim_v2_names(d$w,'w');invisible(lapply(d$w,apim_v2_validate_w))}else apim_v2_assert(is.null(d$w),'Unexpected moderator')
    apim_v2_assert(length(d$samples)>0&&all(d$samples%in%names(config$samples))&&!anyDuplicated(d$samples),'Invalid sample selection')
    apim_v2_names(d$steps,'constraint steps')
    for(s in d$steps)apim_v2_fields(s,c('equal'),'constraint step')
    apim_v2_assert(is.character(d$testing_family)&&length(d$testing_family)==1&&nzchar(d$testing_family),'Declare testing_family')
    controls<-apim_v2_default(d$controls,list())
    apim_v2_fields(controls,if(med)c('y1','y2','m1','m2') else c('y1','y2'),'equation controls')
    apim_v2_assert(all(vapply(controls,function(z)is.character(z)&&!anyDuplicated(z),logical(1))),'Invalid equation controls')
    grid<-expand.grid(sample=seq_along(d$samples),x=seq_along(d$x),y=seq_along(d$y),
      m=if(med)seq_along(d$m) else 1L,w=if(mod)seq_along(d$w) else 1L,step=seq_along(d$steps),KEEP.OUT.ATTRS=FALSE)
    for(i in seq_len(nrow(grid))) {
      g<-as.list(grid[i,]);id<-paste(did,paste(names(g),unlist(g),sep='',collapse='_'),sep='_')
      mm<-list(id=id,design=did,family=d$family,x=d$x[[g$x]],y=d$y[[g$y]],
        m=if(med)d$m[[g$m]] else NULL,w=if(mod)d$w[[g$w]] else NULL,
        sample=d$samples[g$sample],step=names(d$steps)[g$step],equal=d$steps[[g$step]]$equal,
        controls=controls,covariances=apim_v2_default(d$covariances,list()),
        probes=if(mod)apim_v2_default(d$probes_by_w[[names(d$w)[g$w]]],d$probes) else NULL,
        contrasts=if(mod)apim_v2_default(d$contrasts_by_w[[names(d$w)[g$w]]],d$contrasts) else NULL,
        testing_family=d$testing_family,axes=g,execute=is.null(d$execute)||id%in%d$execute)
      required<-c(mm$x,mm$y,mm$m,mm$w$columns)
      apim_v2_assert(!anyDuplicated(required),'X/M/W/Y columns must be distinct; declare shared moderator once')
      if(mod) {
        apim_v2_names(mm$probes,'probes');apim_v2_names(mm$contrasts,'contrasts')
        for(pr in mm$probes) {
          apim_v2_fields(pr,c('values','scale'),'probe')
          apim_v2_assert(length(pr$values)==length(mm$w$columns)&&pr$scale%in%c('raw','analysis'),'Invalid probe scale/length')
          if(mm$w$type!='continuous')apim_v2_assert(pr$scale=='raw'&&all(pr$values%in%mm$w$levels),'Categorical probes must name declared raw levels')
        }
        for(ct in mm$contrasts)apim_v2_assert(is.character(ct)&&length(ct)==2&&all(ct%in%names(mm$probes))&&ct[1]!=ct[2],
          'Contrast must explicitly name minuend and subtrahend')
      }
      models[[id]]<-mm
    }
    grids[[did]]<-grid
    if(!is.null(d$execute))apim_v2_assert(all(d$execute%in%names(models)),'Execution selection contains unknown model')
  }
  apim_v2_assert(!anyDuplicated(tolower(names(models))),'Duplicate model ID')
  if(length(config$template_bundles)) {
    apim_v2_names(config$template_bundles,'template bundles')
    apim_v2_assert(all(names(config$template_bundles)%in%names(config$designs)),'Template bundle must bind a named design')
    for(b in config$template_bundles) {
      apim_v2_fields(b,c('template','sha256','expected_files'),'template bundle')
      apim_v2_assert(identical(apim_sha(b$template,TRUE),b$sha256),'Complete template hash mismatch')
    }
  }
  # 检查所有源列；此步骤只读取，不生成DAT、不创建运行目录。
  if(apim_v2_default(config$data_mode,'csv')=='csv')cols<-names(read.csv(config$data,nrows=0,check.names=FALSE)) else cols<-config$data_columns
  for(m in models)apim_v2_assert(all(c(config$row_id,config$cluster,m$x,m$y,m$m,m$w$columns,unlist(m$controls),
    names(config$samples[[m$sample]]$filter))%in%cols),paste('Missing source column in',m$id))
  list(schema_version=2L,root=root,source_sha256=apim_sha(config$data,TRUE),models=models,grids=grids,
    candidate_count=length(models),execution_count=sum(vapply(models,`[[`,logical(1),'execute')),new_mplus_calls=0L)
}
