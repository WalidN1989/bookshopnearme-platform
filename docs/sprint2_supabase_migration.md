# Sprint 2 — GSC Storage Migration: SQLite → Supabase

## Why

Railway containers are ephemeral. The SQLite file at `data/bookshop.db` is destroyed on every
redeploy. This means GSC data collected on one deploy is lost the next day.

Supabase replaces SQLite as the single source of truth. Railway becomes completely stateless —
all persistence lives in Supabase.

---

## Architecture After Migration

```
Railway cron (stateless)
  └─ GSCAgent
       ├─ Google Search Console API   (reads)
       └─ Supabase Postgres           (writes)

Supabase tables:
  gsc_queries        — unique search queries + first/last seen dates
  gsc_pages          — unique page URLs + first/last seen dates
  gsc_daily_metrics  — (date, query_id, page_id) → impressions, clicks, ctr, position
  agent_runs         — run history: status, duration, records, errors
```

---

## Step 1 — Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click **New project**
3. Name it `bookshopnearme-gsc` (or similar)
4. Choose the **Singapore** region (closest to Sri Lanka)
5. Set a strong database password and save it somewhere safe
6. Wait ~2 minutes for the project to provision

---

## Step 2 — Apply the Schema

1. In your Supabase project, go to **SQL Editor → New query**
2. Open `supabase/migrations/001_initial_schema.sql` from this repo
3. Paste the entire contents into the editor
4. Click **Run**

You should see: `Success. No rows returned`

This creates:
- 4 tables: `gsc_queries`, `gsc_pages`, `gsc_daily_metrics`, `agent_runs`
- 5 indexes for query performance
- 3 Postgres RPC functions for correct upsert semantics

---

## Step 3 — Get Your Credentials

1. In Supabase, go to **Project Settings → API**
2. Copy two values:

| Value | Where to find it |
|-------|-----------------|
| `SUPABASE_URL` | "Project URL" field, e.g. `https://xyzxyz.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | "service_role" key under "Project API keys" (click to reveal) |

> **Use the `service_role` key, not the `anon` key.**
> The service role key bypasses Row Level Security and is required for server-side writes.
> Never expose this key in the browser or frontend code.

---

## Step 4 — Set Railway Environment Variables

Railway dashboard → your project → `gsc-agent` service → **Variables**:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | `https://your-project-ref.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJhbGci...` (the full service_role JWT) |

You can leave `DATABASE_PATH` in place — it is now ignored when `SUPABASE_URL` is set.

---

## Step 5 — Deploy

```bash
git push origin main
```

Railway will automatically rebuild and redeploy. The new build includes:
- `supabase>=2.0.0` Python package (added to `apps/gsc-agent/pyproject.toml`)
- `SupabaseConnection` storage backend (`shared/database/supabase_connection.py`)
- Updated `get_db()` factory that selects Supabase when env vars are present

**What changes in the logs:**

Before (SQLite):
```
[TRACE 11] settings loaded — backend=sqlite site='https://bookshopnearme.lk/' ...
[TRACE 12] connecting to storage backend (sqlite)
[TRACE 13] storage backend connected
```

After (Supabase):
```
[TRACE 11] settings loaded — backend=supabase site='https://bookshopnearme.lk/' ...
[TRACE 12] connecting to storage backend (supabase)
[TRACE 13] storage backend connected
```

---

## Step 6 — Verify

Run the verification script locally (with your Supabase credentials exported):

```bash
export SUPABASE_URL=https://your-project-ref.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=eyJ...

python scripts/verify_supabase.py
```

Expected output after the first successful cron run:

```
── Connectivity ──────────────────────────────────────────
  PASS  Supabase reachable

── Schema — Tables ───────────────────────────────────────
  PASS  Table: agent_runs
  PASS  Table: gsc_daily_metrics
  PASS  Table: gsc_pages
  PASS  Table: gsc_queries

── Schema — RPC Functions ────────────────────────────────
  PASS  RPC: upsert_gsc_query   (id=1)
  PASS  RPC: upsert_gsc_page    (id=1)
  PASS  RPC: upsert_gsc_daily_metric

── Agent Runs ────────────────────────────────────────────
  PASS  At least one agent run recorded  (1 total)
  INFO  Runs with status=COMPLETED: 1
  INFO  Last run: gsc_agent | COMPLETED | 2026-06-09 06:00:12 | 312 records | 8.3s

── GSC Data ──────────────────────────────────────────────
  PASS  GSC queries collected   (87 unique queries)
  PASS  GSC pages collected     (12 unique pages)
  PASS  GSC daily metrics collected  (624 rows)
  INFO  Date range: 2026-06-02 → 2026-06-08 (7 distinct dates)
  PASS  Recent GSC data present (within 5 days)

── Summary ───────────────────────────────────────────────
  PASS  All checks passed.
```

---

## Environment Variables Reference

| Variable | Required in production | Description |
|---|---|---|
| `SUPABASE_URL` | **Yes** | Project URL from Supabase dashboard |
| `SUPABASE_SERVICE_ROLE_KEY` | **Yes** | Service role key (server-side only) |
| `DATABASE_PATH` | No | SQLite path — only used for local dev when Supabase vars absent |
| `GSC_OAUTH_CLIENT_ID` | **Yes** | Google OAuth client ID |
| `GSC_OAUTH_CLIENT_SECRET` | **Yes** | Google OAuth client secret |
| `GSC_OAUTH_REFRESH_TOKEN` | **Yes** | Long-lived refresh token |
| `GSC_SITE_URL` | **Yes** | `https://bookshopnearme.lk/` |
| `GSC_LOOKBACK_DAYS` | No (default: 7) | Days to back-fill |
| `ENVIRONMENT` | No (default: development) | Set to `production` on Railway |
| `LOG_LEVEL` | No (default: INFO) | `INFO` or `DEBUG` |

---

## Storage Backend Selection Logic

```
SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY set?
  ├─ YES → SupabaseConnection (production, Railway)
  └─ NO  → DatabaseConnection / SQLite (local dev, CI without Supabase)
```

This means local development continues to work without Supabase credentials.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Supabase connectivity check failed` | Wrong URL or key | Double-check Railway Variables; use service_role not anon key |
| `relation "agent_runs" does not exist` | Schema not applied | Run `001_initial_schema.sql` in Supabase SQL Editor |
| `function upsert_gsc_query does not exist` | RPC functions not created | Re-run the full migration SQL file |
| `[TRACE 11] backend=sqlite` in Railway logs | `SUPABASE_URL` not set | Add both Supabase variables to Railway |
| `supabase package not installed` | Build failed | Check Railway build logs; `supabase>=2.0.0` is in `apps/gsc-agent/pyproject.toml` |
| RPC returns wrong id type | supabase-py version difference | The `_scalar_int()` helper in `supabase_connection.py` handles this |

---

## What Was NOT Changed

- GSC collection logic (`gsc_agent/ingestion.py`) — identical
- OAuth authentication (`gsc_agent/credentials.py`) — identical
- GSC API client (`gsc_agent/client.py`) — identical
- MCP server — not affected
- All Railway cron scheduling — not affected
- Local SQLite path — still works for local development

---

## Sprint 3 Gate Criteria

Before Sprint 3 (DataForSEO integration), confirm:

- [ ] 3+ consecutive `COMPLETED` runs visible in `agent_runs` table in Supabase
- [ ] 5+ distinct dates in `gsc_daily_metrics`
- [ ] Real search queries visible (not 0 rows)
- [ ] `verify_supabase.py` passes all non-warning checks
- [ ] No `FAILED` runs in the last 7 days
