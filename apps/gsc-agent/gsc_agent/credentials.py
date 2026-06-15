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

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from shared.logging.logger import get_logger

logger = get_logger("gsc_agent.credentials")

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def resolve_oauth_credentials():
    """
    Build and return a refreshed google.oauth2.credentials.Credentials object.

    Uses a direct HTTP POST to the token endpoint instead of google-auth's
    reauth layer, which adds extra parameters that Google rejects for
    desktop OAuth clients in newer library versions.

    Raises RuntimeError if any required env var is missing or the refresh fails.
    """
    try:
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

    # ── Direct HTTP token refresh (bypasses google-auth reauth layer) ────────
    post_data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")

    req = urllib.request.Request(
        TOKEN_URI,
        data=post_data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            error_body = {"error": str(exc)}
        raise RuntimeError(
            f"OAuth token refresh failed: {error_body}\n"
            "The refresh token may be expired or revoked. "
            "Re-run scripts/gsc_oauth_setup.py to generate a new one."
        ) from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError(
            f"OAuth token refresh returned no access_token: {token_data}\n"
            "The refresh token may be expired or revoked. "
            "Re-run scripts/gsc_oauth_setup.py to generate a new one."
        )

    logger.info("[AUTH] Access token refresh successful")

    expires_in = token_data.get("expires_in", 3600)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    return Credentials(
        token=access_token,
        refresh_token=token_data.get("refresh_token", refresh_token),
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
        expiry=expiry,
    )
