# 仅处理声明的 CHARLS 基期来源；不猜配偶、不继承旧个体增长样本、不运行引擎。
charls_swap_assert <- function(ok,message) if(!isTRUE(ok))stop(message,call.=FALSE)
charls_swap_sha <- function(path) digest::digest(path,algo='sha256',file=TRUE)
charls_swap_validate_contract <- function(contract) {
  s<-contract$spouse_link
  charls_swap_assert(identical(as.integer(contract$schema_version),1L)&&identical(as.integer(contract$wave),2011L),
    'Only the explicitly declared 2011 source contract is implemented')
  charls_swap_assert(is.list(s)&&isTRUE(s$verified)&&isTRUE(s$reciprocity_required)&&
    is.character(s$spouse_id_column)&&length(s$spouse_id_column)==1&&nzchar(s$spouse_id_column),
    'BLOCKED_UNVERIFIED_SPOUSE_LINK: declare a documented reciprocal spouse ID column')
  for(n in c('relationship_semantics','documentation_sha256','documentation_locator'))
    charls_swap_assert(is.character(s[[n]])&&length(s[[n]])==1&&nzchar(s[[n]]),paste('Missing spouse evidence:',n))
  charls_swap_assert(grepl('^[a-fA-F0-9]{64}$',s$documentation_sha256),'Invalid spouse documentation SHA256')
  charls_swap_assert(isTRUE(contract$missing_codes_verified)&&
    is.character(contract$missing_codes_documentation_sha256)&&length(contract$missing_codes_documentation_sha256)==1&&
    grepl('^[a-fA-F0-9]{64}$',contract$missing_codes_documentation_sha256)&&
    is.character(contract$missing_codes_documentation_locator)&&length(contract$missing_codes_documentation_locator)==1&&
    nzchar(contract$missing_codes_documentation_locator),
    'BLOCKED_UNREVIEWED_MISSING_CODES: empty code lists are not evidence of source review')
  charls_swap_assert(isTRUE(contract$identity_codes_verified)&&
    is.character(contract$identity_documentation_sha256)&&length(contract$identity_documentation_sha256)==1&&
    grepl('^[a-fA-F0-9]{64}$',contract$identity_documentation_sha256)&&
    is.character(contract$identity_documentation_locator)&&length(contract$identity_documentation_locator)==1&&
    nzchar(contract$identity_documentation_locator)&&
    identical(contract$identity_policy,'normalized_12_digit_person_ids_native_or_empty_spouse_missing_only'),
    'BLOCKED_UNREVIEWED_IDENTITY_CODES: confirm ID formats and spouse missing representations')
  charls_swap_assert(s$source%in%c('harmonized','spouse_roster'),'Spouse source must be harmonized or an explicit roster')
  charls_swap_assert(length(contract$member_values)==2&&!anyDuplicated(contract$member_values)&&
    length(contract$member_labels)==2&&!anyDuplicated(contract$member_labels),'Declare two distinguishable member roles')
  charls_swap_assert(identical(as.numeric(contract$member_values),c(1,2)),
    'This source contract uses documented demographic sex codes 1=male, 2=female')
  charls_swap_assert(length(contract$age_valid_range)==2&&all(is.finite(contract$age_valid_range))&&
    contract$age_valid_range[1]>=0&&contract$age_valid_range[1]<contract$age_valid_range[2], 'Declare age validity range')
  charls_swap_assert(identical(contract$adl_completeness,'unknown_from_harmonized_score'),
    'Harmonized ADL score does not establish all six items observed')
  charls_swap_assert(identical(contract$join_policy,'baseline_demographic_anchor_require_paired_health'),
    'Declare the baseline demographic anchor and paired-health module policy')
  charls_swap_assert(identical(contract$invalid_birth_year_policy,'missing_without_fallback'),
    'Invalid observed birth year cannot silently trigger reported-age fallback')
  invisible(TRUE)
}

