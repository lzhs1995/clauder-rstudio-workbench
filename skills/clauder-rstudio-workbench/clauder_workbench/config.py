from __future__ import annotations

import os
import shutil
from pathlib import Path


def _home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home()).expanduser()


def _env_path(name: str, default: Path | None = None) -> Path | None:
    value = os.environ.get(name)
    if value:
        return Path(value).expanduser()
    return default


HOME = _home()
STATE_DIR = HOME / ".clauder_workbench"
EVIDENCE_DIR = STATE_DIR / "evidence"
INFLIGHT_DIR = STATE_DIR / "inflight"
ARCHIVE_DIR = INFLIGHT_DIR / "archive"

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA") or (HOME / "AppData" / "Local"))
DEFAULT_PYTHON314 = LOCALAPPDATA / "Programs" / "Python" / "Python314" / "python.exe"
PYTHON_EXE = _env_path("CLAUDER_WORKBENCH_PYTHON", DEFAULT_PYTHON314)
PYTHON314 = PYTHON_EXE
WINDOWS_STORE_PYTHON = LOCALAPPDATA / "Microsoft" / "WindowsApps" / "python3.exe"
LOCAL_CLAUDER_BRIDGE = _env_path("CLAUDER_WORKBENCH_CLAUDER_MCP", HOME / "projects" / "ClaudeR" / "clauder-mcp")
DISCOVERY_DIR = _env_path("CLAUDER_WORKBENCH_DISCOVERY_DIR", HOME / ".claude_r_sessions")
CODEX_CONFIG = _env_path("CLAUDER_WORKBENCH_CODEX_CONFIG", HOME / ".codex" / "config.toml")
CODEX_INSTALL_INFO = _env_path("CLAUDER_WORKBENCH_CODEX_INSTALL_INFO", HOME / ".codex" / "skills" / "clauder-rstudio-workbench" / "INSTALL_INFO.json")
AGENTS_INSTALL_INFO = _env_path("CLAUDER_WORKBENCH_AGENTS_INSTALL_INFO", HOME / ".agents" / "skills" / "clauder-rstudio-workbench" / "INSTALL_INFO.json")
CLAUDE_JSON = _env_path("CLAUDER_WORKBENCH_CLAUDE_JSON", HOME / ".claude.json")
COPILOT_CONFIG = _env_path("CLAUDER_WORKBENCH_COPILOT_CONFIG", HOME / ".copilot" / "mcp-config.json")
CLAUDER_HTTP_PORT = int(os.environ.get("CLAUDER_WORKBENCH_HTTP_PORT", "8787"))

PASS = 0
WARN = 2
BLOCK = 3
TRANSPORT_UNSTABLE = 4
CONTRACT_FAILED = 5


def ensure_state_dirs() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    INFLIGHT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def default_agent() -> str:
    return os.environ.get("CLAUDER_WORKBENCH_AGENT") or os.environ.get("AGENT_NAME") or "unknown"


def python_command() -> str:
    if PYTHON_EXE and PYTHON_EXE.exists():
        return str(PYTHON_EXE)
    found = shutil.which("python")
    if found:
        return found
    return "python"


def normalize_path(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(Path(value).expanduser().resolve()).lower()
    except Exception:
        return value.strip().lower()
