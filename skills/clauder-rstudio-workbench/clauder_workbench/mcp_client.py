from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any

from .config import CODEX_CONFIG, HOME, IS_WINDOWS, LOCAL_CLAUDER_BRIDGE, UV_CACHE_DIR


EXPECTED_R_STUDIO_TOOLS = {
    "annotate",
    "cancel_annotation_job",
    "cancel_async_job",
    "check_cross_references",
    "check_messages",
    "checkpoint_session",
    "clean_error_log",
    "connect_session",
    "coordination_roster",
    "create_task_list",
    "execute_r",
    "execute_r_async",
    "execute_r_with_plot",
    "generate_codebook",
    "generate_notebook",
    "get_active_document",
    "get_annotation_job_status",
    "get_async_result",
    "get_bibtex",
    "get_r_info",
    "get_session_history",
    "get_viewer_content",
    "insert_text",
    "list_checkpoints",
    "list_sessions",
    "load_annotation_data",
    "modify_code_section",
    "probe_scripts",
    "read_file",
    "reconcile_values",
    "restore_session",
    "run_annotation_job",
    "screening_report",
    "search_citations",
    "search_project_code",
    "send_message",
    "set_agent_name",
    "update_task_status",
    "verify_references",
    "wait_for_message",
}


def _load_codex_rstudio_server() -> tuple[str, list[str], dict[str, str]] | None:
    if not CODEX_CONFIG.exists():
        return None
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        raw = CODEX_CONFIG.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        data = tomllib.loads(raw.decode("utf-8"))
        server = ((data.get("mcp_servers") or {}).get("r-studio") or {}) if isinstance(data, dict) else {}
        command = str(server.get("command") or "")
        if not command:
            return None
        raw_args = server.get("args") or []
        if isinstance(raw_args, str):
            args = [raw_args]
        else:
            args = [str(a) for a in raw_args]
        raw_env = (server.get("env") or {}) if isinstance(server, dict) else {}
        env = {str(k): str(v) for k, v in raw_env.items() if v is not None}
        return command, args, env
    except Exception:
        return None


def _server_spec() -> tuple[str, list[str], dict[str, str]]:
    configured = _load_codex_rstudio_server()
    if configured:
        return configured
    if LOCAL_CLAUDER_BRIDGE and LOCAL_CLAUDER_BRIDGE.exists():
        return "uvx", ["--from", str(LOCAL_CLAUDER_BRIDGE), "clauder-mcp"], {}
    return "uvx", ["clauder-mcp"], {}


def _server_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("HOME", str(HOME))
    if IS_WINDOWS:
        env.setdefault("USERPROFILE", str(os.environ.get("USERPROFILE") or HOME))
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("NO_PROXY", "127.0.0.1,localhost")
    if UV_CACHE_DIR:
        env.setdefault("UV_CACHE_DIR", str(UV_CACHE_DIR))
    if extra:
        env.update(extra)
    return env


def _server_args() -> tuple[str, list[str]]:
    command, args, _env = _server_spec()
    return command, args


def _result_text(result: Any) -> str:
    chunks: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            chunks.append(str(text))
        elif hasattr(item, "model_dump"):
            chunks.append(str(item.model_dump()))
        else:
            chunks.append(str(item))
    return "\n".join(chunks)


def _tool_result(result: Any, *, tool_name: str) -> dict[str, Any]:
    text = _result_text(result)
    is_error = bool(getattr(result, "isError", False) or getattr(result, "is_error", False))
    return {"tool": tool_name, "ok": not is_error and not text.lower().startswith("error:"), "is_error": is_error, "text": text}


