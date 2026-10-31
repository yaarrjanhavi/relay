"""
Honest benchmark comparison module:
Evaluates Router vs Always-Large vs Always-Small vs Random across 10 random seeds
on held-out test data (70/30 train/test split).
Supports simulated ground-truth mode and real dataset mode.
"""

import json
import math
import os
import random
from typing import Dict, List, Tuple

from app.bandit import sample_tier, update_posterior
from app.config import compute_cost_usd, settings
from app.schemas import BenchmarkMetrics, BenchmarkResult

# Ground truth baseline probabilities per category x tier
TRUE_QUALITY: Dict[str, Dict[str, float]] = {
    "code": {"small": 0.55, "medium": 0.85, "large": 0.93},
    "math": {"small": 0.40, "medium": 0.75, "large": 0.92},
    "summarize": {"small": 0.85, "medium": 0.90, "large": 0.93},
    "chat": {"small": 0.88, "medium": 0.92, "large": 0.94},
    "high_stakes": {"small": 0.60, "medium": 0.80, "large": 0.95},
}

# Category mix for simulated mode
CATEGORY_MIX: Dict[str, float] = {
    "code": 0.30,
    "math": 0.20,
    "summarize": 0.15,
    "chat": 0.25,
    "high_stakes": 0.10,
}

EVAL_PROMPTS_PATH = os.path.join("data", "eval_prompts.json")
EVAL_GRADES_PATH = os.path.join("data", "eval_grades.json")


def compute_mean_and_std(values: List[float]) -> Tuple[float, float]:
    """Calculate mean and sample standard deviation."""
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean_val = sum(values) / n
    if n <= 1:
        return round(mean_val, 4), 0.0
    var = sum((x - mean_val) ** 2 for x in values) / (n - 1)
    std_val = math.sqrt(max(0.0, var))
    return round(mean_val, 4), round(std_val, 4)


