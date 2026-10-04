# Windows NLM reliability contract

This contract records the Windows failure modes found while reviewing Chapter 7.
A successful nlm notebook list --json proves authentication, but it does not
prove that a source query will complete. Query failures remain separate from
authentication failures.

## Required sequence

1. Resolve the native Windows nlm.exe and record nlm --version.
2. Check the active Windows Clash profile for exactly
   DOMAIN-SUFFIX,notebooklm.google.com,链式代理-Gemini and the target group.
3. Run the no-cookie endpoint/TLS probe through the active mixed port.
4. Run nlm notebook list --json and persist only status, count, exit code and
   failure class.
5. Verify the PDF-only source by Notebook ID, source ID, title and SHA-256.
6. Query with a short prompt containing the literal `[filename.pdf]` marker
   (square brackets included) and explicit comma-separated `--source-ids`.

## Query runner rules

Use scripts/nlm_reliability.py on Windows Python 3.14. It captures raw bytes
and decodes UTF-8 after the child process exits, so PowerShell's GBK console
cannot corrupt JSON metadata. Each request has a fingerprint and a
request-manifest; a matching fingerprint is blocked rather than submitted
again after a timeout.

Retry only timeout/proxy/DNS/TLS errors. After every failed query, run
nlm notebook list --json again. Do not call nlm login automatically.
Parameter/JSON errors stop the request and require a corrected prompt or source.

The response is accepted only when it is a JSON object with a non-empty answer,
the expected source IDs in sources_used, at least one citation bound to an
expected source, and (for A5 scans) an explicit
NEW_ISSUES_COUNT=<n>; A5_NO_NEW_ISSUES=YES|NO trailer. The parser also accepts
the CLI's multiline colon form (`NEW_ISSUES_COUNT: 0` followed by
`A5_NO_NEW_ISSUES: YES`). Authentication is classified from command errors and
notebook-list checks; an answer that merely mentions authentication is not an
auth failure.

## Failure lessons from Chapter 7

- nlm login --check can disagree with a successful notebook-list gate; the JSON
  notebook list is authoritative.
- A query response with sources_used=[] is not a valid source-specific round,
  even if the prose looks plausible.
- In segmented Chapter 7 tests, broad prompts sometimes returned exit code 0 and
  plausible prose but `sources_used=[]`. The reliable recovery was to start a
  new conversation, keep the exact PDF filename in square brackets, and split
  the review into short source-bound checks. The empty-source response stays a
  diagnostic and is never promoted to an NLM citation.
- A 180/300 second timeout is a network/service failure, not evidence of
  missing authentication.
- SSL UNEXPECTED_EOF_WHILE_READING requires a fresh list check and active
  Clash/TLS diagnostics before retrying.
- NLM text extraction cannot prove a PDF page's red pixels; retain local PDF
  raster evidence as a separate visual audit.

## Windows release marker

Write WINDOWS_NLM_E2E_PASS only after two consecutive source-specific query
successes with valid citations and preserved raw/status evidence. A single
successful list check or one successful query is only READY_FOR_NLM.

The Chapter 7 Windows acceptance and formal A5 receipt are retained under the
isolated `final_delivery_20260930/` directory.
