from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

from .config import CLAUDER_HTTP_PORT, CODEX_CONFIG, DISCOVERY_DIR, LOCAL_CLAUDER_BRIDGE, PYTHON314, python_command
from .mcp_client import probe_mcp_stdio


TRANSPORT_CLASSES = {
    "NATIVE_MCP_OK",
    "MCP_STDIO_OK",
    "HTTP_ONLY_DIAGNOSTIC",
    "RSCRIPT_ONLY",
    "BLOCKED",
}


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def discovery_sessions() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    if not DISCOVERY_DIR.exists():
        return sessions
    for path in DISCOVERY_DIR.glob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            sessions.append({"path": str(path), "error": str(exc)})
            continue
        doc["path"] = str(path)
        port = doc.get("port")
        if isinstance(port, int):
            doc["port_open"] = port_open("127.0.0.1", port)
        sessions.append(doc)
    return sessions


def classify_transport(
    *,
    native_ok: bool = False,
    mcp_stdio_ok: bool = False,
    http_ok: bool = False,
    rscript_ok: bool = False,
    native_required: bool = False,
    allow_agent_hints: bool = False,
    probe_stdio: bool = False,
    probe_http: bool = False,
    probe_rscript: bool = False,
    timeout: float = 20.0,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if native_ok and allow_agent_hints:
        return "NATIVE_MCP_OK", ["native MCP wrapper evidence is available"]
    if mcp_stdio_ok and allow_agent_hints:
        if native_required:
            return "BLOCKED", ["native wrapper is required, MCP stdio cannot be reported as native success"]
        return "MCP_STDIO_OK", ["MCP stdio evidence is available and must be labeled as such"]
    if http_ok and allow_agent_hints:
        if native_required:
            return "BLOCKED", ["HTTP is diagnostic only and cannot satisfy native MCP requirement"]
        return "HTTP_ONLY_DIAGNOSTIC", ["HTTP fallback is available only as diagnostic evidence"]
    if rscript_ok and allow_agent_hints:
        return "RSCRIPT_ONLY", ["Rscript is available but does not prove RStudio/ClaudeR/MCP readiness"]

    ignored = []
    if native_ok:
        ignored.append("native_ok")
    if mcp_stdio_ok:
        ignored.append("mcp_stdio_ok")
    if http_ok:
        ignored.append("http_ok")
    if rscript_ok:
        ignored.append("rscript_ok")
    if ignored:
        reasons.append(f"agent-supplied hints ignored without allow_agent_hints: {', '.join(ignored)}")

    if probe_stdio:
        mcp_result = probe_mcp_stdio(timeout=timeout)
        if mcp_result.get("ok"):
            if native_required:
                return "BLOCKED", reasons + ["native wrapper is required; independent MCP stdio is not native evidence"]
            return "MCP_STDIO_OK", reasons + ["independent MCP stdio probe succeeded"]
        reasons.append(f"MCP stdio probe failed: {mcp_result.get('reason') or mcp_result.get('missing')}")

    if probe_http:
        http_result = http_execute_probe(timeout=min(timeout, 10.0))
        if http_result.get("ok"):
            if native_required:
                return "BLOCKED", reasons + ["HTTP is diagnostic only and cannot satisfy native MCP requirement"]
            return "HTTP_ONLY_DIAGNOSTIC", reasons + ["independent HTTP execute probe succeeded"]
        reasons.append(f"HTTP probe failed: {http_result.get('reason')}")

    if probe_rscript:
        rscript_result = rscript_probe()
        if rscript_result.get("ok"):
            return "RSCRIPT_ONLY", reasons + [f"Rscript is available at {rscript_result.get('path')}, but it is not RStudio/ClaudeR/MCP evidence"]
        reasons.append(f"Rscript probe failed: {rscript_result.get('reason')}")

    return "BLOCKED", reasons or ["no acceptable transport evidence found"]


def run_python_smoke() -> dict[str, Any]:
    python = python_command()
    try:
        proc = subprocess.run(
            [python, "-c", "import sys; print(sys.executable); print(sys.version.split()[0])"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "python": python,
        }
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "python": python}


def codex_config_mentions_local_bridge() -> bool:
    if not CODEX_CONFIG.exists():
        return False
    text = CODEX_CONFIG.read_text(encoding="utf-8", errors="ignore")
    normalized = text.replace("\\\\", "\\").lower()
    return str(LOCAL_CLAUDER_BRIDGE).lower() in normalized


def current_python() -> str:
    return sys.executable


def http_execute_probe(port: int = CLAUDER_HTTP_PORT, timeout: float = 10.0) -> dict[str, Any]:
    url = f"http://127.0.0.1:{port}/execute"
    payload = json.dumps({"code": "cat('clauder_http_probe_ok')"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return {"ok": "clauder_http_probe_ok" in body or bool(body), "port": port, "body_preview": body[:500]}
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "port": port, "reason": f"{type(exc).__name__}: {exc}"}


def rscript_probe() -> dict[str, Any]:
    path = shutil.which("Rscript") or shutil.which("Rscript.exe")
    if not path:
        return {"ok": False, "reason": "Rscript not found on PATH"}
    return {"ok": True, "path": path}
