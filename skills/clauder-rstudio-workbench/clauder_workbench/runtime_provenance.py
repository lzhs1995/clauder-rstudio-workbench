"""按客户端读取配置与磁盘运行时；源码登记永远不是安装或加载证明。"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import sysconfig
from urllib.parse import unquote, urlparse

from . import config

CLIENTS = ('codex', 'claude', 'copilot')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def client_paths(client, explicit=None, cwd=None):
    """显式文件最优先；Claude按当前项目逐层找项目配置，最后用户配置。"""
    if explicit:
        return [Path(explicit)]
    if client == 'codex':
        return [config.CODEX_CONFIG]
    if client == 'copilot':
        return [config.COPILOT_CONFIG]
    if os.environ.get('CLAUDER_WORKBENCH_CLAUDE_JSON'):
        return [config.CLAUDE_JSON]
    current = Path(cwd or Path.cwd()).resolve()
    return [p / '.mcp.json' for p in (current, *current.parents)] + [config.CLAUDE_JSON]


def load_client(client, explicit=None, cwd=None):
    paths = client_paths(client, explicit, cwd)
    for path in paths:
        if not path.is_file():
            continue
        raw = path.read_text(encoding='utf-8-sig')
        if client == 'codex':
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            servers = tomllib.loads(raw).get('mcp_servers', {})
        else:
            servers = json.loads(raw).get('mcpServers', {})
        if 'r-studio' in servers:
            return servers['r-studio'], path
    raise ValueError('R_STUDIO_CONFIG_MISSING')


def select_clients(requested, install_info=None):
    if requested == 'all':
        return list(CLIENTS)
    if requested != 'auto':
        return [requested]
    # 明确调用上下文优先；不能用Codex配置替代其他客户端。
    current = os.environ.get('CLAUDER_WORKBENCH_AGENT') or os.environ.get('AGENT_NAME')
    if current in CLIENTS:
        return [current]
    declared = (install_info or {}).get('configured_clients') or []
    if isinstance(declared, str):
        declared = [declared]
    selected = [c for c in declared if c in CLIENTS]
    if selected:
        return list(dict.fromkeys(selected))
    for client in CLIENTS:
        try:
            load_client(client)
        except ValueError as exc:
            if type(exc) is ValueError and str(exc) == 'R_STUDIO_CONFIG_MISSING':
                continue
            # 解析错误属于实际坏配置，不能在auto列表中静默排除。
        except Exception:
            pass
        selected.append(client)
    return selected or ['codex']


def bridge_python(command, env):
    """只识别受支持启动器形态；不执行配置命令、不猜任意shell包装器。"""
    command = Path(command).resolve()
    if command.name.lower() == 'clauder-mcp.exe':
        python = command.with_name('python.exe')
        if not python.is_file():
            raise ValueError('BRIDGE_PYTHON_UNRESOLVED')
        return python, 'adjacent_windows_python'
    raw = command.read_text(encoding='utf-8')
    shell = re.fullmatch(r'#!/bin/sh\nset -eu\nPYTHON="\$\{CLAUDER_WORKBENCH_MCP_PYTHON:-([^}\n]+)\}"\nexec "\$PYTHON" -c \'from clauder_mcp import main; raise SystemExit\(main\(\)\)\' "\$@"\n', raw)
    if shell:
        return Path(env.get('CLAUDER_WORKBENCH_MCP_PYTHON') or shell.group(1)), 'stable_shell_override' if env.get('CLAUDER_WORKBENCH_MCP_PYTHON') else 'stable_shell_default'
    first = raw.splitlines()[0] if raw else ''
    if first.startswith('#!/') and 'from clauder_mcp import main' in raw:
        return Path(first[2:]), 'console_script_shebang'
    raise ValueError('BRIDGE_LAUNCHER_UNRECOGNIZED')


def inspect_package(python, dispatcher=None):
    python = Path(python)
    if not python.is_absolute():
        raise ValueError('BRIDGE_PYTHON_ABSOLUTE_PATH_REQUIRED')
    if not python.is_file():
        raise ValueError('BRIDGE_PYTHON_MISSING')
    venv = python.parent.parent
    roots = [venv / 'Lib/site-packages'] + sorted((venv / 'lib').glob('python*/site-packages'))
    matches = [p for root in roots for p in root.glob('clauder_mcp-*.dist-info')]
    if len(matches) != 1:
        raise ValueError('BRIDGE_DISTRIBUTION_MISSING_OR_AMBIGUOUS')
    dist = matches[0]
    site = dist.parent
    metadata = (dist / 'METADATA').read_text()
    version = re.search(r'^Version: (.+)$', metadata, re.M)
    if not version:
        raise ValueError('BRIDGE_VERSION_MISSING')
    direct = json.loads((dist / 'direct_url.json').read_text())
    if direct.get('dir_info', {}).get('editable') is True:
        raise ValueError('EDITABLE_BRIDGE_NOT_SUPPORTED')
    url = urlparse(direct.get('url', ''))
    if url.scheme != 'file' or url.netloc not in ('', 'localhost'):
        raise ValueError('LOCAL_SOURCE_PROVENANCE_MISSING')
    source_text = unquote(url.path)
    if config.IS_WINDOWS and re.match(r'^/[A-Za-z]:/', source_text):
        source_text = source_text[1:]
    source = Path(source_text)
    if not source.is_dir():
        raise ValueError('LOCAL_SOURCE_MISSING')
    records = {}
    with (dist / 'RECORD').open(newline='') as f:
        for name, digest, size in csv.reader(f):
            records[name] = (digest, size)
    if dispatcher is not None:
        dispatcher = Path(dispatcher).resolve()
        entries = [(digest, size) for name, (digest, size) in records.items()
                   if (site / name).resolve() == dispatcher]
        digest = 'sha256=' + base64.urlsafe_b64encode(bytes.fromhex(sha(dispatcher))).decode().rstrip('=')
        if len(entries) != 1 or entries[0] != (digest, str(dispatcher.stat().st_size)):
            raise ValueError('BRIDGE_DISPATCHER_RECORD_MISMATCH')
    registered = {name for name in records if name.startswith('clauder_mcp/') and name.endswith('.py')}
    actual_files = {p.relative_to(site).as_posix() for p in (site / 'clauder_mcp').rglob('*.py')}
    if registered != actual_files or not {'clauder_mcp/__init__.py', 'clauder_mcp/server.py'} <= registered:
        raise ValueError('INSTALLED_BRIDGE_FILE_SET_MISMATCH')
    files = []
    for p in sorted((site / 'clauder_mcp').rglob('*.py')):
        rel = p.relative_to(site).as_posix()
        digest, size = records.get(rel, ('', ''))
        actual = sha(p)
        encoded = base64.urlsafe_b64encode(bytes.fromhex(actual)).decode().rstrip('=')
        if digest != 'sha256=' + encoded or size != str(p.stat().st_size):
            raise ValueError('INSTALLED_BRIDGE_RECORD_MISMATCH')
        original = source / 'src' / rel
        if not original.is_file() or sha(original) != actual:
            raise ValueError('INSTALLED_BRIDGE_SOURCE_MISMATCH')
        files.append({'path': str(p), 'relative': rel, 'sha256': actual})
    if not any(p['relative'] == 'clauder_mcp/server.py' for p in files):
        raise ValueError('INSTALLED_BRIDGE_SERVER_MISSING')
    result = {'version': version.group(1), 'python': str(python), 'source': str(source),
              'metadata_path': str(dist), 'direct_url_sha256': sha(dist / 'direct_url.json'),
              'record_sha256': sha(dist / 'RECORD'), 'files': files, 'integrity': 'PASS'}
    receipt_path = venv.parent / 'release.json'
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        installed = receipt['installed_packages']['bridge']
        if receipt.get('status') != 'STAGED_VERIFIED' or not receipt.get('verification', {}).get('ok'):
            raise ValueError('PAIRED_RECEIPT_NOT_VERIFIED')
        if Path(installed['root']).resolve() != (site / 'clauder_mcp').resolve():
            raise ValueError('PAIRED_RECEIPT_LOCATION_MISMATCH')
        for name, expected in installed['files'].items():
            if sha(Path(installed['root']) / name) != expected:
                raise ValueError('PAIRED_RECEIPT_FILE_MISMATCH')
        result['pair_receipt'] = {'path': str(receipt_path), 'sha256': sha(receipt_path),
                                  'scope': receipt.get('verification', {}).get('scope'),
                                  'manifest_sha256': receipt.get('manifest_sha256')}
    return result


def compatibility_manifest():
    # 期望清单必须属于本次执行的harness；源码不能借用另一安装的清单。
    package = Path(__file__).resolve().parent
    installed_roots = {Path(sysconfig.get_path(key)).resolve() for key in ('purelib', 'platlib')}
    if package.name == 'clauder_workbench' and package.parent in installed_roots:
        candidates = [Path(sys.prefix) / 'share' / 'clauder-rstudio-workbench' / 'runtime-compatibility.json']
    elif package.name == 'clauder_workbench' and package.parent.name == 'clauder-rstudio-workbench':
        skill = package.parent
        candidates = [skill / 'runtime-compatibility.json']
        if skill.parent.name == 'skills':
            candidates.append(skill.parent.parent / 'runtime-compatibility.json')
    else:
        candidates = []
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text()), path
    return None, None


def inspect_client(client, explicit=None, cwd=None):
    result = {'client': client, 'ok': False, 'warnings': [], 'reasons': [],
              'scope': 'configured_files_and_installed_bridge_only',
              'loaded_mcp_server': 'NOT_CHECKED', 'loaded_r_namespace': 'NOT_CHECKED',
              'agent_native_tools': 'NOT_CHECKED'}
    try:
        server, path = load_client(client, explicit, cwd)
        result['config_path'] = str(path)
        result['config_sha256'] = sha(path)
        if not isinstance(server, dict) or server.get('disabled') is True or server.get('enabled') is False:
            raise ValueError('R_STUDIO_DISABLED_OR_INVALID')
        command = server.get('command')
        if not isinstance(command, str) or not Path(command).is_absolute() or not Path(command).is_file() or Path(command).name.lower() not in ('clauder-mcp', 'clauder-mcp.exe') or server.get('url'):
            raise ValueError('PERSISTENT_BRIDGE_REQUIRED')
        if server.get('args') not in (None, []):
            raise ValueError('PERSISTENT_BRIDGE_ARGUMENTS_UNSUPPORTED')
        env = server.get('env') or {}
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise ValueError('INVALID_ENVIRONMENT')
        home_key = 'USERPROFILE' if config.IS_WINDOWS else 'HOME'
        if not env.get(home_key) or not Path(env[home_key]).is_absolute():
            raise ValueError('EXPLICIT_DISCOVERY_HOME_REQUIRED')
        if not env.get('UV_CACHE_DIR') or not Path(env['UV_CACHE_DIR']).is_absolute():
            raise ValueError('EXPLICIT_ABSOLUTE_UV_CACHE_REQUIRED')
        if client == 'codex':
            timeout = server.get('startup_timeout_sec')
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 180:
                raise ValueError('CODEX_STARTUP_TIMEOUT_BELOW_180')
        python, route = bridge_python(command, env)
        result.update({'command': command, 'command_sha256': sha(command), 'runtime_route': route,
                       'configured_python_override': env.get('CLAUDER_WORKBENCH_MCP_PYTHON')})
        dispatcher = command if route in ('adjacent_windows_python', 'console_script_shebang') else None
        result['runtime'] = inspect_package(python, dispatcher)
        result['dispatcher_provenance'] = 'installed_RECORD_SHA256' if dispatcher else 'exact_stable_wrapper_grammar'
        manifest, manifest_path = compatibility_manifest()
        if manifest:
            result['compatibility'] = {'manifest': str(manifest_path), 'sha256': sha(manifest_path),
                'expected_bridge_version': manifest['mcp_bridge_version'], 'provider_commit': manifest['clauder_commit']}
            expected_hash = manifest.get('critical_file_sha256', {}).get('clauder-mcp/src/clauder_mcp/server.py')
            actual_hash = next(x['sha256'] for x in result['runtime']['files'] if x['relative'] == 'clauder_mcp/server.py')
            if result['runtime']['version'] != manifest['mcp_bridge_version'] or (expected_hash and actual_hash != expected_hash):
                raise ValueError('CONFIGURED_BRIDGE_DIFFERS_FROM_SOURCE_PAIR')
            receipt = result['runtime'].get('pair_receipt')
            if receipt and receipt['manifest_sha256'] != sha(manifest_path):
                raise ValueError('PAIRED_RECEIPT_MANIFEST_MISMATCH')
            result['compatibility']['ok'] = True
        else:
            result['warnings'].append('SOURCE_PAIR_MANIFEST_UNAVAILABLE')
        result['ok'] = True
    except Exception as exc:
        reason = str(exc) if type(exc) is ValueError and re.fullmatch('[A-Z_0-9]+', str(exc)) else type(exc).__name__
        result['reasons'].append(reason)
    return result
