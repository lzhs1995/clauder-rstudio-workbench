import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from clauder_workbench import cli, runtime_provenance as rp, session_bootstrap


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.venv = self.root / 'pair/venv'
        self.python = self.venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        self.python.parent.mkdir(parents=True)
        self.python.touch()
        self.site = self.venv / ('Lib/site-packages' if os.name == 'nt' else 'lib/python3.12/site-packages')
        self.pkg = self.site / 'clauder_mcp'
        self.pkg.mkdir(parents=True)
        self.source = self.root / 'source/clauder-mcp'
        (self.source / 'src/clauder_mcp').mkdir(parents=True)
        self.dist = self.site / 'clauder_mcp-9.0.dist-info'
        self.dist.mkdir()
        self.dist.joinpath('METADATA').write_text('Name: clauder-mcp\nVersion: 9.0\n')
        self.dist.joinpath('direct_url.json').write_text(json.dumps({'url': self.source.as_uri()}))
        rows = []
        for name in ['__init__.py', 'server.py']:
            raw = ('# fixture ' + name + '\n').encode()
            (self.pkg / name).write_bytes(raw)
            (self.source / 'src/clauder_mcp' / name).write_bytes(raw)
            rows.append(['clauder_mcp/' + name, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('='), str(len(raw))])
        with self.dist.joinpath('RECORD').open('w', newline='') as f:
            csv.writer(f).writerows(rows)
        self.launcher = self.python.with_name('clauder-mcp.exe') if os.name == 'nt' else self.root / 'clauder-mcp'
        if os.name == 'nt':
            self.launcher.write_bytes(b'MZfixture')
        else:
            self.launcher.write_text(f'#!{self.python}\nfrom clauder_mcp import main\n')
        self.register_dispatcher(self.launcher, self.dist, self.site)
        self.env = {'HOME': str(self.root), 'USERPROFILE': str(self.root), 'UV_CACHE_DIR': str(self.root / 'cache')}
        self.server = {'command': str(self.launcher), 'env': self.env, 'startup_timeout_sec': 180}
        self.manifest_path = self.root / 'runtime-compatibility.json'
        self.manifest = {'mcp_bridge_version': '9.0', 'clauder_commit': 'fixture', 'critical_file_sha256': {'clauder-mcp/src/clauder_mcp/server.py': rp.sha(self.pkg / 'server.py')}}
        self.manifest_path.write_text(json.dumps(self.manifest))
        patcher = patch.object(rp, 'compatibility_manifest', return_value=(self.manifest, self.manifest_path))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.paths = {}
        for client in rp.CLIENTS:
            p = self.root / (client + ('.toml' if client == 'codex' else '.json'))
            self.write_config(client, p)
            self.paths[client] = p

    def write_config(self, client, path):
        if client == 'codex':
            path.write_text('[mcp_servers.r-studio]\ncommand = ' + json.dumps(str(self.launcher)) + '\nstartup_timeout_sec = 180\n[mcp_servers.r-studio.env]\n' + '\n'.join(k + ' = ' + json.dumps(v) for k, v in self.env.items()))
        else:
            path.write_text(json.dumps({'mcpServers': {'r-studio': self.server}}))

    def register_dispatcher(self, dispatcher, dist, site):
        raw = dispatcher.read_bytes()
        digest = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
        with (dist / 'RECORD').open('a', newline='') as f:
            csv.writer(f).writerow([os.path.relpath(dispatcher, site), digest, str(len(raw))])

    def inspect(self, client='codex'):
        return rp.inspect_client(client, self.paths[client])

    def test_all_three_clients_own_configuration_without_codex_fallback(self):
        self.paths['codex'].write_text('invalid TOML [')
        self.assertFalse(self.inspect('codex')['ok'])
        for client in ['claude', 'copilot']:
            value = self.inspect(client)
            self.assertTrue(value['ok'], value)
            self.assertEqual(value['config_path'], str(self.paths[client]))
            self.assertEqual(value['loaded_mcp_server'], 'NOT_CHECKED')

    def test_source_only_info_does_not_claim_runtime(self):
        args = cli.build_parser().parse_args(['doctor', '--expect-client', 'claude', '--config-file', str(self.paths['claude'])])
        info = {'schema': 'three-skill-source-install-info-v1', 'runtime_installed': False}
        with patch.object(cli, '_load_install_info', return_value=(info, None)), patch.object(cli, 'emit', side_effect=lambda x: x):
            result = cli.cmd_doctor(args)
        self.assertEqual(result['decision'], 'PASS')
        self.assertFalse(result['extra']['install_info']['runtime_installed'])
        self.assertEqual(result['extra']['client_checks']['claude']['runtime']['version'], '9.0')

    def test_default_doctor_with_source_only_info_and_two_healthy_clients(self):
        args = cli.build_parser().parse_args(['doctor'])
        info = {'schema': 'three-skill-source-install-info-v1', 'configured_clients': []}
        def paths(client, explicit=None, cwd=None):
            return [self.paths[client]] if client != 'copilot' else [self.root / 'missing.json']
        with patch.dict(os.environ, {}, clear=True), patch.object(rp, 'client_paths', side_effect=paths), patch.object(cli, '_load_install_info', return_value=(info, None)), patch.object(cli, 'emit', side_effect=lambda x: x):
            result = cli.cmd_doctor(args)
        self.assertEqual(result['decision'], 'PASS')
        self.assertEqual(result['extra']['expected_clients'], ['codex', 'claude'])

    def test_missing_client_not_satisfied_by_another_client(self):
        self.paths['copilot'].write_text('{"mcpServers": {}}')
        self.assertEqual(self.inspect('copilot')['reasons'], ['R_STUDIO_CONFIG_MISSING'])
        self.assertTrue(self.inspect('codex')['ok'])

    def test_changed_installed_file_rejected(self):
        (self.pkg / 'server.py').write_text('# modified')
        self.assertEqual(self.inspect()['reasons'], ['INSTALLED_BRIDGE_RECORD_MISMATCH'])

    def test_changed_local_source_rejected(self):
        (self.source / 'src/clauder_mcp/server.py').write_text('# modified')
        self.assertEqual(self.inspect()['reasons'], ['INSTALLED_BRIDGE_SOURCE_MISMATCH'])

    def test_wrong_configured_version_rejected(self):
        self.dist.joinpath('METADATA').write_text('Version: 8.0\n')
        self.assertEqual(self.inspect()['reasons'], ['CONFIGURED_BRIDGE_DIFFERS_FROM_SOURCE_PAIR'])

    def test_timeout_boolean_and_disabled_client_rejected(self):
        self.paths['codex'].write_text(self.paths['codex'].read_text().replace('180', 'true'))
        self.assertEqual(self.inspect()['reasons'], ['CODEX_STARTUP_TIMEOUT_BELOW_180'])
        self.server['disabled'] = True
        self.write_config('claude', self.paths['claude'])
        self.assertEqual(self.inspect('claude')['reasons'], ['R_STUDIO_DISABLED_OR_INVALID'])

    def test_shell_override_selected_only_if_launcher_supports_it(self):
        self.launcher = self.root / 'clauder-mcp'
        self.server['command'] = str(self.launcher)
        self.launcher.write_text('#!/bin/sh\nset -eu\nPYTHON="${CLAUDER_WORKBENCH_MCP_PYTHON:-/missing/default/python}"\nexec "$PYTHON" -c \'from clauder_mcp import main; raise SystemExit(main())\' "$@"\n')
        self.env['CLAUDER_WORKBENCH_MCP_PYTHON'] = str(self.python)
        self.write_config('claude', self.paths['claude'])
        self.assertTrue(self.inspect('claude')['ok'])
        self.launcher.write_text('#!/bin/sh\nexec /missing/python "$@"\n')
        self.assertEqual(self.inspect('claude')['reasons'], ['BRIDGE_LAUNCHER_UNRECOGNIZED'])

    def test_windows_adjacent_python_and_library_layout(self):
        import shutil
        win = self.root / 'win'
        (win / 'Scripts').mkdir(parents=True)
        exe = win / 'Scripts/clauder-mcp.exe'
        exe.write_bytes(b'MZfixture')
        (win / 'Scripts/python.exe').touch()
        shutil.copytree(self.site, win / 'Lib/site-packages')
        self.register_dispatcher(exe, win / 'Lib/site-packages/clauder_mcp-9.0.dist-info', win / 'Lib/site-packages')
        with patch.object(rp.config, 'IS_WINDOWS', True):
            py, route = rp.bridge_python(exe, {'CLAUDER_WORKBENCH_MCP_PYTHON': '/must/not/use'})
            self.assertEqual(py, (win / 'Scripts/python.exe').resolve())
            self.assertEqual(rp.inspect_package(py, exe)['version'], '9.0')
            self.assertEqual(route, 'adjacent_windows_python')
            exe.write_bytes(b'MZchanged')
            with self.assertRaisesRegex(ValueError, 'BRIDGE_DISPATCHER_RECORD_MISMATCH'):
                rp.inspect_package(py, exe)

    def test_bootstrap_actual_client_and_unknown_native(self):
        self.paths['codex'].write_text('invalid')
        with patch.object(session_bootstrap, 'EVIDENCE_DIR', self.root / 'evidence'), redirect_stdout(io.StringIO()) as stdout:
            code = session_bootstrap.run(client='claude', config_file=self.paths['claude'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), {'continue': True})
        doc = json.loads(next((self.root / 'evidence').glob('*.json')).read_text())
        self.assertEqual(doc['agent'], 'claude')
        self.assertEqual(doc['extra']['native_registration'], 'UNKNOWN')

    def test_project_claude_config_and_explicit_override(self):
        project = self.root / 'project'
        cwd = project / 'nested'
        cwd.mkdir(parents=True)
        self.write_config('claude', project / '.mcp.json')
        with patch.dict(os.environ, {}, clear=True):
            server, path = rp.load_client('claude', cwd=cwd)
        self.assertEqual(path, (project / '.mcp.json').resolve())
        self.assertEqual(rp.load_client('claude', self.paths['claude'])[1], self.paths['claude'])

    def test_auto_detects_configured_clients_and_no_false_all_ready(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(rp, 'load_client', side_effect=lambda c: (_ for _ in ()).throw(ValueError('R_STUDIO_CONFIG_MISSING')) if c == 'copilot' else ({}, Path(c))):
            self.assertEqual(rp.select_clients('auto', {'configured_clients': []}), ['codex', 'claude'])
        self.assertEqual(rp.select_clients('all'), ['codex', 'claude', 'copilot'])

    def test_auto_keeps_malformed_configuration_as_failure(self):
        def load(client):
            if client == 'claude':
                raise json.JSONDecodeError('invalid fixture', '{', 1)
            if client == 'copilot':
                raise ValueError('R_STUDIO_CONFIG_MISSING')
            return {}, Path(client)
        with patch.dict(os.environ, {}, clear=True), patch.object(rp, 'load_client', side_effect=load):
            self.assertEqual(rp.select_clients('auto'), ['codex', 'claude'])

    def test_relative_python_override_rejected(self):
        with self.assertRaisesRegex(ValueError, 'BRIDGE_PYTHON_ABSOLUTE_PATH_REQUIRED'):
            rp.inspect_package('relative/bin/python')

    def test_missing_registered_module_rejected(self):
        (self.pkg / '__init__.py').unlink()
        self.assertEqual(self.inspect()['reasons'], ['INSTALLED_BRIDGE_FILE_SET_MISMATCH'])

    def test_toml_nan_and_both_infinite_timeouts_rejected(self):
        for value in ['nan', '+inf', '-inf']:
            with self.subTest(value=value):
                self.write_config('codex', self.paths['codex'])
                path = self.paths['codex']
                path.write_text(path.read_text().replace('startup_timeout_sec = 180', 'startup_timeout_sec = ' + value))
                self.assertEqual(self.inspect()['reasons'], ['CODEX_STARTUP_TIMEOUT_BELOW_180'])

    def test_editable_metadata_explicitly_rejected(self):
        self.dist.joinpath('direct_url.json').write_text(json.dumps({'url': self.source.as_uri(), 'dir_info': {'editable': True}}))
        self.assertEqual(self.inspect()['reasons'], ['EDITABLE_BRIDGE_NOT_SUPPORTED'])

    def test_missing_or_relative_cache_rejected(self):
        for value in [None, 'relative/cache']:
            if value is None:
                self.env.pop('UV_CACHE_DIR', None)
            else:
                self.env['UV_CACHE_DIR'] = value
            self.write_config('claude', self.paths['claude'])
            self.assertEqual(self.inspect('claude')['reasons'], ['EXPLICIT_ABSOLUTE_UV_CACHE_REQUIRED'])

    def test_tampered_recorded_dispatcher_rejected(self):
        self.launcher.write_bytes(self.launcher.read_bytes() + b'\n# changed dispatcher\n')
        self.assertEqual(self.inspect()['reasons'], ['BRIDGE_DISPATCHER_RECORD_MISMATCH'])

    def test_remote_source_url_is_not_local_provenance(self):
        self.dist.joinpath('direct_url.json').write_text('{"url":"https://example.invalid/pkg"}')
        self.assertEqual(self.inspect()['reasons'], ['LOCAL_SOURCE_PROVENANCE_MISSING'])

    def test_pair_receipt_for_different_install_is_rejected(self):
        receipt = {'status': 'STAGED_VERIFIED', 'verification': {'ok': True},
                   'installed_packages': {'bridge': {'root': str(self.root / 'other'), 'files': {}}}}
        (self.venv.parent / 'release.json').write_text(json.dumps(receipt))
        self.assertEqual(self.inspect()['reasons'], ['PAIRED_RECEIPT_LOCATION_MISMATCH'])


if __name__ == '__main__':
    unittest.main()
