from __future__ import annotations

import sys
import os

# Allow running from the apps/gsc-agent directory without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from shared.config import get_settings
from shared.database.connection import get_db
from shared.logging.logger import AgentRunLogger, get_logger

from gsc_agent.client import GSCClient
from gsc_agent.credentials import resolve_oauth_credentials
from gsc_agent.ingestion import dates_to_collect, ingest_query_rows

logger = get_logger("gsc_agent.agent")

AGENT_NAME = "gsc_agent"


def run() -> None:
    settings = get_settings()
    db = get_db(settings.database_path)
    run_logger = AgentRunLogger(agent_name=AGENT_NAME, db_connection=db)

    run_logger.started(
        metadata={
            "site_url": settings.gsc_site_url,
            "lookback_days": settings.gsc_lookback_days,
        }
    )

    try:
        if not settings.gsc_site_url:
            raise ValueError("GSC_SITE_URL is not configured")

        credentials = resolve_oauth_credentials()   # logs: loaded + token refreshed
        client = GSCClient(
            credentials=credentials,
            site_url=settings.gsc_site_url,
        )
        client.validate_access()                    # logs: property URL + permission level

        missing_dates = dates_to_collect(db=db, lookback_days=settings.gsc_lookback_days)
        logger.info(f"Dates to collect: {missing_dates}")

        total_records = 0

        for collection_date in missing_dates:
            logger.info(f"Fetching GSC data for {collection_date}")
            rows = client.fetch_query_metrics(
                start_date=collection_date,
                end_date=collection_date,
            )
            saved = ingest_query_rows(db=db, rows=rows, collection_date=collection_date)
            logger.info(f"Saved {saved} records for {collection_date}")
            total_records += saved

        run_logger.completed(
            records_processed=total_records,
            metadata={"dates_collected": missing_dates},
        )

    except Exception as exc:
        run_logger.failed(error=exc)
        raise


if __name__ == "__main__":
    run()
