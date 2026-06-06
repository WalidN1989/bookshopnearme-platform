from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class Settings:
    # Paths
    project_root: Path = Path(__file__).resolve().parents[2]
    database_path: Path

    # API
    books_api_base_url: str
    books_api_timeout: int

    # GSC — OAuth refresh-token credentials
    gsc_oauth_client_id: str
    gsc_oauth_client_secret: str
    gsc_oauth_refresh_token: str
    gsc_site_url: str
    gsc_lookback_days: int

    # App
    log_level: str
    environment: str

    def __init__(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]

        db_path = os.getenv("DATABASE_PATH", str(self.project_root / "data" / "bookshop.db"))
        self.database_path = Path(db_path)

        self.books_api_base_url = os.getenv(
            "BOOKS_API_BASE_URL",
            "https://pthcjxgnaycbjrlsjhbt.supabase.co/functions/v1/public-books-api",
        )
        self.books_api_timeout = int(os.getenv("BOOKS_API_TIMEOUT", "60"))

        self.gsc_oauth_client_id = os.getenv("GSC_OAUTH_CLIENT_ID", "")
        self.gsc_oauth_client_secret = os.getenv("GSC_OAUTH_CLIENT_SECRET", "")
        self.gsc_oauth_refresh_token = os.getenv("GSC_OAUTH_REFRESH_TOKEN", "")
        self.gsc_site_url = os.getenv("GSC_SITE_URL", "")
        self.gsc_lookback_days = int(os.getenv("GSC_LOOKBACK_DAYS", "7"))

        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.environment = os.getenv("ENVIRONMENT", "development")

    def ensure_data_dir(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