def extract_job_id(text: str) -> str | None:
    patterns = [
        r"Job\s+([A-Za-z0-9_-]+)\s+started",
        r"get_async_result\(\"([A-Za-z0-9_-]+)\"\)",
        r"job_id['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


async def _session_run(timeout: float, runner: Any) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except Exception as exc:  # pragma: no cover - depends on optional package
        return {"ok": False, "reason": f"mcp python package unavailable: {exc}"}

    command, args, env_extra = _server_spec()
    params = StdioServerParameters(command=command, args=args, env=_server_env(env_extra))

    async def run() -> dict[str, Any]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await runner(session, command, args)

    try:
        return await asyncio.wait_for(run(), timeout=timeout)
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "command": command,
            "args": args,
            "local_bridge": str(LOCAL_CLAUDER_BRIDGE),
        }


async def _list_tools_async(timeout: float = 20.0) -> dict[str, Any]:
    async def runner(session: Any, command: str, args: list[str]) -> dict[str, Any]:
        result = await session.list_tools()
        tools = sorted(tool.name for tool in result.tools)
        missing = sorted(EXPECTED_R_STUDIO_TOOLS - set(tools))
        return {
            "ok": not missing,
            "tools": tools,
            "missing": missing,
            "command": command,
            "args": args,
            "local_bridge": str(LOCAL_CLAUDER_BRIDGE),
        }

    return await _session_run(timeout, runner)


