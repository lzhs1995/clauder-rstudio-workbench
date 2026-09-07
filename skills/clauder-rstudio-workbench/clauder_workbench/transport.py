from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

from .config import CODEX_CONFIG, DISCOVERY_DIR, LOCAL_CLAUDER_BRIDGE, PYTHON314, python_command
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
        # Discovery files carry the bearer token used by the local HTTP
        # bridge. Doctor evidence is durable and may be shared for support, so
        # it must report only whether a token exists, never the secret itself.
        if not isinstance(doc, dict):
            sessions.append({"path": str(path), "error": "discovery must be an object"})
            continue
        doc["token_present"] = bool(doc.pop("token", None))
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
    session_name: str = "",
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
        http_result = http_execute_probe(timeout=min(timeout, 10.0), session_name=session_name)
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


def _http_target(port: int | None, session_name: str) -> dict[str, Any]:
    # 不猜测 8787，不删 discovery，不在多会话之间静默切换。
    candidates = []
    for path in sorted(DISCOVERY_DIR.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        value = doc.get("port")
        if type(value) is not int or not 1 <= value <= 65535:
            continue
        if port is not None and value != port:
            continue
        if session_name and doc.get("session_name") != session_name:
            continue
        candidates.append(doc)
    if len(candidates) != 1:
        raise ValueError(f"expected one discovery match, found {len(candidates)}; specify session_name or a discovered port")
    return candidates[0]


def http_execute_probe(port: int | None = None, timeout: float = 10.0, *, session_name: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "scope": "addin_http_execution_only"}
    try:
        target = _http_target(port, session_name)
    except ValueError as exc:
        return {**result, "reason": str(exc)}
    port = target["port"]
    result.update(port=port, session_name=target.get("session_name"), token_present=bool(target.get("token")))
    marker = "clauder_http_probe_ok_" + secrets.token_hex(12)
    payload = json.dumps({"code": f"cat('{marker}')"}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if target.get("token"):
        headers["X-Clauder-Token"] = str(target["token"])
    req = urllib.request.Request(f"http://127.0.0.1:{port}/execute", data=payload, headers=headers, method="POST")
    try:
        # 回环诊断不继承代理，也不把会话 token 跟随重定向发送到其他地址。
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=timeout) as resp:
            if not 200 <= resp.status < 300:
                return {**result, "reason": f"HTTP status {resp.status}"}
            body = resp.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            return {**result, "reason": "HTTP response too large"}
        doc = json.loads(body)
        ok = (isinstance(doc, dict) and doc.get("success") is True
              and not doc.get("error") and isinstance(doc.get("output"), str)
              and marker in doc["output"])
        return {**result, "ok": ok, "marker_observed": ok,
                "reason": "execution marker verified" if ok else "response lacks successful execution marker or contains an error"}
    except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        # 不保留原始响应或异常正文，避免回显 token、研究数据或代理凭据。
        return {**result, "reason": f"HTTP probe failed: {type(exc).__name__}",
                "status": getattr(exc, "code", None)}


def terminal_status() -> dict[str, Any]:
    return {"scope": "diagnostic_process_fds_not_parent_terminal",
            "stdin": os.isatty(0), "stdout": os.isatty(1), "stderr": os.isatty(2)}


def rscript_probe() -> dict[str, Any]:
    path = shutil.which("Rscript") or shutil.which("Rscript.exe")
    if not path:
        return {"ok": False, "reason": "Rscript not found on PATH"}
    return {"ok": True, "path": path}
