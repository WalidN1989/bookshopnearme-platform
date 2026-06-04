from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from .migrations import run_migrations


class DatabaseConnection:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            run_migrations(self._conn)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        return self.connect()

    # ── agent_runs ──────────────────────────────────────────────────────────

    def insert_agent_run(
        self,
        agent_name: str,
        status: str,
        started_at: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        meta_json = json.dumps(metadata) if metadata else None
        cur = self.conn.execute(
            """
            INSERT INTO agent_runs (agent_name, status, started_at, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (agent_name, status, started_at, meta_json),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def update_agent_run(
        self,
        run_id: int,
        status: str,
        duration_seconds: float = 0,
        records_processed: int = 0,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        meta_json = json.dumps(metadata) if metadata else None
        self.conn.execute(
            """
            UPDATE agent_runs
            SET status=?, duration_seconds=?, records_processed=?,
                error_message=?, metadata=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (status, duration_seconds, records_processed, error_message, meta_json, run_id),
        )
        self.conn.commit()

    # ── GSC ─────────────────────────────────────────────────────────────────

    def upsert_gsc_query(self, query: str, date: str) -> int:
        self.conn.execute(
            """
            INSERT INTO gsc_queries (query, first_seen, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(query) DO UPDATE SET
                last_seen=excluded.last_seen,
                updated_at=datetime('now')
            """,
            (query, date, date),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM gsc_queries WHERE query=?", (query,)
        ).fetchone()
        return row["id"]

    def upsert_gsc_page(self, page_url: str, date: str) -> int:
        self.conn.execute(
            """
            INSERT INTO gsc_pages (page_url, first_seen, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(page_url) DO UPDATE SET
                last_seen=excluded.last_seen,
                updated_at=datetime('now')
            """,
            (page_url, date, date),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM gsc_pages WHERE page_url=?", (page_url,)
        ).fetchone()
        return row["id"]

    def upsert_gsc_daily_metric(
        self,
        date: str,
        query_id: int | None,
        page_id: int | None,
        impressions: int,
        clicks: int,
        ctr: float,
        position: float,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO gsc_daily_metrics
                (date, query_id, page_id, impressions, clicks, ctr, position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, query_id, page_id) DO UPDATE SET
                impressions=excluded.impressions,
                clicks=excluded.clicks,
                ctr=excluded.ctr,
                position=excluded.position,
                updated_at=datetime('now')
            """,
            (date, query_id, page_id, impressions, clicks, ctr, position),
        )
        self.conn.commit()

    def get_gsc_metrics_for_date(self, date: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT m.*, q.query, p.page_url
            FROM gsc_daily_metrics m
            LEFT JOIN gsc_queries q ON m.query_id = q.id
            LEFT JOIN gsc_pages p ON m.page_id = p.id
            WHERE m.date = ?
            ORDER BY m.impressions DESC
            """,
            (date,),
        ).fetchall()

    def get_date_range_exists(self, start_date: str, end_date: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT date FROM gsc_daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
            (start_date, end_date),
        ).fetchall()
        return [r["date"] for r in rows]

    # ── content_opportunities ────────────────────────────────────────────────

    def insert_content_opportunity(
        self,
        keyword: str,
        source: str,
        search_volume: int | None = None,
        difficulty: float | None = None,
        book_available: bool = False,
        priority_score: float | None = None,
        notes: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO content_opportunities
                (keyword, source, search_volume, difficulty, book_available, priority_score, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (keyword, source, search_volume, difficulty, int(book_available), priority_score, notes),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    # ── system_settings ──────────────────────────────────────────────────────

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM system_settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO system_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')
            """,
            (key, value),
        )
        self.conn.commit()


_instance: DatabaseConnection | None = None


def get_db(db_path: str | Path | None = None) -> DatabaseConnection:
    global _instance
    if _instance is None:
        if db_path is None:
            from shared.config import get_settings
            db_path = get_settings().database_path
        _instance = DatabaseConnection(db_path)
    return _instance


@contextmanager
def get_db_context(db_path: str | Path | None = None) -> Generator[DatabaseConnection, None, None]:
    db = DatabaseConnection(db_path or get_db().db_path)
    try:
        yield db
    finally:
        db.close()
