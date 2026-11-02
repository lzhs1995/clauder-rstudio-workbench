# 数据准备、可解释的参数字典及多维模板编译。
apim_v2_read <- function(config,path) {
  if(apim_v2_default(config$data_mode,'csv')=='csv')
    read.csv(path,colClasses='character',check.names=FALSE,na.strings=config$missing)
  else {
    x<-read.table(path,colClasses='character',na.strings=config$missing,header=FALSE,check.names=FALSE)
    apim_v2_assert(ncol(x)==length(config$data_columns),'Archived DAT column mismatch')
    names(x)<-config$data_columns;x
  }
}
apim_v2_prepare <- function(config,m,raw,folder,snapshot_path=NULL) {
  archived <- identical(apim_v2_default(config$data_mode,'csv'),'archived_dat')
  if(archived) {
    apim_v2_assert(length(snapshot_path)==1&&file.exists(snapshot_path),
      'Archived DAT requires the immutable source snapshot')
    exact_copy <- file.path(folder,'source_data_exact.dat')
    apim_v2_assert(file.copy(snapshot_path,exact_copy,overwrite=FALSE),
      'Cannot preserve the archived DAT source bytes')
    apim_v2_assert(identical(apim_sha(exact_copy,TRUE),config$data_expected_sha256),
      'Archived DAT snapshot hash changed')
  }
  ids<-c(config$row_id,config$cluster)
  apim_v2_assert(!anyNA(raw[,ids,drop=FALSE])&&!anyDuplicated(raw[[config$row_id]]),'Missing or duplicate record identities')
  subset<-apim_v2_filter(raw,config$samples[[m$sample]]$filter)
  used<-unique(c(ids,m$x,m$y,m$m,m$w$columns,unlist(m$controls)))
  numeric_cols<-setdiff(used,c(ids,if(!is.null(m$w)&&m$w$type!='continuous')m$w$columns else character()))
  for(n in numeric_cols) {
    val<-suppressWarnings(as.numeric(subset[[n]]))
    apim_v2_assert(!any(!is.na(subset[[n]])&(!is.finite(val))),paste('Invalid numeric column',n))
    subset[[n]]<-val
  }
  if(!is.null(m$w)&&m$w$type!='continuous')for(n in m$w$columns)
    apim_v2_assert(all(is.na(subset[[n]])|subset[[n]]%in%as.character(m$w$levels)),paste('Unrecognized moderator level',n))
  complete<-complete.cases(subset[,used,drop=FALSE]);excluded<-subset[!complete,ids,drop=FALSE]
  if(archived) {
    apim_v2_assert(all(complete),'Archived DAT rows cannot be silently dropped')
    apim_v2_assert(nrow(subset)==nrow(raw),'Archived DAT sample filtering would change source rows; provide a source-specific DAT')
  }
  selected<-subset[complete,,drop=FALSE]
  apim_v2_assert(nrow(selected)>0&&length(unique(selected[[config$cluster]]))>1,'Insufficient selected observations/clusters')
  ref<-if(config$transform$reference=='analysis_rows')selected else
    apim_v2_filter(raw,config$samples[[config$transform$reference]]$filter)
  d<-data.frame(cid=match(selected[[config$cluster]],unique(selected[[config$cluster]])))
  dictionary<-list();moments<-list();column_alias<-character()
  add<-function(source,alias,role,construct,values,level=NA_character_) {
    d[[alias]]<<-values
    dictionary[[length(dictionary)+1L]]<<-data.frame(source=source,mplus=alias,role=role,construct=construct,level=level)
    if(is.na(level))column_alias[[source]]<<-alias
  }
  pair<-function(n,columns) {
    v<-unlist(lapply(ref[,columns,drop=FALSE],function(z){
      v<-suppressWarnings(as.numeric(z))
      apim_v2_assert(!any(!is.na(z)&!is.finite(v)),paste('Invalid transformation reference value',n))
      v}),use.names=FALSE)
    v<-v[is.finite(v)];apim_v2_assert(length(v)>1,paste('Insufficient transform reference',n))
    scheme<-apim_v2_default(config$transform$overrides[[n]],config$transform$scheme)
    center<-if(scheme=='none')0 else mean(v);scale<-if(scheme=='pooled_z')sd(v) else 1
    apim_v2_assert(is.finite(scale)&&scale>0,'Zero or invalid reference SD')
    moments[[n]]<<-list(center=center,scale=scale,reference=config$transform$reference,reference_observations=length(v),scheme=scheme)
    for(k in seq_along(columns))add(columns[k],paste0(n,k),as.character(k),n,(as.numeric(selected[[columns[k]]])-center)/scale)
  }
  pair('x',m$x);pair('y',m$y);if(length(m$m))pair('m',m$m)
  w_alias<-character();probe_values<-list()
  if(!is.null(m$w)) {
    w<-m$w
    if(w$type=='continuous') {pair('w',w$columns);w_alias<-paste0('w',seq_along(w$columns))}
    else {
      levels<-as.character(w$levels[w$levels!=w$reference])
      for(k in seq_along(w$columns))for(h in seq_along(levels)) {
        alias<-paste0('w',k,'d',h);w_alias<-c(w_alias,alias)
        add(w$columns[k],alias,if(w$scope=='shared')'shared' else as.character(k),'w',
          as.numeric(selected[[w$columns[k]]]==levels[h]),levels[h])
      }
      moments$w<-list(scheme='treatment_coding',levels=w$levels,reference=w$reference,scope=w$scope)
    }
    for(p in names(m$probes)) {
      pr<-m$probes[[p]]
      if(w$type=='continuous') {
        val<-as.numeric(pr$values);apim_v2_assert(all(is.finite(val)),'Nonfinite probe')
        if(pr$scale=='raw')val<-(val-moments$w$center)/moments$w$scale
      } else val<-unlist(lapply(pr$values,function(z)as.numeric(as.character(z)==levels)),use.names=FALSE)
      names(val)<-w_alias;probe_values[[p]]<-val
    }
  }
  control_alias<-list();control_cols<-unique(unlist(m$controls,use.names=FALSE))
  apim_v2_assert(!length(intersect(control_cols,c(m$x,m$y,m$m,m$w$columns))),'Controls overlap focal variables; specify their existing path instead')
  for(i in seq_along(control_cols))add(control_cols[i],sprintf('k%03d',i),'control','control',as.numeric(selected[[control_cols[i]]]))
  for(eq in names(m$controls))control_alias[[eq]]<-unname(column_alias[m$controls[[eq]]])
  products<-list()
  if(length(w_alias))for(k in 1:2)for(h in seq_along(w_alias)) {
    pred<-paste0(if(m$family=='APIMoM')'x' else 'm',k)
    alias<-sprintf('p%03d',length(products)+1L);d[[alias]]<-d[[pred]]*d[[w_alias[h]]]
    products[[length(products)+1L]]<-list(alias=alias,pred=pred,k=k,h=h,w=w_alias[h])
  }
  stopifnot(all(is.finite(as.matrix(d))),all(nchar(names(d))<=8))
  MplusAutomation::prepareMplusData(d,filename=file.path(folder,'data.dat'),inpfile=file.path(folder,'data_block.inp'),
    interactive=FALSE,overwrite=FALSE,quiet=TRUE)
  write.csv(data.frame(row_id=selected[[config$row_id]],cluster=selected[[config$cluster]],cid=d$cid),file.path(folder,'selected_rows.csv'),row.names=FALSE)
  write.csv(data.frame(excluded,reason=rep('missing_required_variable',nrow(excluded))),file.path(folder,'excluded_rows.csv'),row.names=FALSE)
  write.csv(do.call(rbind,dictionary),file.path(folder,'variable_dictionary.csv'),row.names=FALSE)
  if(length(products))write.csv(do.call(rbind,lapply(products,as.data.frame)),file.path(folder,'product_dictionary.csv'),row.names=FALSE)
  apim_json(moments,file.path(folder,'transform.json'))
  apim_json(list(raw=m$probes,analysis=probe_values,contrasts=m$contrasts),file.path(folder,'probe_dictionary.json'))
  if(archived) apim_json(list(mode='archived_dat',source_snapshot_sha256=config$data_expected_sha256,
    source_data_exact_sha256=apim_sha(file.path(folder,'source_data_exact.dat'),TRUE),
    mplus_data_sha256=apim_sha(file.path(folder,'data.dat'),TRUE),
    source_bytes_preserved=TRUE,adapter='character-read/explicit-column-alias/MplusAutomation-format'),
    file.path(folder,'archived_dat_receipt.json'))
  list(data=d,N=nrow(d),clusters=length(unique(d$cid)),excluded=nrow(excluded),moments=moments,
    controls=control_alias,w_alias=w_alias,products=products,probes=probe_values,selected_sha256=apim_sha(file.path(folder,'selected_rows.csv'),TRUE))
}

