param(
    [string]$ClaudeRRepo = "https://github.com/lzhs1995/ClaudeR.git",
    [string]$ClaudeRRef = "v0.2.0-lzhs.1",
    [string]$ClaudeRDir = "$env:USERPROFILE\projects\ClaudeR",
    [string]$CodexHome = "$env:USERPROFILE\.codex",
    [string]$RExe = "",
    [string]$LogFile = "",
    [switch]$ConfigureCodex,
    [switch]$ConfigureClaudeCode,
    [switch]$ConfigureCopilot,
    [switch]$SkipHarness,
    [switch]$SkipClaudeR,
    [switch]$DevSync,
    [switch]$SyncAgentsSkill,
    [string]$AgentsHome = "$env:USERPROFILE\.agents",
    [string]$HarnessPython = "",
    [string]$WorkbenchBinDir = "$env:USERPROFILE\bin",
    [switch]$AddHarnessToPath,
    [switch]$NoZipFallback,
    [switch]$InstallPython314,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$script:ClaudeRSourceType = "unknown"
$script:ClaudeRSourceUrl = $ClaudeRRepo

if ($LogFile) {
    $logDir = Split-Path -Parent $LogFile
    if ($logDir -and -not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Force $logDir | Out-Null
    }
    Start-Transcript -Path $LogFile -Append | Out-Null
}

function Write-Step($Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

# v0.2.4: UTF-8 编码安全读写助手
# 解决：PowerShell 5.1 默认 Set-Content -Encoding UTF8 写入带 BOM；
#       Get-Content -Raw 在 Windows 中文环境用 ANSI/CP936 读取，把 UTF-8 字节误解码。
function Read-Utf8File($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return "" }
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -eq 0) { return "" }
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $bytes = $bytes[3..($bytes.Length - 1)]
    }
    return [System.Text.Encoding]::UTF8.GetString($bytes)
}

function Write-Utf8NoBom($Path, $Content) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

