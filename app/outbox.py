"""
Transactional Outbox Background Worker for asynchronous posterior updates.
Ensures resilience with exponential backoff retry and 5-attempt dead-letter storage.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict

from app.bandit import update_posterior
from app.config import settings
from app.database import transaction

logger = logging.getLogger("relay.outbox")


def enqueue_feedback_outbox(
    conn: Any,
    event_id: str,
    request_id: str,
    category: str,
    tier: str,
    thumbs_up: bool,
    source: str = "human",
    now: float | None = None,
) -> None:
    """Enqueues a feedback event in the same SQLite transaction as the feedback record."""
    current_time = time.time() if now is None else now
    payload = json.dumps(
        {
            "request_id": request_id,
            "category": category,
            "tier": tier,
            "thumbs_up": thumbs_up,
            "source": source,
        }
    )
    conn.execute(
        """
        INSERT INTO outbox (id, payload, status, attempts, next_attempt_at, last_error)
        VALUES (?, ?, 'pending', 0, ?, NULL)
        """,
        (event_id, payload, current_time),
    )


def process_single_outbox_item(
    item: Dict[str, Any],
    conn: Any,
    now: float | None = None,
    simulated_failure: bool = False,
) -> None:
    """Processes one outbox event, updating arms posterior and history."""
    if simulated_failure:
        raise RuntimeError("Simulated transient error during outbox processing")

    current_time = time.time() if now is None else now
    payload = json.loads(item["payload"])
    category = payload["category"]
    tier = payload["tier"]
    thumbs_up = payload["thumbs_up"]

    # SAFETY RULE: high_stakes feedback NEVER modifies any posterior
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
                thumbs_up=thumbs_up,
                now=current_time,
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

    conn.execute("UPDATE outbox SET status = 'done' WHERE id = ?", (item["id"],))


def process_pending_outbox_events(
    db_path: str | None = None,
    now: float | None = None,
    fail_event_ids: set[str] | None = None,
) -> int:
    """
    Process due events in the outbox.
    Returns number of successfully processed events.
    """
    current_time = time.time() if now is None else now
    processed = 0

    with transaction(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT id, payload, status, attempts, next_attempt_at, last_error
            FROM outbox
            WHERE status = 'pending' AND next_attempt_at <= ?
            LIMIT 50
            """,
            (current_time,),
        )
        rows = [dict(r) for r in cursor.fetchall()]

    for item in rows:
        event_id = item["id"]
        attempts = item["attempts"]
        should_fail = bool(fail_event_ids and event_id in fail_event_ids)

        try:
            with transaction(db_path) as conn:
                process_single_outbox_item(
                    item, conn, now=current_time, simulated_failure=should_fail
                )
            processed += 1
        except Exception as exc:
            err_msg = str(exc)
            new_attempts = attempts + 1
            with transaction(db_path) as conn:
                if new_attempts >= 5:
                    # Move to dead-letter after 5 failed attempts
                    conn.execute(
                        """
                        INSERT INTO dead_letter (id, payload, error, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (event_id, item["payload"], err_msg, current_time),
                    )
                    conn.execute(
                        "UPDATE outbox SET status = 'dead_letter', attempts = ?, last_error = ? WHERE id = ?",
                        (new_attempts, err_msg, event_id),
                    )
                    logger.error(
                        "Event %s exceeded 5 attempts and was moved to dead-letter table: %s",
                        event_id,
                        err_msg,
                    )
                else:
                    # Exponential backoff: 0.5s * 2^(attempts)
                    backoff_sec = 0.5 * (2**new_attempts)
                    next_attempt = current_time + backoff_sec
                    conn.execute(
                        """
                        UPDATE outbox
                        SET attempts = ?, next_attempt_at = ?, last_error = ?
                        WHERE id = ?
                        """,
                        (new_attempts, next_attempt, err_msg, event_id),
                    )
                    logger.warning(
                        "Event %s failed attempt %d, retrying in %.2fs: %s",
                        event_id,
                        new_attempts,
                        backoff_sec,
                        err_msg,
                    )

    return processed


async def outbox_worker_loop(
    stop_event: asyncio.Event, interval_seconds: float = 0.5, db_path: str | None = None
) -> None:
    """Continuous background worker loop for FastAPI lifespan."""
    logger.info("Outbox worker loop started")
    while not stop_event.is_set():
        try:
            process_pending_outbox_events(db_path=db_path)
        except Exception as exc:
            logger.error("Error in outbox worker loop: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
    logger.info("Outbox worker loop stopped")
