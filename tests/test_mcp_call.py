import asyncio, json, os
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
load_dotenv()
PAYLOAD_PATH = "testspayload-essay.json"

async def main():
    servers = json.loads(os.environ["MCP_SERVERS_JSON"])
    client = MultiServerMCPClient(servers)
    tools = await client.get_tools()

    tool = next(t for t in tools if t.name == "insert_essay")

    payload = json.load(open(PAYLOAD_PATH, "r", encoding="utf-8"))

    result = await tool.ainvoke(payload)
    print("RESULT:", result)

    aclose = getattr(client, "aclose", None)
    if callable(aclose):
        await aclose()

asyncio.run(main())