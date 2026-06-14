"""
Kavalx Redis Connection Utilities
===================================

Provides a managed Redis connection pool and high-level helpers for
caching, rate-limiting, and distributed locking.

Usage:
    from services.shared.redis_utils import get_redis, redis_cache

    r = get_redis()
    await r.set("key", "value", ex=300)

    @redis_cache(ttl=60)
    async def get_account(account_id: str) -> dict:
        ...
"""

from __future__ import annotations

import functools
import json
import logging
from typing import Any, Callable, Optional

import redis
from redis import ConnectionPool, Redis
from redis.exceptions import RedisError

from services.shared.config import get_settings

logger = logging.getLogger(__name__)

# Module-level connection pool (created lazily)
_pool: Optional[ConnectionPool] = None


def _get_pool() -> ConnectionPool:
    """Return the module-level Redis connection pool, creating it if needed."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        logger.info(
            "Redis connection pool created (url=%s, max_conn=%d)",
            settings.redis_url,
            settings.redis_max_connections,
        )
    return _pool


def get_redis() -> Redis:
    """Return a Redis client from the shared connection pool.

    Returns:
        A ``redis.Redis`` instance bound to the shared pool.

    Raises:
        RedisError: If the connection cannot be established.
    """
    return Redis(connection_pool=_get_pool())


def close_pool() -> None:
    """Disconnect all connections in the pool.  Call at shutdown."""
    global _pool
    if _pool is not None:
        _pool.disconnect()
        _pool = None
        logger.info("Redis connection pool closed.")


# ── Caching Decorator ──────────────────────────────────────


def redis_cache(
    ttl: int = 300,
    prefix: str = "kavalx:cache",
    serializer: Callable[[Any], str] = lambda v: json.dumps(v, default=str),
    deserializer: Callable[[str], Any] = json.loads,
) -> Callable:
    """Decorator that caches function results in Redis.

    Args:
        ttl: Cache time-to-live in seconds (default 5 minutes).
        prefix: Redis key prefix.
        serializer: Function to serialize the return value to a string.
        deserializer: Function to deserialize cached strings back.

    Example:
        @redis_cache(ttl=120, prefix="kavalx:account")
        def get_account_risk(account_id: str) -> dict:
            ...
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build a deterministic cache key
            key_parts = [prefix, fn.__name__]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            r = get_redis()

            # Try cache hit
            try:
                cached = r.get(cache_key)
                if cached is not None:
                    logger.debug("Cache HIT: %s", cache_key)
                    return deserializer(cached)
            except RedisError:
                logger.warning("Redis read error for key=%s, falling through.", cache_key)

            # Cache miss – execute function
            result = fn(*args, **kwargs)

            # Store result
            try:
                r.set(cache_key, serializer(result), ex=ttl)
                logger.debug("Cache SET: %s (ttl=%ds)", cache_key, ttl)
            except RedisError:
                logger.warning("Redis write error for key=%s", cache_key)

            return result

        return wrapper

    return decorator


# ── Rate Limiter ───────────────────────────────────────────


class RateLimiter:
    """Sliding-window rate limiter backed by Redis.

    Args:
        key_prefix: Prefix for rate-limit keys.
        max_requests: Maximum requests allowed in the window.
        window_seconds: Window duration in seconds.
    """

    def __init__(
        self,
        key_prefix: str = "kavalx:ratelimit",
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis = get_redis()

    def is_allowed(self, identifier: str) -> bool:
        """Check whether a request from ``identifier`` is within limits.

        Uses a Redis ``INCR`` + ``EXPIRE`` sliding-window pattern.

        Args:
            identifier: Unique client identifier (e.g. IP, user ID).

        Returns:
            ``True`` if the request is allowed, ``False`` if rate-limited.
        """
        key = f"{self.key_prefix}:{identifier}"
        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.incr(key)
            pipe.expire(key, self.window_seconds)
            results = pipe.execute()
            current_count: int = results[0]

            if current_count > self.max_requests:
                logger.warning(
                    "Rate limit exceeded: identifier=%s count=%d limit=%d",
                    identifier,
                    current_count,
                    self.max_requests,
                )
                return False
            return True
        except RedisError:
            logger.error("Rate limiter Redis error for identifier=%s", identifier)
            # Fail open – allow the request if Redis is down
            return True

    def remaining(self, identifier: str) -> int:
        """Return the number of remaining requests for ``identifier``."""
        key = f"{self.key_prefix}:{identifier}"
        try:
            current = self._redis.get(key)
            if current is None:
                return self.max_requests
            return max(0, self.max_requests - int(current))
        except RedisError:
            return self.max_requests


# ── Distributed Lock ───────────────────────────────────────


class DistributedLock:
    """Simple Redis-based distributed lock (non-reentrant).

    Uses ``SET NX EX`` for atomic acquire and Lua script for safe release.

    Args:
        name: Lock name.
        timeout: Lock auto-expiry in seconds (default 30s).
    """

    RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(self, name: str, timeout: int = 30) -> None:
        self.key = f"kavalx:lock:{name}"
        self.timeout = timeout
        self._redis = get_redis()
        self._token: Optional[str] = None

    def acquire(self, token: str) -> bool:
        """Attempt to acquire the lock.

        Args:
            token: Unique token identifying this lock holder.

        Returns:
            ``True`` if the lock was acquired.
        """
        acquired = self._redis.set(self.key, token, nx=True, ex=self.timeout)
        if acquired:
            self._token = token
            logger.debug("Lock acquired: %s (token=%s)", self.key, token)
        return bool(acquired)

    def release(self, token: str) -> bool:
        """Release the lock only if held by ``token``.

        Returns:
            ``True`` if the lock was released.
        """
        result = self._redis.eval(self.RELEASE_SCRIPT, 1, self.key, token)
        released = bool(result)
        if released:
            self._token = None
            logger.debug("Lock released: %s (token=%s)", self.key, token)
        return released

    def __enter__(self) -> "DistributedLock":
        import uuid

        self._token = str(uuid.uuid4())
        if not self.acquire(self._token):
            raise RedisError(f"Failed to acquire lock: {self.key}")
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._token:
            self.release(self._token)
