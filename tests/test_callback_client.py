from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock

from src.agent.callback import WebhookCallbackClient


class WebhookCallbackClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_json_success(self) -> None:
        client = WebhookCallbackClient()
        mock_response = Mock()
        mock_response.raise_for_status = Mock(return_value=None)
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        await client.send_json(
            callback_url="https://example.com/callback",
            payload={"hello": "world"},
        )

        mock_http_client.post.assert_awaited_once()

    async def test_send_json_raises_for_non_2xx(self) -> None:
        client = WebhookCallbackClient()
        mock_response = Mock()
        mock_response.raise_for_status = Mock(side_effect=RuntimeError("bad status"))
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        with self.assertRaises(RuntimeError):
            await client.send_json(
                callback_url="https://example.com/callback",
                payload={"hello": "world"},
            )


if __name__ == "__main__":
    unittest.main()
