# 合成模板测试；不读取研究数据、不调用Mplus引擎。
test_compile_template_bundle <- function(skill_root,output_dir) {
  source(file.path(skill_root,'scripts/compile_template_bundle.R'),local=TRUE)
  if(dir.exists(output_dir))stop('Fresh test output_dir required')
  dir.create(output_dir,recursive=TRUE)
  original<-c('[[init]]','iterators = step;','step = 1:2;','label#step = b2 b1;',
    'filename = "pair_step[[step]].inp";','outputDirectory = "DO_NOT_WRITE_HERE";','[[/init]]',
    'TITLE: synthetic paired mediation step [[step]];','DATA: FILE = data.dat;',
    'VARIABLE: NAMES = x1 x2 m1 m2 y1 y2;',
    'MODEL:','m1 ON x1 (a1);','m2 ON x2 (a2);','y1 ON m1 (b1);','y2 ON m2 ([[label#step]]);',
    'MODEL CONSTRAINT:','NEW(i1 i2);','i1 = a1*b1;','i2 = a2*[[label#step]];',
    '[[step==2]]','MODEL TEST: 0 = a1-a2;','[[/step==2]]','OUTPUT: CINTERVAL;')
  path<-file.path(output_dir,'fixture_template.txt');writeLines(original,path)
  sha<-function(p)digest::digest(p,algo='sha256',file=TRUE)
  before<-sha(path);expected<-c('pair_step1.inp','pair_step2.inp');checks<-list()
  check<-function(name,value){stopifnot(isTRUE(value));checks[[name]]<<-TRUE}
  reject<-function(expr)inherits(tryCatch(force(expr),error=function(e)e),'error')
  target<-file.path(output_dir,'expanded')
  receipt<-compile_mplus_template_bundle(path,before,expected,target)
  one<-paste(readLines(file.path(target,expected[1])),collapse='\n')
  two<-paste(readLines(file.path(target,expected[2])),collapse='\n')
  check('template_source_bytes_unchanged',sha(path)==before)
  check('two_outputs_only',setequal(list.files(target,pattern='\\.inp$'),expected))
  check('unconstrained_label_preserved',grepl('y2 ON m2 (b2);',one,fixed=TRUE))
  check('equality_label_preserved',grepl('y2 ON m2 (b1);',two,fixed=TRUE))
  check('derived_formula_uses_selected_label',grepl('i2 = a2*b1;',two,fixed=TRUE))
  check('conditional_test_omitted_from_step1',!grepl('MODEL TEST:',one,fixed=TRUE))
  check('conditional_test_present_in_step2',grepl('MODEL TEST: 0 = a1-a2;',two,fixed=TRUE))
  check('no_unexpanded_tokens',!grepl('[[',paste(one,two),fixed=TRUE))
  check('source_body_unchanged_in_relocated_template',isTRUE(receipt$body_unchanged))
  check('wrong_sha_rejected',reject(compile_mplus_template_bundle(path,paste(rep('0',64),collapse=''),expected,file.path(output_dir,'bad_hash'))))
  check('partial_expected_scope_rejected',reject(compile_mplus_template_bundle(path,before,expected[1],file.path(output_dir,'partial'))))
  check('partial_scope_writes_nothing',!dir.exists(file.path(output_dir,'partial')))
  check('existing_output_rejected',reject(compile_mplus_template_bundle(path,before,expected,target)))
  bad<-sub('b2 b1','../outside b1',original,fixed=TRUE)
  bad<-sub('pair_step[[step]].inp','[[label#step]].inp',bad,fixed=TRUE)
  evil<-file.path(output_dir,'escape_template.txt');writeLines(bad,evil)
  check('expanded_filename_escape_rejected',reject(compile_mplus_template_bundle(evil,sha(evil),c('outside.inp','b1.inp'),file.path(output_dir,'escape'))))
  check('filename_escape_writes_nothing',!dir.exists(file.path(output_dir,'escape')))
  check('original_output_directory_not_used',!dir.exists('DO_NOT_WRITE_HERE'))
  result<-list(status='PASS_NATIVE_CREATE_MODELS_SYNTHETIC_TEMPLATE_ONLY',checks=checks,new_mplus_calls=0,
    research_templates_compiled=0,full_chapter_native_template_acceptance=FALSE,
    script_sha256=sha(file.path(skill_root,'scripts/compile_template_bundle.R')),
    MplusAutomation=as.character(packageVersion('MplusAutomation')))
  jsonlite::write_json(result,file.path(output_dir,'test_receipt.json'),auto_unbox=TRUE,pretty=TRUE)
  cat('TEMPLATE_COMPILER_CHECKS_PASS',length(checks),'\n');invisible(result)
}
