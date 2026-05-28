param(
    [string]$ClaudeRRepo = "https://github.com/lzhs1995/ClaudeR.git",
    [string]$ClaudeRRef = "v0.2.0-lzhs.1",
    [string]$ClaudeRDir = "$env:USERPROFILE\projects\ClaudeR",
    [string]$CodexHome = "$env:USERPROFILE\.codex",
    [string]$RExe = "",
    [switch]$ConfigureCodex,
    [switch]$ConfigureClaudeCode,
    [switch]$ConfigureCopilot,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked($Command, $Arguments) {
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

    if (-not (Test-Path $source)) {
        throw "Skill source not found: $source"
    }
    if (-not (Test-Path $destRoot) -and -not $DryRun) {
        New-Item -ItemType Directory -Force $destRoot | Out-Null
    }
    if (Test-Path $dest) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backup = "${dest}_bak_$stamp"
        Write-Host "Backing up existing skill $dest -> $backup"
        if (-not $DryRun) {
            Move-Item -LiteralPath $dest -Destination $backup
        }
    }
    Write-Host "Copying $source -> $dest"
    if (-not $DryRun) {
        Copy-Item -LiteralPath $source -Destination $dest -Recurse -Force
    }
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
    $content = [regex]::Replace($content, '(?ms)^\[mcp_servers\.r-studio(?:\.env)?\]\r?\n.*?(?=^\[|\z)', '')
    $content = $content.TrimEnd() + "`r`n`r`n" + $block + "`r`n"
    Set-Content -LiteralPath $config -Value $content -Encoding UTF8
}

function Configure-ClaudeCode {
    Write-Step "Configuring Claude Code MCP"
    $claudeJson = Join-Path $env:USERPROFILE ".claude.json"
    Backup-File $claudeJson
    $bridge = Join-Path $ClaudeRDir "clauder-mcp"
    $args = @(
        "mcp", "remove", "r-studio", "-s", "user"
    )
    Write-Host "+ claude $($args -join ' ')"
    if (-not $DryRun) { & claude @args | Out-Host }
    $addArgs = @(
        "mcp", "add", "--transport", "stdio", "--scope", "user",
        "-e", "USERPROFILE=$env:USERPROFILE",
        "-e", "PYTHONIOENCODING=utf-8",
        "-e", "NO_PROXY=127.0.0.1,localhost",
        "r-studio", "--", "uvx", "--from", $bridge, "clauder-mcp"
    )
    Invoke-Checked "claude" $addArgs
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

Install-ClaudeR
Install-Skill

if ($ConfigureCodex) { Write-CodexConfig }
if ($ConfigureClaudeCode) { Configure-ClaudeCode }
if ($ConfigureCopilot) { Write-CopilotConfig }

Write-Step "Done"
Write-Host "Restart Codex/Claude/Copilot after MCP configuration changes."
Write-Host "In RStudio, run: library(ClaudeR); claudeAddin()"
