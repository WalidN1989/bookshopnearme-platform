"""
SEO opportunity detection.

Consumes raw GSC metric rows (as returned by db.get_gsc_metrics_range) and
applies four rule-based detectors to produce a ranked list of Opportunity
objects.  No keywords are hardcoded — all opportunities are derived directly
from Search Console data.

Detection thresholds
────────────────────
NEW_CONTENT          impressions ≥ 5   AND  ctr < 2%   (virtually no engagement)
CTR_IMPROVEMENT      impressions ≥ 10  AND  ctr < 50 % of site average  AND  position ≤ 20
RANKING_IMPROVEMENT  impressions ≥ 5   AND  5 ≤ position ≤ 20  AND  clicks ≥ 1
PAGE_OPTIMIZATION    page impressions ≥ 10  AND  page ctr < 75 % of site average
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .scorer import score_opportunity

logger = logging.getLogger("seo_agent.analyzer")

# ── Detection thresholds ──────────────────────────────────────────────────────

_MIN_IMP_NEW_CONTENT = 5
_MAX_CTR_NEW_CONTENT = 0.02        # 2 %

_MIN_IMP_CTR = 10
_CTR_RATIO_CTR = 0.50              # must be < 50 % of site average

_MIN_IMP_RANKING = 5
_MIN_CLICKS_RANKING = 1
_POS_MIN_RANKING = 5.0
_POS_MAX_RANKING = 20.0

_MIN_IMP_PAGE_OPT = 10
_CTR_RATIO_PAGE_OPT = 0.75        # must be < 75 % of site average


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Opportunity:
    opportunity_type: str
    keyword: str
    page_url: str
    impressions: int
    clicks: int
    ctr: float
    position: float
    opportunity_score: float
    recommendation: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _aggregate_by_query_page(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """Sum impressions/clicks and average position, grouped by (query, page_url)."""
    groups: dict[tuple[str, str], dict] = {}

    for row in rows:
        gq = row.get("gsc_queries") or {}
        gp = row.get("gsc_pages") or {}
        query = (gq.get("query") or "").strip()
        page_url = (gp.get("page_url") or "").strip()
        if not query or not page_url:
            continue

        key = (query, page_url)
        if key not in groups:
            groups[key] = {"impressions": 0, "clicks": 0, "positions": []}
        g = groups[key]
        g["impressions"] += int(row.get("impressions") or 0)
        g["clicks"] += int(row.get("clicks") or 0)
        g["positions"].append(float(row.get("position") or 0.0))

    result: dict[tuple[str, str], dict] = {}
    for (query, page_url), g in groups.items():
        imp = g["impressions"]
        clk = g["clicks"]
        avg_pos = sum(g["positions"]) / len(g["positions"]) if g["positions"] else 0.0
        result[(query, page_url)] = {
            "impressions": imp,
            "clicks": clk,
            "ctr": clk / imp if imp > 0 else 0.0,
            "position": avg_pos,
        }

    return result


def _site_avg_ctr(agg: dict[tuple[str, str], dict]) -> float:
    total_imp = sum(v["impressions"] for v in agg.values())
    total_clk = sum(v["clicks"] for v in agg.values())
    return total_clk / total_imp if total_imp > 0 else 0.0


def _aggregate_by_page(agg: dict[tuple[str, str], dict]) -> dict[str, dict]:
    """Roll up query-level aggregates into page-level totals."""
    pages: dict[str, dict] = {}
    for (query, page_url), m in agg.items():
        if page_url not in pages:
            pages[page_url] = {"impressions": 0, "clicks": 0, "queries": []}
        pages[page_url]["impressions"] += m["impressions"]
        pages[page_url]["clicks"] += m["clicks"]
        pages[page_url]["queries"].append(
            (m["impressions"], m["clicks"], m["ctr"], m["position"], query)
        )
    for p in pages.values():
        imp = p["impressions"]
        p["ctr"] = p["clicks"] / imp if imp > 0 else 0.0
        p["queries"].sort(reverse=True)  # highest impressions first
    return pages


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(rows: list[dict], site_url: str) -> list[Opportunity]:
    """
    Analyze raw GSC metric rows and return a ranked list of Opportunity objects.

    Args:
        rows:     Raw rows from db.get_gsc_metrics_range — each row has
                  gsc_queries(query), gsc_pages(page_url), impressions,
                  clicks, ctr, position.
        site_url: GSC site identifier (e.g. 'sc-domain:period.lk').

    Returns:
        List of Opportunity objects sorted by opportunity_score DESC.
    """
    logger.info("[TRACE] aggregating %d raw metric rows for %s", len(rows), site_url)
    agg = _aggregate_by_query_page(rows)
    logger.info("[TRACE] %d unique (query, page) pairs after aggregation", len(agg))

    site_avg = _site_avg_ctr(agg)
    logger.info("[TRACE] site average CTR: %.4f", site_avg)

    page_agg = _aggregate_by_page(agg)
    opportunities: list[Opportunity] = []

    # Track keywords already captured as NEW_CONTENT to avoid duplicates across pages
    new_content_seen: set[str] = set()

    for (query, page_url), m in agg.items():
        imp = m["impressions"]
        clk = m["clicks"]
        ctr = m["ctr"]
        pos = m["position"]

        # ── Rule 1: NEW_CONTENT ───────────────────────────────────────────────
        if (
            imp >= _MIN_IMP_NEW_CONTENT
            and ctr < _MAX_CTR_NEW_CONTENT
            and query not in new_content_seen
        ):
            score, meta = score_opportunity(imp, clk, ctr, pos, site_avg, "NEW_CONTENT")
            new_content_seen.add(query)
            opportunities.append(
                Opportunity(
                    opportunity_type="NEW_CONTENT",
                    keyword=query,
                    page_url=page_url,
                    impressions=imp,
                    clicks=clk,
                    ctr=round(ctr, 6),
                    position=round(pos, 2),
                    opportunity_score=score,
                    recommendation=(
                        f"Create dedicated content targeting '{query}'. "
                        f"This keyword generates {imp} impressions but only {clk} click(s), "
                        "suggesting no closely matched page currently exists."
                    ),
                    metadata=meta,
                )
            )
            continue

        # ── Rule 3: CTR_IMPROVEMENT ───────────────────────────────────────────
        if (
            imp >= _MIN_IMP_CTR
            and site_avg > 0.0
            and ctr < site_avg * _CTR_RATIO_CTR
            and ctr >= _MAX_CTR_NEW_CONTENT  # not already a NEW_CONTENT candidate
            and pos <= 20.0
        ):
            score, meta = score_opportunity(imp, clk, ctr, pos, site_avg, "CTR_IMPROVEMENT")
            opportunities.append(
                Opportunity(
                    opportunity_type="CTR_IMPROVEMENT",
                    keyword=query,
                    page_url=page_url,
                    impressions=imp,
                    clicks=clk,
                    ctr=round(ctr, 6),
                    position=round(pos, 2),
                    opportunity_score=score,
                    recommendation=(
                        f"Improve title tag and meta description for '{page_url}' "
                        f"targeting '{query}'. "
                        f"Current CTR {ctr:.1%} is below site average {site_avg:.1%}. "
                        "Test more compelling SERP copy and structured-data enhancements."
                    ),
                    metadata=meta,
                )
            )
            continue

        # ── Rule 4: RANKING_IMPROVEMENT ──────────────────────────────────────
        if (
            _POS_MIN_RANKING <= pos <= _POS_MAX_RANKING
            and imp >= _MIN_IMP_RANKING
            and clk >= _MIN_CLICKS_RANKING
        ):
            score, meta = score_opportunity(imp, clk, ctr, pos, site_avg, "RANKING_IMPROVEMENT")
            opportunities.append(
                Opportunity(
                    opportunity_type="RANKING_IMPROVEMENT",
                    keyword=query,
                    page_url=page_url,
                    impressions=imp,
                    clicks=clk,
                    ctr=round(ctr, 6),
                    position=round(pos, 2),
                    opportunity_score=score,
                    recommendation=(
                        f"Strengthen '{page_url}' for '{query}' (avg position {pos:.1f}). "
                        "Improve topical depth, internal linking, and content coverage "
                        "to move this keyword into the top 5."
                    ),
                    metadata=meta,
                )
            )

    # ── Rule 2: PAGE_OPTIMIZATION (page-level, one opportunity per page) ──────
    for page_url, p in page_agg.items():
        imp = p["impressions"]
        page_ctr = p["ctr"]
        clk = p["clicks"]
        if (
            imp >= _MIN_IMP_PAGE_OPT
            and site_avg > 0.0
            and page_ctr < site_avg * _CTR_RATIO_PAGE_OPT
        ):
            top_query_data = p["queries"][0]  # highest-impression query for this page
            _, _, _, top_pos, top_query = top_query_data

            score, meta = score_opportunity(imp, clk, page_ctr, top_pos, site_avg, "PAGE_OPTIMIZATION")
            meta["query_count"] = len(p["queries"])
            opportunities.append(
                Opportunity(
                    opportunity_type="PAGE_OPTIMIZATION",
                    keyword=top_query,
                    page_url=page_url,
                    impressions=imp,
                    clicks=clk,
                    ctr=round(page_ctr, 6),
                    position=round(top_pos, 2),
                    opportunity_score=score,
                    recommendation=(
                        f"Optimize '{page_url}' for better CTR across "
                        f"{len(p['queries'])} ranking quer{'y' if len(p['queries']) == 1 else 'ies'}. "
                        f"Page CTR {page_ctr:.1%} vs site average {site_avg:.1%}. "
                        "Improve title tag, meta description, FAQ content, "
                        "and structured-data markup."
                    ),
                    metadata=meta,
                )
            )

    opportunities.sort(key=lambda o: o.opportunity_score, reverse=True)
    logger.info("[TRACE] detected %d opportunities", len(opportunities))
    return opportunities
