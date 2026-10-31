"""
Unit tests for Transactional Outbox, worker retry with exponential backoff,
dead-letter table, 24-hour Idempotency-Key support, and Judge safety.
"""

import uuid

import pytest

from app.database import get_connection, transaction
from app.judge import parse_judge_output, run_judge_evaluation, should_sample_judge
from app.outbox import enqueue_feedback_outbox, process_pending_outbox_events
from app.provider import MockProvider


def test_transactional_outbox_atomic_write(client, test_db_path):
    """Verify POST /v1/feedback writes to both feedback and outbox tables in one transaction."""
    route_res = client.post("/v1/route", json={"prompt": "def sort_items(items): return items"})
    assert route_res.status_code == 200
    req_id = route_res.json()["request_id"]

    fb_res = client.post("/v1/feedback", json={"request_id": req_id, "thumbs_up": True})
    assert fb_res.status_code == 200

    with get_connection() as conn:
        fb_row = conn.execute(
            "SELECT request_id, reward FROM feedback WHERE request_id = ?", (req_id,)
        ).fetchone()
        assert fb_row is not None
        assert fb_row["reward"] == 1

        outbox_row = conn.execute(
            "SELECT payload, status FROM outbox WHERE payload LIKE ?", (f"%{req_id}%",)
        ).fetchone()
        assert outbox_row is not None


def test_outbox_retry_exponential_backoff_and_dead_letter(test_db_path):
    """
    Simulate failing events:
    Verify retries with exponential backoff, and migration to dead_letter table after 5 failures.
    """
    event_id = str(uuid.uuid4())
    req_id = str(uuid.uuid4())
    now = 1000.0

    with transaction() as conn:
        enqueue_feedback_outbox(
            conn=conn,
            event_id=event_id,
            request_id=req_id,
            category="code",
            tier="small",
            thumbs_up=True,
            now=now,
        )

    # Fail attempts 1 to 4
    for attempt in range(1, 5):
        process_pending_outbox_events(
            db_path=test_db_path, now=now, fail_event_ids={event_id}
        )
        with get_connection() as conn:
            row = conn.execute("SELECT attempts, next_attempt_at, status FROM outbox WHERE id = ?", (event_id,)).fetchone()
            assert row["attempts"] == attempt
            assert row["status"] == "pending"
            assert row["next_attempt_at"] > now
        # Advance time past backoff
        now = row["next_attempt_at"] + 1.0

    # 5th attempt: should move to dead_letter table
    process_pending_outbox_events(db_path=test_db_path, now=now, fail_event_ids={event_id})

    with get_connection() as conn:
        outbox_row = conn.execute("SELECT status, attempts FROM outbox WHERE id = ?", (event_id,)).fetchone()
        assert outbox_row["status"] == "dead_letter"
        assert outbox_row["attempts"] == 5

        dl_row = conn.execute("SELECT id, error FROM dead_letter WHERE id = ?", (event_id,)).fetchone()
        assert dl_row is not None
        assert dl_row["id"] == event_id
        assert "Simulated transient error" in dl_row["error"]


def test_idempotency_key_24h_window(client):
    """Verify same Idempotency-Key returns stored response within 24h."""
    idempotency_key = "test-idempotency-key-" + str(uuid.uuid4())

    headers = {"Idempotency-Key": idempotency_key}
    prompt = "What is the capital of France?"

    # First call
    res1 = client.post("/v1/route", json={"prompt": prompt}, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()

    # Second call with same key
    res2 = client.post("/v1/route", json={"prompt": prompt}, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()

    # Must return identical request_id and response without generating a second request
    assert data1["request_id"] == data2["request_id"]
    assert data1["response"] == data2["response"]


def test_judge_rubric_parsing_and_high_stakes_safety():
    """Verify parse_judge_output and safety rule: judge NEVER evaluates high_stakes."""
    assert parse_judge_output('{"good": true}') is True
    assert parse_judge_output('{"good": false}') is False
    assert parse_judge_output('Random text with {"good": true} included') is True
    assert parse_judge_output('Malformed output') is False

    # Safety check: should_sample_judge NEVER returns True for high_stakes
    assert should_sample_judge("high_stakes", sample_rate=1.0) is False
    assert should_sample_judge("code", sample_rate=1.0) is True


@pytest.mark.asyncio
async def test_judge_evaluation_skips_high_stakes(test_db_path):
    """Verify run_judge_evaluation safely exits immediately on high_stakes."""
    mock_prov = MockProvider()
    good, cost = await run_judge_evaluation(
        request_id="test-req-hs",
        prompt="Dosage of amoxicillin",
        response_text="Take 500mg",
        category="high_stakes",
        tier="large",
        provider=mock_prov,
    )
    assert good is False
    assert cost == 0.0

    # Ensure no feedback was written
    with get_connection() as conn:
        fb = conn.execute("SELECT 1 FROM feedback WHERE request_id = 'test-req-hs'").fetchone()
        assert fb is None
