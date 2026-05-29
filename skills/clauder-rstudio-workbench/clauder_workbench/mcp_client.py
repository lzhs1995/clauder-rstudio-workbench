from __future__ import annotations

import asyncio
import os
from typing import Any

from .config import LOCAL_CLAUDER_BRIDGE


EXPECTED_R_STUDIO_TOOLS = {
    "list_sessions",
    "connect_session",
    "execute_r",
    "execute_r_async",
    "get_async_result",
}


def _server_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("USERPROFILE", str(os.environ.get("USERPROFILE") or os.path.expanduser("~")))
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("NO_PROXY", "127.0.0.1,localhost")
    return env


def _server_args() -> tuple[str, list[str]]:
    if LOCAL_CLAUDER_BRIDGE and LOCAL_CLAUDER_BRIDGE.exists():
        return "uvx", ["--from", str(LOCAL_CLAUDER_BRIDGE), "clauder-mcp"]
    return "uvx", ["clauder-mcp"]


async def _list_tools_async(timeout: float = 20.0) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except Exception as exc:  # pragma: no cover - depends on optional package
        return {"ok": False, "reason": f"mcp python package unavailable: {exc}", "tools": []}

    command, args = _server_args()
    params = StdioServerParameters(command=command, args=args, env=_server_env())

    async def run() -> dict[str, Any]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
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

    try:
        return await asyncio.wait_for(run(), timeout=timeout)
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "tools": [],
            "command": command,
            "args": args,
            "local_bridge": str(LOCAL_CLAUDER_BRIDGE),
        }


def list_tools(timeout: float = 20.0) -> dict[str, Any]:
    return asyncio.run(_list_tools_async(timeout=timeout))


def probe_mcp_stdio(timeout: float = 20.0) -> dict[str, Any]:
    result = list_tools(timeout=timeout)
    result["transport_class"] = "MCP_STDIO_OK" if result.get("ok") else "BLOCKED"
    return result
