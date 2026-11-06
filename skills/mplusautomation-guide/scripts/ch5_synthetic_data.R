# 第五章合成数据生成器：固定种子，不取自论文结果或个人记录。供合成合同与原生合成运行包共用。
# 列顺序即 assets/ch5 全部模板的 NAMES；改列必须同时改模板。
CH5_SYNTHETIC_COLUMNS <- c('id', 'cl', 'grp', 'xa', 'xb', 'ma', 'mb', 'ya', 'yb', 'w', 'wc1', 'wc3',
                           'c1', 'c2', 'yc', 'w2', 'xc', 'mc', 'wcat', 'ycc')

ch5_synthetic_data <- function(seed = 5105L, G = 400L) {
  # 保存并恢复调用者的随机数状态
  old <- if (exists('.Random.seed', envir = globalenv())) get('.Random.seed', envir = globalenv()) else NULL
  on.exit(if (is.null(old)) rm('.Random.seed', envir = globalenv()) else assign('.Random.seed', old, envir = globalenv()))
  set.seed(seed)
  n <- 3L * G
  cl <- rep(seq_len(G), each = 3L); u <- rnorm(G)[cl]
  d <- data.frame(id = seq_len(n), cl = cl, grp = rbinom(n, 1, .5),
                  xa = rbinom(n, 1, .5), xb = rbinom(n, 1, .4))
  d$ma <- rbinom(n, 1, plogis(-.3 + .8 * d$xa)); d$mb <- rbinom(n, 1, plogis(.2 + .5 * d$xb))
  d$ya <- rbinom(n, 1, plogis(-.5 + .4 * d$xa + .7 * d$ma)); d$yb <- rbinom(n, 1, plogis(.1 + .6 * d$mb))
  wcat <- sample(c(1, 2, 3), n, replace = TRUE)
  d$w <- rnorm(n); d$w2 <- runif(n, 0, 4)
  ec <- ch5_effect_code(wcat, c(1, 3, 2), 'wc')
  d$wc1 <- ec$wc_effect1; d$wc3 <- ec$wc_effect2
  d$c1 <- rnorm(n) + .6 * d$w; d$c2 <- rnorm(n)
  d$yc <- .3 * d$xa + .5 * d$ma + .25 * d$ma * d$w + .2 * d$c1 + u + rnorm(n)
  # 以下为续加的列：连续 X→M→Y 与三分类 W 调节 b 路径（真值：a=.5，b 按类别 .6/.2/.4）
  d$xc <- rnorm(n)
  d$mc <- .5 * d$xc + .2 * d$c2 + rnorm(n)
  d$wcat <- wcat
  b_by_cat <- c(`1` = .6, `2` = .2, `3` = .4)
  d$ycc <- .15 * d$xc + b_by_cat[as.character(wcat)] * d$mc + .2 * d$c1 + u + rnorm(n)
  d[, CH5_SYNTHETIC_COLUMNS]
}
