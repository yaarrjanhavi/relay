"""
Pure mathematical functions for Bayesian Thompson Sampling Bandit with Time Decay.
"""

import math
import random
import time
from typing import Dict, NamedTuple, Tuple

from app.config import TIERS, get_tier_relative_cost, settings


class PosteriorStats(NamedTuple):
    category: str
    tier: str
    alpha: float
    beta: float
    mean: float
    variance: float
    ci90_lower: float
    ci90_upper: float
    evidence: float
    cold_start: bool


def compute_decay(
    alpha_stored: float,
    beta_stored: float,
    updated_at: float,
    now: float | None = None,
    retention_per_day: float = 0.98,
) -> Tuple[float, float]:
    """
    Apply time decay toward the Beta(1,1) prior.
    Formula:
        alpha_eff = 1 + retention^(days) * (alpha_stored - 1)
        beta_eff  = 1 + retention^(days) * (beta_stored  - 1)

    Uses `now is None` check so timestamp 0 (Unix epoch) is valid and testable.
    """
    current_time = time.time() if now is None else now
    elapsed_seconds = max(0.0, current_time - updated_at)
    days_since_update = elapsed_seconds / 86400.0

    retention_factor = retention_per_day**days_since_update

    alpha_eff = 1.0 + retention_factor * (alpha_stored - 1.0)
    beta_eff = 1.0 + retention_factor * (beta_stored - 1.0)

    # Bound lower limit to prior parameter 1.0
    return max(1.0, alpha_eff), max(1.0, beta_eff)


def compute_credible_interval(alpha: float, beta: float) -> Tuple[float, float, float, float, bool]:
    """
    Compute mean, variance, 90% credible interval (clipped to [0,1]),
    evidence (alpha + beta - 2), and cold start indicator (< 10).
    """
    total = alpha + beta
    mean = alpha / total
    variance = (alpha * beta) / ((total**2) * (total + 1.0))
    std = math.sqrt(max(0.0, variance))

    # CI90 = mean +/- 1.645 * std
    ci90_lower = max(0.0, min(1.0, mean - 1.645 * std))
    ci90_upper = max(0.0, min(1.0, mean + 1.645 * std))
    evidence = max(0.0, alpha + beta - 2.0)
    cold_start = evidence < 10.0

    return mean, variance, ci90_lower, ci90_upper, cold_start


def sample_tier(
    category: str,
    arms_data: Dict[str, Tuple[float, float]],  # tier -> (alpha_eff, beta_eff)
    lambda_param: float | None = None,
    rng: random.Random | None = None,
) -> Tuple[str, Dict[str, float]]:
    """
    Thompson Sampling with cost penalty.
    Score = theta - LAMBDA * (tier_cost / max_tier_cost)
    Highest score wins.

    SAFETY RULE: category 'high_stakes' ALWAYS routes to 'large' and NEVER explores.
    """
    if category == "high_stakes":
        # Non-negotiable safety rule: always large, never explore
        return "large", {"large": 1.0}

    lam = settings.LAMBDA if lambda_param is None else lambda_param
    generator = random if rng is None else rng

    scores: Dict[str, float] = {}
    best_tier = "large"
    best_score = -float("inf")

    # Evaluate all available tiers in defined order
    for tier in TIERS:
        alpha, beta = arms_data.get(tier, (1.0, 1.0))
        # Ensure alpha and beta are positive
        alpha_val = max(1e-5, alpha)
        beta_val = max(1e-5, beta)

        # Draw theta ~ Beta(alpha, beta)
        theta = generator.betavariate(alpha_val, beta_val)
        relative_cost = get_tier_relative_cost(tier)
        score = theta - (lam * relative_cost)
        scores[tier] = score

        if score > best_score:
            best_score = score
            best_tier = tier

    return best_tier, scores


def update_posterior(
    category: str,
    alpha_stored: float,
    beta_stored: float,
    updated_at: float,
    thumbs_up: bool,
    now: float | None = None,
    retention_per_day: float = 0.98,
) -> Tuple[float, float, float]:
    """
    Decays stored posterior to current time, then applies feedback:
    thumbs up => alpha += 1; thumbs down => beta += 1.

    SAFETY RULE: feedback on 'high_stakes' NEVER modifies any posterior.
    Returns (new_alpha, new_beta, updated_at).
    """
    current_time = time.time() if now is None else now

    if category == "high_stakes":
        # Non-negotiable safety rule: high_stakes never updates posteriors
        return alpha_stored, beta_stored, current_time

    # Apply time decay first
    alpha_eff, beta_eff = compute_decay(
        alpha_stored,
        beta_stored,
        updated_at,
        now=current_time,
        retention_per_day=retention_per_day,
    )

    if thumbs_up:
        new_alpha = alpha_eff + 1.0
        new_beta = beta_eff
    else:
        new_alpha = alpha_eff
        new_beta = beta_eff + 1.0

    return new_alpha, new_beta, current_time
