# 在已核验配偶关系的 CHARLS 夫妻宽表上追加共享调节变量；不建配偶关系、不猜编码、不运行引擎。
charls_mod_assert <- function(ok,message) if(!isTRUE(ok))stop(message,call.=FALSE)
charls_mod_sha <- function(path) digest::digest(path,algo='sha256',file=TRUE)
charls_mod_hex <- function(x) is.character(x)&&length(x)==1&&!is.na(x)&&grepl('^[a-fA-F0-9]{64}$',x)

charls_apim_moderated_validate_contract <- function(contract) {
  w<-contract$moderator
  charls_mod_assert(identical(as.integer(contract$schema_version),1L)&&identical(as.integer(contract$wave),2011L),
    'Only the declared 2011 moderated source contract is implemented')
  charls_mod_assert(is.list(contract$couples)&&identical(contract$couples$receipt_status,'PASS_PREPARE_ONLY')&&
    is.character(contract$couples$required_columns)&&length(contract$couples$required_columns)>0,
    'Moderated swap consumes only a PASS_PREPARE_ONLY couple table')
  charls_mod_assert(is.list(w)&&identical(w$source,'harmonized')&&identical(w$scope,'shared')&&identical(w$level,'household'),
    'Only a household-level shared moderator from the harmonized file is implemented')
  for(n in c('id_column','column','output_column'))
    charls_mod_assert(is.character(w[[n]])&&length(w[[n]])==1&&nzchar(w[[n]]),paste('Missing moderator field:',n))
  charls_mod_assert(grepl('^[a-z][a-z0-9_]*$',w$output_column)&&!w$output_column%in%contract$couples$required_columns,
    'Moderator output column must be a new lower-case name')
  charls_mod_assert(is.numeric(w$valid_codes)&&length(w$valid_codes)==2&&!anyDuplicated(w$valid_codes)&&
    all(is.finite(w$valid_codes))&&length(w$reference)==1&&w$reference%in%w$valid_codes,
    'Binary moderator needs two distinct valid codes and a reference code')
  # labels 用 list（JSON 对象），具名数值向量写 JSON 时会丢掉名字。
  lab<-unlist(w$labels)
  charls_mod_assert(is.list(w$labels)&&is.numeric(lab)&&length(lab)==length(w$valid_codes)&&setequal(unname(lab),w$valid_codes)&&
    !is.null(names(lab))&&all(nzchar(names(lab)))&&!anyDuplicated(names(lab)),'Every valid moderator code needs one label')
  charls_mod_assert(is.numeric(w$missing_codes)&&!anyNA(w$missing_codes)&&all(is.finite(w$missing_codes))&&
    !length(intersect(w$missing_codes,w$valid_codes)),'Moderator missing codes must be finite and disjoint from valid codes')
  charls_mod_assert(identical(w$spouse_discordance_policy,'block')&&identical(w$one_sided_missing_policy,'block'),
    'A household-level moderator must agree within the couple; discordance and one-sided missingness block')
  # 编码方向与缺失码必须绑定真实文档；空缺失码列表本身不是核验证据。
  charls_mod_assert(isTRUE(w$codes_verified)&&charls_mod_hex(w$codes_documentation_sha256)&&
    is.character(w$codes_documentation_locator)&&length(w$codes_documentation_locator)==1&&nzchar(w$codes_documentation_locator),
    'BLOCKED_UNVERIFIED_MODERATOR_CODES: bind the moderator codebook before reading real data')
  invisible(TRUE)
}

# 只读一列调节变量和人员 ID；人员 ID 必须已是 charls_apim_swap 使用的 12 位字符形式。
charls_apim_moderated_read_moderator <- function(path,contract) {
  charls_apim_moderated_validate_contract(contract)
  for(p in c('haven','digest','tidyselect'))charls_mod_assert(requireNamespace(p,quietly=TRUE),paste('Missing package',p))
  charls_mod_assert(is.character(path)&&length(path)==1&&file.exists(path),'Missing declared moderator source')
  w<-contract$moderator;before<-charls_mod_sha(path)
  d<-as.data.frame(haven::read_dta(path,col_select=tidyselect::all_of(c(w$id_column,w$column)),.name_repair='minimal'),check.names=FALSE)
  id<-d[[w$id_column]]
  charls_mod_assert(is.character(id)&&!anyNA(id)&&all(grepl('^[0-9]{12}$',id)),
    'Moderator source IDs must be 12-digit character person IDs; numeric conversion needs a reviewed contract')
  charls_mod_assert(!anyDuplicated(id),'Duplicate person identity in moderator source')
  id<-as.character(id)  # 去掉 haven 的 format.stata 属性，值不变
  x<-d[[w$column]];tagged<-if(is.double(x))sum(haven::is_tagged_na(x)) else 0L
  if(inherits(x,'haven_labelled'))x<-haven::zap_labels(x)
  charls_mod_assert(is.numeric(x),'Moderator must be a numeric code')
  native<-sum(is.na(x));declared<-!is.na(x)&x%in%w$missing_codes;x[declared]<-NA_real_
  # 有效码与已声明缺失码以外的值不能静默改成缺失。
  charls_mod_assert(all(is.na(x)|x%in%w$valid_codes),'BLOCKED_UNREVIEWED_MODERATOR_CODE: value outside valid and declared missing codes')
  charls_mod_assert(identical(charls_mod_sha(path),before),'Moderator source changed during reading')
  out<-data.frame(pid=id,w=as.numeric(x),stringsAsFactors=FALSE)
  attr(out,'charls_moderator_evidence')<-list(source_sha256=before,rows=nrow(d),native_missing=native,
    tagged_missing=tagged,declared_codes_replaced=sum(declared),column=w$column)
  out
}

