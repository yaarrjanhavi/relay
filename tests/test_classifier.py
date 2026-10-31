"""
Unit tests for the embedding classifier, centroid math, safe fallback,
and hard safety override precedence.
"""

import os
import tempfile

from app.classifier import (
    classify_prompt,
    cosine_similarity,
    load_centroids_from_disk,
    normalize_vector,
    save_centroids_to_disk,
    vector_norm,
)
from app.config import settings


def test_vector_math():
    v = [3.0, 4.0]
    assert vector_norm(v) == 5.0
    norm_v = normalize_vector(v)
    assert abs(vector_norm(norm_v) - 1.0) < 1e-9

    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    v3 = [1.0, 0.0]
    assert cosine_similarity(v1, v2) == 0.0
    assert abs(cosine_similarity(v1, v3) - 1.0) < 1e-9


def test_fallback_without_api_key(monkeypatch):
    """When GEMINI_API_KEY is unset and no centroids, falls back seamlessly to regex."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    cat, conf = classify_prompt("Write a quicksort in Python", centroids_override={})
    assert cat == "code"
    assert conf >= 0.8


def test_hard_safety_override_beats_embeddings():
    """High-stakes check runs first and wins unconditionally even if embeddings say code."""
    fake_centroids = {
        "code": [1.0, 0.0],
        "chat": [0.0, 1.0],
    }

    def fake_embed_fn(text: str) -> list[float]:
        return [1.0, 0.0]

    high_stakes_prompt = "Write a Python script to calculate pediatric chemotherapy dosage"

    cat, conf = classify_prompt(
        high_stakes_prompt, embed_fn=fake_embed_fn, centroids_override=fake_centroids
    )

    assert cat == "high_stakes"
    assert conf == 1.0


def test_embedding_classification_above_threshold():
    """When confidence >= 0.55, returns embedding category."""
    fake_centroids = {
        "code": [1.0, 0.0, 0.0],
        "math": [0.0, 1.0, 0.0],
        "chat": [0.0, 0.0, 1.0],
    }

    def fake_embed_fn(text: str) -> list[float]:
        return [0.1, 0.95, 0.0]

    cat, conf = classify_prompt(
        "Calculate the integral of sin(x)",
        embed_fn=fake_embed_fn,
        centroids_override=fake_centroids,
    )
    assert cat == "math"
    assert conf > 0.9


def test_embedding_fallback_when_confidence_below_threshold():
    """When top cosine similarity < 0.55, falls back to regex."""
    fake_centroids = {
        "chat": [1.0, 0.0, 0.0],
        "math": [0.0, 1.0, 0.0],
    }

    def fake_embed_fn(text: str) -> list[float]:
        # Orthogonal to both centroids: sim = 0.0 < 0.55
        return [0.0, 0.0, 1.0]

    prompt = "def my_func(): return True"
    cat, conf = classify_prompt(
        prompt, embed_fn=fake_embed_fn, centroids_override=fake_centroids
    )
    # Should fall back to regex, detecting 'code'
    assert cat == "code"
    assert conf == 0.90


def test_embedding_high_stakes_promotion_threshold():
    """If embeddings indicate high_stakes with confidence >= 0.50, promote to high_stakes."""
    fake_centroids = {
        "code": [0.0, 1.0],
        "high_stakes": [1.0, 0.0],
    }

    def fake_embed_fn(text: str) -> list[float]:
        return [0.52, 0.1]

    cat, conf = classify_prompt(
        "Some nuanced query", embed_fn=fake_embed_fn, centroids_override=fake_centroids
    )
    assert cat == "high_stakes"
    assert conf >= 0.50


def test_disk_cache_roundtrip(monkeypatch):
    """Verify centroid caching saves to disk and loads correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "test_centroids.json")
        monkeypatch.setattr("app.classifier.CENTROIDS_CACHE_PATH", cache_path)

        data = {"code": [0.1, 0.9], "math": [0.8, 0.2]}
        save_centroids_to_disk(data)

        loaded = load_centroids_from_disk()
        assert loaded is not None
        assert "code" in loaded
        assert loaded["code"] == [0.1, 0.9]
