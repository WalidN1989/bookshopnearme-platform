from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from shared.database.connection import DatabaseConnection
from gsc_agent.ingestion import dates_to_collect, ingest_query_rows


def test_ingest_query_rows_basic(tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]):
    count = ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date="2026-01-01")
    assert count == len(sample_gsc_rows)

    metrics = tmp_db.get_gsc_metrics_for_date("2026-01-01")
    assert len(metrics) == len(sample_gsc_rows)


def test_ingest_query_rows_idempotent(tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]):
    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date="2026-01-01")
    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date="2026-01-01")

    metrics = tmp_db.get_gsc_metrics_for_date("2026-01-01")
    assert len(metrics) == len(sample_gsc_rows)


def test_ingest_skips_rows_missing_keys(tmp_db: DatabaseConnection):
    rows = [
        {"keys": ["only_query"], "impressions": 10, "clicks": 1, "ctr": 0.1, "position": 3.0},
        {"keys": [], "impressions": 5, "clicks": 0, "ctr": 0.0, "position": 0.0},
    ]
    count = ingest_query_rows(db=tmp_db, rows=rows, collection_date="2026-01-01")
    assert count == 0


def test_ingest_impressions_stored_correctly(
    tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]
):
    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date="2026-05-15")
    metrics = tmp_db.get_gsc_metrics_for_date("2026-05-15")
    stored_impressions = sorted(m["impressions"] for m in metrics)
    expected = sorted(int(r["impressions"]) for r in sample_gsc_rows)
    assert stored_impressions == expected


def test_dates_to_collect_all_missing(tmp_db: DatabaseConnection):
    yesterday = date.today() - timedelta(days=1)
    missing = dates_to_collect(db=tmp_db, lookback_days=3)
    assert len(missing) == 3
    assert missing[-1] == yesterday.isoformat()


def test_dates_to_collect_skips_existing(
    tmp_db: DatabaseConnection, sample_gsc_rows: list[dict]
):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    ingest_query_rows(db=tmp_db, rows=sample_gsc_rows, collection_date=yesterday)

    missing = dates_to_collect(db=tmp_db, lookback_days=3)
    assert yesterday not in missing