def run_benchmark(
    mode: str = "simulated",
    num_seeds: int = 10,
    train_ratio: float = 0.70,
    simulated_queries: int = 1000,
) -> BenchmarkResult:
    """
    Executes honest benchmark across 10 random seeds with a 70/30 train/test split.
    Metrics are computed strictly on the held-out 30% test set.
    """
    strategies = ["router", "always_large", "always_small", "random"]
    seed_records: Dict[str, Dict[str, List[float]]] = {
        strat: {"quality": [], "cost": [], "cost_saved_pct": []} for strat in strategies
    }

    if mode == "real":
        # Load dataset
        if not os.path.exists(EVAL_PROMPTS_PATH) or not os.path.exists(EVAL_GRADES_PATH):
            raise FileNotFoundError("Eval datasets not found. Run build scripts first.")

        with open(EVAL_PROMPTS_PATH, "r", encoding="utf-8") as f:
            all_prompts = json.load(f)
        with open(EVAL_GRADES_PATH, "r", encoding="utf-8") as f:
            all_grades = json.load(f)

        total_items = len(all_prompts)
        train_count = int(total_items * train_ratio)
        test_count = total_items - train_count

        for seed in range(1, num_seeds + 1):
            rng = random.Random(seed)
            shuffled = list(all_prompts)
            rng.shuffle(shuffled)

            train_set = shuffled[:train_count]
            test_set = shuffled[train_count:]

            # Initial arms for router: Beta(1,1) per (category, tier)
            router_arms = {
                cat: {t: [1.0, 1.0] for t in ["small", "medium", "large"]}
                for cat in TRUE_QUALITY.keys()
            }

            # 1. Training Phase: Router learns online from train set
            for item in train_set:
                p_id = item["id"]
                category = item["category"]
                cat_arms = {t: tuple(router_arms[category][t]) for t in ["small", "medium", "large"]}
                selected_tier, _ = sample_tier(category, cat_arms, lambda_param=settings.LAMBDA, rng=rng)

                grade_info = all_grades.get(p_id, {}).get(selected_tier, {})
                reward = bool(grade_info.get("quality", 1))

                # Update router posterior (high_stakes safety rule applies)
                if category != "high_stakes":
                    a, b = router_arms[category][selected_tier]
                    new_a, new_b, _ = update_posterior(
                        category, a, b, updated_at=0.0, thumbs_up=reward, now=0.0
                    )
                    router_arms[category][selected_tier] = [new_a, new_b]

            # 2. Evaluation Phase on held-out test set
            large_total_cost = 0.0
            test_results: Dict[str, Dict[str, float]] = {
                strat: {"correct": 0, "cost": 0.0} for strat in strategies
            }

            for item in test_set:
                p_id = item["id"]
                category = item["category"]
                grades_for_item = all_grades[p_id]

                # Benchmark large cost for baseline
                large_info = grades_for_item["large"]
                large_total_cost += large_info["cost"]

                # Router choice (Thompson sampling with learned posteriors)
                cat_arms = {t: tuple(router_arms[category][t]) for t in ["small", "medium", "large"]}
                router_tier, _ = sample_tier(category, cat_arms, lambda_param=settings.LAMBDA, rng=rng)

                # Always Large
                large_tier = "large"

                # Always Small (SAFETY RULE: high_stakes routes to large)
                small_tier = "large" if category == "high_stakes" else "small"

                # Random (SAFETY RULE: high_stakes routes to large)
                random_tier = "large" if category == "high_stakes" else rng.choice(["small", "medium", "large"])

                chosen_tiers = {
                    "router": router_tier,
                    "always_large": large_tier,
                    "always_small": small_tier,
                    "random": random_tier,
                }

                for strat, tier in chosen_tiers.items():
                    info = grades_for_item[tier]
                    test_results[strat]["correct"] += info["quality"]
                    test_results[strat]["cost"] += info["cost"]

            # Record metrics for this seed
            for strat in strategies:
                q = test_results[strat]["correct"] / test_count
                c = test_results[strat]["cost"]
                saved_pct = ((large_total_cost - c) / large_total_cost * 100.0) if large_total_cost > 0 else 0.0

                seed_records[strat]["quality"].append(q)
                seed_records[strat]["cost"].append(c)
                seed_records[strat]["cost_saved_pct"].append(saved_pct)

    else:
        # Simulated Mode
        total_queries = simulated_queries
        train_count = int(total_queries * train_ratio)
        test_count = total_queries - train_count

        cats = list(CATEGORY_MIX.keys())
        cat_weights = [CATEGORY_MIX[c] for c in cats]

        for seed in range(1, num_seeds + 1):
            rng = random.Random(seed)

            # Generate synthetic queries matching category mix
            queries = rng.choices(cats, weights=cat_weights, k=total_queries)
            train_queries = queries[:train_count]
            test_queries = queries[train_count:]

            router_arms = {
                cat: {t: [1.0, 1.0] for t in ["small", "medium", "large"]}
                for cat in TRUE_QUALITY.keys()
            }

            # Train Phase
            for category in train_queries:
                cat_arms = {t: tuple(router_arms[category][t]) for t in ["small", "medium", "large"]}
                selected_tier, _ = sample_tier(category, cat_arms, lambda_param=settings.LAMBDA, rng=rng)

                # Simulated reward draw from TRUE_QUALITY
                success_prob = TRUE_QUALITY[category][selected_tier]
                reward = rng.random() < success_prob

                if category != "high_stakes":
                    a, b = router_arms[category][selected_tier]
                    new_a, new_b, _ = update_posterior(
                        category, a, b, updated_at=0.0, thumbs_up=reward, now=0.0
                    )
                    router_arms[category][selected_tier] = [new_a, new_b]

            # Test Phase
            large_total_cost = 0.0
            test_results = {strat: {"correct": 0, "cost": 0.0} for strat in strategies}

            for category in test_queries:
                # Approximate representative tokens: in=50, out=150
                tokens_in = 50
                tokens_out = 150

                large_cost = compute_cost_usd("large", tokens_in, tokens_out)
                large_total_cost += large_cost

                # Router tier
                cat_arms = {t: tuple(router_arms[category][t]) for t in ["small", "medium", "large"]}
                router_tier, _ = sample_tier(category, cat_arms, lambda_param=settings.LAMBDA, rng=rng)

                # Strategy tier choices with safety rule
                chosen_tiers = {
                    "router": router_tier,
                    "always_large": "large",
                    "always_small": "large" if category == "high_stakes" else "small",
                    "random": "large" if category == "high_stakes" else rng.choice(["small", "medium", "large"]),
                }

                for strat, tier in chosen_tiers.items():
                    success_prob = TRUE_QUALITY[category][tier]
                    success = 1 if rng.random() < success_prob else 0
                    tier_cost = compute_cost_usd(tier, tokens_in, tokens_out)

                    test_results[strat]["correct"] += success
                    test_results[strat]["cost"] += tier_cost

            # Record seed metrics
            for strat in strategies:
                q = test_results[strat]["correct"] / test_count
                c = test_results[strat]["cost"]
                saved_pct = ((large_total_cost - c) / large_total_cost * 100.0) if large_total_cost > 0 else 0.0

                seed_records[strat]["quality"].append(q)
                seed_records[strat]["cost"].append(c)
                seed_records[strat]["cost_saved_pct"].append(saved_pct)

    # Aggregate across seeds: mean +/- std
    aggregated: Dict[str, BenchmarkMetrics] = {}
    for strat in strategies:
        mean_q, std_q = compute_mean_and_std(seed_records[strat]["quality"])
        mean_c, std_c = compute_mean_and_std(seed_records[strat]["cost"])
        mean_s, std_s = compute_mean_and_std(seed_records[strat]["cost_saved_pct"])

        aggregated[strat] = BenchmarkMetrics(
            mean_quality=mean_q,
            std_quality=std_q,
            mean_cost=mean_c,
            std_cost=std_c,
            mean_cost_saved_pct=mean_s,
            std_cost_saved_pct=std_s,
        )

    return BenchmarkResult(
        mode=mode,
        seeds=num_seeds,
        train_size=train_count,
        test_size=test_count,
        strategies=aggregated,
        raw_results=seed_records,
    )
