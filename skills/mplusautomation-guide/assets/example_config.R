# 数据和引擎位置由调用者提供；示例没有本机用户路径。
build_apim_model_grid <- function(families,x,y,m=list(),w=list(),probes=NULL,testing_family,controls=list()) {
  # 显式变量组合清单；输出清单可审阅、删选，再交给[[init]]展开。
  stopifnot(all(families%in%c('APIM','APIMeM','APIMoM','APIMeMoM')),
    !anyDuplicated(families),length(x)>0,length(y)>0,length(testing_family)==1,nzchar(testing_family),
    all(lengths(c(x,y,m,w))==2))
  result<-list()
  for(f in families) {
    med<-f%in%c('APIMeM','APIMeMoM');mod<-f%in%c('APIMoM','APIMeMoM')
    if(med)stopifnot(length(m)>0)
    if(mod)stopifnot(length(w)>0,length(probes)>=2)
    grid<-expand.grid(x=seq_along(x),y=seq_along(y),m=if(med)seq_along(m) else 0L,w=if(mod)seq_along(w) else 0L)
    for(j in seq_len(nrow(grid))) {
      g<-grid[j,];item<-list(id=paste(tolower(f),g$x,g$y,g$m,g$w,sep='_'),family=f,
        x=x[[g$x]],y=y[[g$y]],testing_family=testing_family,controls=controls)
      if(med)item$m<-m[[g$m]]
      if(mod){item$w<-w[[g$w]];item$probes<-probes}
      result[[length(result)+1L]]<-item
    }
  }
  result
}

example_apim_config <- function(data,output_dir,engine,python,renamed=FALSE) {
  names<-if(renamed)c('exposure_a','exposure_b','response_a','response_b','mediator_a','mediator_b','context_a','context_b') else c('x_a','x_b','y_a','y_b','m_a','m_b','w_a','w_b')
  list(data=data,output_dir=output_dir,engine=engine,python=python,
    cluster=if(renamed)'pair_key' else 'couple',row_id=if(renamed)'record_key' else 'record',
    missing=c('','NA'),missing_policy='complete_case',transform='pooled_center',
    inference='spouse_cluster_MLR_delta',
    resource=list(ram_reserve_gib=.75,incremental_peak_gib=.6,commit_required_gib=1.2,disk_required_gib=2),
    models=lapply(c('APIM','APIMeM','APIMoM','APIMeMoM'),function(family) {
      m<-list(id=tolower(family),family=family,x=names[1:2],y=names[3:4],testing_family=paste0('example_',family))
      if(family%in%c('APIMeM','APIMeMoM'))m$m<-names[5:6]
      if(family%in%c('APIMoM','APIMeMoM')){m$w<-names[7:8];m$probes<-list(lo=c(-1,-1),hi=c(1,1))}
      m
    }))
}

write_apim_example_data <- function(path,renamed=FALSE,seed=4105L) {
  # 测试用合成数据；显式恢复调用者的随机数状态。
  existed<-exists('.Random.seed',envir=.GlobalEnv,inherits=FALSE)
  if(existed)old<-get('.Random.seed',envir=.GlobalEnv)
  on.exit(if(existed)assign('.Random.seed',old,envir=.GlobalEnv) else if(exists('.Random.seed',envir=.GlobalEnv,inherits=FALSE))rm('.Random.seed',envir=.GlobalEnv))
  set.seed(seed);G<-200L;n<-2L*G
  shared<-rep(rnorm(G),each=2);x1<-rnorm(n)+.3*shared;x2<-rnorm(n)+.3*shared
  w1<-rnorm(n);w2<-rnorm(n);m1<-.4*x1+.2*x2+rnorm(n);m2<-.4*x2+.2*x1+rnorm(n)
  y1<-.2*x1+.1*x2+.5*m1+.2*m2+.15*m1*w1+.1*m2*w2+rnorm(n)+.2*shared
  y2<-.2*x2+.1*x1+.5*m2+.2*m1+.15*m2*w2+.1*m1*w1+rnorm(n)+.2*shared
  d<-data.frame(couple=rep(sprintf('pair_%04d',seq_len(G)),each=2),record=sprintf('row_%04d',seq_len(n)),
    x_a=x1,x_b=x2,y_a=y1,y_b=y2,m_a=m1,m_b=m2,w_a=w1,w_b=w2)
  if(renamed)names(d)<-c('pair_key','record_key','exposure_a','exposure_b','response_a','response_b','mediator_a','mediator_b','context_a','context_b')
  write.csv(d,path,row.names=FALSE);invisible(path)
}
