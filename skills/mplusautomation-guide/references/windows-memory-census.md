# Windows memory census before Mplus concurrency

Windows' total physical RAM is not the same as the memory available to a new
Mplus process. Record both resident set size (RSS) and Windows private bytes,
because MCP and browser processes can reserve a large commit while showing a
small RSS. A single Mplus process can therefore be small while the host still
has too little physical or commit headroom for a second worker.

The 2026-10-05 CFPS census on a 16 GiB host found 661 processes. The three R
sessions had about 3.83 GiB private bytes in total; the running Mplus was about
143 MiB private. Seventy-three Python processes (mostly Zotero/Claude MCP
bridges) reported about 7.2 GiB private bytes, 36 Node MCP processes about 2.5
GiB, and RStudio renderer processes about 2.43 GiB. These private-byte values
include reservations and are not a claim that all of them occupied physical
RAM at once. They explain why “three RStudio plus one Mplus” does not describe
the whole host.

Do not terminate a process solely because it has a large private-byte value.
First resolve its parent chain, creation time, active MCP/session ownership,
and whether it has unsaved R objects or an active model. The safe reclamation
helper may close only its explicit idle-utility allowlist; it must not kill
RStudio, Mplus, MCP bridges, WSL, OneDrive, or user document applications.
When an MCP bridge is confirmed stale, archive its identity and close the
complete owned tree, then verify RStudio/Mplus health and rerun the census.

The practical admission rule remains: reuse successful outputs first; keep one
Mplus worker while FreePhys is near 1–2 GiB or CPU is near the configured
limit; only consider two workers after fresh profiles show stable output
paging=0, low disk latency, sufficient commit headroom, and enough physical
memory for both observed peaks plus reserve. Never trade provenance or a live
research session for an unverified memory gain.
