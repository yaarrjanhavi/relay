"""
SQLite Database interface with thread-safe writes and transaction support.
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Generator

from app.config import CATEGORIES, TIERS, settings

# Thread lock for synchronizing writes to SQLite
_write_lock = threading.Lock()


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Create a sqlite3 connection with WAL mode and row factory."""
    path = db_path or settings.ROUTER_DB
    conn = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def transaction(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for thread-safe atomic transactions."""
    with _write_lock:
        conn = get_connection(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db(db_path: str | None = None) -> None:
    """Initialize schema and seed arms with prior Beta(1,1) if not present."""
    with transaction(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS arms (
                category TEXT NOT NULL,
                tier TEXT NOT NULL,
                alpha REAL NOT NULL DEFAULT 1.0,
                beta REAL NOT NULL DEFAULT 1.0,
                updated_at REAL NOT NULL,
                PRIMARY KEY (category, tier)
            );

            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                tier TEXT NOT NULL,
                cost_usd REAL NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                cache_hit INTEGER NOT NULL DEFAULT 0,
                fallback_used INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feedback (
                request_id TEXT PRIMARY KEY,
                reward INTEGER NOT NULL,
                source TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (request_id) REFERENCES requests(id)
            );

            CREATE TABLE IF NOT EXISTS posterior_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                category TEXT NOT NULL,
                tier TEXT NOT NULL,
                alpha REAL NOT NULL,
                beta REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at REAL NOT NULL,
                last_error TEXT
            );

            CREATE TABLE IF NOT EXISTS dead_letter (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                error TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at);
            CREATE INDEX IF NOT EXISTS idx_idempotency_created ON idempotency_keys(created_at);
            CREATE INDEX IF NOT EXISTS idx_history_ts ON posterior_history(ts);
            CREATE INDEX IF NOT EXISTS idx_outbox_status_next ON outbox(status, next_attempt_at);
            """
        )

        # Seed arms if empty
        now = time.time()
        for cat in CATEGORIES:
            for tier in TIERS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO arms (category, tier, alpha, beta, updated_at)
                    VALUES (?, ?, 1.0, 1.0, ?)
                    """,
                    (cat, tier, now),
                )
                # Seed initial history record
                conn.execute(
                    """
                    INSERT INTO posterior_history (ts, category, tier, alpha, beta)
                    SELECT ?, ?, ?, 1.0, 1.0
                    WHERE NOT EXISTS (
                        SELECT 1 FROM posterior_history WHERE category = ? AND tier = ?
                    )
                    """,
                    (now, cat, tier, cat, tier),
                )
