# 保留原模板全部模型正文，仅重定位[[init]]输出目录；本文件不提交估计。
compile_mplus_template_bundle <- function(template_path,template_sha256,expected_files,output_dir) {
  for(p in c('MplusAutomation','digest','jsonlite'))if(!requireNamespace(p,quietly=TRUE))stop('Missing package: ',p)
  sha<-function(p)digest::digest(p,algo='sha256',file=TRUE)
  stopifnot(file.exists(template_path),identical(sha(template_path),template_sha256),
    is.character(expected_files),length(expected_files)>0,!anyDuplicated(tolower(expected_files)),
    all(grepl('^[A-Za-z0-9_][A-Za-z0-9_.-]*\\.inp$',expected_files,ignore.case=TRUE)))
  if(file.exists(output_dir)||dir.exists(output_dir))stop('Use a fresh isolated output_dir')
  raw<-readLines(template_path,warn=FALSE,encoding='UTF-8')
  start<-grep('[[init]]',raw,fixed=TRUE);end<-grep('[[/init]]',raw,fixed=TRUE)
  stopifnot(length(start)==1,length(end)==1,end>start+1,end<length(raw))
  init<-raw[seq.int(start+1,end-1)];body<-raw[seq.int(end+1,length(raw))]
  # 使用当前安装版本同一初始化解析器，先预测所有文件名，再允许任何写入。
  # 这是包内部API，版本与函数源码哈希随回执冻结，不能无检验升级。
  process_init<-get('processInit',envir=asNamespace('MplusAutomation'))
  values<-process_init(init);iterators<-values$iterators
  stopifnot(length(iterators)>0,!anyDuplicated(iterators),length(values$filename)==1,
    all(vapply(values[iterators],function(x)is.numeric(x)&&length(x)>0&&all(is.finite(x))&&all(x>0)&&all(x==as.integer(x)),logical(1))))
  grid<-expand.grid(values[iterators],KEEP.OUT.ATTRS=FALSE,stringsAsFactors=FALSE)
  resolve<-function(pattern,context) {
    tags<-regmatches(pattern,gregexpr('\\[\\[[^\\[\\]]+\\]\\]',pattern,perl=TRUE))[[1]]
    result<-pattern
    for(tag in unique(tags)) {
      token<-substring(tag,3,nchar(tag)-2);bits<-strsplit(token,'#',fixed=TRUE)[[1]]
      if(length(bits)==1 && token%in%iterators)value<-context[[token]]
      else if(length(bits)==1) {
        value<-values[[token]];stopifnot(length(value)==1,identical(attr(value,'iterator'),''))
      } else if(length(bits)==2) {
        value<-values[[bits[1]]]
        stopifnot(bits[2]%in%iterators,identical(attr(value,'iterator'),bits[2]))
        value<-value[context[[bits[2]]]]
      } else stop('Unsupported filename tag: ',tag)
      stopifnot(length(value)==1,!is.na(value))
      result<-gsub(tag,as.character(value),result,fixed=TRUE)
    }
    stopifnot(grepl('^[A-Za-z0-9_][A-Za-z0-9_.-]*\\.inp$',result,ignore.case=TRUE))
    result
  }
  predicted<-vapply(seq_len(nrow(grid)),function(i)resolve(values$filename,as.list(grid[i,,drop=FALSE])),character(1))
  stopifnot(!anyDuplicated(tolower(predicted)),setequal(predicted,expected_files))
  # 替换唯一完整outputDirectory声明；不更改filename、迭代器、条件分支和模型正文。
  init_text<-paste(init,collapse='\n')
  pattern<-'(?m)^\\s*outputDirectory\\s*=\\s*"[^"\\r\\n]*"\\s*;'
  matches<-gregexpr(pattern,init_text,perl=TRUE)[[1]]
  stopifnot(length(matches)==1,matches[1]>0)
  dir.create(output_dir,recursive=TRUE,showWarnings=FALSE)
  root<-normalizePath(output_dir,winslash='/',mustWork=TRUE)
  stopifnot(!grepl('["\\r\\n]',root,perl=TRUE))
  mlen<-attr(matches,'match.length')[1];at<-matches[1]
  changed<-paste0(substr(init_text,1,at-1),'\noutputDirectory = "',root,'";',substring(init_text,at+mlen))
  copied<-file.path(root,'template.txt')
  writeLines(c('[[init]]',changed,'[[/init]]',body),copied,useBytes=TRUE)
  copied_lines<-readLines(copied,warn=FALSE,encoding='UTF-8')
  copied_end<-grep('[[/init]]',copied_lines,fixed=TRUE)
  stopifnot(length(copied_end)==1,identical(copied_lines[seq.int(copied_end+1,length(copied_lines))],body))
  cat('compile_template',basename(template_path),'expected files',length(expected_files),'\n');flush.console()
  old_sink<-sink.number();log<-file(file.path(root,'createModels.log'),'wt')
  sink(log)
  tryCatch(MplusAutomation::createModels(copied),finally={while(sink.number()>old_sink)sink();close(log)})
  actual<-list.files(root,pattern='\\.inp$',ignore.case=TRUE)
  stopifnot(setequal(actual,expected_files),identical(sha(template_path),template_sha256))
  hashes<-vapply(file.path(root,actual),sha,character(1));names(hashes)<-actual
  receipt<-list(status='NATIVE_TEMPLATE_EXPANSION_ONLY',original_template_sha256=template_sha256,
    relocated_template_sha256=sha(copied),output_dir=root,body_unchanged=TRUE,files=as.list(hashes),
    MplusAutomation=as.character(utils::packageVersion('MplusAutomation')),
    processInit_function_sha256=digest::digest(paste(deparse(process_init),collapse='\n'),algo='sha256',serialize=FALSE),
    new_mplus_calls=0,data_preparation_verified=FALSE,native_model_fit_accepted=FALSE,scientific_closed=FALSE)
  jsonlite::write_json(receipt,file.path(root,'template_receipt.json'),auto_unbox=TRUE,pretty=TRUE)
  cat('compile_template_complete',length(actual),'inputs; no estimation\n');flush.console()
  invisible(receipt)
}
