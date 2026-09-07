param([string]$ReadmePath = (Join-Path $PSScriptRoot "../../README.md"))

$ErrorActionPreference = "Stop"
$markdown = Get-Content -LiteralPath $ReadmePath -Raw
$blocks = @([regex]::Matches($markdown, '(?ms)^```powershell\r?\n(.*?)^```') |
    Where-Object { $_.Groups[1].Value.Contains("Invoke-WebRequest") })
if ($blocks.Count -ne 1) { throw "Expected one documented ZIP bootstrap" }
$bootstrap = $blocks[0].Groups[1].Value
$tokens = $null
$parseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseInput($bootstrap, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }

$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("bootstrap-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$script:fixtureZip = ""
$script:installCalled = $false

function Invoke-WebRequest {
    param([string]$Uri, [string]$OutFile)
    if ($Uri -notmatch '^https://github.com/lzhs1995/clauder-rstudio-workbench/releases/download/v0\.6\.1/clauder-rstudio-workbench-v0\.6\.1\.zip$') {
        throw "Unexpected release URL"
    }
    Copy-Item -LiteralPath $script:fixtureZip -Destination $OutFile
}

function powershell {
    param([switch]$NoProfile, [string]$ExecutionPolicy, [string]$File, [switch]$ConfigureCodex)
    if (-not (Test-Path -LiteralPath $File)) { throw "Missing installer at invocation" }
    $script:installCalled = $true
    $global:LASTEXITCODE = 0
}

function Test-BootstrapCase {
    param([string]$Name, [string]$Code, [string]$Mode)
    $caseRoot = Join-Path $testRoot $Name
    $caseProfile = Join-Path $caseRoot "profile"
    $payload = Join-Path $caseRoot "payload"
    $package = Join-Path $payload "workbench"
    New-Item -ItemType Directory -Path $package -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $package "install.ps1") -Value "exit 0"
    if ($Mode -eq "malformed") {
        New-Item -ItemType Directory -Path (Join-Path $payload "unexpected") | Out-Null
        Set-Content -LiteralPath (Join-Path $payload "unexpected/extra.txt") -Value "extra"
    }
    $script:fixtureZip = Join-Path $caseRoot "fixture.zip"
    Compress-Archive -Path (Join-Path $payload "*") -DestinationPath $script:fixtureZip
    $destination = Join-Path $caseProfile "projects/clauder-rstudio-workbench"
    $sentinel = Join-Path $destination "uncommitted.txt"
    if ($Mode -eq "existing") {
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
        Set-Content -LiteralPath $sentinel -Value "preserve unpublished work"
    }
    $script:installCalled = $false
    $failure = ""
    $locationBefore = Get-Location
    try {
        # Substitute only environment inputs so the literal documented flow runs in a sandbox.
        $isolated = $Code.Replace('$env:USERPROFILE', '$caseProfile').Replace('$env:TEMP', '$caseRoot')
        & ([scriptblock]::Create($isolated))
    } catch {
        $failure = $_.Exception.Message
    } finally {
        Set-Location -LiteralPath $locationBefore.Path
    }
    if ($Mode -eq "existing") {
        $preserved = (Test-Path -LiteralPath $sentinel) -and
            ((Get-Content -LiteralPath $sentinel -Raw).Trim() -eq "preserve unpublished work")
        return $preserved -and (-not $script:installCalled) -and $failure.StartsWith("Destination already exists:")
    }
    if ($Mode -eq "malformed") {
        return (-not (Test-Path -LiteralPath $destination)) -and (-not $script:installCalled) -and
            ($failure -eq "Expected one repository root in release ZIP")
    }
    return (-not $failure) -and $script:installCalled -and
        (Test-Path -LiteralPath (Join-Path $destination "install.ps1"))
}

foreach ($mode in @("success", "existing", "malformed")) {
    if (-not (Test-BootstrapCase -Name $mode -Code $bootstrap -Mode $mode)) { throw "BOOTSTRAP $mode FAIL" }
    Write-Host "BOOTSTRAP $mode PASS"
}
$renamed = $bootstrap.Replace('$staging', '$renamedStage')
if ($renamed -eq $bootstrap) { throw "Equivalent mutation not applied" }
if (-not (Test-BootstrapCase -Name "equivalent" -Code $renamed -Mode "success")) { throw "Equivalent mutation failed" }
Write-Host "BOOTSTRAP equivalent PASS"
$guard = 'if (Test-Path -LiteralPath $dest) { throw "Destination already exists: $dest" }'
$excised = $bootstrap.Replace($guard, "")
if ($excised -eq $bootstrap) { throw "Guard excision not applied" }
if (Test-BootstrapCase -Name "guard-excised" -Code $excised -Mode "existing") { throw "Guard excision was not detected" }
Write-Host "BOOTSTRAP guard_excision DETECTED"
Write-Host "BOOTSTRAP_TOTAL 5/5"
Write-Host "BOOTSTRAP_ARTIFACTS $testRoot"
