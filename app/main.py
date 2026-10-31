"""
FastAPI Application for Relay: Self-learning LLM Router.
Includes Phase 4 Production Engineering:
- Redis atomic token-bucket rate limiter (Lua script) & SHA-256 response cache
- Fail-open fallback when Redis is unavailable
- Transactional Outbox for feedback with asynchronous background worker & dead-letter storage
- 24-hour Idempotency-Key support on /v1/route
- Optional LLM-as-judge auto-feedback
- Structured logging & operational metrics
"""

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.bandit import (
    compute_credible_interval,
    compute_decay,
    sample_tier,
)
from app.classifier import classify_prompt
from app.config import (
    compute_cost_usd,
    settings,
)
from app.database import get_connection, init_db, transaction
from app.judge import run_judge_evaluation, should_sample_judge
from app.logging_config import setup_logging
from app.outbox import (
    enqueue_feedback_outbox,
    outbox_worker_loop,
    process_pending_outbox_events,
)
from app.provider import (
    BaseProvider,
    NonRetryableProviderError,
    ProviderError,
    get_provider,
)
from app.redis_client import redis_service
from app.schemas import (
    DeadLetterItem,
    DeadLetterResponse,
    FeedbackRequest,
    FeedbackResponse,
    HistoryPoint,
    HistoryResponse,
    PosteriorArmStat,
    RouteRequest,
    RouteResponse,
    StatsResponse,
    SystemMetricsResponse,
)

logger = setup_logging()

# Background outbox worker task
_outbox_stop_event = asyncio.Event()
_outbox_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize schema, start outbox worker."""
    global _outbox_task
    init_db()

    _outbox_stop_event.clear()
    _outbox_task = asyncio.create_task(
        outbox_worker_loop(_outbox_stop_event, interval_seconds=0.25)
    )

    yield

    _outbox_stop_event.set()
    if _outbox_task is not None:
        try:
            await asyncio.wait_for(_outbox_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass


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


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start_time = time.perf_counter()

    response = await call_next(request)

    latency_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Request-ID"] = request_id

    # Do not log spam on frequent health checks
    if request.url.path != "/healthz":
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} in {latency_ms:.2f}ms",
            extra={"request_id": request_id},
        )
    return response


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
    raw_request: Request,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    provider: BaseProvider = Depends(get_provider),
) -> Any:
    """
    Route a prompt to the optimal Gemini tier using Thompson Sampling.
    Features rate-limiting, response caching, 24h idempotency, and fallback escalation.
    """
    now = time.time()

    # 1. Atomic token-bucket rate limiter
    client_ip = (
        raw_request.client.host
        if raw_request.client
        else raw_request.headers.get("X-Forwarded-For", "127.0.0.1")
    )
    api_identifier = raw_request.headers.get("Authorization", client_ip)

    allowed, retry_after = redis_service.check_rate_limit(
        identifier=api_identifier,
        rate=settings.RATE_LIMIT_RPS,
        capacity=settings.RATE_LIMIT_BURST,
        now=now,
    )
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests. Rate limit exceeded."},
            headers={"Retry-After": str(retry_after)},
        )

    # 2. 24h Idempotency-Key check
    if idempotency_key:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT response_json, created_at FROM idempotency_keys WHERE key = ?",
                (idempotency_key,),
            ).fetchone()
            if row and (now - row["created_at"]) < 86400.0:
                stored = json.loads(row["response_json"])
                return RouteResponse(**stored)

    # 3. Exact-match response cache check (30m TTL)
    cached = redis_service.get_cached_response(request.prompt)
    if cached:
        cached_req_id = str(uuid.uuid4())
        # Persist cached request record with cache_hit=1
        with transaction() as conn:
            conn.execute(
                """
                INSERT INTO requests (id, category, tier, cost_usd, tokens_in, tokens_out, latency_ms, cache_hit, fallback_used, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
                """,
                (
                    cached_req_id,
                    cached["category"],
                    cached["tier"],
                    0.0,
                    cached.get("tokens_in", 0),
                    cached.get("tokens_out", 0),
                    1.5,
                    now,
                ),
            )
        response_obj = RouteResponse(
            request_id=cached_req_id,
            category=cached["category"],
            confidence=cached["confidence"],
            tier=cached["tier"],
            model_id=cached["model_id"],
            fallback_used=False,
            cache_hit=True,
            cost_usd=0.0,
            latency_ms=1.5,
            response=cached["response"],
        )
        return response_obj

    # 4. Classify prompt
    category, confidence = classify_prompt(request.prompt)

    # 5. Select initial tier
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

    # 6. Fallback chain escalation
    chain = get_fallback_chain(selected_tier)
    provider_resp = None
    served_tier = selected_tier
    fallback_used = False
    last_error: Exception | None = None

    for candidate_tier in chain:
        model_id = get_model_for_tier(candidate_tier)
        try:
            provider_resp = await provider.generate(model_id, request.prompt)
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

    # 7. Calculate cost
    cost_usd = compute_cost_usd(served_tier, provider_resp.tokens_in, provider_resp.tokens_out)
    request_id = str(uuid.uuid4())

    # 8. Persist request record
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO requests (id, category, tier, cost_usd, tokens_in, tokens_out, latency_ms, cache_hit, fallback_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                request_id,
                category,
                served_tier,
                cost_usd,
                provider_resp.tokens_in,
                provider_resp.tokens_out,
                provider_resp.latency_ms,
                1 if fallback_used else 0,
                now,
            ),
        )

    route_result = RouteResponse(
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

    # 9. Store in response cache (30 min)
    redis_service.set_cached_response(
        prompt=request.prompt,
        data={
            "response": provider_resp.text,
            "category": category,
            "confidence": confidence,
            "tier": served_tier,
            "model_id": provider_resp.model_id,
            "tokens_in": provider_resp.tokens_in,
            "tokens_out": provider_resp.tokens_out,
        },
        ttl_seconds=1800,
    )

    # 10. Store in idempotency store if key supplied
    if idempotency_key:
        with transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO idempotency_keys (key, response_json, created_at)
                VALUES (?, ?, ?)
                """,
                (idempotency_key, json.dumps(route_result.model_dump()), now),
            )

    # 11. Optional LLM-as-judge background evaluation
    if should_sample_judge(category):
        background_tasks.add_task(
            run_judge_evaluation,
            request_id=request_id,
            prompt=request.prompt,
            response_text=provider_resp.text,
            category=category,
            tier=served_tier,
            now=now,
        )

    return route_result


