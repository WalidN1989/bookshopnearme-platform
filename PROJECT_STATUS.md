# PROJECT_STATUS.md

_Last updated: 2026-06-04_

---

## Completed Features (Sprint 1)

### bookshopnearme-mcp
- `search_books` — full-text search across the catalog
- `get_book` — retrieve a single book by ID
- `search_by_isbn` — ISBN-10/13 lookup
- `find_books_by_author` — author-filtered browse
- `find_books_by_category` — category-filtered browse
- `catalog_stats` — aggregate catalog statistics
- 60-second in-process response cache
- PyPI-ready (`pyproject.toml` with hatchling)
- Smithery-ready (`smithery.yaml`)
- Glama-ready (`glama.yaml`)

### GSC Agent
- Daily collection of impressions, clicks, CTR, position per query+page pair
- Full history storage (upsert-safe, no duplicates)
- Automatic detection of missing dates in the lookback window
- Structured run logging with duration and record count

### Database (SQLite)
- Migration system with version tracking (`schema_migrations`)
- Tables: `gsc_queries`, `gsc_pages`, `gsc_daily_metrics`, `agent_runs`, `system_settings`, `content_opportunities`
- All tables include `created_at`, `updated_at`
- WAL mode enabled for concurrency

### Infrastructure
- `railway.toml` for production deployment
- `.env.example` with all variables documented
- `scripts/seed.py` for local development seed data
- Full documentation (install, config, deploy, schema, roadmap)

### Tests
- `test_mcp_client.py` — API client + caching
- `test_database.py` — migrations, upserts, CRUD
- `test_logging.py` — AgentRunLogger lifecycle
- `test_gsc_ingestion.py` — ingest rows, idempotency, date gap detection

---

## Future Sprint Placeholders

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 2 | DataForSEO keyword enrichment agent | Not started |
| Sprint 3 | Catalog intelligence (demand × availability) | Not started |
| Sprint 4 | Blog Agent + Shopify Importer | Not started |
| Sprint 5 | Optimization Agent + Orchestrator | Not started |

See [docs/sprint_roadmap.md](docs/sprint_roadmap.md) for details.

---

## Technical Debt

- `BooksApiClient` cache is in-process only (resets on restart). A persistent cache (Redis or SQLite) would be appropriate at scale.
- GSC Agent collects up to 5000 rows per date. Sites with more than 5000 query+page combinations per day will need pagination via the GSC API offset parameter.
- `get_db()` uses a module-level singleton, which is not safe for multi-threaded use without a connection pool.
- No retry logic on HTTP errors in the MCP client.

---

## Known Limitations

- **GSC data delay**: Google Search Console data is typically 2–3 days delayed. The agent collects from "yesterday" backward, which means very recent data may not appear immediately.
- **SQLite concurrency**: SQLite with WAL mode handles multiple readers and one writer. For high-concurrency writes (multiple agents running simultaneously), consider PostgreSQL in a later sprint.
- **MCP server is stateless**: No authentication or rate-limiting. Suitable for internal/local use; add a proxy layer before public exposure.
- **No retry logic**: If the GSC API or Books API returns a transient error, the agent fails the entire run. Retries are a Sprint 2 concern.
- **Railway SQLite persistence**: SQLite databases on Railway require a Volume to survive deployments. Without a Volume, data is lost on redeploy.
