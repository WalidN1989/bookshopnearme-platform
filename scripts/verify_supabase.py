"""
Sprint 2 verification script — confirms Supabase storage is working.

Usage:
    # Reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from environment
    python scripts/verify_supabase.py

    # Or inline:
    SUPABASE_URL=https://... SUPABASE_SERVICE_ROLE_KEY=eyJ... python scripts/verify_supabase.py

Checks:
    1. Supabase connectivity (ping agent_runs table)
    2. Schema — all four tables exist and are reachable
    3. RPC functions exist (upsert_gsc_query, upsert_gsc_page, upsert_gsc_daily_metric)
    4. Agent run history
    5. GSC data coverage (row counts + date range)
    6. Top 10 queries by total impressions
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "gsc-agent"))

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


def main() -> int:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        print(f"\n{FAIL}  SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.\n")
        print("  Export them before running:")
        print("    export SUPABASE_URL=https://your-project-ref.supabase.co")
        print("    export SUPABASE_SERVICE_ROLE_KEY=eyJ...")
        return 1

    try:
        from supabase import create_client
    except ImportError:
        print(f"\n{FAIL}  supabase package not installed.")
        print("  Run: pip install 'supabase>=2.0.0'")
        return 1

    print(f"\nBookShopNearMe.lk — Sprint 2 Supabase Verification")
    print(f"Project: {url}")

    client = create_client(url, key)
    failures = 0

    # ── Connectivity ─────────────────────────────────────────────────────────
    section("Connectivity")
    try:
        client.table("agent_runs").select("id").limit(1).execute()
        check("Supabase reachable", True)
    except Exception as exc:
        check("Supabase reachable", False, detail=str(exc))
        print(f"\n{FAIL}  Cannot connect to Supabase. Aborting remaining checks.\n")
        return 1

    # ── Schema ───────────────────────────────────────────────────────────────
    section("Schema — Tables")
    tables = {
        "agent_runs": "agent_runs",
        "gsc_queries": "gsc_queries",
        "gsc_pages": "gsc_pages",
        "gsc_daily_metrics": "gsc_daily_metrics",
    }
    for label, table in tables.items():
        try:
            client.table(table).select("id").limit(1).execute()
            check(f"Table: {label}", True)
        except Exception as exc:
            check(f"Table: {label}", False, detail=str(exc))
            failures += 1

    # ── RPC Functions ────────────────────────────────────────────────────────
    section("Schema — RPC Functions")

    # Test upsert_gsc_query with a canary value
    try:
        result = client.rpc(
            "upsert_gsc_query",
            {"p_query": "__verify_canary__", "p_date": "2000-01-01"},
        ).execute()
        row_id = result.data
        if isinstance(row_id, list):
            row_id = row_id[0]
        check("RPC: upsert_gsc_query", int(row_id) > 0, detail=f"id={row_id}")
        # Clean up the canary row
        client.table("gsc_queries").delete().eq("query", "__verify_canary__").execute()
    except Exception as exc:
        check("RPC: upsert_gsc_query", False, detail=str(exc))
        failures += 1

    try:
        result = client.rpc(
            "upsert_gsc_page",
            {"p_page_url": "https://verify.example/__canary__", "p_date": "2000-01-01"},
        ).execute()
        row_id = result.data
        if isinstance(row_id, list):
            row_id = row_id[0]
        check("RPC: upsert_gsc_page", int(row_id) > 0, detail=f"id={row_id}")
        client.table("gsc_pages").delete().eq("page_url", "https://verify.example/__canary__").execute()
    except Exception as exc:
        check("RPC: upsert_gsc_page", False, detail=str(exc))
        failures += 1

    try:
        # upsert_gsc_daily_metric returns void — success == no exception
        # Use safe dummy ids that won't violate FK (FK refs to gsc_queries/pages ids that
        # don't exist — so we rely on null query_id/page_id being allowed, or we catch the FK error gracefully)
        client.rpc(
            "upsert_gsc_daily_metric",
            {
                "p_date": "2000-01-01",
                "p_query_id": None,
                "p_page_id": None,
                "p_impressions": 0,
                "p_clicks": 0,
                "p_ctr": 0.0,
                "p_position": 0.0,
            },
        ).execute()
        check("RPC: upsert_gsc_daily_metric", True)
        # Clean up
        client.table("gsc_daily_metrics").delete().eq("date", "2000-01-01").execute()
    except Exception as exc:
        check("RPC: upsert_gsc_daily_metric", False, detail=str(exc))
        failures += 1

    # ── Agent Runs ───────────────────────────────────────────────────────────
    section("Agent Runs")
    try:
        result = client.table("agent_runs").select("status").execute()
        runs = result.data
        counts: dict[str, int] = {}
        for r in runs:
            counts[r["status"]] = counts.get(r["status"], 0) + 1

        total = sum(counts.values())
        check("At least one agent run recorded", total > 0,
              detail=f"{total} total", warn_only=True)

        for status, count in sorted(counts.items()):
            label = f"  Runs with status={status}"
            if status == "FAILED" and count > 0:
                check(label, False, detail=str(count), warn_only=True)
            else:
                print(f"{INFO}  {label}: {count}")

        # Last run details
        last = (
            client.table("agent_runs")
            .select("agent_name, status, started_at, duration_seconds, records_processed")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        if last.data:
            r = last.data[0]
            dur = f"{r['duration_seconds']:.1f}s" if r["duration_seconds"] else "n/a"
            print(
                f"{INFO}  Last run: {r['agent_name']} | "
                f"{r['status']} | "
                f"{(r['started_at'] or '')[:19]} | "
                f"{r['records_processed']} records | {dur}"
            )
    except Exception as exc:
        check("Agent runs query", False, detail=str(exc))
        failures += 1

    # ── GSC Data ─────────────────────────────────────────────────────────────
    section("GSC Data")
    try:
        q_count = len(client.table("gsc_queries").select("id").execute().data)
        p_count = len(client.table("gsc_pages").select("id").execute().data)
        m_count = len(client.table("gsc_daily_metrics").select("id").execute().data)

        check("GSC queries collected", q_count > 0,
              detail=f"{q_count} unique queries", warn_only=True)
        check("GSC pages collected", p_count > 0,
              detail=f"{p_count} unique pages", warn_only=True)
        check("GSC daily metrics collected", m_count > 0,
              detail=f"{m_count} rows", warn_only=True)

        # Date range
        dates_result = (
            client.table("gsc_daily_metrics")
            .select("date")
            .order("date")
            .execute()
        )
        all_dates = sorted({r["date"] for r in dates_result.data})
        if all_dates:
            print(
                f"{INFO}  Date range: {all_dates[0]} → {all_dates[-1]} "
                f"({len(all_dates)} distinct dates)"
            )

        # Recent data check (within last 5 days — accounts for GSC delay)
        recent_cutoff = (date.today() - timedelta(days=5)).isoformat()
        recent = [r for r in dates_result.data if r["date"] >= recent_cutoff]
        check(
            "Recent GSC data present (within 5 days)",
            len(recent) > 0,
            detail=f"{len(recent)} rows since {recent_cutoff}",
            warn_only=True,
        )
    except Exception as exc:
        check("GSC data query", False, detail=str(exc))
        failures += 1

    # ── Top Queries ──────────────────────────────────────────────────────────
    section("Top 10 Queries by Impressions")
    try:
        metrics = (
            client.table("gsc_daily_metrics")
            .select("impressions, clicks, gsc_queries(query)")
            .execute()
        )
        # Aggregate in Python (PostgREST doesn't support GROUP BY directly)
        agg: dict[str, dict] = {}
        for row in metrics.data:
            q = (row.get("gsc_queries") or {}).get("query", "(unknown)")
            if q not in agg:
                agg[q] = {"impressions": 0, "clicks": 0}
            agg[q]["impressions"] += row.get("impressions", 0)
            agg[q]["clicks"] += row.get("clicks", 0)

        top = sorted(agg.items(), key=lambda x: x[1]["impressions"], reverse=True)[:10]
        if top:
            for q, vals in top:
                print(
                    f"{INFO}  {vals['impressions']:>7} impr | "
                    f"{vals['clicks']:>5} clicks | {q}"
                )
        else:
            print(f"{WARN}  No query data yet.")
    except Exception as exc:
        print(f"{WARN}  Could not aggregate top queries: {exc}")

    # ── Summary ──────────────────────────────────────────────────────────────
    section("Summary")
    if failures == 0:
        print(f"{PASS}  All checks passed.\n")
    else:
        print(f"{FAIL}  {failures} check(s) failed. Review output above.\n")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
