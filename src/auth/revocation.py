from __future__ import annotations

import asyncio
import logging

from src.config import settings

logger = logging.getLogger(__name__)


class RedisTokenDenylist:
    def __init__(self) -> None:
        self._redis = None
        self._lock = asyncio.Lock()
        self._warned_unavailable = False

    def _key(self, jti: str) -> str:
        return f"{settings.jwt_denylist_prefix}{jti}"

    def _warn_once(self, message: str) -> None:
        if self._warned_unavailable:
            return
        self._warned_unavailable = True
        logger.warning(message)

    async def _get_redis(self):
        if not settings.jwt_denylist_enabled:
            return None

        if self._redis is not None:
            return self._redis

        async with self._lock:
            if self._redis is not None:
                return self._redis

            try:
                from redis.asyncio import Redis
            except ImportError:
                self._warn_once("redis package missing; JWT denylist disabled.")
                return None

            redis = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            try:
                await redis.ping()
            except Exception:
                await redis.close()
                self._warn_once("Redis unavailable; JWT denylist checks skipped.")
                return None

            self._redis = redis
            return self._redis

    async def is_revoked(self, jti: str) -> bool:
        if not settings.jwt_denylist_enabled or not jti:
            return False

        redis = await self._get_redis()
        if redis is None:
            return False

        try:
            return bool(await redis.exists(self._key(jti)))
        except Exception:
            self._warn_once("Redis denylist read failed; revocation checks skipped.")
            return False

    async def revoke(self, jti: str, *, ttl_seconds: int | None = None) -> None:
        if not settings.jwt_denylist_enabled or not jti:
            return

        redis = await self._get_redis()
        if redis is None:
            return

        ttl = max(1, ttl_seconds or settings.oauth_token_ttl_seconds)
        try:
            await redis.set(self._key(jti), "1", ex=ttl)
        except Exception:
            self._warn_once("Redis denylist write failed; revoke skipped.")

    async def shutdown(self) -> None:
        if self._redis is None:
            return
        await self._redis.close()
        self._redis = None
        self._warned_unavailable = False


token_denylist = RedisTokenDenylist()


async def is_token_revoked(jti: str) -> bool:
    return await token_denylist.is_revoked(jti)


async def revoke_token(jti: str, *, ttl_seconds: int | None = None) -> None:
    await token_denylist.revoke(jti, ttl_seconds=ttl_seconds)


async def shutdown_token_denylist() -> None:
    await token_denylist.shutdown()
