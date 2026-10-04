# 根据真实观测时间生成增长载荷；不替研究者选择趋势或分段点。
growth_time_basis <- function(waves, shape = c("linear", "quadratic", "piecewise"), knot = NULL) {
  shape <- match.arg(shape)
  if (!is.numeric(waves) || length(waves) < 3L || any(!is.finite(waves)) ||
      any(diff(waves) <= 0)) stop("waves must contain at least three strictly increasing finite times")
  time <- waves - waves[1L]
  if (shape != "piecewise" && !is.null(knot)) stop("knot is only used for piecewise growth")
  basis <- switch(shape,
    linear = cbind(intercept = 1, slope = time),
    quadratic = cbind(intercept = 1, slope = time, quadratic = time^2),
    piecewise = {
      if (!is.numeric(knot) || length(knot) != 1L || !is.finite(knot) ||
          knot <= waves[1L] || knot >= waves[length(waves)])
        stop("Specify one interior knot on the original wave-time scale")
      centered_knot <- knot - waves[1L]
      cbind(intercept = 1, before = pmin(time, centered_knot), after = pmax(0, time - centered_knot))
    })
  rownames(basis) <- as.character(waves)
  basis
}
