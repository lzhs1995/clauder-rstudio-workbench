# 自包含合成案例：只通过配置改名、交换成员、切换样本与模型规格。
write_apim_v2_example_data <- function(path,seed=4105L,renamed=FALSE) {
  existed<-exists('.Random.seed',envir=.GlobalEnv,inherits=FALSE)
  if(existed)old<-get('.Random.seed',envir=.GlobalEnv)
  on.exit(if(existed)assign('.Random.seed',old,envir=.GlobalEnv) else if(exists('.Random.seed',envir=.GlobalEnv,inherits=FALSE))rm('.Random.seed',envir=.GlobalEnv))
  set.seed(seed);n<-400L;shared<-rep(rnorm(200),each=2)
  x1<-rnorm(n)+.3*shared;x2<-rnorm(n)+.3*shared;w1<-rnorm(n);w2<-rnorm(n)
  m1<-.4*x1+.2*x2+rnorm(n);m2<-.4*x2+.2*x1+rnorm(n)
  y1<-.2*x1+.1*x2+.5*m1+.2*m2+.15*m1*w1+.1*m2*w2+rnorm(n)+.2*shared
  y2<-.2*x2+.1*x1+.5*m2+.2*m1+.15*m2*w2+.1*m1*w1+rnorm(n)+.2*shared
  d<-data.frame(pair=rep(sprintf('pair_%04d',1:200),each=2),record=sprintf('record_%04d',1:n),
    x1,x2,m1,m2,y1,y2,w1,w2,wb=rep(rep(0:1,length.out=200),each=2),
    wc=rep(rep(0:2,length.out=200),each=2),control1=rnorm(n),control2=rnorm(n),phase=rep(c('early','late'),200))
  if(renamed)names(d)<-paste0('new_',names(d))
  stopifnot(!file.exists(path));write.csv(d,path,row.names=FALSE);invisible(path)
}
example_apim_config_v2 <- function(data,output_dir,engine,python,renamed=FALSE,inference='spouse_cluster_MLR_delta') {
  nm<-function(x)if(renamed)paste0('new_',x) else x
  pair<-function(x)nm(paste0(x,if(renamed)2:1 else 1:2))
  samples<-list(all=list(filter=list()),late=list(filter=setNames(list('late'),nm('phase'))))
  build<-function(family,kind=NULL,constrained=FALSE) {
    med<-family%in%c('APIMeM','APIMeMoM')
    d<-list(family=family,x=list(exposure=pair('x')),y=list(response=pair('y')),
      samples=if(renamed)'late' else 'all',steps=list(free=list(equal=list())),
      controls=list(y1=nm('control1'),y2=nm('control2')),testing_family=paste0('synthetic_',family))
    if(med){d$m<-list(mediator=pair('m'));d$controls$m1<-nm('control1');d$controls$m2<-nm(c('control1','control2'))}
    if(constrained)d$steps$equal<-list(equal=if(med)list(c('a11','a22'),c('a12','a21'),c('b11','b22'),c('b12','b21'),c('c11','c22'),c('c12','c21')) else list(c('c11','c22'),c('c12','c21')))
    if(!is.null(kind)) {
      if(kind=='continuous') {
        d$w<-list(context=list(columns=pair('w'),scope='paired',type='continuous'))
        d$probes<-list(low=list(values=c(-1,-1),scale='analysis'),middle=list(values=c(0,0),scale='analysis'),high=list(values=c(1,1),scale='analysis'))
      } else {
        levels<-if(kind=='binary')0:1 else 0:2
        d$w<-list(context=list(columns=nm(if(kind=='binary')'wb' else 'wc'),scope='shared',type=kind,levels=levels,reference=0))
        d$probes<-list(low=list(values=0,scale='raw'),high=list(values=max(levels),scale='raw'))
        if(kind=='categorical')d$probes$middle<-list(values=1,scale='raw')
      }
      d$contrasts<-list(high_minus_low=c('high','low'))
    }
    d
  }
  cfg<-list(schema_version=2L,data=data,output_dir=output_dir,engine=engine,python=python,
    row_id=nm('record'),cluster=nm('pair'),members=if(renamed)c('Member B','Member A') else c('Member A','Member B'),
    missing=c('','NA'),missing_policy='complete_case',samples=samples,
    transform=list(scheme='pooled_center',reference='analysis_rows',overrides=list()),inference=inference,
    designs=list(apim=build('APIM',constrained=TRUE),apimem=build('APIMeM',constrained=TRUE),
      apimom_cont=build('APIMoM','continuous'),apimom_binary=build('APIMoM','binary'),apimom_category=build('APIMoM','categorical'),
      apimemom_cont=build('APIMeMoM','continuous'),apimemom_binary=build('APIMeMoM','binary'),apimemom_category=build('APIMeMoM','categorical')),
    # 16 GiB Windows主机的实测准入默认：保留0.75 GiB，单槽候选增量0.55 GiB；
    # 正式并发必须先由resource_measurement.json校准，不按静态峰值臆测。
    resource=list(ram_reserve_gib=.75,incremental_peak_gib=.55,commit_required_gib=.7,disk_required_gib=10),
    execution=list(max_parallel=1L,processor_budget=2L,wait_limit_seconds=14400),
    presentation=list(profile='generic'),testing=list(adjustment='none'))
  if(inference=='row_ML_BCbootstrap')cfg$bootstrap<-list(draws=1000L,resampling_unit='row',seed_policy='engine_default_not_user_controlled')
  cfg
}
