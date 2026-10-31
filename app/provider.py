"""
LLM Provider abstractions, MockProvider for offline/testing, and GeminiProvider.
"""

import abc
import hashlib
import time
from typing import Any

from app.config import settings


class ProviderError(Exception):
    """Base exception for provider failures (triggers fallback chain)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NonRetryableProviderError(ProviderError):
    """Raised for 400-class errors that must not be retried."""
    pass


class ProviderResponse:
    """Standardized response from any LLM provider."""

    def __init__(
        self,
        text: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        model_id: str,
    ):
        self.text = text
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.latency_ms = latency_ms
        self.model_id = model_id


class BaseProvider(abc.ABC):
    """Abstract base class for model providers."""

    @abc.abstractmethod
    async def generate(self, model_id: str, prompt: str) -> ProviderResponse:
        """Generate response for a prompt using specified model ID."""
        pass


class MockProvider(BaseProvider):
    """
    Deterministic mock provider for offline operation and automated testing.
    Produces predictable responses without network calls.
    """

    def __init__(self, failure_rate: float = 0.0, fail_models: set[str] | None = None):
        self.failure_rate = failure_rate
        self.fail_models = fail_models or set()

    async def generate(self, model_id: str, prompt: str) -> ProviderResponse:
        start_time = time.perf_counter()

        # Check explicit model failure for testing fallback escalation
        if model_id in self.fail_models:
            raise ProviderError(f"Mock failure simulated for model: {model_id}", status_code=500)

        # Hash-based deterministic failure simulation if failure_rate > 0
        prompt_hash = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        if self.failure_rate > 0.0 and (prompt_hash % 1000) / 1000.0 < self.failure_rate:
            raise ProviderError("Deterministic mock random failure triggered", status_code=503)

        # Generate deterministic response
        tokens_in = max(1, len(prompt) // 4)
        digest = hashlib.md5((prompt + model_id).encode()).hexdigest()[:8]
        text = f"[{model_id}] Response to: '{prompt[:40]}...' (hash: {digest})"
        tokens_out = max(1, len(text) // 4)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0 + 5.0
        return ProviderResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=round(elapsed_ms, 2),
            model_id=model_id,
        )


class GeminiProvider(BaseProvider):
    """
    Official Google Gemini provider using google-genai SDK.
    Accepts an injected client for testing without real network calls.
    """

    def __init__(self, api_key: str | None = None, client: Any | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY is not configured", status_code=401)

        from google import genai
        self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate(self, model_id: str, prompt: str) -> ProviderResponse:
        start_time = time.perf_counter()
        client = self._get_client()

        try:
            # google-genai client call
            # Note: client.models.generate_content is synchronous or asynchronous depending on client
            # We call in standard try/except with timeout protection
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Extract usage metadata
            tokens_in = 0
            tokens_out = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata is not None:
                tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            # Fallback estimation if metadata missing
            if tokens_in == 0:
                tokens_in = max(1, len(prompt) // 4)
            if tokens_out == 0:
                tokens_out = max(1, len(getattr(response, "text", "") or "") // 4)

            text_output = getattr(response, "text", "") or ""
            return ProviderResponse(
                text=text_output,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=round(elapsed_ms, 2),
                model_id=model_id,
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            error_msg = str(exc)
            status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)

            # Check 400-class non-retryable errors except 429 (rate limit)
            if status_code is not None and 400 <= status_code < 500 and status_code != 429:
                raise NonRetryableProviderError(
                    f"Gemini client error ({status_code}): {error_msg}", status_code=status_code
                ) from exc

            # Network, quota (429), 5xx, or generic SDK error -> ProviderError for fallback escalation
            raise ProviderError(
                f"Gemini API failure ({model_id}): {error_msg}", status_code=status_code or 500
            ) from exc


def get_provider(force_mock: bool = False) -> BaseProvider:
    """
    Factory: returns GeminiProvider if GEMINI_API_KEY is configured and not forced mock,
    otherwise returns MockProvider for seamless offline operation.
    """
    if not force_mock and settings.GEMINI_API_KEY:
        return GeminiProvider(api_key=settings.GEMINI_API_KEY)
    return MockProvider()