async def _call_tool_async(tool_name: str, arguments: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    async def runner(session: Any, command: str, args: list[str]) -> dict[str, Any]:
        result = await session.call_tool(tool_name, arguments or {})
        out = _tool_result(result, tool_name=tool_name)
        out.update({"command": command, "args": args, "local_bridge": str(LOCAL_CLAUDER_BRIDGE)})
        return out

    return await _session_run(timeout, runner)


async def _preflight_smoke_async(
    *,
    session_name: str = "",
    timeout: float = 90.0,
    async_poll_attempts: int = 2,
) -> dict[str, Any]:
    async def runner(session: Any, command: str, args: list[str]) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        tools_result = await session.list_tools()
        tools = sorted(tool.name for tool in tools_result.tools)
        missing = sorted(EXPECTED_R_STUDIO_TOOLS - set(tools))
        steps.append({"step": "tools_list", "ok": not missing, "missing": missing, "tools": tools})
        if missing:
            return {"ok": False, "reason": f"missing tools: {', '.join(missing)}", "steps": steps}

        list_result = _tool_result(await session.call_tool("list_sessions", {}), tool_name="list_sessions")
        steps.append({"step": "list_sessions", **list_result})
        if not list_result["ok"]:
            return {"ok": False, "reason": "list_sessions failed", "steps": steps}

        if session_name:
            connect_result = _tool_result(await session.call_tool("connect_session", {"session_name": session_name}), tool_name="connect_session")
            steps.append({"step": "connect_session", **connect_result})
            if not connect_result["ok"]:
                return {"ok": False, "reason": "connect_session failed", "steps": steps}

        sync_code = "cat('clauder_preflight_sync_ok pid=', Sys.getpid(), ' r=', as.character(getRversion()), '\\n', sep='')"
        sync_result = _tool_result(await session.call_tool("execute_r", {"code": sync_code}), tool_name="execute_r")
        steps.append({"step": "execute_r", **sync_result})
        if not sync_result["ok"] or "clauder_preflight_sync_ok" not in sync_result["text"]:
            return {"ok": False, "reason": "execute_r smoke failed", "steps": steps}

        async_code = "cat('clauder_preflight_async_ok\\n')"
        submit_result = _tool_result(await session.call_tool("execute_r_async", {"code": async_code}), tool_name="execute_r_async")
        job_id = extract_job_id(submit_result["text"])
        steps.append({"step": "execute_r_async", **submit_result, "job_id": job_id})
        if not submit_result["ok"] or not job_id:
            return {"ok": False, "reason": "execute_r_async smoke failed or job_id missing", "steps": steps}

        final_result: dict[str, Any] | None = None
        for attempt in range(1, async_poll_attempts + 1):
            poll_result = _tool_result(await session.call_tool("get_async_result", {"job_id": job_id}), tool_name="get_async_result")
            poll_result["attempt"] = attempt
            steps.append({"step": "get_async_result", **poll_result})
            final_result = poll_result
            text_lower = poll_result["text"].lower()
            if "clauder_preflight_async_ok" in poll_result["text"] or "completed" in text_lower or "final progress" in text_lower:
                return {
                    "ok": True,
                    "transport_class": "MCP_STDIO_OK",
                    "job_id": job_id,
                    "steps": steps,
                    "tools": tools,
                    "command": command,
                    "args": args,
                    "local_bridge": str(LOCAL_CLAUDER_BRIDGE),
                }
        return {"ok": False, "reason": "async smoke did not reach completion", "job_id": job_id, "steps": steps, "last_poll": final_result}

    return await _session_run(timeout, runner)


def _retry_if_cold_timeout(func: Any, *, timeout: float, retries: int = 1) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(retries + 1):
        result = asyncio.run(func(timeout=timeout))
        result["attempt"] = attempt + 1
        attempts.append(result)
        if result.get("ok"):
            if len(attempts) > 1:
                result["cold_start_retried"] = True
                result["attempts"] = attempts
            return result
        reason = str(result.get("reason", ""))
        if "TimeoutError" not in reason or attempt >= retries:
            result["attempts"] = attempts
            return result
        time.sleep(1.0)
    return attempts[-1]


def list_tools(timeout: float = 20.0, retries: int = 1) -> dict[str, Any]:
    return _retry_if_cold_timeout(_list_tools_async, timeout=timeout, retries=retries)


def call_tool(tool_name: str, arguments: dict[str, Any] | None = None, timeout: float = 20.0, retries: int = 0) -> dict[str, Any]:
    async def run(timeout: float) -> dict[str, Any]:
        return await _call_tool_async(tool_name, arguments=arguments, timeout=timeout)

    return _retry_if_cold_timeout(run, timeout=timeout, retries=retries)


def preflight_smoke(session_name: str = "", timeout: float = 90.0, async_poll_attempts: int = 2, retries: int = 1) -> dict[str, Any]:
    async def run(timeout: float) -> dict[str, Any]:
        return await _preflight_smoke_async(session_name=session_name, timeout=timeout, async_poll_attempts=async_poll_attempts)

    return _retry_if_cold_timeout(run, timeout=timeout, retries=retries)


def probe_mcp_stdio(timeout: float = 20.0) -> dict[str, Any]:
    result = list_tools(timeout=timeout)
    result["transport_class"] = "MCP_STDIO_OK" if result.get("ok") else "BLOCKED"
    return result


async def _submit_async_async(*, session_name: str, code: str, timeout: float) -> dict[str, Any]:
    async def runner(session: Any, command: str, args: list[str]) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        if session_name:
            connect = _tool_result(
                await session.call_tool("connect_session", {"session_name": session_name}),
                tool_name="connect_session",
            )
            steps.append({"step": "connect_session", **connect})
            if not connect["ok"]:
                return {"ok": False, "reason": "connect_session failed", "steps": steps}
        submit = _tool_result(await session.call_tool("execute_r_async", {"code": code}), tool_name="execute_r_async")
        job_id = extract_job_id(submit["text"])
        steps.append({"step": "execute_r_async", **submit, "job_id": job_id})
        return {
            "ok": bool(submit["ok"] and job_id),
            "job_id": job_id,
            "text": submit["text"],
            "transport_class": "MCP_STDIO_OK",
            "steps": steps,
        }

    return await _session_run(timeout, runner)


def submit_async(session_name: str, code: str, timeout: float = 60.0, retries: int = 1) -> dict[str, Any]:
    """在单个 MCP stdio 会话内 connect_session（可选）+ execute_r_async 提交，返回 job_id。"""

    async def run(timeout: float) -> dict[str, Any]:
        return await _submit_async_async(session_name=session_name, code=code, timeout=timeout)

    return _retry_if_cold_timeout(run, timeout=timeout, retries=retries)