apim_v2_model <- function(m,prep) {
  med<-m$family%in%c('APIMeM','APIMeMoM');mod<-length(prep$w_alias)>0
  paths<-list();add_path<-function(key,target,pred)paths[[key]]<<-list(target=target,pred=pred,label=key)
  for(j in 1:2)for(k in 1:2) {
    add_path(paste0('c',j,k),paste0('y',j),paste0('x',k))
    if(med){add_path(paste0('a',j,k),paste0('m',j),paste0('x',k));add_path(paste0('b',j,k),paste0('y',j),paste0('m',k))}
  }
  if(mod)for(j in 1:2)for(p in prep$products)add_path(paste0('z',j,p$k,p$h),paste0('y',j),p$alias)
  grouped<-character()
  for(group in m$equal) {
    apim_v2_assert(is.character(group)&&length(group)>=2&&!anyDuplicated(group)&&all(group%in%names(paths)),'Unknown equality path group')
    apim_v2_assert(!length(intersect(group,grouped)),'Overlapping equality groups must be consolidated explicitly')
    for(key in group)paths[[key]]$label<-group[1]
    grouped<-c(grouped,group)
  }
  lines<-vapply(paths,function(p)sprintf('%s ON %s (%s);',p$target,p$pred,p$label),character(1))
  for(eq in names(prep$controls))for(p in prep$controls[[eq]])lines<-c(lines,sprintf('%s ON %s;',eq,p))
  if(mod)for(j in 1:2)for(p in prep$w_alias)lines<-c(lines,sprintf('y%d ON %s;',j,p))
  lines<-c(lines,'y1 WITH y2;',if(med)'m1 WITH m2;')
  for(cov in m$covariances) {
    apim_v2_assert(is.character(cov)&&length(cov)==2&&!anyDuplicated(cov)&&all(cov%in%names(prep$data))&&!'cid'%in%cov,'Invalid explicit covariance aliases')
    statement<-sprintf('%s WITH %s;',cov[1],cov[2]);reverse<-sprintf('%s WITH %s;',cov[2],cov[1])
    apim_v2_assert(!any(c(statement,reverse)%in%lines),'Duplicate covariance')
    lines<-c(lines,statement)
  }
  coefficient<-function(key)paths[[key]]$label
  effects<-list();definitions<-character();effect_labels<-character()
  derived<-function(key,expression,kind,source,via,target,probe='none') {
    label<-sprintf('e%06d',length(effects)+1L)
    effects[[length(effects)+1L]]<<-data.frame(label=toupper(label),effect_id=key,kind=kind,
      source=source,via=via,target=target,probe=probe,expression=expression,stringsAsFactors=FALSE)
    definitions<<-c(definitions,paste0(label,' = ',expression,';'));effect_labels[[key]]<<-label
    label
  }
  slope<-function(j,k,probe) {
    base<-coefficient(paste0(if(med)'b' else 'c',j,k));values<-prep$probes[[probe]]
    paste(c(base,vapply(seq_along(values),function(h)sprintf('%s*(%.15g)',coefficient(paste0('z',j,k,h)),values[h]),character(1))),collapse=' + ')
  }
  for(j in 1:2)for(k in 1:2) {
    direct<-derived(paste0('direct_x',k,'_y',j),coefficient(paste0('c',j,k)),'direct',k,NA_integer_,j)
    if(med) {
      indirect<-character()
      for(v in 1:2)indirect<-c(indirect,derived(paste0('indirect_x',k,'_m',v,'_y',j),
        paste(coefficient(paste0('a',v,k)),coefficient(paste0('b',j,v)),sep='*'),'indirect',k,v,j))
      derived(paste0('total_x',k,'_y',j),paste(c(direct,indirect),collapse=' + '),'total',k,NA_integer_,j)
    }
    if(mod)for(pr in names(prep$probes)) {
      sl<-derived(paste0('slope_',k,'_',j,'_',pr),slope(j,k,pr),'simple_slope',k,NA_integer_,j,pr)
      if(med) {
        ci<-character()
        for(v in 1:2)ci<-c(ci,derived(paste0('conditional_x',k,'_m',v,'_y',j,'_',pr),
          sprintf('%s*(%s)',coefficient(paste0('a',v,k)),slope(j,v,pr)),'conditional_indirect',k,v,j,pr))
        derived(paste0('conditional_total_x',k,'_y',j,'_',pr),paste(c(direct,ci),collapse=' + '),'conditional_total',k,NA_integer_,j,pr)
      }
    }
    if(mod)for(ct in names(m$contrasts)) {
      pair<-m$contrasts[[ct]]
      for(v in if(med)1:2 else 0L) {
        keys<-if(med)paste0('conditional_x',k,'_m',v,'_y',j,'_',pair) else paste0('slope_',k,'_',j,'_',pair)
        derived(paste0('contrast_',ct,'_x',k,'_m',v,'_y',j),paste(effect_labels[keys],collapse=' - '),
          if(med)'conditional_contrast' else 'slope_contrast',k,if(med)v else NA_integer_,j,ct)
      }
    }
  }
  dictionary<-do.call(rbind,effects)
  path_dictionary<-do.call(rbind,lapply(names(paths),function(key)data.frame(path=key,paths[[key]],stringsAsFactors=FALSE)))
  list(model=unname(lines),constraints=c('NEW(',paste0(' ',tolower(dictionary$label)),');',definitions),
    effects=dictionary,paths=path_dictionary)
}

