# Windows portability checks for the workbench skill

When a cross-platform skill uses atomic JSON publication, flush the file before
`os.replace()`. A POSIX directory `fsync()` is an additional durability step;
Windows may reject opening the directory with `PermissionError`, so that step
must be optional and must not turn a successfully published file into a false
failure.

Tests that require creating a directory symlink need an explicit Windows
capability check. Without Developer Mode or the corresponding privilege,
`Path.symlink_to()` raises `WinError 1314`. Mark only that capability-dependent
test as skipped on Windows; keep the assertion active on hosts where symlink
creation is available.

The isolated Windows Python 3.14 verification on 2026-10-04 ran 282 tests:
267 passed and 15 were skipped because the isolated environment lacks Rscript
and, for one capability check, Windows symlink privilege. The run used the repository's uv-managed
environment and inserted the current checkout first on `sys.path`, avoiding
an older globally installed workbench package. The symlink-capability test was
the only platform-privilege skip among the Windows-specific checks.

## Stable file hashing on Windows Python 3.14

The 2026-11-01 native check observed identical device, inode, size, mtime and
SHA256, but path `stat` and handle `fstat` returned ctime values 11 ms apart.
Both APIs were stable across the read. Compare each API before/after using its
own ctime, and compare device/inode/size/mtime across the two APIs. Do not
discard ctime stability checks entirely or label the differing API values as
an actual file mutation. The manifest tests include that observed case and a
real mid-read content change; the original false rejection is retained.