charls_swap_id <- function(id,household=NULL,mode='as_is',allow_missing=FALSE) {
  charls_swap_assert(is.character(id),'ID type must be character; numeric conversion requires a reviewed upstream contract')
  id<-as.character(id)
  absent<-is.na(id)|!nzchar(id)
  charls_swap_assert(allow_missing||!any(absent),'Missing person identity')
  charls_swap_assert(all(absent|id==trimws(id)),'ID has surrounding whitespace; do not silently trim')
  if(mode=='as_is')return(replace(id,absent,NA_character_))
  charls_swap_assert(identical(mode,'charls2011_household_person'),'Unsupported identity normalization')
  charls_swap_assert(is.character(household)&&length(household)==length(id),'Explicit household identity required for 2011 normalization')
  good<-!absent
  charls_swap_assert(all(!is.na(household[good])&grepl('^[0-9]{9}$',household[good]))&&
    all(grepl('^[0-9]{11}$',id[good]))&&all(substr(id[good],1,9)==household[good]),
    '2011 ID/household format mismatch; inspect source metadata')
  result<-rep(NA_character_,length(id));result[good]<-paste0(household[good],'0',substr(id[good],10,11));result
}

charls_swap_read_sources <- function(paths,contract) {
  charls_swap_validate_contract(contract)
  for(p in c('haven','digest','tidyselect'))charls_swap_assert(requireNamespace(p,quietly=TRUE),paste('Missing package',p))
  needed<-c('harmonized','demographic','health',if(contract$spouse_link$source=='spouse_roster')'spouse_roster')
  charls_swap_assert(all(needed%in%names(paths))&&all(file.exists(unlist(paths[needed]))),'Missing declared source file')
  hashes<-vapply(paths[needed],charls_swap_sha,'')
  audit<-list();tables<-list()
  for(name in needed) {
    columns<-unique(unlist(contract$source_columns[[name]],use.names=FALSE))
    s<-contract$spouse_link
    if(name==s$source)columns<-unique(c(columns,s$person_id_column,s$spouse_id_column,s$household_column))
    charls_swap_assert(length(columns)>0,'Empty source-column contract')
    d<-as.data.frame(haven::read_dta(paths[[name]],col_select=tidyselect::all_of(columns),.name_repair='minimal'),check.names=FALSE)
    charls_swap_assert(!anyDuplicated(names(d)),'Duplicate source columns')
    identity_cols<-intersect(names(d),c(contract$source_columns[[name]]$id,contract$source_columns[[name]]$household,
      contract$source_columns[[name]]$community,if(name==s$source)c(s$person_id_column,s$spouse_id_column,s$household_column)))
    codes<-contract$missing_codes[[name]]
    charls_swap_assert(!length(intersect(names(codes),identity_cols)),'Identity columns cannot use missing-code recoding')
    required_codes<-setdiff(names(d),identity_cols)
    charls_swap_assert(is.list(codes)&&!anyDuplicated(names(codes))&&setequal(names(codes),required_codes),
      paste('Every non-identity source field needs an explicit reviewed missing-code entry:',name))
    charls_swap_assert(all(vapply(codes,function(z)length(z)==0L||
      ((is.numeric(z)||is.character(z))&&!anyNA(z)&&(!is.numeric(z)||all(is.finite(z)))),logical(1))),
      'Invalid per-field missing-code declaration')
    counts<-list()
    for(n in names(d)) {
      x<-d[[n]];tagged<-if(is.double(x))sum(haven::is_tagged_na(x)) else 0L
      if(inherits(x,'haven_labelled'))x<-haven::zap_labels(x)
      before<-sum(is.na(x));selected<-!is.na(x)&x%in%codes[[n]];x[selected]<-NA
      counts[[n]]<-list(native_missing=before,tagged_missing=tagged,declared_codes_replaced=sum(selected))
      d[[n]]<-x
    }
    tables[[name]]<-d;audit[[name]]<-list(rows=nrow(d),columns=ncol(d),missingness=counts)
  }
  key<-function(name) {
    c<-contract$source_columns[[name]];d<-tables[[name]]
    ids<-charls_swap_id(d[[c$id]],if(is.null(c$household))NULL else d[[c$household]],contract$key_modes[[name]])
    charls_swap_assert(!anyDuplicated(ids),paste('Duplicate person identity in',name));ids
  }
  hi<-key('harmonized');di<-key('demographic');yi<-key('health')
  s<-contract$spouse_link;sd<-tables[[s$source]]
  sh<-if(is.null(s$household_column))NULL else sd[[s$household_column]]
  si<-charls_swap_id(sd[[s$person_id_column]],sh,s$person_id_mode)
  sp<-charls_swap_id(sd[[s$spouse_id_column]],sh,s$spouse_id_mode,allow_missing=TRUE)
  charls_swap_assert(all(grepl('^[0-9]{12}$',c(hi,di,yi,si,sp[!is.na(sp)]))),
    'Unexpected normalized person ID format or unreviewed spouse missing sentinel')
  charls_swap_assert(!anyDuplicated(si),'Duplicate person identity in spouse source')
  dm<-match(hi,di);ym<-match(hi,yi);sm<-match(hi,si)
  d<-tables$demographic;c<-contract$source_columns$demographic
  number<-function(x,label) {
    z<-suppressWarnings(as.numeric(x));charls_swap_assert(!any(!is.na(x)&!is.finite(z)),paste('Invalid numeric source',label));z
  }
  birth<-number(d[[c$birth_year]][dm],'birth_year');fallback<-number(d[[c$age_fallback]][dm],'age_fallback')
  age<-contract$wave-birth;limits<-contract$age_valid_range
  valid_age<-function(x)!is.na(x)&is.finite(x)&x>=limits[1]&x<=limits[2]
  invalid_birth<-!is.na(birth)&!valid_age(age)
  age[!valid_age(age)]<-NA_real_;fallback[!valid_age(fallback)]<-NA_real_
  use_fallback<-is.na(birth)&!is.na(fallback);age[use_fallback]<-fallback[use_fallback]
  community<-tables$harmonized[[contract$source_columns$harmonized$community]]
  charls_swap_assert(is.character(community),'Community IDs must preserve the declared character representation')
  community<-charls_swap_id(community,allow_missing=TRUE)
  persons<-data.frame(pid=hi,spouse_pid=sp[sm],community=community,sex=number(d[[c$sex]][dm],'sex'),
    age=age,adl=number(tables$harmonized[[contract$source_columns$harmonized$adl]],'adl'),
    health_module_present=!is.na(ym),stringsAsFactors=FALSE)
  items<-contract$source_columns$health$cesd
  charls_swap_assert(identical(items,sprintf('dc%03d',9:18)),
    'This scoring contract requires ordered dc009 through dc018; dc013 and dc016 are reversed')
  for(i in seq_along(items))persons[[paste0('cesd',i)]]<-number(tables$health[[items[i]]][ym],items[i])
  # harmonized 可跨波；仅原始 2011 demographic 中实有个人进入基期候选。
  # 关系互指之后缺 health 模块会单独阻断，不能冒充十题题项缺失。
  persons<-persons[!is.na(dm),,drop=FALSE]
  attr(persons,'charls_source_evidence')<-list(source_hashes=hashes,source_rows=audit,
    harmonized_without_demographic=sum(is.na(dm)),harmonized_without_health=sum(is.na(ym)),
    harmonized_without_spouse_roster=sum(is.na(sm)),age_fallback_used=sum(use_fallback),invalid_birth_year=sum(invalid_birth),
    join_policy=contract$join_policy,baseline_persons=nrow(persons),
    source_contract_sha256=digest::digest(contract,algo='sha256'))
  charls_swap_assert(identical(vapply(paths[needed],charls_swap_sha,''),hashes),'Source changed during reading')
  persons
}

