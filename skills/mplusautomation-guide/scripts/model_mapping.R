# 将研究数据映射到稳定的 Mplus 别名；不推断或改写统计模型。
mplus_from_mapping <- function(data, variables, model, analysis,
                               title = "Mapped growth model", variable = "",
                               output = "", savedata = "") {
  if (!is.data.frame(data) || !nrow(data)) stop("A nonempty data.frame is required")
  if (!is.character(variables) || !length(variables) || is.null(names(variables)))
    stop("variables must be a named character vector: Mplus alias = source column")
  aliases <- names(variables)
  if (anyNA(aliases) || any(!grepl("^[A-Za-z][A-Za-z0-9_]{0,7}$", aliases)) ||
      anyDuplicated(toupper(aliases))) stop("Mplus aliases must be unique, case-insensitive, and at most 8 characters")
  if (anyNA(variables) || any(!nzchar(variables)) || anyDuplicated(variables) ||
      anyDuplicated(names(data)) || any(!variables %in% names(data)))
    stop("Source columns must exist and have an unambiguous one-to-one mapping")
  selected <- data[, unname(variables), drop = FALSE]
  if (!all(vapply(selected, is.numeric, logical(1))))
    stop("Mapped columns must be numeric; encode categories explicitly before mapping")
  if (any(vapply(selected, function(x) any(is.infinite(x)) || all(is.na(x)), logical(1))))
    stop("Mapped columns cannot contain infinite values or be entirely missing")
  if (!is.character(model) || length(model) != 1L || is.na(model) || !nzchar(trimws(model)) ||
      !is.character(analysis) || length(analysis) != 1L || is.na(analysis) || !nzchar(trimws(analysis)))
    stop("Explicit MODEL and ANALYSIS syntax is required")
  # 保留行次序、缺失值和数值；仅更名，不进行标准化、插补或删行。
  names(selected) <- aliases
  MplusAutomation::mplusObject(TITLE = title, MODEL = model, ANALYSIS = analysis,
    VARIABLE = variable, OUTPUT = output, SAVEDATA = savedata,
    usevariables = aliases, rdata = selected, autov = FALSE, quiet = TRUE)
}
