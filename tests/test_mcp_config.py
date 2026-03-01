from __future__ import annotations

import unittest

from src.agent.mcp import parse_mcp_servers_config


class ParseMcpServersConfigTests(unittest.TestCase):
    def test_accepts_http_transport(self) -> None:
        servers, warnings = parse_mcp_servers_config(
            '{"weather":{"url":"http://localhost:8000/mcp","transport":"streamable_http"}}'
        )
        self.assertIn("weather", servers)
        self.assertEqual(warnings, [])

    def test_rejects_non_http_transport(self) -> None:
        servers, warnings = parse_mcp_servers_config(
            '{"math":{"command":"python","args":["server.py"],"transport":"stdio"}}'
        )
        self.assertEqual(servers, {})
        self.assertTrue(any("streamable_http" in item for item in warnings))

    def test_invalid_json_returns_warning(self) -> None:
        servers, warnings = parse_mcp_servers_config("{invalid")
        self.assertEqual(servers, {})
        self.assertTrue(any("Invalid MCP_SERVERS_JSON" in item for item in warnings))


if __name__ == "__main__":
    unittest.main()
