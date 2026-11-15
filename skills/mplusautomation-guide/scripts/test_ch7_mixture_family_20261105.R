# 第七章合成编译合同：只生成INP/DAT，不读取研究文件或调用Mplus。
# 独立运行：Rscript test_ch7_mixture_family_20261105.R <新的证据目录>
# 语法由 scripts/ch7_mixture_syntax.R 生成；本文件独立解析写出的 INP/DAT 作验收依据。
test_ch7_mixture_family <- function(output_dir, skill_root) {
  source(file.path(normalizePath(skill_root, winslash = '/'), 'scripts/ch7_mixture_syntax.R'), local = TRUE)
  for (pkg in c('MplusAutomation', 'digest', 'jsonlite')) {
    if (!requireNamespace(pkg, quietly = TRUE)) stop('Missing package: ', pkg)
  }
  if (file.exists(output_dir)) stop('Fresh output directory required')
  dir.create(output_dir, recursive = TRUE)
  output_dir <- normalizePath(output_dir, winslash = '/')
  checks <- list()
  check <- function(name, ok) {
    if (!isTRUE(ok)) stop('Contract failed: ', name)
    checks[[name]] <<- TRUE
  }
  sha <- function(path) digest::digest(path, algo = 'sha256', file = TRUE)
  reject <- function(name, expr) {
    check(name, inherits(tryCatch(force(expr), error = identity), 'error'))
  }
  # 即使后续误改run参数，也在调用外部引擎之前失败；不允许自动找引擎。
  ns <- asNamespace('MplusAutomation')
  for (fun in c('runModels', 'detectMplus')) {
    trace(fun, tracer = quote(stop('ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI')),
          print = FALSE, where = ns)
  }
  on.exit(for (fun in c('runModels', 'detectMplus')) untrace(fun, where = ns), add = TRUE)
  # 断言拦截信息本身：没装 Mplus 时 runModels 本来就会报错，只查"有报错"不能证明拦截生效。
  guard <- function(expr) tryCatch({ force(expr); '' }, error = conditionMessage)
  check('engine_guard_blocks_runModels',
        identical(guard(MplusAutomation::runModels()), 'ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI'))
  check('engine_guard_blocks_detectMplus',
        identical(guard(MplusAutomation::detectMplus()), 'ENGINE_CALL_FORBIDDEN_SYNTHETIC_CI'))

  # 所有数值仅为固定种子的合成设计，不从论文结果或个人记录取得。
  set.seed(7105L)
  roles <- unlist(lapply(1:4, function(t) paste0('t', t, c('x1','x2','x3','x4','b1','b2'))))
  nominal_roles <- paste0('n', 1:4)
  all_roles <- c(roles, nominal_roles)
  synthetic <- as.data.frame(setNames(lapply(all_roles, function(role) {
    if (grepl('^n', role)) sample.int(3L, 320L, replace = TRUE)
    else if (grepl('b', role)) rbinom(320L, 1L, .45)
    else rnorm(320L)
  }), all_roles))
  original <- setNames(all_roles, all_roles)
  renamed <- setNames(sprintf('v%02d', seq_along(all_roles)), all_roles)
  changed_source <- synthetic[, rev(all_roles)]
  names(changed_source) <- unname(renamed[names(changed_source)])
  check('four_waves_four_continuous_two_binary', length(roles) == 24L && nrow(synthetic) == 320L)
  check('binary_support', all(vapply(synthetic[grep('b', names(synthetic))], function(x) setequal(unique(x), 0:1), logical(1))))

  # 误分类矩阵是另行声明的合成输入，不是Step-1估计，也不授予端到端血缘。
  error_probability <- rbind(c(.82,.11,.07), c(.13,.78,.09), c(.08,.17,.75))
  check('synthetic_error_matrix_rows', all(abs(rowSums(error_probability) - 1) < 1e-12))
  specs <- c(unlist(lapply(1:4, function(t) paste0('lpa_t', t, '_k', 1:3))),
             'lta_invariant', 'lta_free', 'mslta_invariant', 'lta_step3', 'mslta_step3')

  # 生成器在 scripts/ch7_mixture_syntax.R（ch7_mixture_object）；这里只把角色映射成显式规格。
  build <- function(id, data, mapping) {
    getv <- function(role) unname(mapping[role])
    step3 <- grepl('step3$', id)
    family <- if (grepl('^lpa_', id)) 'lpa' else if (grepl('^mslta', id)) 'mslta' else 'lta'
    keep <- getv(if (step3) nominal_roles else roles)
    title <- paste0('Synthetic compile ', id, ';')
    if (step3) return(ch7_mixture_object(data, family, classes = 3L, keep = keep, title = title,
      step3 = list(nominal = getv(nominal_roles), error = error_probability)))
    waves <- if (family == 'lpa') list(getv(paste0('t', sub('lpa_t([1-4])_.*', '\\1', id), c('x1','x2','x3','x4','b1','b2'))))
             else lapply(1:4, function(t) getv(paste0('t', t, c('x1','x2','x3','x4','b1','b2'))))
    classes <- if (family == 'lpa') as.integer(sub('.*_k', '', id)) else 3L
    ch7_mixture_object(data, family, waves = waves, categorical = intersect(getv(roles[grepl('b', roles)]), unlist(waves)),
      classes = classes, invariant = id != 'lta_free', center = getv(roles[grepl('x', roles)]),
      keep = keep, title = title)
  }

  normalize <- function(x) tolower(gsub('\\s+', ' ', trimws(x)))
  statement <- function(text, key) {
    rx <- paste0('(?i)\\b',key,'\\s*=\\s*([^;]+);')
    hit <- regmatches(text, gregexpr(rx,text,perl=TRUE))[[1]]
    if (length(hit)!=1L) stop('Missing or duplicated statement: ',key)
    trimws(sub(rx,'\\1',hit,perl=TRUE))
  }
  words <- function(x) strsplit(tolower(trimws(x)), '\\s+')[[1]]
  segment <- function(text, start, end=NULL) {
    pos <- regexpr(start,text,fixed=TRUE)[1]
    if (pos<0) stop('Missing block: ',start)
    tail <- substring(text,pos+nchar(start))
    if (!is.null(end)) {
      finish <- regexpr(end,tail,fixed=TRUE)[1]
      if (finish<0) stop('Missing block end: ',end)
      tail <- substr(tail,1,finish-1)
    }
    tail
  }
  canonical <- function(text, mapping) {
    # 将变量名还原到角色名；NAMES单独核列序，其余语句必须完全相同。
    for (role in names(mapping)[order(nchar(mapping),decreasing=TRUE)]) {
      text <- gsub(paste0('\\b',mapping[[role]],'\\b'),role,text,perl=TRUE)
    }
    normalize(gsub('(?i)\\bNAMES\\s*=\\s*[^;]+;', '', text, perl=TRUE))
  }

  # 验收独立解析实际写出的INP及DAT，不使用生成器返回对象作正确性依据。
  validate <- function(text, dat, id, data, mapping) {
    text <- tolower(text)
    stopifnot(all(nchar(strsplit(text,'\n',fixed=TRUE)[[1]],type='bytes')<=90L))
    stopifnot(statement(segment(text,'data:','variable:'),'file')=='"source.dat"')
    nm <- words(statement(text,'names'))
    stopifnot(identical(nm,tolower(names(data))), ncol(dat)==length(nm), nrow(dat)==320L,
              isTRUE(all.equal(as.matrix(dat),unname(as.matrix(data)),check.attributes=FALSE,tolerance=1e-12)))
    stopifnot(!grepl('knownclass',text,fixed=TRUE), !grepl('[[',text,fixed=TRUE),
              normalize(statement(text,'type'))=='mixture', normalize(statement(text,'estimator'))=='mlr',
              statement(text,'processors')=='1', normalize(statement(text,'save'))=='cprobabilities')
    save_block <- segment(text,'savedata:')
    stopifnot(statement(save_block,'file')=='posterior.dat')
    step3 <- grepl('step3$',id)
    ms <- grepl('^mslta',id)
    lpa <- grepl('^lpa_',id)
    headers <- regmatches(text,gregexpr('(?m)^model [a-z][a-z0-9]*:',text,perl=TRUE))[[1]]
    if(lpa) stopifnot(length(headers)==0L)
    else stopifnot(identical(headers,c(if(ms)'model g:',paste0('model c',1:4,':'))))
    if (lpa) {
      t <- as.integer(sub('lpa_t([1-4])_.*','\\1',id)); k <- as.integer(sub('.*_k','',id))
      stopifnot(statement(text,'classes')==paste0('c(',k,')'))
      expected_use <- unname(mapping[paste0('t',t,c('x1','x2','x3','x4','b1','b2'))])
      expected_cat <- unname(mapping[paste0('t',t,c('b1','b2'))])
      blocks <- regmatches(text,gregexpr('%c#[0-9]+%',text))[[1]]
      stopifnot(identical(blocks,paste0('%c#',seq_len(k),'%')))
      for(j in seq_len(k)) {
        part<-segment(text,paste0('%c#',j,'%'),if(j<k)paste0('%c#',j+1,'%')else'output:')
        terms<-regmatches(part,gregexpr('\\[[^]]+\\];',part))[[1]]
        expected<-c(paste0('[',paste(unname(mapping[paste0('t',t,'x',1:4)]),collapse=' '),'];'),
                    paste0('[',paste0(unname(mapping[paste0('t',t,'b',1:2)]),'$1',collapse=' '),'];'))
        stopifnot(identical(terms,tolower(expected)))
      }
    } else {
      stopifnot(normalize(statement(text,'classes'))==paste(c(if(ms)'g(2)',paste0('c',1:4,'(3)')),collapse=' '))
      expected_use <- unname(mapping[if(step3)nominal_roles else roles])
      expected_cat <- unname(mapping[roles[grepl('b',roles)]])
      overall <- segment(text,'%overall%','model ')
      edges <- regmatches(overall,gregexpr('c[1-4] on c[1-4];',overall))[[1]]
      stopifnot(identical(edges,c('c2 on c1;','c3 on c2;','c4 on c3;')))
      for(t in 1:4) for(j in 1:3) {
        namespace <- segment(text,paste0('model c',t,':'),if(t<4)paste0('model c',t+1,':')else'output:')
        blocks<-regmatches(namespace,gregexpr('%c[1-4]#[0-9]+%',namespace))[[1]]
        stopifnot(identical(blocks,paste0('%c',t,'#',1:3,'%')))
        block <- segment(namespace,paste0('%c',t,'#',j,'%'),if(j<3)paste0('%c',t,'#',j+1,'%')else NULL)
        if(step3) {
          # 从打印的固定logit反算概率，核方向为P(赋类|真类)，而非其逆。
          n <- unname(mapping[paste0('n',t)])
          terms<-regmatches(block,gregexpr('\\[[^]]+\\];',block))[[1]]
          stopifnot(length(terms)==2L)
          vals <- vapply(1:2,function(a) {
            rx <- paste0('\\[',n,'#',a,'@(-?[0-9.]+)\\];')
            hit <- regmatches(block,regexpr(rx,block,perl=TRUE))
            if(!length(hit)||!nzchar(hit))stop('Missing fixed nominal logit')
            as.numeric(sub(rx,'\\1',hit,perl=TRUE))
          },numeric(1))
          p <- exp(c(vals,0));p<-p/sum(p)
          stopifnot(max(abs(p-error_probability[j,]))<1e-11)
        } else for(a in 1:6) {
          variable <- unname(mapping[paste0('t',t,if(a<=4)paste0('x',a)else paste0('b',a-4))])
          rx <- paste0('\\[',variable,if(a>4)'\\$1','\\] \\(([^)]+)\\);')
          hit <- regmatches(block,regexpr(rx,block,perl=TRUE))
          if(!length(hit)||!nzchar(hit))stop('Missing measurement parameter')
          actual_label <- sub(rx,'\\1',hit,perl=TRUE)
          expected_label <- paste0(if(id=='lta_free')paste0('w',t)else'm','k',j,'i',a)
          stopifnot(actual_label==expected_label)
        }
      }
    }
    stopifnot(identical(words(statement(text,'usevariables')),tolower(expected_use)),
              normalize(statement(text,'starts'))==if(step3)'0'else'20 5')
    if(step3) stopifnot(identical(words(statement(text,'nominal')),tolower(expected_use)), !grepl('categorical',text))
    else {
      stopifnot(identical(words(statement(text,'categorical')),tolower(expected_cat)))
      flat <- normalize(text)
      center <- regmatches(flat,regexpr('center ([^;]+) \\(grandmean\\);',flat,perl=TRUE))
      stopifnot(length(center)==1L,nzchar(center))
      center_vars <- words(sub('center ([^;]+) \\(grandmean\\);','\\1',center,perl=TRUE))
      stopifnot(identical(center_vars,tolower(unname(mapping[roles[grepl('x',roles)]]))))
    }
    if(ms) {
      mover <- segment(text,'%g#1%','%g#2%')
      stayer <- segment(text,'%g#2%','model c1:')
      group_block<-segment(text,'model g:','model c1:')
      stopifnot(identical(regmatches(group_block,gregexpr('%g#[0-9]+%',group_block))[[1]],c('%g#1%','%g#2%')))
      stopifnot(!grepl('@',mover,fixed=TRUE),
                all(vapply(c('c2 on c1;','c3 on c2;','c4 on c3;'),grepl,logical(1),x=mover,fixed=TRUE)))
      stopifnot(all(vapply(2:4,function(t) grepl(sprintf('[c%d#1 c%d#2];',t,t),mover,fixed=TRUE),logical(1))))
      for(t in 2:4) {
        # 数值从实际语法读取；三起点各自的最大概率必须在对应对角。
        intercept <- vapply(1:2,function(j) {
          rx<-sprintf('c%d#%d@(-?[0-9.]+)',t,j)
          h<-regmatches(stayer,regexpr(rx,stayer,perl=TRUE))
          if(!length(h)||!nzchar(h))stop('Missing stayer intercept')
          as.numeric(sub(rx,'\\1',h,perl=TRUE))
        },numeric(1))
        slopes <- matrix(0,2,2)
        for(j in 1:2) {
          rx<-sprintf('c%d#%d on ([^;]+);',t,j)
          h<-regmatches(stayer,regexpr(rx,stayer,perl=TRUE))
          if(!length(h)||!nzchar(h))stop('Missing stayer slope row')
          for(a in 1:2) {
            coefficient<-sprintf('c%d#%d@(-?[0-9.]+)',t-1,a)
            z<-regmatches(h,regexpr(coefficient,h,perl=TRUE))
            if(!length(z)||!nzchar(z))stop('Missing fixed stayer slope')
            slopes[j,a]<-as.numeric(sub(coefficient,'\\1',z,perl=TRUE))
          }
        }
        stopifnot(identical(as.numeric(intercept),c(-10,-10)),
                  isTRUE(all.equal(unname(slopes),diag(20,2))))
        for(a in 1:3) {
          z<-c(intercept+if(a<3)slopes[,a]else c(0,0),0);p<-exp(z-max(z));p<-p/sum(p)
          stopifnot(which.max(p)==a,all(p>0),all(p<1))
        }
      }
    }
    invisible(TRUE)
  }

  compiled <- list(); manifest <- list()
  for(source in c('original','renamed_reordered')) {
    data <- if(source=='original')synthetic else changed_source
    mapping <- if(source=='original')original else renamed
    for(id in specs) {
      built <- build(id,data,mapping)
      folder <- file.path(output_dir,source,id);dir.create(folder,recursive=TRUE)
      prior <- getwd()
      tryCatch({
        setwd(folder)
        MplusAutomation::mplusModeler(built$object,modelout='model.inp',dataout='source.dat',
          run=0L,check=FALSE,hashfilename=FALSE,writeData='always',quiet=TRUE,
          Mplus_command='FORBIDDEN_IN_SYNTHETIC_CI',killOnFail=FALSE)
      },finally=setwd(prior))
      ch7_validate_input_width(file.path(folder, 'model.inp'))
      text <- paste(readLines(file.path(folder,'model.inp'),warn=FALSE),collapse='\n')
      data_name<-gsub('"','',statement(segment(tolower(text),'data:','variable:'),'file'),fixed=TRUE)
      stopifnot(data_name=='source.dat')
      dat <- read.table(file.path(folder,data_name),header=FALSE)
      validate(text,dat,id,built$data,mapping)
      check(paste(source,id,'structure_and_dat',sep=':'),TRUE)
      key<-paste(source,id,sep='/')
      compiled[[key]]<-list(text=text,dat=dat,data=built$data,mapping=mapping)
      manifest[[key]]<-list(model_id=id,source=source,rows=nrow(dat),columns=ncol(dat),
        input=paste0(key,'/model.inp'),input_sha256=sha(file.path(folder,'model.inp')),
        data=paste0(key,'/source.dat'),data_sha256=sha(file.path(folder,'source.dat')))
    }
  }
  for(id in specs) {
    a<-compiled[[paste0('original/',id)]];b<-compiled[[paste0('renamed_reordered/',id)]]
    check(paste0(id,':renamed_syntax_changed'),a$text!=b$text)
    check(paste0(id,':canonical_semantics_equal'),identical(canonical(a$text,original),canonical(b$text,renamed)))
    check(paste0(id,':column_order_changed'),!identical(names(a$data),names(b$data)))
  }
  mutate_reject <- function(name,id,pattern,replacement) {
    item<-compiled[[paste0('original/',id)]]
    changed<-sub(pattern,replacement,item$text,fixed=TRUE)
    check(paste0(name,':mutation_applied'),changed!=item$text)
    reject(name,validate(changed,item$dat,id,item$data,item$mapping))
  }
  mutate_reject('wrong_categorical_type','lpa_t1_k2','CATEGORICAL = t1b1','CATEGORICAL = t1x1')
  mutate_reject('lpa_missing_class_block','lpa_t1_k2','%c#2%','%wrong#2%')
  mutate_reject('lpa_wrong_measurement_threshold','lpa_t1_k2','t1b1$1','t1b1$2')
  mutate_reject('wrong_data_file','lta_invariant','FILE = "source.dat"','FILE = "missing.dat"')
  mutate_reject('wrong_measurement_namespace','lta_invariant','MODEL c1:','MODEL c9:')
  mutate_reject('wrong_group_namespace','mslta_invariant','MODEL g:','MODEL x:')
  mutate_reject('missing_fourth_class','lta_invariant','c4(3)','c4(2)')
  mutate_reject('skip_wave_edge','lta_invariant','c3 ON c2;','c3 ON c1;')
  mutate_reject('broken_invariance_label','lta_invariant','(mk1i1)','(wrong)')
  mutate_reject('latent_g_must_not_be_known','mslta_invariant','CLASSES = g(2)','KNOWNCLASS = g(t1b1=0 t1b1=1); CLASSES = g(2)')
  mutate_reject('missing_stayer_group','mslta_invariant','%g#2%','%g#3%')
  mutate_reject('stayer_slope_not_fixed','mslta_invariant','c1#1@20','c1#1*20')
  mutate_reject('mover_intercept_not_free','mslta_invariant','[c2#1 c2#2];','[c2#1@0 c2#2@0];')
  mutate_reject('step3_initial_not_fixed','lta_step3','n1#1@','n1#1*')
  mutate_reject('step3_threshold_not_nominal','mslta_step3','n1#1@','n1$1@')
  mutate_reject('wrong_savedata_mode','lpa_t2_k3','SAVE = CPROBABILITIES','SAVE = FSCORES')
  mutate_reject('missing_define_dependency','lta_invariant','CENTER t1x1','CENTER missing')
  item<-compiled[['original/lta_invariant']]
  reject('dat_reordered_without_names',validate(item$text,item$dat[,rev(seq_len(ncol(item$dat)))],
         'lta_invariant',item$data,item$mapping))
  check('no_engine_outputs',length(list.files(output_dir,pattern='\\.(out|gh5)$',recursive=TRUE))==0L)
  check('no_posterior_file_without_engine',length(list.files(output_dir,pattern='^posterior.dat$',recursive=TRUE))==0L)
  receipt<-list(status='PASS_SYNTHETIC_COMPILE_ONLY',schema_version=1,
    models=length(specs),source_variants=2,compiled_inputs=length(manifest),
    synthetic_rows=320L,measurement_columns=24L,checks=checks,
    engine_calls=0L,research_data_read=FALSE,engine_syntax_acceptance=FALSE,
    knownclass_contract='absent: G is latent, not an observed group',
    step3_contract='synthetic error probabilities; not fitted Step-1 estimates',
    stayer_contract='finite logits approximate identity; mover diagonal remains allowed',
    R=as.character(getRversion()),MplusAutomation=as.character(utils::packageVersion('MplusAutomation')),
    artifacts=unname(manifest),
    references=c('lpa-lca-workflow.md','lta-workflow.md','ms-lta-workflow.md','chapter7-source-variable-contract-20261104.md'))
  jsonlite::write_json(receipt,file.path(output_dir,'receipt.json'),auto_unbox=TRUE,pretty=TRUE)
  cat('CH7_MIXTURE_SYNTHETIC_COMPILE_PASS',length(manifest),'inputs',length(checks),'checks; engine_calls=0\n')
  invisible(receipt)
}

if (sys.nframe()==0L) {
  args<-commandArgs(trailingOnly=TRUE)
  if(length(args)!=1L)stop('Usage: Rscript test_ch7_mixture_family_20261105.R <fresh-output-dir>')
  # skill 根：本脚本位于 scripts/ 下
  file_arg<-grep('^--file=',commandArgs(FALSE),value=TRUE)
  test_ch7_mixture_family(args[[1]],file.path(dirname(sub('^--file=','',file_arg[[1]])),'..'))
}
