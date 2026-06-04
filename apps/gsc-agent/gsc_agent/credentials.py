"""
Resolve GSC credentials from either a file path or a base64-encoded env var.

Railway doesn't support uploading arbitrary files as secrets, so the service
account JSON is base64-encoded and stored in GSC_CREDENTIALS_B64. This module
writes it to a temp file on startup so the Google SDK can read it normally.
"""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path


def resolve_credentials_path() -> str:
    """Return a file path to the GSC service account JSON.

    Priority:
    1. GSC_CREDENTIALS_B64 — base64-encoded JSON (used on Railway)
    2. GSC_CREDENTIALS_PATH — path to a local JSON file (used in dev)
    """
    b64 = os.getenv("GSC_CREDENTIALS_B64", "").strip()
    if b64:
        decoded = base64.b64decode(b64)
        # Write to a temp file that persists for the process lifetime
        tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, prefix="gsc_creds_"
        )
        tmp.write(decoded)
        tmp.flush()
        tmp.close()
        return tmp.name

    path = os.getenv("GSC_CREDENTIALS_PATH", "")
    if path and Path(path).exists():
        return path

    raise RuntimeError(
        "GSC credentials not found. Set either:\n"
        "  GSC_CREDENTIALS_B64  — base64-encoded service account JSON (Railway)\n"
        "  GSC_CREDENTIALS_PATH — path to service account JSON file (local dev)"
    )
