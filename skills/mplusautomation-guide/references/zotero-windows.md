# Windows Zotero evidence runbook

Use this runbook when a Chapter 7 method claim must be checked against the
original Zotero record or attachment. It complements the Word/Zotero workflow;
it does not turn a citation key into evidence by itself.

## Connection and stale-lock recovery

1. Use the pinned Windows interpreter
   `<WINDOWS_USERPROFILE>\AppData\Local\Programs\Python\Python314\python.exe`.
2. Check that `zotero.exe` is running and probe
   `http://127.0.0.1:23119/connector/ping`. A 200 response containing
   `Zotero is running`, together with a 200 `/api/users/<user>/items` response,
   proves the local API is available.
3. If the API returns WinError 10061, treat it as an unavailable local app/API
   endpoint. It is not evidence that an attachment is missing.
4. A stale `parent.lock` can prevent Zotero from starting. After confirming
   that no Zotero process is alive, make a reversible rename such as
   `parent.lock.stale_backup_YYYYMMDD`; never delete the profile, database or
   attachment directory. Start Zotero and repeat the two API probes.
5. Record the original lock path, backup path, backup hash, process snapshot,
   endpoint status and timestamp. Do not copy cookies, tokens or proxy secrets
   into a receipt.

## Item and attachment verification

- Search by author/year or title, then record the parent item key and every
  attachment key returned by `zotero_get_item_children`.
- Call `zotero_get_item_fulltext` on the attachment key. Mark the source
  `MCP_FULLTEXT_VERIFIED` only when the call returns non-empty source text;
  otherwise retain `METADATA_ONLY` or `ATTACHMENT_UNAVAILABLE`.
- Duplicate linked-file attachments may fail with `file://` errors while an
  imported or alternate attachment succeeds. Record both facts and use the
  successful key; do not silently treat the failed duplicate as proof that the
  paper is unavailable.
- A parent item with no child attachment remains metadata-only, even when a
  DOI or external URL is present. External web evidence can be recorded as a
  separate source and must not be labelled as a Zotero attachment read.
- The local semantic database is a search index, not a full-text audit. Record
  its document count and update time, but use the live Zotero API/MCP response
  for source verification.

## Evidence contract for MplusAutomation work

Keep a JSON and human-readable receipt beside the isolated Chapter 7 run. For
each source store the citation label, parent key, attachment key(s), full-text
status, claims actually checked, and the matching Mplus/R workflow stage. Keep
methodology limits explicit: no library-wide full-text claim, no invented
attachment hash when the API does not expose a local path, and no modification
of the Zotero database or attachments.

The 2026-10-01 Windows validation is recorded in
`final_delivery_20260930/zotero_windows_repair_20261001.json` and
`final_delivery_20260930/zotero_method_evidence_20261001.json` in the Chapter 7
replay directory.
