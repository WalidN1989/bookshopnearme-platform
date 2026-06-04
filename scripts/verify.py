"""
Verification script for Sprint 1 deployment.

Run locally or on Railway to confirm:
  - Database is reachable and schema is correct
  - GSC data is being collected
  - Agent runs are being logged

Usage:
    python scripts/verify.py
    python scripts/verify.py --db /data/bookshop.db
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "gsc-agent"))

from shared.config import get_settings
from shared.database.connection import DatabaseConnection

PASS = "\033[92m  PASS\033[0m"
FAIL = "\033[91m  FAIL\033[0m"
WARN = "\033[93m  WARN\033[0m"
INFO = "\033[94m  INFO\033[0m"


def check(label: str, condition: bool, detail: str = "", warn_only: bool = False) -> bool:
    status = PASS if condition else (WARN if warn_only else FAIL)
    suffix = f"  ({detail})" if detail else ""
    print(f"{status}  {label}{suffix}")
    return condition


def section(title: str) -> None:
    print(f"\n── {title} {'─' * (50 - len(title))}")


def main(db_path: str | None = None) -> int:
    settings = get_settings()
    path = db_path or str(settings.database_path)
    print(f"\nBookShopNearMe.lk — Sprint 1 Verification")
    print(f"Database: {path}")

    db = DatabaseConnection(path)
    conn = db.connect()

    failures = 0

    # ── Schema ───────────────────────────────────────────────────────────────
    section("Schema")
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    required = {
        "schema_migrations", "system_settings", "agent_runs",
        "gsc_queries", "gsc_pages", "gsc_daily_metrics", "content_opportunities",
    }
    for t in sorted(required):
        ok = check(f"Table: {t}", t in tables)
        if not ok:
            failures += 1

    migrations = conn.execute(
        "SELECT version, description, applied_at FROM schema_migrations ORDER BY version"
    ).fetchall()
    for m in migrations:
        print(f"{INFO}  Migration v{m[0]}: {m[1]} (applied {m[2][:10]})")

    # ── Agent runs ───────────────────────────────────────────────────────────
    section("Agent Runs")
    runs = conn.execute(
        "SELECT status, COUNT(*) as n FROM agent_runs GROUP BY status"
    ).fetchall()
    run_counts = {r["status"]: r["n"] for r in runs}

    total_runs = sum(run_counts.values())
    ok = check("At least one agent run recorded", total_runs > 0,
               detail=f"{total_runs} total", warn_only=True)
    if not ok:
        failures += 1

    for status, count in sorted(run_counts.items()):
        label = f"  Runs with status={status}"
        if status == "FAILED" and count > 0:
            check(label, False, detail=str(count), warn_only=True)
        else:
            print(f"{INFO}  {label}: {count}")

    last_run = conn.execute(
        "SELECT agent_name, status, started_at, duration_seconds, records_processed "
        "FROM agent_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if last_run:
        print(
            f"{INFO}  Last run: {last_run['agent_name']} | "
            f"{last_run['status']} | "
            f"{(last_run['started_at'] or '')[:19]} | "
            f"{last_run['records_processed']} records | "
            f"{last_run['duration_seconds']:.1f}s"
        )

    # ── GSC Data ─────────────────────────────────────────────────────────────
    section("GSC Data")
    query_count = conn.execute("SELECT COUNT(*) FROM gsc_queries").fetchone()[0]
    page_count = conn.execute("SELECT COUNT(*) FROM gsc_pages").fetchone()[0]
    metric_count = conn.execute("SELECT COUNT(*) FROM gsc_daily_metrics").fetchone()[0]

    check("GSC queries collected", query_count > 0,
          detail=f"{query_count} unique queries", warn_only=True)
    check("GSC pages collected", page_count > 0,
          detail=f"{page_count} unique pages", warn_only=True)
    check("GSC daily metrics collected", metric_count > 0,
          detail=f"{metric_count} rows", warn_only=True)

    date_range = conn.execute(
        "SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(DISTINCT date) as n "
        "FROM gsc_daily_metrics"
    ).fetchone()
    if date_range and date_range["n"]:
        print(
            f"{INFO}  Date range: {date_range['earliest']} → {date_range['latest']} "
            f"({date_range['n']} distinct dates)"
        )

    # Check for recent data (within last 5 days — accounting for GSC delay)
    recent_cutoff = (date.today() - timedelta(days=5)).isoformat()
    recent = conn.execute(
        "SELECT COUNT(*) FROM gsc_daily_metrics WHERE date >= ?", (recent_cutoff,)
    ).fetchone()[0]
    check(
        "Recent GSC data present (within 5 days)",
        recent > 0,
        detail=f"{recent} rows since {recent_cutoff}",
        warn_only=True,
    )

    # Top 5 queries by impressions
    top = conn.execute(
        """
        SELECT q.query, SUM(m.impressions) as total_impressions, SUM(m.clicks) as total_clicks
        FROM gsc_daily_metrics m
        JOIN gsc_queries q ON m.query_id = q.id
        GROUP BY q.id
        ORDER BY total_impressions DESC
        LIMIT 5
        """
    ).fetchall()
    if top:
        print(f"{INFO}  Top 5 queries by impressions:")
        for row in top:
            print(f"         {row['total_impressions']:>6} impr | {row['total_clicks']:>5} clicks | {row['query']}")

    # ── Missing dates ────────────────────────────────────────────────────────
    section("Coverage Check (last 7 days)")
    lookback = settings.gsc_lookback_days
    yesterday = date.today() - timedelta(days=1)
    start = yesterday - timedelta(days=lookback - 1)
    existing_dates = set(
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT date FROM gsc_daily_metrics WHERE date BETWEEN ? AND ?",
            (start.isoformat(), yesterday.isoformat()),
        ).fetchall()
    )
    current = start
    all_covered = True
    while current <= yesterday:
        ds = current.isoformat()
        # GSC is 2-3 days delayed; warn rather than fail for very recent dates
        days_ago = (date.today() - current).days
        present = ds in existing_dates
        if not present:
            all_covered = False
            if days_ago <= 3:
                print(f"{WARN}  {ds}  missing (GSC delay — expected)")
            else:
                check(f"{ds}  present", False, warn_only=False)
                failures += 1
        else:
            print(f"{PASS}  {ds}  present")
        current += timedelta(days=1)

    # ── Summary ──────────────────────────────────────────────────────────────
    section("Summary")
    if failures == 0:
        print(f"{PASS}  All checks passed.\n")
    else:
        print(f"{FAIL}  {failures} check(s) failed. Review output above.\n")

    db.close()
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Sprint 1 deployment")
    parser.add_argument("--db", help="Path to SQLite database (overrides DATABASE_PATH)")
    args = parser.parse_args()
    sys.exit(main(db_path=args.db))