charls_prepare_apim_swap <- function(persons,contract,output_dir,source_paths=character()) {
  charls_swap_validate_contract(contract)
  for(p in c('haven','digest','jsonlite'))charls_swap_assert(requireNamespace(p,quietly=TRUE),paste('Missing package',p))
  needed<-c('pid','spouse_pid','community','sex','age','adl','health_module_present',paste0('cesd',1:10))
  charls_swap_assert(is.data.frame(persons)&&all(needed%in%names(persons))&&!anyDuplicated(names(persons)), 'Missing canonical person columns')
  id<-charls_swap_id(persons$pid);spouse<-charls_swap_id(persons$spouse_pid,allow_missing=TRUE)
  charls_swap_assert(all(grepl('^[0-9]{12}$',c(id,spouse[!is.na(spouse)]))),
    'Unexpected normalized person ID format or unreviewed spouse missing sentinel')
  charls_swap_assert(!anyDuplicated(id),'Duplicate person identity')
  j<-match(spouse,id);linked<-!is.na(spouse)
  charls_swap_assert(any(linked),'No documented spouse links')
  charls_swap_assert(!any(linked&id==spouse),'Self spouse link')
  # 只有来源范围外的配偶可记录排除；存在但不互指的关系属于身份冲突，直接阻断。
  observed<-linked&!is.na(j)
  charls_swap_assert(all(!is.na(spouse[j[observed]])&spouse[j[observed]]==id[observed]),'Nonreciprocal spouse link')
  valid<-observed
  charls_swap_assert(any(valid),'No reciprocal spouses present in the declared source')
  charls_swap_assert(is.logical(persons$health_module_present)&&all(persons$health_module_present[valid]),
    'Missing health module for a reciprocal baseline spouse; inspect the source join before item missingness')
  sex<-persons$sex;charls_swap_assert(is.numeric(sex)&&all(sex[valid]%in%contract$member_values),'Unknown member role code')
  first<-which(valid&sex==contract$member_values[1]);second<-j[first]
  charls_swap_assert(length(first)>0&&all(sex[second]==contract$member_values[2])&&length(first)*2==sum(valid),
    'Spouse pairs do not each contain one declared member role')
  community<-persons$community
  charls_swap_assert(is.character(community)&&all(!is.na(community[valid])&nzchar(community[valid]))&&
    all(community[first]==community[second]),'Missing or discordant spouse community')
  # CESD 十项全有效才计总分，第 5/8 项反向；保留逐项无效计数，不填补。
  item_cols<-paste0('cesd',1:10);charls_swap_assert(all(vapply(persons[item_cols],is.numeric,logical(1))),'CESD items must be numeric codes')
  raw<-as.matrix(persons[item_cols]);ok<-is.finite(raw)&raw%in%1:4
  dim(ok)<-dim(raw);invalid<-!is.na(raw)&!ok;raw[!ok]<-NA_real_
  scored<-raw-1;scored[,c(5,8)]<-4-raw[,c(5,8)];complete<-rowSums(is.na(scored))==0
  cesd<-rep(NA_real_,nrow(persons));cesd[complete]<-rowSums(scored[complete,,drop=FALSE])
  adl<-persons$adl;age<-persons$age
  charls_swap_assert(is.numeric(adl)&&is.numeric(age),'Age and ADL must be numeric')
  bad_adl<-!is.na(adl)&(!is.finite(adl)|adl!=trunc(adl)|adl<0|adl>6);adl[bad_adl]<-NA_real_
  lim<-contract$age_valid_range;bad_age<-!is.na(age)&(!is.finite(age)|age<lim[1]|age>lim[2]);age[bad_age]<-NA_real_
  # 长 ID 仅进入本地文件；长度前缀避免拼接歧义，不按 ID 排序推断成员角色。
  pair<-paste0(nchar(id[first]),':',id[first],nchar(id[second]),':',id[second])
  wide<-data.frame(couple_wave_id=paste0(contract$wave,':',pair),community_id=community[first],
    member1_id=id[first],member2_id=id[second],member1_age=age[first],member2_age=age[second],
    member1_adl=adl[first],member2_adl=adl[second],member1_cesd10=cesd[first],member2_cesd10=cesd[second],stringsAsFactors=FALSE)
  charls_swap_assert(!anyDuplicated(wide$couple_wave_id),'Duplicate couple record')
  cc_apim<-complete.cases(wide[c('member1_age','member2_age','member1_cesd10','member2_cesd10')])
  cc_med<-cc_apim&complete.cases(wide[c('member1_adl','member2_adl')])
  charls_swap_assert(sum(cc_apim)>0&&sum(cc_med)>0&&length(unique(wide$community_id[cc_apim]))>1&&
    length(unique(wide$community_id[cc_med]))>1,'Insufficient complete couples or communities')
  for(cols in list(c('member1_age','member2_age','member1_cesd10','member2_cesd10'),
    c('member1_age','member2_age','member1_adl','member2_adl','member1_cesd10','member2_cesd10'))) {
    rows<-if(length(cols)==4)cc_apim else cc_med
    charls_swap_assert(all(vapply(wide[rows,cols,drop=FALSE],function(x)length(unique(x))>1,logical(1))),
      'Degenerate model variable; retain this source failure rather than fitting')
  }
  ranks<-list()
  for(spec in list(apim=list(rows=cc_apim,columns=c('member1_age','member2_age')),
    apimem_m=list(rows=cc_med,columns=c('member1_age','member2_age')),
    apimem_y=list(rows=cc_med,columns=c('member1_age','member2_age','member1_adl','member2_adl')))) {
    matrix<-cbind(intercept=1,as.matrix(wide[spec$rows,spec$columns,drop=FALSE]))
    rank<-qr(matrix)$rank
    charls_swap_assert(rank==ncol(matrix),'Rank-deficient declared predictor matrix; do not fit')
    ranks[[length(ranks)+1L]]<-list(columns=colnames(matrix),rank=rank)
  }
  charls_swap_assert(!dir.exists(output_dir),'Preparation directory already exists; preserve original attempt')
  for(p in source_paths) {
    src<-normalizePath(p,winslash='/',mustWork=TRUE);dest<-normalizePath(dirname(output_dir),winslash='/',mustWork=TRUE)
    charls_swap_assert(!identical(dest,dirname(src))&&!startsWith(dest,paste0(dirname(src),'/')),'Preparation must be disjoint from sources')
  }
  dir.create(output_dir,recursive=TRUE);data_path<-file.path(output_dir,'charls_couples_2011_v2.dta')
  haven::write_dta(wide,data_path)
  # 输出仅本机私有证据；公开仓库只提交生成器。
  receipt<-list(status='PASS_PREPARE_ONLY',wave=contract$wave,persons=nrow(persons),
    absent_spouse=sum(!linked),spouse_outside_source=sum(linked&is.na(j)),reciprocal_persons=sum(valid),
    couples=nrow(wide),complete_apim=sum(cc_apim),complete_apimem=sum(cc_med),
    invalid_cesd_by_item=as.list(setNames(colSums(invalid),item_cols)),invalid_adl=sum(bad_adl),invalid_age=sum(bad_age),
    predictor_rank_checks=ranks,join_policy=contract$join_policy,
    adl_completeness=contract$adl_completeness,member_labels=contract$member_labels,
    cluster='community',inference_entry='spouse_cluster_MLR_delta',
    scientific_boundary=contract$scientific_boundary,new_mplus_calls=0L,
    data_sha256=charls_swap_sha(data_path),source_evidence=attr(persons,'charls_source_evidence'),
    contract_sha256=digest::digest(contract,algo='sha256'))
  jsonlite::write_json(receipt,file.path(output_dir,'preparation_receipt.json'),auto_unbox=TRUE,pretty=TRUE,null='null')
  saveRDS(contract,file.path(output_dir,'source_contract.rds'))
  invisible(list(data_path=normalizePath(data_path,winslash='/',mustWork=TRUE),receipt=receipt))
}

