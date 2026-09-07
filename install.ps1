param(
    [string]$ClaudeRRepo = "https://github.com/lzhs1995/ClaudeR.git",
    [string]$ClaudeRRef = "v0.14.1.9002-lzhs.1",
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
    [switch]$SyncClaudeRAlias,
    [string]$AgentsHome = "$env:USERPROFILE\.agents",
    [string]$HarnessPython = "",
    [string]$WorkbenchBinDir = "$env:USERPROFILE\bin",
    [switch]$AddHarnessToPath,
    [switch]$NoZipFallback,
    [switch]$InstallPython314,
    [switch]$SkipPrewarm,
    [int]$BackupRetention = 5,
    [switch]$RequirePrewarm,
    [int]$PrewarmTimeoutSec = 60,
    [switch]$ConfigureWorkspaceMcp,
    [string]$WorkspaceMcpPath = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$script:InstallerRoot = $PSScriptRoot
$script:ClaudeRSourceType = "unknown"
$script:ClaudeRSourceUrl = $ClaudeRRepo
$script:McpPrewarmResult = [ordered]@{
    attempted = $false
    decision = "not_run"
    exit_code = $null
    timeout_sec = $null
    command = ""
    output_tail = @()
}

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

    if ($ConfigureCodex -or $ConfigureClaudeCode -or $ConfigureCopilot -or $ConfigureWorkspaceMcp) {
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
        claudeR_ref_requested = $ClaudeRRef
        claudeR_commit = (Get-ClaudeRCommit)
        claudeR_head_commit = (Get-ClaudeRCommit)
        claudeR_git_origin = (Get-ClaudeRGitOrigin)
        clauder_mcp_source = (Join-Path $ClaudeRDir "clauder-mcp")
        clauder_mcp_command = (Get-ClaudeRMcpExe)
        clauder_mcp_install_mode = "uv_tool_from_local_lzhs_fork"
        clauder_mcp_install_from = (Join-Path $ClaudeRDir "clauder-mcp")
        clauder_mcp_exe_sha256 = (Get-FileSha256 (Get-ClaudeRMcpExe))
        recommended_r_studio_startup_timeout_sec = 180.0
        runtime_verification_scope = "source declarations and executable hash, not running namespaces"
        loaded_r_namespace = "NOT_CHECKED"
        loaded_mcp_server = "NOT_CHECKED"
        harness_install_mode = "packaged"
        uv_cache_dir = (Get-WorkbenchUvCacheDir)
        prewarm_result = $script:McpPrewarmResult
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

function Get-ClaudeRGitOrigin {
    if (Test-Path -LiteralPath (Join-Path $ClaudeRDir ".git")) {
        try {
            $value = & git -C $ClaudeRDir config --get remote.origin.url 2>$null
            if ($LASTEXITCODE -eq 0 -and $value) { return (($value | Out-String).Trim()) }
        } catch { return "unknown" }
    }
    return "unknown"
}

function Get-FileSha256($Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return "" }
    try {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    } catch {
        return ""
    }
}

function Install-ClaudeRMcpTool {
    Write-Step "Installing persistent ClaudeR MCP entry from lzhs fork"
    Test-PairedSource
    $bridge = Join-Path $ClaudeRDir "clauder-mcp"
    if (-not (Test-Path -LiteralPath (Join-Path $bridge "pyproject.toml"))) {
        throw "ClaudeR MCP bridge source missing or invalid: $bridge"
    }
    Require-Command "uv" "Install uv: winget install --id astral-sh.uv -e"
    $args = @("tool", "install", "--force", "--from", $bridge, "clauder-mcp")
    Write-Host "+ uv $($args -join ' ')" -ForegroundColor DarkGray
    if (-not $DryRun) {
        $oldErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $uvOutput = & uv @args 2>&1
            $uvExit = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $oldErrorActionPreference
        }
        if ($uvExit -ne 0) {
            $existing = Get-ClaudeRMcpExe
            if ($existing -and (Test-Path -LiteralPath $existing)) {
                Write-Warning "uv tool install clauder-mcp failed with exit code ${uvExit}; reusing existing persistent entry at $existing. This usually means the current agent MCP server has the exe open. Output: $($uvOutput | Out-String)"
                return $existing
            }
            throw "uv tool install clauder-mcp failed with exit code ${uvExit}. Output: $($uvOutput | Out-String)"
        }
        $uvOutput | Out-Host
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

    Test-PairedSource
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

function Get-SkillBackups($DestRoot, $SkillName) {
    if (-not (Test-Path -LiteralPath $DestRoot)) { return @() }
    return @(Get-ChildItem -LiteralPath $DestRoot -Directory -Filter "${SkillName}_bak_*" | Sort-Object LastWriteTime -Descending)
}

function Prune-SkillBackups($DestRoot, $SkillName) {
    if ($BackupRetention -lt 0) { throw "BackupRetention must be >= 0" }
    $backups = Get-SkillBackups $DestRoot $SkillName
    if ($BackupRetention -eq 0) {
        Write-Host "Backup retention disabled for $SkillName; existing backups: $($backups.Count)"
        return
    }
    $remove = @($backups | Select-Object -Skip $BackupRetention)
    if (-not $remove) { return }
    foreach ($b in $remove) {
        if ($DryRun) {
            Write-Host "Would remove old skill backup $($b.FullName)"
        } else {
            Write-Host "Removing old skill backup $($b.FullName)"
            Remove-Item -LiteralPath $b.FullName -Recurse -Force
        }
    }
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
            Prune-SkillBackups -DestRoot $DestRoot -SkillName $name
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
        Prune-SkillBackups -DestRoot $DestRoot -SkillName $name
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
        Write-Step "Skipping harness package install"
        return
    }
    Write-Step "Installing harness package"
    $python = Find-HarnessPython
    $args = @("-m", "pip", "install", "--user", $PSScriptRoot)
    Write-Host "+ $python $($args -join ' ')" -ForegroundColor DarkGray
    if ($DryRun) { return }
    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Harness package install failed with exit code ${LASTEXITCODE}."
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

function Invoke-McpPrewarm {
    if ($SkipPrewarm) {
        $script:McpPrewarmResult = [ordered]@{
            attempted = $false
            decision = "skipped"
            exit_code = $null
            timeout_sec = $PrewarmTimeoutSec
            command = ""
            output_tail = @("Skipped by -SkipPrewarm")
        }
        return
    }
    if (-not ($ConfigureCodex -or $ConfigureClaudeCode -or $ConfigureCopilot -or $ConfigureWorkspaceMcp)) {
        return
    }
    Write-Step "Prewarming ClaudeR MCP persistent entry"
    $python = Find-HarnessPython
    $cmd = "$python -m clauder_workbench tool-surface --timeout $PrewarmTimeoutSec"
    Write-Host "+ $cmd" -ForegroundColor DarkGray
    if ($DryRun) {
        $script:McpPrewarmResult = [ordered]@{
            attempted = $true
            decision = "dry_run"
            exit_code = 0
            timeout_sec = $PrewarmTimeoutSec
            command = $cmd
            output_tail = @("Dry run: would prewarm MCP tool surface")
        }
        return
    }
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $python -m clauder_workbench tool-surface --timeout $PrewarmTimeoutSec 2>&1
        $exit = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
    $tail = @($output | Select-Object -Last 20 | ForEach-Object { "$_" })
    $decision = if ($exit -eq 0) { "PASS" } else { "WARN" }
    $script:McpPrewarmResult = [ordered]@{
        attempted = $true
        decision = $decision
        exit_code = $exit
        timeout_sec = $PrewarmTimeoutSec
        command = $cmd
        output_tail = $tail
    }
    $tail | Out-Host
    if ($exit -ne 0) {
        $msg = "MCP prewarm did not pass (exit=$exit). Persistent entry remains installed; run doctor/native-smoke before long jobs."
        if ($RequirePrewarm) {
            throw $msg
        }
        Write-Warning $msg
    }
}

function Refresh-InstallInfo {
    $targets = @()
    $codexSkill = Join-Path $CodexHome "skills\clauder-rstudio-workbench"
    if (Test-Path -LiteralPath $codexSkill) { $targets += $codexSkill }
    $agentsSkill = Join-Path $AgentsHome "skills\clauder-rstudio-workbench"
    if ($SyncAgentsSkill -and (Test-Path -LiteralPath $agentsSkill)) { $targets += $agentsSkill }
    foreach ($target in $targets) {
        Write-InstallInfo $target
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

function Get-WorkbenchUvCacheDir {
    $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $env:USERPROFILE "AppData\Local" }
    return (Join-Path $base "uv\cache")
}

function Test-PairedSource {
    if ($DryRun) { return }
    $manifest = Join-Path $script:InstallerRoot "runtime-compatibility.json"
    if (-not (Test-Path -LiteralPath $manifest)) { throw "Missing published runtime-compatibility.json" }
    $py = Find-HarnessPython
    $priorPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = Join-Path $script:InstallerRoot "skills\clauder-rstudio-workbench"
    try {
        & $py -m clauder_workbench.compatibility --manifest $manifest --source $ClaudeRDir | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "ClaudeR source does not match the published pair; runtime was not changed" }
    } finally {
        $env:PYTHONPATH = $priorPythonPath
    }
}

function Write-ScopedMcpConfig([string]$Client, [string]$Path) {
    # 共用 Python 原子合并器；不删除整段配置，不调用 Claude，不覆盖其它 MCP。
    $py = Find-HarnessPython
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = Join-Path $script:InstallerRoot "skills\clauder-rstudio-workbench"
    try {
        $configArgs = @("-m", "clauder_workbench.config_store", "--client", $Client,
            "--path", $Path, "--command", (Get-ClaudeRMcpExe),
            "--home", $env:USERPROFILE, "--cache", (Get-WorkbenchUvCacheDir))
        if ($DryRun) { $configArgs += "--dry-run" }
        & $py @configArgs | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "Scoped MCP update blocked. Preserve the configuration and private backup; no rollback over external changes."
        }
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }
}

function Write-CodexConfig {
    Write-Step "Configuring Codex MCP (atomic scoped merge)"
    Write-ScopedMcpConfig "codex" (Join-Path $CodexHome "config.toml")
}

function Configure-ClaudeCode {
    Write-Step "Configuring Claude Code MCP (user file only; no Claude process launch)"
    Write-ScopedMcpConfig "claude" (Join-Path $env:USERPROFILE ".claude.json")
}

function Write-CopilotConfig {
    Write-Step "Configuring GitHub Copilot MCP (preserve other servers)"
    Write-ScopedMcpConfig "copilot" (Join-Path $env:USERPROFILE ".copilot\mcp-config.json")
}

function Write-WorkspaceMcpConfig {
    if (-not $ConfigureWorkspaceMcp) { return }
    $target = $WorkspaceMcpPath
    if (-not $target) { $target = Join-Path (Get-Location) ".mcp.json" }
    Write-ScopedMcpConfig "claude" $target
}

try {
    Test-Prerequisites
    if (-not ($DevSync -or $SkipClaudeR)) { Install-ClaudeR } else { Set-ClaudeRExistingSourceInfo; Write-Step "Skipping ClaudeR install" }
    if ($ConfigureCodex -or $ConfigureClaudeCode -or $ConfigureCopilot -or $ConfigureWorkspaceMcp) { Install-ClaudeRMcpTool | Out-Null }
    Install-Skill
    if ($SyncClaudeRAlias) {
        Install-OneSkill -Source (Join-Path $PSScriptRoot "adapters\clauder") -DestRoot (Join-Path $CodexHome "skills")
    }
    Install-AgentsSkill
    Install-Harness
    Install-HarnessWrapper

    if ($ConfigureCodex) { Write-CodexConfig }
    if ($ConfigureClaudeCode) { Configure-ClaudeCode }
    if ($ConfigureCopilot) { Write-CopilotConfig }
    if ($ConfigureWorkspaceMcp) { Write-WorkspaceMcpConfig }
    Invoke-McpPrewarm
    Refresh-InstallInfo

    Write-Step "Done"
    Write-Host "Verify with ensure-ready --client <client> --session-name <target>. Configuration is not native-tool proof."
    Write-Host "Keep existing RStudio sessions alive. Use a supported targeted MCP reload only if the loaded bridge is stale."
}
finally {
    if ($LogFile) {
        Stop-Transcript | Out-Null
    }
}
