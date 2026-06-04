# Sprint Roadmap

## Sprint 1 — Foundation (COMPLETED)

- [x] `bookshopnearme-mcp`: PyPI/Smithery/Glama-ready MCP server with 6 tools
- [x] GSC Agent: daily data collection with full history storage
- [x] SQLite database with migration system
- [x] Structured logging with per-agent run tracking
- [x] Railway deployment configuration
- [x] Unit test suite (MCP client, database, GSC ingestion, logging)
- [x] Seed data for local development
- [x] Documentation (install, config, deploy, schema)

---

## Sprint 2 — DataForSEO Integration (STUB)

> **Status**: Placeholder only. Do not implement until Sprint 2 begins.

- [ ] `apps/dataseo-agent/`: DataForSEO keyword research agent
  - Fetch search volume, CPC, competition data for keywords
  - Enrich `content_opportunities` rows sourced from GSC
  - Tables: extend `content_opportunities` with DataForSEO fields
- [ ] Keyword difficulty scoring pipeline
- [ ] `DATASEO_API_KEY` environment variable
- [ ] Rate-limiting and quota management for DataForSEO API

---

## Sprint 3 — Catalog Intelligence (STUB)

> **Status**: Placeholder only. Do not implement until Sprint 3 begins.

- [ ] `apps/catalog-agent/`: Cross-reference search demand against book catalog
  - Query MCP for each content opportunity keyword
  - Populate `book_available` field in `content_opportunities`
  - Track catalog coverage gaps
- [ ] Catalog coverage dashboard data export (CSV/JSON)

---

## Sprint 4 — Content Workflow (STUB)

> **Status**: Placeholder only. Do not implement until Sprint 4 begins.

- [ ] `apps/blog-agent/`: AI-powered blog post drafting
  - Input: approved `content_opportunities`
  - Output: draft blog posts in Markdown
  - Integration with Shopify Blog API
- [ ] Shopify Importer: push blog posts to Shopify store

---

## Sprint 5 — Optimization & Orchestration (STUB)

> **Status**: Placeholder only. Do not implement until Sprint 5 begins.

- [ ] `apps/optimization-agent/`: Monitor RANKING content opportunities
  - Track position changes over time
  - Suggest content updates for declining pages
- [ ] `apps/orchestrator/`: Master scheduler
  - Coordinate all agents on a cron schedule
  - Slack/email notifications on failures
- [ ] Google Trends integration for demand signals
