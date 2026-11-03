# 运行于独立合成目录；不调用Mplus。测试可观察行为而非实现字符串。
test_apim_v2 <- function(skill_root,test_root,engine,python) {
  source(file.path(skill_root,'scripts','workflow.R'),local=TRUE)
  source(file.path(skill_root,'assets','example_config_v2.R'),local=TRUE)
  stopifnot(!dir.exists(test_root));dir.create(test_root,recursive=TRUE)
  fixture<-file.path(test_root,'fixtures');dir.create(fixture)
  data<-file.path(fixture,'data.csv');write_apim_v2_example_data(data)
  cfg<-example_apim_config_v2(data,file.path(test_root,'runs','base'),engine,python)
  checks<-list();check<-function(name,value){stopifnot(isTRUE(value));checks[[name]]<<-TRUE}
  fails<-function(expression)inherits(tryCatch({force(expression);NULL},error=identity),'error')
  plan<-plan_apim_workflow(cfg)
  check('ten_scenarios',plan$candidate_count==10L&&plan$execution_count==10L)
  check('planning_no_output',!dir.exists(cfg$output_dir))
  bad<-cfg;bad$output_dir<-fixture;check('source_overlap_rejected',fails(plan_apim_workflow(bad)))
  bad<-cfg;bad$missing_policy<-'fiml';check('unsupported_fiml_rejected',fails(plan_apim_workflow(bad)))
  bad<-cfg;bad$designs$apimom_binary$w$context$columns<-c('wb','wb');check('duplicate_shared_columns_rejected',fails(plan_apim_workflow(bad)))
  bad<-cfg;bad$designs$apimemom_cont$contrasts<-list(bad=c('high','absent'));check('unknown_contrast_rejected',fails(plan_apim_workflow(bad)))
  bad<-cfg;bad$unexpected_option<-TRUE;check('unknown_field_rejected',fails(plan_apim_workflow(bad)))
  original<-apim_sha(data,TRUE)
  run<-run_apim_workflow(cfg,stages=c('check','prepare','compile'))
  check('source_unchanged',identical(apim_sha(data,TRUE),original))
  check('all_inputs_compiled',all(vapply(run$compiled,function(c)file.exists(c$input),logical(1))))
  check('no_estimation',!any(vapply(run$compiled,function(c)file.exists(c$output),logical(1))))
  pair<-Filter(function(m)m$family=='APIM',run$plan$models)
  free<-run$compiled[[pair[[1]]$id]]$paths;eq<-run$compiled[[pair[[2]]$id]]$paths
  check('constraint_many_paths_one_parameter',length(unique(free$label))==4&&length(unique(eq$label))==2&&nrow(eq)==4)
  category<-Filter(function(m)m$family=='APIMoM'&&identical(m$w$type,'categorical'),run$plan$models)[[1]]
  prep<-readRDS(file.path(run$compiled[[category$id]]$folder,'prepared.rds'))
  check('shared_category_k_minus_one',length(prep$w_alias)==2L&&length(prep$products)==4L)
  check('category_reference_all_zero',all(prep$probes$low==0)&&sum(prep$probes$high)==1)
  check('unchanged_compile_resume',!fails(run_apim_workflow(cfg,stages=c('prepare','compile'))))
  # 多维真实展开：2个样本×2个约束步骤，原生createModels负责产生4个输入。
  cfg2<-cfg;cfg2$output_dir<-file.path(test_root,'runs','multidimensional');cfg2$designs<-cfg2$designs['apim'];cfg2$designs$apim$samples<-c('all','late')
  run2<-run_apim_workflow(cfg2,stages=c('check','prepare','compile'))
  check('multidimensional_native_expansion',length(run2$compiled)==4L)
  counts<-vapply(run2$compiled,function(c)readRDS(file.path(c$folder,'prepared.rds'))$N,integer(1))
  check('sample_specific_N',setequal(unique(counts),c(400L,200L)))
  # a 路径/a+b 路径调节中介：乘积项进 m 方程，W 主效应只进含乘积项的方程；默认 b 与显式 b 编译结果相同。
  bad<-cfg;bad$designs$apimom_cont$moderated_paths<-'a';check('moderated_paths_outside_apimemom_rejected',fails(plan_apim_workflow(bad)))
  bad<-cfg;bad$designs$apimemom_cont$moderated_paths<-'c';check('moderated_paths_unknown_rejected',fails(plan_apim_workflow(bad)))
  cfg3<-cfg;cfg3$output_dir<-file.path(test_root,'runs','apath');base<-cfg$designs$apimemom_cont
  cfg3$designs<-list(b_default=base,b_explicit=modifyList(base,list(moderated_paths='b')),
    a_cont=modifyList(base,list(moderated_paths='a')),ab_cat=modifyList(cfg$designs$apimemom_category,list(moderated_paths='ab')))
  run3<-run_apim_workflow(cfg3,stages=c('check','prepare','compile'))
  ids3<-names(run3$compiled);byd<-function(d)run3$compiled[[ids3[startsWith(ids3,paste0(d,'_'))]]]
  inp<-function(d)toupper(readLines(byd(d)$input,warn=FALSE))
  has<-function(x,pattern)any(grepl(pattern,x))
  check('apath_default_b_identical',identical(inp('b_default')[-1],inp('b_explicit')[-1]))
  a<-inp('a_cont');ab<-inp('ab_cat')
  check('apath_products_in_mediator_equation',has(a,'^\\s*M1 ON P[0-9]{3} \\(U1')&&has(a,'^\\s*M2 ON W1;')&&
    !has(a,'^\\s*Y1 ON W')&&!has(a,'\\(Z[0-9]'))
  check('abpath_products_in_both_equations',has(ab,'^\\s*M1 ON P[0-9]{3} \\(U1')&&has(ab,'^\\s*Y2 ON P[0-9]{3} \\(Z2')&&
    has(ab,'^\\s*M1 ON W1D1;')&&has(ab,'^\\s*Y1 ON W1D2;'))
  ea<-byd('a_cont')$effects;eab<-byd('ab_cat')$effects
  check('apath_effect_kinds',all(c('conditional_a','conditional_indirect','conditional_total','conditional_contrast')%in%ea$kind)&&!'simple_slope'%in%ea$kind)
  check('abpath_effect_kinds',all(c('conditional_a','simple_slope','conditional_indirect','conditional_total')%in%eab$kind))
  # 公式恒等：给路径标签赋确定值，按 MODEL CONSTRAINT 顺序求值，与手算 (a+Σu·W)(b+Σz·W) 比较。
  formula_ok<-function(d,stage) {
    c3<-byd(d);prep<-readRDS(file.path(c3$folder,'prepared.rds'));env<-new.env()
    labs<-unique(c3$paths$label);for(i in seq_along(labs))assign(labs[i],sin(i)+.5,env)
    for(i in seq_len(nrow(c3$effects)))assign(tolower(c3$effects$label[i]),eval(parse(text=c3$effects$expression[i]),env),env)
    g<-function(n)get(n,env);ok<-TRUE
    for(pr in names(prep$probes))for(j in 1:2)for(k in 1:2)for(v in 1:2) {
      w<-prep$probes[[pr]];h<-seq_along(w)
      ca<-g(paste0('a',v,k))+if(grepl('a',stage))sum(vapply(h,function(i)g(paste0('u',v,k,i)),0)*w) else 0
      cb<-g(paste0('b',j,v))+if(grepl('b',stage))sum(vapply(h,function(i)g(paste0('z',j,v,i)),0)*w) else 0
      row<-c3$effects[c3$effects$effect_id==paste0('conditional_x',k,'_m',v,'_y',j,'_',pr),]
      ok<-ok&&nrow(row)==1&&abs(g(tolower(row$label))-ca*cb)<1e-12
    }
    ok
  }
  check('apath_formula_identity',formula_ok('a_cont','a')&&formula_ok('ab_cat','ab')&&formula_ok('b_default','b'))
  # 归档 DAT 只允许逐字节快照与显式列声明；适配器另存原始字节并留下回执。
  archived<-file.path(fixture,'data_archived.dat')
  raw_archived<-read.csv(data,check.names=FALSE,stringsAsFactors=FALSE)
  write.table(raw_archived,archived,row.names=FALSE,col.names=FALSE,quote=FALSE,sep=' ')
  cfg_arch<-example_apim_config_v2(archived,file.path(test_root,'runs','archived'),engine,python)
  cfg_arch$data_mode<-'archived_dat';cfg_arch$data_columns<-names(raw_archived)
  cfg_arch$data_expected_sha256<-apim_sha(archived,TRUE);cfg_arch$transform<-list(scheme='none',reference='analysis_rows',overrides=list())
  arch_run<-run_apim_workflow(cfg_arch,stages=c('check','prepare','compile'))
  arch_folder<-arch_run$compiled[[1]]$folder
  check('archived_source_bytes_preserved',file.exists(file.path(arch_folder,'source_data_exact.dat'))&&
    identical(apim_sha(file.path(arch_folder,'source_data_exact.dat'),TRUE),cfg_arch$data_expected_sha256)&&
    file.exists(file.path(arch_folder,'archived_dat_receipt.json')))
  # DAT篡改不得被存在性缓存接受。
  target<-file.path(run2$compiled[[1]]$folder,'data.dat')
  cat('\n',file=target,append=TRUE)
  check('tampered_preparation_rejected',fails(run_apim_workflow(cfg2,stages='compile')))
  receipt<-list(status='PASS_COMPILE_ONLY',checks=checks,new_mplus_calls=0L,
    input_sha256=original,code=apim_v2_code_hash(c('workflow.R','results.R','apim_v2_config.R','apim_v2_models.R','apim_v2_runtime.R')))
  apim_json(receipt,file.path(test_root,'TEST_RECEIPT.json'))
  print(receipt[c('status','checks','new_mplus_calls')]);invisible(receipt)
}
