# Runtime Platforms

## Apple Silicon and the estimation engine

The [Mplus platform page](https://www.statmodel.com/platforms.shtml), checked
2026-09-28, states that Mplus does not run natively on Apple M-family chips:
it runs through Rosetta, performance degradation has been reported, and there
are currently no plans for a native version because of compiler availability.
The macOS editor also does not support PLOT-command plots; GH5 output can be
read and plotted from R. These are Mplus platform constraints, not an inability
of MplusAutomation or native ARM R to run on macOS.

Use Windows as the validated estimation target for this worked example.
Do not infer a universal Windows-versus-Mac speed ratio or a general operating
system performance ranking. Benchmark identical model/data hashes, Mplus
versions, estimator settings and processor allocations; report hardware,
architecture/Rosetta, peak memory, CPU time, wall time and other host load.

The [MplusAutomation vignette](https://cran.r-project.org/web/packages/MplusAutomation/vignettes/vignette.html)
separates its three automation roles: generating related models, batch
execution, and extracting/comparing parameters and fit statistics. Mplus
remains the licensed estimation engine. Automation can reduce manual work,
queue delay, repeated preparation and unnecessary re-estimation; it does not
by itself accelerate a fixed Mplus numerical algorithm.

The [Mac FAQ](https://www.statmodel.com/macfaq.shtml) includes historical
Version 6.11/6.12 advice. Check version relevance before applying those
instructions to current Mplus installations.

## Runtime adapters

| Concern | Windows | macOS |
|---|---|---|
| R | RStudio-selected native Windows runtime | RStudio-selected native macOS runtime |
| Mplus | Resolve `Mplus.exe`, including custom installations | Resolve the installed command-line executable; GUI availability alone is insufficient |
| Paths | Absolute forward-slash paths in R; executable passed as an argument | Preserve filename case |
| Discovery | Native service `USERPROFILE` | Native service `HOME` |
| Installer | PowerShell adapter | Shell adapter |
| Checkpoints | Flush file and replace; POSIX directory `open/fsync` is not portable | File flush/replacement and supported directory synchronization |

Probe the actual target environment:

```r
R.home()
.libPaths()
packageVersion("MplusAutomation")
Sys.which(c("Mplus", "Mplus.exe", "mplus"))
MplusAutomation::detectMplus()
```

`detectMplus()` can return a command name, not an absolute file. Resolve and
verify it, then check the version in a new `.out`. Upgradable R/package versions
are dependency maintenance, not evidence of an operating-system defect.

## WSL Controller, Windows Runtime

Convert `/mnt/c/...` into `C:/...` at the R submission boundary. Preserve the
Windows service's user home, package library, executable and discovery files.

The same normalization is required when a portable JSON receipt is read by
both WSL Python and native Windows Python. A receipt may store `/mnt/c/...` so
that it remains readable by the Linux controller; before a Windows byte/hash
check, translate the drive prefix to `C:\\...` (or use `Path('C:/...')`). Do
not treat an unconverted WSL path as a missing source. Record the original
portable spelling and the resolved runtime path in the check result. This
small adapter prevents a false source-mutation or missing-file alarm while
keeping the Windows hash calculation authoritative.

```python
from pathlib import Path

def for_windows_runtime(raw: str) -> Path:
    if raw.startswith('/mnt/') and len(raw) > 6 and raw[5].isalpha() and raw[6] == '/':
        return Path(raw[5].upper() + ':/' + raw[7:])
    return Path(raw)
```

Run Windows diagnostics with native Windows Python/PowerShell. These prove the
Windows configuration; they do not automatically establish the Linux agent
process identity required by strict `ensure-ready --require-native`. Retain
real agent tool calls separately and report any gate unable to bind both sides.
Do not invent process IDs or mark an HTTP probe as native MCP evidence.

Cross-platform tests exercise code paths. Real Mac RStudio/Mplus integration
still requires access to that host and a license; report those evidence levels
separately.
