"""Isolated regression tests: no global uv install, R process, or user config.

PowerShell cases load only the named installer function via its real AST.
They run under both Windows PowerShell 5.1 and PowerShell 7 in CI. A skipped
case on another host is not evidence of native Windows installation success.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from clauder_workbench import installer
from clauder_workbench.platform_runtime import resolve_runtime


class CandidateInstallationFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="clauder-full-upgrade-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "candidate workbench"
        self.source = self.root / "candidate ClaudeR"
        self.repo.mkdir()
        (self.repo / "skills").mkdir()
        (self.repo / "pyproject.toml").write_text(
            '[project]\nname="candidate-harness"\nversion="1.2.3"\n', encoding="utf-8")
        files = {
            "DESCRIPTION": b"Package: ClaudeR\nVersion: 1.2.3\n",
            "clauder-mcp/pyproject.toml": b'[project]\nname="clauder-mcp"\nversion="4.5.6"\n',
            "clauder-mcp/src/clauder_mcp/server.py": b"# paired candidate bridge\n",
        }
        for name, data in files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.manifest = {
            "clauder_ref": "synthetic-pair", "clauder_commit": "synthetic-commit",
            "critical_file_sha256": {
                name: hashlib.sha256(data).hexdigest() for name, data in files.items()
            },
        }
        (self.repo / "runtime-compatibility.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")
        self.runtime = resolve_runtime(environ={
            "HOME": str(self.root / "isolated home"),
            "USERPROFILE": str(self.root / "isolated home"),
            "LOCALAPPDATA": str(self.root / "isolated local"),
        })
        self.runtime.bridge_path.parent.mkdir(parents=True)
        self.runtime.bridge_path.write_bytes(b"existing bridge must not be reused as success\n")
        self.old_bytes = self.runtime.bridge_path.read_bytes()
        self.argv = ["--repo-root", str(self.repo), "--clauder-dir", str(self.source),
                     "--codex-home", str(self.root / "codex"),
                     "--agents-home", str(self.root / "agents"),
                     "--uv-cache-dir", str(self.root / "cache"),
                     "--skip-r-package", "--skip-harness", "--configure-codex"]

    def guards(self):
        stack = ExitStack()
        stack.enter_context(mock.patch.object(installer, "resolve_runtime", return_value=self.runtime))
        stack.enter_context(mock.patch.object(installer.shutil, "which", return_value="fixture-uv"))
        guarded = {name: stack.enter_context(mock.patch.object(installer, name)) for name in (
            "_run", "_install_stable_bridge_launcher", "_install_skill", "update_codex_config",
            "_write_install_info",
        )}
        return stack, guarded

    def assert_old_unchanged(self):
        self.assertEqual(self.runtime.bridge_path.read_bytes(), self.old_bytes)
        self.assertFalse((self.root / "codex").exists())
        self.assertFalse((self.root / "agents").exists())

    def test_non_ascii_powershell_files_have_utf8_bom(self):
        repo = Path(__file__).resolve().parents[1]
        files = [repo / "install.ps1", *(repo / ".github/scripts").glob("*.ps1"),
                 *(repo / "skills").rglob("*.ps1")]
        for path in files:
            with self.subTest(file=str(path.relative_to(repo))):
                raw = path.read_bytes()
                raw.decode("utf-8-sig")
                if any(byte >= 128 for byte in raw):
                    self.assertTrue(raw.startswith(b"\xef\xbb\xbf"),
                                    "PS5.1 may silently swallow statements when decoding non-ASCII UTF-8 without BOM")

    def test_stale_candidate_components_are_rejected_before_any_install(self):
        for name in self.manifest["critical_file_sha256"]:
            with self.subTest(component=name):
                path = self.source / name
                original = path.read_bytes()
                path.write_bytes(original + b"# older or mismatched candidate\n")
                try:
                    stack, guarded = self.guards()
                    with stack, self.assertRaisesRegex(SystemExit, "does not match"):
                        installer.main(self.argv)
                    for call in guarded.values():
                        call.assert_not_called()
                    self.assert_old_unchanged()
                finally:
                    path.write_bytes(original)

    def test_failed_bridge_install_cannot_fall_back_to_old_bridge_or_update_config(self):
        stack, guarded = self.guards()
        guarded["_run"].side_effect = subprocess.CalledProcessError(23, ["fixture-uv"])
        with stack, self.assertRaises(subprocess.CalledProcessError):
            installer.main(self.argv)
        guarded["_run"].assert_called_once()
        command = guarded["_run"].call_args.args[0]
        self.assertIn(str((self.source / "clauder-mcp").resolve()), command)
        self.assertEqual(command[-1], "clauder-mcp")
        for name, call in guarded.items():
            if name != "_run":
                call.assert_not_called()
        self.assert_old_unchanged()

    def test_missing_candidate_bridge_is_not_replaced_by_existing_runtime(self):
        shutil.rmtree(self.source / "clauder-mcp")  # owned synthetic fixture only
        stack, guarded = self.guards()
        with stack, self.assertRaisesRegex(SystemExit, "Invalid ClaudeR repository"):
            installer.main(self.argv)
        for call in guarded.values():
            call.assert_not_called()
        self.assert_old_unchanged()

    def test_windows_custom_bin_is_the_configured_entry(self):
        self.runtime = resolve_runtime(system="win32", environ={
            "USERPROFILE": str(self.root / "windows home"),
            "LOCALAPPDATA": str(self.root / "windows local"),
        })
        self.runtime.bridge_path.parent.mkdir(parents=True)
        self.runtime.bridge_path.write_bytes(self.old_bytes)
        tool_root = self.root / "custom uv tools"
        tool_bin = self.root / "custom uv bin"
        tool_bin.mkdir()
        actual_entry = tool_bin / "clauder-mcp.exe"
        actual_entry.write_bytes(b"new entry fixture, never executed")
        stack, guarded = self.guards()
        with stack, mock.patch.object(installer.subprocess, "check_output", side_effect=[
                str(tool_root), str(tool_bin)]), mock.patch(
                "clauder_workbench.runtime_install.verify_bridge", return_value={"ok": True}) as probe:
            self.assertEqual(installer.main(self.argv), 0)
        self.assertEqual(guarded["update_codex_config"].call_args.args[1], actual_entry)
        self.assertEqual(probe.call_args.args[1], tool_root / "clauder-mcp/Scripts/python.exe")
        guarded["_install_stable_bridge_launcher"].assert_not_called()
        self.assert_old_unchanged()

    def test_windows_missing_custom_entry_cannot_fall_back_to_old_default(self):
        self.runtime = resolve_runtime(system="win32", environ={
            "USERPROFILE": str(self.root / "windows home"),
            "LOCALAPPDATA": str(self.root / "windows local"),
        })
        self.runtime.bridge_path.parent.mkdir(parents=True)
        self.runtime.bridge_path.write_bytes(self.old_bytes)
        stack, guarded = self.guards()
        with stack, mock.patch.object(installer.subprocess, "check_output", side_effect=[
                str(self.root / "custom tools"), str(self.root / "missing custom bin")]), mock.patch(
                "clauder_workbench.runtime_install.verify_bridge", return_value={"ok": True}):
            with self.assertRaisesRegex(SystemExit, "entry point is missing"):
                installer.main(self.argv)
        guarded["update_codex_config"].assert_not_called()
        self.assert_old_unchanged()


class SkillInstallationRollbackTests(unittest.TestCase):
    def test_failed_staging_promotion_restores_original_skill_and_backup(self):
        with tempfile.TemporaryDirectory(prefix="clauder-full-upgrade-rollback-") as td:
            root = Path(td)
            source = root / "candidate" / "example-skill"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_bytes(b"new skill\n")
            destination_root = root / "installed"
            destination = destination_root / source.name
            destination.mkdir(parents=True)
            (destination / "SKILL.md").write_bytes(b"old skill\n")
            (destination / "owned.txt").write_bytes(b"old companion\n")
            original_rename = Path.rename

            def fail_staging(path, target):
                if path.name.startswith(".example-skill_staging_"):
                    raise OSError("injected candidate promotion failure")
                return original_rename(path, target)

            with mock.patch.object(Path, "rename", fail_staging):
                with self.assertRaisesRegex(OSError, "promotion failure"):
                    installer._install_skill(source, destination_root)
            self.assertEqual((destination / "SKILL.md").read_bytes(), b"old skill\n")
            self.assertEqual((destination / "owned.txt").read_bytes(), b"old companion\n")
            backups = list(destination_root.glob("example-skill_bak_*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "SKILL.md").read_bytes(), b"old skill\n")
            self.assertEqual((backups[0] / "owned.txt").read_bytes(), b"old companion\n")
            self.assertFalse(list(destination_root.glob(".example-skill_*")))


@unittest.skipUnless(os.name == "nt" and os.environ.get("CLAUDER_TEST_POWERSHELL"),
                     "requires an explicitly selected native Windows PowerShell in CI")
class WindowsInstallerFailureTests(unittest.TestCase):
    def _run_case(self, reject_source):
        shell = os.environ["CLAUDER_TEST_POWERSHELL"]
        self.assertIsNotNone(shutil.which(shell), f"required shell missing: {shell}")
        script = r'''
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne [int]$env:CLAUDER_TEST_POWERSHELL_MAJOR) {
    throw 'Wrong PowerShell version selected'
}
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($env:CLAUDER_TEST_INSTALLER, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Installer parser error' }
$functions = @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Install-ClaudeRMcpTool'}, $false))
if ($functions.Count -ne 1) { throw 'Expected exactly one bridge installer function' }
Invoke-Expression $functions[0].Extent.Text
$script:uvCalls = 0; $script:oldBridgeLookups = 0
function Write-Step { param($message) }
function Require-Command { param($name, $help) }
function Test-PairedSource { if ($env:CLAUDER_TEST_REJECT_SOURCE -eq 'yes') { throw 'TEST_PAIR_REJECTED' } }
function uv { $script:uvCalls++; $global:LASTEXITCODE = 23; 'TEST_INSTALL_FAILED' }
function Get-ClaudeRMcpExe { $script:oldBridgeLookups++; return $env:CLAUDER_TEST_OLD_BRIDGE }
$ClaudeRDir = $env:CLAUDER_TEST_SOURCE
$DryRun = $false
$caught = $null
try { Install-ClaudeRMcpTool | Out-Null } catch { $caught = $_.Exception.Message }
if (-not $caught) { throw 'A failed candidate was incorrectly reported as success' }
if ($env:CLAUDER_TEST_REJECT_SOURCE -eq 'yes') {
    if ($caught -notlike '*TEST_PAIR_REJECTED*' -or $script:uvCalls -ne 0) { throw 'Source refusal was bypassed' }
} else {
    if ($caught -notlike '*exit code 23*' -or $script:uvCalls -ne 1) { throw "Wrong install failure: $caught" }
}
if ($script:oldBridgeLookups -ne 0) { throw 'Old bridge lookup after failed candidate' }
Write-Output ('FULL_UPGRADE_FAILURE_REJECTED_PS_' + $PSVersionTable.PSVersion.Major)
'''
        with tempfile.TemporaryDirectory(prefix="clauder-full-upgrade-ps-") as td:
            root = Path(td)
            (root / "source" / "clauder-mcp").mkdir(parents=True)
            (root / "source" / "clauder-mcp" / "pyproject.toml").write_text(
                '[project]\nname="fixture"\nversion="9.9.9"\n', encoding="utf-8")
            old = root / "clauder-mcp.exe"
            old.write_bytes(b"old bridge fixture, never executed")
            runner = root / "failure.ps1"
            runner.write_text(script, encoding="utf-8")
            env = dict(os.environ, CLAUDER_TEST_INSTALLER=str(Path(__file__).resolve().parents[1] / "install.ps1"),
                       CLAUDER_TEST_SOURCE=str(root / "source"), CLAUDER_TEST_OLD_BRIDGE=str(old),
                       CLAUDER_TEST_REJECT_SOURCE="yes" if reject_source else "no")
            result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                     "-File", str(runner)], env=env, text=True,
                                    capture_output=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("FULL_UPGRADE_FAILURE_REJECTED_PS_", result.stdout)
            self.assertEqual(old.read_bytes(), b"old bridge fixture, never executed")

    def test_failed_uv_install_does_not_reuse_existing_bridge(self):
        self._run_case(False)

    def test_pair_mismatch_stops_before_uv(self):
        self._run_case(True)

    def _run_entry_binding_case(self, mode):
        shell = os.environ["CLAUDER_TEST_POWERSHELL"]
        script = r'''
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne [int]$env:CLAUDER_TEST_POWERSHELL_MAJOR) { throw 'Wrong PowerShell version selected' }
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($env:CLAUDER_TEST_INSTALLER, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Installer parser error' }
$functionSource = @()
foreach ($name in @('Get-ClaudeRMcpExe', 'Install-ClaudeRMcpTool', 'Write-ScopedMcpConfig')) {
    $functions = @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name}, $false))
    if ($functions.Count -ne 1) { throw "Missing function: $name" }
    $functionSource += $functions[0].Extent.Text
}
# A saved file retains PSScriptRoot; IEX strips that context from these functions.
$functionFile = Join-Path $env:CLAUDER_TEST_ROOT 'installer-functions.ps1'
[IO.File]::WriteAllText($functionFile, ($functionSource -join "`n"), [Text.UTF8Encoding]::new($true))
. $functionFile
$script:InstallerRoot = Split-Path -Parent $env:CLAUDER_TEST_INSTALLER
$script:VerifiedClaudeRMcpExe = $null
$script:configArgsSeen = $null
function Write-Step { param($message) }
function Require-Command { param($name, $help) }
function Test-PairedSource {}
function Invoke-Checked { param($command, $arguments) }
function Find-HarnessPython { 'fixture-python' }
function Get-WorkbenchUvCacheDir { Join-Path $env:CLAUDER_TEST_ROOT 'cache' }
function fixture-python { $script:configArgsSeen = @($args); $global:LASTEXITCODE = 0 }
function uv {
    $global:LASTEXITCODE = 0
    if ($args[1] -eq 'dir') {
        if ($args -contains '--bin') { $env:CLAUDER_TEST_BIN } else { $env:CLAUDER_TEST_TOOLS }
    } else { 'INJECTED_INSTALL_OK' }
}
$ClaudeRDir = $env:CLAUDER_TEST_SOURCE
$DryRun = $false; $ConfigureCodex = $true
$ConfigureClaudeCode = $false; $ConfigureCopilot = $false; $ConfigureWorkspaceMcp = $false
$candidate = Join-Path $env:CLAUDER_TEST_BIN 'clauder-mcp.exe'
# Windows TEMP 可含 RUNNER~1；入口回执使用 FileInfo.FullName 的规范路径。
$expectedCandidate = $null
if ($env:CLAUDER_TEST_MODE -ne 'missing') { $expectedCandidate = (Get-Item -LiteralPath $candidate).FullName }
$caught = $null
try { Install-ClaudeRMcpTool | Out-Null } catch { $caught = $_.Exception.Message }
if ($env:CLAUDER_TEST_MODE -eq 'missing') {
    if (-not $caught -or $caught -notlike '*entry point is missing*') { throw 'Missing candidate entry was accepted' }
} elseif ($caught) { throw $caught }
if ($env:CLAUDER_TEST_MODE -eq 'removed') { Remove-Item -LiteralPath $candidate }
if ($env:CLAUDER_TEST_MODE -ne 'present') {
    $refused = $false
    try { Write-ScopedMcpConfig 'codex' (Join-Path $env:CLAUDER_TEST_ROOT 'never-written.toml') } catch { $refused = $true }
    if (-not $refused -or $null -ne $script:configArgsSeen) { throw 'Stale default substituted for missing candidate' }
} else {
    $actualCandidate = Get-ClaudeRMcpExe
    if ($actualCandidate -ne $expectedCandidate) { throw "Verified entry was discarded after Out-Null: expected [$expectedCandidate], got [$actualCandidate]" }
    Write-ScopedMcpConfig 'codex' (Join-Path $env:CLAUDER_TEST_ROOT 'never-written.toml')
    $i = [Array]::IndexOf($script:configArgsSeen, '--command')
    if ($i -lt 0 -or $script:configArgsSeen[$i + 1] -ne $expectedCandidate) { throw 'Config writer did not receive verified custom entry' }
}
Write-Output ('FULL_UPGRADE_ENTRY_BINDING_OK_PS_' + $PSVersionTable.PSVersion.Major)
'''
        with tempfile.TemporaryDirectory(prefix="clauder-entry-binding-") as td:
            root = Path(td)
            source = root / "source" / "clauder-mcp"
            source.mkdir(parents=True)
            (source / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="9.9.9"\n')
            tool_bin = root / "custom uv bin"
            tool_bin.mkdir()
            if mode != "missing":
                (tool_bin / "clauder-mcp.exe").write_bytes(b"candidate fixture, never executed")
            home = root / "old home"
            old = home / ".local" / "bin" / "clauder-mcp.exe"
            old.parent.mkdir(parents=True)
            old.write_bytes(b"old fixture, never executed")
            runner = root / "binding.ps1"
            runner.write_text(script, encoding="utf-8")
            env = dict(os.environ, USERPROFILE=str(home), CLAUDER_TEST_ROOT=str(root),
                       CLAUDER_TEST_INSTALLER=str(Path(__file__).resolve().parents[1] / "install.ps1"),
                       CLAUDER_TEST_SOURCE=str(source.parent), CLAUDER_TEST_BIN=str(tool_bin),
                       CLAUDER_TEST_TOOLS=str(root / "custom uv tools"), CLAUDER_TEST_MODE=mode)
            result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                     "-File", str(runner)], env=env, text=True, capture_output=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("FULL_UPGRADE_ENTRY_BINDING_OK_PS_", result.stdout)
            self.assertEqual(old.read_bytes(), b"old fixture, never executed")
            self.assertFalse((root / "never-written.toml").exists())

    def test_custom_bin_survives_top_level_discard_and_reaches_config_writer(self):
        self._run_entry_binding_case("present")

    def test_missing_custom_bin_is_not_replaced_by_existing_default(self):
        self._run_entry_binding_case("missing")

    def test_removed_verified_entry_is_not_replaced_by_existing_default(self):
        self._run_entry_binding_case("removed")


if __name__ == "__main__":
    unittest.main()
