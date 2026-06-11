from __future__ import annotations

import math

from seo_agent.scorer import score_opportunity


SITE_AVG = 0.031  # 3.1 % — realistic period.lk average


class TestScoreRange:
    def test_score_is_between_0_and_100(self):
        score, _ = score_opportunity(50, 3, 0.06, 8.0, SITE_AVG, "RANKING_IMPROVEMENT")
        assert 0.0 <= score <= 100.0

    def test_zero_impressions_gives_zero(self):
        score, _ = score_opportunity(0, 0, 0.0, 0.0, SITE_AVG, "NEW_CONTENT")
        assert score == 0.0

    def test_high_impressions_high_score(self):
        score_hi, _ = score_opportunity(5000, 0, 0.0, 0.0, SITE_AVG, "NEW_CONTENT")
        score_lo, _ = score_opportunity(10, 0, 0.0, 0.0, SITE_AVG, "NEW_CONTENT")
        assert score_hi > score_lo


class TestDeterminism:
    def test_same_inputs_same_output(self):
        a, _ = score_opportunity(100, 5, 0.05, 10.0, SITE_AVG, "CTR_IMPROVEMENT")
        b, _ = score_opportunity(100, 5, 0.05, 10.0, SITE_AVG, "CTR_IMPROVEMENT")
        assert a == b

    def test_score_does_not_depend_on_opportunity_type_string(self):
        s1, _ = score_opportunity(100, 5, 0.05, 10.0, SITE_AVG, "NEW_CONTENT")
        s2, _ = score_opportunity(100, 5, 0.05, 10.0, SITE_AVG, "CTR_IMPROVEMENT")
        # The type is stored in metadata but must not change the numeric score
        assert s1 == s2


class TestImpressionComponent:
    def test_impression_score_log_scaled(self):
        _, b10 = score_opportunity(10, 0, 0.0, 0.0, 0.0, "NEW_CONTENT")
        _, b100 = score_opportunity(100, 0, 0.0, 0.0, 0.0, "NEW_CONTENT")
        _, b1000 = score_opportunity(1000, 0, 0.0, 0.0, 0.0, "NEW_CONTENT")
        imp10 = b10["components"]["impression_score"]
        imp100 = b100["components"]["impression_score"]
        imp1000 = b1000["components"]["impression_score"]
        # Logarithmic: each 10x increase gives roughly equal additive increment
        assert imp10 < imp100 < imp1000
        # Increments should be roughly equal (log scale)
        delta1 = imp100 - imp10
        delta2 = imp1000 - imp100
        assert abs(delta1 - delta2) < 3.0  # within 3 points

    def test_impression_score_capped_at_35(self):
        _, b = score_opportunity(100_000, 0, 0.0, 0.0, 0.0, "NEW_CONTENT")
        assert b["components"]["impression_score"] == 35.0


class TestCtrGapComponent:
    def test_zero_ctr_gives_max_gap(self):
        _, b = score_opportunity(50, 0, 0.0, 0.0, SITE_AVG, "NEW_CONTENT")
        assert b["components"]["ctr_gap_score"] == 35.0

    def test_ctr_above_avg_gives_zero_gap(self):
        _, b = score_opportunity(50, 10, 0.20, 5.0, SITE_AVG, "CTR_IMPROVEMENT")
        assert b["components"]["ctr_gap_score"] == 0.0

    def test_ctr_at_avg_gives_zero_gap(self):
        _, b = score_opportunity(50, 2, SITE_AVG, 5.0, SITE_AVG, "CTR_IMPROVEMENT")
        assert b["components"]["ctr_gap_score"] == 0.0

    def test_ctr_half_avg_gives_half_max_gap(self):
        _, b = score_opportunity(50, 1, SITE_AVG / 2, 5.0, SITE_AVG, "CTR_IMPROVEMENT")
        assert abs(b["components"]["ctr_gap_score"] - 17.5) < 0.01


