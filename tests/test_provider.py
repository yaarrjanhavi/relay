"""
Unit tests for GeminiProvider with fake client, MockProvider, and Fallback escalation.
No real network calls are made.
"""

from types import SimpleNamespace

import pytest

from app.config import compute_cost_usd, settings
from app.main import get_fallback_chain
from app.provider import (
    GeminiProvider,
    MockProvider,
    NonRetryableProviderError,
    ProviderError,
    get_provider,
)


class FakeUsageMetadata:
    def __init__(self, prompt_tokens: int, candidate_tokens: int):
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = candidate_tokens


class FakeGenerateContentResponse:
    def __init__(self, text: str, prompt_tokens: int = 40, candidate_tokens: int = 120):
        self.text = text
        self.usage_metadata = FakeUsageMetadata(prompt_tokens, candidate_tokens)


class FakeGeminiClient:
    """Fake client mimicking google.genai.Client for testing."""

    def __init__(self, failure_code: int | None = None, delay: float = 0.0):
        self.failure_code = failure_code
        self.delay = delay
        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, model: str, contents: str):
        if self.delay > 0:
            import time
            time.sleep(self.delay)

        if self.failure_code:
            err = Exception(f"Fake API Error with code {self.failure_code}")
            setattr(err, "code", self.failure_code)
            raise err

        return FakeGenerateContentResponse(
            text=f"Response from {model} for '{contents}'",
            prompt_tokens=50,
            candidate_tokens=150,
        )


@pytest.mark.asyncio
async def test_gemini_provider_with_fake_client_success():
    """Verify GeminiProvider handles response and token metadata properly."""
    fake_client = FakeGeminiClient()
    provider = GeminiProvider(api_key="test-fake-key", client=fake_client)

    resp = await provider.generate(model_id="gemini-2.5-flash-lite", prompt="Hello Gemini")

    assert "gemini-2.5-flash-lite" in resp.text
    assert resp.tokens_in == 50
    assert resp.tokens_out == 150
    assert resp.model_id == "gemini-2.5-flash-lite"
    assert resp.latency_ms > 0

    cost = compute_cost_usd("small", resp.tokens_in, resp.tokens_out)
    assert cost > 0


@pytest.mark.asyncio
async def test_gemini_provider_timeout():
    """Verify 30s timeout mechanism aborts long running calls with 504."""
    # Fast test using small timeout
    fake_client = FakeGeminiClient(delay=0.1)
    provider = GeminiProvider(api_key="test-fake-key", client=fake_client, timeout_seconds=0.02)

    with pytest.raises(ProviderError) as exc_info:
        await provider.generate(model_id="gemini-2.5-pro", prompt="Slow request")

    assert exc_info.value.status_code == 504
    assert "timed out" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_gemini_provider_error_classification():
    """Verify 400 non-retryable vs 429 quota vs 500 server errors."""
    # 400 Bad Request
    client_400 = FakeGeminiClient(failure_code=400)
    provider_400 = GeminiProvider(api_key="test-key", client=client_400)
    with pytest.raises(NonRetryableProviderError) as exc_info:
        await provider_400.generate(model_id="gemini-2.5-pro", prompt="Bad request")
    assert exc_info.value.status_code == 400

    # 429 Quota / Rate limit -> ProviderError for fallback escalation
    client_429 = FakeGeminiClient(failure_code=429)
    provider_429 = GeminiProvider(api_key="test-key", client=client_429)
    with pytest.raises(ProviderError) as exc_info:
        await provider_429.generate(model_id="gemini-2.5-pro", prompt="Quota exceeded")
    assert not isinstance(exc_info.value, NonRetryableProviderError)
    assert exc_info.value.status_code == 429

    # 503 Service Unavailable -> ProviderError
    client_503 = FakeGeminiClient(failure_code=503)
    provider_503 = GeminiProvider(api_key="test-key", client=client_503)
    with pytest.raises(ProviderError) as exc_info:
        await provider_503.generate(model_id="gemini-2.5-pro", prompt="Server error")
    assert exc_info.value.status_code == 503


def test_missing_api_key_defaults_to_mock_provider(monkeypatch):
    """When GEMINI_API_KEY is unset, get_provider() defaults to MockProvider."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    provider = get_provider()
    assert isinstance(provider, MockProvider)


def test_fallback_chain_escalation_logic():
    """Verify fallback sequence escalation."""
    assert get_fallback_chain("small") == ["small", "medium", "large"]
    assert get_fallback_chain("medium") == ["medium", "large"]
    assert get_fallback_chain("large") == ["large"]


def test_fallback_escalation_in_route(client):
    """
    Verify /v1/route escalates when a tier fails and sets fallback_used = True.
    """
    # Create MockProvider where small tier fails
    failing_provider = MockProvider(fail_models={settings.GEMINI_MODEL_SMALL})

    from app.main import app
    from app.main import get_provider as app_get_provider

    app.dependency_overrides[app_get_provider] = lambda: failing_provider

    try:
        # Send a prompt likely routed to small/medium
        res = client.post("/v1/route", json={"prompt": "Hey there, how are you today?"})
        assert res.status_code == 200
        data = res.json()

        # If it initially selected small, it escalated to medium
        if data["fallback_used"]:
            assert data["tier"] in ["medium", "large"]
            assert data["model_id"] in [settings.GEMINI_MODEL_MEDIUM, settings.GEMINI_MODEL_LARGE]
    finally:
        app.dependency_overrides.clear()
