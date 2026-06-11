"""
Data access layer for the SEO agent.

load_gsc_data   — reads GSC metrics from Supabase/SQLite for the analysis window.
save_opportunities — idempotent upsert of Opportunity objects into seo_opportunities.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .analyzer import Opportunity

logger = logging.getLogger("seo_agent.repository")

_DEFAULT_LOOKBACK_DAYS = 30


def load_gsc_data(db: object, site_url: str, days: int = _DEFAULT_LOOKBACK_DAYS) -> list[dict]:
    """
    Load raw GSC metric rows for the past *days* days (up to yesterday).

    Returns rows in the format produced by db.get_gsc_metrics_range — each row
    contains nested gsc_queries/gsc_pages dicts that the analyzer expects.
    """
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    logger.info(
        "[TRACE] loading GSC data for %s from %s to %s",
        site_url,
        start.isoformat(),
        end.isoformat(),
    )
    rows = db.get_gsc_metrics_range(  # type: ignore[attr-defined]
        site_url=site_url,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
    logger.info("[TRACE] loaded %d raw GSC rows", len(rows))
    return rows


def save_opportunities(db: object, opportunities: list["Opportunity"], site_url: str) -> int:
    """
    Upsert each Opportunity into seo_opportunities.

    On conflict (site_url, opportunity_type, keyword, page_url) the metrics and
    score are updated while the human-review status field is preserved.

    Returns the number of rows processed.
    """
    count = 0
    for opp in opportunities:
        db.upsert_seo_opportunity(  # type: ignore[attr-defined]
            site_url=site_url,
            opportunity_type=opp.opportunity_type,
            keyword=opp.keyword,
            page_url=opp.page_url,
            impressions=opp.impressions,
            clicks=opp.clicks,
            ctr=opp.ctr,
            position=opp.position,
            opportunity_score=opp.opportunity_score,
            recommendation=opp.recommendation,
            metadata_json=json.dumps(opp.metadata),
        )
        count += 1
    return count
