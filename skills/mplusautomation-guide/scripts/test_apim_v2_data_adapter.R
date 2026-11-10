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

# 追加：2026-11-08 通用source_spec双源合同测试；独立函数，不依赖原APIM测试对象。
# 依赖：source_spec.R与haven/digest/jsonlite；调用者提供全新的out_dir，不运行任何模型。
test_source_spec <- function(skill_root, out_dir) {
  for (p in c('haven','digest','jsonlite')) stopifnot(requireNamespace(p, quietly=TRUE))
  source(file.path(skill_root, 'scripts', 'source_spec.R'), local=TRUE)
  stopifnot(!file.exists(out_dir), !dir.exists(out_dir))
  dir.create(out_dir, recursive=TRUE)
  fixtures <- file.path(out_dir, 'fixtures'); dir.create(fixtures)
  outputs <- file.path(out_dir, 'outputs'); dir.create(outputs)
  sha <- function(p) digest::digest(p, algo='sha256', file=TRUE)
  checks <- list()
  check <- function(name, ok) {
    stopifnot(isTRUE(ok)); checks[[name]] <<- TRUE; cat('PASS', name, '\n'); flush.console()
  }
  rejects <- function(name, spec, message, exact=FALSE) {
    target <- file.path(outputs, name)
    error <- tryCatch({prepare_mplus_source(spec, target); NULL}, error=identity)
    check(name, inherits(error,'error') && if (exact) identical(conditionMessage(error),message) else grepl(message, conditionMessage(error), fixed=TRUE))
    check(paste0(name,'_writes_nothing'), !file.exists(target))
  }
  values <- data.frame(a=c(.10000000000000002, -9, -7, pi), b=c(2, NA_real_, 4, 5),
    c=c(6, 7, haven::tagged_na('a'), 9), unused=letters[1:4])
  values$a <- haven::labelled(values$a, c(refused=-9))
  csv_data <- values
  for (n in c('a','b','c')) csv_data[[n]] <- ifelse(is.na(values[[n]]), '', sprintf('%.17g', as.numeric(values[[n]])))
  names(csv_data) <- paste0('csv_', names(values))
  csv <- file.path(fixtures, 'source.csv'); write.csv(csv_data, csv, row.names=FALSE, na='')
  dta <- file.path(fixtures, 'source.dta'); dta_data <- values[,rev(names(values))]
  names(dta_data) <- paste0('dta_', names(dta_data)); haven::write_dta(dta_data, dta)
  make_spec <- function(path, mode, prefix) list(schema_version=1L, data=path, data_mode=mode,
    data_expected_sha256=sha(path), columns=c('c','a','b'), column_map=setNames(paste0(prefix,c('a','b','c')),c('a','b','c')),
    missing_codes=list(a=c('', '-9'), b='', c=''), missing=character(), missing_value=-999)
  cs <- make_spec(csv, 'csv', 'csv_'); ds <- make_spec(dta, 'dta', 'dta_')
  csv_out <- file.path(outputs,'csv'); dta_out <- file.path(outputs,'dta')
  cr <- prepare_mplus_source(cs,csv_out); dr <- prepare_mplus_source(ds,dta_out)
  check('two_sources_same_dat', identical(cr$dat_sha256,dr$dat_sha256))
  check('two_sources_same_column_order', identical(cr$column_order_sha256,dr$column_order_sha256))
  check('columns_in_declared_order', identical(readLines(file.path(csv_out,'column_order.txt')),c('c','a','b')))
  result <- read.table(file.path(csv_out,'data.dat'),na.strings='-999',colClasses='numeric')
  check('no_row_filtering_or_imputation', nrow(result)==4L && is.na(result[2,2]) && is.na(result[2,3]) && is.na(result[3,1]))
  check('numeric_precision_17_digit_roundtrip', identical(result[1,2],.10000000000000002) && identical(result[4,2],pi))
  check('undeclared_negative_value_preserved', identical(result[3,2],-7))
  check('dta_tagged_missing_counted', dr$missing_recode_counts$c$tagged_missing==1L)
  check('source_hashes_unchanged', identical(sha(csv),cs$data_expected_sha256) && identical(sha(dta),ds$data_expected_sha256))
  check('receipt_has_no_source_path_or_row_values', !grepl(normalizePath(out_dir,winslash='/'),
    paste(readLines(file.path(csv_out,'source_receipt.json')),collapse='\n'),fixed=TRUE) &&
    identical(cr$rows_removed,0L) && !cr$model_generated && cr$mplus_calls==0L)
  check('source_order_hash_is_raw_utf8_lf', identical(cr$column_order_sha256,digest::digest(charToRaw('c\na\nb\n'),algo='sha256',serialize=FALSE)))
  check('dat_fragment_has_only_data_and_names_missing', !any(grepl('MODEL:|ANALYSIS:|OUTPUT:',readLines(file.path(csv_out,'data_block.inp')))))
  # 三份产物各自按磁盘字节核回执；两个来源互相相等不能证明哈希算对了文件。
  for (mode in c('csv','dta')) {
    folder <- if (mode=='csv') csv_out else dta_out
    expected <- if (mode=='csv') cs$columns else ds$columns
    block <- readLines(file.path(folder,'data_block.inp'))
    begin <- which(block=='NAMES ='); end <- which(block==';')
    check(paste0(mode,'_names_block_has_unique_boundaries'),length(begin)==1L && length(end)==1L && end>begin+1L)
    ordered <- trimws(block[seq.int(begin+1L,end-1L)])
    check(paste0(mode,'_names_order_file_and_spec_agree'),identical(ordered,expected) &&
      identical(ordered,readLines(file.path(folder,'column_order.txt'))))
    receipt <- jsonlite::read_json(file.path(folder,'source_receipt.json'))
    files <- c(dat_sha256='data.dat',column_order_sha256='column_order.txt',data_block_sha256='data_block.inp')
    for (key in names(files)) {
      check(paste0(mode,'_',key,'_matches_disk'),identical(receipt[[key]],sha(file.path(folder,files[[key]]))))
    }
  }
  bad <- cs; bad$column_map['b'] <- 'csv_a'; rejects('duplicate_mapping',bad,'one-to-one')
  bad <- cs; bad$column_map <- c(csv_b='csv_a'); rejects('unmapped_collision',bad,'collides')
  bad <- cs; bad$column_map['a'] <- 'absent'; rejects('missing_source_mapping',bad,'missing source')
  bad <- cs; bad$columns <- c('a','A'); bad$missing_codes <- list(a=character(),A=character()); rejects('duplicate_case_names',bad,'unique Mplus names')
  bad <- cs; bad$columns[1] <- 'bad-name'; rejects('illegal_output_name',bad,'unique Mplus names')
  bad <- cs; bad$columns[1] <- 'toolongname'; rejects('long_output_name',bad,'unique Mplus names')
  bad <- cs; bad$missing_codes$b <- NULL; rejects('missing_code_declaration',bad,'every output column')
  bad <- cs; bad$missing_value <- -7; rejects('sentinel_collision',bad,'collides with observed')
  bad <- cs; bad$data_expected_sha256 <- paste(rep('0',64),collapse=''); rejects('wrong_source_sha',bad,'SHA256 mismatch')
  bad <- cs; bad$data_mode <- 'archived_dat'; rejects('unsupported_archived_dat',bad,'CSV or DTA only')
  bad <- cs; bad$filter <- list(a=1); rejects('filter_not_supported',bad,'fields')
  malformed <- file.path(fixtures,'nonnumeric.csv'); writeLines(c('csv_a,csv_b,csv_c','word,2,3'),malformed)
  bad <- cs; bad$data <- malformed; bad$data_expected_sha256 <- sha(malformed); rejects('nonnumeric_output',bad,'Non-numeric')
  duplicate <- file.path(fixtures,'duplicate.csv'); writeLines(c('csv_a,csv_a,csv_c','1,2,3'),duplicate)
  bad <- cs; bad$data <- duplicate; bad$data_expected_sha256 <- sha(duplicate); rejects('duplicate_source_names',bad,'unique nonempty')
  for (kind in c('long','short','blank')) {
    path <- file.path(fixtures,paste0('bad_width_',kind,'.csv'))
    body <- switch(kind,long=c('1,2,3,4','2,3,4,5'),short=c('1,2,3','4,5'),blank=c('1,2,3','','4,5,6'))
    writeLines(c('csv_a,csv_b,csv_c',body),path)
    bad <- cs; bad$data <- path; bad$data_expected_sha256 <- sha(path)
    rejects(paste0('csv_',kind,'_record'),bad,'CSV records must match')
  }
  quoted <- file.path(fixtures,'quoted.csv')
  writeLines(c('csv_a,csv_b,csv_c,note','1,2,3,"comma,quoted"','4,5,6,"multi','line"'),quoted)
  quoted_spec <- cs; quoted_spec$data <- quoted; quoted_spec$data_expected_sha256 <- sha(quoted)
  quoted_receipt <- prepare_mplus_source(quoted_spec,file.path(outputs,'quoted'))
  check('quoted_commas_and_multiline_unselected_text',quoted_receipt$rows==2L)
  dated <- dta_data; dated$dta_a <- as.Date('2000-01-01')+1:4
  date_path <- file.path(fixtures,'date.dta'); haven::write_dta(dated,date_path)
  bad <- ds; bad$data <- date_path; bad$data_expected_sha256 <- sha(date_path); rejects('date_requires_upstream_processing',bad,'date/time preprocessing')
  prior <- vapply(list.files(csv_out,full.names=TRUE),sha,'')
  error <- tryCatch({prepare_mplus_source(cs,csv_out); NULL},error=identity)
  check('existing_output_rejected_unchanged',inherits(error,'error') && identical(prior,vapply(list.files(csv_out,full.names=TRUE),sha,'')))
  # 故障注入更改合成源正文，保留原期望SHA；验证失败不会“自动重算修好”请求。
  changed <- file.path(fixtures,'changed.csv'); file.copy(csv,changed)
  bad <- cs; bad$data <- changed; bad$data_expected_sha256 <- sha(changed)
  original_reader <- source_spec_runtime$apim_v2_read_source
  source_spec_runtime$apim_v2_read_source <- function(config,path) {
    result <- original_reader(config,path); cat('\n',file=path,append=TRUE); result
  }
  tryCatch(rejects('source_changed_while_reading',bad,'Source changed during reading'),
    finally={source_spec_runtime$apim_v2_read_source <- original_reader})
  # 空码向量是显式“无额外缺失码”，允许它而不把空声明偷换为默认值。
  tiny <- file.path(fixtures,'tiny.csv'); writeLines(c('x','0.10000000000000002','-7'),tiny)
  tiny_spec <- list(schema_version=1L,data=tiny,data_mode='csv',data_expected_sha256=sha(tiny),columns='x',
    missing_codes=list(x=character()),missing_value=-999)
  tiny_receipt <- prepare_mplus_source(tiny_spec,file.path(outputs,'one_column'))
  check('single_column_and_empty_codes_work',tiny_receipt$rows==2L && tiny_receipt$columns==1L)
  tiny_json <- jsonlite::read_json(file.path(outputs,'one_column','source_receipt.json'))
  check('single_column_receipt_keeps_ordered_array',is.list(tiny_json$column_names) && identical(tiny_json$column_names[[1]],'x'))
  # 单独的全有效夹具只改空声明的列名，不能靠其他缺失/类型错误冒充声明门通过。
  finite_csv <- file.path(fixtures,'finite.csv'); writeLines(c('x','1','2'),finite_csv)
  finite_dta <- file.path(fixtures,'finite.dta'); haven::write_dta(data.frame(x=c(1,2)),finite_dta)
  for (mode in c('csv','dta')) {
    bad <- tiny_spec; bad$data <- if (mode=='csv') finite_csv else finite_dta
    bad$data_mode <- mode; bad$data_expected_sha256 <- sha(bad$data)
    bad$missing_codes <- list(typo=character())
    rejects(paste0(mode,'_misnamed_empty_missing_declaration'),bad,
      'Declare missing_codes for every output column; use an empty vector for no extra codes',exact=TRUE)
  }
  # 字符缺失码的十进制等价写法必须重码，回执也要计入；全局与逐列重码互斥。
  variants <- file.path(fixtures,'decimal_missing.csv')
  writeLines(c('x','-9.0',' -9','-09','-9e0','-9','-7.0','NA','3'),variants)
  vs <- tiny_spec; vs$data <- variants; vs$data_expected_sha256 <- sha(variants)
  vs$missing <- c('-7','NA'); vs$missing_codes <- list(x='-9')
  vr <- prepare_mplus_source(vs,file.path(outputs,'decimal_missing'))
  actual <- read.table(file.path(outputs,'decimal_missing','data.dat'),na.strings='-999',colClasses='numeric')[[1]]
  check('character_missing_codes_accept_decimal_equivalents',identical(actual,c(rep(NA_real_,7),3)))
  check('decimal_missing_audit_matches_replacements',vr$missing_by_column$x==7L &&
    vr$missing_recode_counts$x$source_missing==0L && vr$missing_recode_counts$x$global_codes_replaced==2L &&
    vr$missing_recode_counts$x$column_codes_replaced==5L && vr$missing_recode_counts$x$missing_after==7L)
  vs$missing <- c('-7','NA','-9')
  vr <- prepare_mplus_source(vs,file.path(outputs,'global_precedence'))
  check('global_missing_precedes_column_missing_once',vr$missing_recode_counts$x$global_codes_replaced==7L &&
    vr$missing_recode_counts$x$column_codes_replaced==0L && vr$missing_by_column$x==7L)
  precision <- file.path(fixtures,'numeric_code_precision.dta')
  haven::write_dta(data.frame(x=c(.10000000000000002,.1,haven::tagged_na('b'),NA_real_)),precision)
  ps <- tiny_spec; ps$data <- precision; ps$data_mode <- 'dta'; ps$data_expected_sha256 <- sha(precision)
  for (kind in c('numeric','character')) {
    ps$missing_codes <- list(x=if (kind=='numeric') .1 else '0.1')
    target <- file.path(outputs,paste0('precision_',kind)); pr <- prepare_mplus_source(ps,target)
    actual <- read.table(file.path(target,'data.dat'),na.strings='-999',colClasses='numeric')[[1]]
    check(paste0(kind,'_missing_code_keeps_neighbor_double'),identical(actual,c(.10000000000000002,rep(NA_real_,3))))
    check(paste0(kind,'_native_tagged_and_recoded_missing_audit'),pr$missing_recode_counts$x$source_missing==2L &&
      pr$missing_recode_counts$x$tagged_missing==1L && pr$missing_recode_counts$x$column_codes_replaced==1L &&
      pr$missing_recode_counts$x$missing_after==3L)
  }
  ps$missing_codes <- list(x=.10000000000000002)
  prepare_mplus_source(ps,file.path(outputs,'precision_high_code'))
  check('numeric_missing_code_not_rounded_before_matching',identical(
    read.table(file.path(outputs,'precision_high_code','data.dat'),na.strings='-999',colClasses='numeric')[[1]],
    c(NA_real_,.1,NA_real_,NA_real_)))
  # 十六进制不能因数值缺失码26而在词法核验之前消失；只有显式文本码可精确替换。
  hex <- file.path(fixtures,'hex.csv'); writeLines(c('x','0x1A','26'),hex)
  hs <- tiny_spec; hs$data <- hex; hs$data_expected_sha256 <- sha(hex)
  for (kind in c('none','column','global')) {
    bad <- hs
    if (kind=='column') bad$missing_codes <- list(x=26)
    if (kind=='global') bad$missing <- 26
    rejects(paste0('hex_rejected_',kind),bad,'Non-numeric or nonfinite output value: x (decimal notation required)',exact=TRUE)
  }
  hs$missing_codes <- list(x='0x1A'); hr <- prepare_mplus_source(hs,file.path(outputs,'hex_explicit_text'))
  actual <- read.table(file.path(outputs,'hex_explicit_text','data.dat'),na.strings='-999',colClasses='numeric')[[1]]
  check('hex_text_code_does_not_recode_decimal_26',identical(actual,c(NA_real_,26)) && hr$missing_recode_counts$x$column_codes_replaced==1L)
  decimal_path <- file.path(fixtures,'decimal_values.csv'); writeLines(c('x',' +1.5e+1 ','-.25','2.','3E-1'),decimal_path)
  valid <- tiny_spec; valid$data <- decimal_path; valid$data_expected_sha256 <- sha(decimal_path)
  prepare_mplus_source(valid,file.path(outputs,'decimal_values'))
  check('signed_whitespace_scientific_decimals_accepted',identical(
    read.table(file.path(outputs,'decimal_values','data.dat'),colClasses='numeric')[[1]],c(15,-.25,2,.3)))
  # 用500个19/20字节数值构造记录边界，避免数千列回执占用过大。
  wide_names <- sprintf('v%03d',seq_len(500L)); wide_values <- rep(.1,500L); wide_values[1] <- -.1
  wide_tokens <- chartr(',','.',sprintf('%.17g',wide_values))
  check('record_limit_fixture_is_exactly_10000_bytes',nchar(paste(wide_tokens,collapse=' '),type='bytes')==10000L)
  wide_path <- file.path(fixtures,'record_10000.csv')
  writeLines(c(paste(wide_names,collapse=','),paste(wide_tokens,collapse=',')),wide_path)
  wide_spec <- list(schema_version=1L,data=wide_path,data_mode='csv',data_expected_sha256=sha(wide_path),
    columns=wide_names,missing_codes=setNames(rep(list(character()),500L),wide_names),missing_value=-999)
  wide_target <- file.path(outputs,'record_10000'); wr <- prepare_mplus_source(wide_spec,wide_target)
  wide_receipt <- jsonlite::read_json(file.path(wide_target,'source_receipt.json'))
  check('record_10000_accepted_and_receipted',wr$max_record_bytes==10000L && wr$record_length_limit_bytes==10000L &&
    wide_receipt$max_record_bytes==10000L && wide_receipt$record_length_limit_bytes==10000L &&
    max(nchar(readLines(file.path(wide_target,'data.dat')),type='bytes'))==10000L)
  wide_tokens[2] <- wide_tokens[1]
  check('record_limit_fixture_is_exactly_10001_bytes',nchar(paste(wide_tokens,collapse=' '),type='bytes')==10001L)
  wide_path <- file.path(fixtures,'record_10001.csv')
  writeLines(c(paste(wide_names,collapse=','),paste(wide_tokens,collapse=',')),wide_path)
  wide_spec$data <- wide_path; wide_spec$data_expected_sha256 <- sha(wide_path)
  rejects('record_10001_rejected_before_output',wide_spec,'DAT record exceeds Mplus 10000-byte limit',exact=TRUE)
  # 只复制实际加载的三份源码；篡改副本后不重载，精确核拒绝原因与零输出。
  code_names <- c('source_spec.R','apim_v2_config.R','apim_v2_data_adapter.R')
  originals <- file.path(skill_root,'scripts',code_names); original_hashes <- vapply(originals,sha,'')
  isolated <- file.path(out_dir,'code_copy'); dir.create(isolated)
  copies <- file.path(isolated,code_names); stopifnot(all(file.copy(originals,copies)))
  check('isolated_code_copy_matches_original',identical(unname(vapply(copies,sha,'')),unname(original_hashes)))
  isolated_env <- new.env(parent=globalenv()); source(copies[1],local=isolated_env)
  check('isolated_loader_binds_only_copies',identical(unname(isolated_env$source_spec_runtime$code_paths),normalizePath(copies,winslash='/')))
  isolated_env$prepare_mplus_source(tiny_spec,file.path(outputs,'isolated_valid'))
  cat('\n# 合成测试：加载之后改变副本字节。\n',file=copies[2],append=TRUE)
  check('isolated_adapter_changed_after_loading',!identical(sha(copies[2]),unname(original_hashes[2])))
  target <- file.path(outputs,'isolated_changed')
  error <- tryCatch({isolated_env$prepare_mplus_source(tiny_spec,target);NULL},error=identity)
  check('loaded_adapter_change_rejected',inherits(error,'error') && identical(conditionMessage(error),
    'Loaded source adapter code changed; reload explicitly'))
  check('loaded_adapter_change_writes_nothing',!file.exists(target))
  check('shared_adapter_files_unchanged',identical(vapply(originals,sha,''),original_hashes))
  report <- list(status='PASS_SOURCE_SPEC_SYNTHETIC_ONLY',checks=checks,mplus_calls=0L,real_data_read=FALSE,
    source_spec_sha256=sha(file.path(skill_root,'scripts/source_spec.R')),
    test_script_sha256=sha(file.path(skill_root,'scripts/test_apim_v2_data_adapter.R')))
  jsonlite::write_json(report,file.path(out_dir,'SOURCE_SPEC_TEST_RECEIPT.json'),auto_unbox=TRUE,pretty=TRUE)
  cat('SOURCE_SPEC_PASS',length(checks),'checks; Mplus calls: 0\n'); flush.console()
  invisible(report)
}
