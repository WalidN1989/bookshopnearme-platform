# Database Schema

SQLite database managed with a version-controlled migration system (`shared/database/migrations.py`).

## Migration System

Migrations are applied automatically on first connection. Each migration is tracked in `schema_migrations`. Running migrations twice is safe (idempotent).

---

## Tables

### `schema_migrations`
Tracks applied migrations.

| Column | Type | Notes |
|--------|------|-------|
| `version` | INTEGER PK | Migration version number |
| `description` | TEXT | Human-readable name |
| `applied_at` | TEXT | ISO datetime |

---

### `system_settings`
Key-value store for runtime configuration and state.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `key` | TEXT UNIQUE | Setting name |
| `value` | TEXT | Setting value |
| `created_at` | TEXT | |
| `updated_at` | TEXT | |

---

### `agent_runs`
Audit log of every agent execution.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `agent_name` | TEXT | e.g. `gsc_agent` |
| `status` | TEXT | `STARTED`, `COMPLETED`, `FAILED` |
| `started_at` | TEXT | ISO datetime |
| `duration_seconds` | REAL | Wall time |
| `records_processed` | INTEGER | |
| `error_message` | TEXT | Populated on FAILED |
| `metadata` | TEXT | JSON blob |
| `created_at` | TEXT | |
| `updated_at` | TEXT | |

---

### `gsc_queries`
Deduplicated index of all GSC search queries seen.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `query` | TEXT UNIQUE | |
| `first_seen` | TEXT | Date first collected |
| `last_seen` | TEXT | Date last collected |
| `created_at` | TEXT | |
| `updated_at` | TEXT | |

---

### `gsc_pages`
Deduplicated index of all GSC page URLs seen.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `page_url` | TEXT UNIQUE | |
| `first_seen` | TEXT | |
| `last_seen` | TEXT | |
| `created_at` | TEXT | |
| `updated_at` | TEXT | |

---

### `gsc_daily_metrics`
One row per (date, query, page) combination. Upserted on each collection run.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `date` | TEXT | `YYYY-MM-DD` |
| `query_id` | INTEGER FK | → `gsc_queries.id` |
| `page_id` | INTEGER FK | → `gsc_pages.id` |
| `impressions` | INTEGER | |
| `clicks` | INTEGER | |
| `ctr` | REAL | Click-through rate (0–1) |
| `position` | REAL | Average search position |
| `created_at` | TEXT | |
| `updated_at` | TEXT | |

Unique constraint on `(date, query_id, page_id)`.

---

### `content_opportunities`
Keyword and content gap tracking across all data sources.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `keyword` | TEXT | |
| `search_volume` | INTEGER | Monthly searches (nullable) |
| `difficulty` | REAL | SEO difficulty 0–1 (nullable) |
| `book_available` | INTEGER | Boolean: 1 = in catalog |
| `priority_score` | REAL | Calculated score (nullable) |
| `source` | TEXT | `GSC`, `DATASEO`, `GOOGLE_TRENDS`, `MANUAL` |
| `status` | TEXT | `NEW` → `RESEARCHED` → `APPROVED` → `WRITING` → `PUBLISHED` → `RANKING` |
| `notes` | TEXT | |
| `created_at` | TEXT | |
| `updated_at` | TEXT | |
