"""
Resolve GSC credentials from OAuth 2.0 refresh-token environment variables.

Service accounts cannot be added to Google Search Console properties —
Google requires a real user account. OAuth with a refresh token is the
correct headless authentication path for GSC.

Required environment variables:
    GSC_OAUTH_CLIENT_ID      — OAuth 2.0 client ID (from Google Cloud Console)
    GSC_OAUTH_CLIENT_SECRET  — OAuth 2.0 client secret
    GSC_OAUTH_REFRESH_TOKEN  — long-lived refresh token (from gsc_oauth_setup.py)

Run scripts/gsc_oauth_setup.py once locally to obtain the refresh token.
"""

from __future__ import annotations

import os

from shared.logging.logger import get_logger

logger = get_logger("gsc_agent.credentials")

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def resolve_oauth_credentials():
    """
    Build and return a refreshed google.oauth2.credentials.Credentials object.

    Logs startup diagnostics:
      - Which env vars are present (secrets masked)
      - Whether the access token refresh succeeded

    Raises RuntimeError if any required env var is missing.
    Raises google.auth.exceptions.RefreshError if the token is invalid or revoked.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise RuntimeError(
            "google-auth is required. "
            "Install with: pip install google-auth"
        ) from exc

    client_id = os.getenv("GSC_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GSC_OAUTH_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("GSC_OAUTH_REFRESH_TOKEN", "").strip()

    # ── Validate presence ────────────────────────────────────────────────────
    missing = [
        name for name, value in [
            ("GSC_OAUTH_CLIENT_ID", client_id),
            ("GSC_OAUTH_CLIENT_SECRET", client_secret),
            ("GSC_OAUTH_REFRESH_TOKEN", refresh_token),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required OAuth environment variable(s): {', '.join(missing)}\n"
            "Run scripts/gsc_oauth_setup.py to generate these values."
        )

    # ── Log (masked) ─────────────────────────────────────────────────────────
    logger.info(
        f"[AUTH] OAuth credentials loaded — "
        f"client_id={client_id[:8]}... "
        f"refresh_token={'*' * 8}{refresh_token[-4:]}"
    )

    # ── Build credentials object ─────────────────────────────────────────────
    creds = Credentials(
        token=None,                 # no cached access token — force a fresh one
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    # ── Force immediate token refresh — validates all three values right now ─
    try:
        creds.refresh(Request())
        logger.info("[AUTH] Access token refresh successful")
    except Exception as exc:
        raise RuntimeError(
            f"OAuth token refresh failed: {exc}\n"
            "The refresh token may be expired or revoked. "
            "Re-run scripts/gsc_oauth_setup.py to generate a new one."
        ) from exc

    return creds