function Test-TomlParseable($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $py = $null
    try { $py = Find-HarnessPython } catch { return $true }
    if (-not $py -or -not (Test-Path -LiteralPath $py)) { return $true }
    $code = @'
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        sys.exit(0)
with open(sys.argv[1], 'rb') as f:
    data = f.read()
if data.startswith(b'\xef\xbb\xbf'):
    data = data[3:]
try:
    tomllib.loads(data.decode('utf-8'))
except Exception as e:
    sys.stderr.write("TOML parse error: " + str(e) + "\n")
    sys.exit(2)
'@
    # v0.2.4: PS 5.1 把多行 -c 字符串传给 python.exe 时会因换行符截断；改用临时文件
    $tmp = [System.IO.Path]::GetTempFileName() + ".py"
    try {
        [System.IO.File]::WriteAllText($tmp, $code, (New-Object System.Text.UTF8Encoding($false)))
        & $py $tmp $Path 2>&1 | Out-Host
        return ($LASTEXITCODE -eq 0)
    } finally {
        Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

function Restore-FromLatestBackup($Path) {
    $dir = Split-Path -Parent $Path
    $name = Split-Path -Leaf $Path
    $bakPattern = "$name.bak_*"
    $bak = Get-ChildItem -LiteralPath $dir -Filter $bakPattern -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($bak) {
        Copy-Item -LiteralPath $bak.FullName -Destination $Path -Force
        Write-Warning "Restored $Path from $($bak.Name)"
        return $bak.FullName
    }
    return $null
}

function Test-Executable($Command) {
    if ($Command -match '[\\/]') {
        return (Test-Path -LiteralPath $Command)
    }
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Require-Command($Command, $InstallHint) {
    if (-not (Test-Executable $Command)) {
        throw "Required command not found: $Command. $InstallHint"
    }
}

function Invoke-Checked($Command, $Arguments) {
    Require-Command $Command "Install it, add it to PATH, or pass an explicit path where supported."
    Write-Host "+ $Command $($Arguments -join ' ')" -ForegroundColor DarkGray
    if ($DryRun) { return }
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command"
    }
}

function Backup-File($Path) {
    if (Test-Path $Path) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backup = "$Path.bak_$stamp"
        Write-Host "Backing up $Path -> $backup"
        if (-not $DryRun) {
            Copy-Item -LiteralPath $Path -Destination $backup -Force
        }
    }
}

function Find-RExe {
    if ($RExe -and (Test-Path $RExe)) { return $RExe }
    $cmd = Get-Command R.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = Get-ChildItem "C:\Program Files\R" -Filter R.exe -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    if ($candidates) { return $candidates[0].FullName }
    throw "Could not find R.exe. Re-run with -RExe <path-to-R.exe>. Install hint: winget install --id RProject.R -e"
}

function Test-RStudioInstalled {
    if (Get-Command rstudio.exe -ErrorAction SilentlyContinue) { return $true }
    $candidates = @(
        "C:\Program Files\RStudio\rstudio.exe",
        "C:\Program Files\Posit\RStudio\rstudio.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $true }
    }
    return $false
}

function Test-Prerequisites {
    Write-Step "Checking prerequisites"
    if (-not (Test-Executable "git")) {
        if ($NoZipFallback) {
            throw "Required command not found: git. Install Git for Windows: winget install --id Git.Git -e"
        }
        Write-Warning "git not found. ClaudeR install will rely on zip fallback. Install Git for Windows: winget install --id Git.Git -e"
    }

    if ($ConfigureCodex -or $ConfigureClaudeCode -or $ConfigureCopilot) {
        Require-Command "uv" "Install uv: winget install --id astral-sh.uv -e"
        Require-Command "uvx" "Install uv: winget install --id astral-sh.uv -e"
    }
    if ($ConfigureClaudeCode) {
        Require-Command "claude" "Install Claude Code first, then re-run this installer."
    }
    if (-not $SkipHarness) {
        $resolvedPython = Find-HarnessPython
        Write-Host "Harness Python: $resolvedPython"
    }

    if (-not ($DevSync -or $SkipClaudeR)) {
        $resolvedR = Find-RExe
        Write-Host "R.exe: $resolvedR"
    } else {
        Write-Host "R.exe: skipped by -DevSync/-SkipClaudeR"
    }
    if (-not (Test-RStudioInstalled)) {
        Write-Warning "RStudio was not found in common locations. Install hint: winget install --id Posit.RStudio -e"
    }
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCmd) {
        Write-Host "git: $($gitCmd.Source)"
    } else {
        Write-Host "git: not found; zip fallback is enabled"
    }
    if ($ConfigureCodex -or $ConfigureClaudeCode -or $ConfigureCopilot) {
        Write-Host "uv: $((Get-Command uv).Source)"
        Write-Host "uvx: $((Get-Command uvx).Source)"
    }
}

function Get-GitValue($Arguments, $Fallback) {
    try {
        $value = & git -C $PSScriptRoot @Arguments 2>$null
        if ($LASTEXITCODE -eq 0 -and $value) { return (($value | Out-String).Trim()) }
    } catch {
        return $Fallback
    }
    return $Fallback
}

function Get-PackageVersion {
    $pyproject = Join-Path $PSScriptRoot "pyproject.toml"
    if (Test-Path -LiteralPath $pyproject) {
        $line = Select-String -LiteralPath $pyproject -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
        if ($line -and $line.Matches.Count -gt 0) {
            return $line.Matches[0].Groups[1].Value
        }
    }
    return "unknown"
}

function Get-WorkbenchSourceType {
    if (Test-Path -LiteralPath (Join-Path $PSScriptRoot ".git")) { return "git" }
    return "zip"
}

function Get-WorkbenchRef {
    if ((Get-WorkbenchSourceType) -eq "git") {
        $tag = Get-GitValue -Arguments @("describe", "--tags", "--exact-match") -Fallback ""
        if ($tag) { return $tag }
        return (Get-GitValue -Arguments @("rev-parse", "--abbrev-ref", "HEAD") -Fallback "unknown")
    }
    $version = Get-PackageVersion
    if ($version -ne "unknown") { return "v$version" }
    return "unknown"
}

