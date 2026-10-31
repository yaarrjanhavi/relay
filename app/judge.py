"""
Optional LLM-as-Judge auto-feedback grading using the LARGE tier.
Evaluates non-high-stakes responses against a strict rubric.
"""

import json
import logging
import random
import re
import uuid
from typing import Tuple

from app.config import compute_cost_usd, settings
from app.database import transaction
from app.outbox import enqueue_feedback_outbox
from app.provider import BaseProvider, get_provider

logger = logging.getLogger("relay.judge")

RUBRIC_SYSTEM_PROMPT = """You are an expert AI evaluator assessing the quality of an LLM response.
Prompt: {prompt}
Response: {response}

Evaluation criteria:
1. Direct relevance: Does the response directly address what was asked?
2. Factual and technical accuracy: Are there hallucinations or critical errors?
3. Clarity and completeness: Is the explanation clear and appropriately detailed?

You MUST respond strictly with a valid JSON object in this format:
{"good": true}
or
{"good": false}
Do not include markdown codeblocks or any additional commentary.
"""


def should_sample_judge(category: str, sample_rate: float | None = None) -> bool:
    """
    Decides whether a request should be auto-judged.
    SAFETY RULE: category 'high_stakes' is NEVER auto-judged.
    """
    if category == "high_stakes":
        return False

    rate = settings.JUDGE_SAMPLE_RATE if sample_rate is None else sample_rate
    if rate <= 0.0:
        return False

    return random.random() < rate


def parse_judge_output(text: str) -> bool:
    """Extract {"good": true|false} from LLM output."""
    clean = text.strip()
    match = re.search(r'\{[^{}]*"good"\s*:\s*(true|false)[^{}]*\}', clean, re.IGNORECASE)
    if match:
        try:
            data = json.loads(match.group(0))
            return bool(data.get("good", False))
        except Exception:
            pass
    # Fallback substring check
    if '"good": true' in clean.lower() or '"good":true' in clean.lower():
        return True
    return False


async def run_judge_evaluation(
    request_id: str,
    prompt: str,
    response_text: str,
    category: str,
    tier: str,
    provider: BaseProvider | None = None,
    now: float | None = None,
) -> Tuple[bool, float]:
    """
    Evaluate response with LARGE tier, insert feedback with source='judge',
    and enqueue outbox event for posterior update.
    Returns (good, judge_cost_usd).
    """
    # SAFETY RULE: high_stakes responses are NEVER graded or fed back
    if category == "high_stakes":
        logger.info("Skipping judge evaluation for high_stakes category")
        return False, 0.0

    active_provider = provider or get_provider()
    model_id = settings.GEMINI_MODEL_LARGE
    rubric_prompt = RUBRIC_SYSTEM_PROMPT.format(prompt=prompt, response=response_text)

    try:
        resp = await active_provider.generate(model_id, rubric_prompt)
        judge_cost = compute_cost_usd("large", resp.tokens_in, resp.tokens_out)
        is_good = parse_judge_output(resp.text)

        event_id = str(uuid.uuid4())
        with transaction() as conn:
            # Check if feedback already recorded
            existing = conn.execute(
                "SELECT reward FROM feedback WHERE request_id = ?", (request_id,)
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO feedback (request_id, reward, source, created_at)
                    VALUES (?, ?, 'judge', ?)
                    """,
                    (request_id, 1 if is_good else 0, now),
                )
                enqueue_feedback_outbox(
                    conn=conn,
                    event_id=event_id,
                    request_id=request_id,
                    category=category,
                    tier=tier,
                    thumbs_up=is_good,
                    source="judge",
                    now=now,
                )
                logger.info(
                    "Judge evaluated request %s: good=%s, cost=$%.6f",
                    request_id,
                    is_good,
                    judge_cost,
                )

        return is_good, judge_cost
    except Exception as exc:
        logger.warning("Judge evaluation failed for request %s: %s", request_id, exc)
        return False, 0.0