@app.post("/v1/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    """
    Submit thumbs up/down feedback for a request.
    Atomically writes feedback row AND outbox event in ONE SQLite transaction.
    """
    now = time.time()
    event_id = str(uuid.uuid4())

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

        # 1. Insert feedback record
        reward = 1 if payload.thumbs_up else 0
        conn.execute(
            "INSERT INTO feedback (request_id, reward, source, created_at) VALUES (?, ?, 'human', ?)",
            (payload.request_id, reward, now),
        )

        # 2. Transactional Outbox write in SAME transaction
        enqueue_feedback_outbox(
            conn=conn,
            event_id=event_id,
            request_id=payload.request_id,
            category=category,
            tier=tier,
            thumbs_up=payload.thumbs_up,
            source="human",
            now=now,
        )

    # Process pending events immediately or let background worker handle it
    process_pending_outbox_events(now=now)

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


@app.get("/v1/system/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics() -> SystemMetricsResponse:
    """Operational metrics: cache hit rate, p50/p95 latency, fallbacks, savings."""
    with get_connection() as conn:
        all_reqs = conn.execute(
            """
            SELECT cost_usd, tokens_in, tokens_out, latency_ms, cache_hit, fallback_used
            FROM requests
            """
        ).fetchall()

    total_requests = len(all_reqs)
    if total_requests == 0:
        return SystemMetricsResponse(
            cache_hit_rate=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            fallback_rate=0.0,
            rate_limited_count=redis_service.get_rate_limited_count(),
            total_cost=0.0,
            estimated_savings_vs_always_large=0.0,
            total_requests=0,
        )

    cache_hits = sum(1 for r in all_reqs if r["cache_hit"] == 1)
    fallbacks = sum(1 for r in all_reqs if r["fallback_used"] == 1)
    total_cost = sum(r["cost_usd"] for r in all_reqs)

    # Latency percentiles (non-cache hits)
    latencies = sorted([r["latency_ms"] for r in all_reqs if r["cache_hit"] == 0])
    if latencies:
        p50_idx = int(0.50 * (len(latencies) - 1))
        p95_idx = int(0.95 * (len(latencies) - 1))
        p50_latency = latencies[p50_idx]
        p95_latency = latencies[p95_idx]
    else:
        p50_latency = 0.0
        p95_latency = 0.0

    # Estimated counterfactual savings vs always-large
    always_large_cost = 0.0
    for r in all_reqs:
        if r["cache_hit"] == 0:
            always_large_cost += compute_cost_usd("large", r["tokens_in"], r["tokens_out"])

    estimated_savings = max(0.0, always_large_cost - total_cost)

    return SystemMetricsResponse(
        cache_hit_rate=round(cache_hits / total_requests, 4),
        p50_latency_ms=round(p50_latency, 2),
        p95_latency_ms=round(p95_latency, 2),
        fallback_rate=round(fallbacks / total_requests, 4),
        rate_limited_count=redis_service.get_rate_limited_count(),
        total_cost=round(total_cost, 6),
        estimated_savings_vs_always_large=round(estimated_savings, 6),
        total_requests=total_requests,
    )


@app.get("/v1/admin/dead-letters", response_model=DeadLetterResponse)
async def get_dead_letters() -> DeadLetterResponse:
    """Inspection endpoint for failed outbox events moved to dead-letter storage."""
    items: list[DeadLetterItem] = []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, payload, error, created_at
            FROM dead_letter
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()

        for r in rows:
            try:
                parsed_payload = json.loads(r["payload"])
            except Exception:
                parsed_payload = r["payload"]

            items.append(
                DeadLetterItem(
                    id=r["id"],
                    payload=parsed_payload,
                    error=r["error"],
                    created_at=r["created_at"],
                )
            )

    return DeadLetterResponse(dead_letters=items, total_count=len(items))
