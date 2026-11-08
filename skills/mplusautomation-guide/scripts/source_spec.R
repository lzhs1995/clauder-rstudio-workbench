# 通用CSV/DTA到DAT准备入口；只读适配、显式列序和缺失码，不选择模型、筛行或插补。
source_spec_runtime <- local({
  files <- vapply(sys.frames(), function(e) if (is.null(e$ofile)) '' else as.character(e$ofile)[1], '')
  files <- files[nzchar(files)]
  if (!length(files)) stop('Load source_spec.R with source()')
  directory <- dirname(normalizePath(tail(files, 1), winslash='/', mustWork=TRUE))
  runtime <- new.env(parent=baseenv())
  runtime$read.csv <- utils::read.csv
  runtime$read.table <- utils::read.table
  # 在私有环境复用APIM的读取/换名规则；不加载工作流、不执行模型准备。
  sys.source(file.path(directory, 'apim_v2_config.R'), envir=runtime)
  sys.source(file.path(directory, 'apim_v2_data_adapter.R'), envir=runtime)
  runtime$code_paths <- file.path(directory, c('source_spec.R', 'apim_v2_config.R', 'apim_v2_data_adapter.R'))
  if (!requireNamespace('digest', quietly=TRUE)) stop('Missing package: digest')
  runtime$loaded_code_hashes <- vapply(runtime$code_paths, function(p) digest::digest(p, algo='sha256', file=TRUE), '')
  runtime
})

