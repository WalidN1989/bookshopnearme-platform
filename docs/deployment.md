# Deployment Guide

## Overview

Sprint 1 deploys one service to Railway:

| Service | Type | Schedule |
|---------|------|----------|
| `gsc-agent` | Cron job | Daily at 06:00 UTC |

The MCP server runs locally via Claude Desktop — no hosting needed for Sprint 1.

---

## Step 1 — Prepare GSC Credentials for Railway

Railway doesn't support uploading JSON files as secrets. Encode the service account file as base64:

```bash
# macOS / Linux
base64 -i gsc-service-account.json | tr -d '\n'
```

Copy the output — you'll paste it into Railway as `GSC_CREDENTIALS_B64`.

> The `gsc_agent/credentials.py` module decodes it back to a temp file at runtime.  
> The original JSON file should **never** be committed to git — it is in `.gitignore`.

---

## Step 2 — Create a Railway Project

```bash
# Install Railway CLI if needed
npm install -g @railway/cli

# Log in
railway login

# From the repo root
railway init
```

Select **Empty Project** when prompted. Name it `bookshopnearme-platform`.

---

## Step 3 — Add a Railway Volume (SQLite Persistence)

SQLite data is lost on redeploy unless you attach a Volume:

1. Railway dashboard → your project → **New** → **Volume**
2. Name: `bookshop-data`
3. Mount path: `/data`
4. Attach it to the `gsc-agent` service

Then set `DATABASE_PATH=/data/bookshop.db` in the service's environment variables.

---

## Step 4 — Set Environment Variables

In the Railway dashboard → `gsc-agent` service → **Variables**, add:

| Variable | Value |
|----------|-------|
| `DATABASE_PATH` | `/data/bookshop.db` |
| `GSC_CREDENTIALS_B64` | _(paste base64 output from Step 1)_ |
| `GSC_SITE_URL` | `https://bookshopnearme.lk/` |
| `GSC_LOOKBACK_DAYS` | `7` |
| `LOG_LEVEL` | `INFO` |
| `ENVIRONMENT` | `production` |

Do **not** set `GSC_CREDENTIALS_PATH` on Railway — `GSC_CREDENTIALS_B64` takes priority.

---

## Step 5 — Deploy

```bash
# From the repo root
railway up
```

Railway reads `railway.toml` and creates the `gsc-agent` cron service automatically.

---

## Step 6 — Verify First Run

Trigger a manual run immediately to confirm credentials and connectivity:

```bash
# Trigger from CLI
railway run python -m gsc_agent.agent

# Or from the Railway dashboard:
# gsc-agent service → Deployments → Run now
```

Watch the logs. A successful run looks like:

```
2026-06-05 06:00:01 | INFO     | agent.gsc_agent | [STARTED] agent=gsc_agent ...
2026-06-05 06:00:03 | INFO     | gsc_agent.agent  | Dates to collect: ['2026-06-02', '2026-06-03']
2026-06-05 06:00:04 | INFO     | gsc_agent.agent  | Saved 312 records for 2026-06-02
2026-06-05 06:00:05 | INFO     | gsc_agent.agent  | Saved 298 records for 2026-06-03
2026-06-05 06:00:05 | INFO     | agent.gsc_agent | [COMPLETED] agent=gsc_agent duration=4.1s records=610
```

---

## Step 7 — Run the Verification Script

```bash
# Locally (after the agent has run at least once)
python scripts/verify.py

# On Railway
railway run python scripts/verify.py --db /data/bookshop.db
```

All checks should pass within 24 hours of the first successful cron run.

---

## MCP Server — Local Setup (Claude Desktop)

No Railway hosting required. Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bookshopnearme": {
      "command": "/path/to/.venv/bin/bookshopnearme-mcp"
    }
  }
}
```

Config file locations:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

---

## Cron Schedule

The agent runs at **06:00 UTC daily** (`0 6 * * *`).

- GSC data for a given day is typically final 2–3 days after that date.
- The agent detects missing dates automatically — if a run fails, the next run catches up.
- To change the schedule, edit `cronSchedule` in `railway.toml` and redeploy.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `GSC credentials not found` | Neither env var set | Set `GSC_CREDENTIALS_B64` in Railway Variables |
| `HttpError 403` from Google API | Service account not added to GSC | Add the service account email as a user in Google Search Console |
| `HttpError 401` | Wrong site URL | Ensure `GSC_SITE_URL` exactly matches the property in GSC (including trailing slash) |
| Database empty after deploy | Volume not attached | Attach the Railway Volume mounted at `/data` |
| `FAILED` runs in `agent_runs` | Any of the above | Check logs: `railway logs --service gsc-agent` |
