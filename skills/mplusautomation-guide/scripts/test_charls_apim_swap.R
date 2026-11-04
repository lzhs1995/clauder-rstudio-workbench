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
  make_request<-function(label,candidate) {
    root<-file.path(test_root,label);dir.create(root);snapshot<-file.path(root,'source_snapshot');dir.create(snapshot)
    copies<-file.path(snapshot,basename(paths));stopifnot(all(file.copy(paths,copies)))
    entries<-setNames(lapply(seq_along(paths),function(i)list(path=normalizePath(copies[i],winslash='/'),sha256=unname(hashes[i]))),names(paths))
    fake_gate<-file.path(root,'deny_gate.py');writeLines('raise SystemExit(7)',fake_gate)
    request<-list(root=normalizePath(root,winslash='/'),attempt_id=paste0('SYNTHETIC_',label),sources=entries,
      scientific_contract=candidate,engine=engine,python=python,gate_script=normalizePath(fake_gate,winslash='/'),
      protected_roots=character(),config_sha256=digest::digest(label,algo='sha256'),grant_sha256=digest::digest('synthetic denied',algo='sha256'),
      expected_models=data.frame(id=names(run$plan$models),family=vapply(run$plan$models,`[[`,'','family'),row.names=NULL))
    path<-file.path(root,'request.json');jsonlite::write_json(request,path,auto_unbox=TRUE,null='null',pretty=TRUE)
    list(root=root,path=path)
  }
  for(case in c('unverified','denied')) {
    req<-make_request(paste0('driver_',case),if(case=='unverified')charls_apim_swap_contract() else contract)
    log<-file.path(req$root,'driver_test.log')
    status<-suppressWarnings(system2(file.path(R.home('bin'),if(.Platform$OS.type=='windows')'Rscript.exe' else 'Rscript'),
      vapply(c('--vanilla',file.path(skill_root,'scripts','charls_apim_swap_driver.R'),'--request',req$path),shQuote,''),stdout=log,stderr=log))
    text<-paste(readLines(log,warn=FALSE),collapse='\n')
    expected_error<-if(case=='unverified')'BLOCKED_UNVERIFIED_SPOUSE_LINK' else
      if(.Platform$OS.type=='windows')'FIT_GATE_NOT_ADMITTED' else 'Fit gate requires native Windows'
    check(paste0('driver_',case,'_stops_before_fit'),status!=0&&grepl(expected_error,text,fixed=TRUE)&&
      !file.exists(file.path(req$root,'FIT_ADMITTED.json'))&&!file.exists(file.path(req$root,'DRIVER_COMPLETE.json'))&&
      !length(list.files(req$root,pattern='\\.out$',recursive=TRUE)))
    if(case=='denied')check('driver_json_contract_reaches_exact_two_inputs',
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