function Get-WorkbenchSourceUrl {
    if ((Get-WorkbenchSourceType) -eq "git") {
        return (Get-GitValue -Arguments @("config", "--get", "remote.origin.url") -Fallback "")
    }
    $ref = Get-WorkbenchRef
    if ($ref -ne "unknown") {
        return "https://github.com/lzhs1995/clauder-rstudio-workbench/releases/download/$ref/clauder-rstudio-workbench-$ref.zip"
    }
    return ""
}

function Get-ConfiguredClients {
    $clients = @()
    if ($ConfigureCodex) { $clients += "codex" }
    if ($ConfigureClaudeCode) { $clients += "claude" }
    if ($ConfigureCopilot) { $clients += "copilot" }
    return @($clients)
}

function Write-InstallInfo($Dest) {
    $python = if ($SkipHarness) { "" } else { Find-HarnessPython }
    $wrapper = Join-Path $WorkbenchBinDir "clauder-workbench.cmd"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $pathParts = @()
    if ($userPath) {
        $pathParts = $userPath -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }
    $info = [ordered]@{
        schema_version = "0.2.4"
        git_commit = (Get-GitValue -Arguments @("rev-parse", "HEAD") -Fallback "unknown")
        git_branch_or_tag = (Get-GitValue -Arguments @("rev-parse", "--abbrev-ref", "HEAD") -Fallback "unknown")
        workbench_source_type = (Get-WorkbenchSourceType)
        workbench_ref = (Get-WorkbenchRef)
        workbench_source_url = (Get-WorkbenchSourceUrl)
        installed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        installed_from = $PSScriptRoot
        install_destination = $Dest
        harness_python = $python
        harness_wrapper = $wrapper
        add_harness_to_path = [bool]$AddHarnessToPath
        user_path_contains_wrapper_dir = [bool](($pathParts -contains $WorkbenchBinDir) -or $AddHarnessToPath)
        user_path_contains_wrapper_dir_before_install = [bool]($pathParts -contains $WorkbenchBinDir)
        configured_clients = @(Get-ConfiguredClients)
        claudeR_source_type = $script:ClaudeRSourceType
        claudeR_source_url = $script:ClaudeRSourceUrl
        claudeR_ref = $ClaudeRRef
        claudeR_commit = (Get-ClaudeRCommit)
        clauder_mcp_source = (Join-Path $ClaudeRDir "clauder-mcp")
        clauder_mcp_command = (Get-ClaudeRMcpExe)
        clauder_mcp_install_mode = "uv_tool_from_local_lzhs_fork"
        r_studio_startup_timeout_sec = 180.0
        uv_cache_dir = "C:\tmp\uv-cache"
        dev_sync = [bool]$DevSync
    }
    $path = Join-Path $Dest "INSTALL_INFO.json"
    $json = $info | ConvertTo-Json -Depth 5
    Write-Host "Writing install info -> $path"
    if (-not $DryRun) {
        Write-Utf8NoBom $path $json
    }
}

