-- ============================================================
-- Sprint 3a: Add site_url to GSC tables for multi-site support
-- ============================================================
-- Run this entire file in the Supabase SQL Editor after
-- 001_initial_schema.sql has been applied.
--
-- What this migration does:
--   1. Adds site_url column to gsc_queries, gsc_pages, gsc_daily_metrics
--   2. Backfills existing rows with 'https://bookshopnearme.lk/'
--   3. Makes site_url NOT NULL
--   4. Drops old single-column UNIQUE constraints
--   5. Adds new composite UNIQUE constraints that include site_url
--   6. Adds site_url indexes for fast per-site queries
--   7. Replaces all three upsert RPC functions with site_url–aware versions
--
-- Existing bookshopnearme.lk data is preserved intact.
-- ============================================================


-- ── Step 1: Add nullable columns ─────────────────────────────────────────────

ALTER TABLE gsc_queries       ADD COLUMN IF NOT EXISTS site_url TEXT;
ALTER TABLE gsc_pages         ADD COLUMN IF NOT EXISTS site_url TEXT;
ALTER TABLE gsc_daily_metrics ADD COLUMN IF NOT EXISTS site_url TEXT;


-- ── Step 2: Backfill existing rows ───────────────────────────────────────────

UPDATE gsc_queries       SET site_url = 'https://bookshopnearme.lk/' WHERE site_url IS NULL;
UPDATE gsc_pages         SET site_url = 'https://bookshopnearme.lk/' WHERE site_url IS NULL;
UPDATE gsc_daily_metrics SET site_url = 'https://bookshopnearme.lk/' WHERE site_url IS NULL;


-- ── Step 3: Make columns NOT NULL ────────────────────────────────────────────

ALTER TABLE gsc_queries       ALTER COLUMN site_url SET NOT NULL;
ALTER TABLE gsc_pages         ALTER COLUMN site_url SET NOT NULL;
ALTER TABLE gsc_daily_metrics ALTER COLUMN site_url SET NOT NULL;


-- ── Step 4: Drop old single-column UNIQUE constraints ────────────────────────
-- These were auto-named by Postgres when the tables were created in migration 001.

ALTER TABLE gsc_queries       DROP CONSTRAINT IF EXISTS gsc_queries_query_key;
ALTER TABLE gsc_pages         DROP CONSTRAINT IF EXISTS gsc_pages_page_url_key;
ALTER TABLE gsc_daily_metrics DROP CONSTRAINT IF EXISTS gsc_daily_metrics_date_query_id_page_id_key;


-- ── Step 5: Add new composite UNIQUE constraints ──────────────────────────────

ALTER TABLE gsc_queries
    ADD CONSTRAINT gsc_queries_site_url_query_key
    UNIQUE (site_url, query);

ALTER TABLE gsc_pages
    ADD CONSTRAINT gsc_pages_site_url_page_url_key
    UNIQUE (site_url, page_url);

ALTER TABLE gsc_daily_metrics
    ADD CONSTRAINT gsc_daily_metrics_site_url_date_query_id_page_id_key
    UNIQUE (site_url, date, query_id, page_id);


-- ── Step 6: Add site_url indexes for per-site filtering ──────────────────────

CREATE INDEX IF NOT EXISTS idx_gsc_queries_site_url       ON gsc_queries(site_url);
CREATE INDEX IF NOT EXISTS idx_gsc_pages_site_url         ON gsc_pages(site_url);
CREATE INDEX IF NOT EXISTS idx_gsc_daily_metrics_site_url ON gsc_daily_metrics(site_url);


-- ── Step 7: Replace RPC functions with site_url–aware versions ───────────────

CREATE OR REPLACE FUNCTION upsert_gsc_query(
    p_query    TEXT,
    p_date     TEXT,
    p_site_url TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO gsc_queries (site_url, query, first_seen, last_seen)
    VALUES (p_site_url, p_query, p_date::date, p_date::date)
    ON CONFLICT (site_url, query) DO UPDATE
        SET last_seen  = GREATEST(gsc_queries.last_seen, EXCLUDED.last_seen),
            updated_at = now()
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;


CREATE OR REPLACE FUNCTION upsert_gsc_page(
    p_page_url TEXT,
    p_date     TEXT,
    p_site_url TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO gsc_pages (site_url, page_url, first_seen, last_seen)
    VALUES (p_site_url, p_page_url, p_date::date, p_date::date)
    ON CONFLICT (site_url, page_url) DO UPDATE
        SET last_seen  = GREATEST(gsc_pages.last_seen, EXCLUDED.last_seen),
            updated_at = now()
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;


CREATE OR REPLACE FUNCTION upsert_gsc_daily_metric(
    p_date        TEXT,
    p_query_id    BIGINT,
    p_page_id     BIGINT,
    p_impressions INTEGER,
    p_clicks      INTEGER,
    p_ctr         REAL,
    p_position    REAL,
    p_site_url    TEXT
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    INSERT INTO gsc_daily_metrics
        (site_url, date, query_id, page_id, impressions, clicks, ctr, position)
    VALUES
        (p_site_url, p_date::date, p_query_id, p_page_id,
         p_impressions, p_clicks, p_ctr, p_position)
    ON CONFLICT (site_url, date, query_id, page_id) DO UPDATE
        SET impressions = EXCLUDED.impressions,
            clicks      = EXCLUDED.clicks,
            ctr         = EXCLUDED.ctr,
            position    = EXCLUDED.position,
            updated_at  = now();
END;
$$;
