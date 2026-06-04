# Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and fill in values.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `./data/bookshop.db` | Path to the SQLite database file |
| `BOOKS_API_BASE_URL` | Supabase URL | Base URL for the BookShopNearMe books API |
| `BOOKS_API_TIMEOUT` | `60` | HTTP request timeout in seconds |
| `GSC_CREDENTIALS_PATH` | _(required)_ | Path to Google service account JSON |
| `GSC_SITE_URL` | _(required)_ | Site URL as registered in GSC (e.g. `https://bookshopnearme.lk/`) |
| `GSC_LOOKBACK_DAYS` | `7` | Days to look back when collecting GSC data |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ENVIRONMENT` | `development` | `development` or `production` |

## Google Search Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Search Console API**
3. Create a **Service Account** with no roles
4. Download the JSON key file → set `GSC_CREDENTIALS_PATH` to its path
5. In Search Console, add the service account email as a **Verified Owner** or at least **Full User**
6. Set `GSC_SITE_URL` to the exact property URL in GSC (including trailing slash for URL-prefix properties)
