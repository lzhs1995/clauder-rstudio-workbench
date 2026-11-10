# Public code, private configuration / 公開程式與本機設定

This public repository contains reusable code, skill instructions, documentation,
synthetic fixtures, and explicitly sanitized examples. Public availability does
not authorize sharing the underlying research data or credentials.

| Publish / 可公開 | Keep local or in approved private storage / 保留於本機或獲准的私人儲存 |
| --- | --- |
| Algorithms, validators, schemas, generic instructions | API keys, passwords, access/refresh tokens, cookies, authorization headers |
| Synthetic data and reproducible synthetic tests | Licensed microdata, participant IDs, unpublished confidential results |
| Placeholder paths and client configuration templates | Complete machine-specific MCP configuration and raw process environments |
| Reviewed summaries of completed checks | Raw session transcripts, unfiltered HTTP responses, private audit receipts |

Use one maintained skill source, with client-specific local entry points. Keep
the secret/configuration loading interface in public code and the actual values
outside the checkout. Do not hard-code local account names to make an example
work on one machine.

Before publishing, inspect the staged diff and relevant Git history for accidental
inclusion. The repository's `.github/scripts/public_boundary_scan.py` checks
added lines for possible private paths and research values; it is a warning-only
heuristic, **not a credential scanner or proof that history contains no secrets**.
Review binary artifacts and archives separately. `.gitignore` prevents some
future additions but does not remove anything already tracked or committed.

If a real credential is discovered in public history, revoke or rotate it first,
then coordinate removal and history cleanup with the repository owner. Do not
silently rewrite shared history or report that deleting the current file removed
older copies. Report locations and secret types without reproducing the value
in public issues or CI output.

## Artwork

[`assets/workbench-logo.svg`](assets/workbench-logo.svg) is an original vector
illustration distributed under this repository's license. It is a project mark,
not an official R, RStudio, Posit, or Claude logo or an endorsement by those
projects. Its text remains accessible through SVG title/description and README
alternative text.
