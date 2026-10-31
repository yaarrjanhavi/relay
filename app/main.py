"""
FastAPI Application for Relay: Self-learning LLM Router.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from app.bandit import (
    compute_credible_interval,
    compute_decay,
    sample_tier,
    update_posterior,
)
from app.classifier import classify_prompt
from app.config import (
    compute_cost_usd,
    settings,
)
from app.database import get_connection, init_db, transaction
from app.provider import (
    BaseProvider,
    NonRetryableProviderError,
    ProviderError,
    get_provider,
)
from app.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    HistoryPoint,
    HistoryResponse,
    PosteriorArmStat,
    RouteRequest,
    RouteResponse,
    StatsResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize database schema on startup."""
    init_db()
    yield


app = FastAPI(
    title="Relay: Self-Learning LLM Router",
    description="Bayesian Thompson Sampling LLM Router across Gemini tiers",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_model_for_tier(tier: str) -> str:
    if tier == "small":
        return settings.GEMINI_MODEL_SMALL
    elif tier == "medium":
        return settings.GEMINI_MODEL_MEDIUM
    return settings.GEMINI_MODEL_LARGE


def get_fallback_chain(start_tier: str) -> list[str]:
    tiers = ["small", "medium", "large"]
    try:
        idx = tiers.index(start_tier)
        return tiers[idx:]
    except ValueError:
        return ["large"]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/v1/route", response_model=RouteResponse)
async def route_prompt(
    request: RouteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    provider: BaseProvider = Depends(get_provider),
) -> RouteResponse:
    """
    Route a prompt to the optimal Gemini tier using Thompson Sampling,
    with high-stakes safety override and fallback escalation.
    """
    active_provider = provider

    # 1. Classify prompt
    category, confidence = classify_prompt(request.prompt)

    # 2. Select initial tier
    if category == "high_stakes":
        selected_tier = "large"
    else:
        # Read current decayed posteriors for this category
        arms_data: dict[str, tuple[float, float]] = {}
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT tier, alpha, beta, updated_at FROM arms WHERE category = ?",
                (category,),
            )
            now = time.time()
            for row in cursor.fetchall():
                t = row["tier"]
                a_eff, b_eff = compute_decay(
                    row["alpha"],
                    row["beta"],
                    row["updated_at"],
                    now=now,
                    retention_per_day=settings.RETENTION_PER_DAY,
                )
                arms_data[t] = (a_eff, b_eff)

        selected_tier, _ = sample_tier(category, arms_data, lambda_param=settings.LAMBDA)

    # 3. Fallback chain escalation
    chain = get_fallback_chain(selected_tier)
    provider_resp = None
    served_tier = selected_tier
    fallback_used = False
    last_error: Exception | None = None

    for candidate_tier in chain:
        model_id = get_model_for_tier(candidate_tier)
        try:
            provider_resp = await active_provider.generate(model_id, request.prompt)
            served_tier = candidate_tier
            if candidate_tier != selected_tier:
                fallback_used = True
            break
        except NonRetryableProviderError:
            raise
        except ProviderError as pe:
            last_error = pe
            continue

    if provider_resp is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"All provider tiers in fallback chain failed: {last_error}",
        )

    # 4. Calculate cost
    cost_usd = compute_cost_usd(served_tier, provider_resp.tokens_in, provider_resp.tokens_out)
    request_id = str(uuid.uuid4())
    now = time.time()

    # 5. Persist request record
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO requests (id, category, tier, cost_usd, tokens_in, tokens_out, latency_ms, cache_hit, fallback_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                category,
                served_tier,
                cost_usd,
                provider_resp.tokens_in,
                provider_resp.tokens_out,
                provider_resp.latency_ms,
                0,
                1 if fallback_used else 0,
                now,
            ),
        )

    return RouteResponse(
        request_id=request_id,
        category=category,
        confidence=confidence,
        tier=served_tier,
        model_id=provider_resp.model_id,
        fallback_used=fallback_used,
        cache_hit=False,
        cost_usd=cost_usd,
        latency_ms=provider_resp.latency_ms,
        response=provider_resp.text,
    )


