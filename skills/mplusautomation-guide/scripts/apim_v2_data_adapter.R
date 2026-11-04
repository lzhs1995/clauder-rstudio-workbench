# v2 数据读入边界：显式换名、保留底层编码、逐列缺失值声明；不推断量表或夫妻身份。
apim_v2_adapter_spec <- function(config, columns) {
  apim_v2_assert(length(columns)>0&&!anyNA(columns)&&all(nzchar(columns))&&!anyDuplicated(columns),
    'Source columns must have unique nonempty names')
  mode<-apim_v2_default(config$data_mode,'csv')
  map<-config$column_map
  codes<-config$missing_codes
  if(mode=='archived_dat')apim_v2_assert(is.null(map)&&is.null(codes),
    'Archived DAT cannot use column_map or missing_codes')
  if(!is.null(map)) {
    apim_v2_assert(is.character(map)&&length(map)>0&&!is.null(names(map))&&
      !anyNA(map)&&!anyNA(names(map))&&all(nzchar(map))&&all(nzchar(names(map)))&&
      !anyDuplicated(map)&&!anyDuplicated(names(map)),
      'column_map must be a one-to-one named character vector: canonical = source')
    apim_v2_assert(all(unname(map)%in%columns),'column_map references missing source columns')
    columns[match(unname(map),columns)]<-names(map)
    apim_v2_assert(!anyDuplicated(columns),'column_map collides with an unmapped source column')
  }
  if(!is.null(codes)) {
    apim_v2_assert(is.list(codes)&&length(codes)>0&&!is.null(names(codes))&&
      !anyNA(names(codes))&&all(nzchar(names(codes)))&&!anyDuplicated(names(codes))&&
      all(names(codes)%in%columns),'missing_codes must name existing canonical columns')
    apim_v2_assert(all(vapply(codes,function(x)(is.character(x)||is.numeric(x))&&length(x)>0&&!anyNA(x),logical(1))),
      'Each missing_codes entry must contain explicit nonmissing codes')
    apim_v2_assert(!length(intersect(names(codes),c(config$row_id,config$cluster))),
      'Do not recode record or cluster identities as missing values')
  }
  columns
}

apim_v2_source_columns <- function(config) {
  mode<-apim_v2_default(config$data_mode,'csv')
  if(mode=='csv')columns<-names(read.csv(config$data,nrows=0,check.names=FALSE))
  else if(mode=='dta') {
    apim_v2_assert(requireNamespace('haven',quietly=TRUE),'DTA input requires the haven package')
    columns<-names(haven::read_dta(config$data,n_max=0,.name_repair='minimal'))
  } else columns<-config$data_columns
  apim_v2_adapter_spec(config,columns)
}

apim_v2_missing_match <- function(value,codes,numeric_source=FALSE) {
  if(!length(codes))return(rep(FALSE,length(value)))
  if(numeric_source||is.numeric(codes)) {
    numbers<-suppressWarnings(as.numeric(value))
    numeric_codes<-suppressWarnings(as.numeric(codes))
    return(!is.na(numbers)&numbers%in%numeric_codes[!is.na(numeric_codes)])
  }
  !is.na(value)&value%in%as.character(codes)
}

apim_v2_read_source <- function(config,path) {
  mode<-apim_v2_default(config$data_mode,'csv')
  if(mode=='archived_dat') {
    x<-read.table(path,colClasses='character',na.strings=config$missing,header=FALSE,check.names=FALSE)
    apim_v2_assert(ncol(x)==length(config$data_columns),'Archived DAT column mismatch')
    names(x)<-config$data_columns
    apim_v2_adapter_spec(config,names(x))
    return(x)
  }
  if(mode=='csv')x<-read.csv(path,colClasses='character',check.names=FALSE,na.strings=config$missing)
  else {
    apim_v2_assert(mode=='dta','Unsupported data mode')
    apim_v2_assert(requireNamespace('haven',quietly=TRUE),'DTA input requires the haven package')
    x<-as.data.frame(haven::read_dta(path,.name_repair='minimal'),check.names=FALSE)
  }
  original_names<-names(x)
  names(x)<-apim_v2_adapter_spec(config,original_names)
  counts<-list()
  model_columns<-unique(unlist(lapply(config$designs,function(d)c(unlist(d$x),unlist(d$y),
    unlist(d$m),unlist(lapply(d$w,`[[`,'columns')),unlist(d$controls))),use.names=FALSE))
  for(n in names(x)) {
    value<-x[[n]]
    numeric_source<-is.numeric(value)
    native_na<-sum(is.na(value));tagged_na<-0L;labelled<-FALSE
    if(mode=='dta') {
      labelled<-inherits(value,'haven_labelled')
      if(is.double(value))tagged_na<-sum(haven::is_tagged_na(value))
      if(labelled)value<-haven::zap_labels(value)
      if(inherits(value,c('Date','POSIXt','difftime'))) {
        apim_v2_assert(!n%in%c(config$row_id,config$cluster,model_columns),
          paste('Explicit date/time preprocessing required for',n))
        value<-as.character(value)
      }
      if(is.numeric(value)&&n%in%c(config$row_id,config$cluster))
        apim_v2_assert(all(is.na(value)|(is.finite(value)&value==trunc(value)&abs(value)<2^53)),
          paste('Unsafe numeric identity; supply an exact character ID:',n))
      # 数值列保持 double，避免筛选值/类别水平比较时经过字符格式化而丢精度。
      # 数值身份列单独转为精确十进制字符；值标签不转换为 factor。
      if(is.numeric(value)) {
        value<-as.numeric(value)
        value[is.na(value)]<-NA_real_
        if(n%in%c(config$row_id,config$cluster))value<-ifelse(is.na(value),NA_character_,sprintf('%.0f',value))
      } else value<-as.character(value)
    }
    # CSV 全局规则由 read.csv 完成，不能重复数值匹配而改变旧版字符 ID。
    global_missing<-if(mode=='csv')rep(FALSE,length(value)) else apim_v2_missing_match(value,config$missing,numeric_source)
    value[global_missing]<-NA
    code_missing<-apim_v2_missing_match(value,config$missing_codes[[n]],numeric_source)
    value[code_missing]<-NA
    x[[n]]<-value
    counts[[n]]<-list(source=original_names[match(n,names(x))],canonical=n,
      source_missing=native_na,tagged_missing=tagged_na,value_labels_removed=labelled,
      global_codes_replaced=sum(global_missing),column_codes_replaced=sum(code_missing),missing_after=sum(is.na(value)))
  }
  attr(x,'apim_source_adapter')<-list(version=1L,mode=mode,rows=nrow(x),columns=ncol(x),
    column_map=config$column_map,missing_codes=config$missing_codes,column_audit=counts,
    haven_version=if(mode=='dta')as.character(utils::packageVersion('haven')) else NULL,
    inference_boundary='I/O and explicit recoding only; no automatic measurement or member equivalence')
  x
}
