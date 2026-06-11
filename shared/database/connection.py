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

    def upsert_gsc_query(self, query: str, date: str, site_url: str) -> int:
        self.conn.execute(
            """
            INSERT INTO gsc_queries (site_url, query, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(site_url, query) DO UPDATE SET
                last_seen=excluded.last_seen,
                updated_at=datetime('now')
            """,
            (site_url, query, date, date),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM gsc_queries WHERE site_url=? AND query=?", (site_url, query)
        ).fetchone()
        return row["id"]

    def upsert_gsc_page(self, page_url: str, date: str, site_url: str) -> int:
        self.conn.execute(
            """
            INSERT INTO gsc_pages (site_url, page_url, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(site_url, page_url) DO UPDATE SET
                last_seen=excluded.last_seen,
                updated_at=datetime('now')
            """,
            (site_url, page_url, date, date),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM gsc_pages WHERE site_url=? AND page_url=?", (site_url, page_url)
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
        site_url: str = "",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO gsc_daily_metrics
                (site_url, date, query_id, page_id, impressions, clicks, ctr, position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_url, date, query_id, page_id) DO UPDATE SET
                impressions=excluded.impressions,
                clicks=excluded.clicks,
                ctr=excluded.ctr,
                position=excluded.position,
                updated_at=datetime('now')
            """,
            (site_url, date, query_id, page_id, impressions, clicks, ctr, position),
        )
        self.conn.commit()

    def get_gsc_metrics_for_date(self, date: str, site_url: str = "") -> list[sqlite3.Row]:
        if site_url:
            return self.conn.execute(
                """
                SELECT m.*, q.query, p.page_url
                FROM gsc_daily_metrics m
                LEFT JOIN gsc_queries q ON m.query_id = q.id
                LEFT JOIN gsc_pages p ON m.page_id = p.id
                WHERE m.date = ? AND m.site_url = ?
                ORDER BY m.impressions DESC
                """,
                (date, site_url),
            ).fetchall()
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

    def get_gsc_metrics_range(
        self, site_url: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Return all metric rows for a site/date-range in Supabase-compatible nested format."""
        rows = self.conn.execute(
            """
            SELECT m.impressions, m.clicks, m.ctr, m.position,
                   q.query, p.page_url
            FROM gsc_daily_metrics m
            LEFT JOIN gsc_queries q ON m.query_id = q.id
            LEFT JOIN gsc_pages p ON m.page_id = p.id
            WHERE m.site_url = ? AND m.date BETWEEN ? AND ?
            ORDER BY m.impressions DESC
            """,
            (site_url, start_date, end_date),
        ).fetchall()
        return [
            {
                "impressions": r["impressions"],
                "clicks": r["clicks"],
                "ctr": r["ctr"],
                "position": r["position"],
                "gsc_queries": {"query": r["query"]},
                "gsc_pages": {"page_url": r["page_url"]},
            }
            for r in rows
        ]

    def get_date_range_exists(self, start_date: str, end_date: str, site_url: str = "") -> list[str]:
        if site_url:
            rows = self.conn.execute(
                "SELECT DISTINCT date FROM gsc_daily_metrics "
                "WHERE date BETWEEN ? AND ? AND site_url = ? ORDER BY date",
                (start_date, end_date, site_url),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT DISTINCT date FROM gsc_daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
                (start_date, end_date),
            ).fetchall()
        return [r["date"] for r in rows]

    # ── seo_opportunities ────────────────────────────────────────────────────

    def upsert_seo_opportunity(
        self,
        site_url: str,
        opportunity_type: str,
        keyword: str,
        page_url: str,
        impressions: int,
        clicks: int,
        ctr: float,
        position: float,
        opportunity_score: float,
        recommendation: str,
        metadata_json: str | None = None,
    ) -> int:
        import json as _json
        cur = self.conn.execute(
            """
            INSERT INTO seo_opportunities
                (site_url, opportunity_type, keyword, page_url,
                 impressions, clicks, ctr, position,
                 opportunity_score, recommendation, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_url, opportunity_type, keyword, page_url) DO UPDATE SET
                impressions       = excluded.impressions,
                clicks            = excluded.clicks,
                ctr               = excluded.ctr,
                position          = excluded.position,
                opportunity_score = excluded.opportunity_score,
                recommendation    = excluded.recommendation,
                metadata_json     = excluded.metadata_json,
                updated_at        = datetime('now')
            """,
            (
                site_url, opportunity_type, keyword, page_url,
                impressions, clicks, ctr, position,
                opportunity_score, recommendation, metadata_json,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM seo_opportunities "
            "WHERE site_url=? AND opportunity_type=? AND keyword=? AND page_url=?",
            (site_url, opportunity_type, keyword, page_url),
        ).fetchone()
        return row["id"]

    def get_seo_opportunities(
        self,
        site_url: str,
        opportunity_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        import json as _json
        sql = (
            "SELECT * FROM seo_opportunities WHERE site_url=?"
        )
        params: list[Any] = [site_url]
        if opportunity_type:
            sql += " AND opportunity_type=?"
            params.append(opportunity_type)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY opportunity_score DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("metadata_json") and isinstance(d["metadata_json"], str):
                try:
                    d["metadata_json"] = _json.loads(d["metadata_json"])
                except Exception:
                    pass
            result.append(d)
        return result

    def get_seo_opportunity_by_id(self, opp_id: int) -> dict[str, Any] | None:
        import json as _json
        row = self.conn.execute(
            "SELECT * FROM seo_opportunities WHERE id=?", (opp_id,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        if d.get("metadata_json") and isinstance(d["metadata_json"], str):
            try:
                d["metadata_json"] = _json.loads(d["metadata_json"])
            except Exception:
                pass
        return d

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


_instance: "DatabaseConnection | SupabaseConnection | None" = None


def get_db(db_path: str | Path | None = None) -> "DatabaseConnection | SupabaseConnection":
    """
    Return the active storage backend.

    Selection logic (evaluated once, then cached as a singleton):
      1. If SUPABASE_URL **and** SUPABASE_SERVICE_ROLE_KEY are both set →
         return a SupabaseConnection (production path; Railway is stateless).
      2. Otherwise → return a DatabaseConnection backed by the SQLite file at
         *db_path* (local development path).

    The *db_path* argument is ignored when Supabase is selected.
    """
    global _instance
    if _instance is None:
        import os

        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

        if supabase_url and supabase_key:
            from .supabase_connection import SupabaseConnection
            _instance = SupabaseConnection(supabase_url, supabase_key)
        else:
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
