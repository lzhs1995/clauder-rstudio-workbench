# Thesis-refiner NLM contract

The canonical `论文精炼助手` skill remains the authority for A5 termination,
PDF-only sources, checkpoint recovery and supervisor/executor communication.
This guide supplies the Windows NLM capability facts that the canonical skill
must consume before starting a review.

## Required preflight

1. Resolve the native Windows `nlm.exe` path and record `nlm --version`.
2. Run `nlm notebook list --json`; a successful JSON list is `AUTH_VALID`.
3. Run the host-local Clash checker for the host that will call NLM.
4. Keep the PDF source hash, Notebook ID, CLI version and gate evidence in the
   task checkpoint; never store cookies, tokens, proxy passwords or raw profile
   contents.

## Failure routing

- A source/query error must be followed by another `nlm notebook list --json`.
- Three consecutive authentication-classified notebook-list failures enter the
  canonical B7 `AUTH_REQUIRED` recovery; the probe must never call `nlm login`
  automatically.
- Proxy, DNS or timeout failures enter `NETWORK_ERROR` and require the
  host-local Clash check before retrying.
- JSON/parameter/CLI failures enter `NLM_ERROR`; they are not evidence of an
  expired login.

MacBook network evidence is required only when NLM is executed on the MacBook.
It is not a prerequisite for Windows RStudio, Mplus or MplusAutomation work.
