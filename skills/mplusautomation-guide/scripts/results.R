# 连续观测变量模型精度回读；严格验证RESULTS布局，不从打印三位数推算高精度。
apim_bc_contract <- function(f,raw,requested=NULL) {
  # 原生按行BC与夫妻簇MLR是不同合同。必须核验原生声明及实际完成数。
  output<-paste(sub('!.*$','',f$input$output),collapse=' ')
  stopifnot(identical(toupper(f$summaries$Estimator),'ML'),
    grepl('CINTERVAL\\s*\\(\\s*BCBOOTSTRAP\\s*\\)',output,ignore.case=TRUE),
    is.null(f$input$variable$cluster),
    is.null(f$input$analysis$type)||identical(toupper(f$input$analysis$type),'GENERAL'))
  at<-grep('^ *Number of bootstrap draws *$',raw)
  stopifnot(length(at)==1)
  block<-raw[seq.int(at,min(at+4,length(raw)))]
  number<-function(label) {
    line<-grep(paste0('^ *',label,' +[0-9]+ *$'),block,value=TRUE)
    stopifnot(length(line)==1);as.integer(sub(paste0('^ *',label,' +'),'',line))
  }
  n<-number('Requested');done<-number('Completed')
  stopifnot(n>1L,done==n)
  if(!is.null(requested))stopifnot(length(requested)==1,n==requested)
  declared<-trimws(f$input$analysis$bootstrap)
  stopifnot(length(declared)==1,grepl('^[0-9]+(\\s*\\(STANDARD\\))?$',declared,ignore.case=TRUE),
    as.integer(sub(' .*|\\(.*','',declared))==n)
  list(requested=n,completed=done,resampling_unit='row',method='Mplus_native_ML_BCbootstrap')
}

apim_native_bc_intervals <- function(f,raw,keys,component='parameters',requested=NULL) {
  # 同一函数支持参数、MODEL INDIRECT总效应与指定中介路径；不按行号联接。
  contract<-apim_bc_contract(f,raw,requested)
  parts<-list(parameters=c('paramHeader','param'),
    indirect_overall=c('pred','outcome','summary'),
    indirect_specific=c('pred','intervening','outcome'))
  stopifnot(length(component)==1,component%in%names(parts),is.data.frame(keys),nrow(keys)>0)
  fields<-parts[[component]]
  table<-if(component=='parameters')f$parameters$ci.unstandardized else
    f$indirect$ci.unstandardized[[if(component=='indirect_overall')'overall' else 'specific']]
  stopifnot(is.data.frame(table),all(fields%in%names(keys)),all(fields%in%names(table)),
    !any(c('Group','LatentClass','BetweenWithin')%in%names(table)))
  make_key<-function(d) {
    stopifnot(!anyNA(d[,fields,drop=FALSE]))
    do.call(paste,c(lapply(d[,fields,drop=FALSE],function(x)toupper(trimws(as.character(x)))),sep='\034'))
  }
  tk<-make_key(table);kk<-make_key(keys)
  stopifnot(!anyDuplicated(tk),!anyDuplicated(kk))
  at<-match(kk,tk);stopifnot(!anyNA(at))
  cols<-c('low.5','low2.5','low5','est','up5','up2.5','up.5')
  stopifnot(all(cols%in%names(table)))
  ci<-table[at,cols,drop=FALSE]
  # MplusAutomation 1.2的indirect区间列可能全为字符；只接受完整数值字面量。
  for(n in cols)if(is.character(ci[[n]])) {
    stopifnot(!anyNA(ci[[n]]),all(grepl('^[+-]?([0-9]+(\\.[0-9]*)?|\\.[0-9]+)([eEdD][+-]?[0-9]+)?$',trimws(ci[[n]]))))
    ci[[n]]<-as.numeric(gsub('[dD]','E',trimws(ci[[n]])))
  }
  stopifnot(all(vapply(ci,is.numeric,logical(1))),all(is.finite(as.matrix(ci))))
  # BC区间可以不包含原始点估计；只验证端点次序及嵌套，绝不改造成对称区间。
  stopifnot(all(ci$low.5<=ci$low2.5 & ci$low2.5<=ci$low5 & ci$low5<=ci$up5 &
    ci$up5<=ci$up2.5 & ci$up2.5<=ci$up.5))
  ans<-data.frame(native_ci_point=ci$est,lower90=ci$low5,upper90=ci$up5,
    lower95=ci$low2.5,upper95=ci$up2.5,lower99=ci$low.5,upper99=ci$up.5,
    interval_method=contract$method,interval_precision='native_OUT_printed',
    bootstrap_requested=contract$requested,bootstrap_completed=contract$completed,
    resampling_unit=contract$resampling_unit,stringsAsFactors=FALSE)
  rownames(ans)<-NULL;ans
}