function Find-HarnessPython {
    if ($HarnessPython -and (Test-Path -LiteralPath $HarnessPython)) { return $HarnessPython }
    if ($env:CLAUDER_WORKBENCH_PYTHON -and (Test-Path -LiteralPath $env:CLAUDER_WORKBENCH_PYTHON)) {
        return $env:CLAUDER_WORKBENCH_PYTHON
    }
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    if ($InstallPython314) {
        Install-Python314
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Could not find Python for harness. Re-run with -HarnessPython <path>, set CLAUDER_WORKBENCH_PYTHON, or install Python 3.14 with: winget install --id Python.Python.3.14 --source winget -e"
}

function Install-Python314 {
    Write-Step "Installing Python 3.14"
    Require-Command "winget" "Install App Installer / winget first, or install Python 3.14 manually from python.org."
    $args = @("install", "--id", "Python.Python.3.14", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements", "-e")
    Write-Host "+ winget $($args -join ' ')" -ForegroundColor DarkGray
    if ($DryRun) { return }
    & winget @args
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.14 winget install failed with exit code ${LASTEXITCODE}."
    }
}

function Get-GitHubZipUrls($Repo, $Ref) {
    if ($Repo -match '^https://github\.com/([^/]+)/([^/.]+)(\.git)?/?$') {
        $owner = $Matches[1]
        $name = $Matches[2]
        return @(
            "https://github.com/$owner/$name/releases/download/$Ref/$name-$Ref.zip",
            "https://github.com/$owner/$name/archive/refs/tags/$Ref.zip"
        )
    }
    return @()
}

function Test-ClaudeRSource($Path) {
    return (Test-Path -LiteralPath (Join-Path $Path "DESCRIPTION")) -and (Test-Path -LiteralPath (Join-Path $Path "clauder-mcp"))
}

function Install-ClaudeRZipFallback($Reason) {
    if ($NoZipFallback) {
        throw "ClaudeR git install failed and -NoZipFallback is set. Original error: $Reason"
    }
    $zipUrls = @(Get-GitHubZipUrls $ClaudeRRepo $ClaudeRRef)
    if (-not $zipUrls) {
        throw "ClaudeR git install failed and zip fallback is unavailable for repo '$ClaudeRRepo'. Original error: $Reason"
    }
    Write-Warning "ClaudeR git install failed; using zip fallback. Original error: $Reason"
    $script:ClaudeRSourceType = "zip"
    $parent = Split-Path -Parent $ClaudeRDir
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $zip = Join-Path $env:TEMP "ClaudeR-$ClaudeRRef.zip"
    $extractRoot = Join-Path $env:TEMP "ClaudeR-$ClaudeRRef-$stamp"
    if ($DryRun) {
        Write-Host "Would try zip fallback URLs:"
        foreach ($candidateUrl in $zipUrls) { Write-Host "  $candidateUrl" }
        Write-Host "Would download first reachable URL -> $zip"
        Write-Host "Would extract zip to $extractRoot and install to $ClaudeRDir"
        return
    }
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $downloaded = $false
    $downloadErrors = @()
    foreach ($candidateUrl in $zipUrls) {
        Write-Host "Trying zip fallback URL: $candidateUrl"
        try {
            Invoke-WebRequest -Uri $candidateUrl -OutFile $zip
            $script:ClaudeRSourceUrl = $candidateUrl
            $downloaded = $true
            break
        } catch {
            $downloadErrors += "$candidateUrl -> $($_.Exception.Message)"
        }
    }
    if (-not $downloaded) {
        throw "All ClaudeR zip fallback URLs failed: $($downloadErrors -join '; ')"
    }
    if (Test-Path -LiteralPath $extractRoot) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
    Expand-Archive -LiteralPath $zip -DestinationPath $extractRoot -Force
    $source = Get-ChildItem -LiteralPath $extractRoot -Directory | Select-Object -First 1
    if (-not $source) {
        throw "ClaudeR zip fallback did not produce a source directory."
    }
    if (Test-Path -LiteralPath $ClaudeRDir) {
        $backup = "${ClaudeRDir}_bak_$stamp"
        Write-Host "Moving existing ClaudeR directory $ClaudeRDir -> $backup"
        Move-Item -LiteralPath $ClaudeRDir -Destination $backup -Force
    }
    Move-Item -LiteralPath $source.FullName -Destination $ClaudeRDir
    if (-not (Test-ClaudeRSource $ClaudeRDir)) {
        throw "ClaudeR zip fallback produced an invalid source directory: $ClaudeRDir"
    }
}

function Set-ClaudeRExistingSourceInfo {
    if (Test-Path -LiteralPath (Join-Path $ClaudeRDir ".git")) {
        $script:ClaudeRSourceType = "git"
        $script:ClaudeRSourceUrl = $ClaudeRDir
    } elseif (Test-Path -LiteralPath $ClaudeRDir) {
        $script:ClaudeRSourceType = "zip"
        $script:ClaudeRSourceUrl = $ClaudeRDir
    }
}


function Get-ClaudeRMcpExe {
    # Stable install path used by `uv tool install`. Prefer it over any PATH entry
    # so a stray PyPI/upstream `clauder-mcp` cannot shadow the lzhs fork install.
    $candidate = Join-Path $env:USERPROFILE ".local\bin\clauder-mcp.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    $cmd = Get-Command "clauder-mcp" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $candidate
}

function Get-ClaudeRCommit {
    if (Test-Path -LiteralPath (Join-Path $ClaudeRDir ".git")) {
        try {
            $value = & git -C $ClaudeRDir rev-parse HEAD 2>$null
            if ($LASTEXITCODE -eq 0 -and $value) { return (($value | Out-String).Trim()) }
        } catch { return "unknown" }
    }
    return "unknown"
}

function Install-ClaudeRMcpTool {
    Write-Step "Installing persistent ClaudeR MCP entry from lzhs fork"
    $bridge = Join-Path $ClaudeRDir "clauder-mcp"
    if (-not (Test-Path -LiteralPath (Join-Path $bridge "pyproject.toml"))) {
        throw "ClaudeR MCP bridge source missing or invalid: $bridge"
    }
    Require-Command "uv" "Install uv: winget install --id astral-sh.uv -e"
    $args = @("tool", "install", "--force", "--from", $bridge, "clauder-mcp")
    Write-Host "+ uv $($args -join ' ')" -ForegroundColor DarkGray
    if (-not $DryRun) {
        & uv @args
        if ($LASTEXITCODE -ne 0) {
            throw "uv tool install clauder-mcp failed with exit code ${LASTEXITCODE}."
        }
    }
    $exe = Get-ClaudeRMcpExe
    Write-Host "clauder-mcp persistent entry: $exe"
    return $exe
}

function Install-ClaudeR {
    Write-Step "Installing ClaudeR fork $ClaudeRRef"
    $parent = Split-Path -Parent $ClaudeRDir
    if (-not (Test-Path $parent) -and -not $DryRun) {
        New-Item -ItemType Directory -Force $parent | Out-Null
    }

    try {
        if (Test-Path $ClaudeRDir) {
            Invoke-Checked "git" @("-C", $ClaudeRDir, "fetch", "--tags", "origin")
            Invoke-Checked "git" @("-C", $ClaudeRDir, "checkout", $ClaudeRRef)
        } else {
            Invoke-Checked "git" @("clone", "--branch", $ClaudeRRef, $ClaudeRRepo, $ClaudeRDir)
        }
        if (-not (Test-ClaudeRSource $ClaudeRDir)) {
            throw "git command finished but ClaudeR source directory is invalid: $ClaudeRDir"
        }
        $script:ClaudeRSourceType = "git"
        $script:ClaudeRSourceUrl = $ClaudeRRepo
    } catch {
        Install-ClaudeRZipFallback $_.Exception.Message
    }

    $resolvedR = Find-RExe
    Invoke-Checked $resolvedR @("CMD", "INSTALL", $ClaudeRDir)
}

function Get-CollectionSkills {
    # A skill is any immediate subdirectory of skills\ that contains a SKILL.md.
    $skillsRoot = Join-Path $PSScriptRoot "skills"
    if (-not (Test-Path $skillsRoot)) { return @() }
    return @(Get-ChildItem -LiteralPath $skillsRoot -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName "SKILL.md") })
}

