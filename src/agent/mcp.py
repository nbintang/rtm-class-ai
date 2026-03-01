from __future__ import annotations

import json
from typing import Any

from src.config import settings


def parse_mcp_servers_config(raw: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not raw.strip():
        return {}, warnings

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, [f"Invalid MCP_SERVERS_JSON: {exc}"]

    if not isinstance(payload, dict):
        return {}, ["MCP_SERVERS_JSON must be a JSON object keyed by server name."]

    servers: dict[str, dict[str, Any]] = {}
    for name, config in payload.items():
        if not isinstance(config, dict):
            warnings.append(f"Skipping MCP server '{name}': value must be an object.")
            continue

        transport = config.get("transport")
        if transport != "streamable_http":
            warnings.append(
                f"Skipping MCP server '{name}': only transport='streamable_http' is allowed."
            )
            continue

        url = str(config.get("url", "")).strip()
        if not url:
            warnings.append(f"Skipping MCP server '{name}': missing url.")
            continue

        servers[name] = config

    return servers, warnings


class MCPToolRegistry:
    def __init__(self) -> None:
        self._client: Any | None = None
        self._tools: list[Any] = []
        self._warnings: list[str] = []
        self._loaded = False
        self._has_config = bool(settings.mcp_servers_json.strip() and settings.mcp_servers_json.strip() != "{}")

    @property
    def has_config(self) -> bool:
        return self._has_config

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    async def load_tools(self) -> list[Any]:
        if self._loaded:
            return self._tools

        servers, parse_warnings = parse_mcp_servers_config(settings.mcp_servers_json)
        self._warnings.extend(parse_warnings)

        if not servers:
            self._loaded = True
            return self._tools

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            self._warnings.append(
                "langchain-mcp-adapters is not installed. MCP tools are disabled."
            )
            self._loaded = True
            return self._tools

        try:
            self._client = MultiServerMCPClient(servers)
            self._tools = await self._client.get_tools()
        except Exception as exc:
            self._warnings.append(f"Failed to load MCP tools: {exc}")
            self._tools = []

        self._loaded = True
        return self._tools

    async def close(self) -> None:
        if not self._client:
            return

        close_method = getattr(self._client, "aclose", None)
        if callable(close_method):
            await close_method()
