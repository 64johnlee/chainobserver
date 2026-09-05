"""Solana MCP backend — spawns the ChainObserver Solana MCP server as a stdio subprocess."""
from __future__ import annotations

import logging
import os
import sys

from .mcp import MCPBackend, _MCP_AVAILABLE

if _MCP_AVAILABLE:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class SolanaMCPBackend(MCPBackend):
    """Manages the chainobserver Solana MCP server subprocess.

    Reuses MCPBackend's tool-listing/calling logic (identical MCP protocol) — only
    the spawned module and env vars differ, so this only overrides __aenter__.
    """

    def __init__(self, solana_rpc_url: str = "") -> None:
        super().__init__()
        self._solana_rpc_url = solana_rpc_url

    async def __aenter__(self) -> "SolanaMCPBackend":
        if not _MCP_AVAILABLE:
            raise RuntimeError("The 'mcp' package is not installed. Run: pip install mcp")
        env = {
            **os.environ,
            "SOLANA_RPC_URL": self._solana_rpc_url or os.environ.get(
                "SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"
            ),
        }
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "chainobserver.solana_mcp_server"],
            env=env,
        )
        logger.info("Starting ChainObserver Solana MCP server…")
        self._stdio_cm = stdio_client(server_params)
        read, write = await self._stdio_cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self
