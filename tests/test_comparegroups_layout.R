source("skills/comparegroups-guide/scripts/comparegroups_common.R")
cg_require_packages()
frame <- data.frame(row_label = c("Continuous variable", "Categorical variable"))
for (i in 1:6) frame[[paste("Comparison", i, "versus other group")]] <- c("4.300 (0.764)", "24082 (49.75%)")
results <- list(list(label = "Wide table", display = frame))
spec <- list(display = list(docx = list()), blocks = list())
measure <- function(path) {
  dir <- tempfile("layout-xml-")
  dir.create(dir)
  on.exit(unlink(dir, recursive = TRUE), add = TRUE)
  xml <- xml2::read_xml(utils::unzip(path, files = "word/document.xml", exdir = dir))
  page <- xml2::xml_find_first(xml, "//w:sectPr/w:pgSz")
  margins <- xml2::xml_find_first(xml, "//w:sectPr/w:pgMar")
  printable <- as.numeric(xml2::xml_attr(page, "w")) -
    sum(as.numeric(xml2::xml_attrs(margins)[c("left", "right")]))
  tables <- xml2::xml_find_all(xml, "//w:tbl")
  widths <- vapply(tables, function(table) sum(as.numeric(xml2::xml_attr(
    xml2::xml_find_all(table, "./w:tblGrid/w:gridCol"), "w"))), numeric(1))
  list(fits = all(widths <= printable + ncol(frame)), widths = widths, printable = printable)
}
render <- function(spec) {
  path <- tempfile(fileext = ".docx")
  cg_render_docx(results, path, "Layout regression", spec)
  measure(path)
}
stopifnot(render(spec)$fits)
landscape <- spec
landscape$display$docx$orientation <- "landscape"
stopifnot(render(landscape)$fits, render(landscape)$printable > render(spec)$printable)
explicit <- spec
explicit$display$docx$column_widths <- as.list(rep(1, ncol(frame)))
error <- tryCatch(render(explicit), error = identity)
stopifnot(inherits(error, "error"), grepl("printable page width", conditionMessage(error)))
dense <- results
for (i in 7:18) dense[[1L]]$display[[paste("Comparison", i)]] <- c("4.300 (0.764)", "24082 (49.75%)")
dense_error <- tryCatch(cg_render_docx(dense, tempfile(fileext = ".docx"), "Dense", spec), error = identity)
stopifnot(inherits(dense_error, "error"), grepl("too dense", conditionMessage(dense_error)))

# 移除自动宽度限制必须让同一个 DOCX 渲染检查失败。
original <- cg_render_docx
code <- paste(deparse(body(original)), collapse = "\n")
body(cg_render_docx) <- parse(text = gsub("available_width", "printable_width", code, fixed = TRUE))[[1L]]
stopifnot(render(spec)$fits)
needle <- "if (sum(widths) > available_width)"
stopifnot(length(gregexpr(needle, code, fixed = TRUE)[[1L]]) == 2L)
body(cg_render_docx) <- parse(text = gsub(needle, "if (FALSE)", code, fixed = TRUE))[[1L]]
stopifnot(!render(spec)$fits)
cg_render_docx <- original
cat("DOCX_LAYOUT 6/6 PASS\n")
