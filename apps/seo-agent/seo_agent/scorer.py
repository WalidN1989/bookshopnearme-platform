"""
Deterministic SEO opportunity scoring model.

Score range: 0–100, computed from four independent components:

  impression_score  (0–35)  Log-scaled impression volume.
                             Higher impressions = larger addressable opportunity.

  ctr_gap_score     (0–35)  How far CTR falls below the site-wide average.
                             Low CTR on high-impression queries = high value.

  position_score    (0–20)  Bonus for queries ranking in positions 5–20.
                             These are the most improvable with targeted effort.

  click_gap_score   (0–10)  Absolute conversion gap (1 − clicks/impressions).
                             Impressions that are not converting to clicks.

All inputs are pure numeric values → output is always the same for the same
inputs (deterministic, no random or time-dependent components).
"""

from __future__ import annotations

import math
from typing import Any


def score_opportunity(
    impressions: int,
    clicks: int,
    ctr: float,
    position: float,
    site_avg_ctr: float,
    opportunity_type: str,
) -> tuple[float, dict[str, Any]]:
    """
    Compute a deterministic opportunity score in range [0.0, 100.0].

    Returns (score, breakdown) where breakdown is suitable for storage in
    metadata_json and explains how the score was reached.
    """
    if impressions == 0:
        empty: dict[str, Any] = {
            "opportunity_type": opportunity_type,
            "components": {"impression_score": 0.0, "ctr_gap_score": 0.0, "position_score": 0.0, "click_gap_score": 0.0},
            "raw_score": 0.0,
            "final_score": 0.0,
            "inputs": {"impressions": 0, "clicks": clicks, "ctr": ctr, "position": position, "site_avg_ctr": site_avg_ctr},
        }
        return 0.0, empty

    # ── Component 1: impression volume (0–35, log-scaled) ─────────────────────
    # log10(10001) ≈ 4.0  →  10 000 impressions = maximum 35 points
    # log10(11)    ≈ 1.04 →  10 impressions ≈ 9 points
    imp_score = 35.0 * math.log10(impressions + 1) / math.log10(10001)
    imp_score = round(min(35.0, max(0.0, imp_score)), 4)

    # ── Component 2: CTR gap below site average (0–35) ───────────────────────
    if site_avg_ctr > 0.0:
        ctr_gap = max(0.0, (site_avg_ctr - ctr) / site_avg_ctr)
    else:
        # No site average available: reward zero-click queries
        ctr_gap = 1.0 if clicks == 0 else 0.0
    ctr_gap_score = round(35.0 * ctr_gap, 4)

    # ── Component 3: position bonus for page-2 / positions 5–20 (0–20) ───────
    # Queries in this band have demonstrated relevance but have clear headroom.
    # Position 5 → 20 points; position 20 → 0 points (linear decay).
    # Positions 1–4 receive a small 5-point bonus (already ranking, less upside).
    if 5.0 <= position <= 20.0:
        pos_score = round(20.0 * (1.0 - (position - 5.0) / 15.0), 4)
    elif 0.0 < position < 5.0:
        pos_score = 5.0
    else:
        pos_score = 0.0  # position 0 (no data) or below 20

    # ── Component 4: absolute click gap (0–10) ───────────────────────────────
    # Fraction of impressions not converting — rewards high-volume, low-click queries.
    if impressions > 0:
        click_gap_score = round(10.0 * (1.0 - clicks / impressions), 4)
    else:
        click_gap_score = 0.0

    raw = imp_score + ctr_gap_score + pos_score + click_gap_score
    final = round(min(100.0, max(0.0, raw)), 2)

    breakdown: dict[str, Any] = {
        "opportunity_type": opportunity_type,
        "components": {
            "impression_score": imp_score,
            "ctr_gap_score": ctr_gap_score,
            "position_score": pos_score,
            "click_gap_score": click_gap_score,
        },
        "raw_score": round(raw, 4),
        "final_score": final,
        "inputs": {
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(ctr, 6),
            "position": round(position, 2),
            "site_avg_ctr": round(site_avg_ctr, 6),
        },
    }

    return final, breakdown
