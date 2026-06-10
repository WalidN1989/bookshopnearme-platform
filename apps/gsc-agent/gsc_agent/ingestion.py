from __future__ import annotations

from datetime import date, timedelta

from shared.database.connection import DatabaseConnection
from shared.logging.logger import get_logger

logger = get_logger("gsc_agent.ingestion")


def ingest_query_rows(
    db: DatabaseConnection,
    rows: list[dict],
    collection_date: str,
    site_url: str,
) -> int:
    """Parse GSC query+page rows and persist them. Returns records saved."""
    count = 0
    for row in rows:
        keys = row.get("keys", [])
        if len(keys) < 2:
            continue
        query_text, page_url = keys[0], keys[1]

        query_id = db.upsert_gsc_query(query=query_text, date=collection_date, site_url=site_url)
        page_id = db.upsert_gsc_page(page_url=page_url, date=collection_date, site_url=site_url)

        db.upsert_gsc_daily_metric(
            date=collection_date,
            query_id=query_id,
            page_id=page_id,
            impressions=int(row.get("impressions", 0)),
            clicks=int(row.get("clicks", 0)),
            ctr=float(row.get("ctr", 0.0)),
            position=float(row.get("position", 0.0)),
            site_url=site_url,
        )
        count += 1
    return count


def dates_to_collect(db: DatabaseConnection, lookback_days: int, site_url: str) -> list[str]:
    """Return dates in the lookback window that haven't been fully collected for this site."""
    today = date.today()
    # GSC data is typically 2-3 days delayed; collect up to yesterday
    end = today - timedelta(days=1)
    start = end - timedelta(days=lookback_days - 1)

    existing = set(
        db.get_date_range_exists(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            site_url=site_url,
        )
    )

    missing = []
    current = start
    while current <= end:
        ds = current.isoformat()
        if ds not in existing:
            missing.append(ds)
        current += timedelta(days=1)

    return missing
