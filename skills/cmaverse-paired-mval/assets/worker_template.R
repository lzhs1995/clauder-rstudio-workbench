# ---------------------------------------------------------------------------
# CMAverse paired-mval worker template (ONE mediator).
#
# This is a generalized, credential-free skeleton. Fill in the marked region
# with the original script's M=0 model block for the target mediator. The worker
# is driven entirely by environment variables so the fan-out harness can launch
# many copies, and it emits the three durable files the orchestrator polls:
#   state_<mediator>.json / manifest_<mediator>.csv / validation_<mediator>.csv
#
# NEVER hard-code credentials here. The optional durable-archive step reads any
# account/token strictly from the environment or an untracked config file.
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(CMAverse)
  library(tidyverse)
  library(jsonlite)
})

env_chr <- function(name, default = "") {
  v <- Sys.getenv(name, unset = default)
  if (!nzchar(v)) default else v
}
env_int  <- function(name, default) as.integer(env_chr(name, as.character(default)))
env_bool <- function(name, default = FALSE) {
  tolower(env_chr(name, if (default) "true" else "false")) %in% c("true", "1", "yes", "y")
}

# --- inputs (rename the prefix per project; keep the shape) ----------------
PREFIX        <- "NEW47"
MEDIATOR      <- env_chr(paste0(PREFIX, "_MEDIATOR"))
if (!nzchar(MEDIATOR)) stop(paste0(PREFIX, "_MEDIATOR is required."))
NBOOT         <- env_int(paste0(PREFIX, "_NBOOT"), 10L)
SEED          <- env_int(paste0(PREFIX, "_SEED"), 12345L)
GROUPS        <- trimws(strsplit(env_chr(paste0(PREFIX, "_GROUPS"), "sy_female,sy_male"), ",", fixed = TRUE)[[1]])
RUN_ID        <- env_chr(paste0(PREFIX, "_RUN_ID"), format(Sys.time(), "%Y%m%d_%H%M%S"))
MAX_PARALLEL  <- env_int(paste0(PREFIX, "_MAX_PARALLEL"), 1L)
OUTPUT_ROOT   <- env_chr(paste0(PREFIX, "_OUTPUT_ROOT"))
if (!nzchar(OUTPUT_ROOT)) stop(paste0(PREFIX, "_OUTPUT_ROOT is required."))
UPLOAD_ENABLED <- env_bool(paste0(PREFIX, "_UPLOAD_ENABLED"), FALSE)

# --- output layout (must match the fan-out contract) ----------------------
LEVEL_DIR    <- file.path(OUTPUT_ROOT, RUN_ID, sprintf("max_parallel_%s", MAX_PARALLEL))
MEDIATOR_DIR <- file.path(LEVEL_DIR, MEDIATOR)
dir.create(MEDIATOR_DIR, recursive = TRUE, showWarnings = FALSE)
STATE_PATH      <- file.path(MEDIATOR_DIR, sprintf("state_%s.json", MEDIATOR))
LOG_PATH        <- file.path(MEDIATOR_DIR, sprintf("run_log_%s.txt", MEDIATOR))
VALIDATION_PATH <- file.path(MEDIATOR_DIR, sprintf("validation_%s.csv", MEDIATOR))
MANIFEST_PATH   <- file.path(MEDIATOR_DIR, sprintf("manifest_%s.csv", MEDIATOR))
OUTPUT_RDATA    <- file.path(MEDIATOR_DIR, sprintf("res_cma_%s_aincc_2_1_list.RData", MEDIATOR))

