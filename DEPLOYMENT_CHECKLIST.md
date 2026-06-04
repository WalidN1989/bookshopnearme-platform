# Sprint 1 — Deployment Checklist

Generated: 2026-06-05  
Status: **Ready for deployment**

---

## Local Validation Results

| Check | Result |
|-------|--------|
| Git initialized, working tree clean | PASS |
| 26/26 unit tests pass | PASS |
| MCP package builds (wheel + sdist) | PASS |
| Fresh database: 1 migration applied, 7 tables, 7 indexes | PASS |
| Migration idempotency (second run = 0 applied) | PASS |
| WAL mode enabled | PASS |
| Foreign keys enforced | PASS |
| All tables have `created_at` + `updated_at` | PASS |
| MCP server: 6 tools registered | PASS |
| Credential resolver: no vars → graceful RuntimeError | PASS |
| Credential resolver: valid B64 → temp file written | PASS |
| Credential resolver: missing file path → graceful RuntimeError | PASS |
| Credential resolver: valid file path → resolved | PASS |
| GSC agent: no site URL → FAILED written to agent_runs | PASS |
| GSC agent: raises and exits non-zero on bad config | PASS |
| Railway config: all 12 structural checks | PASS |
| .gitignore: `.env`, `*.json`, `data/` excluded | PASS |
| .gitignore: config files, YAML not excluded | PASS |

---

## Pre-Deployment Checklist

Work through this top to bottom. Check each box before moving to the next section.

---

### Phase 1 — Google Cloud Console
> Time: ~10 minutes | Requires: browser, Google account with access to the GSC property

