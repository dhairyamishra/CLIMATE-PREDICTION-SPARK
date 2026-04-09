"""
Multi-backend TTL cache for API responses.
Supports both in-memory (development) and Redis (production).
Thread-safe, async-compatible.
"""
import os
import time
import asyncio
import hashlib
import json
import logging
from typing import Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "")


class TTLCache:
    """Simple in-memory cache with per-key TTL expiration."""

    def __init__(self, default_ttl: int = 60, max_size: int = 256):
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = asyncio.Lock()

    def _is_expired(self, key: str) -> bool:
        if key not in self._store:
            return True
        _, expires_at = self._store[key]
        return time.monotonic() > expires_at

    async def get(self, key: str) -> Optional[Any]:
        if self._is_expired(key):
            self._store.pop(key, None)
            return None
        value, _ = self._store[key]
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        async with self._lock:
            if len(self._store) >= self._max_size:
                self._evict_expired()
                if len(self._store) >= self._max_size:
                    oldest_key = min(self._store, key=lambda k: self._store[k][1])
                    del self._store[oldest_key]
            self._store[key] = (value, time.monotonic() + (ttl or self._default_ttl))

    async def invalidate(self, pattern: str = ""):
        async with self._lock:
            if not pattern:
                self._store.clear()
            else:
                keys_to_remove = [k for k in self._store if pattern in k]
                for k in keys_to_remove:
                    del self._store[k]

    def _evict_expired(self):
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def backend(self) -> str:
        return "memory"


class RedisCache:
    """Redis-backed cache for production horizontal scaling."""

    def __init__(self, redis_url: str, default_ttl: int = 60, prefix: str = "climate:"):
        self._default_ttl = default_ttl
        self._prefix = prefix
        self._redis = None
        self._redis_url = redis_url

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, falling back to memory")
                self._redis = None
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        r = await self._get_redis()
        if r is None:
            return None
        try:
            data = await r.get(f"{self._prefix}{key}")
            if data is not None:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        r = await self._get_redis()
        if r is None:
            return
        try:
            await r.setex(
                f"{self._prefix}{key}",
                ttl or self._default_ttl,
                json.dumps(value, default=str),
            )
        except Exception:
            pass

    async def invalidate(self, pattern: str = ""):
        r = await self._get_redis()
        if r is None:
            return
        try:
            if not pattern:
                keys = []
                async for key in r.scan_iter(f"{self._prefix}*"):
                    keys.append(key)
                if keys:
                    await r.delete(*keys)
            else:
                keys = []
                async for key in r.scan_iter(f"{self._prefix}*{pattern}*"):
                    keys.append(key)
                if keys:
                    await r.delete(*keys)
        except Exception:
            pass

    @property
    def size(self) -> int:
        return -1

    @property
    def backend(self) -> str:
        return "redis"


def _create_cache() -> TTLCache | RedisCache:
    """Create the appropriate cache backend."""
    if REDIS_URL:
        logger.info(f"Using Redis cache: {REDIS_URL}")
        return RedisCache(REDIS_URL, default_ttl=60)
    logger.info("Using in-memory cache")
    return TTLCache(default_ttl=60, max_size=512)


response_cache = _create_cache()


def cache_key(*args, **kwargs) -> str:
    """Generate a deterministic cache key from arguments."""
    raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def cached(ttl: int = 60):
    """Decorator for caching async endpoint results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__module__}.{func.__name__}:{cache_key(*args[1:], **kwargs)}"
            result = await response_cache.get(key)
            if result is not None:
                return result
            result = await func(*args, **kwargs)
            await response_cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator
