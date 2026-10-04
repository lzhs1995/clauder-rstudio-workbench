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
267 passed and 15 were skipped only because Rscript is not installed in the
isolated test environment. The run used the repository's uv-managed
environment and inserted the current checkout first on `sys.path`, avoiding
an older globally installed workbench package. The symlink-capability test was
the only platform-privilege skip among the Windows-specific checks.
