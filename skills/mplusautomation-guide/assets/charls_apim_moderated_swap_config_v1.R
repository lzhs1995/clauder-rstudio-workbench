# CHARLS 调节 APIM 换源（APIMoM、APIMeMoM）；在 charls_apim_swap 的夫妻宽表上追加共享调节变量。
# 默认合同必须阻断：调节变量的编码方向与缺失码尚未对照真实文档核实。
charls_apim_moderated_swap_contract <- function() {
  list(schema_version=1L,wave=2011L,
    # 输入是 charls_prepare_apim_swap() 的产物，只认 PASS_PREPARE_ONLY 回执；配偶关系在那一步核验。
    couples=list(receipt_status='PASS_PREPARE_ONLY',
      required_columns=c('couple_wave_id','community_id','member1_id','member2_id','member1_age','member2_age',
        'member1_adl','member2_adl','member1_cesd10','member2_cesd10')),
    # 城乡是住户层变量，夫妻共用；按 shared 调节变量处理，两人取值不一致时阻断。
    moderator=list(source='harmonized',id_column='ID',column='h1rural',output_column='couple_rural',
      scope='shared',level='household',valid_codes=c(0,1),labels=list(urban=0,rural=1),reference=0,
      # 空向量表示“经核实无额外数值缺失码”的候选；verified=FALSE 时仍不能运行。
      missing_codes=numeric(),
      codes_verified=FALSE,codes_documentation_sha256=NULL,codes_documentation_locator=NULL,
      coding_basis='0=urban 1=rural taken from an existing CHARLS covariate producer; codebook not yet bound',
      spouse_discordance_policy='block',one_sided_missing_policy='block'),
    scientific_boundary='2011 cross-sectional technical demonstration of moderated APIM; not a substantive finding')
}

charls_apim_moderated_swap_config <- function(data,output_dir,engine,python,protected_roots=character(),
                                              member_labels=c('Husband','Wife'),hard_cap=NULL) {
  # 四个模型：APIMoM 一个，APIMeMoM 按 moderated_paths 取 a、b、ab 各一个；都只有一个无约束步骤。
  w<-list(rural=list(columns='wr',scope='shared',type='binary',levels=c(0,1),reference=0))
  probes<-list(urban=list(values=0,scale='raw'),rural=list(values=1,scale='raw'))
  design<-function(family,paths=NULL) {
    x<-list(family=family,x=list(age=c('x1','x2')),y=list(cesd10=c('y1','y2')),w=w,
      samples='baseline',steps=list(free=list(equal=list())),controls=list(),
      probes=probes,contrasts=list(rural_minus_urban=c('rural','urban')),
      testing_family=paste0('charls_moderated_technical_',family))
    if(family=='APIMeMoM'){x$m<-list(adl=c('m1','m2'));x$moderated_paths<-paths}
    x
  }
  # grant 的 hard_cap：processors_per_model 进处理器预算；max_wall_seconds 收紧调度等待上限（到时停调度、保留进程，不强杀）
  execution<-list(max_parallel=1L,processor_budget=1L,wait_limit_seconds=14400)
  if(!is.null(hard_cap)) {
    execution$processor_budget<-as.integer(hard_cap$processors_per_model)
    execution$wait_limit_seconds<-as.integer(min(14400L,as.integer(hard_cap$max_wall_seconds)))
  }
  list(schema_version=2L,data=data,data_mode='dta',output_dir=output_dir,engine=engine,python=python,
    row_id='record',cluster='community',members=member_labels,
    column_map=c(record='couple_wave_id',community='community_id',
      x1='member1_age',x2='member2_age',m1='member1_adl',m2='member2_adl',
      y1='member1_cesd10',y2='member2_cesd10',wr='couple_rural'),
    # 宽表已按核实的合同转成原生 NA，这里不再声明第二套数值缺失码。
    missing=c('','NA'),missing_codes=NULL,missing_policy='complete_case',
    samples=list(baseline=list(filter=list())),
    transform=list(scheme='none',reference='analysis_rows',overrides=list()),
    designs=list(apimom=design('APIMoM'),apimemom_a=design('APIMeMoM','a'),
      apimemom_b=design('APIMeMoM','b'),apimemom_ab=design('APIMeMoM','ab')),
    # 与 charls_apim_swap 相同：历史入口名不决定聚类层级，CLUSTER=cid 来自 community 映射。
    inference='spouse_cluster_MLR_delta',
    resource=list(ram_reserve_gib=.75,incremental_peak_gib=.55,commit_required_gib=.7,disk_required_gib=10),
    execution=execution,
    presentation=list(profile='generic',title='CHARLS cross-sectional moderated APIM technical demonstration'),
    testing=list(adjustment='none'),protected_roots=protected_roots)
}

# 计划里必须恰好是这四个模型，顺序固定；驱动与测试都用它核对。
charls_apim_moderated_expected_models <- function() {
  data.frame(id=c('apimom_sample1_x1_y1_m1_w1_step1','apimemom_a_sample1_x1_y1_m1_w1_step1',
      'apimemom_b_sample1_x1_y1_m1_w1_step1','apimemom_ab_sample1_x1_y1_m1_w1_step1'),
    family=c('APIMoM','APIMeMoM','APIMeMoM','APIMeMoM'),moderated_paths=c('none','a','b','ab'),
    stringsAsFactors=FALSE)
}
