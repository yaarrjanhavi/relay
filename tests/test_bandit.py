"""
Unit tests for bandit math, time decay, credible intervals, and sampling.
"""

import math
import random

from app.bandit import (
    compute_credible_interval,
    compute_decay,
    sample_tier,
    update_posterior,
)


def test_decay_math_exact():
    """Verify decay formula: 1 + 0.98^(days) * (val - 1)."""
    # 0 days elapsed -> identical to stored
    a, b = compute_decay(10.0, 5.0, updated_at=1000.0, now=1000.0, retention_per_day=0.98)
    assert math.isclose(a, 10.0)
    assert math.isclose(b, 5.0)

    # Exactly 1 day (86400s) elapsed
    a1, b1 = compute_decay(11.0, 1.0, updated_at=0.0, now=86400.0, retention_per_day=0.98)
    # alpha_eff = 1 + 0.98^1 * (11 - 1) = 1 + 9.8 = 10.8
    assert math.isclose(a1, 10.8, rel_tol=1e-5)
    assert math.isclose(b1, 1.0, rel_tol=1e-5)


def test_decay_now_injectable_epoch_zero():
    """Verify decay works when now is 0 (Unix epoch) without falsy pitfalls."""
    a, b = compute_decay(5.0, 5.0, updated_at=0.0, now=0.0, retention_per_day=0.98)
    assert math.isclose(a, 5.0)
    assert math.isclose(b, 5.0)


def test_decay_approaches_prior_asymptotically():
    """After many days, eff parameters should asymptotically decay to Beta(1,1)."""
    # 365 days later
    a, b = compute_decay(100.0, 100.0, updated_at=0.0, now=365 * 86400.0, retention_per_day=0.98)
    assert a >= 1.0
    assert b >= 1.0
    assert a < 1.1
    assert b < 1.1


def test_credible_interval_cold_start():
    """Verify analytical mean, variance, CI90, and cold start badge flag."""
    # Prior Beta(1,1): evidence = 1 + 1 - 2 = 0 (< 10 -> cold start)
    mean, var, ci_low, ci_high, cold_start = compute_credible_interval(1.0, 1.0)
    assert math.isclose(mean, 0.5)
    assert math.isclose(var, 1.0 / 12.0)
    assert cold_start is True
    assert 0.0 <= ci_low < 0.5 < ci_high <= 1.0

    # Evidence >= 10: e.g. alpha=10, beta=4 -> total=14, evidence=12 -> not cold start
    mean2, var2, ci_low2, ci_high2, cold_start2 = compute_credible_interval(10.0, 4.0)
    assert cold_start2 is False
    assert math.isclose(mean2, 10.0 / 14.0)
    assert ci_low2 < mean2 < ci_high2


def test_thompson_sampling_deterministic_with_rng():
    """Verify Thompson sampling behavior is deterministic given fixed RNG."""
    rng1 = random.Random(42)
    rng2 = random.Random(42)

    arms = {
        "small": (10.0, 1.0),
        "medium": (1.0, 1.0),
        "large": (1.0, 1.0),
    }

    tier1, scores1 = sample_tier("code", arms, lambda_param=0.25, rng=rng1)
    tier2, scores2 = sample_tier("code", arms, lambda_param=0.25, rng=rng2)

    assert tier1 == tier2
    assert scores1 == scores2
    # Small has high alpha (10, 1) and lowest cost penalty -> should easily win
    assert tier1 == "small"


def test_posterior_update_thumbs_up_and_down():
    """Verify thumbs up increments alpha, thumbs down increments beta."""
    # Thumbs up
    a_up, b_up, _ = update_posterior("code", 1.0, 1.0, 100.0, thumbs_up=True, now=100.0)
    assert math.isclose(a_up, 2.0)
    assert math.isclose(b_up, 1.0)

    # Thumbs down
    a_down, b_down, _ = update_posterior("code", 1.0, 1.0, 100.0, thumbs_up=False, now=100.0)
    assert math.isclose(a_down, 1.0)
    assert math.isclose(b_down, 2.0)
