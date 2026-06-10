from __future__ import annotations

import sys
import os

# ── TRACE 1: absolute first line ─────────────────────────────────────────────
# Printed before any import so we know the process started.
print("[TRACE 01] process started", flush=True)

# Redirect stderr → stdout so Railway captures everything in one stream.
sys.stderr = sys.stdout

# Allow running from the apps/gsc-agent directory without installing.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ── TRACE 2: stdlib imports done ──────────────────────────────────────────────
print("[TRACE 02] stdlib imports OK", flush=True)

try:
    from shared.config import get_settings
    print("[TRACE 03] shared.config imported", flush=True)

    from shared.database.connection import get_db
    print("[TRACE 04] shared.database imported", flush=True)

    from shared.logging.logger import AgentRunLogger, get_logger
    print("[TRACE 05] shared.logging imported", flush=True)

    from gsc_agent.client import GSCClient
    print("[TRACE 06] gsc_agent.client imported", flush=True)

    from gsc_agent.credentials import resolve_oauth_credentials
    print("[TRACE 07] gsc_agent.credentials imported", flush=True)

    from gsc_agent.ingestion import dates_to_collect, ingest_query_rows
    print("[TRACE 08] gsc_agent.ingestion imported", flush=True)

except Exception as _import_exc:
    import traceback
    print(f"[TRACE ERROR] import failed: {_import_exc}", flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)

logger = get_logger("gsc_agent.agent")
AGENT_NAME = "gsc_agent"

print("[TRACE 09] module-level setup complete — entering run()", flush=True)


def run() -> None:
    import traceback

    # ── STEP 1: load settings ─────────────────────────────────────────────────
    try:
        print("[TRACE 10] loading settings", flush=True)
        settings = get_settings()
        backend = "supabase" if settings.supabase_url else "sqlite"
        print(
            f"[TRACE 11] settings loaded — "
            f"backend={backend} "
            f"site={settings.gsc_site_url!r} "
            f"lookback={settings.gsc_lookback_days} "
            f"env={settings.environment}",
            flush=True,
        )
    except Exception as exc:
        print(f"[TRACE ERROR] settings failed: {exc}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    # ── STEP 2: connect to storage backend ───────────────────────────────────
    try:
        print(f"[TRACE 12] connecting to storage backend ({backend})", flush=True)
        db = get_db(settings.database_path)
        db.connect()          # validates connectivity; runs SQLite migrations or pings Supabase
        print("[TRACE 13] storage backend connected", flush=True)
    except Exception as exc:
        print(f"[TRACE ERROR] database failed: {exc}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    # ── STEP 3: record run start ──────────────────────────────────────────────
    try:
        print("[TRACE 14] recording agent run start", flush=True)
        run_logger = AgentRunLogger(agent_name=AGENT_NAME, db_connection=db)
        run_logger.started(
            metadata={
                "site_url": settings.gsc_site_url,
                "lookback_days": settings.gsc_lookback_days,
            }
        )
        print("[TRACE 15] agent run recorded in DB", flush=True)
    except Exception as exc:
        print(f"[TRACE ERROR] run logger failed: {exc}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    # ── STEP 4 onward: main logic (failures logged to agent_runs) ─────────────
    try:
        if not settings.gsc_site_url:
            raise ValueError("GSC_SITE_URL is not configured")

        # ── OAuth ─────────────────────────────────────────────────────────────
        print("[TRACE 16] resolving OAuth credentials", flush=True)
        credentials = resolve_oauth_credentials()
        print("[TRACE 17] OAuth credentials resolved and token refreshed", flush=True)

        # ── GSC client ────────────────────────────────────────────────────────
        print("[TRACE 18] initialising GSC client", flush=True)
        client = GSCClient(credentials=credentials, site_url=settings.gsc_site_url)
        print("[TRACE 19] GSC client initialised", flush=True)

        print("[TRACE 20] validating GSC property access", flush=True)
        client.validate_access()
        print("[TRACE 21] GSC property access confirmed", flush=True)

        # ── Date gap detection ────────────────────────────────────────────────
        print("[TRACE 22] calculating missing dates", flush=True)
        missing_dates = dates_to_collect(
            db=db,
            lookback_days=settings.gsc_lookback_days,
            site_url=settings.gsc_site_url,
        )
        logger.info(f"Dates to collect: {missing_dates}")
        print(f"[TRACE 23] missing dates: {missing_dates}", flush=True)

        # ── Collection loop ───────────────────────────────────────────────────
        total_records = 0
        for collection_date in missing_dates:
            print(f"[TRACE 24] fetching {collection_date}", flush=True)
            logger.info(f"Fetching GSC data for {collection_date}")
            rows = client.fetch_query_metrics(
                start_date=collection_date,
                end_date=collection_date,
            )
            print(f"[TRACE 25] {len(rows)} rows received for {collection_date}", flush=True)
            saved = ingest_query_rows(
                db=db,
                rows=rows,
                collection_date=collection_date,
                site_url=settings.gsc_site_url,
            )
            logger.info(f"Saved {saved} records for {collection_date}")
            print(f"[TRACE 26] {saved} records saved for {collection_date}", flush=True)
            total_records += saved

        # ── Done ──────────────────────────────────────────────────────────────
        print(f"[TRACE 27] collection complete — total records: {total_records}", flush=True)
        run_logger.completed(
            records_processed=total_records,
            metadata={"dates_collected": missing_dates},
        )
        print("[TRACE 28] agent run marked COMPLETED in DB", flush=True)

    except Exception as exc:
        import traceback as tb
        print(f"[TRACE ERROR] {type(exc).__name__}: {exc}", flush=True)
        tb.print_exc(file=sys.stdout)
        run_logger.failed(error=exc)
        raise


if __name__ == "__main__":
    print("[TRACE __main__] calling run()", flush=True)
    run()
