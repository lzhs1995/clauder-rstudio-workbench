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
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

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
    throw "Could not find R.exe. Re-run with -RExe <path-to-R.exe>."
}

function Test-Prerequisites {
    Write-Step "Checking prerequisites"
    Require-Command "git" "Install Git for Windows: winget install --id Git.Git -e"

    if ($ConfigureCodex -or $ConfigureClaudeCode -or $ConfigureCopilot) {
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
    Write-Host "git: $((Get-Command git).Source)"
    if ($ConfigureCodex -or $ConfigureClaudeCode -or $ConfigureCopilot) {
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

function Write-InstallInfo($Dest) {
    $python = if ($SkipHarness) { "" } else { Find-HarnessPython }
    $wrapper = Join-Path $WorkbenchBinDir "clauder-workbench.cmd"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $pathParts = @()
    if ($userPath) {
        $pathParts = $userPath -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }
    $info = [ordered]@{
        schema_version = "0.2.2"
        git_commit = (Get-GitValue -Arguments @("rev-parse", "HEAD") -Fallback "unknown")
        git_branch_or_tag = (Get-GitValue -Arguments @("rev-parse", "--abbrev-ref", "HEAD") -Fallback "unknown")
        installed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        installed_from = $PSScriptRoot
        install_destination = $Dest
        harness_python = $python
        harness_wrapper = $wrapper
        add_harness_to_path = [bool]$AddHarnessToPath
        user_path_contains_wrapper_dir = [bool](($pathParts -contains $WorkbenchBinDir) -or $AddHarnessToPath)
        user_path_contains_wrapper_dir_before_install = [bool]($pathParts -contains $WorkbenchBinDir)
        claudeR_ref = $ClaudeRRef
        dev_sync = [bool]$DevSync
    }
    $path = Join-Path $Dest "INSTALL_INFO.json"
    $json = $info | ConvertTo-Json -Depth 5
    Write-Host "Writing install info -> $path"
    if (-not $DryRun) {
        Set-Content -LiteralPath $path -Value $json -Encoding UTF8
    }
}

function Find-HarnessPython {
    if ($HarnessPython -and (Test-Path -LiteralPath $HarnessPython)) { return $HarnessPython }
    if ($env:CLAUDER_WORKBENCH_PYTHON -and (Test-Path -LiteralPath $env:CLAUDER_WORKBENCH_PYTHON)) {
        return $env:CLAUDER_WORKBENCH_PYTHON
    }
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Could not find Python for harness. Re-run with -HarnessPython <path> or set CLAUDER_WORKBENCH_PYTHON."
}

function Install-ClaudeR {
    Write-Step "Installing ClaudeR fork $ClaudeRRef"
    $parent = Split-Path -Parent $ClaudeRDir
    if (-not (Test-Path $parent) -and -not $DryRun) {
        New-Item -ItemType Directory -Force $parent | Out-Null
    }

    if (Test-Path $ClaudeRDir) {
        Invoke-Checked "git" @("-C", $ClaudeRDir, "fetch", "--tags", "origin")
        Invoke-Checked "git" @("-C", $ClaudeRDir, "checkout", $ClaudeRRef)
    } else {
        Invoke-Checked "git" @("clone", "--branch", $ClaudeRRef, $ClaudeRRepo, $ClaudeRDir)
    }

    $resolvedR = Find-RExe
    Invoke-Checked $resolvedR @("CMD", "INSTALL", $ClaudeRDir)
}

function Install-Skill {
    Write-Step "Installing Codex skill"
    $source = Join-Path $PSScriptRoot "skills\clauder-rstudio-workbench"
    $destRoot = Join-Path $CodexHome "skills"
    $dest = Join-Path $destRoot "clauder-rstudio-workbench"
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = "${dest}_bak_$stamp"
    $staging = "${dest}_staging_$stamp"
    $old = "${dest}_old_$stamp"

    if (-not (Test-Path $source)) {
        throw "Skill source not found: $source"
    }
    if (-not (Test-Path $destRoot) -and -not $DryRun) {
        New-Item -ItemType Directory -Force $destRoot | Out-Null
    }

    if ($DryRun) {
        if (Test-Path $dest) {
            Write-Host "Would copy backup $dest -> $backup"
            Write-Host "Would stage new skill $source -> $staging"
            Write-Host "Would replace $dest with staged skill and keep backup"
        } else {
            Write-Host "Would stage and install $source -> $dest"
        }
        return
    }

    try {
        Write-Host "Staging new skill $source -> $staging"
        Copy-Item -LiteralPath $source -Destination $staging -Recurse -Force

        if (Test-Path $dest) {
            Write-Host "Copying backup $dest -> $backup"
            Copy-Item -LiteralPath $dest -Destination $backup -Recurse -Force
            Rename-Item -LiteralPath $dest -NewName (Split-Path -Leaf $old)
        }

        Move-Item -LiteralPath $staging -Destination $dest

        if (Test-Path $old) {
            Remove-Item -LiteralPath $old -Recurse -Force
        }
        Write-InstallInfo $dest
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

function Install-AgentsSkill {
    if (-not $SyncAgentsSkill) { return }
    Write-Step "Installing shared agents skill"
    $source = Join-Path $PSScriptRoot "skills\clauder-rstudio-workbench"
    $destRoot = Join-Path $AgentsHome "skills"
    $dest = Join-Path $destRoot "clauder-rstudio-workbench"
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup = "${dest}_bak_$stamp"
    $staging = "${dest}_staging_$stamp"
    $old = "${dest}_old_$stamp"

    if ($DryRun) {
        Write-Host "Would stage and install $source -> $dest"
        return
    }
    if (-not (Test-Path $destRoot)) {
        New-Item -ItemType Directory -Force $destRoot | Out-Null
    }
    try {
        Copy-Item -LiteralPath $source -Destination $staging -Recurse -Force
        if (Test-Path $dest) {
            Copy-Item -LiteralPath $dest -Destination $backup -Recurse -Force
            Rename-Item -LiteralPath $dest -NewName (Split-Path -Leaf $old)
        }
        Move-Item -LiteralPath $staging -Destination $dest
        if (Test-Path $old) {
            Remove-Item -LiteralPath $old -Recurse -Force
        }
        Write-InstallInfo $dest
        Write-Host "Installed shared agents skill to $dest"
    }
    finally {
        if (Test-Path $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
        }
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
    $userProfile = $env:USERPROFILE
    $block = @"
[mcp_servers.r-studio]
command = "uvx"
args = ["--from", "$($bridge.Replace('\', '\\'))", "clauder-mcp"]

[mcp_servers.r-studio.env]
USERPROFILE = "$($userProfile.Replace('\', '\\'))"
PYTHONIOENCODING = "utf-8"
NO_PROXY = "127.0.0.1,localhost"
"@

    Write-Host "Codex MCP block:"
    Write-Host $block
    if ($DryRun) { return }

    $content = if (Test-Path $config) { Get-Content -LiteralPath $config -Raw } else { "" }
    $content = Remove-TomlSections $content @("mcp_servers.r-studio", "mcp_servers.r-studio.env")
    $content = $content.TrimEnd()
    if ($content) {
        $content = $content + "`r`n`r`n" + $block + "`r`n"
    } else {
        $content = $block + "`r`n"
    }
    Set-Content -LiteralPath $config -Value $content -Encoding UTF8
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
    $bridge = Join-Path $ClaudeRDir "clauder-mcp"
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
        "r-studio", "--", "uvx", "--from", $bridge, "clauder-mcp"
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
        Set-Content -LiteralPath $config -Value "{}" -Encoding UTF8
    }
    Backup-File $config

    $bridge = Join-Path $ClaudeRDir "clauder-mcp"
    $obj = [ordered]@{
        mcpServers = [ordered]@{
            "r-studio" = [ordered]@{
                type = "local"
                command = "uvx"
                args = @("--from", $bridge, "clauder-mcp")
                env = [ordered]@{
                    USERPROFILE = $env:USERPROFILE
                    PYTHONIOENCODING = "utf-8"
                    NO_PROXY = "127.0.0.1,localhost"
                }
                tools = @("*")
            }
        }
    }
    $json = $obj | ConvertTo-Json -Depth 10
    Write-Host $json
    if (-not $DryRun) {
        Set-Content -LiteralPath $config -Value $json -Encoding UTF8
    }
}

try {
    Test-Prerequisites
    if (-not ($DevSync -or $SkipClaudeR)) { Install-ClaudeR } else { Write-Step "Skipping ClaudeR install" }
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
