"""
Offline and repeatable evaluation grades builder.
Evaluates prompts on small, medium, and large tiers, grades each answer,
and caches results to data/eval_grades.json so benchmarks are fast, repeatable, and free.
"""

import asyncio
import hashlib
import json
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import Any, Dict

from app.config import compute_cost_usd, settings
from app.judge import RUBRIC_SYSTEM_PROMPT, parse_judge_output
from app.provider import get_provider

EVAL_PROMPTS_PATH = os.path.join("data", "eval_prompts.json")
EVAL_GRADES_PATH = os.path.join("data", "eval_grades.json")

# Ground truth baseline probabilities per category x tier
TRUE_QUALITY: Dict[str, Dict[str, float]] = {
    "code": {"small": 0.55, "medium": 0.85, "large": 0.93},
    "math": {"small": 0.40, "medium": 0.75, "large": 0.92},
    "summarize": {"small": 0.85, "medium": 0.90, "large": 0.93},
    "chat": {"small": 0.88, "medium": 0.92, "large": 0.94},
    "high_stakes": {"small": 0.60, "medium": 0.80, "large": 0.95},
}


def deterministic_grade(prompt_id: str, category: str, tier: str, prompt: str) -> Dict[str, Any]:
    """Deterministic simulated grade when running offline without Gemini API key."""
    # Deterministic hash in [0, 1]
    h = hashlib.sha256(f"{prompt_id}:{tier}".encode()).hexdigest()
    val = int(h[:8], 16) / 0xFFFFFFFF

    prob = TRUE_QUALITY.get(category, {}).get(tier, 0.75)
    quality = 1 if val < prob else 0

    tokens_in = max(10, len(prompt) // 4)
    # Output length scales by tier
    if tier == "small":
        tokens_out = max(20, tokens_in * 2)
    elif tier == "medium":
        tokens_out = max(35, int(tokens_in * 2.8))
    else:
        tokens_out = max(50, int(tokens_in * 3.5))

    cost = compute_cost_usd(tier, tokens_in, tokens_out)

    return {
        "quality": quality,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": cost,
    }


async def build_grades() -> None:
    if not os.path.exists(EVAL_PROMPTS_PATH):
        print(f"Error: {EVAL_PROMPTS_PATH} not found. Run scripts/build_eval_prompts.py first.")
        sys.exit(1)

    with open(EVAL_PROMPTS_PATH, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    provider = get_provider()
    use_live_api = bool(settings.GEMINI_API_KEY)
    print(f"Building eval grades for {len(prompts)} prompts (Live API: {use_live_api})...")

    grades: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for i, item in enumerate(prompts):
        p_id = item["id"]
        prompt = item["prompt"]
        category = item["category"]
        grades[p_id] = {}

        for tier in ["small", "medium", "large"]:
            if not use_live_api:
                grades[p_id][tier] = deterministic_grade(p_id, category, tier, prompt)
            else:
                try:
                    # Live generation
                    model_id = (
                        settings.GEMINI_MODEL_SMALL
                        if tier == "small"
                        else settings.GEMINI_MODEL_MEDIUM
                        if tier == "medium"
                        else settings.GEMINI_MODEL_LARGE
                    )
                    resp = await provider.generate(model_id, prompt)

                    # Grade with large tier judge
                    rubric = RUBRIC_SYSTEM_PROMPT.format(prompt=prompt, response=resp.text)
                    judge_resp = await provider.generate(settings.GEMINI_MODEL_LARGE, rubric)
                    is_good = 1 if parse_judge_output(judge_resp.text) else 0

                    cost = compute_cost_usd(tier, resp.tokens_in, resp.tokens_out)
                    grades[p_id][tier] = {
                        "quality": is_good,
                        "tokens_in": resp.tokens_in,
                        "tokens_out": resp.tokens_out,
                        "cost": cost,
                    }
                except Exception as exc:
                    print(f"Live grading failed for {p_id}/{tier}: {exc}. Using deterministic grade.")
                    grades[p_id][tier] = deterministic_grade(p_id, category, tier, prompt)

        if (i + 1) % 25 == 0 or (i + 1) == len(prompts):
            print(f"Progress: {i + 1}/{len(prompts)} prompts graded.")

    with open(EVAL_GRADES_PATH, "w", encoding="utf-8") as f:
        json.dump(grades, f, indent=2)

    print(f"Saved evaluation grades to {EVAL_GRADES_PATH}")


if __name__ == "__main__":
    asyncio.run(build_grades())