# #79 在回执旁存 source_contract.rds，回执的 contract_sha256 是它的 digest。
# 这里核绑定与三项核验结果；哈希只核格式与一致性，挡不住有意伪造，但能挡住拿未核实或合成合同产出的回执去跑。
charls_apim_moderated_check_couples_contract <- function(receipt,contract_path) {
  charls_mod_assert(charls_mod_hex(receipt$contract_sha256),'BLOCKED_UNBOUND_COUPLE_CONTRACT: receipt contract_sha256 must be a 64-hex digest')
  charls_mod_assert(is.character(contract_path)&&length(contract_path)==1&&file.exists(contract_path),
    'BLOCKED_UNBOUND_COUPLE_CONTRACT: source_contract.rds saved by charls_prepare_apim_swap() is missing')
  k<-readRDS(contract_path)
  charls_mod_assert(identical(digest::digest(k,algo='sha256'),receipt$contract_sha256),
    'BLOCKED_UNBOUND_COUPLE_CONTRACT: source_contract.rds digest differs from receipt contract_sha256')
  s<-k$spouse_link
  charls_mod_assert(is.list(s)&&isTRUE(s$verified)&&isTRUE(s$reciprocity_required)&&charls_mod_hex(s$documentation_sha256),
    'BLOCKED_UNVERIFIED_COUPLE_CONTRACT: reciprocal spouse link is not verified')
  charls_mod_assert(isTRUE(k$missing_codes_verified)&&charls_mod_hex(k$missing_codes_documentation_sha256),
    'BLOCKED_UNVERIFIED_COUPLE_CONTRACT: missing codes are not verified')
  charls_mod_assert(isTRUE(k$identity_codes_verified)&&charls_mod_hex(k$identity_documentation_sha256),
    'BLOCKED_UNVERIFIED_COUPLE_CONTRACT: identity codes are not verified')
  invisible(digest::digest(k,algo='sha256'))
}

