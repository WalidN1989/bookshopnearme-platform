"""
Supabase storage backend — drop-in replacement for DatabaseConnection.

All public method signatures are identical to DatabaseConnection so the
rest of the codebase (agent.py, ingestion.py, logger.py) requires no changes.

Upserts for gsc_queries and gsc_pages are handled via Postgres RPC functions
(defined in supabase/migrations/001_initial_schema.sql) to preserve correct
first_seen / last_seen semantics that PostgREST's built-in upsert cannot
express in a single round-trip.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class SupabaseConnection:
    """Storage backend backed by Supabase (Postgres + PostgREST)."""

    def __init__(self, url: str, key: str) -> None:
        if not url or not key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must both be set."
            )

        # Normalise the URL: supabase-py constructs the PostgREST path itself
        # as <base>/rest/v1.  If the caller included /rest/v1/ in the URL
        # (common mistake when copying from the Supabase API docs), supabase-py
        # doubles it → .../rest/v1/rest/v1 → every request returns 404.
        # Strip any trailing path components beyond the bare origin.
        url = _normalise_supabase_url(url)

        # Lazy import so the shared package does not hard-require supabase
        # when only the MCP or local-SQLite path is used.
        try:
            from supabase import create_client  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "supabase package is not installed. "
                "Run: pip install 'supabase>=2.0.0'"
            ) from exc

        self._client = create_client(url, key)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def connect(self) -> "SupabaseConnection":
        """Validate connectivity by pinging the agent_runs table."""
        try:
            self._client.table("agent_runs").select("id").limit(1).execute()
        except Exception as exc:
            raise RuntimeError(
                f"Supabase connectivity check failed: {exc}\n"
                "Ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are correct "
                "and the schema has been applied (supabase/migrations/001_initial_schema.sql)."
            ) from exc
        return self

    def close(self) -> None:
        """No-op — Supabase HTTP client has no persistent connection to close."""
        pass

    # ── agent_runs ───────────────────────────────────────────────────────────

    def insert_agent_run(
        self,
        agent_name: str,
        status: str,
        started_at: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        result = (
            self._client.table("agent_runs")
            .insert(
                {
                    "agent_name": agent_name,
                    "status": status,
                    "started_at": started_at,
                    "metadata": metadata,
                }
            )
            .execute()
        )
        return result.data[0]["id"]

    def update_agent_run(
        self,
        run_id: int,
        status: str,
        duration_seconds: float = 0,
        records_processed: int = 0,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        (
            self._client.table("agent_runs")
            .update(
                {
                    "status": status,
                    "duration_seconds": duration_seconds,
                    "records_processed": records_processed,
                    "error_message": error_message,
                    "metadata": metadata,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", run_id)
            .execute()
        )

    # ── GSC upserts (via RPC for correct first_seen/last_seen semantics) ─────

    def upsert_gsc_query(self, query: str, date: str, site_url: str) -> int:
        """Insert query or update last_seen. Returns row id."""
        result = self._client.rpc(
            "upsert_gsc_query",
            {"p_query": query, "p_date": date, "p_site_url": site_url},
        ).execute()
        return _scalar_int(result.data)

    def upsert_gsc_page(self, page_url: str, date: str, site_url: str) -> int:
        """Insert page URL or update last_seen. Returns row id."""
        result = self._client.rpc(
            "upsert_gsc_page",
            {"p_page_url": page_url, "p_date": date, "p_site_url": site_url},
        ).execute()
        return _scalar_int(result.data)

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
        """Insert or replace a (site_url, date, query_id, page_id) metric row."""
        self._client.rpc(
            "upsert_gsc_daily_metric",
            {
                "p_date": date,
                "p_query_id": query_id,
                "p_page_id": page_id,
                "p_impressions": impressions,
                "p_clicks": clicks,
                "p_ctr": ctr,
                "p_position": position,
                "p_site_url": site_url,
            },
        ).execute()

    # ── GSC reads ────────────────────────────────────────────────────────────

    def get_date_range_exists(self, start_date: str, end_date: str, site_url: str = "") -> list[str]:
        """Return sorted list of distinct dates that already have metrics for this site."""
        query = (
            self._client.table("gsc_daily_metrics")
            .select("date")
            .gte("date", start_date)
            .lte("date", end_date)
        )
        if site_url:
            query = query.eq("site_url", site_url)
        result = query.execute()
        return sorted({row["date"] for row in result.data})

    def get_gsc_metrics_for_date(self, date: str, site_url: str = "") -> list[dict[str, Any]]:
        query = (
            self._client.table("gsc_daily_metrics")
            .select("*, gsc_queries(query), gsc_pages(page_url)")
            .eq("date", date)
            .order("impressions", desc=True)
        )
        if site_url:
            query = query.eq("site_url", site_url)
        return query.execute().data

    # ── system_settings (stub — not used in Sprint 2) ────────────────────────

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        return default

    def set_setting(self, key: str, value: str) -> None:
        pass  # Deferred to future sprint

    # ── content_opportunities (stub — Sprint 3+) ─────────────────────────────

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
        raise NotImplementedError("content_opportunities is a Sprint 3+ feature.")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalise_supabase_url(url: str) -> str:
    """
    Return the bare project origin that supabase-py expects.

    supabase-py appends /rest/v1 to whatever URL you pass.  If the user
    copied the URL from the Supabase API docs (which shows the full REST
    endpoint), it already contains /rest/v1/ and supabase-py would produce
    the doubled path  .../rest/v1/rest/v1  causing 404 on every call.

    Strips known Supabase path suffixes so the result is always:
        https://<ref>.supabase.co
    """
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url.rstrip("/"))
    # Remove any path component — supabase-py only needs scheme + netloc
    clean = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    return clean


def _scalar_int(data: Any) -> int:
    """
    PostgREST returns scalar function results in varying shapes across
    supabase-py versions. Handle both the bare-int and list-wrapped forms.
    """
    if isinstance(data, list):
        return int(data[0])
    return int(data)
