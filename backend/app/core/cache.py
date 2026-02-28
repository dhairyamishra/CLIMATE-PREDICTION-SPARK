"""
Lightweight in-memory TTL cache for expensive API responses.
Thread-safe, async-compatible, no external dependencies.
"""
import time
import asyncio
import hashlib
import json
from typing import Any, Optional
from functools import wraps


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


# Global cache instance
response_cache = TTLCache(default_ttl=60, max_size=512)


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
