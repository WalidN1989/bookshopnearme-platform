from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migration_files"

# Each migration is a tuple of (version, description, sql)
MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "initial_schema",
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS system_settings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT NOT NULL UNIQUE,
            value       TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name         TEXT NOT NULL,
            status             TEXT NOT NULL CHECK (status IN ('STARTED','COMPLETED','FAILED')),
            started_at         TEXT,
            duration_seconds   REAL,
            records_processed  INTEGER DEFAULT 0,
            error_message      TEXT,
            metadata           TEXT,
            created_at         TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS gsc_queries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            query        TEXT NOT NULL UNIQUE,
            first_seen   TEXT NOT NULL,
            last_seen    TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS gsc_pages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            page_url     TEXT NOT NULL UNIQUE,
            first_seen   TEXT NOT NULL,
            last_seen    TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS gsc_daily_metrics (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            date          TEXT NOT NULL,
            query_id      INTEGER REFERENCES gsc_queries(id),
            page_id       INTEGER REFERENCES gsc_pages(id),
            impressions   INTEGER NOT NULL DEFAULT 0,
            clicks        INTEGER NOT NULL DEFAULT 0,
            ctr           REAL NOT NULL DEFAULT 0.0,
            position      REAL NOT NULL DEFAULT 0.0,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (date, query_id, page_id)
        );

        CREATE TABLE IF NOT EXISTS content_opportunities (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword         TEXT NOT NULL,
            search_volume   INTEGER,
            difficulty      REAL,
            book_available  INTEGER NOT NULL DEFAULT 0,
            priority_score  REAL,
            source          TEXT NOT NULL CHECK (source IN ('GSC','DATASEO','GOOGLE_TRENDS','MANUAL')),
            status          TEXT NOT NULL DEFAULT 'NEW'
                            CHECK (status IN ('NEW','RESEARCHED','APPROVED','WRITING','PUBLISHED','RANKING')),
            notes           TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_gsc_daily_date ON gsc_daily_metrics(date);
        CREATE INDEX IF NOT EXISTS idx_gsc_daily_query ON gsc_daily_metrics(query_id);
        CREATE INDEX IF NOT EXISTS idx_gsc_daily_page ON gsc_daily_metrics(page_id);
        CREATE INDEX IF NOT EXISTS idx_content_opp_status ON content_opportunities(status);
        CREATE INDEX IF NOT EXISTS idx_content_opp_source ON content_opportunities(source);
        CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name);
        CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
        """,
    ),
]


def run_migrations(conn: sqlite3.Connection) -> int:
    """Apply pending migrations. Returns number of migrations applied."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()

    applied = {
        row[0]
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }

    count = 0
    for version, description, sql in MIGRATIONS:
        if version in applied:
            continue
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, description),
        )
        conn.commit()
        count += 1

    return count