write_state <- function(stage, status, ...) {
  payload <- c(list(mediator = MEDIATOR, run_id = RUN_ID, stage = stage,
                    status = status, updated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S")),
               list(...))
  jsonlite::write_json(payload, STATE_PATH, auto_unbox = TRUE, pretty = TRUE)
  cat(sprintf("[%s] %s: %s\n", format(Sys.time(), "%H:%M:%S"), stage, status))
  flush.console()
}

write_state("init", "running", nboot = NBOOT, groups = paste(GROUPS, collapse = ","))

# --- paired-mval mechanism --------------------------------------------------
# Shadow cmest()/saveRDS so the single mval=list(0) call also produces M=1 on
# the SAME bootstrap indices, then assemble the nested object:
#   nested[[group]][["0"]] <- full cmest, mval = 0
#   nested[[group]][["1"]] <- full cmest, mval = 1
# See references/worker-contract.md for the full pattern. Reuse the ORIGINAL
# M=0 region only; never re-run the original M=1 region.
#
# The paired estimator MUST record, per group, a hash of the bootstrap indices
# used for M=0 and for M=1, so pairing can be PROVEN (not assumed):
#   boot_hash[[group]][["0"]]  and  boot_hash[[group]][["1"]]
# These must be equal. Initialize the store the gate relies on:
boot_hash <- list()
#
# >>> BEGIN model region: paste the original M=0 block for this mediator <<<
#     - run cmest(..., mval = list(0), inference = "bootstrap", nboot = NBOOT)
#       once per group under a fixed SEED;
#     - the wrapper captures the paired M=1 result on the SAME indices;
#     - record boot_hash[[g]][["0"]] / [["1"]] (e.g. digest of the index matrix);
#     - build `nested` as a named list over GROUPS, each with [["0"]] and [["1"]].
# >>> END model region <<<

# placeholder so the template parses; replace with the real assembly above
if (!exists("nested")) stop("Model region not implemented: build `nested` before validation.")

# --- validation (one row per group) ----------------------------------------
write_state("validate", "running")
is_full_cmest <- function(x) inherits(x, "cmest")
paired_ok <- function(g) {
  h <- boot_hash[[g]]
  is.list(h) && !is.null(h[["0"]]) && !is.null(h[["1"]]) &&
    identical(h[["0"]], h[["1"]])
}
validation <- do.call(rbind, lapply(GROUPS, function(g) {
  data.frame(
    mediator = MEDIATOR, group = g,
    m0_is_full_cmest = is_full_cmest(nested[[g]][["0"]]),
    m1_is_full_cmest = is_full_cmest(nested[[g]][["1"]]),
    m0_effect_n = length(nested[[g]][["0"]]$effect.pe),
    m1_effect_n = length(nested[[g]][["1"]]$effect.pe),
    m0_data_ncol = ncol(nested[[g]][["0"]]$data),
    m1_data_ncol = ncol(nested[[g]][["1"]]$data),
    m0_ref_mval = paste(unlist(nested[[g]][["0"]]$ref$mval), collapse = "|"),
    m1_ref_mval = paste(unlist(nested[[g]][["1"]]$ref$mval), collapse = "|"),
    m0_boot_hash = if (!is.null(boot_hash[[g]][["0"]])) boot_hash[[g]][["0"]] else "",
    m1_boot_hash = if (!is.null(boot_hash[[g]][["1"]])) boot_hash[[g]][["1"]] else "",
    paired_same_bootstrap = paired_ok(g),
    stringsAsFactors = FALSE
  )
}))
utils::write.csv(validation, VALIDATION_PATH, row.names = FALSE, fileEncoding = "UTF-8")

# --- save full nested object ------------------------------------------------
write_state("save", "running")
save_started <- Sys.time()
assign(sprintf("res_cma_%s_aincc_2_1_list", MEDIATOR), nested)
saveRDS(nested, file = OUTPUT_RDATA, compress = FALSE)
save_elapsed <- as.numeric(difftime(Sys.time(), save_started, units = "secs"))
local_size <- file.info(OUTPUT_RDATA)$size

# --- optional durable archive (NO credentials in this file) ----------------
upload_status <- "skipped"; remote_path <- ""; remote_size <- NA; size_match <- NA; fs_id <- ""
if (UPLOAD_ENABLED) {
  # Call an external uploader that reads its credentials from the environment
  # or an untracked config. Verify remote fs_id + size before any local delete.
  write_state("upload", "running")
  # upload_status <- ...; remote_size <- ...; size_match <- (remote_size == local_size)
}

# --- manifest (one row) -----------------------------------------------------
manifest <- data.frame(
  run_id = RUN_ID, mediator = MEDIATOR, groups = paste(GROUPS, collapse = ","),
  nboot = NBOOT, seed = SEED, max_parallel = MAX_PARALLEL,
  local_rds_path = OUTPUT_RDATA, local_size = local_size,
  save_elapsed_sec = save_elapsed, validation_csv = VALIDATION_PATH,
  upload_status = upload_status, remote_path = remote_path, remote_size = remote_size,
  size_match = size_match, fs_id = fs_id, upload_log_path = "",
  completed_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"), worker_version = "template-1",
  stringsAsFactors = FALSE
)
utils::write.csv(manifest, MANIFEST_PATH, row.names = FALSE, fileEncoding = "UTF-8")

write_state("done", "complete", local_size = local_size, save_elapsed_sec = save_elapsed)
