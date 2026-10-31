"""
Tests for Redis token-bucket limiter, exact-match cache,
and fail-open in-memory resilience when Redis is down.
"""

from app.redis_client import RedisService, redis_service


class FakeRedisClient:
    """Mock Redis client for testing Redis-backed caching and Lua scripts."""

    def __init__(self):
        self.store = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value

    def ping(self):
        return True


def test_in_memory_token_bucket_rate_limiter():
    """Verify token bucket limiter allows burst up to capacity and denies excess."""
    limiter = RedisService(enabled=False)  # Force in-memory fallback
    identifier = "test-client-ip"

    # Burst of 5 requests with capacity 5
    for _ in range(5):
        allowed, retry_after = limiter.check_rate_limit(
            identifier=identifier, rate=1.0, capacity=5, now=100.0
        )
        assert allowed is True
        assert retry_after == 0

    # 6th request immediately exceeds burst capacity
    allowed6, retry_after6 = limiter.check_rate_limit(
        identifier=identifier, rate=1.0, capacity=5, now=100.0
    )
    assert allowed6 is False
    assert retry_after6 >= 1

    # After 1 second, 1 token refilled
    allowed7, _ = limiter.check_rate_limit(identifier=identifier, rate=1.0, capacity=5, now=101.0)
    assert allowed7 is True


def test_redis_down_fail_open_does_not_crash():
    """When Redis is completely unreachable, rate limit and cache fail open."""
    bad_service = RedisService(redis_url="redis://invalid-host-that-does-not-exist:6379/0")

    # Rate limiting should fail open to in-memory limiter without raising
    allowed, retry_after = bad_service.check_rate_limit("client-123", rate=10.0, capacity=10)
    assert allowed is True

    # Cache read/write should safely return None / no-op
    cached = bad_service.get_cached_response("hello")
    assert cached is None
    bad_service.set_cached_response("hello", {"data": 123})


def test_api_rate_limiting_429_with_retry_after(client):
    """Verify API returns HTTP 429 with Retry-After header when rate limit exceeded."""
    redis_service.reset_metrics()

    # Exhaust capacity (burst 30) by sending 45 rapid requests
    headers = {"Authorization": "bearer rate-limit-test-key-unique"}
    blocked = False
    blocked_res = None

    for _ in range(45):
        res = client.post("/v1/route", json={"prompt": "Short test prompt"}, headers=headers)
        if res.status_code == 429:
            blocked = True
            blocked_res = res
            break

    assert blocked is True
    assert blocked_res is not None
    assert blocked_res.status_code == 429
    assert "Retry-After" in blocked_res.headers
    assert int(blocked_res.headers["Retry-After"]) >= 1


def test_response_cache_hit_and_cost_zero(client, monkeypatch):
    """Verify exact match response cache returns 0 cost and cache_hit=True."""
    prompt = "Unique prompt for caching test verification 12345"
    fake_redis = FakeRedisClient()

    monkeypatch.setattr(redis_service, "_client", fake_redis)
    monkeypatch.setattr(redis_service, "enabled", True)
    monkeypatch.setattr(redis_service, "_redis_available", True)

    # First call: cache miss
    res1 = client.post("/v1/route", json={"prompt": prompt})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["cache_hit"] is False
    assert data1["cost_usd"] > 0.0

    # Second call: cache hit via fake_redis
    res2 = client.post("/v1/route", json={"prompt": prompt})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["cache_hit"] is True
    assert data2["cost_usd"] == 0.0
    assert data2["response"] == data1["response"]
