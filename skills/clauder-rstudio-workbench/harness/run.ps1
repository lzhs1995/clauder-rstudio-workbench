param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $RemainingArgs
)

$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path -Parent $PSScriptRoot

if ($env:CLAUDER_WORKBENCH_PYTHON) {
  $Python = $env:CLAUDER_WORKBENCH_PYTHON
} else {
  $candidate = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"
  if (Test-Path -LiteralPath $candidate) {
    $Python = $candidate
  } else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
      $Python = $cmd.Source
    }
  }
}

if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
  throw "Python not found. Set CLAUDER_WORKBENCH_PYTHON or install Python 3.10+."
}

$oldPythonPath = $env:PYTHONPATH
if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
  $env:PYTHONPATH = $SkillRoot
} else {
  $env:PYTHONPATH = "$SkillRoot;$oldPythonPath"
}

& $Python -m clauder_workbench @RemainingArgs
exit $LASTEXITCODE
