from __future__ import annotations

import pytest

from seo_agent.analyzer import (
    Opportunity,
    _aggregate_by_query_page,
    _site_avg_ctr,
    analyze,
)

SITE = "sc-domain:period.lk"


def _row(query: str, page_url: str, impressions: int, clicks: int, ctr: float, position: float) -> dict:
    return {
        "gsc_queries": {"query": query},
        "gsc_pages": {"page_url": page_url},
        "impressions": impressions,
        "clicks": clicks,
        "ctr": ctr,
        "position": position,
    }


# ── Aggregation helpers ───────────────────────────────────────────────────────

class TestAggregation:
    def test_sums_impressions_and_clicks_across_days(self):
        rows = [
            _row("period panty", "https://period.lk/p", 10, 1, 0.1, 5.0),
            _row("period panty", "https://period.lk/p", 20, 2, 0.1, 6.0),
        ]
        agg = _aggregate_by_query_page(rows)
        assert len(agg) == 1
        key = ("period panty", "https://period.lk/p")
        assert agg[key]["impressions"] == 30
        assert agg[key]["clicks"] == 3

    def test_averages_position(self):
        rows = [
            _row("q", "https://period.lk/p", 10, 1, 0.1, 4.0),
            _row("q", "https://period.lk/p", 10, 1, 0.1, 6.0),
        ]
        agg = _aggregate_by_query_page(rows)
        key = ("q", "https://period.lk/p")
        assert agg[key]["position"] == pytest.approx(5.0)

    def test_computes_ctr_from_totals(self):
        rows = [
            _row("q", "https://period.lk/p", 100, 5, 0.05, 8.0),
            _row("q", "https://period.lk/p", 100, 15, 0.15, 8.0),
        ]
        agg = _aggregate_by_query_page(rows)
        key = ("q", "https://period.lk/p")
        assert agg[key]["ctr"] == pytest.approx(0.10)

    def test_skips_rows_with_missing_query_or_page(self):
        rows = [
            {"gsc_queries": {"query": ""}, "gsc_pages": {"page_url": "https://period.lk/"}, "impressions": 10, "clicks": 1, "ctr": 0.1, "position": 5.0},
            {"gsc_queries": None, "gsc_pages": {"page_url": "https://period.lk/"}, "impressions": 10, "clicks": 1, "ctr": 0.1, "position": 5.0},
        ]
        agg = _aggregate_by_query_page(rows)
        assert len(agg) == 0


class TestSiteAvgCtr:
    def test_weighted_average(self):
        rows = [
            _row("a", "https://period.lk/a", 100, 10, 0.10, 5.0),
            _row("b", "https://period.lk/b", 100, 20, 0.20, 5.0),
        ]
        agg = _aggregate_by_query_page(rows)
        avg = _site_avg_ctr(agg)
        assert avg == pytest.approx(0.15)

    def test_zero_impressions_returns_zero(self):
        assert _site_avg_ctr({}) == 0.0


# ── Opportunity detection ─────────────────────────────────────────────────────

class TestNewContentDetection:
    def test_detects_high_impression_zero_click(self):
        rows = [_row("pressure points for period cramps", "https://period.lk/", 28, 0, 0.0, 30.0)]
        opps = analyze(rows, SITE)
        new_content = [o for o in opps if o.opportunity_type == "NEW_CONTENT"]
        assert any(o.keyword == "pressure points for period cramps" for o in new_content)

    def test_does_not_detect_below_min_impressions(self):
        rows = [_row("rare query", "https://period.lk/", 3, 0, 0.0, 40.0)]
        opps = analyze(rows, SITE)
        assert not any(o.opportunity_type == "NEW_CONTENT" for o in opps)

    def test_does_not_detect_when_ctr_above_threshold(self):
        rows = [_row("good query", "https://period.lk/", 50, 3, 0.06, 8.0)]
        opps = analyze(rows, SITE)
        assert not any(
            o.opportunity_type == "NEW_CONTENT" and o.keyword == "good query"
            for o in opps
        )

    def test_no_duplicate_keyword_across_pages(self):
        rows = [
            _row("shared keyword", "https://period.lk/page-a", 20, 0, 0.0, 25.0),
            _row("shared keyword", "https://period.lk/page-b", 15, 0, 0.0, 28.0),
        ]
        opps = analyze(rows, SITE)
        new_content = [o for o in opps if o.opportunity_type == "NEW_CONTENT"]
        kw_count = sum(1 for o in new_content if o.keyword == "shared keyword")
        assert kw_count == 1


