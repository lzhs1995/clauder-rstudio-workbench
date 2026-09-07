# Exercise actual installer functions in an isolated directory, including PS 5.1.
$ErrorActionPreference = "Stop"
$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$source = [System.IO.File]::ReadAllText((Join-Path $repo "install.ps1"), [System.Text.Encoding]::UTF8)
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw "Installer PowerShell parse failed" }
$names = @("Get-WorkbenchUvCacheDir", "Write-ScopedMcpConfig", "Write-CodexConfig", "Configure-ClaudeCode", "Write-CopilotConfig", "Write-WorkspaceMcpConfig")
foreach ($fn in $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)) {
    if ($names -contains $fn.Name) { Invoke-Expression $fn.Extent.Text }
}
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("clauder-config-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory $root | Out-Null
$priorProfile = $env:USERPROFILE
$priorLocal = $env:LOCALAPPDATA
$script:TestPython = (Get-Command python).Source
$script:InstallerRoot = $repo
$script:TestExe = Join-Path $root "clauder-mcp.exe"
function Find-HarnessPython { return $script:TestPython }
function Get-ClaudeRMcpExe { return $script:TestExe }
function Write-Step($message) { Write-Host $message }
$DryRun = $false
$ConfigureWorkspaceMcp = $true
try {
    $env:USERPROFILE = $root
    $env:LOCALAPPDATA = Join-Path $root "Local"
    $CodexHome = Join-Path $root ".codex"
    New-Item -ItemType Directory $CodexHome | Out-Null
    New-Item -ItemType Directory (Join-Path $root ".copilot") | Out-Null
    $WorkspaceMcpPath = Join-Path $root ".mcp.json"
    $codex = Join-Path $CodexHome "config.toml"
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $initial = "# user's comment`n[mcp_servers.other]`ncommand='other'`n[mcp_servers.r-studio]`ncommand='clauder-mcp.exe'`nargs=['--agent-id','preserved']`nenabled=false`nstartup_timeout_sec=240`n"
    [System.IO.File]::WriteAllText($codex, $initial, $utf8)
    foreach ($p in @((Join-Path $root ".claude.json"), (Join-Path $root ".copilot/mcp-config.json"), $WorkspaceMcpPath)) {
        [System.IO.File]::WriteAllText($p, '{"custom":1,"mcpServers":{"other":{"command":"other"}}}', $utf8)
    }
    Write-CodexConfig
    Configure-ClaudeCode
    Write-CopilotConfig
    Write-WorkspaceMcpConfig
    $before = [System.IO.File]::ReadAllText($codex, $utf8)
    Write-CodexConfig
    if ($before -cne [System.IO.File]::ReadAllText($codex, $utf8)) { throw "Not idempotent" }
    if (-not $before.Contains("# user's comment") -or -not $before.Contains("enabled=false") -or -not $before.Contains("startup_timeout_sec=240")) { throw "Custom Codex fields lost" }
    if ($before.StartsWith([char]0xfeff)) { throw "Unexpected BOM" }
    foreach ($p in @((Join-Path $root ".claude.json"), (Join-Path $root ".copilot/mcp-config.json"), $WorkspaceMcpPath)) {
        $doc = [System.IO.File]::ReadAllText($p, $utf8) | ConvertFrom-Json
        if ($doc.custom -ne 1 -or $doc.mcpServers.other.command -ne "other") { throw "Unrelated JSON settings lost" }
    }
    $workspace = [System.IO.File]::ReadAllText($WorkspaceMcpPath, $utf8) | ConvertFrom-Json
    if ($workspace.mcpServers.'r-studio'.type -ne "stdio") { throw "Workspace Claude transport is not stdio" }
    Write-Host "CONFIG_WRITERS_RUNTIME_OK PowerShell=$($PSVersionTable.PSVersion)"
} finally {
    $env:USERPROFILE = $priorProfile
    $env:LOCALAPPDATA = $priorLocal
    # Exact directory created and owned by this fixture only.
    Remove-Item -LiteralPath $root -Recurse -Force
}
