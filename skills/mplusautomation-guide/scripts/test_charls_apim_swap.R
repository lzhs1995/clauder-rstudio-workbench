# 完全合成 CHARLS 形状数据；所有 ID/题项均由生成器创建，禁止替换为真实个体夹具。
test_charls_apim_swap <- function(skill_root,test_root,engine,python) {
  source(file.path(skill_root,'scripts','workflow.R'),local=TRUE)
  source(file.path(skill_root,'scripts','charls_apim_swap.R'),local=TRUE)
  source(file.path(skill_root,'assets','charls_apim_swap_config_v2.R'),local=TRUE)
  stopifnot(!dir.exists(test_root));dir.create(test_root,recursive=TRUE)
  checks<-list();check<-function(name,value){stopifnot(isTRUE(value));checks[[name]]<<-TRUE;cat('PASS',name,'\n');flush.console()}
  fails<-function(x)inherits(tryCatch({force(x);NULL},error=identity),'error')
  contract<-charls_apim_swap_contract()
  check('unverified_default_spouse_contract_blocks',fails(charls_swap_validate_contract(contract)))
  contract$spouse_link$spouse_id_column<-'spouse_id';contract$spouse_link$verified<-TRUE
  contract$spouse_link$relationship_semantics<-'Synthetic reciprocal spouse links only'
  contract$spouse_link$documentation_sha256<-digest::digest('synthetic fixture source',algo='sha256')
  contract$spouse_link$documentation_locator<-'synthetic generator, paired records'
  check('unreviewed_empty_missing_codes_block',fails(charls_swap_validate_contract(contract)))
  contract$missing_codes_verified<-TRUE
  contract$missing_codes_documentation_sha256<-digest::digest('synthetic missing-code design',algo='sha256')
  contract$missing_codes_documentation_locator<-'synthetic generator: native missing and explicit validity violations'
  check('unreviewed_identity_codes_block',fails(charls_swap_validate_contract(contract)))
  contract$identity_codes_verified<-TRUE
  contract$identity_documentation_sha256<-digest::digest('synthetic 11 to 12 digit ID fixture',algo='sha256')
  contract$identity_documentation_locator<-'synthetic generator: character IDs; only native or empty spouse missing'
  fixture<-file.path(test_root,'source');dir.create(fixture)
  n<-48L;house<-rep(sprintf('%09d',1:(n/2)),each=2);slot<-rep(c('01','02'),n/2)
  rawid<-paste0(house,slot);pid<-paste0(house,'0',slot);mate<-rep(seq(1,n,by=2),each=2)+rep(c(1,0),n/2)
  demo<-data.frame(ID=rawid,householdID=house,
    ba002_1=1940+(1:n)%%30,ba004=rep(NA_real_,n),rgender=rep(1:2,n/2))
  demo$ba002_1[1]<-NA;demo$ba004[1]<-64
  harmonized<-data.frame(ID=pid,communityID=rep(sprintf('SYN_COMM_%02d',1:8),each=6),
    r1adlab_c=(1:n)%%7,spouse_id=pid[mate])
  health<-data.frame(ID=rawid,householdID=house)
  for(k in 1:10)health[[sprintf('dc%03d',k+8)]]<-((1:n)*k+(1:n)%/%5)%%4+1
  health$dc009[3]<-NA_real_;harmonized$r1adlab_c[5]<-9;health$dc010[7]<-9
  # 原生缺失与值标签通过真正的 .dta 文件读入，不用伪造读取结果。
  health$dc011[9]<-haven::tagged_na('a');demo$rgender<-haven::labelled(demo$rgender,c(male=1,female=2))
  paths<-file.path(fixture,c('harmonized_synthetic_v2.dta','demographic_synthetic_v2.dta','health_synthetic_v2.dta'))
  names(paths)<-c('harmonized','demographic','health')
  haven::write_dta(harmonized,paths[['harmonized']]);haven::write_dta(demo,paths[['demographic']]);haven::write_dta(health,paths[['health']])
  hashes<-vapply(paths,charls_swap_sha,'')
  persons<-charls_swap_read_sources(paths,contract)
  check('source_join_exact_character_ids',identical(persons$pid,pid)&&identical(persons$spouse_pid,pid[mate]))
  check('age_fallback_without_trajectory_age_filter',persons$age[1]==64&&nrow(persons)==n&&min(persons$age,na.rm=TRUE)<60)
  prep<-charls_prepare_apim_swap(persons,contract,file.path(test_root,'prepared'),paths)
  wide<-haven::read_dta(prep$data_path)
  check('reciprocal_pairs_collapse_exactly_once',nrow(wide)==24L&&identical(as.character(wide$member1_id),pid[seq(1,n,2)])&&identical(as.character(wide$member2_id),pid[seq(2,n,2)]))
  # 独立 CESD 手算只使用一个未设缺失的合成行。
  row<-2L;values<-as.numeric(health[row,sprintf('dc%03d',9:18)])
  expected<-sum(values[-c(5,8)]-1)+sum(4-values[c(5,8)])
  check('cesd_reverse_items_and_complete_rule',wide$member2_cesd10[1]==expected&&is.na(wide$member1_cesd10[2])&&is.na(wide$member1_cesd10[4]))
  check('invalid_adl_is_missing_and_completeness_unknown',is.na(wide$member1_adl[3])&&identical(prep$receipt$adl_completeness,'unknown_from_harmonized_score'))
  check('tagged_missing_preserved',is.na(wide$member1_cesd10[5]))
  cfg<-charls_apim_swap_config(prep$data_path,file.path(test_root,'run'),engine,python)
  plan<-plan_apim_workflow(cfg)
  check('exactly_two_unconstrained_models',plan$candidate_count==2L&&plan$execution_count==2L&&
    identical(vapply(plan$models,`[[`,'','family'),c(apim_sample1_x1_y1_m1_w1_step1='APIM',apimem_sample1_x1_y1_m1_w1_step1='APIMeM')))
  run<-run_apim_workflow(cfg,stages=c('check','prepare','compile'))
  for(model in run$plan$models) {
    compiled<-run$compiled[[model$id]];p<-readRDS(file.path(compiled$folder,'prepared.rds'))
    expected_n<-if(model$family=='APIM')prep$receipt$complete_apim else prep$receipt$complete_apimem
    check(paste0(model$family,'_full_prepare_compile'),p$N==expected_n&&file.exists(compiled$input)&&!file.exists(compiled$output))
    check(paste0(model$family,'_community_clustering_and_raw_scale'),p$clusters==8L&&all(vapply(p$moments,function(x)x$center==0&&x$scale==1,logical(1)))&&
      any(grepl('CLUSTER = cid;',readLines(compiled$input),fixed=TRUE)))
  }
  bad<-persons;bad$spouse_pid<-NA_character_;check('no_spouse_data_blocks',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_none'))))
  bad<-persons;bad<-rbind(bad,bad[1,]);check('duplicate_person_blocks',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_duplicate'))))
  bad<-persons;bad$spouse_pid[2]<-persons$pid[3];check('nonreciprocal_spouse_blocks',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_reciprocal'))))
  bad<-persons;bad$spouse_pid[1]<-persons$pid[1];check('self_spouse_blocks',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_self'))))
  bad<-persons;bad$community[1]<-'SYN_DIFFERENT';check('discordant_community_blocks',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_cluster'))))
  bad<-persons;bad$pid<-as.numeric(bad$pid);check('numeric_ids_block_without_conversion_contract',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_ids'))))
  bad<-persons;bad[paste0('cesd',1:10)]<-NA_real_;check('all_missing_outcome_blocks',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_missing'))))
  bad<-persons;bad$sex[2]<-1;check('sex_does_not_manufacture_pairing',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_roles'))))
  check('source_files_unchanged',identical(vapply(paths,charls_swap_sha,''),hashes))
  check('preparation_never_overwrites_existing_attempt',fails(charls_prepare_apim_swap(persons,contract,file.path(test_root,'prepared'),paths)))
  bad_contract<-contract;bad_contract$source_columns$health$cesd<-rev(bad_contract$source_columns$health$cesd)
  check('cesd_item_reordering_blocks',fails(charls_swap_read_sources(paths,bad_contract)))
  bad_contract<-contract;bad_contract$missing_codes$demographic<-list(ID='01')
  check('identity_missing_code_recode_blocks',fails(charls_swap_read_sources(paths,bad_contract)))
  check('normalizer_rejects_mismatched_household_prefix',fails(charls_swap_id(rawid,rev(house),'charls2011_household_person')))
  bad_contract<-contract;bad_contract$missing_codes$health$dc009<-NULL
  check('omitted_field_missing_code_review_blocks',fails(charls_swap_read_sources(paths,bad_contract)))
  bad<-persons;bad$spouse_pid[1]<-'-9'
  check('unknown_spouse_string_sentinel_blocks',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_spouse_code'))))
  bad<-persons;bad$health_module_present[1]<-FALSE
  check('missing_module_is_not_silent_item_missing',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_module'))))
  bad<-persons;bad$age[seq(2,n,2)]<-bad$age[seq(1,n,2)]
  check('collinear_predictors_block',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'bad_rank'))))
  altered<-demo;altered$ba002_1[2]<-contract$wave+1;altered$ba004[2]<-50
  altered_path<-file.path(fixture,'invalid_birth_synthetic_v2.dta');haven::write_dta(altered,altered_path)
  altered_paths<-paths;altered_paths[['demographic']]<-altered_path
  altered_persons<-charls_swap_read_sources(altered_paths,contract)
  check('invalid_observed_birth_does_not_trigger_fallback',is.na(altered_persons$age[2])&&
    attr(altered_persons,'charls_source_evidence')$invalid_birth_year==1L)
  shortened_path<-file.path(fixture,'baseline_shortened_synthetic_v2.dta');haven::write_dta(demo[-c(47,48),],shortened_path)
  altered_paths[['demographic']]<-shortened_path
  anchored<-charls_swap_read_sources(altered_paths,contract)
  check('harmonized_future_only_rows_excluded_by_baseline_anchor',nrow(anchored)==46L&&
    attr(anchored,'charls_source_evidence')$harmonized_without_demographic==2L)
  # 显式整对资格策略：各原因与交集按互指夫妻计数，默认仍逐项阻断。
  blocks_with<-function(expr,message,exact=FALSE) {
    error<-tryCatch({force(expr);NULL},error=identity)
    inherits(error,'error')&&if(exact)identical(conditionMessage(error),message) else
      grepl(message,conditionMessage(error),fixed=TRUE)
  }
  # 旧合同不能仅靠新增字段偷开官方映射或零缺失；两个拒绝原因分别精确断言。
  bad_contract<-contract;bad_contract$spouse_link$spouse_missing_values<-'0'
  check('legacy_contract_rejects_declared_zero_missing',blocks_with(charls_swap_validate_contract(bad_contract),
    'Extra spouse missing codes require the explicit official crosswalk contract',exact=TRUE))
  bad_contract<-contract
  bad_contract$spouse_link$crosswalk<-list(source='harmonized',from_column='ID_w1',to_column='ID',
    sha256=charls_swap_sha(paths[['harmonized']]))
  check('legacy_contract_rejects_crosswalk_declaration',blocks_with(charls_swap_validate_contract(bad_contract),
    'Extra spouse missing codes require the explicit official crosswalk contract',exact=TRUE))
  optional<-contract;optional$pair_eligibility<-'exclude_ineligible_pairs'
  check('pair_policy_default_remains_strict',identical(contract$pair_eligibility,'strict'))
  old_contract<-contract;old_contract$pair_eligibility<-NULL
  check('legacy_contract_uses_strict',blocks_with(charls_prepare_apim_swap(
    transform(persons,health_module_present=replace(health_module_present,1,FALSE)),old_contract,
    file.path(test_root,'legacy_strict')),'Missing health module'))
  cases<-list(missing_health=list(column='health_module_present',value=FALSE,reason='missing_health'),
    missing_role=list(column='sex',value=NA_real_,reason='missing_role'),
    outside_role=list(column='sex',value=0,reason='outside_role'),
    same_role=list(column='sex',value=2,reason='same_role'))
  for(label in names(cases)) {
    case<-cases[[label]];bad<-persons;bad[[case$column]][1]<-case$value
    check(paste0('strict_rejects_',label),fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,paste0('strict_',label)))))
    result<-charls_prepare_apim_swap(bad,optional,file.path(test_root,paste0('exclude_',label)),paths)
    table<-haven::read_dta(result$data_path);audit<-result$receipt$pair_eligibility
    check(paste0('whole_pair_excluded_',label),audit[[case$reason]]==1&&audit$excluded_pairs==1&&
      audit$remaining_pairs==23&&nrow(table)==23&&!any(c(pid[1],pid[2])%in%c(table$member1_id,table$member2_id)))
  }
  # 双方同为域外码也只属于域外角色，不能重复记到有效角色同码原因。
  bad<-persons;bad$sex[1:2]<-0
  result<-charls_prepare_apim_swap(bad,optional,file.path(test_root,'both_outside_roles'),paths)
  audit<-result$receipt$pair_eligibility;table<-haven::read_dta(result$data_path)
  check('both_outside_roles_not_counted_as_same_role',audit$outside_role==1&&audit$same_role==0&&
    audit$missing_role==0&&audit$invalid_role==1&&audit$missing_health==0&&audit$health_role_overlap==0&&
    audit$excluded_pairs==1&&audit$remaining_pairs==23&&nrow(table)==23&&
    !any(c(pid[1],pid[2])%in%c(table$member1_id,table$member2_id)))
  bad<-persons;bad$health_module_present[c(1,3)]<-FALSE;bad$sex[c(3,5)]<-NA;bad$sex[4]<-0;bad$sex[7]<-2
  result<-charls_prepare_apim_swap(bad,optional,file.path(test_root,'exclude_overlap'),paths)
  audit<-result$receipt$pair_eligibility
  check('pair_exclusion_overlap_not_double_counted',audit$missing_health==2&&audit$missing_role==2&&
    audit$outside_role==1&&audit$same_role==1&&audit$invalid_role==3&&audit$health_role_overlap==1&&
    audit$missing_outside_role_overlap==1&&audit$excluded_pairs==4&&audit$remaining_pairs==20)
  table<-haven::read_dta(result$data_path)
  check('exclusion_keeps_model_specific_complete_cases',result$receipt$complete_apim==sum(complete.cases(
    table[c('member1_age','member2_age','member1_cesd10','member2_cesd10')]))&&
    result$receipt$complete_apimem==sum(complete.cases(table[c('member1_age','member2_age',
      'member1_adl','member2_adl','member1_cesd10','member2_cesd10')])))
  bad<-persons;bad$health_module_present[]<-FALSE
  check('excluding_every_pair_blocks',blocks_with(charls_prepare_apim_swap(bad,optional,file.path(test_root,'exclude_all')),
    'No eligible distinguishable spouse pairs'))
  # 身份错误始终先拒绝；即使受影响夫妻另有可排除原因，也不能绕过关系核验。
  bad<-persons;bad$health_module_present[1]<-FALSE;bad<-rbind(bad,bad[1,])
  check('optional_still_rejects_identity_conflict',blocks_with(charls_prepare_apim_swap(bad,optional,file.path(test_root,'optional_duplicate')),'Duplicate person identity'))
  bad<-persons;bad$health_module_present[1]<-FALSE;bad$spouse_pid[1]<-bad$pid[1]
  check('optional_still_rejects_self_link',blocks_with(charls_prepare_apim_swap(bad,optional,file.path(test_root,'optional_self')),'Self spouse link'))
  bad<-persons;bad$health_module_present[1]<-FALSE;bad$spouse_pid[2]<-NA_character_
  check('optional_still_rejects_nonreciprocity',blocks_with(charls_prepare_apim_swap(bad,optional,file.path(test_root,'optional_nonreciprocal')),'Nonreciprocal spouse link'))
  bad<-persons;bad$health_module_present[1]<-FALSE;bad$spouse_pid[3]<-bad$spouse_pid[1]
  check('optional_still_rejects_multiple_claimants',blocks_with(charls_prepare_apim_swap(bad,optional,file.path(test_root,'optional_multiple')),'Multiple persons claim the same spouse'))
  bad<-persons;bad$health_module_present[1]<-FALSE;bad$community[1]<-'SYN_CONFLICT'
  check('exclusions_do_not_hide_community_conflict',blocks_with(charls_prepare_apim_swap(bad,optional,file.path(test_root,'optional_community')),'Missing or discordant spouse community'))
  bad_contract<-contract;bad_contract$pair_eligibility<-'ignore'
  check('unknown_pair_policy_blocks',fails(charls_swap_validate_contract(bad_contract)))
  # 官方 crosswalk 测试故意配对到另一 household，验证只按 ID_w1 精确查找。
  crosswalk_data<-harmonized;crosswalk_data$spouse_id<-NULL
  crosswalk_data$ID_w1<-rawid;crosswalk_mate<-mate;crosswalk_mate[1:4]<-c(4L,3L,2L,1L)
  crosswalk_data$s1id<-rawid[crosswalk_mate];crosswalk_data$s1id[47:48]<-'0'
  future<-crosswalk_data[1,,drop=FALSE];future$ID<-sprintf('%012d',n+1L);future$ID_w1<-'';future$s1id<-''
  crosswalk_data<-rbind(crosswalk_data,future)
  crosswalk_path<-file.path(fixture,'official_crosswalk_synthetic_v2.dta');haven::write_dta(crosswalk_data,crosswalk_path)
  crosswalk_paths<-paths;crosswalk_paths[['harmonized']]<-crosswalk_path
  crosswalk_contract<-contract
  crosswalk_contract$identity_policy<-'official_id_w1_crosswalk_zero_spouse_missing_only'
  crosswalk_contract$key_modes$demographic<-'official_id_w1_crosswalk'
  crosswalk_contract$key_modes$health<-'official_id_w1_crosswalk'
  crosswalk_contract$spouse_link$spouse_id_column<-'s1id'
  crosswalk_contract$spouse_link$spouse_id_mode<-'official_id_w1_crosswalk'
  crosswalk_contract$spouse_link$spouse_missing_values<-'0'
  crosswalk_contract$spouse_link$crosswalk<-list(source='harmonized',from_column='ID_w1',to_column='ID',sha256=charls_swap_sha(crosswalk_path))
  crosswalk_persons<-charls_swap_read_sources(crosswalk_paths,crosswalk_contract)
  check('official_crosswalk_preserves_leading_zero_and_cross_household_spouse',
    identical(crosswalk_persons$pid,pid)&&identical(crosswalk_persons$spouse_pid[1:46],pid[crosswalk_mate[1:46]])&&
    all(is.na(crosswalk_persons$spouse_pid[47:48])))
  evidence<-attr(crosswalk_persons,'charls_source_evidence')$crosswalk
  check('crosswalk_receipt_binds_file_and_zero_count',identical(evidence$sha256,charls_swap_sha(crosswalk_path))&&
    evidence$mapping_rows==48&&evidence$missing_old_id_rows==1&&evidence$spouse_zero_to_missing==2)
  result<-charls_prepare_apim_swap(crosswalk_persons,crosswalk_contract,file.path(test_root,'crosswalk_prepared'),crosswalk_paths)
  check('crosswalk_preparation_preserves_source_hash',identical(result$receipt$source_evidence$crosswalk$sha256,
    crosswalk_contract$spouse_link$crosswalk$sha256)&&result$receipt$absent_spouse==2&&result$receipt$couples==23)
  # 新增冲突行排在前面且保留全部原行；删掉唯一性门后不会靠缺键门侥幸拒绝。
  duplicate_old<-crosswalk_data[1,,drop=FALSE];duplicate_old$ID<-sprintf('%012d',n+100L)
  duplicate_old<-rbind(duplicate_old,crosswalk_data)
  duplicate_path<-file.path(fixture,'crosswalk_duplicate_old_retained.dta');haven::write_dta(duplicate_old,duplicate_path)
  duplicate_paths<-crosswalk_paths;duplicate_paths[['harmonized']]<-duplicate_path
  duplicate_contract<-crosswalk_contract;duplicate_contract$spouse_link$crosswalk$sha256<-charls_swap_sha(duplicate_path)
  check('duplicate_crosswalk_old_id_rejected_by_uniqueness_gate',blocks_with(
    charls_swap_read_sources(duplicate_paths,duplicate_contract),'Conflicting official crosswalk identity',exact=TRUE))
  # 官方目标身份允许与旧插零结果不同，两个模块必须跟随官方目标，不能静默掉行。
  remapped<-crosswalk_data;remapped$ID[1:2]<-sprintf('%012d',n+c(2L,3L))
  remap_path<-file.path(fixture,'official_remapped_synthetic_v2.dta');haven::write_dta(remapped,remap_path)
  remap_paths<-crosswalk_paths;remap_paths[['harmonized']]<-remap_path
  remap_contract<-crosswalk_contract;remap_contract$spouse_link$crosswalk$sha256<-charls_swap_sha(remap_path)
  remap_persons<-charls_swap_read_sources(remap_paths,remap_contract)
  check('official_remapping_keeps_all_baseline_module_people',nrow(remap_persons)==n&&
    identical(remap_persons$pid,remapped$ID[seq_len(n)])&&all(remap_persons$health_module_present)&&
    identical(remap_persons$spouse_pid[1:46],remapped$ID[crosswalk_mate[1:46]])&&
    attr(remap_persons,'charls_source_evidence')$harmonized_without_demographic==1&&
    attr(remap_persons,'charls_source_evidence')$crosswalk$mapped_demographic_persons==n&&
    attr(remap_persons,'charls_source_evidence')$crosswalk$mapped_health_persons==n)
  remap_prep<-charls_prepare_apim_swap(remap_persons,remap_contract,file.path(test_root,'official_remap_prepared'),remap_paths)
  check('official_remapping_retains_pairs_and_model_cases',remap_prep$receipt$couples==result$receipt$couples&&
    remap_prep$receipt$complete_apim==result$receipt$complete_apim&&
    remap_prep$receipt$complete_apimem==result$receipt$complete_apimem)
  for(module in c('demographic','health')) {
    changed<-if(module=='demographic')demo else health
    changed$ID[1]<-sprintf('%011d',n+100L)
    path<-file.path(fixture,paste0('crosswalk_unmapped_',module,'.dta'));haven::write_dta(changed,path)
    candidate_paths<-crosswalk_paths;candidate_paths[[module]]<-path
    check(paste0('unmapped_',module,'_identity_blocks'),blocks_with(charls_swap_read_sources(candidate_paths,crosswalk_contract),
      paste('Person ID absent from official crosswalk in',module)))
    bad_contract<-crosswalk_contract;bad_contract$key_modes[[module]]<-'charls2011_household_person'
    check(paste0('mixed_legacy_',module,'_key_mode_blocks'),fails(charls_swap_validate_contract(bad_contract)))
  }
  bad_contract<-crosswalk_contract;bad_contract$spouse_link$crosswalk$sha256<-digest::digest('wrong synthetic SHA',algo='sha256')
  check('crosswalk_wrong_source_sha_blocks',blocks_with(charls_swap_read_sources(crosswalk_paths,bad_contract),'Crosswalk source SHA256 mismatch'))
  bad_contract<-crosswalk_contract;bad_contract$spouse_link$spouse_missing_values<-c('0','-9')
  check('crosswalk_extra_missing_codes_block',fails(charls_swap_validate_contract(bad_contract)))
  bad_contract<-crosswalk_contract;bad_contract$spouse_link$spouse_missing_values<-NULL
  check('zero_missing_requires_explicit_declaration',fails(charls_swap_validate_contract(bad_contract)))
  bad<-crosswalk_persons;attr(bad,'charls_source_evidence')<-NULL
  check('canonical_crosswalk_input_requires_bound_read_evidence',fails(charls_prepare_apim_swap(bad,crosswalk_contract,file.path(test_root,'crosswalk_unbound'))))
  for(label in c('duplicate_old','duplicate_new','unmapped','numeric_old','bad_sentinel','whitespace')) {
    changed<-crosswalk_data
    if(label=='duplicate_old')changed$ID_w1[2]<-changed$ID_w1[1]
    if(label=='duplicate_new')changed$ID[2]<-changed$ID[1]
    if(label=='unmapped')changed$ID_w1[1]<-''
    if(label=='numeric_old')changed$ID_w1<-suppressWarnings(as.numeric(changed$ID_w1))
    if(label=='bad_sentinel')changed$s1id[1]<-'-9'
    if(label=='whitespace')changed$ID_w1[1]<-paste0(' ',changed$ID_w1[1])
    path<-file.path(fixture,paste0('crosswalk_',label,'.dta'));haven::write_dta(changed,path)
    candidate_paths<-crosswalk_paths;candidate_paths[['harmonized']]<-path
    candidate_contract<-crosswalk_contract;candidate_contract$spouse_link$crosswalk$sha256<-charls_swap_sha(path)
    check(paste0('crosswalk_rejects_',label),fails(charls_swap_read_sources(candidate_paths,candidate_contract)))
  }
  for(module in c('demographic','health')) {
    changed<-if(module=='demographic')demo else health
    changed$householdID[1]<-house[3]
    path<-file.path(fixture,paste0('crosswalk_household_conflict_',module,'.dta'))
    haven::write_dta(changed,path)
    candidate_paths<-crosswalk_paths;candidate_paths[[module]]<-path
    check(paste0('crosswalk_rejects_household_conflict_',module),blocks_with(
      charls_swap_read_sources(candidate_paths,crosswalk_contract),'2011 ID/household format mismatch'))
  }
  bad<-persons;bad$spouse_pid[1]<-'0'
  check('legacy_contract_never_silently_normalizes_zero',fails(charls_prepare_apim_swap(bad,contract,file.path(test_root,'legacy_zero'))))
  # 只为展示代码构造合成效应对象；不把这个对象或渲染结果当作 Mplus 估计验收。
  synthetic_effects<-do.call(rbind,lapply(names(run$compiled),function(id) {
    e<-run$compiled[[id]]$effects;n_effects<-nrow(e)
    e$model_id<-id;e$family<-run$plan$models[[id]]$family
    e$estimate<-sin(seq_len(n_effects));e$se<-rep(1/10,n_effects)
    e$lower95<-e$estimate-2*e$se;e$upper95<-e$estimate+2*e$se
    e$p<-e$p_BH<-e$p_BY<-rep(1/2,n_effects)
    e$interval_method<-'Mplus_MLR_spouse_cluster_delta_normal';e$p_method<-'MLR_cluster_robust_Wald_normal'
    e$display_label<-paste('SYNTHETIC',e$family,e$kind,e$label);e
  }))
  saveRDS(synthetic_effects,file.path(cfg$output_dir,'effects.rds'))
  display_dir<-file.path(test_root,'synthetic_display');display<-charls_render_apim_swap(cfg,display_dir)
  check('display_adapter_preserves_numeric_cache',isTRUE(display$numeric_columns_unchanged)&&
    identical(readRDS(file.path(cfg$output_dir,'effects.rds')),synthetic_effects))
  xml_dir<-file.path(test_root,'docx_xml');dir.create(xml_dir)
  utils::unzip(file.path(display_dir,'tables.docx'),files='word/document.xml',exdir=xml_dir)
  xml<-paste(readLines(file.path(xml_dir,'word/document.xml'),warn=FALSE),collapse='')
  check('word_and_html_state_community_not_spouse',grepl('Mplus_MLR_community_cluster_delta_normal',xml,fixed=TRUE)&&
    !grepl('Mplus_MLR_spouse_cluster_delta_normal',xml,fixed=TRUE)&&
    any(grepl('Mplus_MLR_community_cluster_delta_normal',readLines(file.path(display_dir,'tables','effects.html')),fixed=TRUE)))
  check('synthetic_display_produces_two_figure_sets_and_table',length(list.files(file.path(display_dir,'figures'),pattern='\\.(png|pdf|svg)$'))==6L&&
    file.exists(file.path(display_dir,'tables.docx')))
  # 真正运行 CLI 至拒绝点，验证 JSON 源合同与路径绑定；任何平台都不给拟合许可。
  make_request<-function(label,candidate,source_paths=paths) {
    root<-file.path(test_root,label);dir.create(root);snapshot<-file.path(root,'source_snapshot');dir.create(snapshot)
    copies<-file.path(snapshot,basename(source_paths));stopifnot(all(file.copy(source_paths,copies)))
    source_hashes<-vapply(source_paths,charls_swap_sha,'')
    entries<-setNames(lapply(seq_along(source_paths),function(i)list(path=normalizePath(copies[i],winslash='/'),sha256=unname(source_hashes[i]))),names(source_paths))
    fake_gate<-file.path(root,'deny_gate.py');writeLines('raise SystemExit(7)',fake_gate)
    request<-list(root=normalizePath(root,winslash='/'),attempt_id=paste0('SYNTHETIC_',label),sources=entries,
      scientific_contract=candidate,engine=engine,python=python,gate_script=normalizePath(fake_gate,winslash='/'),
      protected_roots=character(),config_sha256=digest::digest(label,algo='sha256'),grant_sha256=digest::digest('synthetic denied',algo='sha256'),
      expected_models=data.frame(id=names(run$plan$models),family=vapply(run$plan$models,`[[`,'','family'),row.names=NULL))
    path<-file.path(root,'request.json');jsonlite::write_json(request,path,auto_unbox=TRUE,null='null',pretty=TRUE)
    list(root=root,path=path)
  }
  for(case in c('unverified','denied','crosswalk')) {
    req<-if(case=='crosswalk')make_request(paste0('driver_',case),crosswalk_contract,crosswalk_paths) else
      make_request(paste0('driver_',case),if(case=='unverified')charls_apim_swap_contract() else contract)
    log<-file.path(req$root,'driver_test.log')
    status<-suppressWarnings(system2(file.path(R.home('bin'),if(.Platform$OS.type=='windows')'Rscript.exe' else 'Rscript'),
      vapply(c('--vanilla',file.path(skill_root,'scripts','charls_apim_swap_driver.R'),'--request',req$path),shQuote,''),stdout=log,stderr=log))
    text<-paste(readLines(log,warn=FALSE),collapse='\n')
    expected_error<-if(case=='unverified')'BLOCKED_UNVERIFIED_SPOUSE_LINK' else
      if(.Platform$OS.type=='windows')'FIT_GATE_NOT_ADMITTED' else 'Fit gate requires native Windows'
    check(paste0('driver_',case,'_stops_before_fit'),status!=0&&grepl(expected_error,text,fixed=TRUE)&&
      !file.exists(file.path(req$root,'FIT_ADMITTED.json'))&&!file.exists(file.path(req$root,'DRIVER_COMPLETE.json'))&&
      !length(list.files(req$root,pattern='\\.out$',recursive=TRUE)))
    if(case%in%c('denied','crosswalk'))check(paste0('driver_',case,'_json_contract_reaches_exact_two_inputs'),
      length(list.files(file.path(req$root,'models_run','models'),pattern='step1\\.inp$',recursive=TRUE))==2L)
  }
  result<-list(status='PASS_SYNTHETIC_PREPARE_COMPILE_ONLY',checks=checks,new_mplus_calls=0L,
    real_charls_pair_identity_verified=FALSE,scientific_released=FALSE,
    code_sha256=vapply(file.path(skill_root,c('scripts/charls_apim_swap.R','assets/charls_apim_swap_config_v2.R',
      'scripts/charls_apim_swap_driver.R','scripts/test_charls_apim_swap.R')),charls_swap_sha,''))
  jsonlite::write_json(result,file.path(test_root,'TEST_RECEIPT.json'),auto_unbox=TRUE,pretty=TRUE)
  writeLines(capture.output(sessionInfo()),file.path(test_root,'sessionInfo.txt'))
  cat('CHARLS_SWAP_SYNTHETIC_PASS',length(checks),'checks; Mplus calls 0\n');invisible(result)
}