- [ ] **1.1** Go to [console.cloud.google.com](https://console.cloud.google.com)
- [ ] **1.2** Create or select a project (suggested name: `bookshopnearme`)
- [ ] **1.3** Navigate to **APIs & Services → Library**
- [ ] **1.4** Search for **Google Search Console API** → Enable it
- [ ] **1.5** Navigate to **IAM & Admin → Service Accounts → + Create Service Account**
  - Name: `bookshopnearme-gsc`
  - Description: `GSC data collection for BookShopNearMe.lk`
  - Skip role assignment (GSC manages its own permissions)
- [ ] **1.6** Open the service account → **Keys → Add Key → Create new key → JSON**
  - Save the downloaded file as `gsc-service-account.json` (do NOT place it in the repo)
- [ ] **1.7** Note the `client_email` value from the JSON file — you'll need it in Phase 2

---

### Phase 2 — Google Search Console Property
> Time: ~2 minutes | Requires: browser, GSC owner access for `https://bookshopnearme.lk/`

- [ ] **2.1** Go to [search.google.com/search-console](https://search.google.com/search-console)
- [ ] **2.2** Select property: `https://bookshopnearme.lk/`
- [ ] **2.3** Settings (gear icon) → **Users and permissions → Add user**
  - Email: paste the `client_email` from Phase 1 step 1.7
  - Permission: **Full**
- [ ] **2.4** Confirm the service account appears in the users list

---

### Phase 3 — Encode Credentials
> Time: ~1 minute | Requires: terminal

Run this in the directory where you saved `gsc-service-account.json`:

```bash
base64 -i gsc-service-account.json | tr -d '\n' | pbcopy
echo "Credentials copied to clipboard."
```

- [ ] **3.1** Command ran without error
- [ ] **3.2** Clipboard contains the base64 string (it will be very long — this is correct)

> Keep this in your clipboard — you'll paste it into Railway in Phase 5.

---

### Phase 4 — GitHub
> Time: ~2 minutes | Requires: terminal, GitHub account

```bash
# Create a new private repository on github.com first, then:
cd /Users/mohammedwalidnazmi/bookshopnearme-platform

git remote add origin git@github.com:YOUR_USERNAME/bookshopnearme-platform.git
git push -u origin main
```

- [ ] **4.1** Repo created on GitHub (set to Private)
- [ ] **4.2** `git push` succeeded
- [ ] **4.3** Confirm `.env` is NOT visible on GitHub (check the file list in the browser)
- [ ] **4.4** Confirm `gsc-service-account.json` is NOT visible on GitHub

---

### Phase 5 — Railway Project Setup
> Time: ~10 minutes | Requires: terminal + browser, Railway account

**Install Railway CLI (if not already installed):**
```bash
npm install -g @railway/cli
```

**Initialize project:**
```bash
cd /Users/mohammedwalidnazmi/bookshopnearme-platform
railway login
railway init
# When prompted: select Empty Project
# Project name: bookshopnearme-platform
```

- [ ] **5.1** Railway CLI installed
- [ ] **5.2** `railway login` succeeded
- [ ] **5.3** `railway init` completed, project visible in Railway dashboard

**Attach a Volume for SQLite persistence:**

In the Railway dashboard → your project → **+ New → Volume**:
- Volume name: `bookshop-data`
- Mount path: `/data`
- Attach to: `gsc-agent` service

- [ ] **5.4** Volume created and attached to gsc-agent service

---

### Phase 6 — Environment Variables
> Time: ~3 minutes | Requires: Railway dashboard

In Railway dashboard → `gsc-agent` service → **Variables**, add each row:

| Variable | Value |
|---|---|
| `DATABASE_PATH` | `/data/bookshop.db` |
| `GSC_CREDENTIALS_B64` | _(paste from clipboard — from Phase 3)_ |
| `GSC_SITE_URL` | `https://bookshopnearme.lk/` |
| `GSC_LOOKBACK_DAYS` | `7` |
| `LOG_LEVEL` | `INFO` |
| `ENVIRONMENT` | `production` |

- [ ] **6.1** `DATABASE_PATH` set to `/data/bookshop.db`
- [ ] **6.2** `GSC_CREDENTIALS_B64` set (value is a long base64 string, no newlines)
- [ ] **6.3** `GSC_SITE_URL` set — **must exactly match** the property in GSC including trailing slash
- [ ] **6.4** `GSC_LOOKBACK_DAYS` set to `7`
- [ ] **6.5** `LOG_LEVEL` set to `INFO`
- [ ] **6.6** `ENVIRONMENT` set to `production`

> Do NOT set `GSC_CREDENTIALS_PATH` — `GSC_CREDENTIALS_B64` takes priority automatically.

---

### Phase 7 — Deploy
> Time: ~3 minutes | Requires: terminal

```bash
cd /Users/mohammedwalidnazmi/bookshopnearme-platform
railway up
```

- [ ] **7.1** `railway up` completed without errors
- [ ] **7.2** Railway dashboard shows `gsc-agent` service with cron schedule `0 6 * * *`
- [ ] **7.3** Build logs show all three `pip install -e` commands succeeded

---

### Phase 8 — First Manual Run
> Time: ~2 minutes | Requires: terminal

Trigger immediately — do not wait for 06:00 UTC:

```bash
railway run --service gsc-agent python -m gsc_agent.agent
```

**Expected output:**
```
[STARTED]   agent=gsc_agent at=2026-...
Dates to collect: ['2026-05-30', '2026-05-31', ..., '2026-06-04']
Fetching GSC data for 2026-05-30
Saved 280 records for 2026-05-30
...
[COMPLETED] agent=gsc_agent duration=8.4s records=1940
```

**If you see an error instead, check:**

| Error message | Fix |
|---|---|
| `GSC credentials not found` | `GSC_CREDENTIALS_B64` not set or blank in Railway Variables |
| `HttpError 403` | Service account email not added to GSC property (Phase 2) |
| `HttpError 401` | `GSC_SITE_URL` doesn't exactly match the GSC property URL |
| `unable to open database` | Volume not attached or mount path mismatch |

- [ ] **8.1** Run completed with `[COMPLETED]` in output
- [ ] **8.2** At least one date shown in "Dates to collect"
- [ ] **8.3** At least 1 record saved (sites with any GSC data will have rows)

---

### Phase 9 — Verification Script
> Time: ~1 minute | Requires: terminal

```bash
railway run --service gsc-agent python scripts/verify.py --db /data/bookshop.db
```

**Expected output (after first successful run):**

```
── Schema ──────────────────────────────────────────────
  PASS  Table: agent_runs
  PASS  Table: content_opportunities
  PASS  Table: gsc_daily_metrics
  PASS  Table: gsc_pages
  PASS  Table: gsc_queries
  PASS  Table: schema_migrations
  PASS  Table: system_settings

── Agent Runs ──────────────────────────────────────────
  INFO  Last run: gsc_agent | COMPLETED | 2026-06-05 06:00 | 1940 records | 8.4s

── GSC Data ────────────────────────────────────────────
  PASS  GSC queries collected   (N unique queries)
  PASS  GSC pages collected     (N unique pages)
  PASS  PASS  GSC daily metrics collected  (N rows)

── Coverage Check (last 7 days) ────────────────────────
  PASS  2026-05-30  present
  PASS  2026-05-31  present
  PASS  2026-06-01  present
  PASS  2026-06-02  present
  WARN  2026-06-03  missing (GSC delay — expected)
  WARN  2026-06-04  missing (GSC delay — expected)
  WARN  2026-06-05  missing (GSC delay — expected)

── Summary ─────────────────────────────────────────────
  PASS  All checks passed.
```

The 2–3 most recent dates will show `WARN (GSC delay — expected)` — this is correct.

- [ ] **9.1** All Schema checks: PASS
- [ ] **9.2** At least one COMPLETED run in Agent Runs
- [ ] **9.3** GSC data checks: PASS (queries, pages, metrics > 0)
- [ ] **9.4** Coverage shows no unexpected gaps (only recent 3 days WARN is acceptable)

---

### Phase 10 — MCP Server (Local)
> Time: ~2 minutes | Requires: Claude Desktop installed

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bookshopnearme": {
      "command": "/Users/mohammedwalidnazmi/bookshopnearme-platform/.venv/bin/bookshopnearme-mcp"
    }
  }
}
```

Restart Claude Desktop.

- [ ] **10.1** Config file updated
- [ ] **10.2** Claude Desktop restarted
- [ ] **10.3** In a new Claude conversation, ask: *"Search for Harry Potter books"* — tool should be called and results returned

---

## Sprint 2 Gate

Do not begin Sprint 2 until **all** of the following are true:

- [ ] 3 or more consecutive `COMPLETED` runs in `agent_runs` (check daily after 06:00 UTC)
- [ ] 5 or more distinct dates in `gsc_daily_metrics`
- [ ] Top queries in verify output show real BookShopNearMe.lk search terms
- [ ] No `FAILED` runs in the past 7 days
- [ ] Verify script shows zero unexpected gaps in coverage

Run verify after each cron fires:
```bash
railway run --service gsc-agent python scripts/verify.py --db /data/bookshop.db
```

**When the Sprint 2 gate is met:** share the verify output and the collected baseline data. Sprint 2 (DataForSEO integration) will be scoped from actual search terms, not assumptions.

---

## Reference

| File | Purpose |
|------|---------|
| [`railway.toml`](railway.toml) | Cron schedule, build command, restart policy |
| [`apps/gsc-agent/gsc_agent/credentials.py`](apps/gsc-agent/gsc_agent/credentials.py) | B64 vs file credential resolution |
| [`shared/database/migrations.py`](shared/database/migrations.py) | Schema version history |
| [`scripts/verify.py`](scripts/verify.py) | Post-deployment health check |
| [`docs/deployment.md`](docs/deployment.md) | Full deployment narrative |
| [`docs/configuration.md`](docs/configuration.md) | All environment variables |
