from __future__ import annotations

from shared.database.connection import DatabaseConnection
from shared.database.migrations import run_migrations

SITE_A = "https://bookshopnearme.lk/"
SITE_B = "https://period.lk/"


def test_migrations_run_idempotent(tmp_db: DatabaseConnection):
    conn = tmp_db.connect()
    applied = run_migrations(conn)
    assert applied == 0


def test_tables_exist(tmp_db: DatabaseConnection):
    conn = tmp_db.connect()
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    required = {
        "schema_migrations",
        "system_settings",
        "agent_runs",
        "gsc_queries",
        "gsc_pages",
        "gsc_daily_metrics",
        "content_opportunities",
    }
    assert required.issubset(tables)


def test_agent_run_lifecycle(tmp_db: DatabaseConnection):
    run_id = tmp_db.insert_agent_run(
        agent_name="test_agent",
        status="STARTED",
        started_at="2026-01-01T00:00:00+00:00",
    )
    assert run_id is not None

    tmp_db.update_agent_run(
        run_id=run_id,
        status="COMPLETED",
        duration_seconds=1.23,
        records_processed=42,
    )

    row = tmp_db.conn.execute(
        "SELECT * FROM agent_runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["status"] == "COMPLETED"
    assert row["records_processed"] == 42
    assert abs(row["duration_seconds"] - 1.23) < 0.001


def test_gsc_upsert_idempotent(tmp_db: DatabaseConnection):
    qid1 = tmp_db.upsert_gsc_query("buy books sri lanka", "2026-01-01", SITE_A)
    qid2 = tmp_db.upsert_gsc_query("buy books sri lanka", "2026-01-02", SITE_A)
    assert qid1 == qid2  # same row, same id

    pid1 = tmp_db.upsert_gsc_page("https://bookshopnearme.lk/", "2026-01-01", SITE_A)
    pid2 = tmp_db.upsert_gsc_page("https://bookshopnearme.lk/", "2026-01-02", SITE_A)
    assert pid1 == pid2


def test_gsc_daily_metrics(tmp_db: DatabaseConnection):
    qid = tmp_db.upsert_gsc_query("test query", "2026-01-01", SITE_A)
    pid = tmp_db.upsert_gsc_page("https://example.com/page", "2026-01-01", SITE_A)

    tmp_db.upsert_gsc_daily_metric(
        date="2026-01-01",
        query_id=qid,
        page_id=pid,
        impressions=100,
        clicks=10,
        ctr=0.1,
        position=3.5,
        site_url=SITE_A,
    )

    metrics = tmp_db.get_gsc_metrics_for_date("2026-01-01", site_url=SITE_A)
    assert len(metrics) == 1
    assert metrics[0]["impressions"] == 100
    assert metrics[0]["clicks"] == 10


def test_multi_site_isolation(tmp_db: DatabaseConnection):
    """Same query string for two sites must produce separate rows and never mix."""
    query = "buy books online"

    qid_a = tmp_db.upsert_gsc_query(query, "2026-01-01", SITE_A)
    qid_b = tmp_db.upsert_gsc_query(query, "2026-01-01", SITE_B)
    assert qid_a != qid_b, "Same query for two sites must be separate rows"

    pid_a = tmp_db.upsert_gsc_page("https://bookshopnearme.lk/", "2026-01-01", SITE_A)
    pid_b = tmp_db.upsert_gsc_page("https://period.lk/", "2026-01-01", SITE_B)

    tmp_db.upsert_gsc_daily_metric("2026-01-01", qid_a, pid_a, 500, 30, 0.06, 2.1, site_url=SITE_A)
    tmp_db.upsert_gsc_daily_metric("2026-01-01", qid_b, pid_b, 120, 8,  0.07, 3.5, site_url=SITE_B)

    metrics_a = tmp_db.get_gsc_metrics_for_date("2026-01-01", site_url=SITE_A)
    metrics_b = tmp_db.get_gsc_metrics_for_date("2026-01-01", site_url=SITE_B)

    assert len(metrics_a) == 1
    assert len(metrics_b) == 1
    assert metrics_a[0]["impressions"] == 500
    assert metrics_b[0]["impressions"] == 120

    # get_date_range_exists must also be site-scoped
    dates_a = tmp_db.get_date_range_exists("2026-01-01", "2026-01-01", site_url=SITE_A)
    dates_b = tmp_db.get_date_range_exists("2026-01-01", "2026-01-01", site_url=SITE_B)
    assert "2026-01-01" in dates_a
    assert "2026-01-01" in dates_b


def test_system_settings(tmp_db: DatabaseConnection):
    assert tmp_db.get_setting("missing_key") is None
    assert tmp_db.get_setting("missing_key", "default") == "default"

    tmp_db.set_setting("last_run", "2026-01-01")
    assert tmp_db.get_setting("last_run") == "2026-01-01"

    tmp_db.set_setting("last_run", "2026-01-02")
    assert tmp_db.get_setting("last_run") == "2026-01-02"


def test_content_opportunity_insert(tmp_db: DatabaseConnection):
    opp_id = tmp_db.insert_content_opportunity(
        keyword="buy harry potter sri lanka",
        source="GSC",
        search_volume=320,
        difficulty=0.35,
        book_available=True,
        priority_score=8.5,
        notes="High-intent keyword from GSC data",
    )
    assert opp_id is not None

    row = tmp_db.conn.execute(
        "SELECT * FROM content_opportunities WHERE id=?", (opp_id,)
    ).fetchone()
    assert row["keyword"] == "buy harry potter sri lanka"
    assert row["status"] == "NEW"
    assert row["source"] == "GSC"
