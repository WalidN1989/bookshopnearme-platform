"""
SEO Intelligence API.

Run with: uvicorn seo_agent.api:app --host 0.0.0.0 --port $PORT

Endpoints:

  GET /seo/opportunities
      List opportunities for a site, ordered by score DESC.
      Query params: site_url (required), opportunity_type, status, limit (default 50)

  GET /seo/opportunities/top
      Shorthand for top-N across all types.
      Query params: site_url (required), limit (default 10)

  GET /seo/opportunities/{id}
      Fetch a single opportunity by ID.

  GET /health
      Health check.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from shared.database.connection import get_db

app = FastAPI(
    title="SEO Intelligence API",
    description="Period.lk (and future sites) SEO opportunity rankings from Search Console data.",
    version="0.1.0",
)


def _get_db():
    return get_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/seo/opportunities/top")
def get_top_opportunities(
    site_url: str = Query(..., description="GSC site identifier, e.g. sc-domain:period.lk"),
    limit: int = Query(10, ge=1, le=200, description="Number of results to return"),
) -> list[dict[str, Any]]:
    """Return the top N highest-scored opportunities for a site across all types."""
    db = _get_db()
    return db.get_seo_opportunities(site_url=site_url, limit=limit)  # type: ignore[attr-defined]


@app.get("/seo/opportunities/{opp_id}")
def get_opportunity(opp_id: int) -> dict[str, Any]:
    """Fetch a single SEO opportunity by its database ID."""
    db = _get_db()
    result = db.get_seo_opportunity_by_id(opp_id)  # type: ignore[attr-defined]
    if result is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opp_id} not found.")
    return result


@app.get("/seo/opportunities")
def list_opportunities(
    site_url: str = Query(..., description="GSC site identifier, e.g. sc-domain:period.lk"),
    opportunity_type: str | None = Query(
        None,
        description="Filter by type: NEW_CONTENT | PAGE_OPTIMIZATION | CTR_IMPROVEMENT | RANKING_IMPROVEMENT",
    ),
    status: str | None = Query(
        None,
        description="Filter by status: pending | reviewed | approved | rejected",
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum rows to return"),
) -> list[dict[str, Any]]:
    """
    List SEO opportunities ordered by opportunity_score DESC.

    Optionally filter by opportunity_type and/or status.
    """
    valid_types = {"NEW_CONTENT", "PAGE_OPTIMIZATION", "CTR_IMPROVEMENT", "RANKING_IMPROVEMENT"}
    valid_statuses = {"pending", "reviewed", "approved", "rejected"}

    if opportunity_type and opportunity_type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid opportunity_type '{opportunity_type}'. Must be one of: {sorted(valid_types)}",
        )
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Must be one of: {sorted(valid_statuses)}",
        )

    db = _get_db()
    return db.get_seo_opportunities(  # type: ignore[attr-defined]
        site_url=site_url,
        opportunity_type=opportunity_type,
        status=status,
        limit=limit,
    )