# couples_data/couples_receipt 是 charls_prepare_apim_swap() 的输出；配偶互指、成员角色与社区一致在那一步已核过。
charls_apim_moderated_attach <- function(couples_data,couples_receipt,moderator,contract,output_dir,
                                         couples_contract=file.path(dirname(couples_receipt),'source_contract.rds')) {
  charls_apim_moderated_validate_contract(contract)
  for(p in c('haven','digest','jsonlite'))charls_mod_assert(requireNamespace(p,quietly=TRUE),paste('Missing package',p))
  charls_mod_assert(file.exists(couples_data)&&file.exists(couples_receipt),'Missing couple table or its receipt')
  data_sha<-charls_mod_sha(couples_data);receipt_sha<-charls_mod_sha(couples_receipt)
  r<-jsonlite::read_json(couples_receipt,simplifyVector=TRUE)
  charls_mod_assert(identical(r$status,contract$couples$receipt_status)&&identical(as.integer(r$wave),as.integer(contract$wave))&&
    identical(r$cluster,'community')&&identical(r$data_sha256,data_sha),
    'Couple table must match a PASS_PREPARE_ONLY receipt for the same wave, community clustering and data hash')
  contract79_sha<-charls_apim_moderated_check_couples_contract(r,couples_contract)
  wide<-as.data.frame(haven::read_dta(couples_data,.name_repair='minimal'),check.names=FALSE)
  need<-contract$couples$required_columns;w<-contract$moderator
  charls_mod_assert(all(need%in%names(wide))&&!w$output_column%in%names(wide),'Couple table columns differ from the declared contract')
  charls_mod_assert(nrow(wide)>0&&identical(as.integer(r$couples),nrow(wide))&&!anyDuplicated(wide$couple_wave_id),
    'Couple count differs from receipt or couple records repeat')
  charls_mod_assert(!anyNA(wide$member1_id)&&!anyNA(wide$member2_id)&&all(as.character(wide$member1_id)!=as.character(wide$member2_id)),
    'BLOCKED_SELF_PAIRED_COUPLE: member1_id equals member2_id')
  charls_mod_assert(is.data.frame(moderator)&&identical(names(moderator)[1:2],c('pid','w'))&&!anyDuplicated(moderator$pid),
    'Moderator table must come from charls_apim_moderated_read_moderator()')
  i1<-match(as.character(wide$member1_id),moderator$pid);i2<-match(as.character(wide$member2_id),moderator$pid)
  # 两人都必须在同一版调节来源里；缺人说明来源版本不一致，不当作缺失值处理。
  charls_mod_assert(!anyNA(i1)&&!anyNA(i2),'Couple member absent from moderator source; bind the same harmonized release')
  w1<-moderator$w[i1];w2<-moderator$w[i2]
  charls_mod_assert(!any(xor(is.na(w1),is.na(w2))),'BLOCKED_ONE_SIDED_MODERATOR_MISSING: household-level moderator observed for one spouse only')
  charls_mod_assert(all(is.na(w1)|w1==w2),'BLOCKED_DISCORDANT_SHARED_MODERATOR: spouses differ on a household-level moderator')
  wide[[w$output_column]]<-w1
  base<-c('member1_age','member2_age','member1_cesd10','member2_cesd10',w$output_column)
  cc_mod<-complete.cases(wide[base]);cc_medmod<-cc_mod&complete.cases(wide[c('member1_adl','member2_adl')])
  for(rows in list(cc_mod,cc_medmod)) {
    charls_mod_assert(sum(rows)>0&&length(unique(wide$community_id[rows]))>1,'Insufficient complete couples or communities')
    charls_mod_assert(all(w$valid_codes%in%wide[[w$output_column]][rows]),'Degenerate moderator in complete cases; do not fit')
  }
  # 每个方程的预测矩阵（含 W 主效应与乘积项）必须满秩；只核 Y 方程与 M 方程两种最大集合。
  wv<-wide[[w$output_column]];x<-as.matrix(wide[c('member1_age','member2_age')]);m<-as.matrix(wide[c('member1_adl','member2_adl')])
  full<-function(cols,rows){mx<-cbind(1,cols)[rows,,drop=FALSE];list(columns=ncol(mx),rank=qr(mx)$rank)}
  ranks<-list(apimom_y=full(cbind(x,wv,x*wv),cc_mod),apimemom_m=full(cbind(x,wv,x*wv),cc_medmod),
    apimemom_y=full(cbind(x,m,wv,m*wv),cc_medmod))
  charls_mod_assert(all(vapply(ranks,function(z)z$rank==z$columns,logical(1))),'Rank-deficient moderated predictor matrix; do not fit')
  charls_mod_assert(!dir.exists(output_dir),'Moderated preparation directory already exists; preserve original attempt')
  dir.create(output_dir,recursive=TRUE);data_path<-file.path(output_dir,'charls_couples_2011_moderated_v1.dta')
  haven::write_dta(wide,data_path)
  # 回执只记计数与哈希；取值分布留在本机证据。
  receipt<-list(status='PASS_MODERATED_PREPARE_ONLY',wave=contract$wave,couples=nrow(wide),
    complete_apimom=sum(cc_mod),complete_apimemom=sum(cc_medmod),moderator_missing_couples=sum(is.na(w1)),
    one_sided_missing=0L,discordant=0L,moderator=list(column=w$column,output_column=w$output_column,
      scope=w$scope,level=w$level,valid_codes=w$valid_codes,reference=w$reference,coding_basis=w$coding_basis),
    predictor_rank_checks=ranks,moderator_evidence=attr(moderator,'charls_moderator_evidence'),
    couples_data_sha256=data_sha,couples_receipt_sha256=receipt_sha,couples_contract_sha256=contract79_sha,
    couples_contract_file_sha256=charls_mod_sha(couples_contract),
    moderated_contract_sha256=digest::digest(contract,algo='sha256'),data_sha256=charls_mod_sha(data_path),
    scientific_boundary=contract$scientific_boundary,new_mplus_calls=0L)
  jsonlite::write_json(receipt,file.path(output_dir,'moderated_preparation_receipt.json'),auto_unbox=TRUE,pretty=TRUE,null='null')
  charls_mod_assert(identical(charls_mod_sha(couples_data),data_sha),'Couple table changed during preparation')
  invisible(list(data_path=normalizePath(data_path,winslash='/',mustWork=TRUE),receipt=receipt))
}

