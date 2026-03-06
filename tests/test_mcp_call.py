import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient as _MultiServerMCPClient
except ImportError as exc:
    _MultiServerMCPClient = None
    _MCP_IMPORT_ERROR: ImportError | None = exc
else:
    _MCP_IMPORT_ERROR = None

load_dotenv()
PAYLOAD_PATH = Path(__file__).with_name("payload-essay.json")


async def main():
    if _MultiServerMCPClient is None:
        raise RuntimeError(
            "langchain-mcp-adapters is not installed. Install dependencies before running this test."
        ) from _MCP_IMPORT_ERROR

    raw_servers = os.environ.get("MCP_SERVERS_JSON", "{}")
    servers = json.loads(raw_servers)
    if not servers:
        raise RuntimeError("MCP_SERVERS_JSON is empty. Configure at least one server.")

    client = _MultiServerMCPClient(servers)
    tools = await client.get_tools()

    tool = next(t for t in tools if t.name == "insert_essay")

    with PAYLOAD_PATH.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    result = await tool.ainvoke(payload)
    print("RESULT:", result)

    aclose = getattr(client, "aclose", None)
    if callable(aclose):
        await aclose()


if __name__ == "__main__":
    asyncio.run(main())
