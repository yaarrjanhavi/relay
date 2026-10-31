"""
Prompt classification with hard safety override and semantic embedding fallback.
Centroid-based classification using Gemini embeddings with local disk caching.
"""

import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Tuple

from app.config import settings

logger = logging.getLogger("relay.classifier")

# Cache paths
SEED_PROMPTS_PATH = os.path.join("data", "seed_prompts.json")
CENTROIDS_CACHE_PATH = os.path.join("data", "centroids_cache.json")

# High-stakes domains (legal, medical, financial, tax, investment, contract, dosage, diagnosis)
# Non-negotiable: MUST ALWAYS RUN FIRST AND WIN
HIGH_STAKES_PATTERNS = [
    r"\b(legal|lawyer|attorney|lawsuit|litigation|court|subpoena|deposition|statute)\b",
    r"\b(contract|liability|indemnity|nda|arbitration|patent|trademark|infringement)\b",
    r"\b(medical|doctor|physician|medicine|diagnosis|diagnose|symptom|prescription|dosage)\b",
    r"\b(chemotherapy|cardiology|oncology|neurology|radiology|disease|disorder|pharmaceutical)\b",
    r"\b(financial|tax|taxes|irs|investment|investing|stock|portfolio|dividend|mortgage)\b",
    r"\b(crypto|equity|retirement|401k|ira|capital\s+gains|financial\s+advice)\b",
    r"\b(is\s+this\s+cancer|what\s+dose|should\s+i\s+take|how\s+many\s+mg)\b",
]

CODE_PATTERNS = [
    r"\b(def|class|function|async|await|return|import|from\s+\w+\s+import)\b",
    r"\b(const|let|var|console\.log|println!|public\s+static\s+void|std::)\b",
    r"\b(select\s+.+\s+from|insert\s+into|update\s+.+\s+set|delete\s+from)\b",
    r"\b(python|javascript|typescript|c\+\+|golang|rust|html|css|sql|bash|dockerfile)\b",
    r"(\{|\}|\(\)|=>|===|!==|\[\]|->|\bnull\b|\bundefined\b|\bNone\b)",
    r"\b(debug|refactor|compile|compiler|runtime\s+error|stack\s*trace|syntax\s*error)\b",
    r"\b(git\s+(commit|push|pull|rebase|merge|checkout|status))\b",
]

MATH_PATTERNS = [
    r"\b(solve|equation|equations|derivative|integral|integrate|differentiate)\b",
    r"\b(matrix|matrices|eigenvalue|eigenvector|vector\s+space|polynomial)\b",
    r"\b(algebra|calculus|geometry|trigonometry|arithmetic|prime\s+number)\b",
    r"\b(theorem|proof|prove\s+that|lemma|corollary|qed)\b",
    r"(\d+[\+\-\*\/\^]\d+|[\$|\\\[].*[\$|\\\]]|\\frac|\\sqrt|\\int|\\sum)",
    r"\b(calculate|compute\s+the\s+sum|find\s+the\s+value\s+of|probability)\b",
]

SUMMARIZE_PATTERNS = [
    r"\b(summarize|summarise|summary|tl;?dr|synopsis|recap|abstract)\b",
    r"\b(key\s+takeaways|bullet\s+points|condense|in\s+a\s+nutshell)\b",
    r"\b(briefly\s+explain|give\s+me\s+the\s+highlights|shorten\s+this)\b",
]

_re_high_stakes = re.compile("|".join(HIGH_STAKES_PATTERNS), re.IGNORECASE)
_re_code = re.compile("|".join(CODE_PATTERNS), re.IGNORECASE)
_re_math = re.compile("|".join(MATH_PATTERNS), re.IGNORECASE)
_re_summarize = re.compile("|".join(SUMMARIZE_PATTERNS), re.IGNORECASE)

# In-memory centroids storage: category -> List[float]
_centroids: Dict[str, List[float]] | None = None


def is_high_stakes(prompt: str) -> bool:
    """Check if prompt matches any high-stakes pattern. Non-negotiable override."""
    return bool(_re_high_stakes.search(prompt))


def classify_by_regex(prompt: str) -> Tuple[str, float]:
    """
    Rule-based baseline classifier with strict high-stakes precedence.
    Returns (category, confidence).
    """
    # 1. HARD SAFETY OVERRIDE: high-stakes check ALWAYS runs first and wins
    if is_high_stakes(prompt):
        return "high_stakes", 1.0

    # 2. Check code
    if _re_code.search(prompt):
        return "code", 0.90

    # 3. Check math
    if _re_math.search(prompt):
        return "math", 0.90

    # 4. Check summarize
    if _re_summarize.search(prompt):
        return "summarize", 0.85

    # 5. Default chat
    return "chat", 0.70


def vector_norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def normalize_vector(v: List[float]) -> List[float]:
    norm = vector_norm(v)
    if norm < 1e-12:
        return v
    return [x / norm for x in v]


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = vector_norm(v1)
    norm2 = vector_norm(v2)
    if norm1 < 1e-12 or norm2 < 1e-12:
        return 0.0
    return dot / (norm1 * norm2)


