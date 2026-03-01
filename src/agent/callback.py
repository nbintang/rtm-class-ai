from __future__ import annotations

from src.config import settings


class WebhookCallbackClient:
    def __init__(self) -> None:
        self._client = None

    async def initialize(self) -> None:
        if self._client is not None:
            return

        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx package is required for webhook callback.") from exc

        self._client = httpx.AsyncClient(
            timeout=settings.webhook_callback_timeout_seconds,
        )

    async def shutdown(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None

    async def send_json(self, *, callback_url: str, payload: dict) -> None:
        await self.initialize()
        assert self._client is not None

        response = await self._client.post(callback_url, json=payload)
        response.raise_for_status()
