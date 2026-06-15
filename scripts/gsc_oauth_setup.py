"""
One-time OAuth 2.0 setup script.

Run this locally to obtain the refresh token that the GSC agent uses
on Railway. You only need to run this once (or again if the token is
revoked or expired).

Usage:
    python scripts/gsc_oauth_setup.py --client-secrets /path/to/client_secret.json

What it does:
    1. Opens your browser for Google OAuth consent
    2. You log in with the Google account that owns the GSC property
    3. Prints CLIENT_ID, CLIENT_SECRET, and REFRESH_TOKEN
    4. Copy those three values into Railway environment variables

Requirements:
    pip install google-auth-oauthlib

See docs/gsc_oauth_setup.md for full step-by-step instructions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a GSC OAuth refresh token for the BookShopNearMe GSC agent."
    )
    parser.add_argument(
        "--client-secrets",
        metavar="PATH",
        help="Path to the OAuth 2.0 client secrets JSON downloaded from Google Cloud Console.",
    )
    parser.add_argument(
        "--client-id",
        metavar="CLIENT_ID",
        help="OAuth Client ID (alternative to --client-secrets).",
    )
    parser.add_argument(
        "--client-secret",
        metavar="CLIENT_SECRET",
        help="OAuth Client Secret (alternative to --client-secrets).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local port for the OAuth callback server (0 = random available port).",
    )
    args = parser.parse_args()

    # ── Resolve client_id / client_secret ─────────────────────────────────────
    if args.client_id and args.client_secret:
        client_id = args.client_id
        client_secret = args.client_secret
    elif args.client_secrets:
        if not os.path.exists(args.client_secrets):
            print(f"ERROR: File not found: {args.client_secrets}", file=sys.stderr)
            sys.exit(1)
        with open(args.client_secrets) as f:
            raw = json.load(f)
        key = next((k for k in ("installed", "web") if k in raw), None)
        if key is None:
            print(
                "ERROR: client secrets file does not contain an 'installed' or 'web' key.\n"
                "Download type must be 'Desktop app' from Google Cloud Console → Credentials.",
                file=sys.stderr,
            )
            sys.exit(1)
        client_id = raw[key]["client_id"]
        client_secret = raw[key]["client_secret"]
    else:
        print(
            "ERROR: provide either --client-secrets PATH\n"
            "       or both --client-id CLIENT_ID --client-secret CLIENT_SECRET",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Import oauthlib ───────────────────────────────────────────────────────
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "ERROR: google-auth-oauthlib is not installed.\n"
            "Run: pip install google-auth-oauthlib",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Run the OAuth flow ────────────────────────────────────────────────────
    print()
    print("Opening your browser for Google OAuth authorization...")
    print("Log in with the Google account that owns the Search Console property.")
    print()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)

    try:
        creds = flow.run_local_server(
            port=args.port,
            prompt="consent",          # always show consent screen so refresh_token is returned
            access_type="offline",
        )
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)

    if not creds.refresh_token:
        print(
            "\nWARNING: No refresh token returned.\n"
            "This can happen if you have previously authorized this app.\n"
            "To force a new refresh token:\n"
            "  1. Go to https://myaccount.google.com/permissions\n"
            "  2. Remove access for your app\n"
            "  3. Re-run this script",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Print results ─────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("SUCCESS — copy these three values into Railway Variables")
    print("=" * 60)
    print()
    print(f"GSC_OAUTH_CLIENT_ID={client_id}")
    print(f"GSC_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"GSC_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
    print()
    print("=" * 60)
    print("IMPORTANT")
    print("=" * 60)
    print("- Do NOT put these in .env or commit them to git")
    print("- Set them directly in the Railway dashboard under Variables")
    print("- The refresh token is long-lived but can be revoked via")
    print("  https://myaccount.google.com/permissions")
    print()

    # ── Quick validation ──────────────────────────────────────────────────────
    print("Validating: calling sites().list() to confirm GSC access...")
    try:
        from googleapiclient.discovery import build
        service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        response = service.sites().list().execute()
        entries = response.get("siteEntry", [])
        if entries:
            print(f"Confirmed access to {len(entries)} GSC property/properties:")
            for e in entries:
                print(f"  {e['siteUrl']}  ({e.get('permissionLevel', 'unknown')})")
        else:
            print(
                "WARNING: sites().list() returned 0 properties.\n"
                "This account has no verified GSC properties yet.\n"
                "Add and verify https://bookshopnearme.lk/ in Search Console,\n"
                "then re-run this script."
            )
    except Exception as exc:
        print(f"WARNING: Could not validate GSC access: {exc}")

    print()
    print("Setup complete.")


if __name__ == "__main__":
    main()
