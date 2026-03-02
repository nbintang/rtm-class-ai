from __future__ import annotations

import json
from typing import Any


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