apim_v2_input <- function(config,m,prep,spec) {
  bc<-config$inference=='row_ML_BCbootstrap'
  c(paste0('TITLE: ',m$id,';'),'DATA: FILE = data.dat;','VARIABLE:','NAMES =',paste0(' ',names(prep$data)),';',
    'USEVARIABLES =',paste0(' ',setdiff(names(prep$data),'cid')),';',
    if(bc)c('ANALYSIS: TYPE = GENERAL; ESTIMATOR = ML;',sprintf('BOOTSTRAP = %d;',config$bootstrap$draws)) else
      c('CLUSTER = cid;','ANALYSIS: TYPE = COMPLEX; ESTIMATOR = MLR;'),
    'MODEL:',spec$model,'MODEL CONSTRAINT:',spec$constraints,
    if(bc)'OUTPUT: TECH1 CINTERVAL(BCBOOTSTRAP);' else 'OUTPUT: STANDARDIZED TECH1 TECH3 CINTERVAL;',
    'SAVEDATA: RESULTS = results.dat;')
}

apim_v2_compile <- function(config,plan,prepared) {
  source(file.path(apim_script_dir,'compile_template_bundle.R'),local=TRUE)
  compiled<-list()
  for(did in names(plan$grids)) {
    models<-Filter(function(m)identical(m$design,did),plan$models);grid<-plan$grids[[did]]
    template_dir<-file.path(plan$root,'templates',did)
    expected<-paste0(vapply(models,`[[`,'','id'),'.inp')
    dimensions<-names(grid)
    pattern<-paste0(did,'_',paste(paste0(dimensions,'[[',dimensions,']]'),collapse='_'),'.inp')
    init<-c('[[init]]',paste0('iterators = ',paste(dimensions,collapse=' '),';'),
      vapply(dimensions,function(n)paste0(n,' = ',paste(sort(unique(grid[[n]])),collapse=' '),';'),character(1)),
      paste0('filename = "',pattern,'";'),'outputDirectory = "UNBOUND_OUTPUT";','[[/init]]')
    # 保留普通迭代标签，避免MplusAutomation 1.2仅条件标签模板的空表缺陷。
    body<-paste0('TITLE: ',sub('\\.inp$','',pattern),';')
    for(m in models) {
      prep<-prepared[[m$id]];spec<-apim_v2_model(m,prep)
      tags<-paste0(names(m$axes),'==',unlist(m$axes))
      body<-c(body,paste0('[[',tags,']]'),apim_v2_input(config,m,prep,spec)[-1],paste0('[[/',rev(tags),']]'))
      folder<-file.path(plan$root,'models',m$id,'attempts','001')
      write.csv(spec$effects,file.path(folder,'effect_dictionary.csv'),row.names=FALSE)
      write.csv(spec$paths,file.path(folder,'path_dictionary.csv'),row.names=FALSE)
      compiled[[m$id]]<-list(input=file.path(folder,paste0(m$id,'.inp')),output=file.path(folder,paste0(m$id,'.out')),
        folder=folder,effects=spec$effects,paths=spec$paths)
    }
    source_template<-file.path(plan$root,'templates',paste0(did,'.txt'))
    writeLines(c(init,body),source_template,useBytes=TRUE)
    supplied<-config$template_bundles[[did]]
    if(!is.null(supplied)) {
      apim_v2_assert(setequal(expected,supplied$expected_files),'Template filename contract differs from design grid')
      source_template<-supplied$template
    }
    compile_mplus_template_bundle(source_template,apim_sha(source_template,TRUE),expected,template_dir)
    for(m in models) {
      src<-file.path(template_dir,paste0(m$id,'.inp'));dest<-compiled[[m$id]]$input
      apim_v2_assert(file.copy(src,dest,overwrite=FALSE),'Cannot stage expanded input')
      text<-readLines(dest,warn=FALSE)
      apim_v2_assert(!any(grepl('[[',text,fixed=TRUE))&&all(nchar(text)<=90),'Unexpanded tag or overlong Mplus line')
      if(!is.null(supplied)) {
        # 完整模板是独立来源；只有与显式配置相同的科学正文才能复用其效应字典。
        canonical<-function(x)toupper(gsub('[[:space:]]+','',paste(sub('!.*$','',x),collapse='')))
        expected_text<-apim_v2_input(config,m,prepared[[m$id]],apim_v2_model(m,prepared[[m$id]]))
        apim_v2_assert(identical(canonical(text),canonical(expected_text)),
          'Complete template differs from declared analysis; use the standalone preserving compiler and explicit result adapter')
      }
      compiled[[m$id]]$input_sha256<-apim_sha(dest,TRUE)
    }
  }
  compiled
}
