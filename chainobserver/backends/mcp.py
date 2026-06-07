"""MCP backend — spawns the ChainObserver MCP server as a stdio subprocess."""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

from google.genai import types

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import Tool as MCPTool
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    ClientSession = None  # type: ignore[assignment,misc]
    StdioServerParameters = None  # type: ignore[assignment,misc]
    stdio_client = None  # type: ignore[assignment]
    MCPTool = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class MCPBackend:
    """Manages the chainobserver MCP server subprocess and exposes its tools as Gemini declarations."""

    def __init__(self, eth_rpc_url: str = "", etherscan_api_key: str = "") -> None:
        self._eth_rpc_url = eth_rpc_url
        self._etherscan_api_key = etherscan_api_key
        self._session: Any = None
        self._stdio_cm: Any = None

    @staticmethod
    def is_available() -> bool:
        return _MCP_AVAILABLE

    async def __aenter__(self) -> "MCPBackend":
        if not _MCP_AVAILABLE:
            raise RuntimeError("The 'mcp' package is not installed. Run: pip install mcp")
        env = {
            **os.environ,
            "ETH_RPC_URL": self._eth_rpc_url or os.environ.get("ETH_RPC_URL", "https://eth.llamarpc.com"),
            "ETHERSCAN_API_KEY": self._etherscan_api_key or os.environ.get("ETHERSCAN_API_KEY", ""),
        }
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "chainobserver.mcp_server"],
            env=env,
        )
        logger.info("Starting ChainObserver MCP server…")
        self._stdio_cm = stdio_client(server_params)
        read, write = await self._stdio_cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._session:
            try:
                await self._session.__aexit__(*exc_info)
            except BaseException:
                pass
        if self._stdio_cm:
            try:
                await self._stdio_cm.__aexit__(*exc_info)
            except BaseException:
                pass

    async def list_tools_as_gemini(self) -> list[types.Tool]:
        assert self._session is not None
        result = await self._session.list_tools()
        declarations = [_mcp_to_gemini(t) for t in result.tools]
        return [types.Tool(function_declarations=declarations)]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        assert self._session is not None
        result = await self._session.call_tool(name, arguments)
        parts: list[str] = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
            else:
                parts.append(str(item))
        return "\n".join(parts)


def _mcp_to_gemini(tool: Any) -> types.FunctionDeclaration:
    schema = tool.inputSchema or {}
    properties: dict[str, types.Schema] = {}
    for prop_name, prop_def in schema.get("properties", {}).items():
        properties[prop_name] = types.Schema(
            type=_json_type(prop_def.get("type", "string")),
            description=prop_def.get("description", ""),
        )
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description or "",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties=properties,
            required=schema.get("required", []),
        ),
    )


def _json_type(t: str) -> types.Type:
    return {
        "string": types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number": types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
        "array": types.Type.ARRAY,
        "object": types.Type.OBJECT,
    }.get(t, types.Type.STRING)
