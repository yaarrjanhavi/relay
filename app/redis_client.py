"""
Redis integration: Atomic Lua token-bucket rate limiter, SHA-256 response cache,
and thread-safe in-memory fail-open fallbacks.
"""

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger("relay.redis")

# Rate limit metrics counter
_rate_limited_count = 0
_metrics_lock = threading.Lock()

# In-memory token bucket fallback state
_mem_lock = threading.Lock()
_mem_buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_updated)

# Lua script for atomic token bucket in Redis
# KEYS[1]: bucket key
# ARGV[1]: rate (tokens added per second, e.g. 2.0 = 120/min)
# ARGV[2]: capacity (burst limit, e.g. 30)
# ARGV[3]: requested tokens (e.g. 1)
# ARGV[4]: current timestamp (epoch seconds)
# Returns: {allowed (0 or 1), retry_after (seconds)}
LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if not tokens or not last_updated then
    tokens = capacity
    last_updated = now
else
    local delta = math.max(0, now - last_updated)
    tokens = math.min(capacity, tokens + delta * rate)
    last_updated = now
end

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HSET', key, 'tokens', tokens, 'last_updated', last_updated)
    redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)
    return {1, 0}
else
    local missing = requested - tokens
    local retry_after = missing / rate
    redis.call('HSET', key, 'tokens', tokens, 'last_updated', last_updated)
    redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)
    return {0, math.ceil(retry_after)}
end
"""


class RedisService:
    """Manages Redis connection, rate limiting, and exact response caching."""

    def __init__(self, redis_url: str | None = None, enabled: bool = True):
        self.redis_url = redis_url or settings.REDIS_URL
        self.enabled = enabled
        self._client: Any = None
        self._lua_script: Any = None
        self._redis_available: bool = True
        self._last_warn_time: float = 0.0

    def _get_client(self) -> Any:
        if not self.enabled:
            return None
        if self._client is None and self._redis_available:
            try:
                import redis
                self._client = redis.Redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=0.2,
                    socket_timeout=0.5,
                )
                self._client.ping()
                self._lua_script = self._client.register_script(LUA_TOKEN_BUCKET)
                self._redis_available = True
            except Exception as exc:
                self._redis_available = False
                self._log_redis_warning(f"Redis unavailable, failing open with in-memory fallback: {exc}")
                self._client = None
        return self._client

    def _log_redis_warning(self, msg: str) -> None:
        now = time.time()
        if now - self._last_warn_time > 30.0:  # Throttled warning
            logger.warning(msg)
            self._last_warn_time = now

    def check_rate_limit(
        self,
        identifier: str,
        rate: float = 2.0,  # 120 req/min
        capacity: int = 30,  # burst 30
        now: float | None = None,
    ) -> Tuple[bool, int]:
        """
        Check rate limit atomically using token bucket.
        Returns: (is_allowed, retry_after_seconds).
        If rate limited, increments global counter.
        """
        global _rate_limited_count
        current_time = time.time() if now is None else now
        key = f"relay:ratelimit:{identifier}"

        client = self._get_client()
        if client is not None and self._lua_script is not None:
            try:
                res = self._lua_script(
                    keys=[key],
                    args=[rate, capacity, 1, current_time],
                )
                allowed = bool(res[0] == 1)
                retry_after = int(res[1])
                if not allowed:
                    with _metrics_lock:
                        _rate_limited_count += 1
                return allowed, retry_after
            except Exception as exc:
                self._redis_available = False
                self._log_redis_warning(f"Redis rate limiter error, falling open: {exc}")

        # In-memory token bucket fallback (fail-open protection)
        with _mem_lock:
            tokens, last_updated = _mem_buckets.get(identifier, (float(capacity), current_time))
            delta = max(0.0, current_time - last_updated)
            tokens = min(float(capacity), tokens + delta * rate)

            if tokens >= 1.0:
                _mem_buckets[identifier] = (tokens - 1.0, current_time)
                return True, 0
            else:
                retry_after = max(1, int((1.0 - tokens) / rate))
                _mem_buckets[identifier] = (tokens, current_time)
                with _metrics_lock:
                    _rate_limited_count += 1
                return False, retry_after

    def get_cached_response(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Exact-match response cache (SHA-256 of normalized prompt)."""
        client = self._get_client()
        if client is None:
            return None

        normalized = prompt.strip().encode("utf-8")
        prompt_hash = hashlib.sha256(normalized).hexdigest()
        cache_key = f"relay:cache:{prompt_hash}"

        try:
            cached_data = client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as exc:
            self._log_redis_warning(f"Redis cache read error, failing open: {exc}")
        return None

    def set_cached_response(
        self, prompt: str, data: Dict[str, Any], ttl_seconds: int = 1800
    ) -> None:
        """Cache response with 30-minute default TTL."""
        client = self._get_client()
        if client is None:
            return

        normalized = prompt.strip().encode("utf-8")
        prompt_hash = hashlib.sha256(normalized).hexdigest()
        cache_key = f"relay:cache:{prompt_hash}"

        try:
            client.setex(cache_key, ttl_seconds, json.dumps(data))
        except Exception as exc:
            self._log_redis_warning(f"Redis cache write error, failing open: {exc}")

    @staticmethod
    def get_rate_limited_count() -> int:
        with _metrics_lock:
            return _rate_limited_count

    @staticmethod
    def reset_metrics() -> None:
        global _rate_limited_count
        with _metrics_lock:
            _rate_limited_count = 0
        with _mem_lock:
            _mem_buckets.clear()


redis_service = RedisService()
