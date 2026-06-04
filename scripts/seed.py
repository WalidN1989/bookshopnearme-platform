"""Seed script for local development. Populates the database with sample data."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "gsc-agent"))

from shared.config import get_settings
from shared.database.connection import DatabaseConnection
from shared.logging.logger import get_logger

logger = get_logger("seed")

SAMPLE_GSC_ROWS = [
    {
        "date": "2026-05-28",
        "query": "buy books online sri lanka",
        "page": "https://bookshopnearme.lk/",
        "impressions": 1240,
        "clicks": 98,
        "ctr": 0.079,
        "position": 2.3,
    },
    {
        "date": "2026-05-28",
        "query": "harry potter books sri lanka",
        "page": "https://bookshopnearme.lk/harry-potter",
        "impressions": 430,
        "clicks": 31,
        "ctr": 0.072,
        "position": 3.1,
    },
    {
        "date": "2026-05-28",
        "query": "sinhala novels online",
        "page": "https://bookshopnearme.lk/sinhala",
        "impressions": 215,
        "clicks": 14,
        "ctr": 0.065,
        "position": 5.7,
    },
    {
        "date": "2026-05-29",
        "query": "buy books online sri lanka",
        "page": "https://bookshopnearme.lk/",
        "impressions": 1180,
        "clicks": 91,
        "ctr": 0.077,
        "position": 2.4,
    },
    {
        "date": "2026-05-29",
        "query": "children books colombo",
        "page": "https://bookshopnearme.lk/children",
        "impressions": 87,
        "clicks": 6,
        "ctr": 0.069,
        "position": 7.2,
    },
]

SAMPLE_OPPORTUNITIES = [
    {
        "keyword": "buy harry potter sri lanka",
        "source": "GSC",
        "search_volume": 430,
        "difficulty": 0.32,
        "book_available": True,
        "priority_score": 8.5,
        "notes": "High-intent purchase query, book is in catalog",
    },
    {
        "keyword": "online bookshop colombo",
        "source": "GSC",
        "search_volume": 890,
        "difficulty": 0.45,
        "book_available": False,
        "priority_score": 7.2,
        "notes": "Location-specific query, strong local intent",
    },
    {
        "keyword": "sinhala novel books",
        "source": "MANUAL",
        "search_volume": None,
        "difficulty": None,
        "book_available": True,
        "priority_score": 6.0,
        "notes": "Local language — underserved niche",
    },
]


def seed(db_path: str | None = None) -> None:
    settings = get_settings()
    path = db_path or settings.database_path
    db = DatabaseConnection(path)

    logger.info(f"Seeding database at {path}")

    for row in SAMPLE_GSC_ROWS:
        qid = db.upsert_gsc_query(row["query"], row["date"])
        pid = db.upsert_gsc_page(row["page"], row["date"])
        db.upsert_gsc_daily_metric(
            date=row["date"],
            query_id=qid,
            page_id=pid,
            impressions=row["impressions"],
            clicks=row["clicks"],
            ctr=row["ctr"],
            position=row["position"],
        )

    for opp in SAMPLE_OPPORTUNITIES:
        db.insert_content_opportunity(**opp)  # type: ignore[arg-type]

    db.set_setting("seeded_at", "2026-05-28")
    logger.info("Seed complete.")
    db.close()


if __name__ == "__main__":
    seed()