prepare_mplus_source <- function(spec, output_dir) {
  for (package in c('digest', 'jsonlite'))
    if (!requireNamespace(package, quietly=TRUE)) stop('Missing package: ', package)
  runtime <- source_spec_runtime
  assert <- runtime$apim_v2_assert
  hash <- function(path) digest::digest(path, algo='sha256', file=TRUE)
  assert(identical(vapply(runtime$code_paths, hash, ''), runtime$loaded_code_hashes), 'Loaded source adapter code changed; reload explicitly')
  scalar_string <- function(x) is.character(x) && length(x)==1L && !is.na(x) && nzchar(x)
  required <- c('schema_version', 'data', 'data_mode', 'data_expected_sha256', 'columns', 'missing_codes', 'missing_value')
  allowed <- c(required, 'column_map', 'missing')
  assert(is.list(spec) && !is.null(names(spec)) && !anyDuplicated(names(spec)) &&
    all(required %in% names(spec)) && all(names(spec) %in% allowed), 'Invalid source_spec fields')
  assert(identical(spec$schema_version, 1L) || identical(spec$schema_version, 1), 'Unsupported source_spec version')
  assert(scalar_string(spec$data_mode) && spec$data_mode %in% c('csv', 'dta'), 'source_spec supports CSV or DTA only')
  assert(scalar_string(spec$data) && file.exists(spec$data) && !dir.exists(spec$data), 'Source file required')
  assert(scalar_string(spec$data_expected_sha256) && grepl('^[0-9a-f]{64}$', spec$data_expected_sha256), 'Expected source SHA256 required')
  columns <- spec$columns
  assert(is.character(columns) && length(columns)>0L && !anyNA(columns) &&
    all(grepl('^[A-Za-z][A-Za-z0-9_]{0,7}$', columns)) && !anyDuplicated(tolower(columns)),
    'Output columns must be unique Mplus names of at most eight characters')
  missing_value <- spec$missing_value
  assert(is.numeric(missing_value) && length(missing_value)==1L && is.finite(missing_value), 'Missing sentinel must be one finite number')
  missing <- spec$missing
  if (is.null(missing)) missing <- character()
  assert((is.character(missing) || is.numeric(missing)) && !anyNA(missing) &&
    (!is.numeric(missing) || all(is.finite(missing))), 'Invalid global missing codes')
  codes <- spec$missing_codes
  assert(is.list(codes) && length(codes)==length(columns) && !is.null(names(codes)) &&
    !anyNA(names(codes)) && !anyDuplicated(names(codes)) && setequal(names(codes), columns),
    'Declare missing_codes for every output column; use an empty vector for no extra codes')
  assert(all(vapply(codes, function(x) (is.character(x) || is.numeric(x)) && !anyNA(x) &&
    (!is.numeric(x) || all(is.finite(x))), logical(1))), 'Missing code entries must be finite numeric or character vectors')
  # APIM既有接口只接受非空码向量；先核完整声明，再仅传真正要替换的码。
  adapter_codes <- codes[lengths(codes)>0L]
  if (!length(adapter_codes)) adapter_codes <- NULL
  config <- list(data=spec$data, data_mode=spec$data_mode, column_map=spec$column_map,
    missing=missing, missing_codes=adapter_codes, row_id=NULL, cluster=NULL,
    # 这里只提供日期/时间列拒绝范围，不调用任何设计或建模函数。
    designs=list(list(x=columns)), output_dir=output_dir, template_bundles=list(), protected_roots=character())
  target <- runtime$apim_v2_path_check(config)
  link <- Sys.readlink(target)
  assert(!file.exists(target) && !dir.exists(target) && (is.na(link) || !nzchar(link)), 'Use a fresh output directory; never overwrite')
  assert(identical(hash(spec$data), spec$data_expected_sha256), 'Source SHA256 mismatch before reading')
  if (spec$data_mode=='csv') {
    # read.csv默认可能把多余首字段当行名，或给短行补空；先拒绝结构推断。
    # 引号内换行在count.fields中标记NA，逻辑记录末行给出完整字段数。
    widths <- utils::count.fields(spec$data, sep=',', quote='"', comment.char='', blank.lines.skip=FALSE)
    assert(length(widths)>1L && !is.na(widths[1]) && widths[1]>0L && !is.na(tail(widths,1)) &&
      all(widths[!is.na(widths)]==widths[1]), 'CSV records must match the header width without inferred row names or filling')
  }
  raw <- runtime$apim_v2_read_source(config, spec$data)
  assert(identical(hash(spec$data), spec$data_expected_sha256), 'Source changed during reading')
  assert(nrow(raw)>0L && all(columns %in% names(raw)), 'Source must have rows and every declared output column')
  audit <- attr(raw, 'apim_source_adapter')
  data <- raw[, columns, drop=FALSE]
  for (name in columns) {
    value <- data[[name]]
    # 禁止as.numeric把任意字符串变成缺失或把日期类偷换为数字。
    assert(is.character(value) || (is.numeric(value) && !is.object(value)), paste('Unsupported numeric column type:', name))
    parsed <- suppressWarnings(as.numeric(value))
    assert(!any(!is.na(value) & !is.finite(parsed)), paste('Non-numeric or nonfinite output value:', name))
    assert(!any(parsed[!is.na(parsed)] == missing_value), paste('Missing sentinel collides with observed value:', name))
    data[[name]] <- parsed
  }
  assert(identical(vapply(runtime$code_paths, hash, ''), runtime$loaded_code_hashes), 'Loaded source adapter code changed during preparation')
  # 所有验证完成后才独占创建新目录；失败保留已写文件，不清空或恢复旧输出。
  assert(dir.create(target, recursive=TRUE, showWarnings=FALSE), 'Cannot create fresh output directory')
  dat_path <- file.path(target, 'data.dat')
  order_path <- file.path(target, 'column_order.txt')
  block_path <- file.path(target, 'data_block.inp')
  write_utf8 <- function(text, path) {
    connection <- file(path, open='wb')
    on.exit(close(connection))
    writeBin(charToRaw(enc2utf8(text)), connection)
  }
  # 每列一行、UTF-8无BOM、LF及末尾换行；列序SHA独立于R序列化和平台。
  write_utf8(paste0(paste(columns, collapse='\n'), '\n'), order_path)
  # 17位有效数字保证有限IEEE double往返；小数点固定为点，缺失只写显式sentinel。
  sentinel <- chartr(',', '.', sprintf('%.17g', missing_value))
  tokens <- lapply(data, function(x) {
    result <- chartr(',', '.', sprintf('%.17g', x))
    result[is.na(x)] <- sentinel
    result
  })
  lines <- do.call(paste, c(tokens, list(sep=' ')))
  write_utf8(paste0(paste(lines, collapse='\n'), '\n'), dat_path)
  write_utf8(paste0('DATA: FILE = data.dat;\nVARIABLE:\nNAMES =\n',
    paste0(' ', columns, collapse='\n'), '\n;\nMISSING = ALL (', sentinel, ');\n'), block_path)
  # 回读逐位核数值、缺失和行列数，不把“文件写出”当作DAT合同通过。
  back <- utils::read.table(dat_path, header=FALSE, colClasses='numeric', na.strings=sentinel,
    comment.char='', quote='', check.names=FALSE)
  assert(nrow(back)==nrow(data) && ncol(back)==length(columns) &&
    all(vapply(seq_along(columns), function(i) identical(back[[i]], data[[i]]), logical(1))), 'DAT numeric round-trip failed')
  assert(identical(readLines(order_path, warn=FALSE, encoding='UTF-8'), columns), 'Column order readback failed')
  assert(identical(hash(spec$data), spec$data_expected_sha256), 'Source changed before receipt')
  assert(identical(vapply(runtime$code_paths, hash, ''), runtime$loaded_code_hashes), 'Loaded source adapter code changed before receipt')
  code_hashes <- setNames(runtime$loaded_code_hashes, basename(runtime$code_paths))
  # 只含哈希、变量名、计数和边界；不保存路径、逐行值、ID或描述统计。
  receipt <- list(schema_version=1L, status='DAT_PREPARED_NO_MODEL', source_format=spec$data_mode,
    source_sha256=spec$data_expected_sha256, dat_sha256=hash(dat_path), column_order_sha256=hash(order_path),
    data_block_sha256=hash(block_path), code_sha256=as.list(code_hashes), rows=nrow(data), columns=length(columns),
    column_names=I(columns), missing_by_column=as.list(vapply(data, function(x) sum(is.na(x)), 0L)),
    source_column_names=setNames(lapply(columns, function(n) audit$column_audit[[n]]$source), columns),
    missing_recode_counts=setNames(lapply(columns, function(n) audit$column_audit[[n]][c('source_missing',
      'tagged_missing', 'global_codes_replaced', 'column_codes_replaced', 'missing_after')]), columns),
    row_order_preserved=TRUE, rows_removed=0L, imputation_performed=FALSE, model_generated=FALSE,
    mplus_calls=0L, scientific_verified=FALSE)
  jsonlite::write_json(receipt, file.path(target, 'source_receipt.json'), auto_unbox=TRUE, pretty=TRUE)
  invisible(receipt)
}
