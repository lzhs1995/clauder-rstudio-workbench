# 小样本合成验收：不读真实数据、不运行 Mplus，比较可观察的准备数据和模型输入。
test_apim_v2_data_adapter <- function(skill_root,test_root,engine,python) {
  source(file.path(skill_root,'scripts','workflow.R'),local=TRUE)
  source(file.path(skill_root,'assets','example_config_v2.R'),local=TRUE)
  stopifnot(requireNamespace('haven',quietly=TRUE),!dir.exists(test_root))
  dir.create(test_root,recursive=TRUE);fixtures<-file.path(test_root,'fixtures');dir.create(fixtures)
  checks<-list();check<-function(name,ok){stopifnot(isTRUE(ok));checks[[name]]<<-TRUE;cat('PASS',name,'\n');flush.console()}
  fails<-function(expr)inherits(tryCatch({force(expr);NULL},error=identity),'error')
  d<-data.frame(record=sprintf('0009007199254741%03d',1:32),pair=rep(sprintf('000%03d',1:16),each=2),
    x1=sin(1:32),x2=cos(1:32),m1=sin((1:32)/2),m2=cos((1:32)/3),
    y1=sin((1:32)/4),y2=cos((1:32)/5),stringsAsFactors=FALSE)
  d$x1[1]<-.10000000000000002;d$x1[2]<- -9;d$x2[6]<- -7
  d$m1[3]<-haven::tagged_na('a');d$y2[4]<-NA_real_;d$y1[5]<-99.9
  d$x1<-haven::labelled(d$x1,c(refused=-9))
  csv<-file.path(fixtures,'synthetic_cfps_v2.csv');dta<-file.path(fixtures,'synthetic_charls_v2.dta')
  # CSV 使用 17 位往返字符串，避免写入工具自身精度变化与读取适配混淆。
  csv_data<-d
  for(n in setdiff(names(d),c('record','pair')))csv_data[[n]]<-ifelse(is.na(d[[n]]),NA_character_,sprintf('%.17g',as.numeric(d[[n]])))
  names(csv_data)<-paste0('cfps_',names(d));write.csv(csv_data,csv,row.names=FALSE,na='NA')
  dta_data<-d[,rev(names(d))];names(dta_data)<-paste0('charls_',names(dta_data));haven::write_dta(dta_data,dta)
  make_config<-function(path,mode,prefix,run) {
    c<-example_apim_config_v2(path,file.path(test_root,'runs',run),engine,python)
    c$designs<-c$designs[c('apim','apimem')]
    for(k in names(c$designs)) {
      c$designs[[k]]$steps<-list(free=list(equal=list()))
      c$designs[[k]]$controls<-list()
    }
    c$samples<-list(all=list(filter=list()));c$data_mode<-mode
    c$column_map<-setNames(paste0(prefix,names(d)),names(d))
    c$missing_codes<-list(x1=-9,y1=99.9)
    c
  }
  cc<-make_config(csv,'csv','cfps_','csv');cd<-make_config(dta,'dta','charls_','dta')
  originals<-vapply(c(csv,dta),apim_sha,'',file=TRUE)
  check('planning_reads_both_formats_without_run_directory',plan_apim_workflow(cc)$candidate_count==2&&
    plan_apim_workflow(cd)$candidate_count==2&&!dir.exists(cc$output_dir)&&!dir.exists(cd$output_dir))
  rc<-apim_v2_read(cc,csv);rd<-apim_v2_read(cd,dta)
  check('long_character_ids_and_leading_zeros_preserved',identical(rc$record,d$record)&&identical(rd$record,d$record)&&identical(rd$pair,d$pair))
  check('numeric_labels_keep_underlying_codes',as.numeric(rd$x1[1])==as.numeric(d$x1[1])&&is.na(rd$x1[2]))
  check('tagged_missing_normalized_and_counted',is.na(rd$m1[3])&&attr(rd,'apim_source_adapter')$column_audit$m1$tagged_missing==1L)
  check('explicit_numeric_decimal_missing_code',is.na(rd$y1[5])&&is.na(rc$y1[5]))
  check('undeclared_negative_values_retained',identical(as.numeric(rd$x2[6]),-7)&&identical(as.numeric(rc$x2[6]),-7))
  check('source_order_and_names_do_not_change_values',all(vapply(names(d),function(n)
    if(n%in%c('record','pair'))identical(rc[[n]],rd[[n]]) else isTRUE(all.equal(as.numeric(rc[[n]]),rd[[n]],tolerance=1e-14)),logical(1))))
  check('dta_numeric_filter_keeps_exact_value',nrow(apim_v2_filter(rd,list(x1=as.numeric(d$x1[1]))))==1L&&
    nrow(apim_v2_filter(rd,list(x1=.1)))==0L)
  # 交换成员仅通过映射声明；模型无需改写。
  swapped<-cd;swapped$column_map[c('x1','x2')]<-swapped$column_map[c('x2','x1')]
  rs<-apim_v2_read(swapped,dta)
  check('explicit_member_swap_is_respected',identical(as.numeric(rs$x1[6]),-7)&&as.numeric(rs$x2[1])==as.numeric(d$x1[1]))
  a<-run_apim_workflow(cc,stages=c('check','prepare','compile'))
  b<-run_apim_workflow(cd,stages=c('check','prepare','compile'))
  for(id in names(a$compiled)) {
    pa<-readRDS(file.path(a$compiled[[id]]$folder,'prepared.rds'))
    pb<-readRDS(file.path(b$compiled[[id]]$folder,'prepared.rds'))
    check(paste0(id,'_identical_numeric_preparation'),isTRUE(all.equal(pa$data,pb$data,tolerance=1e-14)))
    check(paste0(id,'_explicit_complete_case_count'),pa$N==if(a$plan$models[[id]]$family=='APIM')29L else 28L)
    check(paste0(id,'_identical_model_syntax'),identical(readLines(a$compiled[[id]]$input),readLines(b$compiled[[id]]$input)))
  }
  receipt<-jsonlite::read_json(file.path(cd$output_dir,'audit','data_adapter.json'))
  check('aggregate_adapter_receipt_bound_to_source',identical(receipt$source_sha256,unname(originals[2]))&&
    receipt$column_audit$x1$column_codes_replaced==1&&receipt$rows==32L&&!is.null(receipt$adapter_sha256))
  check('unchanged_contract_resumes',!fails(run_apim_workflow(cd,stages=c('prepare','compile'))))
  bad<-cd;bad$column_map['x1']<-'missing';check('unknown_source_mapping_rejected',fails(plan_apim_workflow(bad)))
  bad<-cd;bad$column_map['x2']<-bad$column_map['x1'];check('duplicate_source_mapping_rejected',fails(plan_apim_workflow(bad)))
  bad<-cd;bad$column_map<-setNames('charls_x1','charls_x2');check('unmapped_name_collision_rejected',fails(plan_apim_workflow(bad)))
  bad<-cd;bad$missing_codes<-list(record=-9);check('identity_missing_recode_rejected',fails(plan_apim_workflow(bad)))
  bad<-cd;bad$missing_codes<-list(absent=-9);check('unknown_missing_code_column_rejected',fails(plan_apim_workflow(bad)))
  bad<-cd;bad$missing_codes$y1<-NULL;check('changed_missingness_contract_rejected',fails(run_apim_workflow(bad,stages='compile')))
  duplicate_csv<-file.path(fixtures,'duplicate_headers_v2.csv');writeLines(c('id,id','1,2'),duplicate_csv)
  bad<-cc;bad$data<-duplicate_csv;check('duplicate_csv_headers_rejected',fails(plan_apim_workflow(bad)))
  unsafe<-d;unsafe$record<-rep(2^53,nrow(d));unsafe_path<-file.path(fixtures,'unsafe_ids_v2.dta');haven::write_dta(unsafe,unsafe_path)
  bad<-cd;bad$column_map<-NULL;check('unsafe_numeric_ids_rejected',fails(apim_v2_read(bad,unsafe_path)))
  dated<-d;dated$x1<-as.Date('2000-01-01')+seq_len(nrow(d));dated_path<-file.path(fixtures,'date_model_v2.dta');haven::write_dta(dated,dated_path)
  check('implicit_date_model_conversion_rejected',fails(apim_v2_read(bad,dated_path)))
  # 非整数类别保留数值比较，不经显示字符串改写类别值。
  catdata<-d;catdata$context<-rep(c(.2,.10000000000000002),16)
  catpath<-file.path(fixtures,'decimal_category_v2.dta');haven::write_dta(catdata,catpath)
  ccat<-cd;ccat$data<-catpath;ccat$column_map<-NULL;ccat$output_dir<-file.path(test_root,'runs','decimal_category')
  ccat$designs<-list(category=ccat$designs$apim);ccat$designs$category$family<-'APIMoM'
  ccat$designs$category$w<-list(context=list(columns='context',scope='shared',type='binary',
    levels=c(.2,.10000000000000002),reference=.2))
  ccat$designs$category$probes<-list(low=list(values=.2,scale='raw'),high=list(values=.10000000000000002,scale='raw'))
  ccat$designs$category$contrasts<-list(high_minus_low=c('high','low'))
  catrun<-run_apim_workflow(ccat,stages=c('check','prepare','compile'))
  catprep<-readRDS(file.path(catrun$compiled[[1]]$folder,'prepared.rds'))
  catrows<-read.csv(file.path(catrun$compiled[[1]]$folder,'selected_rows.csv'),colClasses='character')
  selected_context<-catdata$context[match(catrows$row_id,catdata$record)]
  check('decimal_categories_keep_exact_distinct_codes',identical(catprep$data$w1d1,as.numeric(selected_context==.10000000000000002))&&
    identical(unname(catprep$probes$low),0)&&identical(unname(catprep$probes$high),1))
  bad<-ccat;bad$data_mode<-'archived_dat';bad$data_columns<-names(catdata);bad$data_expected_sha256<-apim_sha(catpath,TRUE)
  bad$transform<-list(scheme='none',reference='analysis_rows',overrides=list())
  check('archived_dat_recoding_rejected',fails(plan_apim_workflow(bad)))
  check('numeric_missing_codes_do_not_round_neighbors',!apim_v2_missing_match(.10000000000000002,.1,TRUE))
  csv_id_path<-file.path(fixtures,'csv_id_missing_v2.csv');writeLines(c('record,pair','01,a','1.0,b','1,c'),csv_id_path)
  oldcfg<-list(data_mode='csv',row_id='record',cluster='pair',missing=1)
  oldread<-read.csv(csv_id_path,colClasses='character',check.names=FALSE,na.strings=1)
  check('legacy_csv_global_missing_matches_exact_strings',identical(apim_v2_read(oldcfg,csv_id_path)$record,oldread$record))
  check('sources_unchanged',identical(vapply(c(csv,dta),apim_sha,'',file=TRUE),originals))
  check('no_mplus_outputs',!any(vapply(c(a$compiled,b$compiled),function(c)file.exists(c$output),logical(1))))
  result<-list(status='PASS_SYNTHETIC_IO_AND_COMPILE_ONLY',checks=checks,new_mplus_calls=0L,
    fixture_rows=32L,source_sha256=as.list(originals),haven_version=as.character(utils::packageVersion('haven')),
    code=apim_v2_code_hash(c('workflow.R','apim_v2_config.R','apim_v2_data_adapter.R','apim_v2_models.R','apim_v2_runtime.R')))
  apim_json(result,file.path(test_root,'TEST_RECEIPT.json'))
  writeLines(capture.output(sessionInfo()),file.path(test_root,'sessionInfo.txt'))
  cat('APIM_V2_DATA_ADAPTER_PASS',length(checks),'checks; Mplus calls: 0\n')
  invisible(result)
}
