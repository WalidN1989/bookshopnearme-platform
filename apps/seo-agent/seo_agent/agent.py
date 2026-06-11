from __future__ import annotations

import sys
import os

print("[TRACE 01] process started", flush=True)

sys.stderr = sys.stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

print("[TRACE 02] stdlib imports OK", flush=True)

try:
    from shared.config import get_settings
    print("[TRACE 03] shared.config imported", flush=True)

    from shared.database.connection import get_db
    print("[TRACE 04] shared.database imported", flush=True)

    from shared.logging.logger import AgentRunLogger, get_logger
    print("[TRACE 05] shared.logging imported", flush=True)

    from seo_agent.analyzer import analyze
    print("[TRACE 06] seo_agent.analyzer imported", flush=True)

    from seo_agent.repository import load_gsc_data, save_opportunities
    print("[TRACE 07] seo_agent.repository imported", flush=True)

except Exception as _import_exc:
    import traceback
    print(f"[TRACE ERROR] import failed: {_import_exc}", flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)

logger = get_logger("seo_agent.agent")
AGENT_NAME = "seo_agent"

print("[TRACE 08] module-level setup complete — entering run()", flush=True)


def run() -> None:
    import traceback

    # ── STEP 1: load settings ─────────────────────────────────────────────────
    try:
        print("[TRACE 10] loading settings", flush=True)
        settings = get_settings()
        backend = "supabase" if settings.supabase_url else "sqlite"
        site_url = settings.gsc_site_url
        print(
            f"[TRACE 11] settings loaded — "
            f"backend={backend} site={site_url!r} env={settings.environment}",
            flush=True,
        )
    except Exception as exc:
        print(f"[TRACE ERROR] settings failed: {exc}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    if not site_url:
        print("[TRACE ERROR] GSC_SITE_URL is not configured", flush=True)
        sys.exit(1)

    # ── STEP 2: connect to storage backend ───────────────────────────────────
    try:
        print(f"[TRACE 12] connecting to storage backend ({backend})", flush=True)
        db = get_db(settings.database_path)
        db.connect()
        print("[TRACE 13] storage backend connected", flush=True)
    except Exception as exc:
        print(f"[TRACE ERROR] database failed: {exc}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    # ── STEP 3: record run start ──────────────────────────────────────────────
    try:
        print("[TRACE 14] recording agent run start", flush=True)
        run_logger = AgentRunLogger(agent_name=AGENT_NAME, db_connection=db)
        run_logger.started(metadata={"site_url": site_url})
        print("[TRACE 15] agent run recorded in DB", flush=True)
    except Exception as exc:
        print(f"[TRACE ERROR] run logger failed: {exc}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    # ── STEP 4 onward: analysis ───────────────────────────────────────────────
    try:
        # ── Load GSC data ─────────────────────────────────────────────────────
        print("[TRACE 16] loading period.lk search console data", flush=True)
        rows = load_gsc_data(db, site_url=site_url)
        print(f"[TRACE 17] {len(rows)} raw GSC rows loaded", flush=True)

        if not rows:
            print("[TRACE 18] no GSC data found — skipping analysis", flush=True)
            run_logger.completed(records_processed=0, metadata={"opportunities_saved": 0})
            print("[TRACE 19] agent run marked COMPLETED in DB (no data)", flush=True)
            return

        # ── Analyse opportunities ─────────────────────────────────────────────
        print("[TRACE 18] analysing seo opportunities", flush=True)
        opportunities = analyze(rows, site_url=site_url)
        print(f"[TRACE 19] {len(opportunities)} opportunities detected", flush=True)

        # ── Score summary ─────────────────────────────────────────────────────
        by_type: dict[str, int] = {}
        for opp in opportunities:
            by_type[opp.opportunity_type] = by_type.get(opp.opportunity_type, 0) + 1
        print(f"[TRACE 20] opportunity breakdown: {by_type}", flush=True)

        # ── Save to database ──────────────────────────────────────────────────
        print("[TRACE 21] storing opportunities", flush=True)
        saved = save_opportunities(db, opportunities, site_url=site_url)
        print(f"[TRACE 22] {saved} opportunities upserted (existing rows updated in place)", flush=True)

        # ── Done ──────────────────────────────────────────────────────────────
        print("[TRACE 23] seo analysis completed", flush=True)
        run_logger.completed(
            records_processed=saved,
            metadata={
                "site_url": site_url,
                "gsc_rows_loaded": len(rows),
                "opportunities_by_type": by_type,
                "opportunities_saved": saved,
            },
        )
        print("[TRACE 24] agent run marked COMPLETED in DB", flush=True)

    except Exception as exc:
        import traceback as tb
        print(f"[TRACE ERROR] {type(exc).__name__}: {exc}", flush=True)
        tb.print_exc(file=sys.stdout)
        run_logger.failed(error=exc)
        raise


if __name__ == "__main__":
    print("[TRACE __main__] calling run()", flush=True)
    run()
