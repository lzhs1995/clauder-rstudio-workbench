"""真实构包与隔离安装回归；不替换清单定位函数，不调用bridge或R。"""
import base64
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
import zipfile


class ManifestPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 可选保留本次构包、安装与子进程原始输出；普通测试使用独立临时目录。
        retained = os.environ.get('CLAUDER_PACKAGING_TEST_ROOT')
        if retained:
            cls.root = Path(retained).resolve()
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            temp = tempfile.TemporaryDirectory()
            cls.addClassCleanup(temp.cleanup)
            cls.root = Path(temp.name).resolve()
        cls.counter = 0
        cls.env = {k: v for k, v in os.environ.items()
                   if k not in ('PYTHONPATH', 'PYTHONHOME') and not k.startswith('CLAUDER_WORKBENCH_')}
        cls.env['PYTHONDONTWRITEBYTECODE'] = '1'
        cls.env['PYTHONNOUSERSITE'] = '1'
        cls.cwd = cls.root / 'empty-cwd'
        cls.cwd.mkdir()
        repo = Path(__file__).resolve().parents[1]
        cls.source = cls.root / 'build-source'
        cls.source.mkdir()
        for name in ('pyproject.toml', 'runtime-compatibility.json'):
            shutil.copyfile(repo / name, cls.source / name)
        cls.relative_package = Path('skills/clauder-rstudio-workbench/clauder_workbench')
        shutil.copytree(repo / cls.relative_package, cls.source / cls.relative_package,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        cls.manifest_bytes = (cls.source / 'runtime-compatibility.json').read_bytes()
        cls.manifest = json.loads(cls.manifest_bytes)
        wheels = cls.root / 'wheels'
        wheels.mkdir()
        cls.run_command([sys.executable, '-m', 'pip', '--isolated', 'wheel', '--no-index',
                         '--no-deps', '--no-build-isolation', '--disable-pip-version-check',
                         '--wheel-dir', str(wheels), str(cls.source)])
        wheel, = wheels.glob('*.whl')
        sdists = cls.root / 'sdist'
        sdists.mkdir()
        cls.run_command([sys.executable, '-c',
                         'import os; from setuptools.build_meta import build_sdist; '
                         f'os.chdir({str(cls.source)!r}); build_sdist({str(sdists)!r})'])
        sdist, = sdists.glob('*.tar.gz')
        rebuilt = cls.root / 'sdist-wheel'
        rebuilt.mkdir()
        cls.run_command([sys.executable, '-m', 'pip', '--isolated', 'wheel', '--no-index',
                         '--no-deps', '--no-build-isolation', '--disable-pip-version-check',
                         '--wheel-dir', str(rebuilt), str(sdist)])
        rebuilt_wheel, = rebuilt.glob('*.whl')
        for candidate in (wheel, rebuilt_wheel):
            with zipfile.ZipFile(candidate) as zf:
                member, = [n for n in zf.namelist()
                           if n.endswith('/share/clauder-rstudio-workbench/runtime-compatibility.json')]
                if zf.read(member) != cls.manifest_bytes:
                    raise AssertionError(f'Manifest bytes changed in {candidate}')
        cls.venv = cls.root / 'isolated'
        venv.EnvBuilder(with_pip=True).create(cls.venv)
        cls.python = cls.venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        cls.run_command([str(cls.python), '-m', 'pip', '--isolated', 'install', '--no-index',
                         '--no-deps', '--no-compile', '--disable-pip-version-check', str(rebuilt_wheel)])
        cls.hidden_source = cls.root / 'hidden-build-source'
        cls.source.rename(cls.hidden_source)
        cls.installed_manifest = cls.venv / 'share/clauder-rstudio-workbench/runtime-compatibility.json'
        cls.installed_package = Path(cls.probe()['module']).parent

    @classmethod
    def run_command(cls, argv, env=None):
        cls.counter += 1
        stem = cls.root / f'command-{cls.counter:02d}'
        stem.with_suffix('.argv.json').write_text(json.dumps(argv, indent=2))
        result = subprocess.run(argv, cwd=cls.cwd, env=env or cls.env,
                                capture_output=True, text=True, timeout=120)
        stem.with_suffix('.stdout').write_text(result.stdout)
        stem.with_suffix('.stderr').write_text(result.stderr)
        stem.with_suffix('.rc').write_text(str(result.returncode) + '\n')
        if result.returncode:
            raise AssertionError(f'{argv!r}\nrc={result.returncode}\n{result.stdout}\n{result.stderr}')
        return result.stdout

    @classmethod
    def probe(cls, *, import_root=None, config=None):
        # 子进程实际导入已安装/显式源码模块，调用真实locator与真实检查器。
        code = (
            'import json; from clauder_workbench import runtime_provenance as rp; '
            'm,p=rp.compatibility_manifest(); '
            'result={"module":rp.__file__,"manifest":m,"path":str(p) if p else None}; '
        )
        if config is not None:
            code += f'result["check"]=rp.inspect_client("claude", {str(config)!r}); '
        code += 'print(json.dumps(result))'
        env = cls.env.copy()
        if import_root is not None:
            env['PYTHONPATH'] = str(import_root)
        return json.loads(cls.run_command([str(cls.python), '-B', '-c', code], env))

    def bridge_config(self, version):
        # 文件检查使用独立bridge夹具；其Python/启动器绝不执行。
        root = self.root / self._testMethodName
        root.mkdir()
        scripts = root / ('Scripts' if os.name == 'nt' else 'bin')
        scripts.mkdir()
        python = scripts / ('python.exe' if os.name == 'nt' else 'python')
        python.touch()
        site = root / ('Lib/site-packages' if os.name == 'nt' else 'lib/python3.12/site-packages')
        package = site / 'clauder_mcp'
        package.mkdir(parents=True)
        source = root / 'bridge-source'
        (source / 'src/clauder_mcp').mkdir(parents=True)
        metadata = site / f'clauder_mcp-{version}.dist-info'
        metadata.mkdir()
        (metadata / 'METADATA').write_text(f'Name: clauder-mcp\nVersion: {version}\n')
        (metadata / 'direct_url.json').write_text(json.dumps({'url': source.as_uri()}))
        rows = []
        for name in ('__init__.py', 'server.py'):
            data = ('# synthetic bridge for packaging check: ' + name + '\n').encode()
            (package / name).write_bytes(data)
            (source / 'src/clauder_mcp' / name).write_bytes(data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
            rows.append(['clauder_mcp/' + name, 'sha256=' + digest, str(len(data))])
        launcher = scripts / ('clauder-mcp.exe' if os.name == 'nt' else 'clauder-mcp')
        launcher.write_bytes(b'MZfixture' if os.name == 'nt' else
                             f'#!{python}\nfrom clauder_mcp import main\n'.encode())
        digest = base64.urlsafe_b64encode(hashlib.sha256(launcher.read_bytes()).digest()).decode().rstrip('=')
        rows.append([os.path.relpath(launcher, site), 'sha256=' + digest, str(launcher.stat().st_size)])
        with (metadata / 'RECORD').open('w', newline='') as f:
            csv.writer(f).writerows(rows)
        config = root / 'config.json'
        config.write_text(json.dumps({'mcpServers': {'r-studio': {
            'command': str(launcher),
            'env': {'HOME': str(root), 'USERPROFILE': str(root), 'UV_CACHE_DIR': str(root / 'cache')}
        }}}))
        # 错误bridge自己的清单不能成为harness的期望值。
        (root / 'manifest.json').write_text(json.dumps({'mcp_bridge_version': version,
            'clauder_commit': 'untrusted-bridge', 'critical_file_sha256': {
                'clauder-mcp/src/clauder_mcp/server.py': hashlib.sha256((package / 'server.py').read_bytes()).hexdigest()}}))
        return config

    def source_skill(self):
        root = self.root / self._testMethodName
        skill = root / 'skills/clauder-rstudio-workbench'
        shutil.copytree(self.hidden_source / self.relative_package, skill / 'clauder_workbench')
        return root, skill

    def test_installed_manifest_without_build_source(self):
        self.assertFalse(self.source.exists())
        value = self.probe()
        self.assertEqual(Path(value['path']), self.installed_manifest)
        self.assertEqual(value['manifest'], self.manifest)
        self.assertEqual(self.installed_manifest.read_bytes(), self.manifest_bytes)
        self.assertTrue(Path(value['module']).is_relative_to(self.venv))

    def test_installed_package_ignores_neighbor_manifests(self):
        decoys = [self.installed_package.parent / 'runtime-compatibility.json',
                  self.installed_package.parent.parent.parent / 'runtime-compatibility.json']
        try:
            for p in decoys:
                p.write_text('{"mcp_bridge_version":"foreign-neighbor"}')
            self.assertEqual(self.probe()['manifest'], self.manifest)
        finally:
            for p in decoys:
                p.unlink()

    def test_installed_manifest_rejects_wrong_bridge_version(self):
        check = self.probe(config=self.bridge_config('0.0.1'))['check']
        self.assertEqual(check['runtime']['integrity'], 'PASS')
        self.assertFalse(check['ok'])
        self.assertEqual(check['reasons'], ['CONFIGURED_BRIDGE_DIFFERS_FROM_SOURCE_PAIR'])

    def test_installed_manifest_rejects_wrong_bridge_bytes(self):
        check = self.probe(config=self.bridge_config(self.manifest['mcp_bridge_version']))['check']
        self.assertEqual(check['runtime']['integrity'], 'PASS')
        self.assertFalse(check['ok'])
        self.assertEqual(check['reasons'], ['CONFIGURED_BRIDGE_DIFFERS_FROM_SOURCE_PAIR'])

    def test_missing_installed_manifest_warns(self):
        hidden = self.installed_manifest.with_suffix('.hidden')
        self.installed_manifest.rename(hidden)
        try:
            check = self.probe(config=self.bridge_config('0.0.1'))['check']
            self.assertTrue(check['ok'])
            self.assertEqual(check['warnings'], ['SOURCE_PAIR_MANIFEST_UNAVAILABLE'])
            self.assertNotIn('compatibility', check)
        finally:
            hidden.rename(self.installed_manifest)

    def test_source_and_skill_manifest_precedence(self):
        root, skill = self.source_skill()
        manifest = {'mcp_bridge_version': 'checkout', 'clauder_commit': 'checkout'}
        (root / 'runtime-compatibility.json').write_text(json.dumps(manifest))
        self.assertEqual(self.probe(import_root=skill)['manifest'], manifest)
        own = {'mcp_bridge_version': 'skill', 'clauder_commit': 'skill'}
        (skill / 'runtime-compatibility.json').write_text(json.dumps(own))
        self.assertEqual(self.probe(import_root=skill)['manifest'], own)

    def test_source_missing_manifest_cannot_borrow_prefix(self):
        _, skill = self.source_skill()
        self.assertTrue(self.installed_manifest.exists())
        self.assertIsNone(self.probe(import_root=skill)['manifest'])

    def test_external_pythonpath_cannot_borrow_prefix_or_parent(self):
        external = self.root / self._testMethodName
        shutil.copytree(self.hidden_source / self.relative_package, external / 'clauder_workbench')
        (external / 'runtime-compatibility.json').write_text(self.manifest_bytes.decode())
        self.assertIsNone(self.probe(import_root=external)['manifest'])

    def test_symlink_package_cannot_borrow_prefix(self):
        external = self.root / self._testMethodName / 'clauder_workbench'
        shutil.copytree(self.hidden_source / self.relative_package, external)
        saved = self.installed_package.with_name('saved_clauder_workbench')
        self.installed_package.rename(saved)
        try:
            try:
                self.installed_package.symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f'Host does not permit directory symlinks: {exc}')
            self.assertIsNone(self.probe()['manifest'])
        finally:
            if self.installed_package.is_symlink():
                self.installed_package.unlink()
            saved.rename(self.installed_package)


if __name__ == '__main__':
    unittest.main()
