from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# google-auth and google-api-python-client are optional at import time
# so that the module can be imported in tests without the full Google stack.
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False


SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


class GSCClient:
    """Thin wrapper around the Search Console API."""

    def __init__(self, credentials_path: str | Path, site_url: str) -> None:
        if not _GOOGLE_AVAILABLE:
            raise RuntimeError(
                "google-auth and google-api-python-client are required. "
                "Install them with: pip install google-auth google-api-python-client"
            )
        creds = service_account.Credentials.from_service_account_file(
            str(credentials_path), scopes=SCOPES
        )
        self._service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        self.site_url = site_url

    def fetch_query_metrics(
        self,
        start_date: str,
        end_date: str,
        row_limit: int = 5000,
    ) -> list[dict]:
        """Fetch query-level metrics for a date range."""
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query", "page"],
            "rowLimit": row_limit,
            "dataState": "final",
        }
        response = (
            self._service.searchanalytics()
            .query(siteUrl=self.site_url, body=body)
            .execute()
        )
        return response.get("rows", [])

    def fetch_page_metrics(
        self,
        start_date: str,
        end_date: str,
        row_limit: int = 5000,
    ) -> list[dict]:
        """Fetch page-level metrics for a date range."""
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page"],
            "rowLimit": row_limit,
            "dataState": "final",
        }
        response = (
            self._service.searchanalytics()
            .query(siteUrl=self.site_url, body=body)
            .execute()
        )
        return response.get("rows", [])
