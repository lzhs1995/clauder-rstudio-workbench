# CHARLS 基期技术换源；配偶字段和来源文档尚未核实，默认合同必须阻断。
charls_apim_swap_contract <- function() {
  list(schema_version=1L,wave=2011L,
    source_columns=list(
      harmonized=list(id='ID',community='communityID',adl='r1adlab_c'),
      demographic=list(id='ID',household='householdID',
        birth_year='ba002_1',age_fallback='ba004',sex='rgender'),
      health=list(id='ID',household='householdID',cesd=sprintf('dc%03d',9:18))),
    key_modes=list(harmonized='as_is',demographic='charls2011_household_person',health='charls2011_household_person'),
    spouse_link=list(source='harmonized',person_id_column='ID',spouse_id_column=NULL,
      person_id_mode='as_is',spouse_id_mode='as_is',household_column=NULL,
      verified=FALSE,relationship_semantics=NULL,documentation_sha256=NULL,documentation_locator=NULL,
      reciprocity_required=TRUE),
    # 范围仅作数据有效性检查；不沿用既有轨迹研究的双方 60 岁筛选。
    age_valid_range=c(0,120),member_values=c(1,2),member_labels=c('Husband','Wife'),
    # 空向量表示“经核实无额外数值缺失码”的候选，verified=FALSE 时仍不能运行。
    missing_codes=list(harmonized=list(r1adlab_c=numeric()),
      demographic=list(ba002_1=numeric(),ba004=numeric(),rgender=numeric()),
      health=setNames(rep(list(numeric()),10),sprintf('dc%03d',9:18)),spouse_roster=list()),
    missing_codes_verified=FALSE,missing_codes_documentation_sha256=NULL,missing_codes_documentation_locator=NULL,
    identity_codes_verified=FALSE,identity_documentation_sha256=NULL,identity_documentation_locator=NULL,
    identity_policy='normalized_12_digit_person_ids_native_or_empty_spouse_missing_only',
    join_policy='baseline_demographic_anchor_require_paired_health',
    invalid_birth_year_policy='missing_without_fallback',
    adl_completeness='unknown_from_harmonized_score',
    scientific_boundary='2011 cross-sectional technical demonstration; indirect associations are not causal mediation')
}

charls_apim_swap_config <- function(data,output_dir,engine,python,protected_roots=character(),
                                  member_labels=c('Husband','Wife')) {
  design<-function(family) {
    x<-list(family=family,x=list(age=c('x1','x2')),y=list(cesd10=c('y1','y2')),
      samples='baseline',steps=list(free=list(equal=list())),controls=list(),
      testing_family=paste0('charls_technical_',family))
    if(family=='APIMeM')x$m<-list(adl=c('m1','m2'))
    x
  }
  list(schema_version=2L,data=data,data_mode='dta',output_dir=output_dir,engine=engine,python=python,
    row_id='record',cluster='community',members=member_labels,
    column_map=c(record='couple_wave_id',community='community_id',
      x1='member1_age',x2='member2_age',m1='member1_adl',m2='member2_adl',
      y1='member1_cesd10',y2='member2_cesd10'),
    # wide DTA 已按核实的逐字段合同转换为原生 NA，不再虚构第二套数值缺失码。
    missing=c('','NA'),missing_codes=NULL,missing_policy='complete_case',
    samples=list(baseline=list(filter=list())),
    transform=list(scheme='none',reference='analysis_rows',overrides=list()),
    designs=list(apim=design('APIM'),apimem=design('APIMeM')),
    # v2 的历史入口名不决定聚类层级；CLUSTER=cid 实际由上面的 community 映射产生。
    inference='spouse_cluster_MLR_delta',
    resource=list(ram_reserve_gib=.75,incremental_peak_gib=.55,commit_required_gib=.7,disk_required_gib=10),
    execution=list(max_parallel=1L,processor_budget=1L,wait_limit_seconds=14400),
    presentation=list(profile='generic',title='CHARLS cross-sectional technical demonstration'),
    testing=list(adjustment='none'),protected_roots=protected_roots)
}
