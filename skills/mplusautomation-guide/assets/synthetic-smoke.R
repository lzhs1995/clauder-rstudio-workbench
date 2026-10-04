# Configure these paths in the approved worker submission.
source(Sys.getenv("MPLUS_GUIDE_HELPER"),local=TRUE)
library(MplusAutomation)
set.seed(104729)
data <- data.frame(x=rnorm(400))
data$y <- 1.5*data$x+rnorm(400)
object <- mplusObject(TITLE="Synthetic MplusAutomation integration",MODEL="y ON x;",
  ANALYSIS="ESTIMATOR=ML; PROCESSORS=1;",rdata=data)
result <- run_mplus_model(object,run_root=Sys.getenv("MPLUS_GUIDE_RUN_ROOT"),model_id="synthetic_regression")
stopifnot(identical(result$validation$status,"PASS"))