def get_embedding_sync(text: str, client: Any | None = None) -> List[float]:
    """Call Google GenAI SDK to generate text embedding."""
    if client is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY unset; embedding call unavailable")
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

    result = client.models.embed_content(
        model=settings.GEMINI_MODEL_EMBEDDING,
        contents=text,
    )

    if hasattr(result, "embeddings") and result.embeddings:
        return list(result.embeddings[0].values)
    if hasattr(result, "embedding") and result.embedding:
        return list(result.embedding.values)
    raise RuntimeError("Unexpected embedding response structure from Gemini SDK")


def load_centroids_from_disk() -> Dict[str, List[float]] | None:
    """Load centroids from disk cache if present."""
    if os.path.exists(CENTROIDS_CACHE_PATH):
        try:
            with open(CENTROIDS_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {k: list(v) for k, v in data.items()}
        except Exception as exc:
            logger.warning("Failed to load centroids cache: %s", exc)
    return None


def save_centroids_to_disk(centroids: Dict[str, List[float]]) -> None:
    """Save normalized centroids to disk cache."""
    try:
        os.makedirs(os.path.dirname(CENTROIDS_CACHE_PATH) or ".", exist_ok=True)
        with open(CENTROIDS_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(centroids, f)
    except Exception as exc:
        logger.warning("Failed to write centroids cache: %s", exc)


def build_centroids(client: Any | None = None) -> Dict[str, List[float]] | None:
    """
    Build centroids by embedding prompts in data/seed_prompts.json and averaging.
    Caches result to disk.
    """
    if not os.path.exists(SEED_PROMPTS_PATH):
        return None

    try:
        with open(SEED_PROMPTS_PATH, "r", encoding="utf-8") as f:
            seed_data: Dict[str, List[str]] = json.load(f)
    except Exception as exc:
        logger.warning("Failed to read seed prompts: %s", exc)
        return None

    centroids: Dict[str, List[float]] = {}
    for category, prompts in seed_data.items():
        embeddings: List[List[float]] = []
        for prompt in prompts:
            try:
                emb = get_embedding_sync(prompt, client=client)
                embeddings.append(emb)
            except Exception as exc:
                logger.warning("Embedding error on seed prompt: %s", exc)
                return None

        if not embeddings:
            return None

        dim = len(embeddings[0])
        avg_vec = [0.0] * dim
        for emb in embeddings:
            for i, val in enumerate(emb):
                avg_vec[i] += val
        avg_vec = [val / len(embeddings) for val in avg_vec]
        centroids[category] = normalize_vector(avg_vec)

    save_centroids_to_disk(centroids)
    return centroids


def get_centroids(client: Any | None = None) -> Dict[str, List[float]] | None:
    """Retrieve centroids: memory -> disk -> build."""
    global _centroids
    if _centroids is not None:
        return _centroids

    disk_centroids = load_centroids_from_disk()
    if disk_centroids:
        _centroids = disk_centroids
        return _centroids

    if settings.GEMINI_API_KEY or client is not None:
        built = build_centroids(client=client)
        if built:
            _centroids = built
            return _centroids

    return None


def set_in_memory_centroids(centroids: Dict[str, List[float]]) -> None:
    """Test helper to inject centroids directly."""
    global _centroids
    _centroids = centroids


def classify_prompt(
    prompt: str,
    embed_fn: Any | None = None,
    centroids_override: Dict[str, List[float]] | None = None,
) -> Tuple[str, float]:
    """
    Unified classifier:
    1. HARD SAFETY OVERRIDE: High-stakes regex runs first and wins unconditionally.
    2. Try semantic embedding classification via cosine similarity with cached centroids.
    3. If confidence < 0.55 or embedding fails, safely fall back to regex.
    4. If embeddings indicate 'high_stakes' with confidence >= 0.50, promote to high_stakes.
    """
    # 1. HARD SAFETY OVERRIDE: Always runs first and wins unconditionally
    if is_high_stakes(prompt):
        return "high_stakes", 1.0

    # 2. Try embedding classification
    centroids = centroids_override or get_centroids()

    if centroids:
        try:
            if embed_fn is not None:
                query_vec = embed_fn(prompt)
            else:
                query_vec = get_embedding_sync(prompt)

            best_cat = "chat"
            best_sim = -1.0

            for cat, centroid in centroids.items():
                sim = cosine_similarity(query_vec, centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_cat = cat

            # Safety rule: if embeddings indicate high_stakes with confidence >= 0.5, treat as high_stakes
            if best_cat == "high_stakes" and best_sim >= 0.50:
                return "high_stakes", round(best_sim, 4)

            # Check confidence threshold (0.55)
            if best_sim >= 0.55:
                return best_cat, round(best_sim, 4)

        except Exception as exc:
            # Classification failure must never break a request -> log & fallback
            logger.info("Embedding classifier unavailable, falling back to regex: %s", exc)

    # 3. Safe fallback to regex classifier
    return classify_by_regex(prompt)
