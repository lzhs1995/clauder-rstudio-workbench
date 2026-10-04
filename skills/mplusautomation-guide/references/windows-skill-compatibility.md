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

The isolated workbench verification after these changes was 267 passed, 15
skipped and 34 subtests passed.
