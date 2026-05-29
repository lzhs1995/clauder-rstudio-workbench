# Verification and Recovery

## Before Reporting Completion

- Confirm the R code ran in the intended RStudio session.
- Confirm returned objects or output files exist.
- Confirm important dimensions, counts, or validation flags.
- For long jobs, confirm the same `job_id` reached a terminal state.
- For formal deliverables, keep durable evidence: logs, CSV, RDS, figures, tables, or manifests.
- For formal deliverables, run `completion-check --mode formal`; do not report completion when it returns `BLOCK`, `TRANSPORT_UNSTABLE`, or `CONTRACT_FAILED`.
- Use `--require-file` constraints such as `min_rows`, `min_bytes`, `max_age_h`, and `output_root` so stale or tiny files cannot pass as durable evidence.
- Use `--require-transport-class` and `--require-preflight` when the task requires native MCP evidence.

## When Connection Fails

1. Check whether RStudio and the ClaudeR Addin are running.
2. Check session discovery files under `<USER_HOME>\.claude_r_sessions`.
3. Check the MCP config points to the intended ClaudeR bridge.
4. Restart the agent/MCP process after config changes.
5. Use HTTP only to diagnose Addin health, not to claim MCP-only success.

## Evidence Chain

Each harness run writes JSON evidence with `evidence_id`, `parent_evidence_ids`, `task_key`, `transport_class`, `job_id`, `io_mode`, artifact paths, and policy violations. A completion gate should point back to the preflight, async, resource-gate, and transport evidence that justified the final claim.

## Windows Multi-Session Check

If a second RStudio session causes the first to abort, suspect stale discovery cleanup. Use a ClaudeR build with a read-only PID liveness probe and rerun a multi-session regression before trusting long work.
