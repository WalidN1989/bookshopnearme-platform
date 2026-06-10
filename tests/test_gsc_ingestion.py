from __future__ import annotations

from datetime import date, timedelta

from shared.database.connection import DatabaseConnection
from gsc_agent.ingestion import dates_to_collect, ingest_query_rows

SITE_A = "https://bookshopnearme.lk/"
SITE_B = "https://period.lk/"


def test_ingest_query_rows_basic(tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]):
    count = ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date="2026-01-01", site_url=SITE_A)
    assert count == len(sample_gsc_rows)

    metrics = tmp_db.get_gsc_metrics_for_date("2026-01-01", site_url=SITE_A)
    assert len(metrics) == len(sample_gsc_rows)


def test_ingest_query_rows_idempotent(tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]):
    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date="2026-01-01", site_url=SITE_A)
    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date="2026-01-01", site_url=SITE_A)

    metrics = tmp_db.get_gsc_metrics_for_date("2026-01-01", site_url=SITE_A)
    assert len(metrics) == len(sample_gsc_rows)


def test_ingest_skips_rows_missing_keys(tmp_db: DatabaseConnection):
    rows = [
        {"keys": ["only_query"], "impressions": 10, "clicks": 1, "ctr": 0.1, "position": 3.0},
        {"keys": [], "impressions": 5, "clicks": 0, "ctr": 0.0, "position": 0.0},
    ]
    count = ingest_query_rows(db=tmp_db, rows=rows, collection_date="2026-01-01", site_url=SITE_A)
    assert count == 0


def test_ingest_impressions_stored_correctly(
    tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]
):
    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date="2026-05-15", site_url=SITE_A)
    metrics = tmp_db.get_gsc_metrics_for_date("2026-05-15", site_url=SITE_A)
    stored_impressions = sorted(m["impressions"] for m in metrics)
    expected = sorted(int(r["impressions"]) for r in sample_gsc_rows)
    assert stored_impressions == expected


def test_dates_to_collect_all_missing(tmp_db: DatabaseConnection):
    yesterday = date.today() - timedelta(days=1)
    missing = dates_to_collect(db=tmp_db, lookback_days=3, site_url=SITE_A)
    assert len(missing) == 3
    assert missing[-1] == yesterday.isoformat()


def test_dates_to_collect_skips_existing(
    tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]
):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date=yesterday, site_url=SITE_A)

    missing = dates_to_collect(db=tmp_db, lookback_days=3, site_url=SITE_A)
    assert yesterday not in missing


def test_two_sites_collect_independently(
    tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]
):
    """Filling dates for site A must not suppress date collection for site B."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date=yesterday, site_url=SITE_A)

    # site B has no data yet — yesterday must still appear as missing
    missing_b = dates_to_collect(db=tmp_db, lookback_days=3, site_url=SITE_B)
    assert yesterday in missing_b

    # site A already has yesterday — it must not appear as missing
    missing_a = dates_to_collect(db=tmp_db, lookback_days=3, site_url=SITE_A)
    assert yesterday not in missing_a