function Install-OneSkill($Source, $DestRoot, [switch]$WriteInfo) {
    $name = Split-Path -Leaf $Source
    $dest = Join-Path $DestRoot $name
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = "${dest}_bak_$stamp"
    $staging = "${dest}_staging_$stamp"
    $old = "${dest}_old_$stamp"

    if (-not (Test-Path $Source)) {
        throw "Skill source not found: $Source"
    }
    if (-not (Test-Path $DestRoot) -and -not $DryRun) {
        New-Item -ItemType Directory -Force $DestRoot | Out-Null
    }

    if ($DryRun) {
        if (Test-Path $dest) {
            Write-Host "Would copy backup $dest -> $backup"
            Write-Host "Would stage new skill $Source -> $staging"
            Write-Host "Would replace $dest with staged skill and keep backup"
        } else {
            Write-Host "Would stage and install $Source -> $dest"
        }
        return
    }

    try {
        Write-Host "Staging new skill $Source -> $staging"
        Copy-Item -LiteralPath $Source -Destination $staging -Recurse -Force

        if (Test-Path $dest) {
            Write-Host "Copying backup $dest -> $backup"
            Copy-Item -LiteralPath $dest -Destination $backup -Recurse -Force
            Rename-Item -LiteralPath $dest -NewName (Split-Path -Leaf $old)
        }

        Move-Item -LiteralPath $staging -Destination $dest

        if (Test-Path $old) {
            Remove-Item -LiteralPath $old -Recurse -Force
        }
        if ($WriteInfo) { Write-InstallInfo $dest }
        Write-Host "Installed skill to $dest"
    }
    catch {
        Write-Warning "Skill installation failed; attempting restore. Error: $($_.Exception.Message)"
        if (-not (Test-Path $dest)) {
            if (Test-Path $old) {
                Rename-Item -LiteralPath $old -NewName (Split-Path -Leaf $dest)
            } elseif (Test-Path $backup) {
                Copy-Item -LiteralPath $backup -Destination $dest -Recurse -Force
            }
        }
        throw
    }
    finally {
        if (Test-Path $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Install-Skill {
    Write-Step "Installing Codex skills"
    $destRoot = Join-Path $CodexHome "skills"
    $skills = Get-CollectionSkills
    if (-not $skills) { throw "No skills found under $(Join-Path $PSScriptRoot 'skills')" }
    foreach ($s in $skills) {
        # Write INSTALL_INFO.json only into the primary workbench skill.
        $writeInfo = ($s.Name -eq "clauder-rstudio-workbench")
        Install-OneSkill -Source $s.FullName -DestRoot $destRoot -WriteInfo:$writeInfo
    }
}

function Install-AgentsSkill {
    if (-not $SyncAgentsSkill) { return }
    Write-Step "Installing shared agents skills"
    $destRoot = Join-Path $AgentsHome "skills"
    $skills = Get-CollectionSkills
    if (-not $skills) { throw "No skills found under $(Join-Path $PSScriptRoot 'skills')" }
    foreach ($s in $skills) {
        $writeInfo = ($s.Name -eq "clauder-rstudio-workbench")
        Install-OneSkill -Source $s.FullName -DestRoot $destRoot -WriteInfo:$writeInfo
    }
}

function Install-Harness {
    if ($SkipHarness) {
        Write-Step "Skipping harness editable install"
        return
    }
    Write-Step "Installing harness package"
    $python = Find-HarnessPython
    $args = @("-m", "pip", "install", "--user", "-e", $PSScriptRoot)
    Write-Host "+ $python $($args -join ' ')" -ForegroundColor DarkGray
    if ($DryRun) { return }
    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Harness editable install failed with exit code ${LASTEXITCODE}."
    }
}

function Install-HarnessWrapper {
    if ($SkipHarness) {
        Write-Step "Skipping harness command wrapper"
        return
    }
    Write-Step "Installing harness command wrapper"
    $python = Find-HarnessPython
    $wrapper = Join-Path $WorkbenchBinDir "clauder-workbench.cmd"
    $content = @"
@echo off
"$python" -m clauder_workbench %*
"@
    Write-Host "Wrapper: $wrapper"
    if ($DryRun) {
        Write-Host "Would write clauder-workbench.cmd wrapper to $WorkbenchBinDir"
    } else {
        if (-not (Test-Path -LiteralPath $WorkbenchBinDir)) {
            New-Item -ItemType Directory -Force -Path $WorkbenchBinDir | Out-Null
        }
        Set-Content -LiteralPath $wrapper -Value $content -Encoding ASCII
    }

    if ($AddHarnessToPath) {
        Add-WorkbenchBinToUserPath $WorkbenchBinDir
    } else {
        Write-Host "PATH unchanged. Run with -AddHarnessToPath to add $WorkbenchBinDir to the user PATH."
        Write-Host "Portable fallback: $python -m clauder_workbench doctor"
    }
}

function Add-WorkbenchBinToUserPath($Dir) {
    Write-Step "Checking user PATH for harness wrapper"
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) {
        $parts = $current -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }
    if ($parts -contains $Dir) {
        Write-Host "User PATH already contains $Dir"
        return
    }
    $newPath = if ($current) { "$current;$Dir" } else { $Dir }
    Write-Host "Adding $Dir to user PATH"
    if ($DryRun) {
        Write-Host "Would set user PATH to: $newPath"
        return
    }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    if (-not (($env:Path -split ';') -contains $Dir)) {
        $env:Path = "$env:Path;$Dir"
    }
    Write-Host "User PATH updated. Restart terminals/agents for inherited PATH to refresh."
}

function Write-CodexConfig {
    Write-Step "Configuring Codex MCP"
    $configDir = Join-Path $CodexHome ""
    $config = Join-Path $CodexHome "config.toml"
    if (-not (Test-Path $configDir) -and -not $DryRun) {
        New-Item -ItemType Directory -Force $configDir | Out-Null
    }
    if (-not (Test-Path $config) -and -not $DryRun) {
        New-Item -ItemType File -Force $config | Out-Null
    }
    Backup-File $config

    $bridge = Join-Path $ClaudeRDir "clauder-mcp"
    $mcpExe = Get-ClaudeRMcpExe
    if (-not (Test-Path -LiteralPath $mcpExe) -and -not $DryRun) {
        $mcpExe = Install-ClaudeRMcpTool
    }
    $userProfile = $env:USERPROFILE
    $uvCacheDir = "C:\tmp\uv-cache"
    if (-not (Test-Path -LiteralPath $uvCacheDir) -and -not $DryRun) {
        New-Item -ItemType Directory -Force -Path $uvCacheDir | Out-Null
    }
    $block = @"
[mcp_servers.r-studio]
command = "$($mcpExe.Replace('\', '\\'))"
startup_timeout_sec = 180.0

[mcp_servers.r-studio.env]
USERPROFILE = "$($userProfile.Replace('\', '\\'))"
PYTHONIOENCODING = "utf-8"
NO_PROXY = "127.0.0.1,localhost"
UV_CACHE_DIR = "$($uvCacheDir.Replace('\', '\\'))"
"@

    Write-Host "Codex MCP block:"
    Write-Host $block
    if ($DryRun) { return }

    # v0.2.4: 用 UTF-8 安全读写，避免 PS 5.1 默认 ANSI/CP936 读取 + BOM 写入污染中文路径
    $content = Read-Utf8File $config
    $content = Remove-TomlSections $content @("mcp_servers.r-studio", "mcp_servers.r-studio.env")
    $content = $content.TrimEnd()
    if ($content) {
        $content = $content + "`r`n`r`n" + $block + "`r`n"
    } else {
        $content = $block + "`r`n"
    }
    Write-Utf8NoBom $config $content

    # v0.2.4: 写后 TOML 解析自检；fail 自动回滚备份
    if (-not (Test-TomlParseable $config)) {
        $restored = Restore-FromLatestBackup $config
        if ($restored) {
            throw "Codex config.toml write produced invalid TOML; restored from backup '$restored'. See guide 27.11 for root cause and manual recovery."
        } else {
            throw "Codex config.toml write produced invalid TOML and no backup found. Manual recovery required; see guide 27.11."
        }
    }
    Write-Host "Codex config.toml parse OK"
}

function Remove-TomlSections($Content, [string[]]$SectionNames) {
    if (-not $Content) { return "" }
    $lines = $Content -split "\r?\n"
    $out = New-Object System.Collections.Generic.List[string]
    $skip = $false

    foreach ($line in $lines) {
        if ($line -match '^\s*\[([^\]]+)\]\s*$') {
            $name = $Matches[1]
            $skip = $SectionNames -contains $name
            if (-not $skip) {
                $out.Add($line)
            }
            continue
        }

        if (-not $skip) {
            $out.Add($line)
        }
    }

    return (($out -join "`r`n").TrimEnd())
}

function Configure-ClaudeCode {
    Write-Step "Configuring Claude Code MCP"
    $claudeJson = Join-Path $env:USERPROFILE ".claude.json"
    Backup-File $claudeJson
    $mcpExe = Get-ClaudeRMcpExe
    $removeArgs = @(
        "mcp", "remove", "r-studio", "-s", "user"
    )
    Write-Host "+ claude $($removeArgs -join ' ')"
    if (-not $DryRun) {
        & claude @removeArgs | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Existing Claude Code r-studio MCP entry was not removed. Continuing with add."
        }
    }
    $addArgs = @(
        "mcp", "add", "--transport", "stdio", "--scope", "user",
        "-e", "USERPROFILE=$env:USERPROFILE",
        "-e", "PYTHONIOENCODING=utf-8",
        "-e", "NO_PROXY=127.0.0.1,localhost",
        "-e", "UV_CACHE_DIR=C:\tmp\uv-cache",
        "r-studio", "--", $mcpExe
    )
    Invoke-Checked "claude" $addArgs
    Verify-ClaudeCodeMcp
}

