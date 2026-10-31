"""
Pydantic v2 schemas for request and response models.
"""

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=20000, description="The user prompt to route")


class RouteResponse(BaseModel):
    request_id: str
    category: str
    confidence: float
    tier: str
    model_id: str
    fallback_used: bool
    cache_hit: bool
    cost_usd: float
    latency_ms: float
    response: str


class FeedbackRequest(BaseModel):
    request_id: str
    thumbs_up: bool


class FeedbackResponse(BaseModel):
    status: Literal["accepted", "duplicate_ignored"]
    request_id: str


class PosteriorArmStat(BaseModel):
    category: str
    tier: str
    alpha: float
    beta: float
    mean: float
    variance: float
    ci90: List[float]  # [lower, upper]
    evidence: float
    cold_start: bool


class StatsResponse(BaseModel):
    posteriors: List[PosteriorArmStat]
    request_count: int
    total_cost_usd: float


class HistoryPoint(BaseModel):
    ts: float
    category: str
    tier: str
    alpha: float
    beta: float
    mean: float


class HistoryResponse(BaseModel):
    history: List[HistoryPoint]


class SystemMetricsResponse(BaseModel):
    cache_hit_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    fallback_rate: float
    rate_limited_count: int
    total_cost: float
    estimated_savings_vs_always_large: float
    total_requests: int


class DeadLetterItem(BaseModel):
    id: str
    payload: Any
    error: str
    created_at: float


class DeadLetterResponse(BaseModel):
    dead_letters: List[DeadLetterItem]
    total_count: int


class BenchmarkMetrics(BaseModel):
    mean_quality: float
    std_quality: float
    mean_cost: float
    std_cost: float
    mean_cost_saved_pct: float
    std_cost_saved_pct: float


class BenchmarkResult(BaseModel):
    mode: str
    seeds: int
    train_size: int
    test_size: int
    strategies: Dict[str, BenchmarkMetrics]
    raw_results: Dict[str, Any]
