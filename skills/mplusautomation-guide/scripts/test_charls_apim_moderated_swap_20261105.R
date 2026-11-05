# 完全合成的 CHARLS 形状夫妻宽表与调节来源；ID、取值都由生成器产生，禁止换成真实个体夹具。不调用 Mplus。
test_charls_apim_moderated_swap <- function(skill_root,test_root,engine,python) {
  source(file.path(skill_root,'scripts','workflow.R'),local=TRUE)
  source(file.path(skill_root,'scripts','charls_apim_moderated_swap.R'),local=TRUE)
  source(file.path(skill_root,'assets','charls_apim_moderated_swap_config_v1.R'),local=TRUE)
  stopifnot(!dir.exists(test_root));dir.create(test_root,recursive=TRUE)
  checks<-list();check<-function(name,value){stopifnot(isTRUE(value));checks[[name]]<<-TRUE;cat('PASS',name,'\n');flush.console()}
  # 只接受指定原因的报错，避免别的错误冒充“按设计阻断”。
  blocks<-function(x,pattern){e<-tryCatch({force(x);NULL},error=identity);inherits(e,'error')&&grepl(pattern,conditionMessage(e),fixed=TRUE)}
  # 夫妻宽表：列与回执字段同 charls_prepare_apim_swap() 的输出。
  fixture<-file.path(test_root,'source');dir.create(fixture)
  set.seed(5207L);n<-96L;house<-sprintf('%09d',seq_len(n))
  id1<-paste0(house,'001');id2<-paste0(house,'002')
  wide<-data.frame(couple_wave_id=paste0('2011:12:',id1,'12:',id2),community_id=sprintf('SYN_COMM_%02d',rep(1:12,each=8)),
    member1_id=id1,member2_id=id2,member1_age=round(runif(n,45,85)),member2_age=round(runif(n,45,85)),
    member1_adl=sample(0:6,n,TRUE),member2_adl=sample(0:6,n,TRUE),
    member1_cesd10=sample(0:30,n,TRUE),member2_cesd10=sample(0:30,n,TRUE),stringsAsFactors=FALSE)
  wide$member1_cesd10[3]<-NA_real_;wide$member2_adl[5]<-NA_real_
  # #79 风格的配偶合同：三项核验都为 TRUE，文档哈希为合成值；回执的 contract_sha256 是它的 digest
  doc<-function(x)digest::digest(paste('synthetic',x),algo='sha256')
  couple_contract<-list(schema_version=1L,wave=2011L,
    spouse_link=list(verified=TRUE,reciprocity_required=TRUE,spouse_id_column='spouse_id',documentation_sha256=doc('spouse')),
    missing_codes_verified=TRUE,missing_codes_documentation_sha256=doc('missing'),
    identity_codes_verified=TRUE,identity_documentation_sha256=doc('identity'))
  write_couples<-function(d,label,status='PASS_PREPARE_ONLY',couples=nrow(d),sha=NULL,k=couple_contract,write_rds=TRUE,contract_sha=NULL) {
    dir<-file.path(fixture,label);dir.create(dir);data<-file.path(dir,'charls_couples_2011_v2.dta');haven::write_dta(d,data)
    if(write_rds)saveRDS(k,file.path(dir,'source_contract.rds'))
    receipt<-list(status=status,wave=2011L,couples=couples,cluster='community',
      data_sha256=if(is.null(sha))charls_mod_sha(data) else sha,
      contract_sha256=if(is.null(contract_sha))digest::digest(k,algo='sha256') else contract_sha)
    rp<-file.path(dir,'preparation_receipt.json');jsonlite::write_json(receipt,rp,auto_unbox=TRUE,pretty=TRUE,null='null')
    list(data=data,receipt=rp,contract=file.path(dir,'source_contract.rds'))
  }
  couples<-write_couples(wide,'couples')
  # 调节来源：住户层城乡，同户两人取值相同；含原生缺失、标记缺失与一个已声明的数值缺失码。
  rural<-rep(c(0,1),length.out=n);rural[c(2,4)]<-0;rural[c(6,8)]<-1
  harmonized<-data.frame(ID=c(id1,id2,sprintf('%09d999',n+1:4)),h1rural=c(rural,rural,c(0,1,1,0)),stringsAsFactors=FALSE)
  harmonized$h1rural[c(7,n+7)]<-NA_real_
  harmonized$h1rural[c(9,n+9)]<-haven::tagged_na('d')
  harmonized$h1rural[c(11,n+11)]<-9
  harmonized$h1rural<-haven::labelled(harmonized$h1rural,c(urban=0,rural=1))
  hpath<-file.path(fixture,'harmonized_moderator_synthetic_v1.dta');haven::write_dta(harmonized,hpath)
  hashes<-c(couples=charls_mod_sha(couples$data),receipt=charls_mod_sha(couples$receipt),harmonized=charls_mod_sha(hpath),
    contract=charls_mod_sha(couples$contract))
  # 合同：默认阻断；合成文档哈希只为放行合成数据。
  default<-charls_apim_moderated_swap_contract()
  check('unverified_default_moderator_contract_blocks',blocks(charls_apim_moderated_validate_contract(default),'BLOCKED_UNVERIFIED_MODERATOR_CODES'))
  contract<-default;contract$moderator$codes_verified<-TRUE
  check('verified_flag_without_codebook_evidence_blocks',blocks(charls_apim_moderated_validate_contract(contract),'BLOCKED_UNVERIFIED_MODERATOR_CODES'))
  contract$moderator$codes_documentation_sha256<-digest::digest('synthetic moderator codebook',algo='sha256')
  contract$moderator$codes_documentation_locator<-'synthetic generator: 0 urban, 1 rural, 9 declared missing'
  contract$moderator$missing_codes<-9
  check('verified_contract_passes',isTRUE(charls_apim_moderated_validate_contract(contract)))
  bad<-contract;bad$moderator$missing_codes<-c(1,9)
  check('missing_code_overlapping_valid_code_blocks',blocks(charls_apim_moderated_validate_contract(bad),'disjoint'))
  bad<-contract;bad$moderator$scope<-'paired'
  check('paired_scope_not_accepted_for_household_moderator',blocks(charls_apim_moderated_validate_contract(bad),'household-level shared'))
  bad<-contract;bad$moderator$spouse_discordance_policy<-'use_member1'
  check('discordance_policy_cannot_pick_a_spouse',blocks(charls_apim_moderated_validate_contract(bad),'discordance'))
  bad<-contract;bad$moderator$output_column<-'member1_age'
  check('output_column_cannot_overwrite_couple_column',blocks(charls_apim_moderated_validate_contract(bad),'new lower-case name'))
  bad<-contract;bad$moderator$labels<-list(urban=0,rural=0)
  check('each_valid_code_needs_one_label',blocks(charls_apim_moderated_validate_contract(bad),'one label'))
  # 读调节来源：默认合同不读真实数据；声明码、标记缺失、原生缺失都成 NA，未登记的码阻断。
  check('default_contract_reads_nothing',blocks(charls_apim_moderated_read_moderator(hpath,default),'BLOCKED_UNVERIFIED_MODERATOR_CODES'))
  moderator<-charls_apim_moderated_read_moderator(hpath,contract);ev<-attr(moderator,'charls_moderator_evidence')
  check('moderator_ids_kept_as_character',identical(moderator$pid,harmonized$ID))
  check('declared_tagged_and_native_missing_become_na',is.numeric(moderator$w)&&!inherits(moderator$w,'haven_labelled')&&
    identical(which(is.na(moderator$w)),sort(c(7L,9L,11L,n+7L,n+9L,n+11L)))&&
    ev$declared_codes_replaced==2L&&ev$tagged_missing==2L&&ev$native_missing==4L)
  plain<-harmonized;plain$h1rural<-as.numeric(haven::zap_labels(plain$h1rural))
  write_source<-function(d,label){p<-file.path(fixture,paste0('harmonized_',label,'_v1.dta'));haven::write_dta(d,p);p}
  odd<-plain;odd$h1rural[1]<-2
  check('unreviewed_source_code_blocks',blocks(charls_apim_moderated_read_moderator(write_source(odd,'unreviewed'),contract),'BLOCKED_UNREVIEWED_MODERATOR_CODE'))
  odd<-plain;odd$ID<-as.numeric(odd$ID)
  check('numeric_person_ids_block',blocks(charls_apim_moderated_read_moderator(write_source(odd,'numeric_id'),contract),'12-digit character'))
  odd<-rbind(plain,plain[1,])
  check('duplicate_person_ids_block',blocks(charls_apim_moderated_read_moderator(write_source(odd,'duplicate'),contract),'Duplicate person identity'))
  # 追加到夫妻宽表：同户两人共用一个值；期望值按生成器独立写出。
  prep<-charls_apim_moderated_attach(couples$data,couples$receipt,moderator,contract,file.path(test_root,'prepared'))
  out<-as.data.frame(haven::read_dta(prep$data_path))
  expected_w<-rural;expected_w[c(7,9,11)]<-NA_real_
  check('shared_moderator_attached_once_per_couple',nrow(out)==n&&identical(as.numeric(out$couple_rural),expected_w))
  check('couple_columns_unchanged',isTRUE(all.equal(haven::zap_formats(out[names(wide)]),wide,check.attributes=FALSE)))
  cc<-complete.cases(cbind(wide[c('member1_age','member2_age','member1_cesd10','member2_cesd10')],expected_w))
  ccm<-cc&complete.cases(wide[c('member1_adl','member2_adl')])
  check('receipt_complete_case_counts',prep$receipt$complete_apimom==sum(cc)&&prep$receipt$complete_apimemom==sum(ccm)&&
    sum(cc)==n-4L&&sum(ccm)==n-5L&&prep$receipt$moderator_missing_couples==3L)
  check('receipt_binds_couple_table_and_contracts',identical(prep$receipt$status,'PASS_MODERATED_PREPARE_ONLY')&&
    identical(prep$receipt$couples_data_sha256,unname(hashes['couples']))&&identical(prep$receipt$couples_receipt_sha256,unname(hashes['receipt']))&&
    identical(prep$receipt$data_sha256,charls_mod_sha(prep$data_path))&&identical(prep$receipt$new_mplus_calls,0L)&&
    identical(prep$receipt$couples_contract_sha256,digest::digest(couple_contract,algo='sha256'))&&
    identical(prep$receipt$couples_contract_file_sha256,unname(hashes['contract'])))
  check('preparation_never_overwrites_existing_attempt',
    blocks(charls_apim_moderated_attach(couples$data,couples$receipt,moderator,contract,file.path(test_root,'prepared')),'already exists'))
  att<-function(c,m=moderator,label)charls_apim_moderated_attach(c$data,c$receipt,m,contract,file.path(test_root,paste0('bad_',label)))
  check('display_receipt_is_not_a_couple_table',blocks(att(write_couples(wide,'display','PASS_DISPLAY_LABEL_ADAPTER'),label='display'),'PASS_PREPARE_ONLY receipt'))
  check('receipt_hash_mismatch_blocks',blocks(att(write_couples(wide,'stale',sha=strrep('0',64)),label='stale'),'PASS_PREPARE_ONLY receipt'))
  check('receipt_count_mismatch_blocks',blocks(att(write_couples(wide,'count',couples=n-1L),label='count'),'Couple count differs'))
  m<-moderator[moderator$pid!=id2[1],]
  check('member_absent_from_moderator_source_blocks',blocks(att(couples,m,'absent'),'absent from moderator source'))
  m<-moderator;m$w[match(id2[2],m$pid)]<-NA_real_
  check('one_sided_missing_moderator_blocks',blocks(att(couples,m,'one_sided'),'BLOCKED_ONE_SIDED_MODERATOR_MISSING'))
  m<-moderator;k<-match(id2[2],m$pid);m$w[k]<-1-m$w[k]
  check('discordant_spouse_moderator_blocks',blocks(att(couples,m,'discordant'),'BLOCKED_DISCORDANT_SHARED_MODERATOR'))
  m<-moderator;m$w[!is.na(m$w)]<-1
  check('degenerate_moderator_blocks',blocks(att(couples,m,'degenerate'),'Degenerate moderator'))
  coll<-wide;coll$member1_age<-50+10*ifelse(is.na(expected_w),0,expected_w)
  check('collinear_moderated_predictors_block',blocks(att(write_couples(coll,'collinear'),label='collinear'),'Rank-deficient'))
  # #79 的核验结果：回执必须绑定一份三项都已核验的配偶合同
  check('missing_couple_contract_rds_blocks',blocks(att(write_couples(wide,'no_rds',write_rds=FALSE),label='no_rds'),'source_contract.rds saved'))
  check('receipt_contract_sha_absent_blocks',blocks(att(write_couples(wide,'sha_absent',contract_sha=NA_character_),label='sha_absent'),'64-hex digest'))
  check('receipt_contract_sha_garbage_blocks',blocks(att(write_couples(wide,'sha_garbage',contract_sha='not-a-hash'),label='sha_garbage'),'64-hex digest'))
  check('couple_contract_digest_mismatch_blocks',blocks(att(write_couples(wide,'sha_other',contract_sha=strrep('a',64)),label='sha_other'),'digest differs'))
  for(f in c('spouse','missing','identity')) {
    k<-couple_contract
    if(f=='spouse')k$spouse_link$verified<-FALSE else if(f=='missing')k$missing_codes_verified<-FALSE else k$identity_codes_verified<-FALSE
    check(paste0('unverified_',f,'_in_couple_contract_blocks'),blocks(att(write_couples(wide,paste0('unv_',f),k=k),label=paste0('unv_',f)),'BLOCKED_UNVERIFIED_COUPLE_CONTRACT'))
  }
  k<-couple_contract;k$spouse_link$documentation_sha256<-'documented'
  check('couple_contract_doc_hash_format_blocks',blocks(att(write_couples(wide,'doc_fmt',k=k),label='doc_fmt'),'spouse link is not verified'))
  # 复审里那份手写回执：没跑 #79，没有合同文件，contract_sha256 是一句话
  check('hand_written_receipt_blocks',blocks(att(write_couples(wide,'forged',write_rds=FALSE,contract_sha='hand-written, no #79 contract'),label='forged'),'BLOCKED_UNBOUND_COUPLE_CONTRACT'))
  self<-wide;self$member2_id<-self$member1_id
  check('self_paired_couple_blocks',blocks(att(write_couples(self,'self_pair'),label='self_pair'),'BLOCKED_SELF_PAIRED_COUPLE'))
  # 计划与编译：恰好四个模型，W 原始 0/1，乘积项所在方程随 moderated_paths 变化。
  cfg<-charls_apim_moderated_swap_config(prep$data_path,file.path(test_root,'run'),engine,python)
  plan<-plan_apim_workflow(cfg)
  model_table<-data.frame(id=names(plan$models),family=vapply(plan$models,`[[`,'','family'),
    moderated_paths=vapply(plan$models,function(m)if(is.null(m$moderated_paths))'none' else m$moderated_paths,''),
    row.names=NULL,stringsAsFactors=FALSE)
  check('exactly_four_moderated_models',plan$candidate_count==4L&&plan$execution_count==4L&&
    identical(model_table,charls_apim_moderated_expected_models()))
  run<-run_apim_workflow(cfg,stages=c('check','prepare','compile'))
  check('four_inputs_compiled_no_estimation',length(run$compiled)==4L&&
    all(vapply(run$compiled,function(c)file.exists(c$input)&&!file.exists(c$output),logical(1))))
  for(model in run$plan$models) {
    compiled<-run$compiled[[model$id]];p<-readRDS(file.path(compiled$folder,'prepared.rds'))
    expected_n<-if(model$family=='APIMoM')prep$receipt$complete_apimom else prep$receipt$complete_apimemom
    check(paste0(model$design,'_complete_case_N_and_community_clusters'),p$N==expected_n&&p$clusters==12L&&
      any(grepl('CLUSTER = cid;',readLines(compiled$input),fixed=TRUE)))
    check(paste0(model$design,'_raw_binary_probes'),identical(names(p$probes),c('urban','rural'))&&
      identical(unname(unlist(p$probes)),c(0,1))&&all(vapply(p$moments,function(x)all(x$center==0)&&all(x$scale==1),logical(1))))
  }
  inp<-function(d)toupper(readLines(run$compiled[[paste0(d,'_sample1_x1_y1_m1_w1_step1')]]$input,warn=FALSE))
  has<-function(x,pattern)any(grepl(pattern,x))
  kinds<-function(d)unique(run$compiled[[paste0(d,'_sample1_x1_y1_m1_w1_step1')]]$effects$kind)
  i<-inp('apimom')
  check('apimom_products_in_outcome_equation',has(i,'^\\s*Y1 ON P[0-9]{3} \\(Z1')&&has(i,'^\\s*Y2 ON W1D1;')&&!has(i,'^\\s*M[12] ON'))
  i<-inp('apimemom_a')
  check('apimemom_a_products_in_mediator_equation',has(i,'^\\s*M1 ON P[0-9]{3} \\(U1')&&has(i,'^\\s*M2 ON W1D1;')&&
    !has(i,'^\\s*Y[12] ON W1D1;')&&!has(i,'\\(Z[0-9]'))
  i<-inp('apimemom_b')
  check('apimemom_b_products_in_outcome_equation',has(i,'^\\s*Y2 ON P[0-9]{3} \\(Z2')&&has(i,'^\\s*Y1 ON W1D1;')&&
    !has(i,'^\\s*M[12] ON W1D1;')&&!has(i,'\\(U[0-9]'))
  i<-inp('apimemom_ab')
  check('apimemom_ab_products_in_both_equations',has(i,'^\\s*M1 ON P[0-9]{3} \\(U1')&&has(i,'^\\s*Y2 ON P[0-9]{3} \\(Z2')&&
    has(i,'^\\s*M1 ON W1D1;')&&has(i,'^\\s*Y1 ON W1D1;'))
  check('effect_kinds_follow_moderated_paths',all(c('simple_slope','slope_contrast')%in%kinds('apimom'))&&
    'conditional_a'%in%kinds('apimemom_a')&&!'simple_slope'%in%kinds('apimemom_a')&&
    'simple_slope'%in%kinds('apimemom_b')&&!'conditional_a'%in%kinds('apimemom_b')&&
    all(c('conditional_a','simple_slope','conditional_indirect','conditional_contrast')%in%kinds('apimemom_ab')))
  # 合同经 JSON 往返后仍能通过同一校验，数值字段恢复成向量。
  cpath<-file.path(test_root,'contract_roundtrip.json');jsonlite::write_json(contract,cpath,auto_unbox=TRUE,null='null',pretty=TRUE)
  back<-charls_apim_moderated_contract_from_json(jsonlite::read_json(cpath,simplifyVector=TRUE))
  check('contract_json_roundtrip',isTRUE(charls_apim_moderated_validate_contract(back))&&
    identical(back$moderator$valid_codes,contract$moderator$valid_codes)&&identical(back$moderator$missing_codes,contract$moderator$missing_codes)&&
    identical(back$moderator$labels,contract$moderator$labels)&&identical(back$couples$required_columns,contract$couples$required_columns))
  # 拟合准入：解析 grant 内容逐项核对；与平台无关，各平台都跑
  win<-file.path(test_root,'window');run_root<-file.path(test_root,'grant_run_root')
  for(d in c(file.path(win,'requests'),file.path(win,'grants'),file.path(run_root,'grants')))dir.create(d,recursive=TRUE)
  rname<-'SYNTHETIC-moderated-v1';caps<-list(max_engine_starts=4L,max_wall_seconds=600L,processors_per_model=1L)
  qpath<-file.path(win,'requests',paste0(rname,'.json'))
  qbody<-list(worker='W3',request_id=rname,purpose='synthetic moderated swap',models=4L,hard_cap=caps)
  jsonlite::write_json(qbody,qpath,auto_unbox=TRUE);qsha<-charls_mod_sha(qpath)
  grant_body<-function(...)modifyList(list(approved=TRUE,request_name=rname,request_sha256=qsha,worker='W3',request_id=rname,
    purpose='synthetic moderated swap',models=4L,root=normalizePath(run_root,winslash='/'),hard_cap=caps,
    granted_by='synthetic dispatcher',granted_taipei='2026-11-05 13:00'),list(...))
  # request=换一份窗口请求（SHA 随之重算并写进 grant）；wd=调用时的工作目录；at=本次运行根
  admit<-function(body,dir=file.path(win,'grants'),raw=NULL,request=NULL,wd=NULL,at=run_root){
    qp<-qpath;qs<-qsha
    if(!is.null(request)){qp<-file.path(test_root,'window_alt','requests',paste0(rname,'.json'));dir.create(dirname(qp),recursive=TRUE,showWarnings=FALSE)
      jsonlite::write_json(request,qp,auto_unbox=TRUE);qs<-charls_mod_sha(qp);body$request_sha256<-qs}
    p<-file.path(dir,paste0(rname,'.json'));if(is.null(raw))jsonlite::write_json(body,p,auto_unbox=TRUE,null='null') else writeLines(raw,p)
    old<-getwd();if(!is.null(wd))setwd(wd);on.exit(setwd(old))
    tryCatch(charls_apim_moderated_admit_grant(list(path=p,sha256=charls_mod_sha(p)),list(path=qp,sha256=qs),at,rname,4L),
      error=function(e)conditionMessage(e))}
  denied<-function(x,why)is.character(x)&&startsWith(x,'FIT_GRANT_NOT_ADMITTED')&&grepl(why,x,fixed=TRUE)
  good<-admit(grant_body())
  check('grant_with_matching_content_admitted',is.list(good)&&identical(good$hard_cap,caps)&&identical(good$window_request_sha256,qsha))
  check('grant_approved_false_refused',denied(admit(grant_body(approved=FALSE)),'approved'))
  check('grant_other_worker_refused',denied(admit(grant_body(worker='W1')),'worker'))
  check('grant_empty_file_refused',denied(admit(NULL,raw=''),'JSON object'))
  check('grant_root_mismatch_refused',denied(admit(grant_body(root=normalizePath(test_root,winslash='/'))),'root'))
  check('grant_inside_run_root_refused',denied(admit(grant_body(),dir=file.path(run_root,'grants')),'inside the run root'))
  check('grant_request_sha_mismatch_refused',denied(admit(grant_body(request_sha256=strrep('0',64))),'request_sha256'))
  check('grant_other_request_id_refused',denied(admit(grant_body(request_id='W3-other')),'request_id'))
  check('grant_models_mismatch_refused',denied(admit(grant_body(models=2L)),'models'))
  check('grant_hard_cap_looser_refused',denied(admit(grant_body(hard_cap=modifyList(caps,list(max_wall_seconds=900L)))),'looser'))
  check('grant_hard_cap_missing_refused',denied(admit(grant_body(hard_cap=NULL)),'hard_cap incomplete'))
  check('grant_without_granted_by_refused',denied(admit(grant_body(granted_by=NULL)),'granted_by'))
  # 相对 root：同一份 root="." 的 grant 在两个不同 cwd、两个运行根下都必须拒绝
  other_root<-file.path(test_root,'grant_run_root_b');dir.create(other_root)
  check('grant_relative_root_refused_in_first_cwd',denied(admit(grant_body(root='.'),wd=run_root),'absolute path'))
  check('grant_relative_root_refused_in_second_cwd',denied(admit(grant_body(root='.'),wd=other_root,at=other_root),'absolute path'))
  check('grant_relative_subdir_root_refused',denied(admit(grant_body(root='grant_run_root'),wd=test_root),'absolute path'))
  check('relative_run_root_refused',denied(admit(grant_body(),wd=test_root,at='grant_run_root'),'run root must be an absolute path'))
  # models：先核正整数，不截断；4/4/4 仍放行
  check('grant_fractional_models_refused',denied(admit(grant_body(models=4.5)),'positive integers'))
  check('request_fractional_models_refused',denied(admit(grant_body(),request=modifyList(qbody,list(models=4.9))),'positive integers'))
  check('equal_integer_models_still_admitted',is.list(admit(grant_body(models=4),request=modifyList(qbody,list(models=4)))))
  tight<-admit(grant_body(hard_cap=list(max_engine_starts=4L,max_wall_seconds=300L,processors_per_model=1L)))
  capped<-charls_apim_moderated_swap_config(prep$data_path,file.path(test_root,'run_capped'),engine,python,hard_cap=tight$hard_cap)
  check('admitted_hard_cap_reaches_config',identical(capped$execution$wait_limit_seconds,300L)&&identical(capped$execution$processor_budget,1L)&&
    identical(cfg$execution$wait_limit_seconds,14400))
  # 真正运行 CLI 驱动到拒绝点：未核验合同在读数据前停；已核验合同编译四个输入后，在拟合授权处停。
  make_request<-function(label,candidate) {
    root<-file.path(test_root,label);dir.create(root);own<-file.path(root,'inputs');dir.create(own)
    copies<-file.path(own,c('charls_couples_2011_v2.dta','preparation_receipt.json',basename(hpath),'source_contract.rds'))
    stopifnot(all(file.copy(c(couples$data,couples$receipt,hpath,couples$contract),copies)))
    entry<-function(p)list(path=normalizePath(p,winslash='/'),sha256=charls_mod_sha(p))
    grants<-file.path(root,'grants');dir.create(grants);grant<-file.path(grants,paste0('SYNTHETIC_',label,'.json'))
    writeLines('{"synthetic": "not an approval"}',grant)
    request<-list(request_name=paste0('SYNTHETIC_',label),root=normalizePath(root,winslash='/'),attempt_id=paste0('SYNTHETIC_',label,'_1'),
      couples_data=entry(copies[1]),couples_receipt=entry(copies[2]),moderator_source=entry(copies[3]),couples_contract=entry(copies[4]),
      window_request=list(path=normalizePath(qpath,winslash='/'),sha256=qsha),
      moderated_contract=candidate,engine=engine,python=python,protected_roots=character(),
      expected_models=charls_apim_moderated_expected_models(),
      # SHA 故意不匹配：任何平台都不给拟合许可。
      grant=list(path=normalizePath(grant,winslash='/'),sha256=digest::digest('synthetic denied',algo='sha256')))
    path<-file.path(root,'request.json');jsonlite::write_json(request,path,auto_unbox=TRUE,null='null',pretty=TRUE)
    list(root=root,path=path)
  }
  rscript<-file.path(R.home('bin'),if(.Platform$OS.type=='windows')'Rscript.exe' else 'Rscript')
  for(case in c('unverified','denied')) {
    req<-make_request(paste0('driver_',case),if(case=='unverified')default else contract)
    log<-file.path(req$root,'driver_test.log')
    status<-suppressWarnings(system2(rscript,vapply(c('--vanilla',file.path(skill_root,'scripts','charls_apim_moderated_swap_driver.R'),
      '--request',req$path),shQuote,''),stdout=log,stderr=log))
    text<-paste(readLines(log,warn=FALSE),collapse='\n')
    expected_error<-if(case=='unverified')'BLOCKED_UNVERIFIED_MODERATOR_CODES' else
      if(.Platform$OS.type=='windows')'FIT_GRANT_NOT_ADMITTED' else 'Fit gate requires native Windows'
    check(paste0('driver_',case,'_stops_before_fit'),status!=0&&grepl(expected_error,text,fixed=TRUE)&&
      !file.exists(file.path(req$root,'FIT_STARTED.json'))&&!file.exists(file.path(req$root,'DRIVER_COMPLETE.json'))&&
      !length(list.files(req$root,pattern='\\.out$',recursive=TRUE)))
    if(case=='unverified')check('driver_unverified_writes_no_prepared_table',!dir.exists(file.path(req$root,'prepared_moderated')))
    if(case=='denied')check('driver_json_contract_reaches_exact_four_inputs',
      length(list.files(file.path(req$root,'models_run','models'),pattern='step1\\.inp$',recursive=TRUE))==4L&&
      file.exists(file.path(req$root,'prepared_moderated','moderated_preparation_receipt.json')))
  }
  check('source_files_unchanged',identical(c(couples=charls_mod_sha(couples$data),receipt=charls_mod_sha(couples$receipt),
    harmonized=charls_mod_sha(hpath),contract=charls_mod_sha(couples$contract)),hashes))
  result<-list(status='PASS_SYNTHETIC_PREPARE_COMPILE_ONLY',checks=checks,new_mplus_calls=0L,
    real_moderator_codes_verified=FALSE,real_charls_pair_identity_verified=FALSE,scientific_released=FALSE,
    code_sha256=vapply(file.path(skill_root,c('scripts/charls_apim_moderated_swap.R','assets/charls_apim_moderated_swap_config_v1.R',
      'scripts/charls_apim_moderated_swap_driver.R','scripts/test_charls_apim_moderated_swap_20261105.R')),charls_mod_sha,''))
  names(result$code_sha256)<-basename(names(result$code_sha256))
  jsonlite::write_json(result,file.path(test_root,'TEST_RECEIPT.json'),auto_unbox=TRUE,pretty=TRUE)
  writeLines(capture.output(sessionInfo()),file.path(test_root,'sessionInfo.txt'))
  cat('CHARLS_MODERATED_SWAP_SYNTHETIC_PASS',length(checks),'checks; Mplus calls 0\n');invisible(result)
}
