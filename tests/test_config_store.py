from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import tomlkit
from clauder_workbench import config_store as store


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'config.toml'
        self.kw = dict(client='codex', command=self.root / 'clauder-mcp', home=self.root, cache=self.root / 'cache')

    def test_preserve_comment_custom_args_disabled_and_unrelated_tables(self):
        text = '''# user comment
[projects."/用户/项目"]
trust_level="trusted"
[mcp_servers.other]
command="other-server"
[mcp_servers."r-studio"]
command="/old/clauder-mcp"
args=["--agent-id", "custom"]
enabled=false
startup_timeout_sec=240
tool_timeout_sec=600
[mcp_servers."r-studio".env]
CUSTOM="unchanged"
NO_PROXY="internal.example"
'''
        self.path.write_text(text, encoding='utf-8')
        result = store.update_config(self.path, **self.kw)
        self.assertEqual(Path(result['backup']).read_text(), text)
        updated = self.path.read_text()
        self.assertIn('# user comment', updated)
        doc = tomlkit.parse(updated)
        entry = doc['mcp_servers']['r-studio']
        self.assertFalse(entry['enabled'])
        self.assertEqual(entry['args'], ['--agent-id', 'custom'])
        self.assertEqual(entry['startup_timeout_sec'], 240)
        self.assertEqual(entry['env']['CUSTOM'], 'unchanged')
        self.assertEqual(entry['env']['NO_PROXY'], 'internal.example,127.0.0.1,localhost')
        self.assertEqual(doc['mcp_servers']['other']['command'], 'other-server')
        self.assertEqual(doc['projects']['/用户/项目']['trust_level'], 'trusted')
        stat = self.path.stat().st_mtime_ns
        self.assertFalse(store.update_config(self.path, **self.kw)['changed'])
        self.assertEqual(stat, self.path.stat().st_mtime_ns)

    def test_uvx_migration_strips_only_launcher_args(self):
        self.path.write_text('[mcp_servers.r-studio]\ncommand="uvx"\nargs=["--from","/repo/clauder-mcp","clauder-mcp","--agent-id","mine"]\n')
        store.update_config(self.path, **self.kw)
        self.assertEqual(tomlkit.parse(self.path.read_text())['mcp_servers']['r-studio']['args'], ['--agent-id', 'mine'])

    def test_invalid_input_and_dry_run_do_not_modify(self):
        self.path.write_bytes(b'invalid = [')
        with self.assertRaises(Exception):
            store.update_config(self.path, **self.kw)
        self.assertEqual(self.path.read_bytes(), b'invalid = [')
        self.assertFalse(self.path.with_name('config.toml.clauder.lock').exists())
        self.path.write_bytes(b'')
        self.assertTrue(store.update_config(self.path, **self.kw, dry_run=True)['changed'])
        self.assertEqual(self.path.read_bytes(), b'')

    def test_lock_prevents_concurrent_writer_and_is_not_reclaimed(self):
        with store.config_lock(self.path):
            with self.assertRaises(FileExistsError):
                store.update_config(self.path, **self.kw)

    def test_external_change_detected_without_overwrite(self):
        original = b'[mcp_servers.other]\ncommand="old"\n'
        self.path.write_bytes(original)
        render = store.render_config
        def racing(*args, **kwargs):
            candidate = render(*args, **kwargs)
            self.path.write_bytes(b'# external writer\n')
            return candidate
        with mock.patch.object(store, 'render_config', side_effect=racing):
            with self.assertRaisesRegex(RuntimeError, 'CONFIG_CONFLICT'):
                store.update_config(self.path, **self.kw)
        self.assertEqual(self.path.read_bytes(), b'# external writer\n')

    def test_replace_failure_preserves_original(self):
        self.path.write_bytes(b'# original\n')
        with mock.patch.object(store.os, 'replace', side_effect=OSError('injected failure')):
            with self.assertRaises(OSError):
                store.update_config(self.path, **self.kw)
        self.assertEqual(self.path.read_bytes(), b'# original\n')

    def test_json_clients_preserve_other_servers_and_disabled(self):
        for client in ('claude', 'copilot'):
            with self.subTest(client=client):
                self.path.write_text(json.dumps({'custom': 1, 'mcpServers': {'other': {'command':'other'}, 'r-studio': {'disabled':True, 'env': {'CUSTOM': 'keep'}}}}))
                store.update_config(self.path, **{**self.kw, 'client':client}, windows=True)
                doc = json.loads(self.path.read_text())
                self.assertEqual(doc['custom'], 1)
                self.assertEqual(doc['mcpServers']['other'], {'command':'other'})
                entry=doc['mcpServers']['r-studio']
                self.assertTrue(entry['disabled'])
                self.assertEqual(entry['env']['USERPROFILE'], str(self.root))
                self.assertEqual(entry['env']['CUSTOM'], 'keep')

    def test_url_transport_refused(self):
        self.path.write_text('[mcp_servers.r-studio]\nurl="http://localhost:1"\n')
        with self.assertRaises(ValueError):
            store.update_config(self.path, **self.kw)


if __name__ == '__main__':
    unittest.main()
