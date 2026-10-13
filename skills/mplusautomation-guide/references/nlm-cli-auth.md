# NotebookLM CLI version and authentication gate

`notebooklm-mcp-cli` is independently versioned from the RStudio/Mplus stack.
Before an NLM review, record the installed CLI version and run the authoritative
authentication check:

```powershell
nlm --version
nlm notebook list --json
```

`nlm notebook list --json` is the authentication proof. A successful response
with a JSON notebook list means `AUTH_VALID`; it is not necessary to run
`nlm login` again. `nlm login` is a recovery action only after the prescribed
authentication gate has failed. `nlm doctor auth-replay` is diagnostic and does
not replace the notebook-list check.

The probe in `scripts/nlm_capability_probe.py` records only the CLI version,
exit codes, failure categories and notebook count. It does not persist cookies,
tokens, notebook titles or raw error output. It never invokes `nlm login`.

Use the following state meanings:

| State | Meaning | Next action |
|---|---|---|
| `AUTH_VALID` | `nlm notebook list --json` succeeded | Continue to PDF/source checks |
| `AUTH_REQUIRED` | Three consecutive notebook-list failures classified as authentication failures | Follow the canonical B7 login recovery |
| `NETWORK_ERROR` | A failure was classified as proxy/DNS/timeout/network related | Check the host-local Clash gate, then re-run the list check |
| `NLM_ERROR` | CLI, JSON, parameter or other command failure | Preserve evidence and diagnose without declaring auth loss |

When a source upload or query fails, re-run `nlm notebook list --json` before
classifying the failure. Do not upload DOCX; the thesis-refiner PDF-only rule
remains in force.

The network gate is host-local. A Windows NLM call requires the Windows active
profile to pass `nlm-network`; a MacBook NLM call requires the MacBook active
profile to pass it. A Mac profile does not gate Windows RStudio or Mplus work.