class TestCtrImprovementDetection:
    def test_detects_ctr_well_below_site_average(self):
        # site average will be driven by the second query
        rows = [
            _row("low ctr query", "https://period.lk/low", 50, 1, 0.02, 8.0),
            _row("high ctr anchor", "https://period.lk/hi", 50, 10, 0.20, 3.0),
        ]
        opps = analyze(rows, SITE)
        ctr_opps = [o for o in opps if o.opportunity_type == "CTR_IMPROVEMENT"]
        assert any(o.keyword == "low ctr query" for o in ctr_opps)

    def test_does_not_detect_when_at_site_average(self):
        rows = [
            _row("avg query a", "https://period.lk/a", 50, 5, 0.10, 8.0),
            _row("avg query b", "https://period.lk/b", 50, 5, 0.10, 8.0),
        ]
        opps = analyze(rows, SITE)
        assert not any(o.opportunity_type == "CTR_IMPROVEMENT" for o in opps)


class TestRankingImprovementDetection:
    def test_detects_position_5_to_20_with_clicks(self):
        rows = [_row("mid rank query", "https://period.lk/p", 30, 2, 0.067, 12.0)]
        opps = analyze(rows, SITE)
        rank_opps = [o for o in opps if o.opportunity_type == "RANKING_IMPROVEMENT"]
        assert any(o.keyword == "mid rank query" for o in rank_opps)

    def test_does_not_detect_position_above_20(self):
        rows = [_row("far down query", "https://period.lk/p", 20, 1, 0.05, 25.0)]
        opps = analyze(rows, SITE)
        assert not any(o.opportunity_type == "RANKING_IMPROVEMENT" for o in opps)

    def test_does_not_detect_without_clicks(self):
        rows = [_row("no click query", "https://period.lk/p", 20, 0, 0.0, 10.0)]
        opps = analyze(rows, SITE)
        assert not any(o.opportunity_type == "RANKING_IMPROVEMENT" for o in opps)


class TestPageOptimizationDetection:
    def test_detects_page_ctr_below_site_average(self):
        rows = [
            _row("query a", "https://period.lk/product", 60, 1, 0.017, 8.0),
            _row("query b", "https://period.lk/product", 40, 1, 0.025, 9.0),
            # anchor with high CTR to set site average
            _row("good query", "https://period.lk/home", 50, 10, 0.20, 2.0),
        ]
        opps = analyze(rows, SITE)
        page_opps = [o for o in opps if o.opportunity_type == "PAGE_OPTIMIZATION"]
        assert any(o.page_url == "https://period.lk/product" for o in page_opps)

    def test_one_opportunity_per_page(self):
        rows = [
            _row("query a", "https://period.lk/product", 60, 1, 0.017, 8.0),
            _row("query b", "https://period.lk/product", 40, 1, 0.025, 9.0),
            _row("good query", "https://period.lk/home", 50, 10, 0.20, 2.0),
        ]
        opps = analyze(rows, SITE)
        page_opps = [
            o for o in opps
            if o.opportunity_type == "PAGE_OPTIMIZATION"
            and o.page_url == "https://period.lk/product"
        ]
        assert len(page_opps) == 1


class TestOpportunityOrdering:
    def test_opportunities_sorted_by_score_desc(self):
        rows = [
            # many impressions, 0 clicks → should score very high
            _row("high value", "https://period.lk/p", 500, 0, 0.0, 25.0),
            # few impressions, 0 clicks → lower score
            _row("low value", "https://period.lk/q", 8, 0, 0.0, 28.0),
        ]
        opps = analyze(rows, SITE)
        scores = [o.opportunity_score for o in opps]
        assert scores == sorted(scores, reverse=True)

    def test_empty_rows_returns_empty_list(self):
        assert analyze([], SITE) == []


class TestRecommendationContent:
    def test_new_content_recommendation_mentions_keyword(self):
        rows = [_row("period pain relief", "https://period.lk/", 20, 0, 0.0, 30.0)]
        opps = analyze(rows, SITE)
        new_content = [o for o in opps if o.opportunity_type == "NEW_CONTENT"]
        assert new_content
        assert "period pain relief" in new_content[0].recommendation

    def test_ranking_recommendation_mentions_page_url(self):
        rows = [_row("period shorts", "https://period.lk/products/shorts", 20, 2, 0.10, 9.0)]
        opps = analyze(rows, SITE)
        rank = [o for o in opps if o.opportunity_type == "RANKING_IMPROVEMENT"]
        if rank:
            assert "period.lk/products/shorts" in rank[0].recommendation
