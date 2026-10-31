"""
Comprehensive tests verifying the High-Stakes Safety Rule at every layer:
1. Classifier layer: high-stakes regex runs first and wins unconditionally.
2. Bandit/Sampling layer: sample_tier always returns 'large' and never explores.
3. Update layer: update_posterior never modifies stored posterior.
4. API routing layer: /v1/route forces large tier.
5. API feedback layer: /v1/feedback on high_stakes request preserves arm parameters.
"""

import random

from app.bandit import sample_tier, update_posterior
from app.classifier import classify_prompt, is_high_stakes
from app.database import get_connection


def test_safety_classifier_layer():
    """Verify high-stakes patterns override all other categories."""
    prompts = [
        "What is the chemotherapy dosage for stage 2 lymphoma in a 65kg patient?",
        "Can I sue my employer for breach of contract and liability?",
        "How should I structure my 401k and tax deductions for capital gains?",
        "Write Python code to calculate legal damages for medical malpractice diagnosis",
    ]

    for p in prompts:
        assert is_high_stakes(p) is True
        cat, conf = classify_prompt(p)
        assert cat == "high_stakes"
        assert conf == 1.0


def test_safety_bandit_layer_never_explores():
    """Verify sample_tier always returns 'large' even if other tiers have 100% alpha."""
    # Deliberately give small tier overwhelming empirical success
    rigged_arms = {
        "small": (1000.0, 1.0),
        "medium": (500.0, 1.0),
        "large": (1.0, 100.0),  # large has terrible posterior
    }

    # Test over 100 trials with varied random seeds
    for seed in range(100):
        rng = random.Random(seed)
        chosen_tier, scores = sample_tier("high_stakes", rigged_arms, rng=rng)
        assert chosen_tier == "large"
        assert "large" in scores


def test_safety_posterior_update_layer():
    """Verify update_posterior does not alter alpha or beta for high_stakes."""
    a, b, ts = update_posterior(
        category="high_stakes",
        alpha_stored=5.0,
        beta_stored=2.0,
        updated_at=100.0,
        thumbs_up=True,
        now=200.0,
    )
    assert a == 5.0
    assert b == 2.0

    a2, b2, _ = update_posterior(
        category="high_stakes",
        alpha_stored=5.0,
        beta_stored=2.0,
        updated_at=100.0,
        thumbs_up=False,
        now=200.0,
    )
    assert a2 == 5.0
    assert b2 == 2.0


def test_safety_api_route_and_feedback_layers(client):
    """Verify end-to-end API route and feedback enforces large tier and immutable posteriors."""
    # 1. Route high-stakes prompt
    res = client.post(
        "/v1/route",
        json={"prompt": "What is the recommended dosage for pediatric amoxicillin?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["category"] == "high_stakes"
    assert data["tier"] == "large"
    req_id = data["request_id"]

    # Check baseline posteriors for high_stakes in database
    with get_connection() as conn:
        before_arms = conn.execute(
            "SELECT tier, alpha, beta FROM arms WHERE category = 'high_stakes'"
        ).fetchall()
        before_dict = {row["tier"]: (row["alpha"], row["beta"]) for row in before_arms}

    # 2. Submit negative feedback on this request
    fb_res = client.post("/v1/feedback", json={"request_id": req_id, "thumbs_up": False})
    assert fb_res.status_code == 200
    assert fb_res.json()["status"] == "accepted"

    # 3. Verify high_stakes arms are COMPLETELY unchanged in database
    with get_connection() as conn:
        after_arms = conn.execute(
            "SELECT tier, alpha, beta FROM arms WHERE category = 'high_stakes'"
        ).fetchall()
        after_dict = {row["tier"]: (row["alpha"], row["beta"]) for row in after_arms}

    assert before_dict == after_dict