# JSON 读回后把数值字段恢复成向量：[] 会读成 list()，具名对象会读成 list。
charls_apim_moderated_contract_from_json <- function(x) {
  charls_mod_assert(is.list(x)&&is.list(x$moderator),'Moderated contract must be a JSON object')
  w<-x$moderator
  for(n in c('valid_codes','missing_codes','reference'))w[[n]]<-as.numeric(unlist(w[[n]]))
  charls_mod_assert(is.list(w$labels)&&!is.null(names(w$labels)),'Moderator labels must be a JSON object')
  w$labels<-lapply(w$labels,function(z)as.numeric(unlist(z)))
  x$moderator<-w;x$couples$required_columns<-as.character(unlist(x$couples$required_columns))
  x
}

# 路径比较：统一斜杠、去尾斜杠；Windows 不分大小写
charls_mod_norm <- function(p) {
  q<-sub('/+$','',gsub('\\','/',normalizePath(p,winslash='/',mustWork=FALSE),fixed=TRUE))
  if(.Platform$OS.type=='windows')tolower(q) else q
}

# 拟合准入（PROGRAM 第 4 条的 grant 格式，字段沿用 #79 validate_grant()）：解析 grant 内容逐项核对，
# 不只比文件名和 SHA。任何一项不符都报 FIT_GRANT_NOT_ADMITTED；通过时返回 grant 里的 hard_cap 供配置使用。
charls_apim_moderated_admit_grant <- function(grant,window_request,root,request_name,n_models) {
  why<-function(reason)stop(paste0('FIT_GRANT_NOT_ADMITTED: ',reason),call.=FALSE)
  ok<-function(cond,reason)if(!isTRUE(cond))why(reason)
  for(x in list(grant,window_request))
    ok(is.list(x)&&is.character(x$path)&&length(x$path)==1&&file.exists(x$path)&&charls_mod_hex(x$sha256)&&
      identical(charls_mod_sha(x$path),x$sha256),'grant or window request file missing or hash mismatch')
  ok(identical(basename(grant$path),paste0(request_name,'.json'))&&identical(basename(dirname(grant$path)),'grants'),
    'grant must be grants/<request_name>.json')
  ok(identical(basename(window_request$path),paste0(request_name,'.json'))&&identical(basename(dirname(window_request$path)),'requests'),
    'window request must be requests/<request_name>.json')
  run_root<-charls_mod_norm(root)
  ok(!startsWith(paste0(charls_mod_norm(grant$path),'/'),paste0(run_root,'/')),'grant file must not be inside the run root')
  read<-function(p)tryCatch(jsonlite::read_json(p,simplifyVector=TRUE),error=function(e)NULL)
  g<-read(grant$path);q<-read(window_request$path)
  ok(is.list(g)&&length(g)>0,'grant is not a JSON object');ok(is.list(q)&&length(q)>0,'window request is not a JSON object')
  str1<-function(x)is.character(x)&&length(x)==1&&!is.na(x)&&nzchar(x)
  ok(isTRUE(g$approved),'grant approved is not true')
  ok(identical(g$request_name,request_name),'grant request_name differs')
  ok(identical(g$request_sha256,window_request$sha256),'grant request_sha256 differs from the window request file')
  for(f in c('worker','request_id','purpose'))ok(str1(g[[f]])&&str1(q[[f]])&&identical(g[[f]],q[[f]]),paste('grant',f,'differs from the window request'))
  ok(is.numeric(g$models)&&length(g$models)==1&&is.numeric(q$models)&&identical(as.integer(g$models),as.integer(q$models))&&
    identical(as.integer(g$models),as.integer(n_models)),'grant models differs from the request or the planned model count')
  ok(str1(g$root)&&identical(charls_mod_norm(g$root),run_root),'grant root differs from this run root')
  for(f in c('granted_by','granted_taipei'))ok(str1(g[[f]]),paste('grant',f,'missing'))
  # hard_cap 照抄或收紧请求；引擎启动数要容得下全部模型
  caps<-c('max_engine_starts','max_wall_seconds','processors_per_model')
  int1<-function(x)is.numeric(x)&&length(x)==1&&is.finite(x)&&x>=1&&x==round(x)
  ok(is.list(g$hard_cap)&&all(vapply(caps,function(f)int1(g$hard_cap[[f]]),logical(1))),'grant hard_cap incomplete')
  ok(is.list(q$hard_cap)&&all(vapply(caps,function(f)int1(q$hard_cap[[f]])&&g$hard_cap[[f]]<=q$hard_cap[[f]],logical(1))),
    'grant hard_cap is looser than the request')
  ok(g$hard_cap$max_engine_starts>=n_models,'grant max_engine_starts below the planned model count')
  list(hard_cap=lapply(g$hard_cap[caps],as.integer),granted_by=g$granted_by,granted_taipei=g$granted_taipei,
    grant_sha256=grant$sha256,window_request_sha256=window_request$sha256)
}