apim_parse <- function(m,prep,folder,out,config) {
  f<-MplusAutomation::readModels(out,what='all',quiet=TRUE)
  raw<-readLines(out,warn=FALSE)
  stopifnot(nrow(f$parameters$unstandardized)>0,f$summaries$Observations==prep$N)
  clusters<-grep('Number of clusters',raw,value=TRUE)
  native_bc<-identical(config$inference,'row_ML_BCbootstrap')
  if(native_bc) {
    apim_bc_contract(f,raw,config$bootstrap$draws);stopifnot(length(clusters)==0)
  } else stopifnot(identical(toupper(f$summaries$Estimator),'MLR'),length(clusters)==1,
    as.numeric(sub('.*Number of clusters +','',clusters))==prep$clusters)
  spec<-f$tech1$parameterSpecification;if('alpha'%in%names(spec))spec<-list(X=spec)
  mapping<-list()
  add<-function(id,h,p)mapping[[length(mapping)+1L]]<<-data.frame(id=as.integer(id),header=h,param=p)
  for(g in names(spec))for(mat in names(spec[[g]])) {
    x<-spec[[g]][[mat]];idx<-which(x>0 & !is.na(x),arr.ind=TRUE)
    if(!length(idx))next
    stopifnot(mat%in%c('alpha','beta','psi'))
    for(j in seq_len(nrow(idx))) {
      a<-idx[j,1];b<-idx[j,2];rn<-rownames(x)[a];cn<-colnames(x)[b]
      if(mat=='alpha')add(x[a,b],'Intercepts',cn)
      if(mat=='beta')add(x[a,b],paste0(rn,'.ON'),cn)
      if(mat=='psi')add(x[a,b],if(a==b)'Residual.Variances' else paste0(rn,'.WITH'),if(a==b)rn else cn)
    }
  }
  start<-grep('PARAMETER SPECIFICATION FOR THE ADDITIONAL PARAMETERS',raw,fixed=TRUE)
  stopifnot(length(start)==1)
  end<-which(seq_along(raw)>start & grepl('^ *STARTING VALUES *$',raw))[1];stopifnot(is.finite(end))
  block<-raw[seq.int(start,end-1)]
  for(j in grep('^ *New/Additional Parameters *$',block)) {
    nm<-strsplit(trimws(block[j+1]),' +')[[1]];ids<-as.integer(strsplit(trimws(block[j+3]),' +')[[1]])
    stopifnot(length(nm)==length(ids),!anyNA(ids))
    for(k in seq_along(ids))add(ids[k],'New.Additional.Parameters',nm[k])
  }
  d<-unique(do.call(rbind,mapping));d<-d[order(d$id),];n<-max(d$id)
  # 相等约束下多个路径可以共享一个自由参数；RESULTS仍按唯一参数编号保存。
  stopifnot(identical(sort(unique(d$id)),seq_len(n)),!anyDuplicated(paste(d$header,d$param)))
  saving<-grep('^RESULTS SAVING INFORMATION',raw);stopifnot(length(saving)==1)
  saving<-trimws(raw[saving:length(raw)])
  std<-c('StdYX standardized coefficients','StdY standardized coefficients','Std standardized coefficients')%in%saving
  stopifnot(all(std)||!any(std))
  blocks<-if(all(std))8L else 2L
  if(!native_bc)stopifnot(blocks==8L)
  first<-match('Number of Free Parameters',saving);last<-match('Save file',saving)
  stopifnot(is.finite(first),is.finite(last),last>first)
  fitnames<-saving[seq.int(first,last-1)];fitnames<-fitnames[nzchar(fitnames)]
  v<-scan(file.path(folder,'results.dat'),quiet=TRUE)
  stopifnot(length(v)==blocks*n+length(fitnames),v[blocks*n+1]==f$summaries$Parameters)
  d$estimate<-v[d$id];d$se<-v[n+d$id]
  printed<-f$parameters$unstandardized;key<-paste(printed$paramHeader,printed$param,sep='|')
  # 显式把外生协方差纳入模型时，Mplus将其均值/方差另列；按语义键映射。
  for(j in seq_len(nrow(d))) {
    alternative<-switch(d$header[j],Intercepts='Means',Residual.Variances='Variances',NULL)
    if(!is.null(alternative)&&!paste(d$header[j],d$param[j],sep='|')%in%key&&
      paste(alternative,d$param[j],sep='|')%in%key)d$header[j]<-alternative
  }
  ix<-match(paste(d$header,d$param,sep='|'),key)
  for(j in which(is.na(ix)&grepl('\\.WITH$',d$header)))
    ix[j]<-match(paste(paste0(d$param[j],'.WITH'),sub('\\.WITH$','',d$header[j]),sep='|'),key)
  stopifnot(!anyNA(ix),!anyDuplicated(ix),length(ix)==nrow(printed),
    all(is.finite(d$estimate)),all(is.finite(d$se)),all(d$se>=0),
    max(abs(d$estimate-printed$est[ix]))<=.00050001,max(abs(d$se-printed$se[ix]))<=.00050001)
  # 未带WARNING前缀的最终诊断也纳入审查；此处保守标记，不自动放行。
  diagnostics<-grep('\\*\\*\\* (WARNING|ERROR)|NON-POSITIVE|NONIDENTIFICATION|NON-IDENTIFICATION|SINGULAR|NOT CONVERGE|STANDARD ERRORS.*MAY NOT',raw,value=TRUE,ignore.case=TRUE)
  writeLines(diagnostics,file.path(folder,'raw_diagnostics.txt'))
  write.csv(d,file.path(folder,'precision_parameters.csv'),row.names=FALSE)
  saveRDS(d,file.path(folder,'precision_parameters.rds'))
  saveRDS(f,file.path(folder,'parsed.rds'))
  apim_json(list(N=prep$N,clusters=prep$clusters,inference=config$inference,results_vector_blocks=blocks,
    parameters=n,raw_diagnostic_lines=length(diagnostics),
    out_sha256=apim_sha(out,TRUE),results_sha256=apim_sha(file.path(folder,'results.dat'),TRUE),
    parser_sha256=unname(apim_loaded_code_hashes[2]),
    parsing_pass=TRUE,scientific_released=FALSE),file.path(folder,'parse_validation.json'))
}