# 展示副本修正 legacy API 的聚类文字；模型结果缓存及其数值完全保留。
charls_render_apim_swap <- function(config,output_dir) {
  charls_swap_assert(identical(config$cluster,'community')&&
    identical(config$column_map[['community']],'community_id'),'Display adapter requires declared community clustering')
  original<-file.path(config$output_dir,'effects.rds');e<-readRDS(original)
  charls_swap_assert(nrow(e)>0&&all(e$interval_method=='Mplus_MLR_spouse_cluster_delta_normal'),
    'Unexpected effect inference labels; review before rendering')
  original_sha<-charls_swap_sha(original);before<-e[vapply(e,is.numeric,logical(1))]
  e$interval_method<-'Mplus_MLR_community_cluster_delta_normal'
  e$p_method<-'MLR_community_cluster_robust_Wald_normal'
  charls_swap_assert(!dir.exists(output_dir),'Display directory already exists; preserve prior output')
  for(p in c(output_dir,file.path(output_dir,'figures'),file.path(output_dir,'tables'),file.path(output_dir,'audit')))
    dir.create(p,recursive=TRUE,showWarnings=FALSE)
  saveRDS(e,file.path(output_dir,'effects.rds'));write.csv(e,file.path(output_dir,'effects.csv'),row.names=FALSE)
  plan<-plan_apim_workflow(config);plan$root<-normalizePath(output_dir,winslash='/',mustWork=TRUE)
  apim_v2_render(config,plan,e)
  charls_swap_assert(identical(before,e[vapply(e,is.numeric,logical(1))])&&identical(charls_swap_sha(original),original_sha),
    'Rendering must not change estimates or the original cache')
  receipt<-list(status='PASS_DISPLAY_LABEL_ADAPTER',cluster='community',source_effects_sha256=original_sha,
    display_effects_sha256=charls_swap_sha(file.path(output_dir,'effects.rds')),numeric_columns_unchanged=TRUE,
    scientific_boundary='2011 cross-sectional technical demonstration; indirect associations are not causal mediation',
    scientific_released=FALSE)
  apim_json(receipt,file.path(output_dir,'audit','community_display_receipt.json'))
  invisible(receipt)
}