class TestPositionComponent:
    def test_position_5_gives_max(self):
        _, b = score_opportunity(50, 2, 0.04, 5.0, SITE_AVG, "RANKING_IMPROVEMENT")
        assert b["components"]["position_score"] == 20.0

    def test_position_20_gives_zero(self):
        _, b = score_opportunity(50, 2, 0.04, 20.0, SITE_AVG, "RANKING_IMPROVEMENT")
        assert b["components"]["position_score"] == 0.0

    def test_position_12_5_gives_half(self):
        _, b = score_opportunity(50, 2, 0.04, 12.5, SITE_AVG, "RANKING_IMPROVEMENT")
        assert abs(b["components"]["position_score"] - 10.0) < 0.01

    def test_position_1_to_4_gives_small_bonus(self):
        _, b = score_opportunity(50, 5, 0.10, 2.0, SITE_AVG, "RANKING_IMPROVEMENT")
        assert b["components"]["position_score"] == 5.0

    def test_position_above_20_gives_zero(self):
        _, b = score_opportunity(50, 1, 0.02, 35.0, SITE_AVG, "RANKING_IMPROVEMENT")
        assert b["components"]["position_score"] == 0.0

    def test_position_zero_gives_zero(self):
        _, b = score_opportunity(50, 0, 0.0, 0.0, SITE_AVG, "NEW_CONTENT")
        assert b["components"]["position_score"] == 0.0


class TestClickGapComponent:
    def test_no_clicks_gives_max(self):
        _, b = score_opportunity(50, 0, 0.0, 0.0, SITE_AVG, "NEW_CONTENT")
        assert b["components"]["click_gap_score"] == 10.0

    def test_all_clicks_gives_zero(self):
        _, b = score_opportunity(50, 50, 1.0, 1.0, SITE_AVG, "RANKING_IMPROVEMENT")
        assert b["components"]["click_gap_score"] == 0.0

    def test_half_clicks(self):
        _, b = score_opportunity(100, 50, 0.5, 5.0, SITE_AVG, "RANKING_IMPROVEMENT")
        assert abs(b["components"]["click_gap_score"] - 5.0) < 0.01


class TestBreakdownMetadata:
    def test_breakdown_contains_all_components(self):
        _, b = score_opportunity(100, 3, 0.03, 8.0, SITE_AVG, "RANKING_IMPROVEMENT")
        assert "components" in b
        comps = b["components"]
        for key in ("impression_score", "ctr_gap_score", "position_score", "click_gap_score"):
            assert key in comps

    def test_breakdown_inputs_match_args(self):
        _, b = score_opportunity(123, 7, 0.05, 9.0, SITE_AVG, "CTR_IMPROVEMENT")
        assert b["inputs"]["impressions"] == 123
        assert b["inputs"]["clicks"] == 7

    def test_breakdown_opportunity_type_stored(self):
        _, b = score_opportunity(50, 0, 0.0, 0.0, SITE_AVG, "NEW_CONTENT")
        assert b["opportunity_type"] == "NEW_CONTENT"


class TestRealWorldExamples:
    """Verify that scoring correctly prioritizes period.lk-style opportunities."""

    def test_new_content_keyword_scores_higher_than_ranking_improvement(self):
        # "pressure points for period cramps": 28 impressions, 0 clicks — NEW_CONTENT
        nc_score, _ = score_opportunity(28, 0, 0.0, 30.0, SITE_AVG, "NEW_CONTENT")
        # "period panty sri lanka": 52 impressions, 3 clicks, CTR above avg — RANKING
        ri_score, _ = score_opportunity(52, 3, 0.058, 8.0, SITE_AVG, "RANKING_IMPROVEMENT")
        # New content with zero engagement should score higher
        assert nc_score > ri_score

    def test_higher_impressions_same_ctr_scores_higher(self):
        s_low, _ = score_opportunity(20, 0, 0.0, 25.0, SITE_AVG, "NEW_CONTENT")
        s_high, _ = score_opportunity(100, 0, 0.0, 25.0, SITE_AVG, "NEW_CONTENT")
        assert s_high > s_low
