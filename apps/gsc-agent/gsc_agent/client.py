from __future__ import annotations

from shared.logging.logger import get_logger

logger = get_logger("gsc_agent.client")

# google-api-python-client is optional at import time so the module can be
# imported in tests without the full Google stack installed.
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


class GSCClient:
    """Thin wrapper around the Search Console API using OAuth credentials."""

    def __init__(self, credentials, site_url: str) -> None:
        """
        Args:
            credentials: A refreshed google.oauth2.credentials.Credentials object.
                         Use gsc_agent.credentials.resolve_oauth_credentials() to obtain one.
            site_url:    The GSC property URL exactly as registered
                         (e.g. "https://bookshopnearme.lk/").
        """
        if not _GOOGLE_AVAILABLE:
            raise RuntimeError(
                "google-api-python-client is required. "
                "Install with: pip install google-api-python-client"
            )
        self._service = build(
            "searchconsole", "v1", credentials=credentials, cache_discovery=False
        )
        self.site_url = site_url

    # ── Startup diagnostic ───────────────────────────────────────────────────

    def validate_access(self) -> None:
        """
        Confirm the authenticated user has access to self.site_url.

        Logs the property URL and permission level on success.
        Raises RuntimeError listing accessible sites if the target is absent.
        """
        try:
            response = self._service.sites().list().execute()
        except Exception as exc:
            raise RuntimeError(f"sites().list() failed: {exc}") from exc

        entries = response.get("siteEntry", [])
        accessible = {e["siteUrl"]: e.get("permissionLevel", "unknown") for e in entries}

        if self.site_url in accessible:
            logger.info(
                f"[AUTH] Search Console property accessible — "
                f"url={self.site_url} "
                f"permission={accessible[self.site_url]}"
            )
            return

        # Not found — log what IS accessible so the user can diagnose
        if accessible:
            listed = ", ".join(f"{u} ({p})" for u, p in accessible.items())
            raise RuntimeError(
                f"Site '{self.site_url}' not found in accessible GSC properties.\n"
                f"Accessible properties: {listed}\n"
                "Check that GSC_SITE_URL exactly matches a property the OAuth user owns."
            )
        else:
            raise RuntimeError(
                f"Site '{self.site_url}' not found — sites().list() returned 0 properties.\n"
                "The authenticated Google account has not been verified as an owner "
                "or full user of any Search Console property."
            )

    # ── Data fetching ────────────────────────────────────────────────────────

    def fetch_query_metrics(
        self,
        start_date: str,
        end_date: str,
        row_limit: int = 5000,
    ) -> list[dict]:
        """Fetch query+page metrics for a single date range."""
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
        """Fetch page-level metrics for a single date range."""
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
