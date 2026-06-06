"""
Temporary diagnostic script — NOT for production use.
Tests GSC API connectivity with the service account JSON.

Usage:
    python scripts/gsc_diagnostic.py
    python scripts/gsc_diagnostic.py /path/to/other-key.json

Delete this file after diagnosis is complete.
"""

from __future__ import annotations

import json
import sys
import os

# Default to the downloaded key — override via CLI arg
DEFAULT_KEY_PATH = "/Users/mohammedwalidnazmi/Downloads/bookshopnearme-gsc-4d56be0cc58e.json"
KEY_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_KEY_PATH

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── 1. Load and inspect the JSON ─────────────────────────────────────────────
print("=" * 60)
print("STEP 1: Load service account JSON")
print("=" * 60)

try:
    with open(KEY_PATH) as f:
        key_data = json.load(f)

    safe_fields = {k: v for k, v in key_data.items() if k != "private_key"}
    for field, value in safe_fields.items():
        print(f"  {field}: {value}")
    print(f"  private_key: [present, {len(key_data.get('private_key', ''))} chars]")
    print()

    if key_data.get("type") != "service_account":
        print(f"  WARNING: type is '{key_data.get('type')}', expected 'service_account'")
except FileNotFoundError:
    print(f"  ERROR: File not found: {KEY_PATH}")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"  ERROR: Invalid JSON: {e}")
    sys.exit(1)

# ── 2. Build credentials ──────────────────────────────────────────────────────
print("=" * 60)
print("STEP 2: Build service account credentials")
print("=" * 60)

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"  ERROR: Missing dependency: {e}")
    print("  Run: pip install google-auth google-api-python-client")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

try:
    creds = service_account.Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
    print(f"  service_account_email : {creds.service_account_email}")
    print(f"  scopes                : {list(creds.scopes)}")
    print(f"  token_uri             : {creds._token_uri}")
    print()
except Exception as e:
    print(f"  ERROR building credentials: {type(e).__name__}: {e}")
    sys.exit(1)

# ── 3. Build the API service ──────────────────────────────────────────────────
print("=" * 60)
print("STEP 3: Build Search Console API client")
print("=" * 60)

try:
    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    print("  API client built successfully")
    print()
except Exception as e:
    print(f"  ERROR building API client: {type(e).__name__}: {e}")
    sys.exit(1)

# ── 4. Call sites().list() ────────────────────────────────────────────────────
print("=" * 60)
print("STEP 4: Call sites().list()")
print("=" * 60)

try:
    response = service.sites().list().execute()
    print("  Raw response:")
    print(json.dumps(response, indent=4))
    print()

    sites = response.get("siteEntry", [])
    if not sites:
        print("  RESULT: The service account has access to 0 GSC properties.")
        print("  This means it has not been added as a user to any property yet.")
    else:
        print(f"  RESULT: Service account has access to {len(sites)} property/properties:")
        for site in sites:
            print(f"    siteUrl         : {site.get('siteUrl')}")
            print(f"    permissionLevel : {site.get('permissionLevel')}")
            print()

except HttpError as e:
    print(f"  HTTP ERROR {e.status_code}: {e.reason}")
    try:
        detail = json.loads(e.content)
        print(f"  Detail: {json.dumps(detail, indent=4)}")
    except Exception:
        print(f"  Raw content: {e.content}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# ── 5. Summary ────────────────────────────────────────────────────────────────
print("=" * 60)
print("STEP 5: Summary")
print("=" * 60)
print(f"  Key file     : {KEY_PATH}")
print(f"  Client email : {key_data.get('client_email')}")
print(f"  Project      : {key_data.get('project_id')}")
print()
print("  Next step if sites list is empty:")
print("  → In Google Search Console, add this email as a Full user")
print(f"    on the target property: {key_data.get('client_email')}")
print()
print("  Next step if you got HttpError 403:")
print("  → The Search Console API is not enabled in Google Cloud Console.")
print("    Enable it at: https://console.cloud.google.com/apis/library/searchconsole.googleapis.com")
print()
print("  Next step if sites list shows the property:")
print("  → Authentication works. Run the GSC agent.")