@app.post("/v1/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    """
    Submit thumbs up/down feedback for a completed request.
    Idempotent per request_id.
    """
    now = time.time()
    with transaction() as conn:
        # Check if request exists
        req = conn.execute(
            "SELECT category, tier FROM requests WHERE id = ?", (payload.request_id,)
        ).fetchone()
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Request id '{payload.request_id}' not found",
            )

        category = req["category"]
        tier = req["tier"]

        # Check idempotency
        existing_fb = conn.execute(
            "SELECT reward FROM feedback WHERE request_id = ?", (payload.request_id,)
        ).fetchone()
        if existing_fb:
            return FeedbackResponse(status="duplicate_ignored", request_id=payload.request_id)

        # Insert feedback
        reward = 1 if payload.thumbs_up else 0
        conn.execute(
            "INSERT INTO feedback (request_id, reward, source, created_at) VALUES (?, ?, 'human', ?)",
            (payload.request_id, reward, now),
        )

        # Update posterior (SAFETY RULE: high_stakes never updates)
        if category != "high_stakes":
            arm = conn.execute(
                "SELECT alpha, beta, updated_at FROM arms WHERE category = ? AND tier = ?",
                (category, tier),
            ).fetchone()

            if arm:
                new_a, new_b, update_ts = update_posterior(
                    category=category,
                    alpha_stored=arm["alpha"],
                    beta_stored=arm["beta"],
                    updated_at=arm["updated_at"],
                    thumbs_up=payload.thumbs_up,
                    now=now,
                    retention_per_day=settings.RETENTION_PER_DAY,
                )
                conn.execute(
                    "UPDATE arms SET alpha = ?, beta = ?, updated_at = ? WHERE category = ? AND tier = ?",
                    (new_a, new_b, update_ts, category, tier),
                )
                conn.execute(
                    "INSERT INTO posterior_history (ts, category, tier, alpha, beta) VALUES (?, ?, ?, ?, ?)",
                    (update_ts, category, tier, new_a, new_b),
                )

    return FeedbackResponse(status="accepted", request_id=payload.request_id)


@app.get("/v1/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """
    Get current decayed posteriors, 90% credible intervals, evidence,
    and aggregate request metrics.
    """
    now = time.time()
    posteriors: list[PosteriorArmStat] = []

    with get_connection() as conn:
        arms_rows = conn.execute(
            "SELECT category, tier, alpha, beta, updated_at FROM arms ORDER BY category, tier"
        ).fetchall()

        for row in arms_rows:
            a_eff, b_eff = compute_decay(
                row["alpha"],
                row["beta"],
                row["updated_at"],
                now=now,
                retention_per_day=settings.RETENTION_PER_DAY,
            )
            mean, var, ci_low, ci_high, cold_start = compute_credible_interval(a_eff, b_eff)
            evidence = max(0.0, a_eff + b_eff - 2.0)

            posteriors.append(
                PosteriorArmStat(
                    category=row["category"],
                    tier=row["tier"],
                    alpha=round(a_eff, 4),
                    beta=round(b_eff, 4),
                    mean=round(mean, 4),
                    variance=round(var, 6),
                    ci90=[round(ci_low, 4), round(ci_high, 4)],
                    evidence=round(evidence, 4),
                    cold_start=cold_start,
                )
            )

        agg = conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(cost_usd), 0.0) as total_cost FROM requests"
        ).fetchone()
        request_count = agg["cnt"] if agg else 0
        total_cost = agg["total_cost"] if agg else 0.0

    return StatsResponse(
        posteriors=posteriors,
        request_count=request_count,
        total_cost_usd=round(total_cost, 6),
    )


@app.get("/v1/history", response_model=HistoryResponse)
async def get_history(limit: int = Query(default=1000, le=5000)) -> HistoryResponse:
    """Time-series of posterior changes for dashboard charts."""
    history: list[HistoryPoint] = []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT ts, category, tier, alpha, beta
            FROM posterior_history
            ORDER BY ts ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        for row in rows:
            total = row["alpha"] + row["beta"]
            mean = row["alpha"] / total if total > 0 else 0.5
            history.append(
                HistoryPoint(
                    ts=row["ts"],
                    category=row["category"],
                    tier=row["tier"],
                    alpha=round(row["alpha"], 4),
                    beta=round(row["beta"], 4),
                    mean=round(mean, 4),
                )
            )

    return HistoryResponse(history=history)
