-- ============================================================
-- Sprint 4A: SEO Opportunities table
-- ============================================================
-- Run in the Supabase SQL Editor after 002_add_site_url.sql.
-- Idempotent: safe to re-run.
-- ============================================================


-- ── Table ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS seo_opportunities (
    id                BIGSERIAL   PRIMARY KEY,
    site_url          TEXT        NOT NULL,
    opportunity_type  TEXT        NOT NULL
                      CHECK (opportunity_type IN (
                          'NEW_CONTENT',
                          'PAGE_OPTIMIZATION',
                          'CTR_IMPROVEMENT',
                          'RANKING_IMPROVEMENT'
                      )),
    keyword           TEXT        NOT NULL,
    page_url          TEXT        NOT NULL DEFAULT '',
    impressions       INTEGER     NOT NULL DEFAULT 0,
    clicks            INTEGER     NOT NULL DEFAULT 0,
    ctr               REAL        NOT NULL DEFAULT 0.0,
    position          REAL        NOT NULL DEFAULT 0.0,
    opportunity_score REAL        NOT NULL DEFAULT 0.0,
    recommendation    TEXT        NOT NULL DEFAULT '',
    status            TEXT        NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'reviewed', 'approved', 'rejected')),
    metadata_json     JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Natural key: one live opportunity per (site, type, keyword, page) tuple.
    -- Re-running the agent updates metrics but does not duplicate rows.
    UNIQUE (site_url, opportunity_type, keyword, page_url)
);


-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_seo_opp_site_url
    ON seo_opportunities(site_url);

CREATE INDEX IF NOT EXISTS idx_seo_opp_type
    ON seo_opportunities(opportunity_type);

CREATE INDEX IF NOT EXISTS idx_seo_opp_status
    ON seo_opportunities(status);

-- Primary query pattern: ordered by score for a given site
CREATE INDEX IF NOT EXISTS idx_seo_opp_site_score
    ON seo_opportunities(site_url, opportunity_score DESC);

-- API filter combinations
CREATE INDEX IF NOT EXISTS idx_seo_opp_site_type_score
    ON seo_opportunities(site_url, opportunity_type, opportunity_score DESC);

CREATE INDEX IF NOT EXISTS idx_seo_opp_site_status_score
    ON seo_opportunities(site_url, status, opportunity_score DESC);


-- ── RPC: upsert_seo_opportunity ───────────────────────────────────────────────
-- Inserts a new opportunity or updates its metrics/score while preserving
-- the human-review status field.

CREATE OR REPLACE FUNCTION upsert_seo_opportunity(
    p_site_url          TEXT,
    p_opportunity_type  TEXT,
    p_keyword           TEXT,
    p_page_url          TEXT,
    p_impressions       INTEGER,
    p_clicks            INTEGER,
    p_ctr               REAL,
    p_position          REAL,
    p_opportunity_score REAL,
    p_recommendation    TEXT,
    p_metadata_json     JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO seo_opportunities (
        site_url, opportunity_type, keyword, page_url,
        impressions, clicks, ctr, position,
        opportunity_score, recommendation, metadata_json
    )
    VALUES (
        p_site_url, p_opportunity_type, p_keyword, p_page_url,
        p_impressions, p_clicks, p_ctr, p_position,
        p_opportunity_score, p_recommendation, p_metadata_json
    )
    ON CONFLICT (site_url, opportunity_type, keyword, page_url) DO UPDATE
        SET impressions       = EXCLUDED.impressions,
            clicks            = EXCLUDED.clicks,
            ctr               = EXCLUDED.ctr,
            position          = EXCLUDED.position,
            opportunity_score = EXCLUDED.opportunity_score,
            recommendation    = EXCLUDED.recommendation,
            metadata_json     = EXCLUDED.metadata_json,
            updated_at        = now()
        -- status is intentionally NOT updated — preserves human review decisions
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;
