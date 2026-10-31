"""
Configuration and pricing parameters for Relay.
"""

from typing import Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service configuration
    SERVICE_NAME: str = "relay"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    ROUTER_DB: str = "relay.db"

    # Redis infrastructure
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TIMEOUT_MS: int = 500

    # Bandit parameters
    # Trade-off coefficient between reward expectation and relative cost
    LAMBDA: float = 0.25
    RETENTION_PER_DAY: float = 0.98

    # LLM-as-judge auto-feedback sample rate (0.0 means disabled)
    JUDGE_SAMPLE_RATE: float = 0.0

    # Verified current Google Gemini models
    # Note: re-verify model IDs and availability at https://ai.google.dev/pricing
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL_SMALL: str = "gemini-2.5-flash-lite"
    GEMINI_MODEL_MEDIUM: str = "gemini-2.5-flash"
    GEMINI_MODEL_LARGE: str = "gemini-2.5-pro"
    GEMINI_MODEL_EMBEDDING: str = "gemini-embedding-001"

    # Timeout for provider requests in seconds
    PROVIDER_TIMEOUT_SECONDS: float = 30.0

    # Rate limiting
    RATE_LIMIT_RPS: float = 2.0  # 120 req/minute
    RATE_LIMIT_BURST: int = 30


# IMPORTANT: Re-verify prices periodically against official Google AI Studio pricing docs:
# https://ai.google.dev/pricing
# All prices are in USD per 1,000,000 tokens (1M tokens).
TIER_PRICING: Dict[str, Dict[str, float]] = {
    "small": {
        "input": 0.10,   # $0.10 per 1M input tokens
        "output": 0.40,  # $0.40 per 1M output tokens
    },
    "medium": {
        "input": 0.30,   # $0.30 per 1M input tokens
        "output": 2.50,  # $2.50 per 1M output tokens
    },
    "large": {
        "input": 1.25,   # $1.25 per 1M input tokens
        "output": 10.00, # $10.00 per 1M output tokens
    },
}

CATEGORIES = ["code", "math", "summarize", "chat", "high_stakes"]
TIERS = ["small", "medium", "large"]


def compute_cost_usd(tier: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate the exact USD cost for a given tier and token counts."""
    pricing = TIER_PRICING.get(tier, TIER_PRICING["large"])
    cost_in = (tokens_in / 1_000_000.0) * pricing["input"]
    cost_out = (tokens_out / 1_000_000.0) * pricing["output"]
    return round(cost_in + cost_out, 8)


def get_tier_relative_cost(tier: str) -> float:
    """
    Returns the relative cost of a tier normalized against the maximum tier cost.
    Uses representative blended token cost (e.g. 80% input, 20% output for 1M tokens)
    or output token price. Here we use representative output cost per 1M tokens.
    """
    tier_costs = {t: TIER_PRICING[t]["output"] for t in TIERS}
    max_cost = max(tier_costs.values())
    return tier_costs.get(tier, max_cost) / max_cost


settings = Settings()
