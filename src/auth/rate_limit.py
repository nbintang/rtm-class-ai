from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from src.config import settings


class RateLimitExceededError(Exception):
    pass


class TokenEndpointRateLimiter:
    def __init__(self) -> None:
        self._ip_hits: dict[str, deque[float]] = defaultdict(deque)
        self._client_hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @staticmethod
    def _consume(
        *,
        bucket: deque[float],
        now: float,
        window_seconds: int,
        limit: int,
    ) -> bool:
        while bucket and (now - bucket[0]) >= window_seconds:
            bucket.popleft()

        if len(bucket) >= limit:
            return False

        bucket.append(now)
        return True

    def enforce(self, *, ip: str, client_id: str) -> None:
        window_seconds = max(1, settings.oauth_token_rate_limit_window_seconds)
        per_ip_limit = max(1, settings.oauth_token_rate_limit_per_ip)
        per_client_limit = max(1, settings.oauth_token_rate_limit_per_client)
        key_ip = ip or "unknown"
        key_client = client_id or "unknown"

        with self._lock:
            now = monotonic()
            ip_allowed = self._consume(
                bucket=self._ip_hits[key_ip],
                now=now,
                window_seconds=window_seconds,
                limit=per_ip_limit,
            )
            if not ip_allowed:
                raise RateLimitExceededError("Too many token requests from this IP.")

            client_allowed = self._consume(
                bucket=self._client_hits[key_client],
                now=now,
                window_seconds=window_seconds,
                limit=per_client_limit,
            )
            if not client_allowed:
                raise RateLimitExceededError("Too many token requests for this client.")

    def reset(self) -> None:
        with self._lock:
            self._ip_hits.clear()
            self._client_hits.clear()


oauth_token_rate_limiter = TokenEndpointRateLimiter()