function Verify-ClaudeCodeMcp {
    if ($DryRun) { return }
    Write-Host "+ claude mcp list"
    $list = & claude mcp list 2>&1
    $exit = $LASTEXITCODE
    $list | Out-Host
    if ($exit -ne 0 -or -not (($list | Out-String) -match 'r-studio')) {
        throw "Claude Code MCP verification failed: r-studio was not found in 'claude mcp list'."
    }
}

function Write-CopilotConfig {
    Write-Step "Configuring GitHub Copilot MCP"
    $dir = Join-Path $env:USERPROFILE ".copilot"
    $config = Join-Path $dir "mcp-config.json"
    if (-not (Test-Path $dir) -and -not $DryRun) {
        New-Item -ItemType Directory -Force $dir | Out-Null
    }
    if (-not (Test-Path $config) -and -not $DryRun) {
        Write-Utf8NoBom $config "{}"
    }
    Backup-File $config

    $bridge = Join-Path $ClaudeRDir "clauder-mcp"
    $obj = [ordered]@{
        mcpServers = [ordered]@{
            "r-studio" = [ordered]@{
                type = "local"
                command = (Get-ClaudeRMcpExe)
                args = @()
                env = [ordered]@{
                    USERPROFILE = $env:USERPROFILE
                    PYTHONIOENCODING = "utf-8"
                    NO_PROXY = "127.0.0.1,localhost"
                    UV_CACHE_DIR = "C:\tmp\uv-cache"
                }
                tools = @("*")
            }
        }
    }
    $json = $obj | ConvertTo-Json -Depth 10
    Write-Host $json
    if (-not $DryRun) {
        Write-Utf8NoBom $config $json
    }
}

try {
    Test-Prerequisites
    if (-not ($DevSync -or $SkipClaudeR)) { Install-ClaudeR } else { Set-ClaudeRExistingSourceInfo; Write-Step "Skipping ClaudeR install" }
    if ($ConfigureCodex -or $ConfigureClaudeCode -or $ConfigureCopilot) { Install-ClaudeRMcpTool | Out-Null }
    Install-Skill
    Install-AgentsSkill
    Install-Harness
    Install-HarnessWrapper

    if ($ConfigureCodex) { Write-CodexConfig }
    if ($ConfigureClaudeCode) { Configure-ClaudeCode }
    if ($ConfigureCopilot) { Write-CopilotConfig }

    Write-Step "Done"
    Write-Host "Restart Codex/Claude/Copilot after MCP configuration changes."
    Write-Host "In RStudio, run: library(ClaudeR); claudeAddin()"
}
finally {
    if ($LogFile) {
        Stop-Transcript | Out-Null
    }
}
