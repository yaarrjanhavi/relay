"""
Tests for Phase 5: Honest Benchmark replay, 70/30 split,
multi-seed determinism, and comparison metrics.
"""

from app.benchmark import run_benchmark


def test_benchmark_simulated_mode():
    """Verify simulated benchmark returns structured metrics for all 4 strategies."""
    res = run_benchmark(mode="simulated", num_seeds=3, simulated_queries=200)

    assert res.mode == "simulated"
    assert res.seeds == 3
    assert res.train_size == 140
    assert res.test_size == 60

    strats = ["router", "always_large", "always_small", "random"]
    for s in strats:
        assert s in res.strategies
        metric = res.strategies[s]
        assert 0.0 <= metric.mean_quality <= 1.0
        assert metric.mean_cost >= 0.0
        assert metric.std_quality >= 0.0

    # Always large has 0% cost saved
    assert abs(res.strategies["always_large"].mean_cost_saved_pct) < 1e-4

    # Router should save significant cost relative to always_large
    assert res.strategies["router"].mean_cost < res.strategies["always_large"].mean_cost
    assert res.strategies["router"].mean_cost_saved_pct > 30.0


def test_benchmark_real_mode():
    """Verify real dataset benchmark on held-out 30% split across seeds."""
    res = run_benchmark(mode="real", num_seeds=3)

    assert res.mode == "real"
    assert res.seeds == 3
    assert res.train_size == 140
    assert res.test_size == 60

    router_metric = res.strategies["router"]
    large_metric = res.strategies["always_large"]
    small_metric = res.strategies["always_small"]

    # Router quality is substantially higher than always-small
    assert router_metric.mean_quality > small_metric.mean_quality
    # Router cost is substantially cheaper than always-large
    assert router_metric.mean_cost < large_metric.mean_cost
    assert router_metric.mean_cost_saved_pct > 25.0


def test_benchmark_api_endpoint(client):
    """Verify POST /v1/benchmark/replay endpoint works for both modes."""
    # Simulated
    sim_res = client.post("/v1/benchmark/replay?mode=simulated&seeds=2")
    assert sim_res.status_code == 200
    data = sim_res.json()
    assert data["mode"] == "simulated"
    assert "router" in data["strategies"]

    # Real
    real_res = client.post("/v1/benchmark/replay?mode=real&seeds=2")
    assert real_res.status_code == 200
    data_real = real_res.json()
    assert data_real["mode"] == "real"
    assert "router" in data_real["strategies"]
