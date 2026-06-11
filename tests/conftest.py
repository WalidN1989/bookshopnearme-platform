from __future__ import annotations

import os
import sys
import tempfile

import pytest

# Add repo root so shared packages resolve without install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "mcp"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "gsc-agent"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "seo-agent"))

from shared.database.connection import DatabaseConnection


@pytest.fixture
def tmp_db(tmp_path):
    """Ephemeral in-memory-like SQLite database for each test."""
    db_file = tmp_path / "test.db"
    db = DatabaseConnection(db_file)
    yield db
    db.close()


@pytest.fixture
def sample_gsc_rows():
    return [
        {
            "keys": ["buy harry potter online sri lanka", "https://bookshopnearme.lk/harry-potter"],
            "impressions": 320,
            "clicks": 18,
            "ctr": 0.05625,
            "position": 4.2,
        },
        {
            "keys": ["online bookshop sri lanka", "https://bookshopnearme.lk/"],
            "impressions": 890,
            "clicks": 67,
            "ctr": 0.07528,
            "position": 2.1,
        },
        {
            "keys": ["sinhala novels buy", "https://bookshopnearme.lk/sinhala"],
            "impressions": 145,
            "clicks": 9,
            "ctr": 0.06207,
            "position": 6.8,
        },
    ]
