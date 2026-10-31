"""
API Endpoint tests for /healthz, /v1/route, /v1/feedback, /v1/stats, and /v1/history.
"""

from app.database import get_connection


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_route_endpoint_valid_and_validation(client):
    # Valid route
    res = client.post("/v1/route", json={"prompt": "def quicksort(arr): return arr"})
    assert res.status_code == 200
    data = res.json()
    assert "request_id" in data
    assert data["category"] == "code"
    assert data["tier"] in ["small", "medium", "large"]
    assert data["cost_usd"] >= 0.0
    assert data["latency_ms"] >= 0.0
    assert data["fallback_used"] is False
    assert data["cache_hit"] is False
    assert len(data["response"]) > 0

    # Validation: empty prompt rejected
    bad_res = client.post("/v1/route", json={"prompt": ""})
    assert bad_res.status_code == 422


def test_feedback_success_and_idempotence(client):
    # Route a request first
    route_res = client.post("/v1/route", json={"prompt": "Calculate 15 * 87"})
    assert route_res.status_code == 200
    req_id = route_res.json()["request_id"]
    tier = route_res.json()["tier"]

    # Check initial alpha for (math, tier)
    with get_connection() as conn:
        arm_before = conn.execute(
            "SELECT alpha, beta FROM arms WHERE category = 'math' AND tier = ?",
            (tier,),
        ).fetchone()
        initial_alpha = arm_before["alpha"]

    # First feedback call
    fb_res1 = client.post("/v1/feedback", json={"request_id": req_id, "thumbs_up": True})
    assert fb_res1.status_code == 200
    assert fb_res1.json() == {"status": "accepted", "request_id": req_id}

    # Verify posterior updated
    with get_connection() as conn:
        arm_after = conn.execute(
            "SELECT alpha, beta FROM arms WHERE category = 'math' AND tier = ?",
            (tier,),
        ).fetchone()
        assert arm_after["alpha"] == initial_alpha + 1.0

    # Second feedback call -> idempotent duplicate_ignored
    fb_res2 = client.post("/v1/feedback", json={"request_id": req_id, "thumbs_up": True})
    assert fb_res2.status_code == 200
    assert fb_res2.json() == {"status": "duplicate_ignored", "request_id": req_id}

    # Verify posterior was NOT incremented again
    with get_connection() as conn:
        arm_after2 = conn.execute(
            "SELECT alpha, beta FROM arms WHERE category = 'math' AND tier = ?",
            (tier,),
        ).fetchone()
        assert arm_after2["alpha"] == arm_after["alpha"]


def test_feedback_unknown_request_404(client):
    res = client.post("/v1/feedback", json={"request_id": "non-existent-id", "thumbs_up": True})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_stats_and_history_endpoints(client):
    # Generate 2 requests
    client.post("/v1/route", json={"prompt": "Summarize this article on quantum computing"})
    r2 = client.post("/v1/route", json={"prompt": "Solve x^2 - 4 = 0"})
    client.post("/v1/feedback", json={"request_id": r2.json()["request_id"], "thumbs_up": True})

    # Stats
    stats_res = client.get("/v1/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["request_count"] >= 2
    assert stats["total_cost_usd"] > 0.0
    # 5 categories * 3 tiers = 15 arms
    assert len(stats["posteriors"]) == 15
    for arm in stats["posteriors"]:
        assert arm["alpha"] >= 1.0
        assert arm["beta"] >= 1.0
        assert 0.0 <= arm["mean"] <= 1.0
        assert len(arm["ci90"]) == 2

    # History
    hist_res = client.get("/v1/history")
    assert hist_res.status_code == 200
    history_items = hist_res.json()["history"]
    assert len(history_items) >= 1
    assert "mean" in history_items[0]
