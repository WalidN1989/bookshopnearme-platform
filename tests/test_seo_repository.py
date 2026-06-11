from __future__ import annotations

import json

import pytest

from shared.database.connection import DatabaseConnection
from seo_agent.analyzer import Opportunity
from seo_agent.repository import save_opportunities

SITE = "sc-domain:period.lk"


def _make_opp(**kwargs) -> Opportunity:
    defaults = dict(
        opportunity_type="NEW_CONTENT",
        keyword="period pain relief",
        page_url="https://period.lk/",
        impressions=28,
        clicks=0,
        ctr=0.0,
        position=30.0,
        opportunity_score=57.8,
        recommendation="Create dedicated content targeting 'period pain relief'.",
        metadata={"scoring": {"impression_score": 12.8}, "site_avg_ctr": 0.031},
    )
    defaults.update(kwargs)
    return Opportunity(**defaults)


class TestSaveOpportunities:
    def test_saves_opportunity_to_db(self, tmp_db: DatabaseConnection):
        opps = [_make_opp()]
        count = save_opportunities(tmp_db, opps, SITE)
        assert count == 1
        rows = tmp_db.get_seo_opportunities(SITE)
        assert len(rows) == 1
        assert rows[0]["keyword"] == "period pain relief"
        assert rows[0]["opportunity_type"] == "NEW_CONTENT"

    def test_save_is_idempotent(self, tmp_db: DatabaseConnection):
        opp = _make_opp()
        save_opportunities(tmp_db, [opp], SITE)
        save_opportunities(tmp_db, [opp], SITE)
        rows = tmp_db.get_seo_opportunities(SITE)
        assert len(rows) == 1

    def test_update_preserves_status(self, tmp_db: DatabaseConnection):
        opp = _make_opp()
        save_opportunities(tmp_db, [opp], SITE)

        # Manually set status to 'approved'
        tmp_db.conn.execute(
            "UPDATE seo_opportunities SET status='approved' WHERE keyword=?",
            (opp.keyword,),
        )
        tmp_db.conn.commit()

        # Re-save with updated score — status must remain 'approved'
        updated = _make_opp(opportunity_score=65.0)
        save_opportunities(tmp_db, [updated], SITE)

        rows = tmp_db.get_seo_opportunities(SITE)
        assert len(rows) == 1
        assert rows[0]["status"] == "approved"
        assert rows[0]["opportunity_score"] == pytest.approx(65.0)

    def test_saves_multiple_types(self, tmp_db: DatabaseConnection):
        opps = [
            _make_opp(opportunity_type="NEW_CONTENT", keyword="query a"),
            _make_opp(opportunity_type="CTR_IMPROVEMENT", keyword="query b", page_url="https://period.lk/b", ctr=0.01),
            _make_opp(opportunity_type="RANKING_IMPROVEMENT", keyword="query c", page_url="https://period.lk/c", position=10.0, clicks=2),
        ]
        count = save_opportunities(tmp_db, opps, SITE)
        assert count == 3
        rows = tmp_db.get_seo_opportunities(SITE)
        assert len(rows) == 3

    def test_returns_count_of_processed_rows(self, tmp_db: DatabaseConnection):
        opps = [_make_opp(keyword=f"query {i}", page_url=f"https://period.lk/{i}") for i in range(5)]
        count = save_opportunities(tmp_db, opps, SITE)
        assert count == 5

    def test_metadata_json_stored_and_retrieved(self, tmp_db: DatabaseConnection):
        meta = {"scoring": {"impression_score": 12.8}, "site_avg_ctr": 0.031}
        opp = _make_opp(metadata=meta)
        save_opportunities(tmp_db, [opp], SITE)
        rows = tmp_db.get_seo_opportunities(SITE)
        stored_meta = rows[0]["metadata_json"]
        if isinstance(stored_meta, str):
            stored_meta = json.loads(stored_meta)
        assert stored_meta["site_avg_ctr"] == pytest.approx(0.031)


class TestGetSeoOpportunities:
    def test_filter_by_type(self, tmp_db: DatabaseConnection):
        opps = [
            _make_opp(opportunity_type="NEW_CONTENT", keyword="a"),
            _make_opp(opportunity_type="CTR_IMPROVEMENT", keyword="b", page_url="https://period.lk/b", ctr=0.01),
        ]
        save_opportunities(tmp_db, opps, SITE)
        rows = tmp_db.get_seo_opportunities(SITE, opportunity_type="NEW_CONTENT")
        assert all(r["opportunity_type"] == "NEW_CONTENT" for r in rows)

    def test_filter_by_status(self, tmp_db: DatabaseConnection):
        save_opportunities(tmp_db, [_make_opp()], SITE)
        pending = tmp_db.get_seo_opportunities(SITE, status="pending")
        assert len(pending) == 1
        approved = tmp_db.get_seo_opportunities(SITE, status="approved")
        assert len(approved) == 0

    def test_ordered_by_score_desc(self, tmp_db: DatabaseConnection):
        opps = [
            _make_opp(keyword="low", opportunity_score=20.0),
            _make_opp(keyword="high", page_url="https://period.lk/high", opportunity_score=80.0),
            _make_opp(keyword="mid", page_url="https://period.lk/mid", opportunity_score=50.0),
        ]
        save_opportunities(tmp_db, opps, SITE)
        rows = tmp_db.get_seo_opportunities(SITE)
        scores = [r["opportunity_score"] for r in rows]
        assert scores == sorted(scores, reverse=True)

    def test_limit_respected(self, tmp_db: DatabaseConnection):
        opps = [
            _make_opp(keyword=f"q{i}", page_url=f"https://period.lk/{i}", opportunity_score=float(i))
            for i in range(10)
        ]
        save_opportunities(tmp_db, opps, SITE)
        rows = tmp_db.get_seo_opportunities(SITE, limit=3)
        assert len(rows) == 3

    def test_site_isolation(self, tmp_db: DatabaseConnection):
        save_opportunities(tmp_db, [_make_opp()], SITE)
        other = tmp_db.get_seo_opportunities("sc-domain:bookshopnearme.lk")
        assert len(other) == 0


class TestGetSeoOpportunityById:
    def test_returns_correct_row(self, tmp_db: DatabaseConnection):
        save_opportunities(tmp_db, [_make_opp()], SITE)
        all_rows = tmp_db.get_seo_opportunities(SITE)
        opp_id = all_rows[0]["id"]
        row = tmp_db.get_seo_opportunity_by_id(opp_id)
        assert row is not None
        assert row["id"] == opp_id
        assert row["keyword"] == "period pain relief"

    def test_returns_none_for_missing_id(self, tmp_db: DatabaseConnection):
        assert tmp_db.get_seo_opportunity_by_id(999999) is None