apim_effects <- function(m,prep,folder,config,out_path=file.path(folder,'model_1.out')) {
  d<-readRDS(file.path(folder,'precision_parameters.rds'))
  dictionary<-read.csv(file.path(folder,'effect_dictionary.csv'))
  d<-d[d$header=='New.Additional.Parameters',];idx<-match(dictionary$label,d$param)
  stopifnot(!anyNA(idx),!anyDuplicated(idx),length(idx)==nrow(d))
  e<-cbind(dictionary,d[idx,c('estimate','se')]);e$model_id<-m$id;e$family<-m$family
  e$N<-prep$N;e$clusters<-prep$clusters;e$testing_family<-m$testing_family
  e$p<-ifelse(e$se>0,2*pnorm(-abs(e$estimate/e$se)),NA_real_)
  for(level in c(90,95)) {
    z<-qnorm((1+level/100)/2)
    e[[paste0('lower',level)]]<-e$estimate-z*e$se;e[[paste0('upper',level)]]<-e$estimate+z*e$se
  }
  e$interval_method<-'Mplus_MLR_spouse_cluster_delta_normal'
  e$interval_precision<-'SAVEDATA_RESULTS_normal_formula';e$p_method<-'MLR_cluster_robust_Wald_normal'
  e$resampling_unit<-'none';e$bootstrap_requested<-e$bootstrap_completed<-NA_integer_
  e$native_ci_point<-NA_real_
  if(identical(config$inference,'row_ML_BCbootstrap')) {
    f<-readRDS(file.path(folder,'parsed.rds'));raw<-readLines(out_path,warn=FALSE)
    ci<-apim_native_bc_intervals(f,raw,data.frame(paramHeader='New.Additional.Parameters',param=dictionary$label),
      requested=config$bootstrap$draws)
    stopifnot(all(abs(ci$native_ci_point-e$estimate)<=.00050001))
    for(n in names(ci))e[[n]]<-ci[[n]]
    e$p_method<-'Wald_normal_with_native_bootstrap_SE_not_BC_pvalue'
  }
  e$precision_source<-'SAVEDATA_RESULTS_TECH1_mapping'
  e$scientific_released<-FALSE
  saveRDS(e,file.path(folder,'effects.rds'));write.csv(e,file.path(folder,'effects.csv'),row.names=FALSE)
}

