-- ============================================================
-- Sprint 2: GSC Storage Migration — Supabase Initial Schema
-- ============================================================
-- Run this entire file once in the Supabase SQL Editor:
--   Project → SQL Editor → New query → paste → Run
--
-- Idempotent: all statements use CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS / CREATE OR REPLACE FUNCTION.
-- Safe to re-run if partially applied.
-- ============================================================


-- ── Tables ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gsc_queries (
    id          BIGSERIAL PRIMARY KEY,
    query       TEXT        NOT NULL UNIQUE,
    first_seen  DATE        NOT NULL,
    last_seen   DATE        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gsc_pages (
    id          BIGSERIAL PRIMARY KEY,
    page_url    TEXT        NOT NULL UNIQUE,
    first_seen  DATE        NOT NULL,
    last_seen   DATE        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gsc_daily_metrics (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE        NOT NULL,
    query_id    BIGINT      REFERENCES gsc_queries(id),
    page_id     BIGINT      REFERENCES gsc_pages(id),
    impressions INTEGER     NOT NULL DEFAULT 0,
    clicks      INTEGER     NOT NULL DEFAULT 0,
    ctr         REAL        NOT NULL DEFAULT 0.0,
    position    REAL        NOT NULL DEFAULT 0.0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date, query_id, page_id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id                BIGSERIAL PRIMARY KEY,
    agent_name        TEXT        NOT NULL,
    status            TEXT        NOT NULL
                      CHECK (status IN ('STARTED', 'COMPLETED', 'FAILED')),
    started_at        TIMESTAMPTZ,
    duration_seconds  REAL,
    records_processed INTEGER     DEFAULT 0,
    error_message     TEXT,
    metadata          JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_gsc_daily_date   ON gsc_daily_metrics(date);
CREATE INDEX IF NOT EXISTS idx_gsc_daily_query  ON gsc_daily_metrics(query_id);
CREATE INDEX IF NOT EXISTS idx_gsc_daily_page   ON gsc_daily_metrics(page_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);


-- ── RPC: upsert_gsc_query ────────────────────────────────────────────────────
-- Inserts a query or, on conflict, updates only last_seen (never first_seen).
-- Returns the row id in both cases.

CREATE OR REPLACE FUNCTION upsert_gsc_query(p_query TEXT, p_date TEXT)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO gsc_queries (query, first_seen, last_seen)
    VALUES (p_query, p_date::date, p_date::date)
    ON CONFLICT (query) DO UPDATE
        SET last_seen  = GREATEST(gsc_queries.last_seen, EXCLUDED.last_seen),
            updated_at = now()
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;


-- ── RPC: upsert_gsc_page ─────────────────────────────────────────────────────
-- Inserts a page URL or, on conflict, updates only last_seen.
-- Returns the row id in both cases.

CREATE OR REPLACE FUNCTION upsert_gsc_page(p_page_url TEXT, p_date TEXT)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO gsc_pages (page_url, first_seen, last_seen)
    VALUES (p_page_url, p_date::date, p_date::date)
    ON CONFLICT (page_url) DO UPDATE
        SET last_seen  = GREATEST(gsc_pages.last_seen, EXCLUDED.last_seen),
            updated_at = now()
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;


-- ── RPC: upsert_gsc_daily_metric ─────────────────────────────────────────────
-- Inserts a (date, query_id, page_id) metric row, or replaces all metric
-- values on conflict with the same composite key.

CREATE OR REPLACE FUNCTION upsert_gsc_daily_metric(
    p_date        TEXT,
    p_query_id    BIGINT,
    p_page_id     BIGINT,
    p_impressions INTEGER,
    p_clicks      INTEGER,
    p_ctr         REAL,
    p_position    REAL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    INSERT INTO gsc_daily_metrics
        (date, query_id, page_id, impressions, clicks, ctr, position)
    VALUES
        (p_date::date, p_query_id, p_page_id, p_impressions, p_clicks, p_ctr, p_position)
    ON CONFLICT (date, query_id, page_id) DO UPDATE
        SET impressions = EXCLUDED.impressions,
            clicks      = EXCLUDED.clicks,
            ctr         = EXCLUDED.ctr,
            position    = EXCLUDED.position,
            updated_at  = now();
END;
$$;