apim_render <- function(root) {
  for(p in c('ggplot2','officer','flextable'))if(!requireNamespace(p,quietly=TRUE))stop('Missing rendering package: ',p)
  e<-readRDS(file.path(root,'effects.rds'));figdir<-file.path(root,'figures');dir.create(figdir,showWarnings=FALSE)
  doc<-officer::read_docx()
  # 固定可读的横向页面和表列宽，避免autofit将宽表伸出纸面。
  doc<-officer::body_set_default_section(doc,officer::prop_section(
    page_size=officer::page_size(orient='landscape'),
    page_margins=officer::page_mar(top=.6,bottom=.6,left=.6,right=.6)))
  doc<-officer::body_add_par(doc,'Dyadic model results — numerical candidates; scientific review pending',style='heading 1')
  for(id in unique(e$model_id)) {
    d<-e[e$model_id==id,];d$display<-if('display_label'%in%names(d))d$display_label else paste(d$label,d$kind,d$probe,sep=' | ')
    write.csv(d,file.path(figdir,paste0(id,'_plot_data.csv')),row.names=FALSE)
    method<-unique(d$interval_method);stopifnot(length(method)==1)
    axis<-if(method=='Mplus_native_ML_BCbootstrap')'Estimate and 95% native row-bootstrap BC interval' else
      'Estimate and 95% cluster-robust delta interval'
    plot<-ggplot2::ggplot(d,ggplot2::aes(x=estimate,y=stats::reorder(display,estimate)))+
      ggplot2::geom_vline(xintercept=0,linetype=2)+ggplot2::geom_segment(ggplot2::aes(x=lower95,xend=upper95,yend=stats::reorder(display,estimate)))+
      ggplot2::geom_point()+ggplot2::theme_bw()+ggplot2::labs(title=id,x=axis,y=NULL,
        caption='All configured effects shown. Numerical candidates; scientific adoption pending.')
    for(ext in c('png','pdf','svg'))ggplot2::ggsave(file.path(figdir,paste0(id,'.',ext)),plot,width=10,height=max(4,nrow(d)*.2),limitsize=FALSE)
    tab<-d[,c('label','kind','probe','estimate','se','lower95','upper95','p','p_BH','p_BY')]
    doc<-officer::body_add_par(doc,id,style='heading 2')
    doc<-officer::body_add_par(doc,paste('Interval:',method,'; p-value:',unique(d$p_method)))
    ft<-flextable::flextable(tab)
    ft<-flextable::colformat_double(ft,j=c('estimate','se','lower95','upper95'),digits=3)
    ft<-flextable::colformat_double(ft,j=c('p','p_BH','p_BY'),digits=4)
    ft<-flextable::fontsize(ft,size=9,part='all')
    ft<-flextable::width(ft,j=names(tab),width=c(.7,1.5,.7,rep(.8,7)))
    ft<-flextable::set_table_properties(ft,layout='fixed',opts_word=list(split=FALSE,repeat_headers=TRUE))
    doc<-flextable::body_add_flextable(doc,ft)
  }
  print(doc,target=file.path(root,'tables.docx'))
}
